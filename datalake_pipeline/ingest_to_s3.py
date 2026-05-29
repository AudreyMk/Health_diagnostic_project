"""
=============================================================================
Pipeline d'ingestion des donnees medicales vers AWS S3
Projet M2 - Outil IA de suggestion de pathologies (RAG)
=============================================================================

Sources de donnees :
  1. DDXPlus (FR)  - symptomes/pathologies/patients  -> s3://BUCKET/raw/ddxplus/
  2. FINESS        - etablissements de sante          -> s3://BUCKET/raw/finess/
  3. CSV existant  - combined_medical_data.csv         -> s3://BUCKET/raw/symptom_csv/

Prerequis :
  pip install boto3 requests tqdm python-dotenv --break-system-packages

Configuration AWS :
  - Via le fichier .env dans ce dossier (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)
  - Ou via ~/.aws/credentials (aws configure)
  - Ou via un role IAM si execute sur EC2/Lambda

Usage :
  # Tout ingerer (bucket depuis .env)
  python ingest_to_s3.py

  # Specifier le bucket manuellement
  python ingest_to_s3.py --bucket datalake-rduf6fuy93mcos7fgtyaoy8h5or4neun1a-s3alias --region eu-north-1

  # Seulement DDXPlus et FINESS
  python ingest_to_s3.py --sources ddxplus finess

  # Seulement le CSV existant
  python ingest_to_s3.py --sources csv --csv-path ../combined_medical_data.csv
"""

import os
import sys
import json
import zipfile
import argparse
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Charger les variables du fichier .env
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Bucket par defaut depuis .env
DEFAULT_BUCKET = os.getenv(
    "S3_BUCKET_ALIAS",
    "datalake-rduf6fuy93mcos7fgtyaoy8h5or4neun1a-s3alias"
)
DEFAULT_REGION = os.getenv("AWS_REGION", "eu-north-1")

# DDXPlus FR (figshare) -- version francaise originale
# L'article figshare : https://figshare.com/articles/dataset/DDXPlus_Dataset_French/20043374
# Les URLs sont recuperees dynamiquement via l'API pour eviter les liens expires
DDXPLUS_FIGSHARE_ARTICLE_ID = 20043374
DDXPLUS_FILES_WANTED = {
    "release_conditions.json",
    "release_evidences.json",
    "release_train_patients.zip",
    "release_validate_patients.zip",
    "release_test_patients.zip",
}

# FINESS - etablissements de sante (data.gouv.fr)
FINESS_FILES = {
    "finess_etablissements.csv": (
        "https://www.data.gouv.fr/api/1/datasets/r/98f3161f-79ff-4f16-8f6a-6d571a80fea2"
    ),
    "finess_geolocalisation.csv": (
        "https://www.data.gouv.fr/api/1/datasets/r/2ce43ade-8d2c-4d1d-81da-ca06c82abc68"
    ),
}

# CSV local par defaut (dossier parent du script)
DEFAULT_CSV_PATH = str(Path(__file__).parent.parent / "combined_medical_data.csv")

WORK_DIR = Path("/tmp/medical_data_ingestion")
CHUNK_SIZE = 8 * 1024 * 1024  # 8 Mo pour le multipart upload S3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classes (POO)
# ---------------------------------------------------------------------------


class S3Manager:
    """Gestion des interactions avec AWS S3."""

    def __init__(self, bucket_name: str, region: str = "eu-north-1"):
        self.bucket_name = bucket_name
        self.region = region
        session_kwargs = {"region_name": region}

        # Credentials explicites si presents dans l'environnement
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        session_token = os.getenv("AWS_SESSION_TOKEN")

        if access_key and secret_key:
            session_kwargs["aws_access_key_id"] = access_key
            session_kwargs["aws_secret_access_key"] = secret_key
            if session_token:
                session_kwargs["aws_session_token"] = session_token

        session = boto3.Session(**session_kwargs)
        self.s3_client = session.client("s3")
        self.s3_resource = session.resource("s3")

    def check_bucket_access(self) -> bool:
        """Verifie l'acces au bucket (supporte les alias S3)."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket accessible : {self.bucket_name}")
            return True
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("301", "PermanentRedirect"):
                # L'alias pointe vers une region differente — on accepte quand meme
                logger.info(f"Bucket accessible (redirection region) : {self.bucket_name}")
                return True
            logger.error(f"Acces refuse au bucket ({code}) : {self.bucket_name}")
            return False

    def ensure_bucket_exists(self) -> None:
        """Verifie ou cree le bucket S3."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' existe et est accessible.")
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("301", "PermanentRedirect"):
                logger.info(f"Bucket accessible via alias : {self.bucket_name}")
                return
            if code == "404":
                logger.info(f"Creation du bucket '{self.bucket_name}' dans {self.region}...")
                if self.region == "us-east-1":
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                else:
                    self.s3_client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": self.region},
                    )
                self.s3_client.put_public_access_block(
                    Bucket=self.bucket_name,
                    PublicAccessBlockConfiguration={
                        "BlockPublicAcls": True,
                        "IgnorePublicAcls": True,
                        "BlockPublicPolicy": True,
                        "RestrictPublicBuckets": True,
                    },
                )
                self.s3_client.put_bucket_versioning(
                    Bucket=self.bucket_name,
                    VersioningConfiguration={"Status": "Enabled"},
                )
                logger.info(f"Bucket '{self.bucket_name}' cree avec succes.")
            else:
                raise

    def upload_file(self, local_path: Path, s3_key: str) -> None:
        """Upload un fichier local vers S3 avec multipart pour les gros fichiers."""
        file_size = local_path.stat().st_size
        size_mb = file_size / (1024 * 1024)

        # Calcul du MD5 pour l'integrite
        md5 = hashlib.md5()
        with open(local_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        content_md5 = md5.hexdigest()

        extra_args = {
            "Metadata": {
                "source-md5": content_md5,
                "ingestion-date": datetime.now(timezone.utc).isoformat(),
                "pipeline-version": "1.0.0",
            }
        }

        suffix = local_path.suffix.lower()
        content_types = {
            ".csv":     "text/csv",
            ".json":    "application/json",
            ".zip":     "application/zip",
            ".parquet": "application/octet-stream",
        }
        if suffix in content_types:
            extra_args["ContentType"] = content_types[suffix]

        logger.info(
            f"Upload {local_path.name} ({size_mb:.1f} Mo) "
            f"-> s3://{self.bucket_name}/{s3_key}"
        )

        from boto3.s3.transfer import TransferConfig
        config = TransferConfig(
            multipart_threshold=CHUNK_SIZE,
            multipart_chunksize=CHUNK_SIZE,
            max_concurrency=4,
        )

        self.s3_client.upload_file(
            str(local_path),
            self.bucket_name,
            s3_key,
            ExtraArgs=extra_args,
            Config=config,
        )
        logger.info(f"  -> OK (md5: {content_md5})")

    def upload_manifest(self, manifest: dict, s3_key: str) -> None:
        """Upload un fichier manifeste JSON dans S3."""
        body = json.dumps(manifest, indent=2, ensure_ascii=False, default=str)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(f"Manifeste uploade -> s3://{self.bucket_name}/{s3_key}")


class DataDownloader:
    """Telecharge les fichiers sources depuis les URLs publiques."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "MedRAG-Ingestion/1.0"})

    def download_file(self, url: str, filename: str, subdir: str = "") -> Path:
        """Telecharge un fichier avec barre de progression, gestion des redirections et retry."""
        target_dir = self.work_dir / subdir if subdir else self.work_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename

        if target_path.exists() and target_path.stat().st_size > 1024:
            logger.info(f"  {filename} deja present localement ({target_path.stat().st_size / 1e6:.1f} Mo), skip.")
            return target_path

        logger.info(f"  Telechargement de {filename}...")

        # Suivre toutes les redirections (important pour figshare -> CDN)
        response = self.session.get(
            url,
            stream=True,
            timeout=600,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; MedRAG-Ingestion/1.0)",
                "Accept": "*/*",
            },
        )
        response.raise_for_status()

        # Verifier que la reponse est bien du contenu binaire (pas du HTML)
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            raise ValueError(
                f"Figshare a retourne du HTML pour {filename}. "
                f"URL possiblement invalide ou acces restreint. URL: {url}"
            )

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        print(
                            f"\r    {downloaded / 1e6:.1f}/{total_size / 1e6:.1f} Mo ({pct:.0f}%)",
                            end="", flush=True,
                        )
            print()

        final_size = target_path.stat().st_size
        if final_size < 1024:
            target_path.unlink(missing_ok=True)
            raise ValueError(
                f"Fichier telecharge trop petit ({final_size} octets) pour {filename}. "
                f"Le telechargement a echoue ou l'URL a change."
            )

        logger.info(f"  -> {filename} telecharge ({final_size / 1e6:.1f} Mo)")
        return target_path

    def unzip_file(self, zip_path: Path, extract_dir: Optional[Path] = None) -> list[Path]:
        """Extrait un fichier ZIP et retourne la liste des fichiers extraits."""
        if extract_dir is None:
            extract_dir = zip_path.parent

        # Valider que c'est bien un ZIP avant d'essayer d'extraire
        if not zipfile.is_zipfile(zip_path):
            raise zipfile.BadZipFile(
                f"{zip_path.name} n'est pas un fichier ZIP valide "
                f"(taille: {zip_path.stat().st_size} octets). "
                f"Le telechargement est peut-etre incomplet."
            )

        extracted = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                zf.extract(member, extract_dir)
                extracted.append(extract_dir / member)
                logger.info(f"    Extrait: {member}")
        return extracted


class DDXPlusIngestion:
    """Ingestion du dataset DDXPlus (FR) vers S3."""

    S3_PREFIX = "raw/ddxplus"
    FIGSHARE_API = "https://api.figshare.com/v2/articles/{article_id}/files"

    def __init__(self, downloader: DataDownloader, s3_manager: S3Manager):
        self.downloader = downloader
        self.s3 = s3_manager
        self.files_uploaded: list[str] = []

    def _get_figshare_urls(self) -> dict[str, str]:
        """Recuperer les vraies URLs de telechargement via l'API Figshare."""
        api_url = self.FIGSHARE_API.format(article_id=DDXPLUS_FIGSHARE_ARTICLE_ID)
        logger.info(f"Recuperation des URLs via API Figshare : {api_url}")
        resp = requests.get(api_url, timeout=30)
        resp.raise_for_status()
        files_info = resp.json()
        urls = {
            f["name"]: f["download_url"]
            for f in files_info
            if f["name"] in DDXPLUS_FILES_WANTED
        }
        logger.info(f"URLs recuperees : {list(urls.keys())}")
        return urls

    def run(self) -> dict:
        """Execute l'ingestion complete de DDXPlus."""
        logger.info("=" * 60)
        logger.info("INGESTION DDXPlus (version francaise)")
        logger.info("=" * 60)

        # Recuperer les URLs actuelles depuis l'API Figshare
        try:
            ddxplus_files = self._get_figshare_urls()
        except Exception as e:
            logger.error(f"Impossible de contacter l'API Figshare : {e}")
            logger.warning("Passage en mode offline : verifiez /tmp/medical_data_ingestion/ddxplus/")
            ddxplus_files = {}

        for filename, url in ddxplus_files.items():
            try:
                local_path = self.downloader.download_file(url, filename, subdir="ddxplus")

                if filename.endswith(".zip"):
                    extracted = self.downloader.unzip_file(local_path)
                    for ext_file in extracted:
                        s3_key = f"{self.S3_PREFIX}/{ext_file.name}"
                        self.s3.upload_file(ext_file, s3_key)
                        self.files_uploaded.append(s3_key)
                else:
                    s3_key = f"{self.S3_PREFIX}/{filename}"
                    self.s3.upload_file(local_path, s3_key)
                    self.files_uploaded.append(s3_key)

            except (ValueError, zipfile.BadZipFile) as e:
                logger.warning(f"  IGNORE {filename}: {e}")
                logger.warning(f"  -> URL : {url}")

        manifest = {
            "source": "DDXPlus",
            "version": "FR-original",
            "license": "CC-BY-4.0",
            "paper": "https://arxiv.org/abs/2205.09148",
            "figshare": "https://figshare.com/articles/dataset/DDXPlus_Dataset/20043374",
            "files": self.files_uploaded,
            "ingestion_date": datetime.now(timezone.utc).isoformat(),
            "description": (
                "Dataset synthetique de ~1.3M patients avec diagnostic differentiel, "
                "49 pathologies, symptomes et antecedents. Version francaise."
            ),
        }
        self.s3.upload_manifest(manifest, f"{self.S3_PREFIX}/_manifest.json")
        logger.info(f"DDXPlus: {len(self.files_uploaded)} fichiers uploades.")
        return manifest


class FINESSIngestion:
    """Ingestion du dataset FINESS vers S3."""

    S3_PREFIX = "raw/finess"

    def __init__(self, downloader: DataDownloader, s3_manager: S3Manager):
        self.downloader = downloader
        self.s3 = s3_manager
        self.files_uploaded: list[str] = []

    def run(self) -> dict:
        """Execute l'ingestion complete de FINESS."""
        logger.info("=" * 60)
        logger.info("INGESTION FINESS (etablissements de sante)")
        logger.info("=" * 60)

        for filename, url in FINESS_FILES.items():
            local_path = self.downloader.download_file(url, filename, subdir="finess")
            s3_key = f"{self.S3_PREFIX}/{filename}"
            self.s3.upload_file(local_path, s3_key)
            self.files_uploaded.append(s3_key)

        manifest = {
            "source": "FINESS",
            "license": "Licence Ouverte / Open Licence",
            "origin": "https://www.data.gouv.fr/datasets/finess-extraction-du-fichier-des-etablissements",
            "producer": "Ministere des Solidarites et de la Sante",
            "files": self.files_uploaded,
            "ingestion_date": datetime.now(timezone.utc).isoformat(),
            "description": (
                "Liste des etablissements sanitaires et sociaux de France "
                "avec geolocalisation. Mis a jour tous les 2 mois."
            ),
            "warning": "Le flux FINESS actuel sera arrete a l'ete 2026. Migrer vers le flux ANS.",
        }
        self.s3.upload_manifest(manifest, f"{self.S3_PREFIX}/_manifest.json")
        logger.info(f"FINESS: {len(self.files_uploaded)} fichiers uploades.")
        return manifest


class CSVIngestion:
    """Ingestion du CSV symptomes/pathologies existant vers S3."""

    S3_PREFIX = "raw/symptom_csv"

    def __init__(self, s3_manager: S3Manager):
        self.s3 = s3_manager
        self.files_uploaded: list[str] = []

    def run(self, csv_path: str) -> dict:
        """Upload le CSV local vers S3."""
        logger.info("=" * 60)
        logger.info("INGESTION CSV symptomes/pathologies")
        logger.info("=" * 60)

        local_path = Path(csv_path)
        if not local_path.exists():
            raise FileNotFoundError(f"CSV introuvable: {csv_path}")

        s3_key = f"{self.S3_PREFIX}/{local_path.name}"
        self.s3.upload_file(local_path, s3_key)
        self.files_uploaded.append(s3_key)

        manifest = {
            "source": "combined_medical_data.csv",
            "license": "A verifier (probablement derive de Kaggle/HuggingFace)",
            "files": self.files_uploaded,
            "ingestion_date": datetime.now(timezone.utc).isoformat(),
            "description": (
                "CSV avec 5580 lignes, 27 pathologies, format label/text. "
                "Donnees synthetiques en anglais. A utiliser comme jeu de test."
            ),
            "known_issues": [
                "Distribution desequilibree (6 pathologies dominent)",
                "Seulement 27 pathologies",
                "Anglais uniquement",
                "47 doublons exacts",
            ],
        }
        self.s3.upload_manifest(manifest, f"{self.S3_PREFIX}/_manifest.json")
        logger.info(f"CSV: {len(self.files_uploaded)} fichiers uploades.")
        return manifest


class IngestionPipeline:
    """Pipeline principal d'orchestration de l'ingestion."""

    def __init__(self, bucket: str, region: str = "eu-north-1"):
        self.s3 = S3Manager(bucket, region)
        self.downloader = DataDownloader(WORK_DIR)
        self.manifests: dict = {}

    def run(self, sources: list[str], csv_path: Optional[str] = None) -> dict:
        """Execute l'ingestion pour les sources demandees."""
        start_time = datetime.now(timezone.utc)

        logger.info("=" * 60)
        logger.info("PIPELINE D'INGESTION MEDICALE -> AWS S3")
        logger.info(f"Bucket : {self.s3.bucket_name}")
        logger.info(f"Region : {self.s3.region}")
        logger.info(f"Sources: {', '.join(sources)}")
        logger.info("=" * 60)

        self.s3.ensure_bucket_exists()

        if "ddxplus" in sources:
            ingestor = DDXPlusIngestion(self.downloader, self.s3)
            self.manifests["ddxplus"] = ingestor.run()

        if "finess" in sources:
            ingestor = FINESSIngestion(self.downloader, self.s3)
            self.manifests["finess"] = ingestor.run()

        if "csv" in sources:
            if not csv_path:
                raise ValueError("--csv-path requis quand la source 'csv' est specifiee.")
            ingestor = CSVIngestion(self.s3)
            self.manifests["csv"] = ingestor.run(csv_path)

        end_time = datetime.now(timezone.utc)
        global_manifest = {
            "pipeline": "medical-rag-ingestion",
            "version": "1.0.0",
            "bucket": self.s3.bucket_name,
            "region": self.s3.region,
            "sources_ingested": list(self.manifests.keys()),
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "duration_seconds": (end_time - start_time).total_seconds(),
            "s3_structure": {
                "raw/ddxplus/":     "DDXPlus FR - 1.3M patients, 49 pathologies, symptomes, antecedents",
                "raw/finess/":      "FINESS - etablissements sanitaires et sociaux, geolocalises",
                "raw/symptom_csv/": "CSV symptomes/pathologies (anglais, 27 pathologies)",
            },
            "next_steps": [
                "Etape suivante: nettoyage et structuration (DataProcessor)",
                "Puis: vectorisation et stockage dans pgvector (EmbeddingManager)",
                "Les fichiers DDXPlus necessitent une conversion en texte libre pour le RAG",
            ],
        }
        self.s3.upload_manifest(global_manifest, "_global_manifest.json")

        logger.info("")
        logger.info("=" * 60)
        logger.info("INGESTION TERMINEE")
        logger.info(f"Duree  : {global_manifest['duration_seconds']:.1f}s")
        logger.info(f"Sources: {', '.join(self.manifests.keys())}")
        logger.info("=" * 60)

        self._print_s3_tree()
        return global_manifest

    def _print_s3_tree(self) -> None:
        """Affiche l'arborescence des fichiers dans le bucket."""
        logger.info("")
        logger.info(f"Arborescence s3://{self.s3.bucket_name}/")
        logger.info("-" * 50)
        try:
            paginator = self.s3.s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.s3.bucket_name):
                for obj in page.get("Contents", []):
                    size_mb = obj["Size"] / (1024 * 1024)
                    logger.info(f"  {obj['Key']:55s} {size_mb:8.1f} Mo")
        except ClientError as e:
            logger.warning(f"Impossible de lister le bucket : {e}")


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pipeline d'ingestion des donnees medicales vers AWS S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Tout ingerer (bucket et region depuis .env)
  python ingest_to_s3.py

  # Specifier le bucket manuellement
  python ingest_to_s3.py --bucket datalake-rduf6fuy93mcos7fgtyaoy8h5or4neun1a-s3alias

  # Seulement DDXPlus et FINESS
  python ingest_to_s3.py --sources ddxplus finess

  # Seulement le CSV existant
  python ingest_to_s3.py --sources csv --csv-path ../combined_medical_data.csv
        """,
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"Nom/alias du bucket S3 (defaut depuis .env : {DEFAULT_BUCKET})",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"Region AWS (defaut depuis .env : {DEFAULT_REGION})",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["ddxplus", "finess", "csv"],
        choices=["ddxplus", "finess", "csv"],
        help="Sources a ingerer (defaut: toutes)",
    )
    parser.add_argument(
        "--csv-path",
        default=DEFAULT_CSV_PATH,
        help=f"Chemin vers le CSV (defaut: {DEFAULT_CSV_PATH})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    pipeline = IngestionPipeline(bucket=args.bucket, region=args.region)
    pipeline.run(sources=args.sources, csv_path=args.csv_path)


if __name__ == "__main__":
    main()

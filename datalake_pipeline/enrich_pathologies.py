"""
enrich_pathologies.py — Phase B MedRAG v2

Pour chacune des 49 pathologies DDXPlus :
  1. Lit release_conditions.json + release_evidences.json
  2. Enrichit via l'API ICD-11 WHO  (code ICD-11, définition clinique)
  3. Enrichit via Wikipedia FR      (description narrative paragraphe)
  4. Construit le champ `text` dense qui sera vectorisé
  5. Écrit processed/ddxplus_pathology_documents.jsonl

Usage :
  cd datalake_pipeline/
  python enrich_pathologies.py \
      --conditions  raw/ddxplus/release_conditions.json \
      --evidences   raw/ddxplus/release_evidences.json \
      --output-dir  processed/

  # Avec ICD-11 (facultatif — améliore la qualité) :
  python enrich_pathologies.py ... \
      --icd11-client-id  YOUR_CLIENT_ID \
      --icd11-client-secret YOUR_CLIENT_SECRET

  # Ou via variables d'env (.env) :
  ICD11_CLIENT_ID=...  ICD11_CLIENT_SECRET=...  python enrich_pathologies.py ...

Inscription ICD-11 API (gratuit) : https://icd.who.int/icdapi

Le cache est sauvegardé dans .cache/ pour reprendre sans re-requêter l'API.
"""

import hashlib
import json
import logging
import argparse
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

ICD11_TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
ICD11_SEARCH_URL = "https://id.who.int/icd/entity/search"
WIKI_SUMMARY_URL = "https://fr.wikipedia.org/api/rest_v1/page/summary"

# Traduction des codes DDXPlus (symptômes + antécédents) en français lisible.
# Nécessaire car les clés du fichier conditions ne correspondent pas aux clés
# du fichier evidences (qui utilise des codes E_xx).
SYMPTOM_LABELS: dict[str, str] = {
    # --- Symptômes ---
    "adp_dlr":                   "Adénopathies douloureuses",
    "angor_accelere":            "Angine de poitrine s'accélérant",
    "angor_repos":               "Douleur thoracique au repos",
    "anxiete_s":                 "Anxiété importante",
    "apnee":                     "Apnées",
    "ballon_abdo":               "Ballonnement abdominal",
    "boire_ped":                 "Difficultés à boire (pédiatrique)",
    "bw_bending":                "Aggravé en se penchant en avant",
    "claud_mâchoire":            "Claudication de la mâchoire",
    "confusion":                 "Confusion mentale",
    "contact_allergie":          "Contact avec un allergène",
    "convulsion":                "Convulsions",
    "crach_sg":                  "Crachats sanglants (hémoptysie)",
    "diaph":                     "Transpiration excessive",
    "diarrhee":                  "Diarrhée",
    "diplopie":                  "Vision double (diplopie)",
    "douleurxx":                 "Douleur quelque part",
    "douleurxx_carac":           "Caractère de la douleur",
    "douleurxx_endroitducorps":  "Localisation de la douleur",
    "douleurxx_intens":          "Intensité de la douleur",
    "douleurxx_irrad":           "Irradiation de la douleur",
    "douleurxx_precis":          "Douleur précise au toucher",
    "douleurxx_soudain":         "Début soudain de la douleur",
    "dysarthrie":                "Dysarthrie (trouble de l'articulation)",
    "dysp_effort":               "Essoufflement à l'effort",
    "dysphagie":                 "Dysphagie (difficulté à avaler)",
    "dyspn":                     "Dyspnée (essoufflement)",
    "dyspn_noct":                "Dyspnée nocturne",
    "erytheme_occ":              "Érythème oculaire",
    "etouff":                    "Sensation d'étouffement",
    "etourdissement":            "Étourdissements / vertiges",
    "expecto":                   "Expectorations",
    "faible":                    "Faiblesse générale",
    "faiblesse faciale":         "Faiblesse faciale",
    "faiblesse_msmi":            "Faiblesse des membres",
    "fatig_ext":                 "Fatigue extrême",
    "fatig_mod":                 "Fatigue modérée",
    "fatigabilité_msk":          "Fatigabilité musculaire",
    "fievre":                    "Fièvre",
    "flushing":                  "Bouffées vasomotrices (flushing)",
    "footnumb":                  "Engourdissement des pieds",
    "friss":                     "Frissons",
    "gain_poids":                "Prise de poids",
    "gorge_dlr":                 "Mal de gorge",
    "hyponos":                   "Diminution de l'odorat",
    "impression_mort":           "Sentiment de mort imminente",
    "insp_siffla":               "Stridor inspiratoire (inspiration sifflante)",
    "irritable":                 "Irritabilité",
    "larmes":                    "Larmoiement",
    "laryngospasme":             "Laryngospasme",
    "lesions_peau":              "Lésions cutanées",
    "lesions_peau_couleur":      "Couleur des lésions cutanées",
    "lesions_peau_desquame":     "Lésions cutanées desquamatives",
    "lesions_peau_elevee":       "Lésions cutanées surélevées",
    "lesions_peau_endroitducorps": "Localisation des lésions cutanées",
    "lesions_peau_intens":       "Intensité des lésions cutanées",
    "lesions_peau_plusqu1cm":    "Lésions cutanées > 1 cm",
    "lesions_peau_prurit":       "Lésions cutanées prurigineuses",
    "melena":                    "Méléna (selles noires)",
    "ménorr":                    "Ménorragies",
    "msk_dlr":                   "Douleurs musculosquelettiques",
    "nausee":                    "Nausées",
    "obstipation":               "Constipation sévère",
    "oedeme":                    "Œdème",
    "oedeme_endroitducorps":     "Localisation de l'œdème",
    "pale":                      "Pâleur",
    "palpit":                    "Palpitations",
    "paralysie_visage":          "Paralysie faciale",
    "paresthesies_bilat":        "Paresthésies bilatérales",
    "pdc":                       "Perte de connaissance",
    "perte_appet":               "Perte d'appétit",
    "perte_poids":               "Perte de poids",
    "pertes_vag":                "Pertes vaginales",
    "pls_irreg":                 "Pouls irrégulier",
    "posttus_emesis":            "Vomissements post-tussifs",
    "protu_langue":              "Protrusion de la langue",
    "prurit_nasal":              "Prurit nasal",
    "prurit_occ":                "Prurit oculaire",
    "psy_depers":                "Dépersonnalisation / déréalisation",
    "ptose":                     "Ptose palpébrale",
    "pyrosis":                   "Pyrosis (brûlures remontantes)",
    "rds_anorexie":              "Anorexie",
    "rds_deg":                   "Dégradation de l'état général",
    "rds_paralys_gen":           "Paralysie généralisée",
    "rds_paresthesie_gen":       "Paresthésies généralisées",
    "rds_sg":                    "Saignements",
    "rectorragie":               "Rectorragie (sang rouge dans les selles)",
    "regard_dévié":              "Déviation du regard",
    "rhino_clair":               "Rhinorrhée claire",
    "rhino_pur":                 "Rhinorrhée purulente",
    "sialorhee":                 "Hypersalivation (sialorrhée)",
    "selles_pale":               "Selles pâles / décolorées",
    "spasme_trapeze":            "Spasmes du trapèze",
    "spasmes_msk":               "Spasmes musculosquelettiques",
    "stridor":                   "Stridor",
    "toux":                      "Toux",
    "toux_Aboy":                 "Toux aboyante",
    "toux_sev":                  "Toux sévère / persistante",
    "trismus":                   "Trismus (contracture des mâchoires)",
    "ulcères_bouche":            "Ulcères buccaux",
    "vo_sg":                     "Vomissements sanglants (hématémèse)",
    "vo_violent":                "Vomissements en jet / violents",
    "volume_parole":             "Diminution du volume de la parole",
    "wheez":                     "Wheezing (sifflements respiratoires)",
    "ww_bouffe":                 "Aggravé par la nourriture",
    "ww_bouger":                 "Aggravé par les mouvements",
    "ww_dd":                     "Aggravé allongé sur le dos",
    "ww_effort":                 "Aggravé à l'effort",
    "ww_nuit":                   "Aggravé la nuit",
    "ww_respi":                  "Aggravé par la respiration",
    "ww_valsalva":               "Aggravé par la manœuvre de Valsalva",
    # --- Antécédents / facteurs de risque ---
    "B34.9":          "Infection virale (antécédent)",
    "H6690":          "Otite moyenne (antécédent)",
    "HIV":            "Séropositivité VIH",
    "I30":            "Péricardite (antécédent)",
    "J05.0":          "Croup (antécédent)",
    "J81":            "Œdème pulmonaire (antécédent)",
    "K86.1":          "Pancréatite chronique (antécédent)",
    "Mauv_aliment":   "Alimentation insuffisante",
    "Z99.2":          "Dépendance à la dialyse",
    "ains":           "Prise d'anti-inflammatoires (AINS)",
    "allergie_sev":   "Allergie sévère connue",
    "allait_prol":    "Allaitement prolongé",
    "antipsy_récent": "Prise récente d'antipsychotiques",
    "ap_asian":       "Origine asiatique (facteur de risque)",
    "ap_fk":          "Fibrose kystique (antécédent)",
    "ap_hypert4":     "Hypertension pulmonaire (antécédent)",
    "ap_par":         "Antécédent de parasomnie",
    "ap_pneumothorax":"Pneumothorax (antécédent)",
    "ap_valve":       "Pathologie valvulaire (antécédent)",
    "atcd_anem":      "Anémie (antécédent)",
    "atcd_cluster":   "Céphalée en grappe (antécédent)",
    "atcd_fam_anem":  "Antécédent familial d'anémie",
    "atcd_its":       "IST (antécédent)",
    "atcdfam_mg":     "Antécédent familial de myasthénie",
    "atcdpsyfam":     "Antécédent psychiatrique familial",
    "bode":           "BPCO sévère (score BODE élevé)",
    "c00-d48":        "Néoplasie (antécédent)",
    "cafe":           "Consommation élevée de caféine",
    "cancer_méta":    "Cancer métastatique (antécédent)",
    "cont_coq":       "Contact avec un cas de coqueluche",
    "contact":        "Contact avec personne malade",
    "cortico":        "Corticothérapie en cours",
    "criseasthm":     "Crise d'asthme (antécédent)",
    "crohn_cu":       "Crohn / MICI (antécédent)",
    "crowd":          "Environnement surpeuplé",
    "dayc":           "Crèche / garde en collectivité",
    "drink_energie":  "Consommation de boissons énergisantes",
    "drogues_IV":     "Usage de drogues intraveineuses",
    "drogues_stimul": "Usage de drogues stimulantes",
    "e10_e11":        "Diabète (antécédent)",
    "e66":            "Obésité (antécédent)",
    "e78.5":          "Hyperlipidémie (antécédent)",
    "eampoc1":        "Exacerbation de BPCO (antécédent)",
    "ebolacase":      "Contact avec cas Ebola confirmé",
    "f10.129":        "Alcoolisme (antécédent)",
    "f17.210":        "Tabagisme actif",
    "f32":            "Dépression (antécédent)",
    "f41.9":          "Trouble anxieux (antécédent)",
    "fam_atopie":     "Antécédent familial d'atopie",
    "fam_j45":        "Antécédent familial d'asthme",
    "g20":            "Maladie de Parkinson (antécédent)",
    "hernie_hiatale": "Hernie hiatale (antécédent)",
    "histfammigraine":"Antécédent familial de migraine",
    "horm1":          "Contraceptifs hormonaux",
    "hosptisasm":     "Hospitalisation pour asthme (antécédent)",
    "hta":            "Hypertension artérielle",
    "i10":            "Hypertension artérielle traitée",
    "i25.1":          "Maladie coronarienne (antécédent)",
    "i50":            "Insuffisance cardiaque (antécédent)",
    "i60-i69":        "Antécédent d'AVC",
    "i73.9":          "Artériopathie périphérique",
    "i80":            "Phlébite / thrombose veineuse (antécédent)",
    "immob1":         "Immobilisation prolongée récente",
    "irc":            "Insuffisance rénale chronique",
    "itss_risque":    "Comportements à risque d'IST",
    "j06.9":          "Rhinopharyngite récente",
    "j17_j18":        "Pneumonie (antécédent)",
    "j32":            "Sinusite chronique (antécédent)",
    "j33":            "Polypes nasaux (antécédent)",
    "j34.2":          "Déviation de la cloison nasale",
    "j44_j42":        "BPCO / bronchite chronique (antécédent)",
    "j45":            "Asthme (antécédent)",
    "k21":            "Reflux gastro-œsophagien (antécédent)",
    "k74":            "Cirrhose hépatique (antécédent)",
    "lymphoedème":    "Lymphœdème (antécédent)",
    "m79.7":          "Fibromyalgie (antécédent)",
    "malf_cardiaque": "Malformation cardiaque (antécédent)",
    "menarche_hat":   "Ménarche précoce",
    "momasthma":      "Mère asthmatique",
    "move":           "Sédentarité",
    "naco":           "Anticoagulants (prise en cours)",
    "nau_psy_recent": "Antipsychotique pour nausées (récent)",
    "norvasc":        "Amlodipine (Norvasc) en cours",
    "osteoporose":    "Ostéoporose (antécédent)",
    "patho_endo":     "Pathologie endocrinienne (antécédent)",
    "perinatality":   "Facteur de risque périnatal",
    "pneumothorax":   "Pneumothorax (antécédent)",
    "preg1":          "Grossesse actuelle",
    "rural":          "Environnement rural",
    "rx_vasodil":     "Vasodilatateurs (prise en cours)",
    "s09.90":         "Traumatisme crânien (antécédent)",
    "sahs":           "Syndrome d'apnées du sommeil",
    "scombroide":     "Consommation de poisson mal conservé",
    "sex_vih":        "Comportements sexuels à risque VIH",
    "smokingpast":    "Tabagisme passé (sevré)",
    "suburb":         "Environnement suburbain",
    "surg1":          "Chirurgie récente",
    "synd_nephro":    "Syndrome néphrotique",
    "tagri":          "Traitement de fond pour BPCO",
    "tconst":         "Traitement pour constipation",
    "tmine":          "Bronchodilatateur en cours",
    "trav1":          "Voyage récent à l'étranger",
    "urban1":         "Environnement urbain",
    "v85.0":          "Obésité morbide (IMC ≥ 40)",
    "vaccination":    "Statut vaccinal incomplet",
    "wakeup":         "Réveils nocturnes pour douleur",
    "z77.22":         "Exposition à un allergène environnemental",
    "z80.0":          "Antécédent familial de cancer digestif",
    "z80.1":          "Antécédent familial de cancer pulmonaire",
    "z82.49":         "Antécédent familial de cardiopathie",
    "z84.89":         "Antécédent familial d'allergie",
    "z92.25":         "Antécédent de corticothérapie systémique",
}

# Correspondances DDXPlus → titres Wikipedia FR canoniques.
# Nécessaire car les noms DDXPlus sont souvent des abréviations ou
# des descriptions cliniques qui ne matchent pas les titres d'articles.
WIKI_ALIASES: dict[str, list[str]] = {
    "Pneumothorax spontané":                             ["Pneumothorax"],
    "Fracture de côte spontanée":                        ["Fracture de côte"],
    "VIH (Primo-infection)":                             ["Infection par le VIH", "VIH"],
    "Pharyngite virale":                                 ["Pharyngite"],
    "Hernie inguinale":                                  ["Hernie inguinale"],
    "Myasthénie grave":                                  ["Myasthénie"],
    "Coqueluche":                                        ["Coqueluche"],
    "Anaphylaxie":                                       ["Anaphylaxie"],
    "Épiglottite":                                       ["Épiglottite"],
    "Syndrome de Guillain-Barré":                        ["Syndrome de Guillain-Barré"],
    "Laryngite aigue":                                   ["Laryngite"],
    "TSVP":                                              ["Tachycardie supraventriculaire"],
    "Fibrillation auriculaire/Flutter auriculaire":      ["Fibrillation auriculaire"],
    "Bronchiectasies":                                   ["Bronchectasie"],
    "Rhinite allergique":                                ["Rhinite allergique"],
    "Chagas":                                            ["Maladie de Chagas"],
    "Scombroïde":                                        ["Intoxication scombroïde", "Scombrotoxisme"],
    "Laryngospasme":                                     ["Laryngospasme"],
    "Réaction dystonique aïgue":                         ["Dystonie aiguë", "Dystonie"],
    "Oedème localisé ou généralisé sans atteinte pulmonaire associée": ["Œdème", "Oedème"],
    "Lupus érythémateux disséminé (LED)":                ["Lupus érythémateux disséminé"],
    "Angine instable":                                   ["Angor instable"],
    "Angine stable":                                     ["Angor stable", "Angine de poitrine"],
    "Ebola":                                             ["Maladie à virus Ebola"],
    "Otite moyenne aigue (OMA)":                         ["Otite moyenne"],
    "Attaque de panique":                                ["Attaque de panique"],
    "Asthme exacerbé ou bronchospasme":                  ["Asthme"],
    "Bronchite":                                         ["Bronchite"],
    "Exacerbation aigue de MPOC et/ou surinfection associée": ["Broncho-pneumopathie chronique obstructive"],
    "Embolie pulmonaire":                                ["Embolie pulmonaire"],
    "IVRS ou virémie":                                   ["Infection des voies respiratoires supérieures", "Rhinopharyngite"],
    "Possible influenza ou syndrome virémique typique":   ["Grippe"],
    "Pneumonie":                                         ["Pneumonie"],
    "Rhinosinusite aigue":                               ["Sinusite", "Rhinosinusite"],
    "Rhinosinusite chronique":                           ["Sinusite chronique", "Rhinosinusite chronique"],
    "Bronchiolite":                                      ["Bronchiolite"],
    "néoplasie pulmonaire":                              ["Cancer du poumon"],
    "Possible NSTEMI / STEMI":                           ["Infarctus du myocarde"],
    "Sarcoïdose":                                        ["Sarcoïdose"],
    "Néoplasie du pancréas":                             ["Cancer du pancréas"],
    "OAP/Surcharge pulmonaire":                          ["Œdème aigu du poumon"],
    "Péricardite":                                       ["Péricardite"],
}


# ======================================================================
# ICD-11 CLIENT
# ======================================================================

class ICD11Client:
    """
    Client OAuth2 pour l'API ICD-11 WHO.
    Authentification par client_credentials. Token valide ~1h.
    Cache JSON local pour éviter de re-requêter entre deux runs.
    """

    def __init__(self, client_id: str, client_secret: str, cache_path: Path):
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache_path = cache_path
        self._token: Optional[str] = None
        self._cache: dict = self._load_cache()
        self._available = bool(client_id and client_secret)
        if not self._available:
            logger.warning("ICD-11 : aucune clé fournie — enrichissement ICD-11 désactivé")

    def _load_cache(self) -> dict:
        if self.cache_path.exists():
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _get_token(self) -> Optional[str]:
        if not self._available:
            return None
        if self._token:
            return self._token
        try:
            resp = requests.post(
                ICD11_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "icdapi_access",
                    "grant_type": "client_credentials",
                },
                timeout=20,
            )
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
            logger.info("  ICD-11 : token OAuth2 obtenu")
            return self._token
        except Exception as exc:
            logger.warning(f"  ICD-11 authentification échouée : {exc}")
            self._available = False
            return None

    def _headers(self) -> dict:
        token = self._get_token()
        h = {"API-Version": "v2", "Accept-Language": "fr"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    def lookup(self, name_fr: str, name_en: str) -> dict:
        """
        Retourne {"icd11_code": ..., "definition": ...} ou {}
        Essaie d'abord le nom anglais (plus précis dans l'API), puis français.
        """
        cache_key = f"icd11_{hashlib.md5(name_en.lower().encode()).hexdigest()[:10]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self._available:
            return {}

        result = {}
        for term in [name_en, name_fr]:
            try:
                resp = requests.get(
                    ICD11_SEARCH_URL,
                    params={
                        "q": term,
                        "flatResults": "true",
                        "includeKeywordResult": "false",
                        "useFlexisearch": "false",
                    },
                    headers=self._headers(),
                    timeout=15,
                )
                if resp.status_code == 401:
                    # Token expiré → reset et réessayer
                    self._token = None
                    continue
                if resp.status_code != 200:
                    logger.debug(f"  ICD-11 search '{term}' → HTTP {resp.status_code}")
                    continue

                entities = resp.json().get("destinationEntities", [])
                if not entities:
                    continue

                first = entities[0]
                result = {
                    "icd11_code": first.get("theCode", ""),
                    "definition": first.get("definition", ""),
                }
                if result["icd11_code"]:
                    break
            except Exception as exc:
                logger.debug(f"  ICD-11 exception '{term}' : {exc}")
            finally:
                time.sleep(0.6)  # respecter la limite de débit WHO

        self._cache[cache_key] = result
        self._save_cache()
        return result


# ======================================================================
# WIKIPEDIA FR CLIENT
# ======================================================================

class WikipediaFRClient:
    """
    Récupère le premier paragraphe Wikipedia FR pour une pathologie.
    Utilise l'API REST Wikipedia (pas de clé requise).
    Cache JSON local.
    """

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self._cache: dict = self._load_cache()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "MedRAG/2.0 (student M2 project)"})

    def _load_cache(self) -> dict:
        if self.cache_path.exists():
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _fetch(self, title: str) -> str:
        """Tente de récupérer le résumé Wikipedia pour un titre donné."""
        encoded = quote(title.replace(" ", "_"), safe="")
        url = f"{WIKI_SUMMARY_URL}/{encoded}"
        for attempt in range(3):
            try:
                resp = self._session.get(url, timeout=15)
                if resp.status_code == 404:
                    return ""
                if resp.status_code == 429:
                    # Rate limit : attendre et réessayer
                    time.sleep(3 * (attempt + 1))
                    continue
                if resp.status_code != 200:
                    return ""
                extract = resp.json().get("extract", "").strip()
                if not extract:
                    return ""
                # Prendre le premier paragraphe non vide (≥40 chars)
                # ou à défaut les 500 premiers caractères de l'extrait
                paras = [p.strip() for p in extract.split("\n") if len(p.strip()) >= 40]
                return paras[0] if paras else extract[:500]
            except Exception:
                time.sleep(1)
            finally:
                time.sleep(0.5)
        return ""

    def get_summary(self, name_fr: str, name_en: str) -> str:
        cache_key = f"wiki_{hashlib.md5(name_fr.lower().encode()).hexdigest()[:10]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Ordre de recherche : alias canoniques > nom FR > nom EN
        candidates: list[str] = []
        if name_fr in WIKI_ALIASES:
            candidates.extend(WIKI_ALIASES[name_fr])
        candidates.extend([name_fr, name_en])

        summary = ""
        for title in candidates:
            summary = self._fetch(title)
            if summary:
                break

        self._cache[cache_key] = summary
        self._save_cache()
        return summary


# ======================================================================
# ENRICHISSEUR PRINCIPAL
# ======================================================================

class PathologyEnricher:
    """
    Orchestre l'enrichissement des 49 pathologies DDXPlus.

    Stratégie text (champ vectorisé) :
      description_narrative (Wikipedia > ICD-11 définition)
      + symptômes typiques (DDXPlus)
      + facteurs de risque (DDXPlus)

    Le champ text doit être sémantiquement dense pour que l'embedding
    e5-multilingual place la pathologie précisément dans l'espace vectoriel.
    """

    SEVERITY_FR = {1: "critique", 2: "grave", 3: "modérée", 4: "légère", 5: "bénigne"}

    def __init__(
        self,
        conditions_path: Path,
        evidences_path: Path,
        output_dir: Path,
        icd11: ICD11Client,
        wiki: WikipediaFRClient,
    ):
        self.conditions_path = conditions_path
        self.evidences_path = evidences_path
        self.output_dir = output_dir
        self.icd11 = icd11
        self.wiki = wiki
        self._evidences: dict = {}
        self._conditions: dict = {}

    def load(self) -> None:
        with open(self.evidences_path, encoding="utf-8") as f:
            self._evidences = json.load(f)
        with open(self.conditions_path, encoding="utf-8") as f:
            self._conditions = json.load(f)
        logger.info(f"  {len(self._conditions)} pathologies chargées depuis DDXPlus")

    def _evidence_to_fr(self, evi_name: str) -> str:
        """Convertit un code symptôme/antécédent DDXPlus en texte français lisible."""
        if evi_name in SYMPTOM_LABELS:
            return SYMPTOM_LABELS[evi_name]
        return evi_name.replace("_", " ").capitalize()

    def _build_symptoms_text(self, symptoms: dict) -> str:
        return " ; ".join(self._evidence_to_fr(s) for s in symptoms)

    def _build_risk_factors_text(self, antecedents: dict) -> str:
        return " ; ".join(self._evidence_to_fr(a) for a in antecedents)

    def _build_text(
        self,
        patho_fr: str,
        patho_en: str,
        icd10: str,
        severity: int,
        description_narrative: str,
        typical_symptoms: str,
        risk_factors: str,
    ) -> str:
        sev = self.SEVERITY_FR.get(severity, f"niveau {severity}")
        parts = [
            f"Pathologie : {patho_fr} ({patho_en}).",
            f"Code CIM-10 : {icd10}. Sévérité : {sev}.",
        ]
        if description_narrative:
            parts.append(description_narrative)
        if typical_symptoms:
            parts.append(f"Symptômes typiques : {typical_symptoms}.")
        if risk_factors:
            parts.append(f"Facteurs de risque : {risk_factors}.")
        return " ".join(parts)

    def _enrich_one(self, condition_name: str, d: dict, idx: int, total: int) -> dict:
        patho_fr = d.get("cond-name-fr", condition_name)
        patho_en = d.get("cond-name-eng", condition_name)
        icd10    = d.get("icd10-id", "")
        severity = d.get("severity", 3)

        logger.info(f"  [{idx:02d}/{total}] {patho_fr}")

        # --- DDXPlus : symptômes + facteurs de risque ---
        typical_symptoms = self._build_symptoms_text(d.get("symptoms", {}))
        risk_factors     = self._build_risk_factors_text(d.get("antecedents", {}))

        # --- ICD-11 (optionnel) ---
        icd11_data  = self.icd11.lookup(patho_fr, patho_en)
        icd11_code  = icd11_data.get("icd11_code") or None
        icd11_def   = icd11_data.get("definition", "")

        # --- Wikipedia FR ---
        wiki_summary = self.wiki.get_summary(patho_fr, patho_en)

        # Description narrative : Wikipedia (plus riche) > ICD-11 définition
        description_narrative = wiki_summary or icd11_def or None

        # Champ vectorisé
        text = self._build_text(
            patho_fr, patho_en, icd10, severity,
            description_narrative or "",
            typical_symptoms,
            risk_factors,
        )

        # Source d'enrichissement (traçabilité)
        enrichments = []
        if wiki_summary:
            enrichments.append("wikipedia")
        if icd11_code:
            enrichments.append("icd11")
        source_enrichment = ",".join(enrichments) if enrichments else None

        doc_id = f"patho_{hashlib.md5(condition_name.encode()).hexdigest()[:12]}"

        return {
            "id":                   doc_id,
            "source":               "ddxplus",
            "source_enrichment":    source_enrichment,
            "pathology_fr":         patho_fr,
            "pathology_en":         patho_en,
            "icd10":                icd10 or None,
            "icd11_code":           icd11_code,
            "severity":             severity,
            "text":                 text,
            "description_narrative": description_narrative,
            "typical_symptoms":     typical_symptoms or None,
            "atypical_symptoms":    None,
            "risk_factors":         risk_factors or None,
            "red_flags":            None,
        }

    def run(self) -> list[dict]:
        self.load()
        docs = []
        total = len(self._conditions)

        for idx, (cname, d) in enumerate(self._conditions.items(), 1):
            doc = self._enrich_one(cname, d, idx, total)
            docs.append(doc)

        # Écriture JSONL
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.output_dir / "ddxplus_pathology_documents.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for doc in docs:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        # Rapport
        enriched_wiki  = sum(1 for d in docs if d["description_narrative"] and "wikipedia" in (d["source_enrichment"] or ""))
        enriched_icd11 = sum(1 for d in docs if d["icd11_code"])

        logger.info("")
        logger.info("=" * 50)
        logger.info(f"  Pathologies traitées     : {len(docs)}")
        logger.info(f"  Enrichies Wikipedia      : {enriched_wiki}")
        logger.info(f"  Enrichies ICD-11         : {enriched_icd11}")
        logger.info(f"  Fichier écrit            : {out_path}")
        logger.info("=" * 50)

        return docs


# ======================================================================
# CLI
# ======================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Phase B MedRAG v2 — Enrichissement pathologies DDXPlus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Sans ICD-11 (Wikipedia seulement)
  python enrich_pathologies.py \\
      --conditions raw/ddxplus/release_conditions.json \\
      --evidences  raw/ddxplus/release_evidences.json

  # Avec ICD-11
  python enrich_pathologies.py \\
      --conditions raw/ddxplus/release_conditions.json \\
      --evidences  raw/ddxplus/release_evidences.json \\
      --icd11-client-id  MY_ID \\
      --icd11-client-secret MY_SECRET
        """,
    )
    p.add_argument("--conditions",  required=True, help="release_conditions.json DDXPlus")
    p.add_argument("--evidences",   required=True, help="release_evidences.json DDXPlus")
    p.add_argument("--output-dir",  default="processed", help="Répertoire de sortie (défaut: processed/)")
    p.add_argument("--cache-dir",   default=".cache",    help="Répertoire cache API (défaut: .cache/)")
    p.add_argument(
        "--icd11-client-id",
        default=os.getenv("ICD11_CLIENT_ID", ""),
        help="Client ID ICD-11 API (ou env ICD11_CLIENT_ID)",
    )
    p.add_argument(
        "--icd11-client-secret",
        default=os.getenv("ICD11_CLIENT_SECRET", ""),
        help="Client Secret ICD-11 API (ou env ICD11_CLIENT_SECRET)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    cache_dir = Path(args.cache_dir)

    icd11_client = ICD11Client(
        client_id=args.icd11_client_id,
        client_secret=args.icd11_client_secret,
        cache_path=cache_dir / "icd11_cache.json",
    )
    wiki_client = WikipediaFRClient(
        cache_path=cache_dir / "wiki_cache.json",
    )

    enricher = PathologyEnricher(
        conditions_path=Path(args.conditions),
        evidences_path=Path(args.evidences),
        output_dir=Path(args.output_dir),
        icd11=icd11_client,
        wiki=wiki_client,
    )
    enricher.run()


if __name__ == "__main__":
    main()

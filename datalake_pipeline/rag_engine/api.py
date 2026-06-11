"""
API FastAPI — MedRAG v2
Endpoints : /auth/register  /auth/login  /conversations  /conversations/{id}/chat  /health
"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from . import auth, conversation, llm_client, patient_profile
from .config import API_HOST, API_PORT, EMBEDDING_MODEL
from .retriever import MongoRetriever, PGRetriever

# ── État global (chargé une fois au démarrage) ────────────────────────────────

state: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Le modèle se charge une seule fois ici → rapide pour toutes les requêtes ensuite
    print("Chargement du modele d'embedding (une seule fois)...")
    state["model"] = SentenceTransformer(EMBEDDING_MODEL)
    state["pg"]    = PGRetriever()
    state["mongo"] = MongoRetriever()
    auth.init_tables()             # crée les tables users + sessions si absentes
    conversation.init_tables()    # crée les tables conversations si absentes
    patient_profile.init_table()  # crée la table patient_profiles si absente
    print("MedRAG v2 pret !")
    yield
    state["pg"].close()
    state["mongo"].close()


app = FastAPI(title="MedRAG v2", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Toutes les routes sont montées sous /api (évite les rewrites côté frontend)
router = APIRouter(prefix="/api")

# ── Schémas Pydantic ──────────────────────────────────────────────────────────

class RegisterReq(BaseModel):
    name: str
    email: str
    password: str
    age: int | None = None
    sex: str | None = None

class LoginReq(BaseModel):
    email: str
    password: str

class ChatReq(BaseModel):
    content: str   # message de l'utilisateur

class PatientProfileReq(BaseModel):
    """Données médicales de l'onboarding — tous les champs sont optionnels."""
    antecedents:     list[str] | None = None
    chronic_disease: bool | None      = None
    treatments:      list[dict] | None = None   # [{name, type}]
    allergies:       list[str] | None = None
    lifestyle:       dict | None      = None    # {smoking, activity}

# ── Sécurité triage ───────────────────────────────────────────────────────────

# Échelle de gravité des orientations — utilisée par la règle du cliquet
SEVERITE = {"domicile": 0, "pharmacien": 1, "medecin": 2, "urgent": 3, "samu": 4}


def _appliquer_cliquet(prev_triage: dict | None, new_triage: dict | None) -> dict | None:
    """Règle du cliquet : l'orientation monte mais ne descend jamais.

    Garde-fou en CODE (le prompt contient la même règle, mais on ne fait pas
    confiance au LLM seul pour une règle de sécurité). Si le nouveau triage
    est moins urgent que le précédent — ou illisible — on conserve le précédent.
    Logique alignée sur le re-tri de l'échelle FRENCH (SFMU) : réévaluation
    possible vers plus grave uniquement.
    """
    if not new_triage:
        return None
    if not prev_triage:
        return new_triage
    new_sev = SEVERITE.get(new_triage.get("orientation"))
    old_sev = SEVERITE.get(prev_triage.get("orientation"))
    if new_sev is None or (old_sev is not None and new_sev < old_sev):
        return prev_triage   # rétrogradation refusée
    return new_triage

# ── Auth helper (dépendance FastAPI) ─────────────────────────────────────────

def _check_ownership(conv_id: str, user: dict):
    """Lève 404 si la conversation n'appartient pas à l'utilisateur connecté.
    On retourne 404 (et non 403) pour ne pas révéler l'existence de la ressource."""
    if not conversation.belongs_to_user(conv_id, user["user_id"]):
        raise HTTPException(404, "Conversation introuvable.")


def get_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Non authentifié. Connectez-vous d'abord.")
    user = auth.get_user(authorization.split(" ")[1])
    if not user:
        raise HTTPException(401, "Session expirée. Reconnectez-vous.")
    return user

# ── Endpoints Auth ────────────────────────────────────────────────────────────

@router.post("/auth/register", status_code=201)
def register(req: RegisterReq):
    uid, err = auth.register(req.name, req.email, req.password, req.age, req.sex)
    if err:
        raise HTTPException(400, err)
    return {"message": "Compte créé avec succès.", "user_id": uid}

@router.post("/auth/login")
def login(req: LoginReq):
    data, err = auth.login(req.email, req.password)
    if err:
        raise HTTPException(401, err)
    return data

# ── Endpoints Conversations ───────────────────────────────────────────────────

class UpdateDeptReq(BaseModel):
    """Schéma étendu — tous les champs sont optionnels (PUT partiel).
    Permet de mettre à jour dept, age, sex, et coordonnées GPS (lat/lon)."""
    dept: str   | None = None
    age:  int   | None = None
    sex:  str   | None = None
    lat:  float | None = None
    lon:  float | None = None

@router.put("/auth/profile")
def update_profile(req: UpdateDeptReq, user: dict = Depends(get_user)):
    """Met à jour dept, age, sex, lat et/ou lon de l'utilisateur."""
    auth.update_user_profile(
        user["user_id"],
        dept=req.dept, age=req.age, sex=req.sex,
        lat=req.lat,   lon=req.lon,
    )
    return {"dept": req.dept, "age": req.age, "sex": req.sex,
            "lat": req.lat, "lon": req.lon}

@router.get("/auth/me")
def me(user: dict = Depends(get_user)):
    """Verifie si le token est toujours valide et retourne le profil (onboarding_done inclus)."""
    return user

# ── Profil patient médical ────────────────────────────────────────────────────

@router.get("/patient/profile")
def get_patient_profile(user: dict = Depends(get_user)):
    """Retourne le profil médical (antécédents, traitements, allergies).
    Retourne null si absent — ce n'est pas une erreur (cas skip onboarding)."""
    return {"profile": patient_profile.get_profile(user["user_id"])}

@router.post("/patient/profile", status_code=201)
def save_patient_profile(req: PatientProfileReq, user: dict = Depends(get_user)):
    """Crée ou met à jour le profil médical et marque l'onboarding comme terminé.
    Un body vide {} est valide (cas skip — profil vide mais onboarding_done=True)."""
    patient_profile.upsert_profile(user["user_id"], req.model_dump())
    auth.update_onboarding(user["user_id"])
    return {"message": "Profil enregistré.", "onboarding_done": True}

@router.post("/conversations", status_code=201)
def new_conversation(user: dict = Depends(get_user)):
    conv_id = conversation.create(user["user_id"])
    return {"conversation_id": conv_id}

@router.get("/conversations")
def list_conversations(user: dict = Depends(get_user)):
    return {"conversations": conversation.list_for_user(user["user_id"])}

@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: str, user: dict = Depends(get_user)):
    """Retourne les messages d'une conversation existante."""
    _check_ownership(conv_id, user)
    return {"messages": conversation.get_messages(conv_id)}

@router.post("/conversations/{conv_id}/chat")
def chat(conv_id: str, req: ChatReq, user: dict = Depends(get_user)):
    _check_ownership(conv_id, user)
    # 1. Charger l'historique depuis MongoDB
    history = conversation.get_messages(conv_id)
    history.append({"role": "user", "content": req.content})

    # 2. Appel de l'agent (Claude + outil RAG si nécessaire)
    embed_fn = lambda t: state["model"].encode(t).tolist()
    # Charge le profil médical pour contextualiser Claude (None si skip onboarding)
    profile = patient_profile.get_profile(user["user_id"])
    # Triage déjà émis ? (None au premier tour, sinon mode follow-up)
    prev_triage = conversation.get_triage(conv_id)
    result = llm_client.chat(
        messages=history,
        embed_fn=embed_fn,
        pg=state["pg"],
        mongo=state["mongo"],
        age=user.get("age"),
        sex=user.get("sex"),
        dept=user.get("dept"),
        profile=profile,
        lat=user.get("lat"),
        lon=user.get("lon"),
        prev_triage=prev_triage,
    )

    response_text = result["text"]
    # Règle du cliquet appliquée en code : jamais de rétrogradation d'orientation
    triage        = _appliquer_cliquet(prev_triage, result["triage"])
    report        = result["report"]   # fiche pré-consultation (None si pas encore de triage)

    # 3. Sauvegarder les nouveaux messages (user + assistant)
    conversation.save_messages(conv_id, [
        {"role": "user",      "content": req.content},
        {"role": "assistant", "content": response_text},
    ])

    # 4. Persister la fiche et le triage si générés (non bloquant : peuvent être None)
    if report:
        conversation.save_report(conv_id, report)
    if triage:
        conversation.save_triage(conv_id, triage)

    return {"response": response_text, "triage": triage, "report": report}

@router.get("/conversations/{conv_id}/report")
def get_report(conv_id: str, user: dict = Depends(get_user)):
    """Retourne la fiche pré-consultation persistée pour une conversation."""
    _check_ownership(conv_id, user)
    return {"report": conversation.get_report(conv_id)}

@router.get("/conversations/{conv_id}/triage")
def get_triage(conv_id: str, user: dict = Depends(get_user)):
    """Retourne le triage persisté pour une conversation."""
    _check_ownership(conv_id, user)
    return {"triage": conversation.get_triage(conv_id)}

# ── Établissements de santé ───────────────────────────────────────────────────

def _flatten_center(doc: dict) -> dict:
    """Aplatit un doc FINESS Mongo : extrait location.coordinates -> lat/lon top-level.
    Permet au frontend d'afficher les markers sans géocodage externe (Nominatim)."""
    coords = (doc.get("location") or {}).get("coordinates") or [None, None]
    lon, lat = (coords + [None, None])[:2]
    return {
        "name":           doc.get("name"),
        "address":        doc.get("address"),
        "category_label": doc.get("category_label"),
        "category_code":  doc.get("category_code"),
        "phone":          doc.get("phone"),
        "dept":           doc.get("dept"),
        "lat":            lat,
        "lon":            lon,
    }


@router.get("/centers")
def get_centers(
    dept:   str   | None = None,
    lat:    float | None = None,
    lon:    float | None = None,
    radius: int   = 50_000,
    limit:  int   = 8,
    user:   dict  = Depends(get_user),
):
    """Retourne des établissements FINESS, avec lat/lon à plat.

    - Si lat & lon fournis → recherche géolocalisée ($near) dans le rayon donné (m).
    - Sinon, si dept fourni → recherche par département.
    - Fallback : profil utilisateur (lat/lon prioritaire, sinon dept).
    """
    mongo = state["mongo"]

    # 1. Coords explicites dans la requête
    if lat is not None and lon is not None:
        centers = mongo.search_nearby(longitude=lon, latitude=lat,
                                      max_distance=radius, limit=limit)
        if centers:
            return {"centers": [_flatten_center(c) for c in centers], "source": "nearby"}

    # 2. Coords du profil utilisateur (saisies à l'onboarding)
    u_lat, u_lon = user.get("lat"), user.get("lon")
    if u_lat is not None and u_lon is not None:
        centers = mongo.search_nearby(longitude=u_lon, latitude=u_lat,
                                      max_distance=radius, limit=limit)
        if centers:
            return {"centers": [_flatten_center(c) for c in centers], "source": "nearby"}

    # 3. Fallback département
    target_dept = dept or user.get("dept")
    if target_dept:
        return {
            "centers": [_flatten_center(c) for c in mongo.search_by_dept(target_dept, limit=limit)],
            "source": "dept",
        }

    return {"centers": [], "source": "none"}

# ── Santé du système ──────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "stats": state["pg"].get_stats()}


# Enregistre toutes les routes du router (préfixées /api) sur l'app
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("rag_engine.api:app", host=API_HOST, port=API_PORT, reload=True)

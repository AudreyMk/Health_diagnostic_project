"""
API FastAPI — MedRAG v2
Endpoints : /auth/register  /auth/login  /conversations  /conversations/{id}/chat  /health
"""
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
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

@app.post("/auth/register", status_code=201)
def register(req: RegisterReq):
    uid, err = auth.register(req.name, req.email, req.password, req.age, req.sex)
    if err:
        raise HTTPException(400, err)
    return {"message": "Compte créé avec succès.", "user_id": uid}

@app.post("/auth/login")
def login(req: LoginReq):
    data, err = auth.login(req.email, req.password)
    if err:
        raise HTTPException(401, err)
    return data

# ── Endpoints Conversations ───────────────────────────────────────────────────

class UpdateDeptReq(BaseModel):
    """Schéma étendu — dept reste obligatoire pour la géolocalisation existante,
    age et sex sont optionnels (ajoutés pour l'onboarding)."""
    dept: str | None = None
    age:  int | None = None
    sex:  str | None = None

@app.put("/auth/profile")
def update_profile(req: UpdateDeptReq, user: dict = Depends(get_user)):
    """Met à jour dept, age et/ou sex de l'utilisateur."""
    auth.update_user_profile(user["user_id"], dept=req.dept, age=req.age, sex=req.sex)
    return {"dept": req.dept, "age": req.age, "sex": req.sex}

@app.get("/auth/me")
def me(user: dict = Depends(get_user)):
    """Verifie si le token est toujours valide et retourne le profil (onboarding_done inclus)."""
    return user

# ── Profil patient médical ────────────────────────────────────────────────────

@app.get("/patient/profile")
def get_patient_profile(user: dict = Depends(get_user)):
    """Retourne le profil médical (antécédents, traitements, allergies).
    Retourne null si absent — ce n'est pas une erreur (cas skip onboarding)."""
    return {"profile": patient_profile.get_profile(user["user_id"])}

@app.post("/patient/profile", status_code=201)
def save_patient_profile(req: PatientProfileReq, user: dict = Depends(get_user)):
    """Crée ou met à jour le profil médical et marque l'onboarding comme terminé.
    Un body vide {} est valide (cas skip — profil vide mais onboarding_done=True)."""
    patient_profile.upsert_profile(user["user_id"], req.model_dump())
    auth.update_onboarding(user["user_id"])
    return {"message": "Profil enregistré.", "onboarding_done": True}

@app.post("/conversations", status_code=201)
def new_conversation(user: dict = Depends(get_user)):
    conv_id = conversation.create(user["user_id"])
    return {"conversation_id": conv_id}

@app.get("/conversations")
def list_conversations(user: dict = Depends(get_user)):
    return {"conversations": conversation.list_for_user(user["user_id"])}

@app.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: str, user: dict = Depends(get_user)):
    """Retourne les messages d'une conversation existante."""
    _check_ownership(conv_id, user)
    return {"messages": conversation.get_messages(conv_id)}

@app.post("/conversations/{conv_id}/chat")
def chat(conv_id: str, req: ChatReq, user: dict = Depends(get_user)):
    _check_ownership(conv_id, user)
    # 1. Charger l'historique depuis MongoDB
    history = conversation.get_messages(conv_id)
    history.append({"role": "user", "content": req.content})

    # 2. Appel de l'agent (Claude + outil RAG si nécessaire)
    embed_fn = lambda t: state["model"].encode(t).tolist()
    # Charge le profil médical pour contextualiser Claude (None si skip onboarding)
    profile = patient_profile.get_profile(user["user_id"])
    result = llm_client.chat(
        messages=history,
        embed_fn=embed_fn,
        pg=state["pg"],
        mongo=state["mongo"],
        age=user.get("age"),
        sex=user.get("sex"),
        dept=user.get("dept"),
        profile=profile,
    )


    response_text = result["text"]
    triage        = result["triage"]
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

@app.get("/conversations/{conv_id}/report")
def get_report(conv_id: str, user: dict = Depends(get_user)):
    """Retourne la fiche pré-consultation persistée pour une conversation."""
    _check_ownership(conv_id, user)
    return {"report": conversation.get_report(conv_id)}

@app.get("/conversations/{conv_id}/triage")
def get_triage(conv_id: str, user: dict = Depends(get_user)):
    """Retourne le triage persisté pour une conversation."""
    _check_ownership(conv_id, user)
    return {"triage": conversation.get_triage(conv_id)}

# ── Établissements de santé ───────────────────────────────────────────────────

@app.get("/centers")
def get_centers(dept: str, user: dict = Depends(get_user)):
    """Retourne les établissements FINESS pour un département donné."""
    centers = state["mongo"].search_by_dept(dept, limit=8)
    return {"centers": centers}

# ── Santé du système ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "stats": state["pg"].get_stats()}


if __name__ == "__main__":
    uvicorn.run("rag_engine.api:app", host=API_HOST, port=API_PORT, reload=True)

/**
 * lib/api.ts — Client API centralisé pour MedRAG
 *
 * Toutes les routes FastAPI sont préfixées /api/* (proxy Next.js → localhost:8000)
 * Le token JWT est lu/écrit dans localStorage sous la clé "medrag_token"
 */

// ── Gestion du token ──────────────────────────────────────────────────────────

const TOKEN_KEY = 'medrag_token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ── Fetch wrapper ─────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`/api${path}`, { ...options, headers });

  if (!res.ok) {
    // Essaie de lire le message d'erreur FastAPI
    let errorMsg = `Erreur ${res.status}`;
    try {
      const err = await res.json();
      errorMsg = err.detail || errorMsg;
    } catch {
      // ignore parse error
    }
    throw new Error(errorMsg);
  }

  return res.json() as Promise<T>;
}

// ── Types des réponses API ─────────────────────────────────────────────────────
// (définis ici pour être utilisés dans api.ts, re-exportés depuis types.ts)

/**
 * Réponse POST /auth/login — le backend retourne un objet PLAT (pas de "user" imbriqué).
 * Champs : token, user_id, name, age, sex, dept, onboarding_done
 */
export interface ApiAuthResponse {
  token: string;
  user_id: string;
  name: string;
  age: number | null;
  sex: 'M' | 'F' | null;
  dept: string | null;
  onboarding_done: boolean;
}

/**
 * Réponse GET /auth/me — mêmes champs que ApiAuthResponse sans le token.
 * Retourné par get_user() dans auth.py via la dépendance FastAPI.
 */
export interface ApiUser {
  user_id: string;
  name: string;
  age: number | null;
  sex: 'M' | 'F' | null;
  dept: string | null;
  onboarding_done: boolean;
}

export interface ApiPatientProfile {
  user_id: string;
  age: number | null;
  sex: 'M' | 'F' | null;
  dept: string | null;
  antecedents: string[];
  chronic_disease: boolean | null;
  treatments: { name: string; type: string }[];
  allergies: string[];
  lifestyle: { smoking?: boolean; activity?: string };
}

export interface ApiConversation {
  id: string;
  created_at: string;
  last_message: string;
  triage_color: 'green' | 'yellow' | 'orange' | 'red' | null;
  triage_orientation: string | null;
  has_report: boolean;
}

export interface ApiMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ApiTriage {
  color: string;
  orientation: string;        // 'domicile' | 'pharmacien' | 'medecin' | 'urgent' | 'samu'
  hypotheses: { label: string }[];
  summary?: string;
}

export interface ApiReport {
  main_symptom: string;
  duration: string;
  intensity: number | null;
  associated: string[];
  context: string;
  warning_signs: string[];
  questions: string[];
  generated_at?: string;
}

export interface ApiChatResponse {
  response: string;
  triage?: ApiTriage;
  report?: ApiReport;
}

// ── Endpoints Auth ────────────────────────────────────────────────────────────

export async function apiLogin(
  email: string,
  password: string
): Promise<ApiAuthResponse> {
  return apiFetch<ApiAuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function apiRegister(
  email: string,
  password: string,
  name: string
): Promise<{ user_id: string }> {
  return apiFetch<{ user_id: string }>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  });
}

export async function apiGetMe(): Promise<ApiUser> {
  return apiFetch<ApiUser>('/auth/me');
}

export async function apiUpdateAuthProfile(
  data: Partial<{ dept: string; age: number; sex: string }>
): Promise<{ message: string }> {
  return apiFetch<{ message: string }>('/auth/profile', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// ── Endpoints Patient Profile ─────────────────────────────────────────────────

export async function apiGetPatientProfile(): Promise<{ profile: ApiPatientProfile }> {
  return apiFetch<{ profile: ApiPatientProfile }>('/patient/profile');
}

export async function apiSavePatientProfile(
  data: Partial<ApiPatientProfile>
): Promise<{ message: string }> {
  return apiFetch<{ message: string }>('/patient/profile', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ── Endpoints Conversations ───────────────────────────────────────────────────

export async function apiListConversations(): Promise<{ conversations: ApiConversation[] }> {
  return apiFetch<{ conversations: ApiConversation[] }>('/conversations');
}

export async function apiCreateConversation(): Promise<{ conversation_id: string }> {
  return apiFetch<{ conversation_id: string }>('/conversations', { method: 'POST' });
}

export async function apiGetMessages(convId: string): Promise<{ messages: ApiMessage[] }> {
  return apiFetch<{ messages: ApiMessage[] }>(`/conversations/${convId}/messages`);
}

export async function apiSendMessage(
  convId: string,
  content: string
): Promise<ApiChatResponse> {
  return apiFetch<ApiChatResponse>(`/conversations/${convId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export async function apiGetReport(convId: string): Promise<{ report: ApiReport | null }> {
  return apiFetch<{ report: ApiReport | null }>(`/conversations/${convId}/report`);
}

export async function apiGetTriage(convId: string): Promise<{ triage: ApiTriage | null }> {
  return apiFetch<{ triage: ApiTriage | null }>(`/conversations/${convId}/triage`);
}

// ── Endpoints Établissements ──────────────────────────────────────────────────

export interface ApiCenter {
  name: string;
  address: string;
  category_label: string;
  phone?: string;
}

export async function apiGetCenters(dept: string): Promise<{ centers: ApiCenter[] }> {
  return apiFetch<{ centers: ApiCenter[] }>(`/centers?dept=${dept}`);
}

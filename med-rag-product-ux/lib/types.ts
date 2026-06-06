// ── Types UI (front-end) ──────────────────────────────────────────────────────

/**
 * Orientations supportées.
 * Backend retourne : 'domicile' | 'pharmacien' | 'medecin' | 'urgent' | 'samu'
 * Frontend utilise : 'home' | 'pharmacy' | 'doctor' | 'specialist' | 'urgent' | 'samu'
 */
export type OrientationType = 'home' | 'pharmacy' | 'doctor' | 'specialist' | 'urgent' | 'samu';

export interface PatientProfile {
  id: string;
  firstName: string;   // extrait de users.name (première partie)
  lastName: string;    // extrait de users.name (seconde partie)
  email: string;
  age: number;
  sex: 'male' | 'female' | 'other';
  department: string;  // correspond à users.dept
  lat: number | null;  // coordonnée GPS (géoloc navigateur), null si non partagée
  lon: number | null;
  medicalHistory: string[];       // patient_profiles.antecedents
  chronicConditions: string[];    // dérivé de patient_profiles
  currentTreatments: string[];    // patient_profiles.treatments[].name
  allergies: string[];            // patient_profiles.allergies
  lifestyle: {
    smoking: boolean;
    physicalActivity: 'none' | 'light' | 'moderate' | 'active';
    diet: string;
  };
  createdAt: Date;
  updatedAt: Date;
}

export interface Message {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  timestamp: Date;
  quickReplies?: string[];
}

export interface SymptomSummary {
  mainSymptom: string;
  duration: string;
  intensity: string;
  associatedSymptoms: string[];
  aggravatingFactors: string[];
  relievingFactors: string[];
  alertSigns: string[];
}

export interface Consultation {
  id: string;             // UUID Zustand (pour la liste locale)
  backendId: string;      // UUID PostgreSQL (pour les appels API)
  patientId: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  status: 'in-progress' | 'completed';
  messages: Message[];
  symptomSummary: Partial<SymptomSummary>;
  orientation?: OrientationType;
  preConsultationSheet?: PreConsultationSheet;
}

export interface PreConsultationSheet {
  patientInfo: {
    mainComplaint: string;
    duration: string;
    intensity: string;
    associatedSymptoms: string[];
    triggers: string[];
    aggravatingFactors: string[];
    relievingFactors: string[];
    medicalContext: string;
  };
  aiAnalysis: {
    possibleDiagnoses: string[];
    alertSigns: string[];
    recommendedOrientation: OrientationType;
    recommendedDelay: string;
    justification: string;
  };
  questionsForDoctor: string[];
  disclaimer: string;
}

export interface OnboardingData {
  step: number;
  basicInfo: {
    age: string;
    sex: string;
    department: string;
    lat: number | null;       // GPS via navigator.geolocation (étape 1)
    lon: number | null;
    locationStatus: 'idle' | 'requesting' | 'granted' | 'denied' | 'error';
  };
  medicalContext: {
    medicalHistory: string;
    chronicConditions: string;
    otherInfo: string;
  };
  treatmentsAllergies: {
    currentTreatments: string;
    allergies: string;
    smoking: boolean;
    physicalActivity: string;
  };
}

export type ChatPhase = 'collecting' | 'analyzing' | 'orientation';

// ── Fonctions de mapping API → UI ─────────────────────────────────────────────

import type {
  ApiUser,
  ApiAuthResponse,
  ApiPatientProfile,
  ApiConversation,
  ApiMessage,
  ApiTriage,
  ApiReport,
} from './api';

/**
 * Convertit un ApiUser (GET /auth/me) ou ApiAuthResponse (POST /auth/login) en PatientProfile (UI).
 * Le backend ne retourne pas l'email dans ces endpoints — on laisse la valeur vide.
 * name = "Jean Dupont" → firstName = "Jean", lastName = "Dupont"
 */
export function mapApiUserToProfile(apiUser: ApiUser | ApiAuthResponse): PatientProfile {
  const nameParts = (apiUser.name || '').trim().split(' ');
  const firstName = nameParts[0] || '';
  const lastName = nameParts.slice(1).join(' ') || '';

  return {
    id: apiUser.user_id,   // le backend retourne "user_id", pas "id"
    firstName,
    lastName,
    email: '',             // non fourni par GET /auth/me ni POST /auth/login
    age: apiUser.age || 0,
    sex: apiUser.sex === 'M' ? 'male' : apiUser.sex === 'F' ? 'female' : 'other',
    department: apiUser.dept || '',
    lat: apiUser.lat ?? null,
    lon: apiUser.lon ?? null,
    medicalHistory: [],
    chronicConditions: [],
    currentTreatments: [],
    allergies: [],
    lifestyle: { smoking: false, physicalActivity: 'none', diet: '' },
    createdAt: new Date(),
    updatedAt: new Date(),
  };
}

/**
 * Enrichit un PatientProfile avec les données du profil patient (patient_profiles).
 */
export function mergePatientProfile(
  base: PatientProfile,
  profile: ApiPatientProfile
): PatientProfile {
  return {
    ...base,
    age: profile.age || base.age,
    sex: profile.sex === 'M' ? 'male' : profile.sex === 'F' ? 'female' : base.sex,
    department: profile.dept || base.department,
    medicalHistory: profile.antecedents || [],
    chronicConditions: profile.chronic_disease ? ['Maladie chronique'] : [],
    currentTreatments: (profile.treatments || []).map((t) => t.name),
    allergies: profile.allergies || [],
    lifestyle: {
      smoking: profile.lifestyle?.smoking ?? false,
      physicalActivity: (profile.lifestyle?.activity as PatientProfile['lifestyle']['physicalActivity']) || 'none',
      diet: '',
    },
    updatedAt: new Date(),
  };
}

/**
 * Convertit une orientation backend → OrientationType frontend.
 * Backend: 'domicile' | 'pharmacien' | 'medecin' | 'urgent' | 'samu'
 * Frontend: 'home' | 'pharmacy' | 'doctor' | 'specialist' | 'urgent' | 'samu'
 */
export function mapBackendOrientation(orientation: string): OrientationType {
  const map: Record<string, OrientationType> = {
    domicile: 'home',
    pharmacien: 'pharmacy',
    medecin: 'doctor',
    urgent: 'urgent',
    samu: 'samu',
  };
  return map[orientation] || 'doctor';
}

/**
 * Convertit un ApiTriage en orientationType + PreConsultationSheet partielle.
 */
export function mapApiTriageToOrientation(triage: ApiTriage): OrientationType {
  return mapBackendOrientation(triage.orientation);
}

/**
 * Convertit un ApiReport backend → PreConsultationSheet UI.
 */
export function mapApiReportToSheet(
  report: ApiReport,
  triage?: ApiTriage
): PreConsultationSheet {
  const orientation = triage ? mapBackendOrientation(triage.orientation) : 'doctor';
  const delay =
    orientation === 'samu' ? 'Immédiat' :
    orientation === 'urgent' ? 'Dans les 24h' :
    orientation === 'home' ? '48-72h si aggravation' :
    'Dans la semaine';

  return {
    patientInfo: {
      mainComplaint: report.main_symptom || '',
      duration: report.duration || '',
      intensity: report.intensity != null ? `${report.intensity}/10` : '',
      associatedSymptoms: report.associated || [],
      triggers: [],
      aggravatingFactors: [],
      relievingFactors: [],
      medicalContext: report.context || '',
    },
    aiAnalysis: {
      possibleDiagnoses: triage?.hypotheses?.map((h) => h.label) || [],
      alertSigns: report.warning_signs || [],
      recommendedOrientation: orientation,
      recommendedDelay: delay,
      justification: triage?.summary || 'Basé sur les symptômes décrits.',
    },
    questionsForDoctor: report.questions || [],
    disclaimer:
      "Cette fiche est une aide à l'orientation et ne remplace pas l'avis d'un professionnel de santé. Les informations générées par l'IA sont des hypothèses à discuter avec votre médecin.",
  };
}

/**
 * Convertit un ApiConversation (liste) → Consultation UI (partielle, sans messages).
 */
export function mapApiConvToConsultation(apiConv: ApiConversation): Consultation {
  const orientation = apiConv.triage_orientation
    ? mapBackendOrientation(apiConv.triage_orientation)
    : undefined;

  return {
    id: apiConv.id,
    backendId: apiConv.id,
    patientId: '',
    title: apiConv.last_message || 'Consultation',
    createdAt: new Date(apiConv.created_at),
    updatedAt: new Date(apiConv.created_at),
    status: 'completed',
    messages: [],
    symptomSummary: {},
    orientation,
  };
}

/**
 * Convertit un ApiMessage backend → Message UI.
 */
export function mapApiMessage(msg: ApiMessage, index: number): Message {
  return {
    id: `msg-${index}`,
    role: msg.role,
    content: msg.content,
    timestamp: new Date(),
  };
}

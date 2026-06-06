'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  PatientProfile,
  Consultation,
  OnboardingData,
  Message,
  OrientationType,
  PreConsultationSheet,
} from './types';
import {
  mapApiUserToProfile,
  mergePatientProfile,
  mapApiTriageToOrientation,
  mapApiReportToSheet,
  mapApiConvToConsultation,
  mapApiMessage,
} from './types';
import {
  getToken,
  setToken,
  clearToken,
  apiLogin,
  apiRegister,
  apiGetMe,
  apiGetPatientProfile,
  apiSavePatientProfile,
  apiUpdateAuthProfile,
  apiListConversations,
  apiCreateConversation,
  apiGetMessages,
  apiSendMessage,
  apiGetReport,
  apiGetTriage,
} from './api';

// ── Types du store ────────────────────────────────────────────────────────────

interface AppState {
  // Auth
  isAuthenticated: boolean;
  authToken: string | null;
  currentUser: PatientProfile | null;

  // Onboarding
  onboardingCompleted: boolean;
  onboardingData: OnboardingData;

  // Consultations
  consultations: Consultation[];
  currentConsultation: Consultation | null;

  // ── Actions Auth ──────────────────────────────────────────────────────────
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, firstName: string, lastName: string) => Promise<void>;
  logout: () => void;
  checkPersistedSession: () => Promise<void>;

  // ── Actions Onboarding ────────────────────────────────────────────────────
  updateOnboardingData: (data: Partial<OnboardingData>) => void;
  completeOnboarding: () => Promise<void>;
  updateProfile: (profile: Partial<PatientProfile>) => void;

  // ── Actions Consultations ─────────────────────────────────────────────────
  loadConsultations: () => Promise<void>;
  startNewConsultation: () => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  resumeConsultation: (id: string) => Promise<void>;
  closeConsultation: () => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

// ── Message de bienvenue ──────────────────────────────────────────────────────

function welcomeMessage(name: string): Message {
  return {
    id: generateId(),
    role: 'assistant',
    content: `Bonjour **${name}** 👋 Je suis **MedRAG**, votre assistant de pré-consultation médicale.\n\nJe vais vous poser quelques questions sur vos symptômes, puis vous orienter vers le soin adapté.\n\n⚠️ Je ne remplace pas un médecin. En cas d'urgence, appelez le **15** (SAMU).\n\nQuand vous êtes prêt(e), **décrivez-moi ce qui vous amène**.`,
    timestamp: new Date(),
  };
}

// ── Store ─────────────────────────────────────────────────────────────────────

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // État initial
      isAuthenticated: false,
      authToken: null,
      currentUser: null,
      onboardingCompleted: false,
      onboardingData: {
        step: 1,
        basicInfo: {
          age: '',
          sex: '',
          department: '',
          lat: null,
          lon: null,
          locationStatus: 'idle',
        },
        medicalContext: { medicalHistory: '', chronicConditions: '', otherInfo: '' },
        treatmentsAllergies: {
          currentTreatments: '',
          allergies: '',
          smoking: false,
          physicalActivity: '',
        },
      },
      consultations: [],
      currentConsultation: null,

      // ── Auth ───────────────────────────────────────────────────────────────

      login: async (email, password) => {
        // Le backend retourne un objet PLAT : { token, user_id, name, age, sex, dept, onboarding_done }
        const data = await apiLogin(email, password);
        setToken(data.token);
        const profile = mapApiUserToProfile(data); // data est directement ApiAuthResponse

        // Tente de charger le profil patient pour enrichir les données
        try {
          const { profile: patientProfile } = await apiGetPatientProfile();
          const enriched = mergePatientProfile(profile, patientProfile);
          set({
            isAuthenticated: true,
            authToken: data.token,
            currentUser: enriched,
            onboardingCompleted: data.onboarding_done, // champ direct, pas data.user.onboarding_done
          });
        } catch {
          // Profil pas encore créé (onboarding non fait) — normal
          set({
            isAuthenticated: true,
            authToken: data.token,
            currentUser: profile,
            onboardingCompleted: data.onboarding_done,
          });
        }

        // Charge la liste des conversations en arrière-plan
        try { await get().loadConsultations(); } catch { /* silencieux */ }
      },

      register: async (email, password, firstName, lastName) => {
        const name = `${firstName} ${lastName}`.trim();
        await apiRegister(email, password, name);
        // Après inscription → login automatique
        await get().login(email, password);
        // Forcer onboarding après registration
        set({ onboardingCompleted: false });
      },

      logout: () => {
        clearToken();
        set({
          isAuthenticated: false,
          authToken: null,
          currentUser: null,
          currentConsultation: null,
          consultations: [],
          onboardingCompleted: false,
        });
      },

      checkPersistedSession: async () => {
        const token = getToken();
        if (!token) return;
        try {
          const apiUser = await apiGetMe();
          const profile = mapApiUserToProfile(apiUser);
          try {
            const { profile: patientProfile } = await apiGetPatientProfile();
            const enriched = mergePatientProfile(profile, patientProfile);
            set({
              isAuthenticated: true,
              authToken: token,
              currentUser: enriched,
              onboardingCompleted: apiUser.onboarding_done,
            });
          } catch {
            set({
              isAuthenticated: true,
              authToken: token,
              currentUser: profile,
              onboardingCompleted: apiUser.onboarding_done,
            });
          }
          try { await get().loadConsultations(); } catch { /* silencieux */ }
        } catch {
          // Token expiré ou invalide
          clearToken();
          set({ isAuthenticated: false, authToken: null, currentUser: null });
        }
      },

      // ── Onboarding ─────────────────────────────────────────────────────────

      updateOnboardingData: (data) => {
        set((state) => ({
          onboardingData: { ...state.onboardingData, ...data },
        }));
      },

      completeOnboarding: async () => {
        const { onboardingData, currentUser } = get();
        if (!currentUser) throw new Error('Utilisateur non connecté');

        const dept = onboardingData.basicInfo.department.split(' - ')[0]; // "75 - Paris" → "75"
        const age = parseInt(onboardingData.basicInfo.age) || null;
        const sexRaw = onboardingData.basicInfo.sex;
        const sex = sexRaw === 'male' ? 'M' : sexRaw === 'female' ? 'F' : null;
        const { lat, lon } = onboardingData.basicInfo;

        // 1. Met à jour les infos de base dans users (dept, age, sex, lat, lon)
        await apiUpdateAuthProfile({
          dept: dept || undefined,
          age:  age  || undefined,
          sex:  sex  || undefined,
          lat:  lat  ?? undefined,
          lon:  lon  ?? undefined,
        });

        // 2. Sauvegarde le profil patient complet
        const antecedents = onboardingData.medicalContext.medicalHistory
          .split(',').map((s) => s.trim()).filter(Boolean);
        const chronicConditions = onboardingData.medicalContext.chronicConditions
          .split(',').map((s) => s.trim()).filter(Boolean);
        const treatments = onboardingData.treatmentsAllergies.currentTreatments
          .split(',').map((s) => s.trim()).filter(Boolean)
          .map((name) => ({ name, type: 'chronique' }));
        const allergies = onboardingData.treatmentsAllergies.allergies
          .split(',').map((s) => s.trim()).filter(Boolean);

        await apiSavePatientProfile({
          age,
          sex,
          dept: dept || null,
          antecedents: [...antecedents, ...chronicConditions],
          chronic_disease: chronicConditions.length > 0,
          treatments,
          allergies,
          lifestyle: {
            smoking: onboardingData.treatmentsAllergies.smoking,
            activity: onboardingData.treatmentsAllergies.physicalActivity,
          },
        });

        // 3. Met à jour le store local
        const updatedUser: PatientProfile = {
          ...currentUser,
          age: age || 0,
          sex: sex === 'M' ? 'male' : sex === 'F' ? 'female' : 'other',
          department: dept || '',
          lat: lat ?? currentUser.lat,
          lon: lon ?? currentUser.lon,
          medicalHistory: antecedents,
          chronicConditions,
          currentTreatments: treatments.map((t) => t.name),
          allergies,
          lifestyle: {
            smoking: onboardingData.treatmentsAllergies.smoking,
            physicalActivity: (onboardingData.treatmentsAllergies.physicalActivity as PatientProfile['lifestyle']['physicalActivity']) || 'none',
            diet: '',
          },
          updatedAt: new Date(),
        };

        set({ currentUser: updatedUser, onboardingCompleted: true });
      },

      updateProfile: (profile) => {
        const { currentUser } = get();
        if (!currentUser) return;
        set({ currentUser: { ...currentUser, ...profile, updatedAt: new Date() } });
      },

      // ── Consultations ──────────────────────────────────────────────────────

      loadConsultations: async () => {
        const { conversations } = await apiListConversations();
        const consultations = conversations.map(mapApiConvToConsultation);
        set({ consultations });
      },

      startNewConsultation: async () => {
        const { currentUser } = get();
        if (!currentUser) throw new Error('Utilisateur non connecté');

        const { conversation_id } = await apiCreateConversation();

        const newConsultation: Consultation = {
          id: conversation_id,
          backendId: conversation_id,
          patientId: currentUser.id,
          title: 'Nouvelle consultation',
          createdAt: new Date(),
          updatedAt: new Date(),
          status: 'in-progress',
          messages: [welcomeMessage(currentUser.firstName || 'Patient')],
          symptomSummary: {},
        };

        set((state) => ({
          currentConsultation: newConsultation,
          consultations: [newConsultation, ...state.consultations],
        }));
      },

      sendMessage: async (content: string) => {
        const { currentConsultation } = get();
        if (!currentConsultation?.backendId) throw new Error('Pas de consultation active');

        // Ajoute le message utilisateur immédiatement
        const userMsg: Message = {
          id: generateId(),
          role: 'user',
          content,
          timestamp: new Date(),
        };

        set((state) => ({
          currentConsultation: state.currentConsultation
            ? {
                ...state.currentConsultation,
                messages: [...state.currentConsultation.messages, userMsg],
                updatedAt: new Date(),
              }
            : null,
        }));

        // Appel API → Claude
        const data = await apiSendMessage(currentConsultation.backendId, content);

        // Construit la réponse assistante
        const assistantMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: data.response,
          timestamp: new Date(),
        };

        // Calcule orientation + fiche si triage retourné
        const orientation = data.triage ? mapApiTriageToOrientation(data.triage) : undefined;
        const sheet = data.report ? mapApiReportToSheet(data.report, data.triage) : undefined;

        set((state) => {
          if (!state.currentConsultation) return {};
          const updated: Consultation = {
            ...state.currentConsultation,
            messages: [...state.currentConsultation.messages, assistantMsg],
            updatedAt: new Date(),
            ...(orientation ? { orientation, status: 'completed' } : {}),
            ...(sheet ? { preConsultationSheet: sheet } : {}),
            // Met à jour le titre avec le premier message utilisateur
            title:
              state.currentConsultation.title === 'Nouvelle consultation' && userMsg.role === 'user'
                ? content.substring(0, 60)
                : state.currentConsultation.title,
          };
          return {
            currentConsultation: updated,
            consultations: state.consultations.map((c) =>
              c.id === updated.id ? updated : c
            ),
          };
        });
      },

      resumeConsultation: async (id: string) => {
        // Cherche dans la liste locale (peut être une conv chargée depuis l'API)
        const { consultations } = get();
        const found = consultations.find((c) => c.id === id || c.backendId === id);
        const backendId = found?.backendId || id;

        // Charge messages + report + triage en parallèle
        const [msgData, reportData, triageData] = await Promise.all([
          apiGetMessages(backendId),
          apiGetReport(backendId).catch(() => ({ report: null })),
          apiGetTriage(backendId).catch(() => ({ triage: null })),
        ]);

        // Le message de bienvenue est généré localement et jamais sauvé en base.
        // On le réinjecte systématiquement en tête de conversation.
        const firstName = get().currentUser?.firstName || 'Patient';
        const apiMessages = msgData.messages.map(mapApiMessage);
        const messages: Message[] = [
          welcomeMessage(firstName),
          ...apiMessages,
        ];

        const orientation = triageData.triage
          ? mapApiTriageToOrientation(triageData.triage)
          : undefined;

        const sheet =
          reportData.report
            ? mapApiReportToSheet(reportData.report, triageData.triage || undefined)
            : undefined;

        const consultation: Consultation = {
          id: backendId,
          backendId,
          patientId: get().currentUser?.id || '',
          title: found?.title || messages.find((m) => m.role === 'user')?.content?.substring(0, 60) || 'Consultation',
          createdAt: found?.createdAt || new Date(),
          updatedAt: new Date(),
          status: orientation ? 'completed' : 'in-progress',
          messages,
          symptomSummary: {},
          orientation,
          preConsultationSheet: sheet,
        };

        set({ currentConsultation: consultation });
      },

      closeConsultation: () => {
        set({ currentConsultation: null });
        // Rafraîchit la liste
        get().loadConsultations().catch(() => {});
      },
    }),

    {
      name: 'medrag-storage',
      // On ne persiste que le strict minimum — pas les messages (rechargés depuis l'API)
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        authToken: state.authToken,
        currentUser: state.currentUser,
        onboardingCompleted: state.onboardingCompleted,
        onboardingData: state.onboardingData,
      }),
    }
  )
);

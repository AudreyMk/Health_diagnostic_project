'use client';

import { useEffect, useState } from 'react';
import { useAppStore } from '@/lib/store';
import AuthPage from '@/components/auth-page';
import OnboardingPage from '@/components/onboarding-page';
import DashboardPage from '@/components/dashboard-page';
import ConsultationPage from '@/components/consultation-page';
import HistoryPage from '@/components/history-page';

type AppView = 'auth' | 'onboarding' | 'dashboard' | 'consultation' | 'history';

export default function Home() {
  const [mounted, setMounted] = useState(false);
  const [currentView, setCurrentView] = useState<AppView>('auth');

  const {
    isAuthenticated,
    onboardingCompleted,
    currentConsultation,
    checkPersistedSession,
  } = useAppStore();

  // Montage initial : vérifie si un token valide est stocké
  useEffect(() => {
    async function init() {
      await checkPersistedSession();
      setMounted(true);
    }
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Routing conditionnel basé sur l'état du store
  useEffect(() => {
    if (!mounted) return;

    if (!isAuthenticated) {
      setCurrentView('auth');
    } else if (!onboardingCompleted) {
      setCurrentView('onboarding');
    } else if (currentConsultation) {
      setCurrentView('consultation');
    } else {
      setCurrentView('dashboard');
    }
  }, [mounted, isAuthenticated, onboardingCompleted, currentConsultation]);

  // Écran de chargement pendant la vérification du token
  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4 text-muted-foreground">
          <div className="w-12 h-12 bg-primary/10 rounded-xl animate-pulse" />
          <p className="text-sm animate-pulse">Chargement…</p>
        </div>
      </div>
    );
  }

  const navigateTo = (view: AppView) => {
    setCurrentView(view);
  };

  switch (currentView) {
    case 'auth':
      return <AuthPage />;
    case 'onboarding':
      return <OnboardingPage />;
    case 'consultation':
      return <ConsultationPage onNavigate={navigateTo} />;
    case 'history':
      return <HistoryPage onNavigate={navigateTo} />;
    case 'dashboard':
    default:
      return <DashboardPage onNavigate={navigateTo} />;
  }
}

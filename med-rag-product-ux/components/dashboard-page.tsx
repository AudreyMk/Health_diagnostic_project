'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Stethoscope,
  LogOut,
  Plus,
  User,
  Calendar,
  FileText,
  Clock,
  ChevronRight,
  Heart,
  Pill,
  AlertTriangle,
  History,
  RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';
import type { OrientationType } from '@/lib/types';

interface DashboardPageProps {
  onNavigate: (view: 'auth' | 'onboarding' | 'dashboard' | 'consultation' | 'history') => void;
}

const orientationBadgeColors: Record<OrientationType, string> = {
  home: 'bg-success/10 text-success border-success/20',
  pharmacy: 'bg-success/10 text-success border-success/20',
  doctor: 'bg-primary/10 text-primary border-primary/20',
  specialist: 'bg-primary/10 text-primary border-primary/20',
  urgent: 'bg-warning/10 text-warning border-warning/20',
  samu: 'bg-destructive/10 text-destructive border-destructive/20',
};

const orientationLabels: Record<OrientationType, string> = {
  home: 'Domicile',
  pharmacy: 'Pharmacie',
  doctor: 'Médecin',
  specialist: 'Spécialiste',
  urgent: 'Urgences',
  samu: 'SAMU',
};

export default function DashboardPage({ onNavigate }: DashboardPageProps) {
  const {
    currentUser,
    consultations,
    logout,
    startNewConsultation,
    resumeConsultation,
    loadConsultations,
  } = useAppStore();

  // Rafraîchit la liste des consultations à chaque montage du dashboard
  useEffect(() => {
    loadConsultations().catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleNewConsultation = async () => {
    try {
      await startNewConsultation();
      onNavigate('consultation');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erreur';
      toast.error(msg);
    }
  };

  const handleResumeConsultation = async (id: string) => {
    try {
      await resumeConsultation(id);
      onNavigate('consultation');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erreur de chargement';
      toast.error(msg);
    }
  };

  const handleLogout = () => {
    logout();
  };

  const recentConsultations = consultations
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 3);

  const formatDate = (date: Date) => {
    return new Date(date).toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-card border-b border-border/50">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
              <Stethoscope className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold text-foreground">MedRAG</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground hidden sm:inline">
              {currentUser?.firstName} {currentUser?.lastName}
            </span>
            <Button variant="ghost" size="icon" onClick={handleLogout} title="Déconnexion">
              <LogOut className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {/* Hero Section */}
        <div className="text-center space-y-4">
          <h1 className="text-3xl font-bold text-foreground">
            Bonjour {currentUser?.firstName || 'Patient'}, que souhaitez-vous faire aujourd&apos;hui ?
          </h1>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            MedRAG vous accompagne pour décrire vos symptômes et préparer vos consultations médicales.
          </p>
        </div>

        {/* Main Action */}
        <div className="flex justify-center">
          <Button 
            onClick={handleNewConsultation} 
            size="lg" 
            className="gap-2 text-lg px-8 py-6 h-auto shadow-lg hover:shadow-xl transition-shadow"
          >
            <Plus className="w-5 h-5" />
            Nouveau problème de santé
          </Button>
        </div>

        {/* Content Grid */}
        <div className="grid md:grid-cols-2 gap-6">
          {/* Profile Card */}
          <Card className="border-border/50 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <User className="w-5 h-5 text-primary" />
                  Mon profil santé
                </CardTitle>
                <Button variant="ghost" size="sm">
                  Modifier
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Âge</p>
                  <p className="font-medium">{currentUser?.age || '-'} ans</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Sexe</p>
                  <p className="font-medium">
                    {currentUser?.sex === 'male' ? 'Homme' : 
                     currentUser?.sex === 'female' ? 'Femme' : 'Autre'}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Département</p>
                  <p className="font-medium truncate">{currentUser?.department || '-'}</p>
                </div>
              </div>

              {/* Medical History */}
              {currentUser?.medicalHistory && currentUser.medicalHistory.length > 0 && (
                <div className="pt-3 border-t">
                  <div className="flex items-center gap-2 mb-2">
                    <Heart className="w-4 h-4 text-destructive" />
                    <span className="text-sm font-medium">Antécédents</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {currentUser.medicalHistory.slice(0, 3).map((item, i) => (
                      <Badge key={i} variant="secondary" className="text-xs">
                        {item}
                      </Badge>
                    ))}
                    {currentUser.medicalHistory.length > 3 && (
                      <Badge variant="outline" className="text-xs">
                        +{currentUser.medicalHistory.length - 3}
                      </Badge>
                    )}
                  </div>
                </div>
              )}

              {/* Treatments */}
              {currentUser?.currentTreatments && currentUser.currentTreatments.length > 0 && (
                <div className="pt-3 border-t">
                  <div className="flex items-center gap-2 mb-2">
                    <Pill className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium">Traitements</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {currentUser.currentTreatments.slice(0, 3).map((item, i) => (
                      <Badge key={i} variant="secondary" className="text-xs">
                        {item}
                      </Badge>
                    ))}
                    {currentUser.currentTreatments.length > 3 && (
                      <Badge variant="outline" className="text-xs">
                        +{currentUser.currentTreatments.length - 3}
                      </Badge>
                    )}
                  </div>
                </div>
              )}

              {/* Allergies */}
              {currentUser?.allergies && currentUser.allergies.length > 0 && (
                <div className="pt-3 border-t">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-4 h-4 text-warning" />
                    <span className="text-sm font-medium">Allergies</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {currentUser.allergies.map((item, i) => (
                      <Badge key={i} variant="secondary" className="text-xs bg-warning/10 text-warning">
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Consultations Card */}
          <Card className="border-border/50 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Calendar className="w-5 h-5 text-primary" />
                  Dernières consultations
                </CardTitle>
                {consultations.length > 0 && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="gap-1"
                    onClick={() => onNavigate('history')}
                  >
                    <History className="w-4 h-4" />
                    Historique
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {recentConsultations.length === 0 ? (
                <div className="text-center py-8 space-y-3">
                  <div className="w-12 h-12 mx-auto bg-muted rounded-full flex items-center justify-center">
                    <FileText className="w-6 h-6 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-muted-foreground">
                      Vous n&apos;avez pas encore de consultation.
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Commencez votre première analyse avec MedRAG.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentConsultations.map((consultation) => (
                    <div
                      key={consultation.id}
                      className="flex items-center justify-between p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-sm truncate">
                            {consultation.title}
                          </p>
                          {consultation.orientation && (
                            <Badge 
                              variant="outline" 
                              className={`text-xs ${orientationBadgeColors[consultation.orientation]}`}
                            >
                              {orientationLabels[consultation.orientation]}
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                          <Clock className="w-3 h-3" />
                          {formatDate(consultation.updatedAt)}
                          {consultation.status === 'in-progress' && (
                            <Badge variant="outline" className="text-xs">
                              En cours
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {consultation.preConsultationSheet && (
                          <Button variant="ghost" size="sm" className="gap-1">
                            <FileText className="w-4 h-4" />
                            Fiche
                          </Button>
                        )}
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleResumeConsultation(consultation.id)}
                          className="gap-1"
                        >
                          Reprendre
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Trust Banner */}
        <Card className="bg-primary/5 border-primary/10">
          <CardContent className="py-4">
            <CardDescription className="text-center text-sm">
              MedRAG est un outil d&apos;aide à la préparation de consultation. 
              Il ne remplace pas l&apos;avis d&apos;un professionnel de santé.
            </CardDescription>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

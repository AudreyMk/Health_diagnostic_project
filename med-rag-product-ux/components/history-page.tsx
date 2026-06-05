'use client';

import { useEffect, useState } from 'react';
import { useAppStore } from '@/lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Stethoscope,
  ArrowLeft,
  Calendar,
  Clock,
  FileText,
  ChevronRight,
  Search,
  Filter,
  RefreshCw
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import type { OrientationType, Consultation } from '@/lib/types';

interface HistoryPageProps {
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

export default function HistoryPage({ onNavigate }: HistoryPageProps) {
  const { consultations, resumeConsultation, loadConsultations } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [filterOrientation, setFilterOrientation] = useState<OrientationType | 'all'>('all');
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Rafraîchit la liste à l'ouverture
  useEffect(() => {
    loadConsultations().catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleBack = () => {
    onNavigate('dashboard');
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await loadConsultations();
    } catch {
      toast.error('Impossible de rafraîchir l\'historique');
    } finally {
      setIsRefreshing(false);
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

  const sortedConsultations = [...consultations]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

  const filteredConsultations = sortedConsultations.filter((consultation) => {
    const matchesSearch = consultation.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      consultation.symptomSummary.mainSymptom?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesFilter = filterOrientation === 'all' || consultation.orientation === filterOrientation;
    
    return matchesSearch && matchesFilter;
  });

  const formatDate = (date: Date) => {
    return new Date(date).toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-card border-b border-border/50">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={handleBack}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div className="flex items-center gap-2 flex-1">
            <Calendar className="w-5 h-5 text-primary" />
            <span className="font-semibold text-foreground">Historique des consultations</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Rafraîchir"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Search and Filter */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher une consultation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex gap-2 overflow-x-auto pb-2 sm:pb-0">
            <Button
              variant={filterOrientation === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setFilterOrientation('all')}
              className="shrink-0"
            >
              <Filter className="w-4 h-4 mr-1" />
              Tous
            </Button>
            {(['doctor', 'urgent', 'home'] as OrientationType[]).map((orientation) => (
              <Button
                key={orientation}
                variant={filterOrientation === orientation ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterOrientation(orientation)}
                className="shrink-0"
              >
                {orientationLabels[orientation]}
              </Button>
            ))}
          </div>
        </div>

        {/* Consultations List */}
        {filteredConsultations.length === 0 ? (
          <Card className="border-border/50">
            <CardContent className="py-12 text-center">
              <div className="w-16 h-16 mx-auto bg-muted rounded-full flex items-center justify-center mb-4">
                <Stethoscope className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="font-medium text-foreground mb-2">
                {searchQuery || filterOrientation !== 'all'
                  ? 'Aucune consultation trouvée'
                  : 'Aucune consultation'}
              </h3>
              <p className="text-sm text-muted-foreground">
                {searchQuery || filterOrientation !== 'all'
                  ? 'Essayez de modifier vos critères de recherche.'
                  : 'Vos consultations apparaîtront ici.'}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredConsultations.map((consultation) => (
              <ConsultationCard
                key={consultation.id}
                consultation={consultation}
                onResume={() => handleResumeConsultation(consultation.id)}
                formatDate={formatDate}
                formatTime={formatTime}
              />
            ))}
          </div>
        )}

        {/* Summary */}
        {consultations.length > 0 && (
          <div className="text-center text-sm text-muted-foreground">
            {filteredConsultations.length} consultation{filteredConsultations.length > 1 ? 's' : ''} 
            {searchQuery || filterOrientation !== 'all' ? ' trouvée' : ''}
            {filteredConsultations.length > 1 && (searchQuery || filterOrientation !== 'all') ? 's' : ''}
          </div>
        )}
      </main>
    </div>
  );
}

function ConsultationCard({ 
  consultation, 
  onResume,
  formatDate,
  formatTime
}: { 
  consultation: Consultation;
  onResume: () => void;
  formatDate: (date: Date) => string;
  formatTime: (date: Date) => string;
}) {
  return (
    <Card className="border-border/50 hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-base font-medium truncate">
              {consultation.title}
            </CardTitle>
            <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {formatDate(consultation.createdAt)}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatTime(consultation.createdAt)}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {consultation.status === 'in-progress' && (
              <Badge variant="outline" className="text-xs">
                En cours
              </Badge>
            )}
            {consultation.orientation && (
              <Badge 
                variant="outline" 
                className={`text-xs ${orientationBadgeColors[consultation.orientation]}`}
              >
                {orientationLabels[consultation.orientation]}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        {consultation.symptomSummary.mainSymptom && (
          <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
            {consultation.symptomSummary.mainSymptom}
            {consultation.symptomSummary.duration && ` - ${consultation.symptomSummary.duration}`}
          </p>
        )}
        <div className="flex items-center gap-2">
          {consultation.preConsultationSheet && (
            <Button variant="outline" size="sm" className="gap-1">
              <FileText className="w-4 h-4" />
              Voir la fiche
            </Button>
          )}
          <Button 
            variant={consultation.status === 'in-progress' ? 'default' : 'outline'} 
            size="sm"
            onClick={onResume}
            className="gap-1 ml-auto"
          >
            {consultation.status === 'in-progress' ? 'Reprendre' : 'Revoir'}
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

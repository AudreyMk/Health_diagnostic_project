'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Home,
  Store,
  Stethoscope,
  UserRound,
  AlertTriangle,
  Phone,
  Clock,
  FileText,
  CheckCircle2,
  MapPin,
  ChevronRight,
  Loader2,
  Navigation,
} from 'lucide-react';
import { useAppStore } from '@/lib/store';
import { apiGetCenters, type ApiCenter } from '@/lib/api';
import { haversineKm, formatDistance } from '@/lib/geo';
import type { OrientationType, SymptomSummary } from '@/lib/types';

// ── Chargement dynamique de la carte (Leaflet incompatible avec SSR) ──────────
const HealthMap = dynamic(() => import('./health-map'), {
  ssr: false,
  loading: () => (
    <div className="h-[300px] bg-muted/30 rounded-xl flex items-center justify-center">
      <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
    </div>
  ),
});

// ── Configuration par orientation ─────────────────────────────────────────────

const orientationConfig: Record<
  OrientationType,
  {
    icon: React.ReactNode;
    title: string;
    description: string;
    delay: string;
    actions: string[];
    color: string;
    bgColor: string;
    borderColor: string;
    showMap: boolean; // Afficher la carte ou non
  }
> = {
  home: {
    icon: <Home className="w-6 h-6" />,
    title: 'Surveillance à domicile',
    description:
      'Vos symptômes ne nécessitent pas de consultation immédiate. Surveillez leur évolution.',
    delay: 'Consultez si les symptômes persistent plus de 48-72h',
    actions: [
      'Repos et hydratation',
      'Surveillance de la température',
      'Médicaments en vente libre si nécessaire',
    ],
    color: 'text-success',
    bgColor: 'bg-success/10',
    borderColor: 'border-success/20',
    showMap: false,
  },
  pharmacy: {
    icon: <Store className="w-6 h-6" />,
    title: 'Conseil en pharmacie',
    description:
      'Un pharmacien peut vous conseiller et vous orienter vers un traitement adapté.',
    delay: 'Dans la journée',
    actions: [
      'Décrire vos symptômes au pharmacien',
      'Mentionner vos traitements actuels',
      'Demander conseil pour un traitement approprié',
    ],
    color: 'text-success',
    bgColor: 'bg-success/10',
    borderColor: 'border-success/20',
    showMap: true,
  },
  doctor: {
    icon: <Stethoscope className="w-6 h-6" />,
    title: 'Consultation médecin',
    description: 'Une consultation avec votre médecin généraliste est recommandée.',
    delay: 'Dans les prochains jours',
    actions: [
      'Prendre rendez-vous avec votre médecin traitant',
      'Préparer votre fiche pré-consultation',
      'Noter l\'évolution des symptômes',
    ],
    color: 'text-primary',
    bgColor: 'bg-primary/10',
    borderColor: 'border-primary/20',
    showMap: true,
  },
  specialist: {
    icon: <UserRound className="w-6 h-6" />,
    title: 'Consultation spécialiste',
    description: "Vos symptômes nécessitent l'avis d'un médecin spécialiste.",
    delay: 'Selon disponibilité',
    actions: [
      'Consulter votre médecin traitant pour une orientation',
      'Demander une lettre d\'adressage si nécessaire',
      'Préparer votre dossier médical',
    ],
    color: 'text-primary',
    bgColor: 'bg-primary/10',
    borderColor: 'border-primary/20',
    showMap: true,
  },
  urgent: {
    icon: <AlertTriangle className="w-6 h-6" />,
    title: 'Urgences médicales',
    description: 'Vos symptômes nécessitent une prise en charge rapide aux urgences.',
    delay: 'Dans les 24 heures',
    actions: [
      'Se rendre aux urgences les plus proches',
      'Apporter votre carte vitale et mutuelle',
      'Apporter la liste de vos traitements',
    ],
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    borderColor: 'border-warning/20',
    showMap: true,
  },
  samu: {
    icon: <Phone className="w-6 h-6" />,
    title: 'Appelez le 15',
    description: 'ATTENTION : Vos symptômes nécessitent une intervention immédiate.',
    delay: 'IMMÉDIAT',
    actions: [
      'Appelez le 15 (SAMU) immédiatement',
      'Ne vous déplacez pas seul',
      'Restez au téléphone avec le régulateur',
    ],
    color: 'text-destructive',
    bgColor: 'bg-destructive/10',
    borderColor: 'border-destructive/20',
    showMap: false, // Le patient ne doit pas chercher des lieux — il doit appeler le 15
  },
};

// ── Props ─────────────────────────────────────────────────────────────────────

interface OrientationPanelProps {
  orientation: OrientationType;
  symptomSummary: Partial<SymptomSummary>;
  onViewSheet: () => void;
  hasSheet: boolean;
}

// ── Composant principal ───────────────────────────────────────────────────────

export default function OrientationPanel({
  orientation,
  symptomSummary,
  onViewSheet,
  hasSheet,
}: OrientationPanelProps) {
  const config = orientationConfig[orientation];
  const { currentUser } = useAppStore();
  const dept = currentUser?.department?.split(' - ')[0]; // "75 - Paris" → "75"
  const profileLat = currentUser?.lat ?? null;
  const profileLon = currentUser?.lon ?? null;

  // ── États GPS + centres ─────────────────────────────────────────────────────
  // userPos = position GPS LIVE (au moment de l'affichage de la carte)
  // profileLat/Lon = position enregistrée à l'onboarding (peut être plus ancienne)
  const [userPos, setUserPos] = useState<{ lat: number; lng: number } | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [centers, setCenters] = useState<ApiCenter[] | null>(null); // null = chargement
  const [gpsLoading, setGpsLoading] = useState(false);

  useEffect(() => {
    if (!config.showMap) return;

    // 1. Récupère la position GPS live (priorité pour centrer la carte).
    //    Si refus / indisponible → on retombera sur le profil ou le dept.
    if ('geolocation' in navigator) {
      setGpsLoading(true);
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude });
          setGpsLoading(false);
        },
        (err) => {
          console.warn('GPS non disponible:', err.message);
          setGpsError('Position GPS non disponible');
          setGpsLoading(false);
        },
        { timeout: 8000, maximumAge: 60000 }
      );
    } else {
      setGpsError('Géolocalisation non supportée par le navigateur');
    }

    // 2. Charge les établissements via l'API.
    //    Priorité 1 : coords du profil patient (onboarding) → recherche $near.
    //    Priorité 2 : dept du profil → recherche par département.
    //    Le backend gère les deux cas, on lui passe simplement ce qu'on a.
    const params: Parameters<typeof apiGetCenters>[0] =
      profileLat != null && profileLon != null
        ? { lat: profileLat, lon: profileLon }
        : dept
        ? { dept }
        : {};

    apiGetCenters(params)
      .then(({ centers: data }) => setCenters(data))
      .catch(() => setCenters([]));
  // Dépendance sur orientation pour recharger si l'orientation change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orientation, dept, profileLat, profileLon]);

  // Position effective pour centrer la carte :
  //   GPS live > profil onboarding > (sinon pas de carte)
  const mapCenter = userPos
    ? userPos
    : profileLat != null && profileLon != null
    ? { lat: profileLat, lng: profileLon }
    : null;

  // La carte est affichée si l'orientation le permet, qu'on a un point central
  // et au moins un établissement (avec ses propres coords) à montrer.
  const showMap =
    config.showMap &&
    mapCenter !== null &&
    centers !== null &&
    centers.some((c) => c.lat != null && c.lon != null);

  return (
    <div className="space-y-4">

      {/* ── Carte d'orientation principale ─────────────────────────────────── */}
      <Card className={`${config.borderColor} ${config.bgColor} border-2`}>
        <CardHeader className="pb-3">
          <div
            className={`w-12 h-12 rounded-xl ${config.bgColor} ${config.color} flex items-center justify-center mb-2`}
          >
            {config.icon}
          </div>
          <CardTitle className={`text-lg ${config.color}`}>{config.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-foreground/80">{config.description}</p>

          <div className="flex items-center gap-2 text-sm">
            <Clock className={`w-4 h-4 ${config.color}`} />
            <span className="font-medium">{config.delay}</span>
          </div>

          {/* ── Urgence SAMU ─────────────────────────────────────────────── */}
          {orientation === 'samu' && (
            <a
              href="tel:15"
              className="flex items-center justify-center gap-2 w-full py-3 bg-destructive text-destructive-foreground rounded-lg font-bold text-lg hover:bg-destructive/90 transition-colors"
            >
              <Phone className="w-5 h-5" />
              Appeler le 15
            </a>
          )}
        </CardContent>
      </Card>

      {/* ── Actions recommandées ───────────────────────────────────────────── */}
      <Card className="border-border/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-primary" />
            Actions recommandées
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {config.actions.map((action, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <ChevronRight className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                {action}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* ── Récapitulatif des symptômes ──────────────────────────────────── */}
      {symptomSummary.mainSymptom && (
        <Card className="border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Récapitulatif</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Symptôme</span>
              <span className="font-medium">{symptomSummary.mainSymptom}</span>
            </div>
            {symptomSummary.duration && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Durée</span>
                <span>{symptomSummary.duration}</span>
              </div>
            )}
            {symptomSummary.intensity && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Intensité</span>
                <span>{symptomSummary.intensity}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Bouton fiche pré-consultation ─────────────────────────────────── */}
      {hasSheet && (
        <Button onClick={onViewSheet} className="w-full gap-2">
          <FileText className="w-4 h-4" />
          Voir la fiche pré-consultation
        </Button>
      )}

      {/* ── Section carte & établissements ─────────────────────────────────── */}
      {config.showMap && (
        <Card className="border-border/50 overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <MapPin className="w-4 h-4 text-primary" />
              Établissements à proximité
              {(gpsLoading || centers === null) && (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground ml-auto" />
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pb-3">

            {/* Carte Leaflet — affichée si on a un centre et au moins un établissement géolocalisé */}
            {showMap && mapCenter && (
              <HealthMap
                userLat={mapCenter.lat}
                userLng={mapCenter.lng}
                centers={centers!}
              />
            )}

            {/* Message si GPS non disponible et pas de coords profil */}
            {gpsError && !userPos && profileLat == null && (
              <div className="flex items-start gap-2 p-3 bg-muted/40 rounded-lg text-sm text-muted-foreground">
                <Navigation className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-foreground/70">Position GPS indisponible</p>
                  <p className="text-xs mt-0.5">{gpsError}</p>
                </div>
              </div>
            )}

            {/* Message si chargement GPS en cours et qu'on n'a aucun fallback */}
            {gpsLoading && !userPos && profileLat == null && !gpsError && (
              <div className="flex items-center gap-2 p-3 bg-muted/30 rounded-lg text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                Récupération de votre position…
              </div>
            )}

            {/* Message si département non renseigné et pas de coords */}
            {!dept && profileLat == null && (
              <p className="text-sm text-muted-foreground text-center py-2">
                Renseignez votre département ou activez la géolocalisation dans votre profil.
              </p>
            )}

            {/* Message si pas de centres trouvés après chargement */}
            {centers !== null && centers.length === 0 && dept && (
              <p className="text-sm text-muted-foreground text-center py-2">
                Aucun établissement trouvé pour le département {dept}.
              </p>
            )}

            {/* Liste des centres (toujours visible quand dispo) */}
            {centers !== null && centers.length > 0 && (
              <div className="space-y-2 mt-1">
                {centers.slice(0, 6).map((center, i) => {
                  // Distance calculée si on a un point d'origine (GPS live ou profil)
                  // et si le centre lui-même est géolocalisé.
                  const origin =
                    userPos ?? (profileLat != null && profileLon != null
                      ? { lat: profileLat, lng: profileLon }
                      : null);
                  const distKm =
                    origin && center.lat != null && center.lon != null
                      ? haversineKm(origin.lat, origin.lng, center.lat, center.lon)
                      : null;

                  return (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 p-2.5 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors"
                    >
                      <MapPin className="w-3.5 h-3.5 text-muted-foreground mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-sm font-medium leading-snug truncate flex-1">
                            {center.name}
                          </p>
                          {distKm !== null && (
                            <span className="text-[10px] font-semibold tabular-nums shrink-0 px-1.5 py-0.5 bg-primary/10 text-primary rounded-md">
                              {formatDistance(distKm)}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5 truncate">
                          {center.category_label}
                        </p>
                        {center.address && (
                          <p className="text-xs text-muted-foreground truncate">
                            {center.address}
                          </p>
                        )}
                        {center.phone && (
                          <a
                            href={`tel:${center.phone.replace(/\s/g, '')}`}
                            className="text-xs text-primary hover:underline mt-0.5 inline-flex items-center gap-1"
                          >
                            <Phone className="w-3 h-3" />
                            {center.phone}
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

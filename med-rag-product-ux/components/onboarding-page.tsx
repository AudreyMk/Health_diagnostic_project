'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Stethoscope, ArrowLeft, ArrowRight, Check, User, Heart, Pill, MapPin, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

const DEPARTMENTS = [
  '75 - Paris', '13 - Bouches-du-Rhône', '69 - Rhône', '33 - Gironde',
  '59 - Nord', '44 - Loire-Atlantique', '31 - Haute-Garonne', '67 - Bas-Rhin',
  '06 - Alpes-Maritimes', '34 - Hérault', '35 - Ille-et-Vilaine', '76 - Seine-Maritime',
  '92 - Hauts-de-Seine', '93 - Seine-Saint-Denis', '94 - Val-de-Marne', '91 - Essonne',
  '78 - Yvelines', '77 - Seine-et-Marne', '95 - Val-d\'Oise',
];

export default function OnboardingPage() {
  const { onboardingData, updateOnboardingData, completeOnboarding, currentUser } = useAppStore();
  const [step, setStep] = useState(1);
  const [isSaving, setIsSaving] = useState(false);
  const totalSteps = 3;

  // ── Géolocalisation navigateur (HTML5) ───────────────────────────────────
  // Permet à MedRAG d'afficher des établissements à proximité réelle (et non par département).
  // Les coordonnées sont envoyées à PUT /auth/profile lors de completeOnboarding().
  const handleUseLocation = () => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      updateOnboardingData({
        basicInfo: { ...onboardingData.basicInfo, locationStatus: 'error' },
      });
      toast.error("Votre navigateur ne supporte pas la géolocalisation.");
      return;
    }
    updateOnboardingData({
      basicInfo: { ...onboardingData.basicInfo, locationStatus: 'requesting' },
    });
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        updateOnboardingData({
          basicInfo: {
            ...onboardingData.basicInfo,
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            locationStatus: 'granted',
          },
        });
        toast.success('Position enregistrée.');
      },
      (err) => {
        const status = err.code === err.PERMISSION_DENIED ? 'denied' : 'error';
        updateOnboardingData({
          basicInfo: { ...onboardingData.basicInfo, locationStatus: status },
        });
        toast.error(
          status === 'denied'
            ? 'Permission refusée — vous pouvez quand même utiliser MedRAG via votre département.'
            : "Impossible d'obtenir votre position."
        );
      },
      { timeout: 10000, maximumAge: 0, enableHighAccuracy: false }
    );
  };

  const handleFinish = async () => {
    setIsSaving(true);
    try {
      await completeOnboarding();
      toast.success('Profil créé avec succès !');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erreur lors de la sauvegarde';
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleNext = () => {
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      handleFinish();
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };

  const handleSkip = () => {
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      handleFinish();
    }
  };

  const progress = (step / totalSteps) * 100;

  const stepIcons = [
    <User key="user" className="w-5 h-5" />,
    <Heart key="heart" className="w-5 h-5" />,
    <Pill key="pill" className="w-5 h-5" />,
  ];

  const stepTitles = [
    'Informations de base',
    'Contexte médical',
    'Traitements et allergies',
  ];

  return (
    <div className="min-h-screen bg-background p-4 py-8">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center">
              <Stethoscope className="w-6 h-6 text-primary-foreground" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-foreground">
            Bienvenue {currentUser?.firstName || 'Patient'}
          </h1>
          <p className="text-muted-foreground">
            Créons votre profil santé pour personnaliser vos consultations
          </p>
        </div>

        {/* Progress */}
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                className={`flex items-center gap-2 ${
                  s <= step ? 'text-primary' : 'text-muted-foreground'
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                    s < step
                      ? 'bg-primary text-primary-foreground'
                      : s === step
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {s < step ? <Check className="w-4 h-4" /> : stepIcons[s - 1]}
                </div>
                <span className="text-sm font-medium hidden sm:inline">
                  {stepTitles[s - 1]}
                </span>
              </div>
            ))}
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* Form Card */}
        <Card className="border-border/50 shadow-lg">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {stepIcons[step - 1]}
              {stepTitles[step - 1]}
            </CardTitle>
            <CardDescription>
              {step === 1 && 'Ces informations nous aident à adapter nos questions.'}
              {step === 2 && 'Vos antécédents médicaux permettent une meilleure analyse.'}
              {step === 3 && 'Vos traitements actuels sont importants pour éviter les interactions.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Step 1: Basic Info */}
            {step === 1 && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="age">Âge</Label>
                  <Input
                    id="age"
                    type="number"
                    placeholder="35"
                    value={onboardingData.basicInfo.age}
                    onChange={(e) =>
                      updateOnboardingData({
                        basicInfo: { ...onboardingData.basicInfo, age: e.target.value },
                      })
                    }
                  />
                </div>

                <div className="space-y-3">
                  <Label>Sexe</Label>
                  <RadioGroup
                    value={onboardingData.basicInfo.sex}
                    onValueChange={(value) =>
                      updateOnboardingData({
                        basicInfo: { ...onboardingData.basicInfo, sex: value },
                      })
                    }
                    className="flex gap-4"
                  >
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="male" id="male" />
                      <Label htmlFor="male" className="font-normal cursor-pointer">
                        Homme
                      </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="female" id="female" />
                      <Label htmlFor="female" className="font-normal cursor-pointer">
                        Femme
                      </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="other" id="other" />
                      <Label htmlFor="other" className="font-normal cursor-pointer">
                        Autre
                      </Label>
                    </div>
                  </RadioGroup>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="department">Département</Label>
                  <Select
                    value={onboardingData.basicInfo.department}
                    onValueChange={(value) =>
                      updateOnboardingData({
                        basicInfo: { ...onboardingData.basicInfo, department: value },
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Sélectionnez votre département" />
                    </SelectTrigger>
                    <SelectContent>
                      {DEPARTMENTS.map((dept) => (
                        <SelectItem key={dept} value={dept}>
                          {dept}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* ── Géolocalisation précise (optionnelle) ── */}
                <div className="space-y-2 rounded-lg border border-border/60 bg-muted/30 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <Label className="flex items-center gap-2">
                        <MapPin className="w-4 h-4" />
                        Position précise (optionnel)
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        Pour vous proposer les établissements de santé les plus proches.
                        Vous pouvez refuser — nous utiliserons votre département.
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant={
                        onboardingData.basicInfo.locationStatus === 'granted'
                          ? 'secondary'
                          : 'outline'
                      }
                      size="sm"
                      onClick={handleUseLocation}
                      disabled={onboardingData.basicInfo.locationStatus === 'requesting'}
                      className="gap-2 shrink-0"
                    >
                      {onboardingData.basicInfo.locationStatus === 'requesting' ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Localisation…
                        </>
                      ) : onboardingData.basicInfo.locationStatus === 'granted' ? (
                        <>
                          <Check className="w-4 h-4" />
                          Position OK
                        </>
                      ) : (
                        <>
                          <MapPin className="w-4 h-4" />
                          Utiliser ma position
                        </>
                      )}
                    </Button>
                  </div>
                  {onboardingData.basicInfo.locationStatus === 'granted' &&
                    onboardingData.basicInfo.lat != null &&
                    onboardingData.basicInfo.lon != null && (
                      <p className="text-xs text-emerald-700 dark:text-emerald-400 pt-1">
                        Coordonnées enregistrées ({onboardingData.basicInfo.lat.toFixed(3)},{' '}
                        {onboardingData.basicInfo.lon.toFixed(3)}).
                      </p>
                    )}
                  {(onboardingData.basicInfo.locationStatus === 'denied' ||
                    onboardingData.basicInfo.locationStatus === 'error') && (
                    <p className="text-xs text-amber-700 dark:text-amber-400 pt-1 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      Position non disponible — le département sera utilisé pour la recherche
                      d&apos;établissements.
                    </p>
                  )}
                </div>
              </>
            )}

            {/* Step 2: Medical Context */}
            {step === 2 && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="history">Antécédents médicaux</Label>
                  <Textarea
                    id="history"
                    placeholder="Ex: Opération appendicite 2015, fracture bras 2018..."
                    value={onboardingData.medicalContext.medicalHistory}
                    onChange={(e) =>
                      updateOnboardingData({
                        medicalContext: {
                          ...onboardingData.medicalContext,
                          medicalHistory: e.target.value,
                        },
                      })
                    }
                    className="min-h-[100px]"
                  />
                  <p className="text-xs text-muted-foreground">
                    Séparez les éléments par des virgules
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="chronic">Maladies chroniques</Label>
                  <Textarea
                    id="chronic"
                    placeholder="Ex: Diabète type 2, hypertension..."
                    value={onboardingData.medicalContext.chronicConditions}
                    onChange={(e) =>
                      updateOnboardingData({
                        medicalContext: {
                          ...onboardingData.medicalContext,
                          chronicConditions: e.target.value,
                        },
                      })
                    }
                    className="min-h-[80px]"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="other">Autres informations</Label>
                  <Textarea
                    id="other"
                    placeholder="Informations complémentaires..."
                    value={onboardingData.medicalContext.otherInfo}
                    onChange={(e) =>
                      updateOnboardingData({
                        medicalContext: {
                          ...onboardingData.medicalContext,
                          otherInfo: e.target.value,
                        },
                      })
                    }
                    className="min-h-[60px]"
                  />
                </div>
              </>
            )}

            {/* Step 3: Treatments & Allergies */}
            {step === 3 && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="treatments">Traitements en cours</Label>
                  <Textarea
                    id="treatments"
                    placeholder="Ex: Metformine 500mg, Amlodipine 5mg..."
                    value={onboardingData.treatmentsAllergies.currentTreatments}
                    onChange={(e) =>
                      updateOnboardingData({
                        treatmentsAllergies: {
                          ...onboardingData.treatmentsAllergies,
                          currentTreatments: e.target.value,
                        },
                      })
                    }
                    className="min-h-[80px]"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="allergies">Allergies</Label>
                  <Textarea
                    id="allergies"
                    placeholder="Ex: Pénicilline, arachides, latex..."
                    value={onboardingData.treatmentsAllergies.allergies}
                    onChange={(e) =>
                      updateOnboardingData({
                        treatmentsAllergies: {
                          ...onboardingData.treatmentsAllergies,
                          allergies: e.target.value,
                        },
                      })
                    }
                    className="min-h-[60px]"
                  />
                </div>

                <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                  <div className="space-y-0.5">
                    <Label htmlFor="smoking" className="cursor-pointer">
                      Tabagisme
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      Fumez-vous actuellement ?
                    </p>
                  </div>
                  <Switch
                    id="smoking"
                    checked={onboardingData.treatmentsAllergies.smoking}
                    onCheckedChange={(checked) =>
                      updateOnboardingData({
                        treatmentsAllergies: {
                          ...onboardingData.treatmentsAllergies,
                          smoking: checked,
                        },
                      })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="activity">Activité physique</Label>
                  <Select
                    value={onboardingData.treatmentsAllergies.physicalActivity}
                    onValueChange={(value) =>
                      updateOnboardingData({
                        treatmentsAllergies: {
                          ...onboardingData.treatmentsAllergies,
                          physicalActivity: value,
                        },
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Niveau d'activité" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Sédentaire</SelectItem>
                      <SelectItem value="light">Légère (1-2x/semaine)</SelectItem>
                      <SelectItem value="moderate">Modérée (3-4x/semaine)</SelectItem>
                      <SelectItem value="active">Active (5+/semaine)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}

            {/* Navigation Buttons */}
            <div className="flex items-center justify-between pt-4 border-t">
              <Button
                variant="ghost"
                onClick={handleBack}
                disabled={step === 1 || isSaving}
                className="gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Retour
              </Button>

              <Button
                variant="ghost"
                onClick={handleSkip}
                disabled={isSaving}
                className="text-muted-foreground"
              >
                Passer
              </Button>

              <Button onClick={handleNext} disabled={isSaving} className="gap-2">
                {isSaving ? (
                  <>Enregistrement…</>
                ) : step === totalSteps ? (
                  <>
                    Terminer
                    <Check className="w-4 h-4" />
                  </>
                ) : (
                  <>
                    Suivant
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Info text */}
        <p className="text-center text-xs text-muted-foreground">
          Ces informations aident MedRAG à adapter ses questions et améliorer la qualité de
          l&apos;analyse. Vous pourrez les modifier à tout moment.
        </p>
      </div>
    </div>
  );
}

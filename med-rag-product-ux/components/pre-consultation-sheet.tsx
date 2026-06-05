'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  ArrowLeft, 
  Printer, 
  Copy, 
  Download,
  User,
  Brain,
  HelpCircle,
  AlertTriangle,
  Clock,
  FileText,
  Stethoscope,
  CheckCircle2
} from 'lucide-react';
import { toast } from 'sonner';
import type { PreConsultationSheet as PreConsultationSheetType, OrientationType } from '@/lib/types';

interface PreConsultationSheetProps {
  sheet: PreConsultationSheetType;
  onBack: () => void;
}

const orientationLabels: Record<OrientationType, string> = {
  home: 'Surveillance à domicile',
  pharmacy: 'Conseil en pharmacie',
  doctor: 'Consultation médecin généraliste',
  specialist: 'Consultation spécialiste',
  urgent: 'Urgences',
  samu: 'SAMU - 15',
};

const orientationColors: Record<OrientationType, string> = {
  home: 'bg-success/10 text-success border-success/20',
  pharmacy: 'bg-success/10 text-success border-success/20',
  doctor: 'bg-primary/10 text-primary border-primary/20',
  specialist: 'bg-primary/10 text-primary border-primary/20',
  urgent: 'bg-warning/10 text-warning border-warning/20',
  samu: 'bg-destructive/10 text-destructive border-destructive/20',
};

export default function PreConsultationSheet({ sheet, onBack }: PreConsultationSheetProps) {
  const handleCopy = async () => {
    const text = generatePlainText(sheet);
    await navigator.clipboard.writeText(text);
    toast.success('Fiche copiée dans le presse-papier');
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDownload = () => {
    const text = generatePlainText(sheet);
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fiche-preconsultation-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Fiche téléchargée');
  };

  return (
    <div className="min-h-screen bg-background print:bg-white">
      {/* Header - Hidden on print */}
      <header className="sticky top-0 z-50 bg-card border-b border-border/50 print:hidden">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={onBack}>
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-primary" />
              <span className="font-semibold text-foreground">Fiche pré-consultation</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleCopy} className="gap-2">
              <Copy className="w-4 h-4" />
              <span className="hidden sm:inline">Copier</span>
            </Button>
            <Button variant="outline" size="sm" onClick={handlePrint} className="gap-2">
              <Printer className="w-4 h-4" />
              <span className="hidden sm:inline">Imprimer</span>
            </Button>
            <Button variant="default" size="sm" onClick={handleDownload} className="gap-2">
              <Download className="w-4 h-4" />
              <span className="hidden sm:inline">Télécharger</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6 print:py-4 print:px-8">
        {/* Print Header */}
        <div className="hidden print:flex print:items-center print:justify-between print:mb-6">
          <div className="flex items-center gap-2">
            <Stethoscope className="w-6 h-6" />
            <span className="text-xl font-bold">MedRAG</span>
          </div>
          <p className="text-sm text-gray-500">
            Généré le {new Date().toLocaleDateString('fr-FR')}
          </p>
        </div>

        {/* Section 1: Patient-Declared Information */}
        <Card className="border-border/50 print:border print:shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <User className="w-5 h-5 text-primary" />
              Informations déclarées par le patient
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <InfoItem label="Motif principal" value={sheet.patientInfo.mainComplaint} />
              <InfoItem label="Durée des symptômes" value={sheet.patientInfo.duration} />
              <InfoItem label="Intensité" value={sheet.patientInfo.intensity} />
              <InfoItem 
                label="Contexte médical" 
                value={sheet.patientInfo.medicalContext || 'Non renseigné'} 
              />
            </div>
            
            <Separator />
            
            <div className="grid md:grid-cols-2 gap-4">
              {sheet.patientInfo.associatedSymptoms.length > 0 && (
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Symptômes associés</p>
                  <div className="flex flex-wrap gap-1">
                    {sheet.patientInfo.associatedSymptoms.map((symptom, i) => (
                      <Badge key={i} variant="secondary">{symptom}</Badge>
                    ))}
                  </div>
                </div>
              )}
              
              {sheet.patientInfo.aggravatingFactors.length > 0 && (
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Facteurs aggravants</p>
                  <div className="flex flex-wrap gap-1">
                    {sheet.patientInfo.aggravatingFactors.map((factor, i) => (
                      <Badge key={i} variant="outline" className="text-warning border-warning/30">
                        {factor}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              
              {sheet.patientInfo.relievingFactors.length > 0 && (
                <div>
                  <p className="text-sm text-muted-foreground mb-2">Facteurs calmants</p>
                  <div className="flex flex-wrap gap-1">
                    {sheet.patientInfo.relievingFactors.map((factor, i) => (
                      <Badge key={i} variant="outline" className="text-success border-success/30">
                        {factor}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Section 2: AI Analysis */}
        <Card className="border-primary/20 bg-primary/5 print:border print:bg-gray-50 print:shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Brain className="w-5 h-5 text-primary" />
              Analyse générée par l&apos;IA
              <Badge variant="outline" className="ml-2 text-xs">Hypothèses</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Possible Diagnoses */}
            <div>
              <p className="text-sm font-medium mb-2">Pistes diagnostiques possibles</p>
              <ul className="space-y-1">
                {sheet.aiAnalysis.possibleDiagnoses.map((diagnosis, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                    {diagnosis}
                  </li>
                ))}
              </ul>
            </div>

            {/* Alert Signs */}
            {sheet.aiAnalysis.alertSigns.length > 0 && (
              <div className="p-3 bg-destructive/10 rounded-lg border border-destructive/20 print:bg-red-50">
                <div className="flex items-center gap-2 text-destructive font-medium mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  Signes d&apos;alerte identifiés
                </div>
                <ul className="space-y-1">
                  {sheet.aiAnalysis.alertSigns.map((sign, i) => (
                    <li key={i} className="text-sm text-destructive/80">• {sign}</li>
                  ))}
                </ul>
              </div>
            )}

            <Separator />

            {/* Orientation */}
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Orientation recommandée</p>
                <Badge 
                  variant="outline" 
                  className={`text-sm px-3 py-1 ${orientationColors[sheet.aiAnalysis.recommendedOrientation]}`}
                >
                  {orientationLabels[sheet.aiAnalysis.recommendedOrientation]}
                </Badge>
              </div>
              <div>
                <p className="text-sm text-muted-foreground mb-1">Délai conseillé</p>
                <div className="flex items-center gap-2 font-medium">
                  <Clock className="w-4 h-4 text-muted-foreground" />
                  {sheet.aiAnalysis.recommendedDelay}
                </div>
              </div>
            </div>

            <p className="text-sm text-muted-foreground italic">
              {sheet.aiAnalysis.justification}
            </p>
          </CardContent>
        </Card>

        {/* Section 3: Questions for Doctor */}
        <Card className="border-border/50 print:border print:shadow-none">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <HelpCircle className="w-5 h-5 text-primary" />
              Questions à poser au médecin
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {sheet.questionsForDoctor.map((question, i) => (
                <li key={i} className="flex items-start gap-3 text-sm">
                  <span className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0 text-xs font-medium">
                    {i + 1}
                  </span>
                  {question}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* Disclaimer */}
        <div className="p-4 bg-muted/50 rounded-lg border border-border/50 print:bg-gray-100">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
            <p className="text-sm text-muted-foreground">
              {sheet.disclaimer}
            </p>
          </div>
        </div>

        {/* Back Button - Hidden on print */}
        <div className="flex justify-center print:hidden">
          <Button variant="outline" onClick={onBack} className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            Retour à la consultation
          </Button>
        </div>
      </main>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="font-medium">{value || '-'}</p>
    </div>
  );
}

function generatePlainText(sheet: PreConsultationSheetType): string {
  return `
FICHE DE PRÉ-CONSULTATION MEDRAG
================================
Généré le ${new Date().toLocaleDateString('fr-FR')}

INFORMATIONS DÉCLARÉES PAR LE PATIENT
-------------------------------------
Motif principal: ${sheet.patientInfo.mainComplaint}
Durée: ${sheet.patientInfo.duration}
Intensité: ${sheet.patientInfo.intensity}
Symptômes associés: ${sheet.patientInfo.associatedSymptoms.join(', ') || 'Aucun'}
Facteurs aggravants: ${sheet.patientInfo.aggravatingFactors.join(', ') || 'Aucun'}
Facteurs calmants: ${sheet.patientInfo.relievingFactors.join(', ') || 'Aucun'}
Contexte médical: ${sheet.patientInfo.medicalContext || 'Non renseigné'}

ANALYSE GÉNÉRÉE PAR L'IA (HYPOTHÈSES)
-------------------------------------
Pistes diagnostiques possibles:
${sheet.aiAnalysis.possibleDiagnoses.map(d => `• ${d}`).join('\n')}

Signes d'alerte: ${sheet.aiAnalysis.alertSigns.length > 0 ? sheet.aiAnalysis.alertSigns.join(', ') : 'Aucun identifié'}

Orientation recommandée: ${orientationLabels[sheet.aiAnalysis.recommendedOrientation]}
Délai conseillé: ${sheet.aiAnalysis.recommendedDelay}

${sheet.aiAnalysis.justification}

QUESTIONS À POSER AU MÉDECIN
----------------------------
${sheet.questionsForDoctor.map((q, i) => `${i + 1}. ${q}`).join('\n')}

AVERTISSEMENT
-------------
${sheet.disclaimer}
`.trim();
}

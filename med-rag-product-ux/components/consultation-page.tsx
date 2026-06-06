'use client';

import { useState, useRef, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Stethoscope,
  ArrowLeft,
  Send,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ThermometerSun,
  Activity,
  FileText,
  Plus,
  MessageSquare,
  ChevronRight,
  PanelRightClose,
  PanelRightOpen,
  GripVertical,
} from 'lucide-react';
import { toast } from 'sonner';
import type { ChatPhase, Message } from '@/lib/types';
import PreConsultationSheet from './pre-consultation-sheet';
import OrientationPanel from './orientation-panel';

interface ConsultationPageProps {
  onNavigate: (view: 'auth' | 'onboarding' | 'dashboard' | 'consultation' | 'history') => void;
}

const QUICK_REPLIES_DEFAULT = ['Oui', 'Non', 'Je ne sais pas', 'Depuis hier'];

const ORIENTATION_COLORS: Record<string, string> = {
  home: 'bg-success/15 text-success',
  pharmacy: 'bg-success/15 text-success',
  doctor: 'bg-primary/15 text-primary',
  specialist: 'bg-primary/15 text-primary',
  urgent: 'bg-warning/15 text-warning',
  samu: 'bg-destructive/15 text-destructive',
};

const ORIENTATION_LABELS: Record<string, string> = {
  home: 'Domicile',
  pharmacy: 'Pharmacie',
  doctor: 'Médecin',
  specialist: 'Spécialiste',
  urgent: 'Urgences',
  samu: 'SAMU',
};

// ── Utilitaires ───────────────────────────────────────────────────────────────

/** Supprime le markdown brut pour un affichage propre dans la sidebar */
function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')   // **gras** → gras
    .replace(/\*([^*]+)\*/g, '$1')        // *italique* → italique
    .replace(/^#{1,6}\s+/gm, '')          // ### titres
    .replace(/^---+\s*/gm, '')            // séparateurs ---
    .replace(/^[-•>]\s+/gm, '')           // puces / blockquotes
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // [liens](url)
    .trim();
}

// ── Rendu Markdown léger (sans dépendance externe) ────────────────────────────

function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2 && !part.startsWith('**')) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    return <span key={i}>{part}</span>;
  });
}

function MessageContent({ content }: { content: string }) {
  const lines = content.split('\n');
  const result: React.ReactNode[] = [];
  let listBuffer: React.ReactNode[] = [];

  const flushList = (key: string) => {
    if (listBuffer.length === 0) return;
    result.push(
      <ul key={key} className="my-1 space-y-1 ml-1">
        {listBuffer}
      </ul>
    );
    listBuffer = [];
  };

  lines.forEach((line, i) => {
    const trimmed = line.trim();

    // Listes à puces
    if (/^[-•]\s/.test(trimmed)) {
      listBuffer.push(
        <li key={i} className="flex items-start gap-2">
          <span className="mt-[7px] w-1.5 h-1.5 rounded-full bg-current shrink-0 opacity-50" />
          <span>{renderInline(trimmed.slice(2))}</span>
        </li>
      );
      return;
    }

    // Listes numérotées
    const numMatch = trimmed.match(/^(\d+)\.\s(.+)/);
    if (numMatch) {
      listBuffer.push(
        <li key={i} className="flex items-start gap-2">
          <span className="font-semibold tabular-nums shrink-0 min-w-[1.2em]">{numMatch[1]}.</span>
          <span>{renderInline(numMatch[2])}</span>
        </li>
      );
      return;
    }

    flushList(`ul-${i}`);

    if (trimmed === '') {
      if (result.length > 0) result.push(<div key={`sp-${i}`} className="h-1" />);
      return;
    }

    // Titres
    if (trimmed.startsWith('### ')) {
      result.push(<p key={i} className="font-semibold mt-2 mb-0.5">{renderInline(trimmed.slice(4))}</p>);
      return;
    }
    if (trimmed.startsWith('## ')) {
      result.push(<p key={i} className="font-semibold text-base mt-2 mb-0.5">{renderInline(trimmed.slice(3))}</p>);
      return;
    }

    result.push(<p key={i} className="leading-relaxed">{renderInline(trimmed)}</p>);
  });

  flushList('ul-end');

  return <div className="space-y-1 text-[15px]">{result}</div>;
}

// ── Page consultation ──────────────────────────────────────────────────────────

export default function ConsultationPage({ onNavigate }: ConsultationPageProps) {
  const {
    currentConsultation,
    consultations,
    sendMessage,
    closeConsultation,
    startNewConsultation,
    resumeConsultation,
  } = useAppStore();

  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showSheet, setShowSheet] = useState(false);
  const [isLoadingConv, setIsLoadingConv] = useState(false);

  // ── Sidebar droite redimensionnable + collapsable ──────────────────────
  // Largeur en px (entre SIDEBAR_MIN et SIDEBAR_MAX), persistée dans localStorage.
  const SIDEBAR_MIN = 320;
  const SIDEBAR_MAX = 720;
  const SIDEBAR_DEFAULT = 460;
  const [sidebarWidth, setSidebarWidth] = useState<number>(SIDEBAR_DEFAULT);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(false);
  const [isResizing, setIsResizing] = useState<boolean>(false);

  // Restaure depuis localStorage au mount
  useEffect(() => {
    try {
      const w = localStorage.getItem('medrag.sidebarWidth');
      const c = localStorage.getItem('medrag.sidebarCollapsed');
      if (w) {
        const n = parseInt(w, 10);
        if (!isNaN(n) && n >= SIDEBAR_MIN && n <= SIDEBAR_MAX) setSidebarWidth(n);
      }
      if (c === '1') setSidebarCollapsed(true);
    } catch { /* ignore */ }
  }, []);

  // Drag handlers globaux (mousemove + mouseup) actifs uniquement pendant le resize
  useEffect(() => {
    if (!isResizing) return;
    const onMove = (e: MouseEvent) => {
      // La sidebar est ancrée à droite : sa largeur = innerWidth - clientX
      const next = Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, window.innerWidth - e.clientX));
      setSidebarWidth(next);
    };
    const onUp = () => {
      setIsResizing(false);
      try { localStorage.setItem('medrag.sidebarWidth', String(sidebarWidth)); } catch { /* ignore */ }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, sidebarWidth]);

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem('medrag.sidebarCollapsed', next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const chatPhase: ChatPhase = currentConsultation?.orientation
    ? 'orientation'
    : isTyping
    ? 'analyzing'
    : 'collecting';

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentConsultation?.messages, isTyping]);

  const handleSendMessage = async (message: string) => {
    const text = message.trim();
    if (!text || isTyping || !currentConsultation) return;
    setInputValue('');
    setIsTyping(true);
    try {
      await sendMessage(text);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erreur serveur';
      if (msg.includes('réseau') || msg.includes('fetch')) {
        toast.error('Impossible de contacter le serveur.');
      } else {
        toast.error('❌ ' + msg);
      }
    } finally {
      setIsTyping(false);
      inputRef.current?.focus();
    }
  };

  const handleQuickReply = (reply: string) => handleSendMessage(reply);

  const handleBack = () => {
    closeConsultation();
    onNavigate('dashboard');
  };

  const handleNewConsultation = async () => {
    try {
      await startNewConsultation();
      setShowSheet(false);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erreur');
    }
  };

  const handleSwitchConsultation = async (id: string) => {
    if (id === currentConsultation?.id || id === currentConsultation?.backendId) return;
    setIsLoadingConv(true);
    setShowSheet(false);
    try {
      await resumeConsultation(id);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setIsLoadingConv(false);
    }
  };

  if (!currentConsultation) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  if (showSheet && currentConsultation.preConsultationSheet) {
    return (
      <PreConsultationSheet
        sheet={currentConsultation.preConsultationSheet}
        onBack={() => setShowSheet(false)}
      />
    );
  }

  const sortedConsultations = [...consultations].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  );

  return (
    <div className="h-screen bg-background flex flex-col overflow-hidden">

      {/* ── Header ── */}
      <header className="shrink-0 bg-card border-b border-border/50 z-50">
        <div className="px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={handleBack}>
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <Stethoscope className="w-4 h-4 text-primary-foreground" />
              </div>
              <span className="font-semibold text-base text-foreground">MedRAG</span>
            </div>
          </div>

          <Badge variant="outline" className="gap-1.5 text-xs px-3 py-1">
            {chatPhase === 'collecting' && (
              <><Activity className="w-3 h-3" />Collecte en cours</>
            )}
            {chatPhase === 'analyzing' && (
              <><Loader2 className="w-3 h-3 animate-spin" />Analyse…</>
            )}
            {chatPhase === 'orientation' && (
              <><CheckCircle2 className="w-3 h-3 text-success" />Orientation générée</>
            )}
          </Badge>
        </div>
      </header>

      {/* ── Corps ── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ── Sidebar gauche ── */}
        <aside className="hidden lg:flex flex-col w-60 shrink-0 border-r border-border/50 bg-sidebar min-h-0">

          <div className="p-3 border-b border-border/40">
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 justify-start font-medium"
              onClick={handleNewConsultation}
              disabled={isTyping}
            >
              <Plus className="w-3.5 h-3.5" />
              Nouvelle consultation
            </Button>
          </div>

          <p className="px-3 pt-3 pb-1.5 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Historique
          </p>

          <div className="flex-1 overflow-y-auto min-h-0 px-2 pb-2 space-y-0.5">
            {sortedConsultations.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6 px-2">
                Aucune consultation précédente
              </p>
            ) : (
              sortedConsultations.map((conv) => {
                const isActive =
                  conv.id === currentConsultation.id ||
                  conv.backendId === currentConsultation.backendId;

                return (
                  <button
                    key={conv.id}
                    onClick={() => handleSwitchConsultation(conv.id)}
                    disabled={isLoadingConv}
                    className={`w-full text-left rounded-lg px-2.5 py-2 transition-colors ${
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted/70 text-foreground'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <MessageSquare
                        className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                          isActive ? 'text-primary' : 'text-muted-foreground'
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        {/* stripMarkdown : évite d'afficher --- **Synthèse** Vous p... */}
                        <p className="text-sm font-medium leading-snug truncate">
                          {stripMarkdown(conv.title || 'Consultation') || 'Consultation'}
                        </p>
                        <p className="text-sm text-muted-foreground mt-0.5">
                          {new Date(conv.updatedAt).toLocaleDateString('fr-FR', {
                            day: 'numeric',
                            month: 'short',
                          })}
                        </p>
                        {conv.orientation && (
                          <span
                            className={`inline-block mt-1 text-xs px-1.5 py-0.5 rounded-full font-medium ${
                              ORIENTATION_COLORS[conv.orientation] || ''
                            }`}
                          >
                            {ORIENTATION_LABELS[conv.orientation]}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          <div className="p-2 border-t border-border/40">
            <button
              onClick={() => onNavigate('history')}
              className="w-full text-sm text-muted-foreground hover:text-foreground py-2 flex items-center justify-center gap-1 transition-colors rounded hover:bg-muted/50"
            >
              Voir tout l&apos;historique
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </aside>

        {/* ── Chat ── */}
        {/* overflow-hidden obligatoire : empêche le flex-child de s'étirer au-delà du viewport */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative border-r border-border/50">

          {isLoadingConv && (
            <div className="absolute inset-0 bg-background/70 flex items-center justify-center z-20">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          )}

          {/* div natif overflow-y-auto — ScrollArea Radix ne gère pas flex-1 correctement */}
          <div className="flex-1 overflow-y-auto px-4 pt-4 pb-2">
            <div className="space-y-3 max-w-2xl mx-auto">
              {currentConsultation.messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}

              {isTyping && (
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0">
                    <Stethoscope className="w-4 h-4 text-primary-foreground" />
                  </div>
                  <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:0ms]" />
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:150ms]" />
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:300ms]" />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {chatPhase === 'collecting' && !isTyping && currentConsultation.messages.length > 1 && (
            <div className="px-4 py-2 border-t border-border/30">
              <div className="max-w-2xl mx-auto flex flex-wrap gap-2">
                {QUICK_REPLIES_DEFAULT.map((reply, i) => (
                  <Button
                    key={i}
                    variant="outline"
                    onClick={() => handleQuickReply(reply)}
                    className="text-[15px] h-9 px-4"
                  >
                    {reply}
                  </Button>
                ))}
              </div>
            </div>
          )}

          <div className="px-4 py-3 border-t border-border/50 bg-card/50">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(inputValue);
              }}
              className="max-w-2xl mx-auto flex gap-2"
            >
              <Input
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder={
                  chatPhase === 'orientation'
                    ? 'Consultation terminée — orientation générée'
                    : 'Décrivez vos symptômes…'
                }
                disabled={isTyping || chatPhase === 'orientation'}
                className="flex-1 text-[15px] h-10"
                autoFocus
              />
              <Button
                type="submit"
                className="h-10 px-4"
                disabled={!inputValue.trim() || isTyping || chatPhase === 'orientation'}
              >
                {isTyping ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </form>
            <p className="text-center text-sm text-muted-foreground mt-2">
              Outil d&apos;orientation uniquement · ne remplace pas un médecin · Urgence : <strong>15</strong> (SAMU)
            </p>
          </div>
        </div>

        {/* ── Panneau droit (XL) — redimensionnable + collapsable ── */}
        {sidebarCollapsed ? (
          // ─ Mode rétracté : barre verticale fine avec bouton d'expansion ─
          <div className="hidden xl:flex flex-col w-10 shrink-0 border-l border-border/50 bg-muted/30 items-center py-3">
            <button
              onClick={toggleSidebar}
              className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
              title="Déplier le panneau"
              aria-label="Déplier le panneau latéral"
            >
              <PanelRightOpen className="w-4 h-4" />
            </button>
            <div className="mt-3 text-[10px] text-muted-foreground/70 font-medium tracking-wider [writing-mode:vertical-rl] rotate-180">
              {chatPhase === 'orientation' ? 'ORIENTATION' : 'RÉSUMÉ'}
            </div>
          </div>
        ) : (
          // ─ Mode normal : sidebar resizable avec drag handle à gauche ─
          <div
            className="hidden xl:flex flex-col shrink-0 overflow-hidden min-h-0 relative border-l border-border/50"
            style={{ width: `${sidebarWidth}px` }}
          >
            {/* Drag handle (poignée de redimensionnement) */}
            <div
              onMouseDown={(e) => { e.preventDefault(); setIsResizing(true); }}
              onDoubleClick={() => setSidebarWidth(SIDEBAR_DEFAULT)}
              className={`group absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize z-10 transition-colors ${
                isResizing ? 'bg-primary/40' : 'hover:bg-primary/25'
              }`}
              title="Glisser pour redimensionner — double-clic pour réinitialiser"
            >
              <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/4 opacity-0 group-hover:opacity-100 transition-opacity">
                <GripVertical className="w-3.5 h-3.5 text-primary/70" />
              </div>
            </div>

            {/* Bouton de collapse en haut à droite */}
            <div className="absolute top-2 right-2 z-10">
              <button
                onClick={toggleSidebar}
                className="p-1.5 rounded-md bg-background/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/50 backdrop-blur-sm transition-colors"
                title="Réduire le panneau"
                aria-label="Réduire le panneau latéral"
              >
                <PanelRightClose className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              <div className="p-4 pr-3 pt-12">
                {chatPhase !== 'orientation' ? (
                  <SummaryPanel consultation={currentConsultation} isTyping={isTyping} />
                ) : (
                  <OrientationPanel
                    orientation={currentConsultation.orientation!}
                    symptomSummary={currentConsultation.symptomSummary}
                    onViewSheet={() => setShowSheet(true)}
                    hasSheet={!!currentConsultation.preConsultationSheet}
                  />
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Mobile — bouton fiche flottant */}
      <div className="xl:hidden fixed bottom-6 right-4">
        {chatPhase === 'orientation' && currentConsultation.preConsultationSheet && (
          <Button onClick={() => setShowSheet(true)} className="shadow-lg gap-2">
            <FileText className="w-4 h-4" />
            Voir la fiche
          </Button>
        )}
      </div>
    </div>
  );
}

// ── Bulle de message ───────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: Message }) {
  const isAssistant = message.role === 'assistant';

  return (
    <div className={`flex items-start gap-3 ${!isAssistant ? 'flex-row-reverse' : ''}`}>
      {isAssistant ? (
        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0 mt-0.5">
          <Stethoscope className="w-4 h-4 text-primary-foreground" />
        </div>
      ) : (
        <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0 mt-0.5">
          <span className="text-sm font-semibold text-secondary-foreground">P</span>
        </div>
      )}
      <div
        className={`max-w-[78%] rounded-2xl px-4 py-2.5 ${
          isAssistant
            ? 'bg-card border border-border/70 rounded-tl-sm'
            : 'bg-primary text-primary-foreground rounded-tr-sm'
        }`}
      >
        {isAssistant ? (
          <MessageContent content={message.content} />
        ) : (
          <p className="text-[15px] leading-relaxed">{message.content}</p>
        )}
      </div>
    </div>
  );
}

// ── Panneau résumé ────────────────────────────────────────────────────────────

function SummaryPanel({
  consultation,
  isTyping,
}: {
  consultation: NonNullable<ReturnType<typeof useAppStore>['currentConsultation']>;
  isTyping: boolean;
}) {
  const summary = consultation.symptomSummary;
  const hasData = summary.mainSymptom || summary.duration || summary.intensity;

  return (
    <Card className="border-border/50">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          Résumé en cours
          {isTyping && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground ml-auto" />}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-[14px]">
        {!hasData ? (
          <>
            <p className="text-muted-foreground text-center py-3 text-sm">
              Les informations importantes apparaîtront ici pendant la conversation.
            </p>
            <div className="bg-muted/30 rounded-lg p-3 space-y-1.5">
              <p className="text-sm font-medium text-muted-foreground">💡 Pour une meilleure analyse :</p>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Précisez la durée des symptômes</li>
                <li>• Évaluez la douleur sur 10</li>
                <li>• Mentionnez les facteurs aggravants</li>
                <li>• Signalez tout signe inhabituel</li>
              </ul>
            </div>
          </>
        ) : (
          <>
            {summary.mainSymptom && (
              <SummaryItem
                icon={<ThermometerSun className="w-4 h-4" />}
                label="Symptôme principal"
                value={summary.mainSymptom}
              />
            )}
            {summary.duration && (
              <SummaryItem
                icon={<Clock className="w-4 h-4" />}
                label="Durée"
                value={summary.duration}
              />
            )}
            {summary.intensity && (
              <SummaryItem
                icon={<Activity className="w-4 h-4" />}
                label="Intensité"
                value={summary.intensity}
              />
            )}
            {summary.associatedSymptoms && summary.associatedSymptoms.length > 0 && (
              <SummaryItem label="Symptômes associés" value={summary.associatedSymptoms.join(', ')} />
            )}
            {summary.aggravatingFactors && summary.aggravatingFactors.length > 0 && (
              <SummaryItem label="Facteurs aggravants" value={summary.aggravatingFactors.join(', ')} />
            )}
            {summary.relievingFactors && summary.relievingFactors.length > 0 && (
              <SummaryItem label="Facteurs calmants" value={summary.relievingFactors.join(', ')} />
            )}
            {summary.alertSigns && summary.alertSigns.length > 0 && (
              <div className="p-2.5 bg-destructive/10 rounded-lg border border-destructive/20">
                <div className="flex items-center gap-2 text-destructive font-medium mb-1 text-sm">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Signes d&apos;alerte
                </div>
                <p className="text-destructive/80 text-sm">{summary.alertSigns.join(', ')}</p>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function SummaryItem({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        <span className="text-xs uppercase tracking-wide font-medium">{label}</span>
      </div>
      <p className="font-medium text-[14px]">{value}</p>
    </div>
  );
}

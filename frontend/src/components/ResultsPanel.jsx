import { marked } from 'marked'
import { Clock, Cpu, Database } from 'lucide-react'

// Configure marked for clean output
marked.setOptions({ breaks: true, gfm: true })

const SEV_LABELS = { 1: 'Critique', 2: 'Grave', 3: 'Modérée', 4: 'Légère', 5: 'Bénigne' }
const SEV_COLORS = {
  1: ['#f87171', 'rgba(248,113,113,0.15)'],
  2: ['#fb923c', 'rgba(251,146,60,0.15)'],
  3: ['#facc15', 'rgba(250,204,21,0.15)'],
  4: ['#4ade80', 'rgba(74,222,128,0.15)'],
  5: ['#34d399', 'rgba(52,211,153,0.15)'],
}

function SkeletonBlock({ h = 'h-4', w = 'w-full' }) {
  return <div className={`skeleton ${h} ${w} mb-2`} />
}

function PathologyCard({ doc, rank }) {
  const sim = doc.similarity ?? 0
  const conf = sim >= 0.65 ? 'Élevée' : sim >= 0.45 ? 'Modérée' : 'Faible'
  const confColor = sim >= 0.65 ? '#4ade80' : sim >= 0.45 ? '#facc15' : '#f87171'

  // Extract ICD10 from text if available
  const icd10Match = doc.text?.match(/CIM-10\s*:\s*([A-Z]\d[\dA-Z.]*)/i)
  const icd10 = icd10Match ? icd10Match[1] : '—'

  // Extract pathology name
  const name = doc.pathology || 'Pathologie inconnue'

  // Severity from text
  const sevMatch = doc.text?.match(/Sévérité\s*:\s*(\w+)/i)
  const sevLabel = sevMatch ? sevMatch[1] : null

  return (
    <div className="result-card glass-light rounded-xl p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0"
            style={{ background: `${confColor}25`, color: confColor, border: `1px solid ${confColor}40` }}>
            {rank}
          </span>
          <span className="text-sm font-semibold text-slate-100">{name}</span>
        </div>
        {icd10 !== '—' && (
          <span className="text-[10px] font-mono text-slate-500 bg-slate-800/60 px-1.5 py-0.5 rounded shrink-0">
            {icd10}
          </span>
        )}
      </div>

      {/* Confidence bar */}
      <div>
        <div className="flex justify-between text-[10px] mb-1">
          <span className="text-slate-500">Similarité sémantique</span>
          <span style={{ color: confColor }} className="font-semibold">{conf} · {(sim * 100).toFixed(0)}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-800/80 overflow-hidden">
          <div className="conf-bar-fill h-full rounded-full"
            style={{ width: `${sim * 100}%`, background: `linear-gradient(90deg, ${confColor}80, ${confColor})` }} />
        </div>
      </div>

      {sevLabel && (
        <span className="inline-block text-[10px] px-2 py-0.5 rounded-full border font-medium"
          style={{ color: confColor, background: `${confColor}15`, borderColor: `${confColor}30` }}>
          {sevLabel}
        </span>
      )}
    </div>
  )
}

export default function ResultsPanel({ results, loading }) {
  if (loading && !results) {
    return (
      <div className="space-y-3">
        <div className="glass rounded-2xl p-4 space-y-3">
          <SkeletonBlock h="h-3" w="w-32" />
          <SkeletonBlock h="h-16" />
          <SkeletonBlock h="h-4" />
          <SkeletonBlock h="h-4" w="w-3/4" />
          <SkeletonBlock h="h-4" w="w-1/2" />
        </div>
        {[1,2,3].map(i => (
          <div key={i} className="glass-light rounded-xl p-3 space-y-2">
            <SkeletonBlock h="h-4" w="w-2/3" />
            <SkeletonBlock h="h-2" />
          </div>
        ))}
      </div>
    )
  }
  if (!results) return null

  const { pathologies_retrieved = [], llm_response, performance, retrieval_stats } = results
  const hasLLM = llm_response && !llm_response.startsWith('ANTHROPIC_API_KEY')

  return (
    <div className="space-y-3 animate-fade-in">

      {/* Stats bar */}
      <div className="flex items-center gap-3 text-[11px] text-slate-500 px-1">
        <span className="flex items-center gap-1">
          <Clock size={11} /> {performance?.total_seconds}s
        </span>
        <span className="flex items-center gap-1">
          <Database size={11} /> {retrieval_stats?.pathologies_found} pathologies
        </span>
        <span className="flex items-center gap-1">
          <Cpu size={11} /> {retrieval_stats?.patients_found} cas similaires
        </span>
      </div>

      {/* LLM Analysis */}
      {hasLLM ? (
        <div className="glass rounded-2xl p-4">
          <p className="text-[10px] font-semibold text-blue-400/80 uppercase tracking-wider mb-3">
            Analyse IA — Claude
          </p>
          <div className="llm-content"
            dangerouslySetInnerHTML={{ __html: marked.parse(llm_response) }} />
        </div>
      ) : (
        <div className="glass rounded-2xl p-4">
          <p className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider mb-2">
            ⚠ Analyse LLM indisponible
          </p>
          <p className="text-slate-400 text-xs">
            Ajoutez <code className="text-blue-300 bg-blue-500/10 px-1 rounded">ANTHROPIC_API_KEY</code> dans{' '}
            <code className="text-slate-300 bg-slate-800/60 px-1 rounded">datalake_pipeline/.env</code> pour activer Claude.
          </p>
          <p className="text-slate-500 text-xs mt-2">
            Les {pathologies_retrieved.length} pathologies ci-dessous sont issues du retrieval pgvector.
          </p>
        </div>
      )}

      {/* Pathology cards */}
      {pathologies_retrieved.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider px-1">
            Pathologies similaires
          </p>
          {pathologies_retrieved.map((doc, i) => (
            <PathologyCard key={doc.id} doc={doc} rank={i + 1} />
          ))}
        </div>
      )}

      {/* Disclaimer */}
      <div className="glass-light rounded-xl p-3">
        <p className="text-[10px] text-slate-600 leading-relaxed">
          ⚠ Outil d'aide à la décision uniquement. Ne remplace pas l'évaluation d'un professionnel de santé qualifié. Tout diagnostic doit être posé par un médecin.
        </p>
      </div>

    </div>
  )
}

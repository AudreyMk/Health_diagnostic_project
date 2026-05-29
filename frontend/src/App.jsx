import { useState, useCallback } from 'react'
import { Activity, Stethoscope } from 'lucide-react'
import SymptomForm from './components/SymptomForm'
import ResultsPanel from './components/ResultsPanel'
import HospitalMap from './components/HospitalMap'

export default function App() {
  const [location, setLocation] = useState(null)   // { lat, lng }
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = useCallback(async (formData) => {
    setLoading(true)
    setError(null)

    const body = {
      symptoms: formData.symptoms,
      top_k: 8,
      min_similarity: 0.2,
      top_k_centers: 8,
      max_distance_km: formData.maxDistanceKm ?? 20,
    }
    if (formData.age) body.age = Number(formData.age)
    if (formData.sex) body.sex = formData.sex
    if (location) {
      body.latitude = location.lat
      body.longitude = location.lng
    }

    try {
      const res = await fetch('/api/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Erreur ${res.status}`)
      }
      const data = await res.json()
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [location])

  return (
    <div className="app-bg flex flex-col h-screen overflow-hidden">

      {/* ── Header ─────────────────────────────────────── */}
      <header className="flex items-center gap-3 px-6 py-3 shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="flex items-center justify-center w-9 h-9 rounded-xl"
          style={{ background: 'linear-gradient(135deg,#2563eb,#0891b2)' }}>
          <Stethoscope size={18} className="text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold gradient-text leading-none">MedRAG</h1>
          <p className="text-xs text-slate-500 leading-none mt-0.5">Aide à la décision clinique — M2 Data Science</p>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <Activity size={13} className="text-emerald-400" />
            DDXPlus FR · 49 pathologies · 43 981 cas
          </span>
        </div>
      </header>

      {/* ── Main split layout ───────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left panel — form + results */}
        <aside className="w-[420px] shrink-0 flex flex-col overflow-hidden"
          style={{ borderRight: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="scroll-area flex-1 p-4 space-y-4">
            <SymptomForm
              onSubmit={handleSubmit}
              loading={loading}
              location={location}
              onLocationChange={setLocation}
            />

            {error && (
              <div className="glass rounded-xl p-4 border border-red-500/30 animate-fade-in">
                <p className="text-red-400 text-sm font-medium">⚠ Erreur</p>
                <p className="text-red-300/80 text-xs mt-1">{error}</p>
              </div>
            )}

            {(loading || results) && (
              <ResultsPanel results={results} loading={loading} />
            )}
          </div>
        </aside>

        {/* Right panel — map */}
        <main className="flex-1 relative">
          <HospitalMap
            location={location}
            onLocationChange={setLocation}
            hospitals={results?.nearby_centers ?? []}
          />
        </main>

      </div>
    </div>
  )
}

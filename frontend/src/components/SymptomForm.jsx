import { useState } from 'react'
import { Search, MapPin, Loader2, User, Navigation } from 'lucide-react'

export default function SymptomForm({ onSubmit, loading, location, onLocationChange }) {
  const [symptoms, setSymptoms] = useState('')
  const [age, setAge] = useState('')
  const [sex, setSex] = useState('')
  const [gpsLoading, setGpsLoading] = useState(false)
  const [maxDistanceKm, setMaxDistanceKm] = useState(20)

  const handleGPS = () => {
    if (!navigator.geolocation) return
    setGpsLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        onLocationChange({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setGpsLoading(false)
      },
      () => setGpsLoading(false),
      { timeout: 8000 }
    )
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!symptoms.trim()) return
    onSubmit({ symptoms, age, sex, maxDistanceKm })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">

      {/* Symptoms */}
      <div className="glass rounded-2xl p-4 space-y-2">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <Search size={12} /> Symptômes
        </label>
        <textarea
          value={symptoms}
          onChange={e => setSymptoms(e.target.value)}
          placeholder="Décrivez les symptômes du patient en langage naturel…&#10;Ex : Fièvre à 39°C depuis 3 jours, toux sèche, douleurs thoraciques, fatigue intense."
          rows={5}
          className="w-full bg-transparent text-slate-200 placeholder-slate-600 text-sm resize-none focus:outline-none leading-relaxed"
          required
        />
      </div>

      {/* Patient info */}
      <div className="glass rounded-2xl p-4 space-y-3">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <User size={12} /> Informations patient
        </label>
        <div className="flex gap-3">
          {/* Age */}
          <div className="flex-1">
            <label className="text-xs text-slate-500 mb-1 block">Âge</label>
            <input
              type="number"
              value={age}
              onChange={e => setAge(e.target.value)}
              placeholder="—"
              min={0} max={120}
              className="w-full bg-navy-800/60 border border-white/5 rounded-lg px-3 py-2 text-slate-200 text-sm focus:outline-none focus:border-blue-500/40 transition-colors"
            />
          </div>
          {/* Sex */}
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Sexe</label>
            <div className="flex gap-1">
              {[['M', 'H'], ['F', 'F']].map(([val, label]) => (
                <button key={val} type="button"
                  onClick={() => setSex(sex === val ? '' : val)}
                  className={`w-10 h-9 rounded-lg text-sm font-semibold transition-all border ${
                    sex === val
                      ? 'bg-blue-600/30 border-blue-500/60 text-blue-300'
                      : 'bg-navy-800/60 border-white/5 text-slate-400 hover:border-white/15'
                  }`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Location */}
      <div className="glass rounded-2xl p-4 space-y-3">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
          <MapPin size={12} /> Localisation <span className="text-slate-600 font-normal normal-case">(optionnel)</span>
        </label>

        <div className="flex items-center gap-2">
          <button type="button" onClick={handleGPS} disabled={gpsLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all border border-white/8 text-slate-300 hover:border-blue-500/40 hover:text-blue-300 hover:bg-blue-500/10 disabled:opacity-50">
            {gpsLoading
              ? <Loader2 size={13} className="animate-spin" />
              : <Navigation size={13} />}
            Ma position GPS
          </button>

          {location && (
            <span className="text-xs text-emerald-400/80 flex items-center gap-1">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400" />
              {location.lat.toFixed(4)}, {location.lng.toFixed(4)}
            </span>
          )}
        </div>

        {location && (
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-500">
              <span>Rayon de recherche</span>
              <span className="text-slate-300 font-medium">{maxDistanceKm} km</span>
            </div>
            <input type="range" min={2} max={100} step={2}
              value={maxDistanceKm}
              onChange={e => setMaxDistanceKm(Number(e.target.value))}
              className="w-full h-1 rounded-full appearance-none cursor-pointer"
              style={{ accentColor: '#3b82f6' }}
            />
          </div>
        )}

        {!location && (
          <p className="text-xs text-slate-600">
            Cliquez sur la carte ou utilisez le GPS pour trouver les établissements proches.
          </p>
        )}
      </div>

      {/* Submit */}
      <button type="submit" disabled={loading || !symptoms.trim()}
        className="btn-primary w-full rounded-2xl py-3 text-sm font-semibold text-white flex items-center justify-center gap-2 relative z-10">
        {loading
          ? <><Loader2 size={16} className="animate-spin" /> Analyse en cours…</>
          : <><Search size={16} /> Analyser les symptômes</>}
      </button>
    </form>
  )
}

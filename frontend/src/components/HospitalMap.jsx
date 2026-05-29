import { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMapEvents, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { MapPin, Phone, Building2 } from 'lucide-react'

// ── Custom icons ──────────────────────────────────────────

const userIcon = L.divIcon({
  html: `<div class="user-marker-dot"><div class="user-marker-ring"></div></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
  className: '',
})

const CATEGORY_COLORS = {
  '355': '#ef4444', // CHU
  '101': '#ef4444', // CHR
  '146': '#f97316', // CH
  '109': '#a78bfa', // Santé mentale
  '114': '#fb923c', // Hôpital local
  '124': '#facc15', // Chirurgie
  '129': '#facc15', // Médical
  '131': '#ec4899', // Obstétrique
  '141': '#f87171', // Centre anti-cancer
  '344': '#22c55e', // Maison de santé
  '354': '#22c55e',
  '603': '#22c55e',
  '228': '#4ade80', // Centre de santé
  '214': '#4ade80',
  '620': '#60a5fa', // Pharmacie
  '230': '#818cf8', // Labo
}

function getHospitalColor(code) {
  return CATEGORY_COLORS[code] || '#94a3b8'
}

function makeHospitalIcon(code) {
  const c = getHospitalColor(code)
  return L.divIcon({
    html: `<div class="hosp-marker" style="background:${c};color:${c};box-shadow:0 0 6px ${c}80"></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
    className: '',
  })
}

// ── Map click handler ─────────────────────────────────────

function ClickHandler({ onLocationChange }) {
  useMapEvents({
    click(e) {
      onLocationChange({ lat: e.latlng.lat, lng: e.latlng.lng })
    },
  })
  return null
}

// ── Fly to location when it changes ──────────────────────

function FlyTo({ location }) {
  const map = useMap()
  useEffect(() => {
    if (location) {
      map.flyTo([location.lat, location.lng], Math.max(map.getZoom(), 13), { duration: 1.2 })
    }
  }, [location, map])
  return null
}

// ── Fit bounds to hospitals ───────────────────────────────

function FitBounds({ hospitals, location }) {
  const map = useMap()
  const fitted = useRef(false)

  useEffect(() => {
    if (!hospitals.length) return
    const points = hospitals
      .filter(h => h.location?.coordinates)
      .map(h => [h.location.coordinates[1], h.location.coordinates[0]])

    if (location) points.push([location.lat, location.lng])
    if (points.length < 2) return

    if (!fitted.current) {
      map.fitBounds(points, { padding: [40, 40], maxZoom: 14 })
      fitted.current = true
    }
  }, [hospitals])

  useEffect(() => { fitted.current = false }, [hospitals])
  return null
}

// ── Hospital popup ────────────────────────────────────────

function HospitalPopup({ h }) {
  const color = getHospitalColor(h.category_code)
  return (
    <div className="space-y-1.5" style={{ minWidth: 220 }}>
      <div className="flex items-start gap-2">
        <span className="w-2 h-2 rounded-full shrink-0 mt-1" style={{ background: color }} />
        <div>
          <p className="text-slate-100 font-semibold text-sm leading-tight">{h.name}</p>
          <p className="text-xs mt-0.5" style={{ color }}>{h.category}</p>
        </div>
      </div>
      {h.address && (
        <div className="flex items-start gap-1.5 text-xs text-slate-400">
          <MapPin size={11} className="shrink-0 mt-0.5 text-slate-500" />
          <span>{h.address}</span>
        </div>
      )}
      {h.phone && h.phone.length > 4 && (
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <Phone size={11} className="text-slate-500" />
          <span>{h.phone}</span>
        </div>
      )}
      {h.department && (
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Building2 size={11} />
          <span>{h.department}</span>
        </div>
      )}
    </div>
  )
}

// ── Legend overlay ────────────────────────────────────────

function Legend() {
  const items = [
    { label: 'CHU / CHR', color: '#ef4444' },
    { label: 'Centre Hospitalier', color: '#f97316' },
    { label: 'Clinique', color: '#facc15' },
    { label: 'Maison de santé', color: '#22c55e' },
    { label: 'Pharmacie / Labo', color: '#60a5fa' },
  ]
  return (
    <div className="absolute bottom-6 left-4 z-[1000] glass rounded-xl p-3 space-y-1.5">
      {items.map(({ label, color }) => (
        <div key={label} className="flex items-center gap-2 text-[11px] text-slate-400">
          <span className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ background: color, boxShadow: `0 0 5px ${color}80` }} />
          {label}
        </div>
      ))}
    </div>
  )
}

// ── Map hint overlay ──────────────────────────────────────

function MapHint({ hasLocation }) {
  if (hasLocation) return null
  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000]
      glass rounded-full px-4 py-2 text-xs text-slate-400 pointer-events-none
      flex items-center gap-2">
      <MapPin size={12} className="text-blue-400" />
      Cliquez sur la carte pour définir votre position
    </div>
  )
}

// ── Main component ────────────────────────────────────────

const FRANCE_CENTER = [46.603354, 1.888334]

export default function HospitalMap({ location, onLocationChange, hospitals = [] }) {
  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={FRANCE_CENTER}
        zoom={6}
        style={{ width: '100%', height: '100%' }}
        zoomControl={true}
      >
        {/* Dark CartoDB tiles */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · © <a href="https://carto.com/attributions">CARTO</a>'
          maxZoom={19}
          subdomains="abcd"
        />

        <ClickHandler onLocationChange={onLocationChange} />
        {location && <FlyTo location={location} />}
        {hospitals.length > 0 && <FitBounds hospitals={hospitals} location={location} />}

        {/* User location marker */}
        {location && (
          <Marker position={[location.lat, location.lng]} icon={userIcon}>
            <Popup closeButton={false}>
              <div className="text-xs text-slate-300 text-center py-1">
                <span className="text-blue-400 font-semibold">📍 Votre position</span><br />
                {location.lat.toFixed(5)}, {location.lng.toFixed(5)}
              </div>
            </Popup>
          </Marker>
        )}

        {/* Hospital markers */}
        {hospitals.map((h, i) => {
          const coords = h.location?.coordinates
          if (!coords) return null
          return (
            <Marker
              key={h.finess_id || i}
              position={[coords[1], coords[0]]}
              icon={makeHospitalIcon(h.category_code)}
            >
              <Popup maxWidth={280} closeButton>
                <HospitalPopup h={h} />
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>

      <MapHint hasLocation={!!location} />
      {hospitals.length > 0 && <Legend />}

      {/* Hospital count badge */}
      {hospitals.length > 0 && (
        <div className="absolute top-4 right-4 z-[1000] glass rounded-full px-3 py-1.5
          text-xs text-slate-300 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          {hospitals.length} établissement{hospitals.length > 1 ? 's' : ''} trouvé{hospitals.length > 1 ? 's' : ''}
        </div>
      )}
    </div>
  )
}

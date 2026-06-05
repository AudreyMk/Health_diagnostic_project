'use client';

/**
 * health-map.tsx — Carte Leaflet des établissements de santé à proximité.
 *
 * Ce composant est TOUJOURS chargé via `dynamic(..., { ssr: false })`.
 * Leaflet nécessite `window` donc il ne peut pas tourner côté serveur.
 *
 * Sources de données :
 *   - Position GPS de l'utilisateur (navigator.geolocation)
 *   - Coordonnées des centres géocodées via Nominatim (OpenStreetMap)
 */

import { useEffect, useRef, useState } from 'react';
import type { ApiCenter } from '@/lib/api';

// ── Légende des couleurs par type d'établissement ─────────────────────────────

function getCenterColor(categoryLabel: string): string {
  const cat = categoryLabel.toLowerCase();
  if (cat.includes('pharmacie')) return '#22c55e';
  if (cat.includes('urgence') || cat.includes('samu') || cat.includes('smur')) return '#ef4444';
  if (
    cat.includes('hopital') ||
    cat.includes('hospitalier') ||
    cat.includes('clinique') ||
    cat.includes('chu') ||
    cat.includes('chr')
  )
    return '#f97316';
  if (cat.includes('cabinet') || cat.includes('médecin') || cat.includes('medecin'))
    return '#8b5cf6';
  if (cat.includes('sant')) return '#0ea5e9'; // maison de santé
  return '#3b82f6';
}

// ── Géocodage Nominatim ───────────────────────────────────────────────────────

async function geocodeAddress(
  address: string
): Promise<{ lat: number; lng: number } | null> {
  try {
    const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(
      address + ', France'
    )}&format=json&countrycodes=fr&limit=1`;
    const res = await fetch(url, {
      headers: { 'User-Agent': 'MedRAG/1.0 (student project, contact: non-commercial)' },
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (Array.isArray(data) && data.length > 0) {
      return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
    }
  } catch {
    /* silencieux */
  }
  return null;
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface HealthMapProps {
  userLat: number;
  userLng: number;
  centers: ApiCenter[];
}

// ── Composant ─────────────────────────────────────────────────────────────────

export default function HealthMap({ userLat, userLng, centers }: HealthMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<ReturnType<typeof import('leaflet')['map']> | null>(null);
  const [geocodedCount, setGeocodedCount] = useState(0);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Import synchrone de Leaflet (sûr ici car ssr: false garantit l'environnement browser)
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const L = require('leaflet') as typeof import('leaflet');

    // Nettoyage si re-rendu
    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }

    // ── Init carte ──────────────────────────────────────────────────────────
    const map = L.map(mapContainerRef.current, {
      center: [userLat, userLng],
      zoom: 14,
      zoomControl: true,
      scrollWheelZoom: false,
      attributionControl: true,
    });
    mapRef.current = map;

    // ── Fond de carte OpenStreetMap ─────────────────────────────────────────
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    // ── Marqueur utilisateur (cercle bleu pulsé) ────────────────────────────
    const userIcon = L.divIcon({
      html: `
        <div style="
          position:relative;
          width:20px;height:20px;
          display:flex;align-items:center;justify-content:center;
        ">
          <div style="
            width:14px;height:14px;
            background:#3b82f6;
            border:3px solid white;
            border-radius:50%;
            box-shadow:0 2px 8px rgba(59,130,246,0.6);
          "></div>
        </div>`,
      className: '',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });

    L.marker([userLat, userLng], { icon: userIcon })
      .addTo(map)
      .bindPopup(
        `<div style="font-size:13px;font-weight:600">📍 Votre position</div>`,
        { closeButton: false }
      );

    // Cercle de rayon indicatif
    L.circle([userLat, userLng], {
      radius: 1500,
      color: '#3b82f6',
      fillColor: '#3b82f6',
      fillOpacity: 0.04,
      weight: 1.5,
      dashArray: '4 4',
    }).addTo(map);

    // ── Géocodage progressif des centres ───────────────────────────────────
    const markersLayer = L.layerGroup().addTo(map);
    let localCount = 0;

    const geocodeCenters = async () => {
      // Limite à 6 centres, délai de 1.1s entre chaque (limite Nominatim : 1 req/s)
      const toProcess = centers.slice(0, 6);

      for (let i = 0; i < toProcess.length; i++) {
        // Délai entre requêtes Nominatim (sauf pour le premier)
        if (i > 0) {
          await new Promise<void>((resolve) => setTimeout(resolve, 1200));
        }

        // Vérifie que la carte est toujours montée
        if (!mapRef.current) break;

        const center = toProcess[i];
        const coords = await geocodeAddress(center.address);

        if (coords && mapRef.current) {
          const color = getCenterColor(center.category_label);

          const icon = L.divIcon({
            html: `
              <div style="
                width:14px;height:14px;
                background:${color};
                border:2.5px solid white;
                border-radius:4px;
                box-shadow:0 2px 5px rgba(0,0,0,0.35);
                transform:rotate(45deg);
              "></div>`,
            className: '',
            iconSize: [14, 14],
            iconAnchor: [7, 7],
          });

          L.marker([coords.lat, coords.lng], { icon })
            .addTo(markersLayer)
            .bindPopup(`
              <div style="font-size:12px;max-width:220px;line-height:1.4">
                <strong style="font-size:13px">${center.name}</strong><br/>
                <span style="color:#6b7280;font-size:11px">${center.category_label}</span><br/>
                <span>${center.address}</span>
                ${center.phone ? `<br/><span>📞 ${center.phone}</span>` : ''}
              </div>
            `);

          localCount++;
          setGeocodedCount(localCount);
        }
      }
    };

    geocodeCenters();

    // ── Cleanup ──────────────────────────────────────────────────────────────
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userLat, userLng, centers.length]);

  return (
    <div className="relative">
      <div
        ref={mapContainerRef}
        style={{ height: '280px', width: '100%', borderRadius: '10px', overflow: 'hidden' }}
      />
      {/* Indicateur de géocodage */}
      {geocodedCount === 0 && centers.length > 0 && (
        <div className="absolute bottom-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded-md backdrop-blur-sm">
          Localisation des centres…
        </div>
      )}
      {geocodedCount > 0 && (
        <div className="absolute bottom-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded-md backdrop-blur-sm">
          {geocodedCount} centre{geocodedCount > 1 ? 's' : ''} localisé{geocodedCount > 1 ? 's' : ''}
        </div>
      )}
      {/* Légende */}
      <div className="absolute top-2 right-2 bg-white/90 dark:bg-card/90 text-[11px] px-2 py-1.5 rounded-lg shadow-sm space-y-1 backdrop-blur-sm">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#3b82f6] border border-white/80" />
          <span>Votre position</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-[#22c55e] border border-white/80 rotate-45" />
          <span>Pharmacie</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-[#f97316] border border-white/80 rotate-45" />
          <span>Hôpital</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-[#8b5cf6] border border-white/80 rotate-45" />
          <span>Cabinet médical</span>
        </div>
      </div>
    </div>
  );
}

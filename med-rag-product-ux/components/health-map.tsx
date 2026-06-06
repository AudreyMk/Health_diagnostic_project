'use client';

/**
 * health-map.tsx â€” Carte Leaflet des Ã©tablissements de santÃ© Ã  proximitÃ©.
 *
 * Ce composant est TOUJOURS chargÃ© via `dynamic(..., { ssr: false })`.
 * Leaflet nÃ©cessite `window` donc il ne peut pas tourner cÃ´tÃ© serveur.
 *
 * Sources de donnÃ©es :
 *   - Position GPS de l'utilisateur (navigator.geolocation ou profil patient)
 *   - CoordonnÃ©es des centres : directement depuis le backend (FINESS gÃ©olocalisÃ©)
 */

import { useEffect, useRef } from 'react';
import type { ApiCenter } from '@/lib/api';

// â”€â”€ LÃ©gende des couleurs par type d'Ã©tablissement â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
  if (cat.includes('cabinet') || cat.includes('mÃ©decin') || cat.includes('medecin'))
    return '#8b5cf6';
  if (cat.includes('sant')) return '#0ea5e9'; // maison de santÃ©
  return '#3b82f6';
}

// Distance Haversine entre deux points GPS (en km).
function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface HealthMapProps {
  userLat: number;
  userLng: number;
  centers: ApiCenter[];
}

// â”€â”€ Composant â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export default function HealthMap({ userLat, userLng, centers }: HealthMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<ReturnType<typeof import('leaflet')['map']> | null>(null);

  // Filtre les centres ayant des coordonnÃ©es valides (le backend FINESS les fournit ;
  // on garde un garde-fou au cas oÃ¹).
  const geoCenters = centers.filter(
    (c): c is ApiCenter & { lat: number; lon: number } =>
      c.lat != null && c.lon != null
  );

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Import synchrone de Leaflet (sÃ»r ici car ssr: false garantit l'environnement browser)
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const L = require('leaflet') as typeof import('leaflet');

    // Nettoyage si re-rendu
    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }

    // â”€â”€ Init carte â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    const map = L.map(mapContainerRef.current, {
      center: [userLat, userLng],
      zoom: 13,
      zoomControl: true,
      scrollWheelZoom: false,
      attributionControl: true,
    });
    mapRef.current = map;

    // â”€â”€ Fond de carte OpenStreetMap â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: 'Â© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    // â”€â”€ Marqueur utilisateur (cercle bleu) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
        `<div style="font-size:13px;font-weight:600">ðŸ“ Votre position</div>`,
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

    // â”€â”€ Markers des centres FINESS (coords directes du backend) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    const markersLayer = L.layerGroup().addTo(map);
    const bounds = L.latLngBounds([[userLat, userLng]]);

    geoCenters.forEach((center) => {
      const color = getCenterColor(center.category_label);
      const distanceKm = haversineKm(userLat, userLng, center.lat, center.lon);

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

      L.marker([center.lat, center.lon], { icon })
        .addTo(markersLayer)
        .bindPopup(`
          <div style="font-size:12px;max-width:240px;line-height:1.4">
            <strong style="font-size:13px">${center.name}</strong><br/>
            <span style="color:#6b7280;font-size:11px">${center.category_label}</span><br/>
            <span>${center.address}</span>
            ${center.phone ? `<br/><span>ðŸ“ž ${center.phone}</span>` : ''}
            <br/><span style="color:#6b7280;font-size:11px">â‰ˆ ${distanceKm.toFixed(1)} km</span>
          </div>
        `);

      bounds.extend([center.lat, center.lon]);
    });

    // Ajuste le zoom pour englober tous les markers (avec une marge)
    if (geoCenters.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }

    // â”€â”€ Cleanup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userLat, userLng, geoCenters.length]);

  return (
    <div className="relative">
      <div
        ref={mapContainerRef}
        style={{ height: '280px', width: '100%', borderRadius: '10px', overflow: 'hidden' }}
      />
      {/* Compteur d'Ã©tablissements affichÃ©s */}
      {geoCenters.length > 0 && (
        <div className="absolute bottom-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded-md backdrop-blur-sm">
          {geoCenters.length} Ã©tablissement{geoCenters.length > 1 ? 's' : ''} Ã  proximitÃ©
        </div>
      )}
      {/* LÃ©gende */}
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
          <span>HÃ´pital</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-[#8b5cf6] border border-white/80 rotate-45" />
          <span>Cabinet mÃ©dical</span>
        </div>
      </div>
    </div>
  );
}


'use client';

/**
 * health-map.tsx — Carte Leaflet des etablissements de sante a proximite.
 *
 * Ce composant est TOUJOURS charge via `dynamic(..., { ssr: false })`.
 * Leaflet necessite `window` donc il ne peut pas tourner cote serveur.
 *
 * Sources :
 *   - Position GPS de l'utilisateur (navigator.geolocation ou profil patient)
 *   - Coordonnees des centres directement depuis le backend (FINESS geolocalise)
 */

import { useEffect, useRef } from 'react';
import type { ApiCenter } from '@/lib/api';
import { haversineKm, formatDistance } from '@/lib/geo';

// Couleurs par type d'etablissement
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
  if (cat.includes('cabinet') || cat.includes('medecin') || cat.includes('m\u00e9decin'))
    return '#8b5cf6';
  if (cat.includes('sant')) return '#0ea5e9';
  return '#3b82f6';
}

interface HealthMapProps {
  userLat: number;
  userLng: number;
  centers: ApiCenter[];
}

export default function HealthMap({ userLat, userLng, centers }: HealthMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<ReturnType<typeof import('leaflet')['map']> | null>(null);

  // Filtre les centres ayant des coordonnees valides
  const geoCenters = centers.filter(
    (c): c is ApiCenter & { lat: number; lon: number } =>
      c.lat != null && c.lon != null
  );

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const L = require('leaflet') as typeof import('leaflet');

    // Nettoyage si re-rendu
    if (mapRef.current) {
      mapRef.current.remove();
      mapRef.current = null;
    }

    const map = L.map(mapContainerRef.current, {
      center: [userLat, userLng],
      zoom: 13,
      zoomControl: true,
      scrollWheelZoom: false,
      attributionControl: true,
    });
    mapRef.current = map;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '\u00a9 <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    // Marqueur utilisateur (cercle bleu)
    const userIcon = L.divIcon({
      html: `
        <div style="position:relative;width:20px;height:20px;display:flex;align-items:center;justify-content:center;">
          <div style="width:14px;height:14px;background:#3b82f6;border:3px solid white;border-radius:50%;box-shadow:0 2px 8px rgba(59,130,246,0.6);"></div>
        </div>`,
      className: '',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });

    L.marker([userLat, userLng], { icon: userIcon })
      .addTo(map)
      .bindPopup(
        `<div style="font-size:13px;font-weight:600;font-family:system-ui,sans-serif">Votre position</div>`,
        { closeButton: false }
      );

    // Cercle de rayon indicatif (1.5 km)
    L.circle([userLat, userLng], {
      radius: 1500,
      color: '#3b82f6',
      fillColor: '#3b82f6',
      fillOpacity: 0.04,
      weight: 1.5,
      dashArray: '4 4',
    }).addTo(map);

    // Markers des centres FINESS
    const markersLayer = L.layerGroup().addTo(map);
    const bounds = L.latLngBounds([[userLat, userLng]]);

    geoCenters.forEach((center) => {
      const color = getCenterColor(center.category_label);
      const distKm = haversineKm(userLat, userLng, center.lat, center.lon);
      const distLabel = formatDistance(distKm);

      const icon = L.divIcon({
        html: `
          <div style="width:14px;height:14px;background:${color};border:2.5px solid white;border-radius:4px;box-shadow:0 2px 5px rgba(0,0,0,0.35);transform:rotate(45deg);"></div>`,
        className: '',
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });

      // Echappement simple pour eviter injection HTML via les champs FINESS
      const esc = (s: string) =>
        s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

      const phoneHtml = center.phone
        ? `<div style="margin-top:4px"><a href="tel:${esc(center.phone.replace(/\s/g, ''))}" style="color:#2563eb;text-decoration:none">Tel. ${esc(center.phone)}</a></div>`
        : '';

      L.marker([center.lat, center.lon], { icon })
        .addTo(markersLayer)
        .bindPopup(`
          <div style="font-size:12px;max-width:260px;line-height:1.45;font-family:system-ui,-apple-system,sans-serif">
            <div style="font-weight:600;font-size:13px;color:#111827;margin-bottom:2px">${esc(center.name)}</div>
            <div style="color:#6b7280;font-size:11px;margin-bottom:4px">${esc(center.category_label)}</div>
            <div style="color:#374151">${esc(center.address)}</div>
            ${phoneHtml}
            <div style="margin-top:6px;padding-top:6px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:11px">
              <span style="display:inline-block;background:${color};color:white;padding:1px 6px;border-radius:10px;font-weight:600">${distLabel}</span>
              <span style="margin-left:6px">a vol d'oiseau</span>
            </div>
          </div>
        `);

      bounds.extend([center.lat, center.lon]);
    });

    if (geoCenters.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }

    // Leaflet ne recalcule pas sa taille si le conteneur a change apres l'init
    // (sidebar redimensionnee, transition CSS, parent en flex...).
    // On force une revalidation au montage puis a chaque resize du conteneur.
    map.invalidateSize();
    const t = setTimeout(() => map.invalidateSize(), 200);

    const ro = new ResizeObserver(() => {
      map.invalidateSize();
    });
    ro.observe(mapContainerRef.current);

    return () => {
      clearTimeout(t);
      ro.disconnect();
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
        style={{ height: '300px', width: '100%', borderRadius: '10px', overflow: 'hidden' }}
      />
      {geoCenters.length > 0 && (
        <div className="absolute bottom-2 left-2 bg-black/55 text-white text-xs px-2 py-1 rounded-md backdrop-blur-sm">
          {geoCenters.length} &eacute;tablissement{geoCenters.length > 1 ? 's' : ''} &agrave; proximit&eacute;
        </div>
      )}
      <div className="absolute top-2 right-2 bg-white/90 dark:bg-card/90 text-[11px] px-2 py-1.5 rounded-lg shadow-sm space-y-1 backdrop-blur-sm">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#3b82f6] border border-white/80" />
          <span>Vous</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-[#22c55e] border border-white/80 rotate-45" />
          <span>Pharmacie</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-[#f97316] border border-white/80 rotate-45" />
          <span>H&ocirc;pital</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-[#8b5cf6] border border-white/80 rotate-45" />
          <span>Cabinet m&eacute;dical</span>
        </div>
      </div>
    </div>
  );
}

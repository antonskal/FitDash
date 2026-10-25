import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import type { Telemetry } from '@/api/types';
import { C, METRIC_GRADIENTS, gradient } from '@/lib/colors';
import { num, pace } from '@/lib/format';

export type MapMetric = 'hr' | 'pace' | 'elevation' | 'cadence' | 'power';

const METRIC_OPTS: { id: MapMetric; label: string }[] = [
  { id: 'hr', label: 'Heart Rate' },
  { id: 'pace', label: 'Pace' },
  { id: 'elevation', label: 'Elevation' },
  { id: 'cadence', label: 'Cadence' },
  { id: 'power', label: 'Power' },
];

interface Props {
  telemetry: Telemetry;
  hoverElapsed: number | null;
  onHoverElapsed: (s: number | null) => void;
}

function metricSeries(t: Telemetry, m: MapMetric): (number | null)[] {
  if (m === 'hr') return t.hr;
  if (m === 'pace') return t.speedMps;
  if (m === 'elevation') return t.altitudeM;
  if (m === 'cadence') return t.cadence;
  return t.power;
}

function formatMetric(m: MapMetric, v: number | null): string {
  if (v == null) return '—';
  if (m === 'hr') return `${Math.round(v)} bpm`;
  if (m === 'pace') return pace(v);
  if (m === 'elevation') return `${num(v, 0)} m`;
  if (m === 'cadence') return `${num(v, 0)}`;
  return `${num(v, 0)} W`;
}

export default function GpsMap({ telemetry, hoverElapsed, onHoverElapsed }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const markerRef = useRef<L.CircleMarker | null>(null);
  const [metric, setMetric] = useState<MapMetric>('hr');

  const coords = useMemo(() => {
    const out: { lat: number; lon: number; elapsed: number; idx: number }[] = [];
    for (let i = 0; i < telemetry.lat.length; i++) {
      const lat = telemetry.lat[i];
      const lon = telemetry.lon[i];
      if (lat == null || lon == null || Math.abs(lat) < 0.01) continue;
      out.push({ lat, lon, elapsed: telemetry.elapsedS[i], idx: i });
    }
    return out;
  }, [telemetry]);

  const available = useMemo(
    () =>
      METRIC_OPTS.filter((o) => {
        const s = metricSeries(telemetry, o.id);
        return s.some((v) => v != null && (o.id !== 'pace' || (v ?? 0) > 0));
      }),
    [telemetry],
  );

  useEffect(() => {
    if (available.length && !available.some((a) => a.id === metric)) setMetric(available[0].id);
  }, [available, metric]);

  const values = useMemo(() => {
    const raw = metricSeries(telemetry, metric);
    return coords.map((c) => raw[c.idx]);
  }, [telemetry, metric, coords]);

  const range = useMemo(() => {
    const nums = values.filter((v): v is number => v != null && (metric !== 'pace' || v > 0));
    if (!nums.length) return { min: 0, max: 1 };
    return { min: Math.min(...nums), max: Math.max(...nums) };
  }, [values, metric]);

  useEffect(() => {
    if (!host.current || mapRef.current) return;
    const map = L.map(host.current, { zoomControl: true, attributionControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 19,
      className: 'map-tiles-dark',
    }).addTo(map);
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      markerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer || coords.length < 2) return;
    layer.clearLayers();
    const stops = METRIC_GRADIENTS[metric === 'pace' ? 'pace' : metric === 'hr' ? 'hr' : metric === 'elevation' ? 'elevation' : metric === 'cadence' ? 'cadence' : 'power'];
    const span = range.max - range.min || 1;
    const buckets = 12;
    let bucket = -1;
    let run: L.LatLngExpression[] = [];
    const flush = (b: number) => {
      if (run.length < 2) {
        run = [];
        return;
      }
      const t = (b + 0.5) / buckets;
      L.polyline(run, { color: gradient(stops, t), weight: 4, opacity: 0.95, renderer: L.canvas() }).addTo(layer);
      run = [];
    };
    for (let i = 0; i < coords.length; i++) {
      const v = values[i];
      const t = v == null ? 0 : (v - range.min) / span;
      const b = Math.min(buckets - 1, Math.max(0, Math.floor(t * buckets)));
      const ll: L.LatLngExpression = [coords[i].lat, coords[i].lon];
      if (b !== bucket) {
        if (run.length) run.push(ll);
        flush(bucket);
        bucket = b;
        run = [ll];
      } else {
        run.push(ll);
      }
    }
    flush(bucket);

    const bounds = L.latLngBounds(coords.map((c) => [c.lat, c.lon] as L.LatLngTuple));
    map.fitBounds(bounds, { padding: [16, 16] });

    const hit = L.polyline(
      coords.map((c) => [c.lat, c.lon] as L.LatLngTuple),
      { weight: 18, opacity: 0, renderer: L.canvas() },
    ).addTo(layer);
    hit.on('mousemove', (e: L.LeafletMouseEvent) => {
      let best = 0;
      let bestD = Infinity;
      for (let i = 0; i < coords.length; i++) {
        const d = map.distance(e.latlng, L.latLng(coords[i].lat, coords[i].lon));
        if (d < bestD) {
          bestD = d;
          best = i;
        }
      }
      onHoverElapsed(coords[best].elapsed);
    });
    hit.on('mouseout', () => onHoverElapsed(null));
  }, [coords, values, range, metric, onHoverElapsed]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !coords.length) return;
    let idx = 0;
    if (hoverElapsed != null) {
      let best = Infinity;
      for (let i = 0; i < coords.length; i++) {
        const d = Math.abs(coords[i].elapsed - hoverElapsed);
        if (d < best) {
          best = d;
          idx = i;
        }
      }
    }
    const c = coords[idx];
    if (!markerRef.current) {
      markerRef.current = L.circleMarker([c.lat, c.lon], {
        radius: 6,
        color: '#fff',
        weight: 2,
        fillColor: C.cyan,
        fillOpacity: 1,
      }).addTo(map);
    } else {
      markerRef.current.setLatLng([c.lat, c.lon]);
    }
  }, [hoverElapsed, coords]);

  if (coords.length < 2) {
    return <div className="h-full min-h-[240px] flex items-center justify-center text-xs text-ink-faint">No GPS track for this activity</div>;
  }

  return (
    <div className="relative h-full min-h-[280px]">
      <div ref={host} className="absolute inset-0 rounded-sm overflow-hidden" />
      <div className="absolute top-2 left-2 z-[400] flex flex-wrap gap-1">
        {available.map((o) => (
          <button key={o.id} className={`pill bg-carbon/80 ${metric === o.id ? 'pill-active' : ''}`} onClick={() => setMetric(o.id)}>
            {o.label}
          </button>
        ))}
      </div>
      {hoverElapsed != null && (
        <div className="absolute bottom-2 left-2 z-[400] panel px-2 py-1 text-[11px] num">
          {formatMetric(metric, values[nearest(coords, hoverElapsed)] ?? null)}
        </div>
      )}
    </div>
  );
}

function nearest(coords: { elapsed: number }[], elapsed: number): number {
  let idx = 0;
  let best = Infinity;
  for (let i = 0; i < coords.length; i++) {
    const d = Math.abs(coords[i].elapsed - elapsed);
    if (d < best) {
      best = d;
      idx = i;
    }
  }
  return idx;
}

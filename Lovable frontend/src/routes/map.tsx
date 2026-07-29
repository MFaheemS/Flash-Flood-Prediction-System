import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { ChevronRight, X } from "lucide-react";
import { api, HORIZONS, type Horizon, type RiskLocation } from "@/lib/api";
import { useCurrentWeather, useGeolocation } from "@/lib/useGeo";
import { WeatherBackground } from "@/components/WeatherBackground";
import { Nav } from "@/components/Nav";
import { HorizonTabs } from "@/components/HorizonTabs";
import { RiskBadge } from "@/components/RiskBadge";
import { riskBand, riskColorHex, riskLabel, pct } from "@/lib/risk";

export const Route = createFileRoute("/map")({
  head: () => ({
    meta: [
      { title: "Risk Map — FloodWatch" },
      {
        name: "description",
        content:
          "Interactive map of flash-flood risk across Pakistan, by district and forecast horizon.",
      },
      { property: "og:title", content: "Risk Map — FloodWatch" },
      { property: "og:description", content: "Interactive district-level flood risk map." },
    ],
  }),
  component: MapPage,
});

function MapPage() {
  const [horizon, setHorizon] = useState<Horizon>("day");
  const [selected, setSelected] = useState<RiskLocation | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const coords = useGeolocation();
  const weather = useCurrentWeather(coords?.lat, coords?.lon);

  const risk = useQuery({
    queryKey: ["risk", horizon],
    queryFn: () => api.risk(horizon),
    staleTime: 5 * 60 * 1000,
    retry: (fail, err) => ((err as { status?: number })?.status === 503 ? fail < 30 : fail < 2),
    retryDelay: 10_000,
  });

  const horizonMeta = HORIZONS.find((h) => h.id === horizon)!;
  const locations = risk.data?.locations ?? [];

  const lastUpdated = useMemo(() => {
    if (!risk.data?.computed_at) return null;
    return formatDistanceToNow(new Date(risk.data.computed_at * 1000), { addSuffix: true });
  }, [risk.data]);

  return (
    <>
      <WeatherBackground weather={weather.data} />
      <Nav />

      <main className="mx-auto max-w-7xl px-4 pt-8 pb-16">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs tracking-wider text-white/60 uppercase">National view</div>
            <h1 className="text-display mt-1 text-3xl font-semibold sm:text-4xl">
              Flash-flood risk map
            </h1>
            {lastUpdated && (
              <p className="mt-1 text-xs text-white/60">Last updated {lastUpdated}</p>
            )}
          </div>
          <HorizonTabs value={horizon} onChange={setHorizon} />
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          {/* MAP */}
          <div className="glass relative h-[520px] overflow-hidden p-0 lg:h-[640px]">
            <MapView
              key={horizon}
              locations={locations}
              horizonKey={horizonMeta.key}
              onSelect={setSelected}
            />
          </div>

          {/* SIDE PANEL */}
          <aside className="glass max-h-[640px] overflow-hidden">
            <div className="flex items-center justify-between border-b border-white/10 p-4">
              <div>
                <div className="text-sm font-semibold">All districts</div>
                <div className="text-xs text-white/60">
                  Ranked by {horizonMeta.label.toLowerCase()}
                </div>
              </div>
              <button
                onClick={() => setPanelOpen((v) => !v)}
                className="rounded-full p-1.5 hover:bg-white/10"
              >
                <ChevronRight
                  className={`h-4 w-4 transition-transform ${panelOpen ? "rotate-90" : ""}`}
                />
              </button>
            </div>
            {panelOpen && (
              <div className="max-h-[560px] overflow-y-auto">
                {risk.isLoading &&
                  Array.from({ length: 10 }).map((_, i) => (
                    <div key={i} className="border-b border-white/5 p-3">
                      <div className="shimmer h-4 w-32 rounded" />
                      <div className="shimmer mt-2 h-3 w-20 rounded" />
                    </div>
                  ))}
                {locations.map((l) => {
                  const v = l[horizonMeta.key] as number;
                  return (
                    <button
                      key={l.name + l.lat}
                      onClick={() => setSelected(l)}
                      className="flex w-full items-center justify-between border-b border-white/5 px-4 py-3 text-left transition hover:bg-white/8"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{l.name}</div>
                        <div className="text-[11px] text-white/60">{l.province ?? "—"}</div>
                      </div>
                      <RiskBadge value={v} size="sm" />
                    </button>
                  );
                })}
              </div>
            )}
          </aside>
        </div>
      </main>

      {selected && <DetailSheet loc={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

/* ------- Leaflet map (client-only) ------- */

function MapView({
  locations,
  horizonKey,
  onSelect,
}: {
  locations: RiskLocation[];
  horizonKey: keyof RiskLocation;
  onSelect: (l: RiskLocation) => void;
}) {
  const [mod, setMod] = useState<typeof import("react-leaflet") | null>(null);

  useEffect(() => {
    let cancelled = false;
    import("react-leaflet").then((m) => {
      if (!cancelled) setMod(m);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!mod) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-sm text-white/60">Loading map…</div>
      </div>
    );
  }

  const { MapContainer, TileLayer, CircleMarker, Popup } = mod;

  return (
    <MapContainer
      center={[30.4, 69.3]}
      zoom={5}
      scrollWheelZoom
      style={{ height: "100%", width: "100%" }}
      attributionControl
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> · &copy; <a href="https://carto.com">CARTO</a>'
      />
      {locations.map((l) => {
        const v = l[horizonKey] as number;
        const band = riskBand(v);
        const color = riskColorHex(band);
        return (
          <CircleMarker
            key={l.name + l.lat}
            center={[l.lat, l.lon]}
            radius={6 + v * 14}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.55, weight: 1.5 }}
            eventHandlers={{ click: () => onSelect(l) }}
          >
            <Popup>
              <div className="min-w-[180px]">
                <div className="text-sm font-semibold">{l.name}</div>
                <div className="text-[11px] opacity-70">{l.province ?? "—"}</div>
                <div className="mt-2 space-y-1 text-xs">
                  {HORIZONS.map((h) => (
                    <div key={h.id} className="flex items-center justify-between gap-3">
                      <span className="opacity-70">{h.label}</span>
                      <span style={{ color: riskColorHex(riskBand(l[h.key] as number)) }}>
                        {riskLabel(riskBand(l[h.key] as number))} · {pct(l[h.key] as number)}
                      </span>
                    </div>
                  ))}
                </div>
                <Link
                  to="/location"
                  search={{ lat: l.lat, lon: l.lon, name: l.name }}
                  className="mt-3 block text-center text-xs font-medium text-blue-300 hover:underline"
                >
                  View details →
                </Link>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}

function DetailSheet({ loc, onClose }: { loc: RiskLocation; onClose: () => void }) {
  return (
    <div
      className="fixed inset-x-0 bottom-0 z-30 px-4 pb-6 lg:hidden"
      onClick={onClose}
    >
      <div
        className="glass-strong mx-auto max-w-lg p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="text-display text-lg font-semibold">{loc.name}</div>
            <div className="text-xs text-white/60">{loc.province ?? "—"}</div>
          </div>
          <button onClick={onClose} className="rounded-full p-1 hover:bg-white/10">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {HORIZONS.map((h) => (
            <div key={h.id} className="rounded-xl bg-white/5 p-3">
              <div className="text-[10px] tracking-wider text-white/60 uppercase">{h.label}</div>
              <div className="mt-1"><RiskBadge value={loc[h.key] as number} size="sm" /></div>
            </div>
          ))}
        </div>
        <Link
          to="/location"
          search={{ lat: loc.lat, lon: loc.lon, name: loc.name }}
          className="mt-4 block rounded-full bg-white py-2 text-center text-sm font-medium text-black"
        >
          View details
        </Link>
      </div>
    </div>
  );
}

import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, useMemo } from "react";
import { Play, Pause, SkipBack, Columns2, Square, Waves } from "lucide-react";
import { Nav } from "@/components/Nav";
import { AppBackdrop } from "@/components/AppBackdrop";

export const Route = createFileRoute("/explore")({
  head: () => ({
    meta: [
      { title: "Explore — FloodWatch" },
      {
        name: "description",
        content:
          "Animated month-by-month map of Pakistan: rainfall, snow, vegetation, deforestation, urbanization and floods, 2000–2021.",
      },
    ],
  }),
  component: ExplorePage,
});

// ---- factor catalogue -----------------------------------------------------
type FactorKey = "rain" | "peak_rain" | "snow" | "veg" | "temp" | "flood";

const FACTORS: {
  key: FactorKey; label: string; animated: boolean; unit: string;
  scale: [string, string] | "diverging" | "flood";
}[] = [
  { key: "rain", label: "Rainfall (monthly)", animated: true, unit: "mm", scale: ["#eaf2fb", "#12508f"] },
  { key: "peak_rain", label: "Peak daily rain", animated: true, unit: "mm", scale: ["#fef0e6", "#b23a0e"] },
  { key: "snow", label: "Snow cover (NDSI)", animated: true, unit: "", scale: ["#eef6ff", "#5b8fd6"] },
  { key: "veg", label: "Vegetation (NDVI)", animated: true, unit: "", scale: ["#e7dcc2", "#1a7a35"] },
  { key: "temp", label: "Temperature", animated: true, unit: "°C", scale: ["#3b82c4", "#e5484d"] },
  { key: "flood", label: "Flood occurred", animated: true, unit: "", scale: "flood" },
];

interface Waterways { lines: { t: "river" | "canal"; c: [number, number][] }[] }

interface MapData {
  months: string[];
  factors: Record<string, Record<string, (number | null)[]>>;
  static: Record<string, Record<string, number | null>>;
  ranges: Record<string, [number, number]>;
  geojson: GeoJSON.FeatureCollection;
}

function hex(n: number) { return Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0"); }
function lerp(a: string, b: string, t: number) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return "#" + pa.map((c, i) => hex(c + (pb[i] - c) * t)).join("");
}

function colorFor(fk: FactorKey, value: number | null, ranges: MapData["ranges"]): string {
  const def = FACTORS.find((f) => f.key === fk)!;
  if (value == null || Number.isNaN(value)) return "#2a2f3a"; // no data
  if (def.scale === "flood") return value >= 0.5 ? "#e5484d" : "rgba(255,255,255,0.05)";
  const [min, max] = ranges[fk] ?? [0, 1];
  if (def.scale === "diverging") {
    // deforestation: >0 losing veg (red), <0 greening (green), 0 grey
    const t = Math.max(-1, Math.min(1, value / Math.max(Math.abs(min), Math.abs(max), 1e-6)));
    return t >= 0 ? lerp("#8a8f99", "#e5484d", t) : lerp("#8a8f99", "#2e9e4f", -t);
  }
  const t = Math.max(0, Math.min(1, (value - min) / (max - min || 1)));
  return lerp(def.scale[0], def.scale[1], t);
}

function valueAt(data: MapData, d: string, fk: FactorKey, m: number): number | null {
  const def = FACTORS.find((f) => f.key === fk)!;
  if (def.animated) return data.factors[d]?.[fk]?.[m] ?? null;
  return data.static[d]?.[fk] ?? null;
}

// ---- one Leaflet choropleth panel -----------------------------------------
function MapPanel({
  data, factor, month, province, waterways, showWaterways,
}: {
  data: MapData; factor: FactorKey; month: number; province: string;
  waterways?: Waterways; showWaterways: boolean;
}) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);
  const wwRef = useRef<any>(null);
  const [L, setL] = useState<any>(null);
  const [hover, setHover] = useState<{ name: string; val: number | null } | null>(null);

  useEffect(() => { let c = false; import("leaflet").then((m) => !c && setL(m.default ?? m)); return () => { c = true; }; }, []);

  useEffect(() => {
    if (!L || !elRef.current || mapRef.current) return;
    const map = L.map(elRef.current, { zoomControl: false, attributionControl: false, dragging: true, preferCanvas: true }).setView([30.4, 69.3], 5);
    mapRef.current = map;
    const layer = L.geoJSON(data.geojson as any, {
      style: () => ({ weight: 0.5, color: "#0b0f17", fillOpacity: 0.85 }),
      onEachFeature: (f: any, lyr: any) => {
        lyr.on("mouseover", () => {
          const d = f.properties.d;
          setHover({ name: f.properties.name, val: valueAt(data, d, factorRef.current, monthRef.current) });
          lyr.setStyle({ weight: 1.5, color: "#fff" });
        });
        lyr.on("mouseout", () => { setHover(null); lyr.setStyle({ weight: 0.5, color: "#0b0f17" }); });
      },
    }).addTo(map);
    layerRef.current = layer;
    setTimeout(() => map.invalidateSize(), 60);
  }, [L, data]);

  // keep latest factor/month for hover handler
  const factorRef = useRef(factor); const monthRef = useRef(month);
  factorRef.current = factor; monthRef.current = month;

  // Waterways overlay — persistent rivers/canals (static), drawn as two
  // multi-polylines on a canvas renderer so 13k segments stay fast.
  useEffect(() => {
    if (!L || !mapRef.current || !waterways || wwRef.current) return;
    const renderer = L.canvas({ padding: 0.5 });
    const swap = (line: [number, number][]) => line.map(([x, y]) => [y, x]);
    const rivers = waterways.lines.filter((w) => w.t === "river").map((w) => swap(w.c));
    const canals = waterways.lines.filter((w) => w.t === "canal").map((w) => swap(w.c));
    const group = L.layerGroup([
      L.polyline(canals, { renderer, color: "#3aa0a0", weight: 0.5, opacity: 0.45, interactive: false }),
      L.polyline(rivers, { renderer, color: "#5ab0f0", weight: 1.0, opacity: 0.8, interactive: false }),
    ]);
    wwRef.current = group;
    if (showWaterways) group.addTo(mapRef.current);
  }, [L, waterways]);

  useEffect(() => {
    const g = wwRef.current, map = mapRef.current;
    if (!g || !map) return;
    if (showWaterways) g.addTo(map); else map.removeLayer(g);
  }, [showWaterways]);

  useEffect(() => {
    const layer = layerRef.current; if (!layer) return;
    layer.setStyle((f: any) => {
      const d = f.properties.d;
      const val = valueAt(data, d, factor, month);
      const dim = province !== "all" && f.properties.province !== province;
      return { fillColor: colorFor(factor, val, data.ranges), fillOpacity: dim ? 0.06 : 0.85, weight: 0.5, color: "#0b0f17" };
    });
  }, [factor, month, province, data]);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl">
      <div ref={elRef} className="h-full w-full" style={{ background: "#0b0f17" }} />
      {hover && (
        <div className="glass-strong pointer-events-none absolute top-2 left-2 z-[500] px-3 py-2 text-xs">
          <div className="font-semibold">{hover.name}</div>
          <div className="text-white/70">
            {FACTORS.find((f) => f.key === factor)!.label}:{" "}
            {hover.val == null ? "n/a" : `${hover.val}${FACTORS.find((f) => f.key === factor)!.unit}`}
          </div>
        </div>
      )}
    </div>
  );
}

// ---- page -----------------------------------------------------------------
function ExplorePage() {
  const { data } = useQuery<MapData>({
    queryKey: ["mapdata"],
    queryFn: async () => (await fetch("/pak_map.json")).json(),
    staleTime: Infinity,
  });
  const { data: waterways } = useQuery<Waterways>({
    queryKey: ["waterways"],
    queryFn: async () => (await fetch("/pak_waterways.json")).json(),
    staleTime: Infinity,
  });

  const [factor, setFactor] = useState<FactorKey>("rain");
  const [factor2, setFactor2] = useState<FactorKey>("flood");
  const [month, setMonth] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [province, setProvince] = useState("all");
  const [compare, setCompare] = useState(false);
  const [showWaterways, setShowWaterways] = useState(true);

  const provinces = useMemo(() => {
    if (!data) return [];
    const s = new Set<string>();
    data.geojson.features.forEach((f: any) => f.properties.province && s.add(f.properties.province));
    return [...s].sort();
  }, [data]);

  useEffect(() => {
    if (!playing || !data) return;
    const id = setInterval(() => setMonth((m) => (m + 1) % data.months.length), 700 / speed);
    return () => clearInterval(id);
  }, [playing, speed, data]);

  const def = FACTORS.find((f) => f.key === factor)!;

  if (!data) {
    return (
      <>
        <AppBackdrop /><Nav />
        <main className="mx-auto max-w-6xl px-4 pt-16 text-center text-white/70">Loading map data…</main>
      </>
    );
  }

  const label = data.months[month];

  return (
    <>
      <AppBackdrop />
      <Nav />
      <main className="mx-auto max-w-7xl px-4 pt-6 pb-16">
        <div className="mb-4">
          <div className="text-xs tracking-wider text-white/60 uppercase">Time-lapse</div>
          <h1 className="text-display mt-1 text-3xl font-semibold sm:text-4xl">Explore Pakistan, month by month</h1>
          <p className="mt-1 max-w-2xl text-sm text-white/70">
            Every frame steps one month (2000–2021). Watch rainfall, snow, vegetation, floods and human factors move across the country.
          </p>
        </div>

        {/* Controls */}
        <div className="glass mb-4 flex flex-wrap items-center gap-3 p-3">
          <select value={factor} onChange={(e) => setFactor(e.target.value as FactorKey)}
            className="rounded-lg bg-white/10 px-3 py-1.5 text-sm text-white outline-none">
            {FACTORS.map((f) => <option key={f.key} value={f.key} className="bg-[#141b29]">{f.label}{f.animated ? "" : " (static)"}</option>)}
          </select>
          <select value={province} onChange={(e) => setProvince(e.target.value)}
            className="rounded-lg bg-white/10 px-3 py-1.5 text-sm text-white outline-none">
            <option value="all" className="bg-[#141b29]">All provinces</option>
            {provinces.map((p) => <option key={p} value={p} className="bg-[#141b29]">{p}</option>)}
          </select>
          <button onClick={() => setCompare((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-sm hover:bg-white/20">
            {compare ? <Square className="h-4 w-4" /> : <Columns2 className="h-4 w-4" />}
            {compare ? "Single" : "Compare"}
          </button>
          <button onClick={() => setShowWaterways((v) => !v)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm ${showWaterways ? "bg-[#3b82c4]/30 text-white" : "bg-white/10 hover:bg-white/20"}`}>
            <Waves className="h-4 w-4" /> Rivers
          </button>
          {compare && (
            <select value={factor2} onChange={(e) => setFactor2(e.target.value as FactorKey)}
              className="rounded-lg bg-white/10 px-3 py-1.5 text-sm text-white outline-none">
              {FACTORS.map((f) => <option key={f.key} value={f.key} className="bg-[#141b29]">{f.label}{f.animated ? "" : " (static)"}</option>)}
            </select>
          )}
          <div className="ml-auto flex items-center gap-2 text-xs text-white/60">
            Speed
            {[0.5, 1, 2, 4].map((s) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={`rounded px-2 py-0.5 ${speed === s ? "bg-white/25 text-white" : "hover:bg-white/10"}`}>{s}×</button>
            ))}
          </div>
        </div>

        {/* Maps */}
        <div className={`grid gap-4 ${compare ? "lg:grid-cols-2" : ""}`}>
          <div className="glass h-[440px] p-1 lg:h-[560px]">
            <MapPanel data={data} factor={factor} month={month} province={province} waterways={waterways} showWaterways={showWaterways} />
          </div>
          {compare && (
            <div className="glass h-[440px] p-1 lg:h-[560px]">
              <MapPanel data={data} factor={factor2} month={month} province={province} waterways={waterways} showWaterways={showWaterways} />
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <Legend factor={factor} ranges={data.ranges} />
          {compare && <Legend factor={factor2} ranges={data.ranges} />}
        </div>

        {/* Timeline */}
        <div className="glass mt-4 flex items-center gap-4 p-3">
          <button onClick={() => setMonth(0)} className="rounded-full p-2 hover:bg-white/10" title="Restart">
            <SkipBack className="h-4 w-4" />
          </button>
          <button onClick={() => setPlaying((p) => !p)}
            className="text-display inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-medium text-black">
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {playing ? "Pause" : "Play"}
          </button>
          <div className="text-display w-24 text-lg font-semibold tabular-nums">{label}</div>
          <input type="range" min={0} max={data.months.length - 1} value={month}
            onChange={(e) => setMonth(Number(e.target.value))} className="flex-1 accent-[#3b82c4]" />
          {!def.animated && <span className="text-xs text-white/50">(static factor — same every month)</span>}
        </div>
        <p className="mt-3 text-xs text-white/45">
          Rain/snow/vegetation/temperature from MODIS &amp; CHIRPS satellites; floods from curated records. Blue lines are rivers/canals
          (HOTOSM) shown continuously since they don&apos;t change month-to-month. Grey districts = outside our satellite panel.
        </p>
      </main>
    </>
  );
}

function Legend({ factor, ranges }: { factor: FactorKey; ranges: MapData["ranges"] }) {
  const def = FACTORS.find((f) => f.key === factor)!;
  const [min, max] = ranges[factor] ?? [0, 1];
  const stops = def.scale === "flood"
    ? [{ c: "rgba(255,255,255,0.1)", l: "no flood" }, { c: "#e5484d", l: "flood" }]
    : def.scale === "diverging"
      ? [{ c: "#2e9e4f", l: "greening" }, { c: "#8a8f99", l: "0" }, { c: "#e5484d", l: "deforesting" }]
      : [{ c: def.scale[0], l: `${min}` }, { c: def.scale[1], l: `${max}${def.unit}` }];
  return (
    <div className="glass inline-flex items-center gap-2 px-3 py-1.5 text-[11px] text-white/70">
      <span className="text-white/50">{def.label}</span>
      {stops.map((s, i) => (
        <span key={i} className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-4 rounded" style={{ background: s.c }} /> {s.l}
        </span>
      ))}
    </div>
  );
}

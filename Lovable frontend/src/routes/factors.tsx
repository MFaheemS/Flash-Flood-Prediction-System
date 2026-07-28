import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type FactorItem } from "@/lib/api";
import { formatFactor } from "@/lib/risk";
import { Nav } from "@/components/Nav";

type Dataset = "district_flood" | "satellite_flood" | "cloudburst" | "flood_factors";

const DATASETS: {
  id: Dataset;
  label: string;
  short: string;
  note: string;
}[] = [
  {
    id: "district_flood",
    label: "District satellite model",
    short: "District",
    note: "Satellite features for all 119 Pakistani districts (monthly, 2000–2021), labelled from real curated province flood records disaggregated to the districts that caught the storm. Best-performing model (cross-validated AUC ≈ 0.93). Note: since labels were placed using a rainfall threshold, the rainfall factors' weight is partly by construction — but the top driver is time-of-year (monsoon seasonality), which is learned independently.",
  },
  {
    id: "satellite_flood",
    label: "Province model",
    short: "Province",
    note: "Real monthly flood labels for 6 Pakistani regions (2000–2021) from Google Earth Engine, with satellite precipitation, temperature, snow cover (NDSI) and vegetation (NDVI). Cross-validated AUC ≈ 0.83 — the only model with snow and vegetation, both major flash-flood factors.",
  },
  {
    id: "cloudburst",
    label: "Pakistan model",
    short: "Pakistan",
    note: "Trained on 206 real Pakistan flood events (1988–2025) plus negatives, with 17 weather, terrain, drainage, and soil features.",
  },
  {
    id: "flood_factors",
    label: "Human factors",
    short: "Human",
    note: "Kaggle Flood Prediction Dataset — ~1.1M rows of named human/infrastructure factors. Note: this is a synthetic dataset whose target is essentially the sum of all factors, so every factor scores ~equally (≈5%). Useful as a checklist of factors, not for ranking their real-world importance.",
  },
];

const INC = "#E5484D";
const DEC = "#3B82C4";

export const Route = createFileRoute("/factors")({
  head: () => ({
    meta: [
      { title: "Factor analysis — FloodWatch" },
      {
        name: "description",
        content:
          "SHAP-based factor importance for three flood models: Pakistan-specific, global, and human/infrastructure.",
      },
      { property: "og:title", content: "What drives flood risk — FloodWatch" },
      {
        property: "og:description",
        content: "Compare Pakistan-specific vs global vs human factors driving flood risk.",
      },
    ],
  }),
  component: FactorsPage,
});

function FactorsPage() {
  const [dataset, setDataset] = useState<Dataset>("district_flood");
  const q = useQuery({
    queryKey: ["factors", dataset],
    queryFn: () => api.factors(dataset),
    retry: (fail, err) => ((err as { status?: number })?.status === 503 ? false : fail < 2),
  });

  const active = DATASETS.find((d) => d.id === dataset)!;
  const notReady = (q.error as { status?: number })?.status === 503;

  const data = (q.data?.factors ?? []).map((f) => ({
    ...f,
    label: formatFactor(f.feature),
  }));
  const chartHeight = Math.max(280, data.length * 32);

  return (
    <>
      <div className="app-backdrop" />
      <Nav />

      <main className="mx-auto max-w-6xl px-4 pt-8 pb-24">
        <div className="max-w-3xl">
          <div className="text-xs tracking-widest text-white/60 uppercase">Factor analysis</div>
          <h1 className="text-display mt-1 text-4xl font-semibold sm:text-5xl">
            What drives flood risk
          </h1>
          <p className="mt-3 text-white/75">
            SHAP importance from each trained model. Bars show how strongly a factor moves the
            prediction on average; color shows the direction of that push.
          </p>
        </div>

        {/* Dataset tabs */}
        <div className="glass mt-8 inline-flex flex-wrap gap-1 p-1">
          {DATASETS.map((d) => {
            const active = dataset === d.id;
            return (
              <button
                key={d.id}
                onClick={() => setDataset(d.id)}
                className={`rounded-full px-4 py-2 text-sm transition ${
                  active
                    ? "bg-white text-black shadow-lg"
                    : "text-white/75 hover:bg-white/10 hover:text-white"
                }`}
              >
                {d.label}
              </button>
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-6 flex flex-wrap items-center gap-4 text-xs">
          <LegendChip color={INC} label="Increases risk" />
          <LegendChip color={DEC} label="Decreases risk" />
        </div>

        {/* Chart */}
        <section className="glass mt-4 p-4 sm:p-6">
          {notReady ? (
            <div className="py-12 text-center">
              <div className="text-display text-lg">This model is still being built</div>
              <p className="mt-1 text-sm text-white/70">
                Check back soon — the {active.short} dataset isn't ready yet.
              </p>
            </div>
          ) : q.isLoading ? (
            <div className="space-y-3 py-4">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="shimmer h-6 rounded" style={{ width: `${90 - i * 6}%` }} />
              ))}
            </div>
          ) : q.isError ? (
            <div className="py-8 text-center text-sm text-white/80">
              Couldn't load factors.
              <button
                onClick={() => q.refetch()}
                className="ml-2 rounded-full bg-white/15 px-3 py-1 hover:bg-white/25"
              >
                Retry
              </button>
            </div>
          ) : (
            <div style={{ width: "100%", height: chartHeight }}>
              <ResponsiveContainer>
                <BarChart data={data} layout="vertical" margin={{ left: 20, right: 30 }}>
                  <XAxis
                    type="number"
                    stroke="rgba(255,255,255,0.5)"
                    tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 11 }}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <YAxis
                    dataKey="label"
                    type="category"
                    stroke="rgba(255,255,255,0.5)"
                    tick={{ fill: "rgba(255,255,255,0.85)", fontSize: 12 }}
                    width={180}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.05)" }}
                    content={<GlassTooltip />}
                  />
                  <Bar dataKey="relative_importance_pct" radius={[0, 6, 6, 0]}>
                    {data.map((d, i) => (
                      <Cell
                        key={i}
                        fill={d.direction === "increases risk" ? INC : DEC}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        {/* Context */}
        <div className="glass mt-6 p-6">
          <div className="text-xs tracking-widest text-white/60 uppercase">
            About this dataset
          </div>
          <p className="mt-2 text-sm text-white/85">{active.note}</p>
        </div>

        {/* Comparison callout */}
        <div className="glass mt-6 p-6">
          <div className="text-xs tracking-widest text-white/60 uppercase">Model comparison</div>
          <h3 className="text-display mt-1 text-xl font-semibold">
            Pakistan-specific vs general drivers
          </h3>
          <p className="mt-2 text-sm text-white/80">
            In the Pakistan model, <span className="font-medium text-white">urbanization</span> tends
            to dominate — a small number of features carry most of the weight. The Kaggle human-factors
            model spreads importance roughly evenly across all 20 human/infrastructure variables,
            suggesting no single lever fits everywhere. The global weather+terrain model sits in
            between: useful as a baseline, best interpreted as ranking rather than absolutes.
          </p>
        </div>
      </main>
    </>
  );
}

function LegendChip({ color, label }: { color: string; label: string }) {
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-3 py-1"
      style={{ background: `${color}18`, border: `1px solid ${color}55`, color }}
    >
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      <span className="text-white/85">{label}</span>
    </span>
  );
}

function GlassTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: FactorItem & { label: string } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const color = d.direction === "increases risk" ? INC : DEC;
  return (
    <div className="glass-strong min-w-[220px] p-3 text-xs">
      <div className="text-display text-sm font-semibold">{d.label}</div>
      <div className="mt-1 text-white/70">Rank #{d.rank}</div>
      <div className="mt-2 flex items-center justify-between">
        <span className="text-white/70">Relative importance</span>
        <span className="font-medium" style={{ color }}>
          {d.relative_importance_pct.toFixed(1)}%
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-white/70">Mean |SHAP|</span>
        <span className="font-medium">{d.mean_abs_shap_impact.toFixed(4)}</span>
      </div>
      <div className="mt-2 inline-flex items-center gap-1.5 rounded-full px-2 py-0.5"
        style={{ background: `${color}22`, color }}>
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
        {d.direction}
      </div>
    </div>
  );
}

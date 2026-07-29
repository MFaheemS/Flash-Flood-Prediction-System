import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { ChevronRight, Search, MapPin, Droplets } from "lucide-react";
import { api, HORIZONS, type Horizon } from "@/lib/api";
import { Nav } from "@/components/Nav";
import { AppBackdrop } from "@/components/AppBackdrop";
import { HorizonTabs } from "@/components/HorizonTabs";
import { RiskBadge } from "@/components/RiskBadge";
import { pct } from "@/lib/risk";

export const Route = createFileRoute("/districts")({
  head: () => ({
    meta: [
      { title: "Districts — FloodWatch" },
      {
        name: "description",
        content: "All monitored Pakistani districts ranked by flash-flood risk, with details.",
      },
    ],
  }),
  component: DistrictsPage,
});

function DistrictsPage() {
  const [horizon, setHorizon] = useState<Horizon>("week");
  const [q, setQ] = useState("");

  const risk = useQuery({
    queryKey: ["risk", horizon],
    queryFn: () => api.risk(horizon),
    staleTime: 5 * 60 * 1000,
    retry: (fail, err) => ((err as { status?: number })?.status === 503 ? fail < 30 : fail < 2),
    retryDelay: 10_000,
  });

  const horizonMeta = HORIZONS.find((h) => h.id === horizon)!;
  const updated = risk.data?.computed_at
    ? formatDistanceToNow(new Date(risk.data.computed_at * 1000), { addSuffix: true })
    : null;

  const rows = useMemo(() => {
    const list = risk.data?.locations ?? [];
    const needle = q.trim().toLowerCase();
    return needle
      ? list.filter(
          (l) =>
            l.name.toLowerCase().includes(needle) ||
            (l.province ?? "").toLowerCase().includes(needle),
        )
      : list;
  }, [risk.data, q]);

  return (
    <>
      <AppBackdrop />
      <Nav />

      <main className="mx-auto max-w-5xl px-4 pt-8 pb-24">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs tracking-wider text-white/60 uppercase">All districts</div>
            <h1 className="text-display mt-1 text-3xl font-semibold sm:text-4xl">
              Monitored districts
            </h1>
            <p className="mt-1 text-sm text-white/70">
              {(risk.data?.locations.length ?? 0)} districts ranked by {horizonMeta.label.toLowerCase()} risk
              {updated ? ` · updated ${updated}` : ""}
            </p>
          </div>
          <HorizonTabs value={horizon} onChange={setHorizon} />
        </div>

        {/* Search */}
        <div className="glass mb-4 flex items-center gap-2 px-4 py-2.5">
          <Search className="h-4 w-4 text-white/50" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search district or province…"
            className="w-full bg-transparent text-sm text-white placeholder:text-white/40 focus:outline-none"
          />
        </div>

        {/* States */}
        {risk.isError && (risk.error as { status?: number })?.status === 503 ? (
          <div className="glass p-8 text-center">
            <div className="text-display text-lg">Warming up live risk data…</div>
            <p className="mt-1 text-sm text-white/70">Retrying automatically.</p>
          </div>
        ) : risk.isError ? (
          <div className="glass p-6 text-center">
            <p className="text-sm text-white/80">Couldn&apos;t load districts.</p>
            <button
              onClick={() => risk.refetch()}
              className="mt-3 rounded-full bg-white/15 px-4 py-1.5 text-sm hover:bg-white/25"
            >
              Retry
            </button>
          </div>
        ) : (
          <div className="glass overflow-hidden">
            {risk.isLoading
              ? Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className="border-b border-white/5 px-4 py-4">
                    <div className="shimmer h-4 w-40 rounded" />
                    <div className="shimmer mt-2 h-3 w-24 rounded" />
                  </div>
                ))
              : rows.map((l, i) => {
                  const v = l[horizonMeta.key] as number;
                  return (
                    <Link
                      key={l.name + l.lat}
                      to="/location"
                      search={{ lat: l.lat, lon: l.lon, name: l.name }}
                      className="flex items-center gap-4 border-b border-white/5 px-4 py-3.5 transition hover:bg-white/8"
                    >
                      <div className="w-7 text-sm text-white/40 tabular-nums">{i + 1}</div>
                      <div className="min-w-0 flex-1">
                        <div className="text-display truncate text-base font-medium">{l.name}</div>
                        <div className="flex items-center gap-2 text-[11px] text-white/55">
                          <MapPin className="h-3 w-3" />
                          {l.province ?? "—"}
                          {l.forecast_precip_total_mm != null && (
                            <>
                              <span className="text-white/25">·</span>
                              <Droplets className="h-3 w-3" />
                              {l.forecast_precip_total_mm.toFixed(0)}mm forecast
                            </>
                          )}
                        </div>
                      </div>
                      <div className="hidden text-right sm:block">
                        <div className="text-display text-base font-semibold">{pct(v, 1)}</div>
                      </div>
                      <RiskBadge value={v} size="sm" />
                      <ChevronRight className="h-4 w-4 text-white/30" />
                    </Link>
                  );
                })}
            {!risk.isLoading && rows.length === 0 && (
              <div className="px-4 py-10 text-center text-sm text-white/60">
                No districts match “{q}”.
              </div>
            )}
          </div>
        )}
      </main>
    </>
  );
}

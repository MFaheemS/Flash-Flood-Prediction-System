import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { format } from "date-fns";
import { ArrowLeft, Droplets, Mountain, Sprout, TreePine, History, Clock } from "lucide-react";
import { api, HORIZONS } from "@/lib/api";
import { useCurrentWeather } from "@/lib/useGeo";
import { WeatherBackground } from "@/components/WeatherBackground";
import { Nav } from "@/components/Nav";
import { RiskGauge } from "@/components/RiskGauge";

const searchSchema = z.object({
  lat: z.coerce.number(),
  lon: z.coerce.number(),
  name: z.string().optional(),
});

export const Route = createFileRoute("/location")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "Location risk — FloodWatch" },
      {
        name: "description",
        content:
          "Detailed flash-flood risk breakdown for a location: horizons, contributing factors, and current weather.",
      },
    ],
  }),
  component: LocationPage,
});

function LocationPage() {
  const { lat, lon, name } = Route.useSearch();
  const weather = useCurrentWeather(lat, lon);
  const point = useQuery({
    queryKey: ["point", lat, lon, name],
    queryFn: () => api.riskPoint(lat, lon, name),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <>
      <WeatherBackground
        weather={weather.data}
        floodRisk={
          point.data ? Math.max(point.data.week_risk ?? 0, point.data.month_risk ?? 0) : undefined
        }
      />
      <Nav />

      <main className="mx-auto max-w-6xl px-4 pt-6 pb-24">
        <Link
          to="/map"
          className="inline-flex items-center gap-1.5 text-sm text-white/70 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" /> Back to map
        </Link>

        {/* Hero */}
        <section className="mt-4">
          <div className="text-xs tracking-widest text-white/60 uppercase">Location</div>
          <h1 className="text-display mt-1 text-4xl font-semibold sm:text-5xl">
            {name ?? point.data?.name ?? "Selected location"}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-white/80">
            <span>
              {lat.toFixed(3)}°N, {lon.toFixed(3)}°E
            </span>
            {weather.data && (
              <>
                <span className="h-4 w-px bg-white/20" />
                <span className="text-display text-lg font-semibold">
                  {Math.round(weather.data.temperature)}°
                </span>
                <span className="capitalize">{weather.data.description}</span>
                {weather.data.humidity != null && (
                  <span className="text-white/60">· {weather.data.humidity}% humidity</span>
                )}
                {weather.data.wind_speed != null && (
                  <span className="text-white/60">
                    · {Math.round(weather.data.wind_speed)} km/h wind
                  </span>
                )}
              </>
            )}
          </div>
        </section>

        {/* Gauges */}
        <section className="mt-8">
          <div className="glass p-6 sm:p-8">
            {point.isLoading ? (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="flex flex-col items-center">
                    <div className="shimmer h-4 w-20 rounded" />
                    <div className="shimmer mt-4 h-32 w-32 rounded-full" />
                  </div>
                ))}
              </div>
            ) : point.isError ? (
              <div className="text-center">
                <p className="text-sm text-white/80">Couldn't load risk data.</p>
                <button
                  onClick={() => point.refetch()}
                  className="mt-3 rounded-full bg-white/15 px-4 py-1.5 text-sm hover:bg-white/25"
                >
                  Retry
                </button>
              </div>
            ) : point.data ? (
              <>
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                  {HORIZONS.map((h) => (
                    <RiskGauge
                      key={h.id}
                      label={h.label}
                      value={point.data![h.key] as number}
                    />
                  ))}
                </div>
                {point.data.peak_time && (
                  <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-white/8 px-4 py-2 text-sm text-white/85">
                    <Clock className="h-4 w-4" />
                    Risk peaks around{" "}
                    <span className="text-display font-medium">
                      {format(new Date(point.data.peak_time), "EEE, MMM d · HH:mm")}
                    </span>
                  </div>
                )}
              </>
            ) : null}
          </div>
        </section>

        {/* Factors */}
        {point.data && (
          <section className="mt-8">
            <div className="mb-4">
              <div className="text-xs tracking-wider text-white/60 uppercase">
                Contributing factors
              </div>
              <h2 className="text-display mt-1 text-2xl font-semibold">What drives risk here</h2>
            </div>
            <p className="mb-4 max-w-2xl text-sm text-white/60">
              Risk here comes from the district satellite model — live forecast rainfall
              combined with this district&apos;s historical climate for the season.
            </p>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <FactorCard
                icon={<Droplets className="h-4 w-4" />}
                label="Forecast rain (16-day total)"
                value={fmt(point.data.forecast_precip_total_mm, " mm", 1)}
              />
              <FactorCard
                icon={<Droplets className="h-4 w-4" />}
                label="Forecast peak-day rain"
                value={fmt(point.data.forecast_precip_max_mm, " mm", 1)}
              />
              <FactorCard
                icon={<Mountain className="h-4 w-4" />}
                label="Forecast temperature"
                value={fmt(point.data.forecast_temp_mean_c, "°C", 1)}
              />
              {/* Climatology factors exist only for districts in the satellite
                  panel; hidden for the Gilgit-Baltistan forecast-only fallback. */}
              {point.data.model !== "forecast_fallback" && (
                <>
                  <FactorCard
                    icon={<History className="h-4 w-4" />}
                    label="Last month's rain"
                    value={fmt(point.data.precip_prev_month_mm, " mm", 1)}
                  />
                  <FactorCard
                    icon={<Sprout className="h-4 w-4" />}
                    label="Snow cover (seasonal)"
                    value={fmt(point.data.snow_climatology, "", 2)}
                  />
                  <FactorCard
                    icon={<Sprout className="h-4 w-4" />}
                    label="Vegetation (seasonal)"
                    value={fmt(point.data.veg_climatology, "", 2)}
                  />
                  <FactorCard
                    icon={<TreePine className="h-4 w-4" />}
                    label="Vegetation change (20-yr)"
                    value={
                      point.data.veg_trend == null
                        ? "n/a"
                        : point.data.veg_trend < 0
                          ? `${point.data.veg_trend.toFixed(2)} · losing (deforestation)`
                          : `+${point.data.veg_trend.toFixed(2)} · greening`
                    }
                  />
                </>
              )}
            </div>
            {point.data.model === "forecast_fallback" && (
              <p className="mt-3 text-xs text-white/50">
                This location (Gilgit-Baltistan) isn&apos;t in the satellite panel, so risk here
                uses forecast rainfall only — seasonal snow/vegetation aren&apos;t available.
              </p>
            )}
          </section>
        )}
      </main>
    </>
  );
}

function fmt(v: number | null | undefined, suffix = "", digits = 0) {
  if (v == null || Number.isNaN(v)) return "n/a";
  return `${v.toFixed(digits)}${suffix}`;
}

function FactorCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="glass p-5">
      <div className="flex items-center gap-2 text-xs tracking-wide text-white/60 uppercase">
        <span className="text-white/50">{icon}</span> {label}
      </div>
      <div className="text-display mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

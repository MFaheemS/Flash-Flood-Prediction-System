import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, MapPin, Thermometer, Wind } from "lucide-react";
import { useState } from "react";
import { api, type Horizon } from "@/lib/api";
import { useCurrentWeather, useGeolocation } from "@/lib/useGeo";
import { WeatherBackground } from "@/components/WeatherBackground";
import { Nav } from "@/components/Nav";
import { HorizonTabs } from "@/components/HorizonTabs";
import { RiskBadge } from "@/components/RiskBadge";
import { CountUp } from "@/components/CountUp";
import { HORIZONS } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "FloodWatch — Live flash-flood risk for Pakistan" },
      {
        name: "description",
        content:
          "Cinematic, live view of flash-flood risk across Pakistan. Check your location, explore the map, and understand what drives risk.",
      },
      { property: "og:title", content: "FloodWatch — Live flash-flood risk" },
      {
        property: "og:description",
        content:
          "Weather-reactive dashboard for flash-flood risk across Pakistan.",
      },
    ],
  }),
  component: HomePage,
});

function HomePage() {
  const coords = useGeolocation();
  const weather = useCurrentWeather(coords?.lat, coords?.lon);
  const navigate = useNavigate();
  const [horizon, setHorizon] = useState<Horizon>("day");

  const horizonMeta = HORIZONS.find((h) => h.id === horizon)!;

  const risk = useQuery({
    queryKey: ["risk", horizon],
    queryFn: () => api.risk(horizon),
    staleTime: 5 * 60 * 1000,
    retry: (fail, err) => {
      const status = (err as { status?: number })?.status;
      return status === 503 ? fail < 30 : fail < 2;
    },
    retryDelay: 10_000,
  });

  const top5 = risk.data?.locations.slice(0, 5) ?? [];

  return (
    <>
      <WeatherBackground weather={weather.data} />
      <Nav />

      <main className="mx-auto max-w-6xl px-4 pt-10 pb-24 sm:pt-16">
        {/* HERO */}
        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="text-center"
        >
          <div className="text-display mb-4 text-5xl leading-[1.05] font-semibold tracking-tight sm:text-7xl">
            Flood<span className="text-white/60">Watch</span>
          </div>
          <p className="mx-auto max-w-2xl text-base text-white/75 sm:text-lg">
            Live flash-flood risk for Pakistan — and the science behind it.
          </p>

          {/* Current conditions chip */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass mx-auto mt-8 inline-flex flex-wrap items-center justify-center gap-3 px-5 py-3 text-sm"
          >
            <span className="inline-flex items-center gap-1.5 text-white/85">
              <MapPin className="h-4 w-4 text-white/60" />
              {coords?.label ?? "Locating…"}
            </span>
            {weather.data && (
              <>
                <span className="h-4 w-px bg-white/20" />
                <span className="inline-flex items-center gap-1.5">
                  <Thermometer className="h-4 w-4 text-white/60" />
                  <span className="text-display text-base font-semibold">
                    {Math.round(weather.data.temperature)}°
                  </span>
                </span>
                <span className="h-4 w-px bg-white/20" />
                <span className="text-white/75 capitalize">{weather.data.description}</span>
                {weather.data.wind_speed != null && (
                  <>
                    <span className="h-4 w-px bg-white/20" />
                    <span className="inline-flex items-center gap-1.5 text-white/75">
                      <Wind className="h-4 w-4 text-white/60" />
                      {Math.round(weather.data.wind_speed)} km/h
                    </span>
                  </>
                )}
              </>
            )}
          </motion.div>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={() => {
                if (coords) {
                  void navigate({
                    to: "/location",
                    search: { lat: coords.lat, lon: coords.lon, name: coords.label },
                  });
                }
              }}
              className="text-display group inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 font-medium text-black shadow-2xl transition-transform hover:scale-[1.02]"
            >
              Check my location's flood risk
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </button>
            <Link
              to="/map"
              className="glass inline-flex items-center gap-2 px-6 py-3 text-sm text-white hover:bg-white/15"
            >
              Explore risk map
            </Link>
          </div>
        </motion.section>

        {/* HIGHEST RISK NOW */}
        <section className="mt-24">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="text-xs tracking-wider text-white/60 uppercase">Live rankings</div>
              <h2 className="text-display mt-1 text-3xl font-semibold sm:text-4xl">
                Highest risk right now
              </h2>
              <p className="mt-1 text-sm text-white/70">
                Top 5 monitored districts, ranked by {horizonMeta.label.toLowerCase()} forecast.
              </p>
            </div>
            <HorizonTabs value={horizon} onChange={setHorizon} />
          </div>

          {risk.isError && (risk.error as { status?: number })?.status === 503 ? (
            <div className="glass p-8 text-center">
              <div className="text-display text-lg">Warming up live risk data…</div>
              <p className="mt-1 text-sm text-white/70">
                This can take up to a minute after the backend starts. Retrying automatically.
              </p>
              <div className="mx-auto mt-4 h-1 w-40 overflow-hidden rounded-full bg-white/10">
                <div className="shimmer h-full w-1/2" />
              </div>
            </div>
          ) : risk.isError ? (
            <div className="glass p-6 text-center">
              <p className="text-sm text-white/80">Couldn't reach the risk service.</p>
              <button
                onClick={() => risk.refetch()}
                className="mt-3 rounded-full bg-white/15 px-4 py-1.5 text-sm hover:bg-white/25"
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {(risk.isLoading ? Array.from({ length: 5 }) : top5).map((loc, i) => {
                if (!loc) {
                  return (
                    <div key={i} className="glass h-40 p-5">
                      <div className="shimmer h-4 w-24 rounded" />
                      <div className="shimmer mt-3 h-8 w-20 rounded" />
                      <div className="shimmer mt-6 h-6 w-28 rounded-full" />
                    </div>
                  );
                }
                const l = loc as (typeof top5)[number];
                const v = l[horizonMeta.key] as number;
                return (
                  <motion.div
                    key={l.name + l.lat}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.06 }}
                  >
                    <Link
                      to="/location"
                      search={{ lat: l.lat, lon: l.lon, name: l.name }}
                      className="glass group flex h-full flex-col justify-between p-5 transition-all hover:-translate-y-1 hover:bg-white/12"
                    >
                      <div>
                        <div className="text-[11px] tracking-widest text-white/60 uppercase">
                          #{i + 1} · {l.province ?? "—"}
                        </div>
                        <div className="text-display mt-1 truncate text-xl font-semibold">
                          {l.name}
                        </div>
                      </div>
                      <div className="mt-4">
                        <div className="text-display text-4xl font-semibold">
                          <CountUp value={v * 100} /> <span className="text-lg text-white/50">%</span>
                        </div>
                        <div className="mt-3">
                          <RiskBadge value={v} />
                        </div>
                      </div>
                    </Link>
                  </motion.div>
                );
              })}
            </div>
          )}

          <div className="mt-8 text-center">
            <Link
              to="/map"
              className="text-display inline-flex items-center gap-2 text-sm text-white/85 underline-offset-4 hover:underline"
            >
              Explore all districts on the map
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}

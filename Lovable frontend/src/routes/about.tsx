import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { Database, Gauge, ShieldAlert, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Nav } from "@/components/Nav";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "About & methodology — FloodWatch" },
      {
        name: "description",
        content:
          "How FloodWatch estimates flash-flood risk: model, data sources, horizons, and honest limitations.",
      },
      { property: "og:title", content: "How FloodWatch works" },
      { property: "og:description", content: "Model, data sources, and honest limitations." },
    ],
  }),
  component: AboutPage,
});

function AboutPage() {
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api.meta(), retry: 1 });

  return (
    <>
      <div className="app-backdrop" />
      <Nav />

      <main className="mx-auto max-w-4xl px-4 pt-10 pb-24">
        <div className="text-xs tracking-widest text-white/60 uppercase">About & methodology</div>
        <h1 className="text-display mt-1 text-4xl font-semibold sm:text-5xl">
          How FloodWatch estimates risk
        </h1>
        <p className="mt-4 max-w-2xl text-white/80">
          A machine-learning model scores flash-flood risk by combining current and forecast weather
          with terrain, soil, drainage, and historical flood events. It's designed to help you
          compare places quickly — not to replace an official warning.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <InfoCard
            icon={<Sparkles className="h-4 w-4" />}
            title="What it does"
            body="Produces a 0–100% risk score per district for four horizons: the next hour, 24 hours, 7 days, and 30 days."
          />
          <InfoCard
            icon={<Database className="h-4 w-4" />}
            title="Where the data comes from"
            body={
              meta.data?.data_sources?.length
                ? meta.data.data_sources.join(" · ")
                : "Open weather APIs, terrain and soil datasets, and historical flood records."
            }
          />
          <InfoCard
            icon={<Gauge className="h-4 w-4" />}
            title="Horizons"
            body={
              meta.data?.horizons?.length
                ? meta.data.horizons.map((h) => h.label).join(" · ")
                : "Next hour · 24 hours · 7 days · 30 days"
            }
          />
          <InfoCard
            icon={<ShieldAlert className="h-4 w-4" />}
            title="Coverage"
            body={
              meta.data?.monitored_districts
                ? `${meta.data.monitored_districts} monitored districts across Pakistan.`
                : "All monitored districts across Pakistan."
            }
          />
        </div>

        <section className="glass mt-8 p-6">
          <h2 className="text-display text-xl font-semibold">Limitations — read this</h2>
          <ul className="mt-3 space-y-2 text-sm text-white/85">
            <li>
              • This is a prototype. Trust the <span className="font-medium">ranking</span> between
              locations more than the exact percentage.
            </li>
            <li>
              • Absolute percentages tend to run high. Treat the color band as the primary signal.
            </li>
            <li>
              • Free weather APIs occasionally hiccup. If a card looks wrong, refresh.
            </li>
            <li>
              • Not an official warning. In an emergency, follow guidance from PDMA / NDMA.
            </li>
          </ul>
        </section>

        {meta.data?.notes && (
          <section className="glass mt-6 p-6">
            <div className="text-xs tracking-widest text-white/60 uppercase">Notes</div>
            <p className="mt-2 text-sm text-white/85">{meta.data.notes}</p>
          </section>
        )}

        {meta.data?.risk_computed_at && (
          <p className="mt-8 text-center text-xs text-white/50">
            Risk snapshot computed {format(new Date(meta.data.risk_computed_at * 1000), "PPpp")}
          </p>
        )}
      </main>
    </>
  );
}

function InfoCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="glass p-5">
      <div className="flex items-center gap-2 text-xs tracking-wider text-white/60 uppercase">
        <span className="text-white/50">{icon}</span> {title}
      </div>
      <p className="mt-2 text-sm text-white/85">{body}</p>
    </div>
  );
}

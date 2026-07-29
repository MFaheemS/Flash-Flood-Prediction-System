import { Link, useRouterState } from "@tanstack/react-router";
import { Droplets, Map, BarChart3, Info, Home, List, Clapperboard, Menu, X } from "lucide-react";
import { useState } from "react";

const links = [
  { to: "/", label: "Home", icon: Home },
  { to: "/map", label: "Map", icon: Map },
  { to: "/districts", label: "Districts", icon: List },
  { to: "/explore", label: "Explore", icon: Clapperboard },
  { to: "/factors", label: "Factors", icon: BarChart3 },
  { to: "/about", label: "About", icon: Info },
] as const;

export function Nav() {
  const [open, setOpen] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <header className="sticky top-0 z-[1200] px-4 pt-4">
      <nav className="solid-panel mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/" className="flex items-center gap-2">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-xl"
            style={{
              background: "linear-gradient(135deg, #3b82c4, #46A758)",
              boxShadow: "0 6px 20px -6px rgba(59,130,196,0.6)",
            }}
          >
            <Droplets className="h-5 w-5 text-white" />
          </div>
          <div className="leading-tight">
            <div className="text-display text-base font-semibold">FloodWatch</div>
            <div className="text-[11px] text-white/60">Flash-flood risk · Pakistan</div>
          </div>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {links.map((l) => {
            const active = pathname === l.to || (l.to !== "/" && pathname.startsWith(l.to));
            return (
              <Link
                key={l.to}
                to={l.to}
                className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
                  active
                    ? "bg-white/15 text-white"
                    : "text-white/75 hover:bg-white/10 hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </div>

        <button
          className="rounded-full p-2 text-white/80 hover:bg-white/10 md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {open && (
        <div className="solid-panel mx-auto mt-2 flex max-w-6xl flex-col gap-1 p-2 md:hidden">
          {links.map((l) => {
            const Icon = l.icon;
            const active = pathname === l.to || (l.to !== "/" && pathname.startsWith(l.to));
            return (
              <Link
                key={l.to}
                to={l.to}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm ${
                  active ? "bg-white/15 text-white" : "text-white/80 hover:bg-white/10"
                }`}
              >
                <Icon className="h-4 w-4" />
                {l.label}
              </Link>
            );
          })}
        </div>
      )}
    </header>
  );
}

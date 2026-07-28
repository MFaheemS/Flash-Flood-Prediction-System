import { HORIZONS, type Horizon } from "@/lib/api";
import { cn } from "@/lib/utils";

export function HorizonTabs({
  value,
  onChange,
  className,
}: {
  value: Horizon;
  onChange: (h: Horizon) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "glass inline-flex flex-wrap items-center gap-1 p-1",
        className,
      )}
    >
      {HORIZONS.map((h) => {
        const active = h.id === value;
        return (
          <button
            key={h.id}
            onClick={() => onChange(h.id)}
            className={cn(
              "rounded-full px-4 py-1.5 text-xs font-medium transition-all",
              active
                ? "bg-white text-black shadow-lg"
                : "text-white/75 hover:bg-white/10 hover:text-white",
            )}
          >
            {h.label}
          </button>
        );
      })}
    </div>
  );
}

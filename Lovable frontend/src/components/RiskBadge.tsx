import { riskBand, riskColorHex, riskLabel, pct } from "@/lib/risk";
import { cn } from "@/lib/utils";

export function RiskBadge({
  value,
  className,
  size = "md",
}: {
  value: number | null | undefined;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const band = riskBand(value ?? 0);
  const color = riskColorHex(band);
  const sizes =
    size === "sm"
      ? "text-[11px] px-2 py-0.5"
      : size === "lg"
        ? "text-sm px-3 py-1.5"
        : "text-xs px-2.5 py-1";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap",
        sizes,
        className,
      )}
      style={{
        background: `${color}22`,
        color: color,
        border: `1px solid ${color}55`,
      }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: color, boxShadow: `0 0 8px ${color}` }}
      />
      {riskLabel(band)} · {pct(value)}
    </span>
  );
}

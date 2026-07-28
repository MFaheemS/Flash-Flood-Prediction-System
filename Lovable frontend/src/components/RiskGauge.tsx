import { useEffect, useState } from "react";
import { riskBand, riskColorHex, riskLabel } from "@/lib/risk";

/**
 * Radial arc gauge showing risk 0..1 with animated fill + count-up.
 */
export function RiskGauge({
  value,
  label,
  size = 180,
}: {
  value: number;
  label: string;
  size?: number;
}) {
  const band = riskBand(value);
  const color = riskColorHex(band);
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    const start = performance.now();
    const dur = 900;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - k, 3);
      setDisplay(value * eased);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  const stroke = 14;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  // 3/4 arc
  const arcLen = c * 0.75;
  const offset = arcLen * (1 - display);

  return (
    <div className="flex flex-col items-center">
      <div className="text-xs tracking-wide text-white/70 uppercase">{label}</div>
      <div className="relative" style={{ width: size, height: size * 0.82 }}>
        <svg
          viewBox={`0 0 ${size} ${size}`}
          className="absolute inset-0"
          style={{ transform: "rotate(135deg)" }}
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="rgba(255,255,255,0.12)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arcLen} ${c}`}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arcLen} ${c}`}
            strokeDashoffset={offset}
            style={{
              filter: `drop-shadow(0 0 10px ${color}88)`,
              transition: "stroke 300ms ease",
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center pt-3">
          <div className="text-display text-4xl font-semibold" style={{ color }}>
            {Math.round(display * 100)}
            <span className="text-xl text-white/60">%</span>
          </div>
          <div className="mt-1 text-xs font-medium text-white/70">{riskLabel(band)}</div>
        </div>
      </div>
    </div>
  );
}

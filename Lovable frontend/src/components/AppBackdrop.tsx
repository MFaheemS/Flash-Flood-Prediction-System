/**
 * Static backdrop for the non-weather pages (Factors, About, Districts,
 * Explore). Flat dark base + a fine dot grid + faint concentric "ripple"
 * rings (the app's water motif). No gradient colour washes.
 */
function Ripples({ cx, cy, color }: { cx: string; cy: string; color: string }) {
  return (
    <g>
      {[110, 210, 320, 450, 600, 780].map((r, i) => (
        <circle
          key={i}
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={1}
          opacity={0.07 - i * 0.009}
        />
      ))}
    </g>
  );
}

export function AppBackdrop() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden" style={{ backgroundColor: "#0a0e16" }}>
      {/* fine dot grid */}
      <div
        className="absolute inset-0"
        style={{
          backgroundImage: "radial-gradient(rgba(255,255,255,0.045) 1px, transparent 1.4px)",
          backgroundSize: "26px 26px",
          backgroundPosition: "-1px -1px",
        }}
      />
      {/* faint ripple rings */}
      <svg className="absolute inset-0 h-full w-full" preserveAspectRatio="xMidYMid slice" viewBox="0 0 1600 900">
        <Ripples cx="1500" cy="120" color="#3b82c4" />
        <Ripples cx="120" cy="880" color="#46A758" />
      </svg>
      {/* very subtle top edge sheen (single hairline, not a wash) */}
      <div className="absolute inset-x-0 top-0 h-px" style={{ background: "rgba(255,255,255,0.06)" }} />
    </div>
  );
}

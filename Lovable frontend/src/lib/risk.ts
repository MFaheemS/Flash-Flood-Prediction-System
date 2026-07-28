export type RiskBand = "very-high" | "high" | "moderate" | "low";

export function riskBand(v: number | null | undefined): RiskBand {
  const n = v ?? 0;
  if (n >= 0.75) return "very-high";
  if (n >= 0.5) return "high";
  if (n >= 0.25) return "moderate";
  return "low";
}

export function riskLabel(band: RiskBand) {
  return band === "very-high"
    ? "Very High"
    : band === "high"
      ? "High"
      : band === "moderate"
        ? "Moderate"
        : "Low";
}

export function riskColorVar(band: RiskBand) {
  return `var(--risk-${band})`;
}

export function riskColorHex(band: RiskBand) {
  return band === "very-high"
    ? "#E5484D"
    : band === "high"
      ? "#F76808"
      : band === "moderate"
        ? "#F5D90A"
        : "#46A758";
}

export function pct(v: number | null | undefined, digits = 0) {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

const FACTOR_LABELS: Record<string, string> = {
  snow_mean: "Snow cover (avg)",
  snow_max: "Snow cover (peak)",
  precip_max: "Peak daily rain",
  precip_total: "Total monthly rain",
  precip_days: "Rainy days",
  precip_prev_month: "Previous month's rain",
  temp_mean: "Temperature (avg)",
  temp_max: "Temperature (peak)",
  veg_mean: "Vegetation cover",
  month: "Time of year",
  soil_moisture_root: "Soil moisture (root)",
  soil_moisture_surface: "Soil moisture (surface)",
  soil_clay_pct: "Soil clay %",
  distance_to_waterway_km: "Distance to waterway",
  waterway_count_10km: "Waterways within 10km",
  historical_flood_freq: "Historical flood frequency",
  urbanization_index: "Urbanization",
  temp_dewpoint_spread: "Temp–dewpoint spread",
  pressure_drop_3h: "3h pressure drop",
};

export function formatFactor(feature: string) {
  if (FACTOR_LABELS[feature]) return FACTOR_LABELS[feature];
  return feature
    .replace(/_/g, " ")
    .replace(/\bpct\b/gi, "%")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

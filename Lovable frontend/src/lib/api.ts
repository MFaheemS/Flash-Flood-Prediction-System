export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8080";

export type WeatherCondition = "clear" | "clouds" | "fog" | "rain" | "snow" | "storm";

export interface CurrentWeather {
  lat: number;
  lon: number;
  temperature: number;
  apparent_temperature?: number;
  humidity?: number;
  precipitation?: number;
  wind_speed?: number;
  cloud_cover?: number;
  weather_code?: number;
  condition: WeatherCondition;
  description: string;
  is_day: boolean;
  observed_at?: string;
}

export interface RiskLocation {
  name: string;
  lat: number;
  lon: number;
  province?: string;
  hour_risk: number;
  day_risk: number;
  week_risk: number;
  month_risk: number;
  peak_time: string | null;
  elevation?: number | null;
  slope?: number | null;
  urbanization_index?: number | null;
  historical_flood_freq?: number | null;
  distance_to_waterway_km?: number | null;
  waterway_count_10km?: number | null;
  soil_clay_pct?: number | null;
  soil_moisture_root?: number | null;
  soil_moisture_surface?: number | null;
  // district satellite model drivers
  model?: string;
  gaul_district?: string | null;
  forecast_precip_total_mm?: number | null;
  forecast_precip_max_mm?: number | null;
  forecast_temp_mean_c?: number | null;
  snow_climatology?: number | null;
  veg_climatology?: number | null;
  veg_trend?: number | null;
  precip_prev_month_mm?: number | null;
  month?: number | null;
}

export type Horizon = "hour" | "day" | "week" | "month";

export const HORIZONS: { id: Horizon; label: string; key: keyof RiskLocation }[] = [
  { id: "hour", label: "24 hours", key: "hour_risk" },
  { id: "day", label: "3 days", key: "day_risk" },
  { id: "week", label: "7 days", key: "week_risk" },
  { id: "month", label: "16 days", key: "month_risk" },
];

export interface RiskResponse {
  horizon: Horizon;
  computed_at: number | null;
  locations: RiskLocation[];
}

export interface FactorItem {
  rank: number;
  feature: string;
  mean_abs_shap_impact: number;
  direction: "increases risk" | "decreases risk";
  relative_importance_pct: number;
}

export interface FactorsResponse {
  dataset: string;
  label: string;
  factors: FactorItem[];
}

export interface MetaResponse {
  name: string;
  horizons: { id: string; label: string }[];
  factor_datasets: { id: string; label: string }[];
  monitored_districts: number;
  risk_computed_at: number | null;
  data_sources: string[];
  notes: string;
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (res.status === 503) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body?.detail ?? "Service warming up") as Error & { status?: number };
    err.status = 503;
    throw err;
  }
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return (await res.json()) as T;
}

export const api = {
  meta: () => apiGet<MetaResponse>("/api/meta"),
  risk: (horizon: Horizon = "week") => apiGet<RiskResponse>(`/api/risk?horizon=${horizon}`),
  riskPoint: (lat: number, lon: number, name?: string) =>
    apiGet<RiskLocation>(
      `/api/risk/point?lat=${lat}&lon=${lon}${name ? `&name=${encodeURIComponent(name)}` : ""}`,
    ),
  weather: (lat: number, lon: number) =>
    apiGet<CurrentWeather>(`/api/weather/current?lat=${lat}&lon=${lon}`),
  factors: (dataset: "district_flood" | "satellite_flood" | "cloudburst" | "flood_factors") =>
    apiGet<FactorsResponse>(`/api/factors?dataset=${dataset}`),
};

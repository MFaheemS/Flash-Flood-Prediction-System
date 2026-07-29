import type { WeatherCondition } from "./api";

/**
 * Weather-reactive background videos, served from /public/videos.
 * pickWeatherVideo() maps live weather (WMO code + wind + cloud cover, plus an
 * optional flood-risk override) to one of the clips. Every branch resolves to a
 * clip and `clear` is the final fallback, so there is never a state without a
 * background. All nine clips are reachable.
 */
export const FLOOD_VIDEO = "/videos/flood.mp4";

export interface VideoPick {
  src: string;
  condition: WeatherCondition; // for the gradient fallback behind the video
}

const has = (code: number, arr: number[]) => arr.includes(code);

export function pickWeatherVideo(
  w?: { weather_code?: number | null; wind_speed?: number | null; cloud_cover?: number | null } | null,
  floodRisk?: number | null,
): VideoPick {
  // Flood override — a genuinely high modelled risk trumps the sky.
  if (floodRisk != null && floodRisk >= 0.4) return { src: FLOOD_VIDEO, condition: "rain" };

  const code = w?.weather_code ?? -1;
  const wind = w?.wind_speed ?? 0;
  const cloud = w?.cloud_cover ?? 0;

  if (has(code, [95, 96, 99])) return { src: "/videos/storm.mp4", condition: "storm" };
  if (code === 82) return { src: FLOOD_VIDEO, condition: "rain" }; // violent rain showers
  if (has(code, [71, 73, 75, 77, 85, 86])) return { src: "/videos/snow.mp4", condition: "snow" };
  if (has(code, [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81]))
    return { src: "/videos/rain.mp4", condition: "rain" };
  if (has(code, [45, 48])) return { src: "/videos/fog.mp4", condition: "fog" };
  if (wind >= 30) return { src: "/videos/windy.mp4", condition: "clouds" }; // breezy, no precip
  if (code === 3 || cloud >= 70) return { src: "/videos/clouds.mp4", condition: "clouds" }; // overcast
  if (code === 2 || cloud >= 25) return { src: "/videos/clouds-light.mp4", condition: "clouds" }; // partly cloudy
  return { src: "/videos/clear.mp4", condition: "clear" }; // always applicable
}

export function gradientClass(condition: WeatherCondition, isDay: boolean) {
  switch (condition) {
    case "clear":
      return isDay ? "grad-clear-day" : "grad-clear-night";
    case "clouds":
      return "grad-clouds";
    case "fog":
      return "grad-fog";
    case "rain":
      return "grad-rain";
    case "snow":
      return "grad-snow";
    case "storm":
      return "grad-storm";
  }
}

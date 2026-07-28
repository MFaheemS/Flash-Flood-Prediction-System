import type { WeatherCondition } from "./api";

/**
 * Weather-reactive background videos, served from /public/videos.
 * One clip per condition (used for both day and night). If a clip fails to
 * load, WeatherBackground falls back to the animated CSS gradient.
 */
export const CONDITION_VIDEOS: Record<WeatherCondition, { day: string; night: string }> = {
  clear: { day: "/videos/clear.mp4", night: "/videos/clear.mp4" },
  clouds: { day: "/videos/clouds.mp4", night: "/videos/clouds.mp4" },
  fog: { day: "/videos/fog.mp4", night: "/videos/fog.mp4" },
  rain: { day: "/videos/rain.mp4", night: "/videos/rain.mp4" },
  snow: { day: "/videos/snow.mp4", night: "/videos/snow.mp4" },
  storm: { day: "/videos/storm.mp4", night: "/videos/storm.mp4" },
};

/** Shown instead of the weather clip when a location's flood risk is high. */
export const FLOOD_VIDEO = "/videos/flood.mp4";

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

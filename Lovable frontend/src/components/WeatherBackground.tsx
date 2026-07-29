import { useEffect, useRef, useState } from "react";
import type { CurrentWeather } from "@/lib/api";
import { pickWeatherVideo, gradientClass } from "@/lib/videos";

interface Props {
  weather?: CurrentWeather | null;
  /** 0–1 modelled flood risk; a high value shows the flood clip. */
  floodRisk?: number | null;
}

/**
 * Full-bleed cinematic weather background: animated gradient (always visible)
 * with a looping video crossfaded on top when it loads. The clip is chosen from
 * the live weather (all conditions map to a clip; clear is the fallback).
 */
export function WeatherBackground({ weather, floodRisk }: Props) {
  const pick = pickWeatherVideo(weather ?? undefined, floodRisk);
  const isDay = weather?.is_day ?? true;
  const [videoReady, setVideoReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    setVideoReady(false);
  }, [pick.src]);

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      {/* Always-on animated gradient fallback */}
      <div
        className={`absolute inset-0 ${gradientClass(pick.condition, isDay)} transition-opacity duration-700`}
      />

      {/* Video crossfade */}
      <video
        key={pick.src}
        ref={videoRef}
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        onCanPlay={() => setVideoReady(true)}
        onError={() => setVideoReady(false)}
        className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-700 ${
          videoReady ? "opacity-100" : "opacity-0"
        }`}
      >
        <source src={pick.src} type="video/mp4" />
      </video>

      {/* Dark scrim so text stays readable */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.25) 40%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </div>
  );
}

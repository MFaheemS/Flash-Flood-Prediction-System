import { useEffect, useRef, useState } from "react";
import type { WeatherCondition } from "@/lib/api";
import { CONDITION_VIDEOS, gradientClass } from "@/lib/videos";

interface Props {
  condition?: WeatherCondition;
  isDay?: boolean;
}

/**
 * Full-bleed cinematic weather background: animated gradient (always visible)
 * with a looping video crossfaded on top when it loads. Dark scrim ensures
 * text remains readable.
 */
export function WeatherBackground({ condition = "clouds", isDay = true }: Props) {
  const [videoSrc, setVideoSrc] = useState<string | null>(null);
  const [videoReady, setVideoReady] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    setVideoReady(false);
    const variant = CONDITION_VIDEOS[condition];
    const url = (isDay ? variant.day : variant.night) ?? variant.day;
    setVideoSrc(url);
  }, [condition, isDay]);

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      {/* Always-on animated gradient fallback */}
      <div
        className={`absolute inset-0 ${gradientClass(condition, isDay)} transition-opacity duration-700`}
      />

      {/* Video crossfade */}
      {videoSrc && (
        <video
          key={videoSrc}
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
          <source src={videoSrc} type="video/mp4" />
        </video>
      )}

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

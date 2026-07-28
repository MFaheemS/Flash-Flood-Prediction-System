import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CurrentWeather } from "./api";

const FALLBACK = { lat: 33.6844, lon: 73.0479, label: "Islamabad" };

export function useGeolocation() {
  const [coords, setCoords] = useState<{ lat: number; lon: number; label: string } | null>(null);

  useEffect(() => {
    if (!("geolocation" in navigator)) {
      setCoords(FALLBACK);
      return;
    }
    let done = false;
    const timeout = setTimeout(() => {
      if (!done) setCoords(FALLBACK);
    }, 6000);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        done = true;
        clearTimeout(timeout);
        setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude, label: "Your location" });
      },
      () => {
        done = true;
        clearTimeout(timeout);
        setCoords(FALLBACK);
      },
      { timeout: 5000, maximumAge: 600000 },
    );
    return () => clearTimeout(timeout);
  }, []);

  return coords;
}

export function useCurrentWeather(lat?: number, lon?: number) {
  return useQuery<CurrentWeather>({
    queryKey: ["weather", lat, lon],
    queryFn: () => api.weather(lat!, lon!),
    enabled: lat != null && lon != null,
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}

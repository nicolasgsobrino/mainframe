import { useEffect, useRef, useState } from "react";
import { useDemo } from "../../demo";

const reducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Cifra que cuenta hasta su valor en Modo Demo (y salta directa fuera de él),
 * para que la audiencia vea el resultado aparecer en lugar de estar ya ahí.
 */
export function CountUp({ value, duration = 700 }: { value: number; duration?: number }) {
  const { active } = useDemo();
  const [shown, setShown] = useState(value);
  const from = useRef(value);

  useEffect(() => {
    if (!active || reducedMotion() || from.current === value) {
      from.current = value;
      setShown(value);
      return;
    }
    const start = performance.now();
    const origin = from.current;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setShown(Math.round(origin + (value - origin) * (1 - (1 - t) ** 3)));
      if (t < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, active]);

  return <>{shown.toLocaleString("es-ES")}</>;
}

/**
 * Revela una lista poco a poco en Modo Demo; fuera de él la devuelve entera.
 * No filtra ni inventa datos: sólo controla cuántos se están mostrando ya.
 */
export function useProgressiveReveal<T>(items: T[], stepMs = 350): T[] {
  const { active } = useDemo();
  const [count, setCount] = useState(0);

  // Al entrar en Modo Demo la lista se recompone desde el principio.
  useEffect(() => { if (active) setCount(0); }, [active]);

  useEffect(() => {
    if (!active || reducedMotion()) return;
    const timer = setInterval(() => setCount((c) => (c >= items.length ? c : c + 1)), stepMs);
    return () => clearInterval(timer);
  }, [items.length, stepMs, active]);

  return active ? items.slice(0, count) : items;
}

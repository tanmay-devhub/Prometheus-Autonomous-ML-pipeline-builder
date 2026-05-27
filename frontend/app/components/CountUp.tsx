"use client";

import { useState, useEffect } from "react";

interface Props {
  to: number;
  decimals?: number;
  suffix?: string;
  duration?: number;
}

export default function CountUp({ to, decimals = 4, suffix = "", duration = 1200 }: Props) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    const start = performance.now();
    let raf: number;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setVal(to * (1 - Math.pow(1 - t, 3)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, duration]);
  return <span>{val.toFixed(decimals)}{suffix}</span>;
}

"use client";

import { motion, useReducedMotion } from "motion/react";

const COLORS = ["#22c55e", "#3b82f6", "#eab308", "#ec4899", "#a855f7", "#f97316"];

/** A small confetti burst when a deal is agreed. Skipped when the system asks for less motion. */
export function Burst({ show }: { show: boolean }) {
  const reduce = useReducedMotion();
  if (!show || reduce) return null;
  return (
    <span className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-visible" aria-hidden>
      {Array.from({ length: 18 }, (_, i) => {
        const angle = (i / 18) * Math.PI * 2;
        const dist = 60 + (i % 3) * 18;
        return (
          <motion.span
            key={i}
            className="absolute w-1.5 h-1.5 rounded-[2px]"
            style={{ background: COLORS[i % COLORS.length] }}
            initial={{ x: 0, y: 0, opacity: 1, scale: 1, rotate: 0 }}
            animate={{ x: Math.cos(angle) * dist, y: Math.sin(angle) * dist + 20, opacity: 0, scale: 0.6, rotate: 180 }}
            transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1] }}
          />
        );
      })}
    </span>
  );
}

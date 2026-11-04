"use client";

import { useEffect } from "react";
import { MotionConfig } from "motion/react";

/**
 * One consistent "feel" for the whole app:
 * - press: anything you click sinks slightly (97%) and springs back, on every button, tab and menu item;
 * - haptics: an 8 ms tap on phones that allow it (Android). Browsers can't drive the Mac trackpad's
 *   haptic engine or iPhone vibration, so there the press animation is the feedback;
 * - reduced motion: if the system asks for less motion, none of this runs and Motion animations are
 *   cut to fades (MotionConfig reducedMotion="user").
 */
const PRESSABLE =
  'button:not(:disabled), [role="tab"], [role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"], [data-press]';
const MAX_PRESS_WIDTH = 360; // big surfaces (rows, cards) don't sink: it looks like the page moved
const PRESS_SCALE = 0.97;

function reducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function haptic(ms = 8) {
  try {
    if (!reducedMotion() && typeof navigator !== "undefined" && "vibrate" in navigator) navigator.vibrate(ms);
  } catch {}
}

export function Feel({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const pressed = new Set<HTMLElement>();
    const release = () => {
      pressed.forEach((el) => el.animate([{ scale: PRESS_SCALE }, { scale: 1 }], { duration: 160, easing: "cubic-bezier(.2,.8,.2,1)" }));
      pressed.clear();
    };
    const down = (e: PointerEvent) => {
      if (e.button !== 0 || reducedMotion()) return;
      const el = (e.target as Element | null)?.closest?.(PRESSABLE) as HTMLElement | null;
      if (!el || el.getBoundingClientRect().width > MAX_PRESS_WIDTH) return;
      el.animate([{ scale: 1 }, { scale: PRESS_SCALE }], { duration: 90, easing: "ease-out", fill: "forwards" });
      pressed.add(el);
      if (e.pointerType === "touch") haptic();
    };
    const up = () => {
      // drop the "forwards" hold, then spring back
      pressed.forEach((el) => el.getAnimations().forEach((a) => a.cancel()));
      release();
    };
    document.addEventListener("pointerdown", down, { passive: true });
    document.addEventListener("pointerup", up, { passive: true });
    document.addEventListener("pointercancel", up, { passive: true });
    return () => {
      document.removeEventListener("pointerdown", down);
      document.removeEventListener("pointerup", up);
      document.removeEventListener("pointercancel", up);
    };
  }, []);

  return (
    <MotionConfig reducedMotion="user" transition={{ type: "spring", stiffness: 500, damping: 38, mass: 0.6 }}>
      {children}
    </MotionConfig>
  );
}

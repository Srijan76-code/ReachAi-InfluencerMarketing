"use client";

import { createElement, useEffect, type HTMLAttributes } from "react";

export type LoadingAnimation =
  | "orbit"
  | "beacon"
  | "matrix"
  | "cells"
  | "register"
  | "bands"
  | "lift";

export interface LoadingProps extends Omit<HTMLAttributes<HTMLElement>, "children"> {
  animation?: LoadingAnimation;
  size?: number;
  speed?: number;
  paused?: boolean;
}

/** Seven CSS loaders. Color inherits; reduced motion stays still. */
export function Loading({
  animation = "orbit",
  size = 32,
  speed = 1,
  paused = false,
  style,
  ...props
}: LoadingProps) {
  useEffect(() => {
    // Register only in the browser, including when rendered by Next.js.
    void import("./loading-indicator.js");
  }, []);

  const pixels = Number.isFinite(size) ? Math.min(160, Math.max(12, size)) : 32;
  return createElement("loading-indicator", {
    ...props,
    animation,
    size: String(pixels),
    speed: String(speed),
    paused: paused ? "" : undefined,
    role: props.role ?? "status",
    "aria-label": props["aria-label"] ?? "Loading",
    style: { display: "inline-grid", width: pixels, height: pixels, ...style },
  });
}

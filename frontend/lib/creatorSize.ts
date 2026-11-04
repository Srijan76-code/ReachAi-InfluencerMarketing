/** The creator-size slider has 13 steps; step i (1-based) means SIZE_STEPS[i - 1] subscribers. */
export const SIZE_STEPS = [1000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000, 2000000, 5000000, 10000000, 12000000];

export function stepToSubscribers(step: number, fallback: number): number {
  return SIZE_STEPS[step - 1] ?? fallback;
}

/** Subscriber count -> closest slider step, or `fallback` when not set. */
export function subscribersToStep(value: unknown, fallback: number): number {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  let best = 0;
  SIZE_STEPS.forEach((t, i) => {
    if (Math.abs(t - n) < Math.abs(SIZE_STEPS[best] - n)) best = i;
  });
  return best + 1;
}

import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";

export default function RangeSlider() {
  const maxValue = 13;
  const minValue = 1;
  const skipInterval = 1; // Set to 1 to allow no text skipping

  const ticks = {
    "1k": 1,
    "5k": 2,
    "10k": 3,
    "20k": 4,
    "50k": 5,
    "100k": 6,
    "200k": 7,
    "500k": 8,
    "1M": 9,
    "2M": 10,
    "5M": 11,
    "10M": 12,
    "12M": 13,
  };
  return (
    <div className="*:not-first:mt-4">
      <Label htmlFor="creator-size-slider">Creator Size (Subscriber count)</Label>
      <div>
        <Slider
          aria-label="Slider with ticks"
          defaultValue={[3, 8]}
          max={maxValue}
          min={minValue}
        />
        <span
          aria-hidden="true"
          className="mt-3 flex w-full items-center justify-between gap-1 px-2.5 font-medium text-muted-foreground text-xs"
        >
          {Object.keys(ticks).map((v, i) => (
            <span
              className="flex w-0 flex-col items-center justify-center gap-2"
              key={String(i)}
            >
              <span
                className={cn(
                  "h-1 w-px bg-muted-foreground/70",
                  i % skipInterval !== 0 && "h-0.5",
                )}
              />
              <span className={cn(i % skipInterval !== 0 && "opacity-0")}>
                {v}
              </span>
            </span>
          ))}
        </span>
      </div>
    </div>
  );
}

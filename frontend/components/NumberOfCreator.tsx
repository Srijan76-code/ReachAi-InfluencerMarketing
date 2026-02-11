import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";

export default function NumberOfCreator() {
  const maxValue = 20;

  const skipInterval = 2; // Set to 1 to allow no text skipping

 const ticks = [...Array(maxValue + 1)].map((_, i) => i);
  return (
    <div className="*:not-first:mt-4">
      <Label htmlFor="creator-size-slider">How many creators do you want to hire?</Label>
      <div>
        <Slider
          aria-label="Slider with ticks"
          defaultValue={[3]}
          max={maxValue}

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

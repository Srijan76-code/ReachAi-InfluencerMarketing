import { useId } from "react";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Info } from "lucide-react";

export default function RadioCards3({
  items,
  label,
  sublabel,
}: {
  items: { label: string; value: string }[];
  label: string;
  sublabel?: string;
}) {
  const id = useId();

  return (
    <fieldset className="space-y-4">
      <legend className="font-medium text-foreground text-sm leading-none">
        {label} <span className="text-destructive">*</span>
      </legend>
      <RadioGroup className="flex flex-wrap gap-4" defaultValue="1">
        {items.map((item) => (
          <div
            className="relative flex flex-col items-start gap-4 rounded-md border border-input p-3 shadow-xs outline-none has-data-[state=checked]:border-primary/50"
            key={`${id}-${item.value}`}
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem
                className="after:absolute after:inset-0"
                id={`${id}-${item.value}`}
                value={item.value}
              />
              <Label htmlFor={`${id}-${item.value}`}>{item.label}</Label>
            </div>
          </div>
        ))}
      </RadioGroup>
      {sublabel && (
        <div className="flex items-center text-muted-foreground gap-1">
          <Info size={12} />
          <p className="text-muted-foreground  text-xs">{sublabel}</p>
        </div>
      )}
    </fieldset>
  );
}

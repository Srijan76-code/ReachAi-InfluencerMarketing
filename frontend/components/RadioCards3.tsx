import { useId } from "react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Info } from "lucide-react";

export default function RadioCards3({
  items,
  label,
  sublabel,
  value,
  onChange,
}: {
  items: { label: string; value: string }[];
  label: string;
  sublabel?: string;
  value?: string;
  onChange?: (val: string) => void;
}) {
  const id = useId();

  return (
    <fieldset className="space-y-2">
      <legend className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300 leading-none mb-2">
        {label} <span className="text-rose-500">*</span>
      </legend>
      <RadioGroup
        className="flex flex-wrap gap-2"
        value={value}
        onValueChange={onChange}
        defaultValue={value || "1"}
      >
        {items.map((item) => (
          <div
            className="relative flex flex-col items-start gap-2 rounded-md border border-input p-2.5 shadow-xs outline-none has-data-[state=checked]:border-primary/50 cursor-pointer"
            key={`${id}-${item.value}`}
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem
                className="after:absolute after:inset-0 h-3.5 w-3.5"
                id={`${id}-${item.value}`}
                value={item.value}
              />
              <label
                htmlFor={`${id}-${item.value}`}
                className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300 cursor-pointer"
              >
                {item.label}
              </label>
            </div>
          </div>
        ))}
      </RadioGroup>
      {sublabel && (
        <div className="flex items-center text-zinc-400 gap-1">
          <Info size={11} />
          <p className="text-[11px]">{sublabel}</p>
        </div>
      )}
    </fieldset>
  );
}

import { RiAppleLine, RiBankCardLine, RiPaypalLine } from "@remixicon/react";
import { useId } from "react";

import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

export default function RadioCards2() {
  const id = useId();
  return (
    <RadioGroup className="grid-cols-3" defaultValue="1">
      {/* Credit card */}
      <div className="relative flex cursor-pointer flex-col items-center gap-3 rounded-md border border-input px-2 py-3 text-center shadow-xs outline-none transition-[color,box-shadow] has-data-[state=checked]:border-primary/50 has-focus-visible:border-ring has-focus-visible:ring-[3px] has-focus-visible:ring-ring/50">
        <RadioGroupItem className="sr-only" id={`${id}-1`} value="1" />
        <RiBankCardLine aria-hidden="true" className="opacity-60" size={20} />
        <label
          className="cursor-pointer font-medium text-foreground text-xs leading-none after:absolute after:inset-0"
          htmlFor={`${id}-1`}
        >
          Card
        </label>
      </div>
      {/* PayPal */}
      <div className="relative flex cursor-pointer flex-col items-center gap-3 rounded-md border border-input px-2 py-3 text-center shadow-xs outline-none transition-[color,box-shadow] has-data-[state=checked]:border-primary/50 has-focus-visible:border-ring has-focus-visible:ring-[3px] has-focus-visible:ring-ring/50">
        <RadioGroupItem className="sr-only" id={`${id}-2`} value="2" />
        <RiPaypalLine aria-hidden="true" className="opacity-60" size={20} />
        <label
          className="cursor-pointer font-medium text-foreground text-xs leading-none after:absolute after:inset-0"
          htmlFor={`${id}-2`}
        >
          PayPal
        </label>
      </div>
      {/* Apple Pay */}
      <div className="relative flex cursor-pointer flex-col items-center gap-3 rounded-md border border-input px-2 py-3 text-center shadow-xs outline-none transition-[color,box-shadow] has-data-[state=checked]:border-primary/50 has-focus-visible:border-ring has-focus-visible:ring-[3px] has-focus-visible:ring-ring/50">
        <RadioGroupItem className="sr-only" id={`${id}-3`} value="3" />
        <RiAppleLine aria-hidden="true" className="opacity-60" size={20} />
        <label
          className="cursor-pointer font-medium text-foreground text-xs leading-none after:absolute after:inset-0"
          htmlFor={`${id}-3`}
        >
          Apple Pay
        </label>
      </div>
    </RadioGroup>
  );
}

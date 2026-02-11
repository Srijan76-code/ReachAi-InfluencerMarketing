import { Brush, Eraser, Scissors, SwatchBook, Youtube } from "lucide-react";
import { useId } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { RiInstagramFill, RiYoutubeFill } from "@remixicon/react";
import { color } from "framer-motion";

export default function MultiPlatform() {
  const id = useId();

  const items = [
    { defaultChecked: true, Icon: RiYoutubeFill, label: "YouTube", value: "1",disabled:false  },
    { Icon: RiInstagramFill, label: "Instagram", value: "2" ,disabled:true },

  ];

  return (
    <div className="*:not-first:mt-2">
      <Label htmlFor={id}>Platforms <span className="text-destructive">*</span></Label>
    <div className="flex   gap-4 flex-wrap">
      
      {items.map((item) => (
        <div
          className="relative flex cursor-pointer justify-between  gap-4 rounded-md border border-input p-3 shadow-xs outline-none has-data-[state=checked]:border-primary/50"
          key={`${id}-${item.value}`}
        >
          <div className="flex justify-between gap-2">
            <item.Icon aria-hidden="true" className="opacity-60"   size={20} />
            <Label htmlFor={`${id}-${item.value}`}>{item.label}</Label>
          </div>
          <Checkbox
            className="order-1 after:absolute after:inset-0"
            defaultChecked={item.defaultChecked}
            id={`${id}-${item.value}`}
            value={item.value}
            disabled={item?.disabled}
          />
        </div>
      ))}
    </div>
    </div>
  );
}

"use client";

import { useId } from "react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { User, GraduationCap, BadgeCheck } from "lucide-react";
import { useCampaignStore } from "@/store/campaignStore";

export default function CreatorAuthority() {
  const id = useId();
  const creatorAuthority = useCampaignStore((state) => state.creatorAuthority);
  const setField = useCampaignStore((state) => state.setField);

  const items = [
    {
      value: "1",
      label: "Peer / relatable",
      desc: "Just like me — good for viral reach",
      icon: <User size={14} className="text-blue-500" />,
    },
    {
      value: "2",
      label: "Mentor",
      desc: "Teacher figure — good for mid-ticket sales",
      icon: <GraduationCap size={14} className="text-blue-500" />,
    },
    {
      value: "3",
      label: "Expert",
      desc: "Industry leader — good for high-ticket trust",
      icon: <BadgeCheck size={14} className="text-blue-500" />,
    },
  ];

  return (
    <fieldset className="space-y-2">
      <legend className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300 leading-none mb-2">
        Preferred creator type <span className="text-rose-500">*</span>
      </legend>
      <RadioGroup
        className="gap-1.5"
        value={creatorAuthority}
        onValueChange={(val) => setField("creatorAuthority", val)}
        defaultValue="1"
      >
        {items.map((item) => (
          <div
            key={item.value}
            className="relative flex w-full items-center gap-2 rounded-md border border-input p-2.5 shadow-xs outline-none has-data-[state=checked]:border-primary/50 cursor-pointer"
          >
            <RadioGroupItem
              className="order-1 after:absolute after:inset-0 h-3.5 w-3.5 shrink-0"
              id={`${id}-${item.value}`}
              value={item.value}
            />
            <div className="flex grow items-center gap-2.5">
              <span className="shrink-0">{item.icon}</span>
              <div>
                <label
                  htmlFor={`${id}-${item.value}`}
                  className="text-[12px] font-medium text-zinc-800 dark:text-zinc-200 cursor-pointer block"
                >
                  {item.label}
                </label>
                <p className="text-[11px] text-zinc-400">{item.desc}</p>
              </div>
            </div>
          </div>
        ))}
      </RadioGroup>
    </fieldset>
  );
}

"use client";

import { useId } from "react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  BadgeDollarSign,
  Eye,
  Users,
} from "lucide-react";
import { useCampaignStore } from "@/store/campaignStore";

export default function CampaignGoal() {
  const id = useId();
  const campaignGoal = useCampaignStore((state) => state.campaignGoal);
  const setField = useCampaignStore((state) => state.setField);

  const items = [
    {
      value: "1",
      label: "Brand awareness",
      desc: "Maximize views & reach",
      icon: <Eye size={14} className="text-emerald-500" />,
    },
    {
      value: "2",
      label: "Leads / signups",
      desc: "Maximize clicks & registrations",
      icon: <Users size={14} className="text-emerald-500" />,
    },
    {
      value: "3",
      label: "Sales / conversions",
      desc: "Maximize trust & purchases",
      icon: <BadgeDollarSign size={14} className="text-emerald-500" />,
    },
  ];

  return (
    <fieldset className="space-y-2">
      <legend className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300 leading-none mb-2">
        Campaign goal <span className="text-rose-500">*</span>
      </legend>
      <RadioGroup
        className="gap-1.5"
        value={campaignGoal}
        onValueChange={(val) => setField("campaignGoal", val)}
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

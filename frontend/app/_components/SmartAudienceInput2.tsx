"use client";

import { useState } from "react";
import { CirclePlus, Info, Plus } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { INDUSTRY_ONTOLOGY } from "@/data/INDUSTRY_ONTOLOGY";
// import {
//   Select,
//   SelectContent,
//   SelectItem,
//   SelectTrigger,
//   SelectValue,
// } from '@/components/ui/select';

type Industry = "edtech" | "fintech" | "health" | "saas";

const INDUSTRY_DEFAULTS: Record<Industry, string[]> = {
  edtech: [
    "Coding Bootcamp",
    "Placement Prep",
    "University Course",
    "Upskilling",
  ],
  fintech: ["Trading App", "Credit Card", "Crypto Exchange", "Tax Tools"],
  health: ["Weight Loss Program", "Gym Membership", "Supplements", "Yoga App"],
  saas: ["Project Management", "CRM", "AI Tool", "Email Marketing"],
};

export function SmartAudienceInput2() {
  const [selectedIndustry, setSelectedIndustry] = useState<Industry>("edtech");
  const [pitchText, setPitchText] = useState("");

  const handleChipClick = (chipText: string) => {
    setPitchText((prev) => (prev ? `${prev} ${chipText}` : chipText));
  };

  const chips = INDUSTRY_ONTOLOGY.edtech.chips_persona;

  return (
    <div className="*:not-first:mt-4 ">
      {/* Industry Selector */}
      {/* <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">
          Select Industry
        </label>
        <Select
          value={selectedIndustry}
          onValueChange={(value) => setSelectedIndustry(value as Industry)}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="edtech">EdTech</SelectItem>
            <SelectItem value="fintech">FinTech</SelectItem>
            <SelectItem value="health">Health & Wellness</SelectItem>
            <SelectItem value="saas">SaaS</SelectItem>
          </SelectContent>
        </Select>
      </div> */}

      {/* Textarea */}

      <Label htmlFor="pitch">Target Audience <span className="text-destructive">*</span></Label>

      <div>
        <Textarea
          id="pitch"
          value={pitchText}
          onChange={(e) => setPitchText(e.target.value)}
          placeholder="e.g. Final-year college students looking for internships"
        />

        <div className="flex mt-1  items-center text-muted-foreground gap-1">
          <Info size={12} />
          <p className="text-muted-foreground  text-xs">
            Who is your ideal customer?
          </p>
        </div>
      </div>
      {/* Smart Chips */}

      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <Button
            variant="outline"
            key={chip}
            onClick={() => handleChipClick(chip)}
          >
            <CirclePlus size={14} />
            <span>{chip}</span>
          </Button>
        ))}
      </div>
    </div>
  );
}

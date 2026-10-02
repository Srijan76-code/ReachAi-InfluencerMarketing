"use client";

import NormalInputComponent from "@/components/NormalInputComponent";
import RadioCards3 from "@/components/RadioCards3";
import SearchAndSelectInput from "@/components/SearchAndSelectInput";
import { INDUSTRY_ONTOLOGY } from "@/data/INDUSTRY_ONTOLOGY";
import { useCampaignStore } from "@/store/campaignStore";
import {
  Status,
  StatusIndicator,
  StatusLabel,
} from "@/components/kibo-ui/status";

const BrandDetails = () => {
  const brandName = useCampaignStore((state) => state.brandName);
  const industry = useCampaignStore((state) => state.industry);
  const businessModel = useCampaignStore((state) => state.businessModel);
  const productPriceRange = useCampaignStore((state) => state.productPriceRange);
  const setField = useCampaignStore((state) => state.setField);

  function formatCategory(str: string): string {
    if (!str.includes("_")) return str.charAt(0).toUpperCase() + str.slice(1);
    return str.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" & ");
  }

  const industryFrameworks = Object.keys(INDUSTRY_ONTOLOGY).map((k) => ({
    label: formatCategory(k),
    value: k,
  }));

  const businessModels = [
    { label: "B2B", value: "1" },
    { label: "B2C", value: "2" },
    { label: "D2C", value: "3" },
  ];
  const offerPricePoints = [
    { label: "Low (<$50)", value: "1" },
    { label: "Mid ($50–$500)", value: "2" },
    { label: "High ($500+)", value: "3" },
  ];

  return (
    <div className="group relative border border-zinc-200 dark:border-zinc-800 p-6 rounded-xl space-y-5 bg-white dark:bg-[#0c0d0e]">
      <div className="-translate-y-1/2 text-[13px] text-foreground font-medium absolute start-3 top-0 z-10 block px-2 bg-white dark:bg-[#0c0d0e]">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground text-[13px]">Brand Details</StatusLabel>
        </Status>
      </div>
      <NormalInputComponent value={brandName} onChange={(val) => setField("brandName", val)} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <SearchAndSelectInput
          label="Industry"
          frameworks={industryFrameworks}
          value={industry}
          onChange={(val) => setField("industry", val)}
        />
        <RadioCards3
          label="Business model"
          items={businessModels}
          value={businessModel}
          onChange={(val) => setField("businessModel", val)}
        />
      </div>
      <RadioCards3
        label="Product price range"
        sublabel="How much does your product cost per customer?"
        items={offerPricePoints}
        value={productPriceRange}
        onChange={(val) => setField("productPriceRange", val)}
      />
    </div>
  );
};

export default BrandDetails;

import {
  Status,
  StatusIndicator,
  StatusLabel,
} from "@/components/kibo-ui/status";
import NormalInputComponent from "@/components/NormalInputComponent";
import RadioCards3 from "@/components/RadioCards3";
import SearchAndSelectInput from "@/components/SearchAndSelectInput";
import { Badge } from "@/components/ui/badge";

import { INDUSTRY_ONTOLOGY } from "@/data/INDUSTRY_ONTOLOGY";

const BrandDetails = () => {
  function formatCategory(str: string): string {
    if (!str.includes("_")) {
      return str.charAt(0).toUpperCase() + str.slice(1);
    }

    return str
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" & ");
  }
  const industryFrameworks = Object.keys(INDUSTRY_ONTOLOGY);

  const formattedIndustryFrameworks = industryFrameworks.map((framework) => {
    return {
      label: formatCategory(framework),
      value: framework,
    };
  });

  const businessModels = [
    { label: "B2B", value: "1" },
    { label: "B2C", value: "2" },
    { label: "D2C", value: "3" },
  ];
  const offerPricePoints = [
    { label: "Low Ticket(<$50)", value: "1" },
    { label: "Mid Ticket($50-$500)", value: "2" },
    { label: "High Ticket($500+)", value: "3" },
  ];

  return (
    <div className=" group relative border p-8 rounded-xl mt-16 space-y-10">
      <div className="-translate-y-1/2 text-sm text-foreground font-medium absolute start-1 top-0 z-10 block px-2   group-has-disabled:opacity-50">
        <Status status="online">
          <StatusIndicator />
          <StatusLabel className="text-foreground  " >Brand Details</StatusLabel>
        </Status>
      </div>

      <NormalInputComponent />
      <div className=" grid grid-cols-1 lg:grid-cols-2 gap-16 w-full">
        <SearchAndSelectInput
          label="Industry"
          frameworks={formattedIndustryFrameworks}
        />
        <RadioCards3 label="Business Model" items={businessModels} />
      </div>
      <RadioCards3
        label="Product Price Range"
        sublabel="How much does your product cost for a single customer?"
        items={offerPricePoints}
      />
    </div>
  );
};

export default BrandDetails;

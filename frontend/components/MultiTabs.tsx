import { BoxIcon, HouseIcon, PanelsTopLeftIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import TotalBudget from "./TotalBudget";
import RangeSlider from "./RangeSlider";
import NumberOfCreator from "./NumberOfCreator";

export default function MultiTabs() {
  return (
    <Tabs defaultValue="tab-1">
      <ScrollArea>
        <TabsList className="mb-3">
          <TabsTrigger value="tab-1">
            <HouseIcon
              aria-hidden="true"
              className="-ms-0.5 me-1.5 opacity-60"
              size={16}
            />
            Total Campaign Budget
          </TabsTrigger>
          <TabsTrigger className="group" value="tab-2">
            <PanelsTopLeftIcon
              aria-hidden="true"
              className="-ms-0.5 me-1.5 opacity-60"
              size={16}
            />
            Max Price Per Video

          </TabsTrigger>

        </TabsList>
        <ScrollBar orientation="horizontal" />
      </ScrollArea>
      <TabsContent  value="tab-1">
        <div className="space-y-8 mt-8">

        <TotalBudget />
        <NumberOfCreator />
        </div>
      </TabsContent>
      <TabsContent value="tab-2">
        <div className="mt-8 space-y-8">

        <RangeSlider />
        <NumberOfCreator />

        </div>
      </TabsContent>

    </Tabs>
  );
}

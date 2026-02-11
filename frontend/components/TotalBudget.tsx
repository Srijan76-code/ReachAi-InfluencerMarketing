import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function TotalBudget() {
  const id = useId();
  return (
    <div className="*:not-first:mt-2">
      <Label htmlFor={id}>What is your total budget for this campaign?</Label>
      <div className="flex rounded-md shadow-xs">
        <span className="-z-10 inline-flex items-center rounded-s-md border border-input bg-background px-3 text-muted-foreground text-sm">
          $
        </span>
        <Input
          className="-ms-px rounded-s-none shadow-none"
          id={id}
          placeholder="500"
          type="text"
        />
      </div>
    </div>
  );
}

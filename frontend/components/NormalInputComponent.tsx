import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function NormalInputComponent({ value, onChange }: { value?: string, onChange?: (val: string) => void }) {
  const id = useId();
  return (
    <div className="*:not-first:mt-2 ">
      <Label htmlFor={id}>
        Brand Name <span className="text-destructive">*</span>
      </Label>
      <Input id={id} placeholder="CodeBoost" required type="text" value={value || ""} onChange={e => onChange?.(e.target.value)} />
    </div>
  );
}

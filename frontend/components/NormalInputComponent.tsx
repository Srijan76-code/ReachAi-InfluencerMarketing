import { useId } from "react";
import { Input } from "@/components/ui/input";

export default function NormalInputComponent({
  value,
  onChange,
}: {
  value?: string;
  onChange?: (val: string) => void;
}) {
  const id = useId();
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-[12px] font-medium text-zinc-700 dark:text-zinc-300">
        Brand Name <span className="text-rose-500">*</span>
      </label>
      <Input
        id={id}
        placeholder="e.g. DataLaunch"
        required
        type="text"
        value={value || ""}
        onChange={(e) => onChange?.(e.target.value)}
        className="text-[13px]"
      />
    </div>
  );
}

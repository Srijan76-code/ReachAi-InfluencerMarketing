import { useId } from "react";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
    BadgeCheck,
  BadgeDollarSign,
  CircleUserRound,
  Eye,
  GraduationCap,
  Info,
  User,
  UserPlus,
  UserRound,
  Users,
} from "lucide-react";

export default function CreatorAuthority() {
  const id = useId();
  return (
    <fieldset className="space-y-4">
      <legend className="font-medium text-foreground text-sm leading-none">
        Preferred Creator Type <span className="text-destructive">*</span>
                <div className="flex mt-1  items-center text-muted-foreground gap-1">
          <Info size={12} />
          <p className="text-muted-foreground  text-xs">
            What kind of voice should represent your brand?
          </p>
        </div>
      </legend>
      <RadioGroup className="gap-2" defaultValue="1">
        {/* Radio card #1 */}
        <div className="relative flex w-full items-start gap-2 rounded-md border border-input p-4 shadow-xs outline-none has-data-[state=checked]:border-primary/50">
          <RadioGroupItem
            aria-describedby={`${id}-1-description`}
            className="order-1 after:absolute after:inset-0"
            id={`${id}-1`}
            value="1"
          />
          <div className="flex grow items-center gap-3">

            <div className="rounded-full bg-[#121212] p-1.5">
              <User color="#3B82F6" size={20} />
            </div>
            <div className="grid grow gap-2">
              <Label htmlFor={`${id}-1`}>Peer / Relatable</Label>
              <p
                className="text-muted-foreground text-xs"
                id={`${id}-1-description`}
              >
               Just like me (Good for viral reach)
              </p>
            </div>
          </div>
        </div>
        {/* Radio card #2 */}
        <div className="relative flex items-center gap-2 rounded-md border border-input p-4 shadow-xs outline-none has-data-[state=checked]:border-primary/50">
          <RadioGroupItem
            aria-describedby={`${id}-2-description`}
            className="order-1 after:absolute after:inset-0"
            id={`${id}-2`}
            value="2"
          />
          <div className="flex grow items-center gap-3">
            <div className="rounded-full bg-[#121212] p-1.5">
              <GraduationCap color="#3B82F6" size={20} />
            </div>
            <div className="grid grow gap-2">
              <Label htmlFor={`${id}-2`}>Mentor </Label>
              <p
                className="text-muted-foreground text-xs"
                id={`${id}-2-description`}
              >
                Teacher figure (Good for mid-ticket sales)
              </p>
            </div>
          </div>
        </div>

        {/* Radio card #3 */}
        <div className="relative flex items-center gap-2 rounded-md border border-input p-4 shadow-xs outline-none has-data-[state=checked]:border-primary/50">
          <RadioGroupItem
            aria-describedby={`${id}-2-description`}
            className="order-1 after:absolute after:inset-0"
            id={`${id}-3`}
            value="3"
          />
          <div className="flex grow  items-center gap-3">
            <div className="rounded-full bg-[#121212] p-1.5">
              <BadgeCheck color="#3B82F6" size={20} />
            </div>
            <div className="grid grow gap-2">
              <Label htmlFor={`${id}-2`}>Expert </Label>
              <p
                className="text-muted-foreground text-xs"
                id={`${id}-3-description`}
              >
                Industry Leader (Good for high-ticket trust)
              </p>
            </div>
          </div>
        </div>
      </RadioGroup>
    </fieldset>
  );
}

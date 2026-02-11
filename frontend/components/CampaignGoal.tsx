import { useId } from "react";

import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  BadgeDollarSign,
  CircleUserRound,
  Eye,
  Info,
  UserPlus,
  UserRound,
  Users,
} from "lucide-react";

export default function CampaignGoal() {
  const id = useId();
  return (
    <fieldset className="space-y-4">
      <legend className="font-medium text-foreground text-sm leading-none">
        Campaign Goal <span className="text-destructive">*</span>
        <div className="flex mt-1  items-center text-muted-foreground gap-1">
          <Info size={12} />
          <p className="text-muted-foreground  text-xs">
            What is the #1 thing you want to achieve?
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
            <svg
              aria-hidden="true"
              className="shrink-0"
              height={32}
              width={32}
              xmlns="http://www.w3.org/2000/svg"
            >
              <circle cx="16" cy="16" fill="#121212" r="16" />
              <g clipPath="url(#sb-a)">
                <path
                  d="M17.63 25.52c-.506.637-1.533.287-1.545-.526l-.178-11.903h8.003c1.45 0 2.259 1.674 1.357 2.81l-7.637 9.618Z"
                  fill="url(#sb-b)"
                />
                <path
                  d="M17.63 25.52c-.506.637-1.533.287-1.545-.526l-.178-11.903h8.003c1.45 0 2.259 1.674 1.357 2.81l-7.637 9.618Z"
                  fill="url(#sb-c)"
                  fillOpacity=".2"
                />
                <path
                  d="M14.375 6.367c.506-.638 1.532-.289 1.544.525l.078 11.903H8.094c-1.45 0-2.258-1.674-1.357-2.81l7.638-9.618Z"
                  fill="#3ECF8E"
                />
              </g>
              <defs>
                <linearGradient
                  gradientUnits="userSpaceOnUse"
                  id="sb-b"
                  x1="15.907"
                  x2="23.02"
                  y1="15.73"
                  y2="18.713"
                >
                  <stop stopColor="#249361" />
                  <stop offset="1" stopColor="#3ECF8E" />
                </linearGradient>
                <linearGradient
                  gradientUnits="userSpaceOnUse"
                  id="sb-c"
                  x1="12.753"
                  x2="15.997"
                  y1="11.412"
                  y2="17.519"
                >
                  <stop />
                  <stop offset="1" stopOpacity="0" />
                </linearGradient>
                <clipPath id="sb-a">
                  <path d="M6.354 6h19.292v20H6.354z" fill="#fff" />
                </clipPath>
              </defs>
            </svg>

            {/* <Eye size={16} /> */}

            <div className="grid grow gap-2">
              <Label htmlFor={`${id}-1`}>Brand Awareness </Label>
              <p
                className="text-muted-foreground text-xs"
                id={`${id}-1-description`}
              >
                Maximize Views & Reach
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
              <Users color="#3ECF8E" size={20} />
            </div>
            <div className="grid grow gap-2">
              <Label htmlFor={`${id}-2`}>Leads / Signups </Label>
              <p
                className="text-muted-foreground text-xs"
                id={`${id}-2-description`}
              >
                Maximize Clicks & Registrations
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
              <BadgeDollarSign color="#3ECF8E" size={20} />
            </div>
            <div className="grid grow gap-2">
              <Label htmlFor={`${id}-2`}>Sales/Conversions </Label>
              <p
                className="text-muted-foreground text-xs"
                id={`${id}-2-description`}
              >
                Maximize Trust & Purchases
              </p>
            </div>
          </div>
        </div>
      </RadioGroup>
    </fieldset>
  );
}

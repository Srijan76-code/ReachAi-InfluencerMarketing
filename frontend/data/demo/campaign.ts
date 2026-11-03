import type { Influencer } from "@/data/influencerList";
import leadsJson from "./leads.json";
import pitchesJson from "./pitches.json";

// Public demo campaign shown at /demo. Read-only and ships with the frontend,
// so it never depends on the database or a logged-in user.
// Leads come from a saved discovery run (backend/data/influencer_list.py), with
// email addresses removed. Pitches are hand-written samples that follow the
// same rules as the pitch generator (see app/outreach/nodes/validate_creator_pitch.py).

export const demoBrief = {
  brand: {
    name: "DataLaunch",
    website: "datalaunch.io",
    industry: "Edtech",
    businessModel: "B2C",
    priceRange: "High ($500+)",
    outcome: "A 12-week intensive data science bootcamp that guarantees a job or refunds tuition.",
  },
  audience: {
    persona: "Junior developers and fresh CS graduates looking to switch into AI/ML roles.",
    locations: ["India"],
    languages: ["English", "Hindi"],
  },
  campaign: {
    goal: "Leads / signups",
    creatorType: "Mentor",
    platform: "YouTube",
    budget: 5000,
    creatorCount: 5,
  },
};

export const demoLeads = leadsJson as unknown as Influencer[];

export type DemoChannel = "email" | "instagram" | "twitter";

export interface DemoPitch {
  creatorId: string;
  pitchAngle: string;
  email?: { subject: string; body: string };
  instagram?: string;
  twitter?: string;
}

export const demoCollaboration = "Sponsored video";

export const demoPitches = pitchesJson as DemoPitch[];

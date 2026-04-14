export type CampaignStatus = "draft" | "active" | "in_progress"

export interface Campaign {
  id: string
  name: string
  logoUrl: string
  step: string
  status: CampaignStatus
  createdAt: string // ISO date
}
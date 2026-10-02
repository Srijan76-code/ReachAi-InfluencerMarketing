import ExcelJS from "exceljs";
import { Influencer } from "@/data/influencerList";

export interface ExportConfig {
  type: "raw" | "outreach";
  format: "csv" | "excel";
  template: "generic" | "instantly" | "smartlead";
  removeNoEmail: boolean;
  includeContext: boolean;
}

// Dummy LLM Pipeline mock function for enrichment as requested
function enrichInfluencer(inf: Influencer) {
  const first_name = inf.title.split(" ")[0] || "Creator";
  const topicMatch =
    inf.rich_context
      .slice(0, 20)
      .replace(/[^a-zA-Z ]/g, "")
      .trim() || "Tech";

  return {
    ...inf,
    first_name,
    personalized_line: `Really liked your content around ${topicMatch}`,
    pitch:
      "We're running a campaign targeting developers and your audience aligns well.",
    cta: "Would you be open to a collaboration?",
  };
}

export const processExport = async (
  influencers: Influencer[],
  config: ExportConfig,
) => {
  // STEP 1: FILTER
  let pool = influencers;
  if (config.removeNoEmail) {
    pool = pool.filter((i) => !!i.socials?.email);
  }

  // Handle empty state gracefully
  if (pool.length === 0) {
    alert(
      "No influencers available to export with the current settings (e.g., missing emails).",
    );
    return;
  }

  // STEP 2: ENRICH
  const enriched = pool.map(enrichInfluencer);

  // STEP 3 & 4: TRANSFORM & MAP
  let data: any[] = [];

  if (config.type === "raw") {
    data = enriched; // Full flat nested context
  } else {
    // Outreach Mode
    data = enriched.map((inf) => {
      let row: Record<string, any> = {};
      const email = inf.socials?.email || "";

      if (config.template === "instantly" || config.template === "smartlead") {
        row = {
          email,
          first_name: inf.first_name,
          icebreaker: inf.personalized_line,
          pitch: inf.pitch,
          cta: inf.cta,
        };
      } else {
        // Generic matches InfluencerDetailSheet perfectly
        row = {
          email,
          first_name: inf.first_name,
          icebreaker: inf.personalized_line,
          pitch: inf.pitch,
          cta: inf.cta,
          "Channel Name": inf.title,
          Country: inf.country,
          "Deal Status": inf.deal_status,
          Email: email,
          Instagram: inf.socials?.instagram || "",
          Twitter: inf.socials?.twitter || "",
          "Brand Fit (%)": inf.score_breakdown?.strategy_score,
          "Health (%)": inf.score_breakdown?.health_score,
          Subscribers: inf.subscribers,
          "Avg Views": inf.metrics?.avg_views,
          "Engagement (%)": inf.metrics?.engagement_rate,
          "Trust Score": inf.metrics?.trust_score,
          "Fair Value ($)": inf.valuation,
          "Yield (Clicks)": inf.metrics?.forecast
            .split(" ")[0]
            .replace("~", ""),
          "AI Reasoning": inf.llm_reasoning,
        };
      }

      // STEP 5: CONTEXT FIELDS (Only append if outreach modes are active)
      if (config.includeContext && config.template !== "generic") {
        row.followers = inf.subscribers;
        row.avg_views = inf.metrics?.avg_views;
        row.engagement_rate = inf.metrics?.engagement_rate;
        row.trust_score = inf.metrics?.trust_score;
        row.brand_fit = inf.relevance_score;
        row.fair_value = inf.valuation;
      }

      return row;
    });
  }

  // STEP 6: FORMAT & DOWNLOAD
  if (config.format === "csv") {
    downloadCSV(data);
  } else if (config.format === "excel") {
    await downloadExcel(data);
  }
};

const downloadCSV = (data: any[], filename = "campaign-export.csv") => {
  if (!data.length) return;
  const keys = Object.keys(data[0]);
  const replacer = (_key: any, value: any) => (value === null ? "" : value);

  const csv = [
    keys.join(","),
    ...data.map((row) =>
      keys
        .map((fieldName) => {
          let val = row[fieldName];
          // Handle strictly nested objects dynamically in RAW mode to avoid [Object object]
          if (typeof val === "object" && val !== null) {
            return JSON.stringify(JSON.stringify(val, replacer));
          }
          return JSON.stringify(val, replacer);
        })
        .join(","),
    ),
  ].join("\r\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  triggerDownload(blob, filename);
};

const downloadExcel = async (data: any[], filename = "campaign-export.xlsx") => {
  if (!data.length) return;

  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet("Pitches");

  const keys = Object.keys(data[0]);

  // Format spreadsheet headers
  worksheet.columns = keys.map((key) => ({
    header: key,
    key: key,
    width: Math.max(key.length + 5, 20),
  }));

  // Build row by row, sanitizing heavy nested objects
  data.forEach((row) => {
    let flatRow: Record<string, any> = {};
    keys.forEach((k) => {
      flatRow[k] =
        typeof row[k] === "object" && row[k] !== null
          ? JSON.stringify(row[k])
          : row[k];
    });
    worksheet.addRow(flatRow);
  });

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  triggerDownload(blob, filename);
};

export interface PitchExportItem {
  creator_id: string;
  creator_name: string;
  email: string;
  instagram: string;
  twitter: string;
  country: string;
  subject: string;
  email_body: string;
  instagram_pitch: string;
  twitter_pitch: string;
  pitch_angle: string;
  status: string;
}

export interface PitchExportConfig {
  template: "instantly" | "smartlead" | "generic";
  format: "csv" | "excel";
  removeNoEmail: boolean;
}

export const processPitchesExport = async (
  pitches: PitchExportItem[],
  config: PitchExportConfig,
  campaignId: string
) => {
  let pool = pitches;
  if (config.removeNoEmail) {
    pool = pool.filter((p) => !!p.email);
  }

  if (pool.length === 0) {
    alert("No pitches available to export with current settings (e.g. missing emails).");
    return;
  }

  let data: any[] = [];
  if (config.template === "instantly") {
    data = pool.map((p) => {
      const firstName = p.creator_name.split(" ")[0] || "there";
      return {
        email: p.email,
        first_name: firstName,
        company: p.creator_name,
        subject: p.subject,
        body: p.email_body,
        custom_variable_1: p.pitch_angle,
        instagram: p.instagram,
        twitter: p.twitter,
      };
    });
  } else if (config.template === "smartlead") {
    data = pool.map((p) => {
      const firstName = p.creator_name.split(" ")[0] || "there";
      return {
        email: p.email,
        first_name: firstName,
        company_name: p.creator_name,
        subject: p.subject,
        email_body: p.email_body,
        custom_pitch: p.pitch_angle,
        social_instagram: p.instagram,
        social_twitter: p.twitter,
      };
    });
  } else {
    data = pool.map((p) => ({
      "Creator Name": p.creator_name,
      Email: p.email,
      Country: p.country,
      "Subject Line": p.subject,
      "Email Pitch": p.email_body,
      "Instagram Pitch": p.instagram_pitch,
      "Twitter Pitch": p.twitter_pitch,
      "Pitch Angle": p.pitch_angle,
      Instagram: p.instagram,
      Twitter: p.twitter,
      Status: p.status,
    }));
  }

  const filename = `outreach-pitches-${campaignId}.${config.format === "excel" ? "xlsx" : "csv"}`;
  if (config.format === "csv") {
    downloadCSV(data, filename);
  } else {
    await downloadExcel(data, filename);
  }
};

const triggerDownload = (blob: Blob, filename: string) => {
  const link = document.createElement("a");
  if (link.download !== undefined) {
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
};

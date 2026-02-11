<div align="center">

# Reach AI

### Agentic Influencer Marketing Platform

_From deep lead discovery to hyper-personalized outreach — fully automated._

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_Framework-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Next.js](https://img.shields.io/badge/Next.js_16-React_19-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![Gemini](https://img.shields.io/badge/Google_Gemini-2.5_Flash-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)

</div>

---

## Overview

**Reach AI** is an end-to-end agentic platform that automates the influencer marketing funnel. It replaces manual spreadsheet scouting with an LangGraph pipeline that discovers, qualifies, and ranks influencers (like YouTube creators, Instagram influencers, etc.) — using real-time metrics, semantic analysis, brand-fit & safety analysis.

| What it replaces           | What Reach AI does                           |
| -------------------------- | -------------------------------------------- |
| Manual keyword searching   | AI-generated strategic search queries        |
| Spreadsheet-based vetting  | Automated scoring based on brand-fit analysis|
| Generic outreach templates | Hyper-personalized, context-aware drafts     |
| Gut-feel creator selection | Hybrid semantic + LLM reranking              |

---

## Core Features

### 🔍 Deep Lead Discovery

Uses Gemini-powered keyword expansion and YouTube Data API search to surface creators you'd never find manually. The system generates **topic**, **pain-point**, **cultural**, and **format** keyword variants from your campaign brief.

### 📊 Performance Intelligence

Calculates "Moneyball" metrics beyond vanity numbers:

| Metric                | Description                                         |
| --------------------- | --------------------------------------------------- |
| **Volatility Score**  | Std deviation / mean views — measures consistency   |
| **Trust Score**       | Comment-to-like ratio — gauges authentic engagement |
| **Reliability Grade** | High / Medium / Low based on volatility thresholds  |
| **Estimated CPM**     | Industry × geo-tier adjusted cost-per-mille         |
| **Channel Valuation** | Fair sponsorship price = (avg views / 1000) × CPM   |
| **Engagement Rate**   | (Likes + Comments) / Total Views                    |

### 🤖 Agentic Reranking

A batched, concurrent LLM judge that grades every candidate on **brand fit** and **content relevance** — completely independent of metrics. This ensures the final list reflects strategic alignment, not just big numbers.

### 🧮 Fusion Scoring

Final score = `(LLM Relevance × 0.60) + (Health Score × 0.40)`, with risk penalties applied per reliability grade. Outputs a deal status: **Strong Buy**, **Consider**, or **Avoid**.

### 🌓 Light & Dark Mode

A premium, dashboard-centric frontend built with Next.js 16, featuring system-aware theme switching via `next-themes` and polished UI with Radix primitives.

---

## System Architecture

The backend is a **linear LangGraph StateGraph** with 8 nodes, each with automatic retry policies and in-memory caching.

```mermaid
graph LR
    START((START)) --> A[Campaign<br/>Understanding]
    A --> B[Keyword<br/>Generator]
    B --> C[YouTube<br/>Search Gate]
    C --> D[Subscriber<br/>Filter]
    D --> E[Channel<br/>Enrichment]
    E --> F[Semantic<br/>Processor]
    F --> G[LLM<br/>Reranker]
    G --> H[Final<br/>Scoring]
    H --> END((END))

    style START fill:#10b981,stroke:#059669,color:#fff
    style END fill:#ef4444,stroke:#dc2626,color:#fff
    style A fill:#6366f1,stroke:#4f46e5,color:#fff
    style B fill:#6366f1,stroke:#4f46e5,color:#fff
    style C fill:#f59e0b,stroke:#d97706,color:#fff
    style D fill:#f59e0b,stroke:#d97706,color:#fff
    style E fill:#f59e0b,stroke:#d97706,color:#fff
    style F fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style G fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style H fill:#ec4899,stroke:#db2777,color:#fff
```

### Node Breakdown

| #   | Node                     | Type    | Purpose                                                                           |
| --- | ------------------------ | ------- | --------------------------------------------------------------------------------- |
| 1   | `campaign_understanding` | 🧠 LLM  | Expands brand brief into strategic topics, formats, pain points, and safety level |
| 2   | `keyword_generator`      | 🧠 LLM  | Translates strategy into 4 categories of native YouTube search queries            |
| 3   | `youtube_search_gate`    | 🌐 API  | Async-concurrent YouTube search across top 10 keywords (semaphore-limited)        |
| 4   | `subscriber_filter`      | 🌐 API  | Batch filters by subscriber count, country, and minimum content health            |
| 5   | `channel_enrichment`     | 🌐 API  | Fetches recent videos, calculates metrics, validates health, extracts socials     |
| 6   | `semantic_processor`     | 🧮 Math | Hybrid BM25 + Gemini embedding cosine similarity (70/30 vector/keyword blend)     |
| 7   | `reranker_node`          | 🧠 LLM  | Batched async LLM judge scoring brand-fit relevance (0–100)                       |
| 8   | `final_scoring_node`     | 🧮 Math | Weighted fusion of LLM score + health metrics with risk penalty                   |

### State Schema

The pipeline uses a progressive enrichment pattern — each node extends the channel data model:

```
ChannelData → EnrichedChannel → AnalyzedChannel → RankedChannel → FinalScoredChannel
```

All state is managed via `Pydantic` models and `TypedDict` classes in `backend/my_agent/utils/state.py`.

---

## Project Structure

```
ReachAi-InfluencerMarketing/
│
├── backend/
│   ├── main.py                  # FastAPI entry point (WIP)
│   ├── requirements.txt         # Python dependencies
│   ├── langgraph.json           # LangGraph deployment config
│   │
│   ├── core/
│   │   ├── model.py             # Gemini 2.5 Flash initialization
│   │   └── get_youtube_client.py
│   │
│   ├── my_agent/
│   │   ├── agent.py             # Graph definition & compilation
│   │   ├── utils/
│   │   │   └── state.py         # Pydantic state schema
│   │   └── nodes/
│   │       ├── campaign_understanding.py
│   │       ├── keyword_generator.py
│   │       ├── youtube_search_gate.py
│   │       ├── subscriber_filter.py
│   │       ├── channel_enrichment.py
│   │       ├── semantic_processor.py
│   │       ├── reranker_node.py
│   │       └── final_scoring_node.py
│   │
│   ├── api/
│   │   └── routes.py
│   └── scripts/
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           # Root layout with ThemeProvider
│   │   ├── page.tsx             # Dashboard — BrandDetails, Campaign, Audience, Constraints
│   │   ├── globals.css
│   │   └── _components/         # Page-level form sections
│   │
│   ├── components/
│   │   ├── ui/                  # Radix-based primitives (Badge, Button, Dialog, etc.)
│   │   ├── kibo-ui/             # Status indicators
│   │   ├── theme-provider.tsx   # next-themes wrapper
│   │   ├── CampaignGoal.tsx
│   │   ├── CreatorAuthority.tsx
│   │   ├── SearchAndSelectInput.tsx
│   │   ├── RangeSlider.tsx
│   │   └── ...
│   │
│   ├── data/                    # Static ontologies & datasets
│   ├── hooks/                   # Custom React hooks
│   ├── lib/                     # Utility functions
│   └── public/                  # Static assets
│
└── .gitignore
```

---

## Installation

### Prerequisites

- **Python** 3.11+
- **Node.js** 20+
- **npm** 10+
- A [Google Cloud](https://console.cloud.google.com/) project with YouTube Data API v3 enabled
- A [Google AI Studio](https://aistudio.google.com/) API key for Gemini

### Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (see section below)
cp .env.example .env
```

### Frontend Setup

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:3000`.

---

## API Configuration

Create a `.env` file in the `backend/` directory with the following keys:

| Variable          | Description                               | Required |
| ----------------- | ----------------------------------------- | -------- |
| `GOOGLE_API_KEY`  | Google AI Studio key for Gemini 2.5 Flash | ✅       |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key                   | ✅       |
| `APIFY_API_TOKEN` | Apify client token (for social scraping)  | Optional |

```env
GOOGLE_API_KEY=your_gemini_api_key
YOUTUBE_API_KEY=your_youtube_data_api_key
APIFY_API_TOKEN=your_apify_token
```

> [!IMPORTANT]
> The YouTube Data API has a daily quota of **10,000 units**. Each search query costs ~100 units. Running the full pipeline with 10 keywords consumes ~1,000 units from search alone, plus additional units for channel and video detail fetches. Monitor your usage in the [Google Cloud Console](https://console.cloud.google.com/apis/dashboard).

---

## Tech Stack

| Layer             | Technology              | Role                                                           |
| ----------------- | ----------------------- | -------------------------------------------------------------- |
| **Orchestration** | LangGraph               | Agentic StateGraph with retry policies, caching, checkpointing |
| **AI / LLM**      | Google Gemini 2.5 Flash | Campaign strategy, keyword gen, brand-fit reranking            |
| **Embeddings**    | Gemini Embedding 001    | Semantic similarity for channel matching                       |
| **Search**        | BM25Okapi (rank-bm25)   | Keyword relevance scoring                                      |
| **Data**          | YouTube Data API v3     | Channel stats, video metadata, playlist data                   |
| **State**         | Pydantic + TypedDict    | Strongly-typed pipeline state management                       |
| **Frontend**      | Next.js 16 / React 19   | Dashboard UI with server components                            |
| **Styling**       | Tailwind CSS v4         | Utility-first responsive design                                |
| **Animation**     | Framer Motion           | Micro-interactions and transitions                             |
| **Theming**       | next-themes             | System-aware light/dark mode switching                         |


---

## Roadmap

- [ ] **FastAPI Integration** — Expose the LangGraph pipeline via REST endpoints
- [ ] **Agentic Outreach Subgraph** — LangGraph-driven email drafting with creator-specific personalization
- [ ] **Human-in-the-Loop Review Gate** — Interrupt-based approval flow before outreach goes live
- [ ] **Results Dashboard** — Visual display of ranked creators with score breakdowns
- [ ] **Multi-Platform Support** — Extend beyond YouTube to Instagram, TikTok, and X
- [ ] **Campaign History** — Persistent storage with PostgreSQL for past runs and A/B comparison
- [ ] **Export & CRM Sync** — CSV/JSON export and direct CRM integration (HubSpot, Salesforce)
- [ ] **Real-Time Streaming** — LangGraph event streaming for live pipeline progress in the UI

---

<div align="center">

Built by [Srijan Patel](https://github.com/Srijan76-code)

</div>

<div align="center">
  <br>
  <h1>REACH AI : End-to-End Influencer Marketing Automation</h1>
  <!-- <p><strong>End-to-End Influencer Marketing Automation</strong></p> -->
  <!-- <hr width="72%"> -->
  <p align="right">
    From deep lead discovery to hyper-personalized outreach -- Fully automated.
  </p>
  <br>
  <a href="#-project-overview">Project Overview</a> ✦
  <a href="#-core-features">Key Features</a> ✦
  <a href="#-traditional-platforms-vs-reach-ai">Comparison</a> ✦
  <a href="#-system-architecture">Architecture</a> ✦
  <a href="#-project-structure">Structure</a> ✦
  <a href="#-installation">Installation</a> ✦
  <a href="#-api-configuration">API</a> ✦
  <a href="#-tech-stack">Tech Stack</a>
  <br>
</div>

<hr>

## ◈ Project Overview

**Reach AI** is an end-to-end agentic platform that automates the influencer marketing funnel. It replaces manual spreadsheet scouting with an intelligent LangGraph pipeline that discovers, qualifies, and ranks influencers — using real-time metrics, semantic analysis, and brand-fit & safety analysis.

The platform understands your **actual campaign context** — your brand's industry, price point, target persona, and goals — and uses that understanding to find creators who are a genuine strategic fit, not just names that match a hashtag.


**Why Reach AI**
>
> I built Reach AI after seeing how difficult influencer discovery was while building Haven, a college dating app. Our first organic campaign reached 17k+ views in a week, but finding the right creators still required hours of manual scrolling and guesswork. Reach AI turns that process into a campaign-aware, measurable workflow that can run cheaply at scale.

### Engineering Outcomes

>
> The first working version cost approximately **$5 per run** and took **4+ minutes**. After tracing the workflow in LangSmith, I moved expensive work toward concurrent batched processing, cached repeated work, and removed unnecessary sequential model calls.   This helped me do :
>
> - **99% lower AI inference cost:** approximately **$5 to $0.04 per run**.
> - **60%+ lower pipeline latency:** approximately **4+ minutes to 1–2 minutes**.
> - **Quality validated and improved:** outperformed Aha (market leader) and the previous version on the same product brief, then checked across different campaign briefs, including edtech, which also surfaced stronger creator matches.


### Tech Stack

`Next.js` ·  `TypeScript` ·  `Python` · `FastAPI` · `LangGraph` · `Inngest` · `Gemini AI` · `PostgreSQL` · `LangSmith` · `Zustand`

<br>

## ◈ Core Features

### Core Capabilities

| <kbd>01</kbd> Deep Campaign-Aware Discovery                                                                                                                                  | <kbd>02</kbd> Brand-Fit Ranking                                                                                                                 |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------- |
| Reads your full campaign brief and generates dozens of strategic search queries across niches, audience struggles, and formats to surface creators manual searches miss. | Evaluates each creator on actual content relevance to your brand, independent of metrics, with a written reasoning explaining exactly why they're a fit. |

| <kbd>03</kbd> Performance Intelligence                                                                                                                                 | <kbd>04</kbd> Real-Time Risk Detection                                                                                                                        |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------- |
| Metrics that matter: Fair valuation, estimated CPM, trust scores, consistency, and expected link clicks per video based on industry-specific benchmarks. | Automatically filters out dead channels, zombie engagement, geo-mismatches, and channels not meeting your view thresholds. |

### Platform and Reliability Features

| <kbd>05</kbd> Durable Background Workflows | <kbd>06</kbd> Resumable AI Pipelines |
| :--- | :--- |
| Inngest runs campaign jobs asynchronously with event-driven execution, while LangGraph retry policies recover from transient failures. | PostgreSQL-backed LangGraph checkpoints preserve workflow state by campaign thread, making long-running runs inspectable and resumable. |

| <kbd>07</kbd> Live Progress and Reconciliation | <kbd>08</kbd> Cost and Latency Optimization |
| :--- | :--- |
| Signed Inngest Realtime subscriptions stream stage and completion events to the campaign UI, while Zustand reconciles state with the backend. | Batched processing, selective model usage, and caching reduce inference cost and unnecessary sequential work. |

<br>

## ◈ Traditional Platforms vs Reach AI

| Domain             | Traditional Platforms (Modash, Upfluence)                             | Reach AI                                     |
| :----------------- | :------------------------------------------------ | :------------------------------------------- |
| **Discovery**      | Browse static database filtered by tags, category | AI generates strategic queries to find what creators *actually* talk about     |
| **Evaluation**     | Surface-level: followers, avg likes              | Deep: fair-price valuation, consistency, expected ROI per video  |
| **Brand Safety**   | Little to no safety screening        | Real-time risk detection (flags dead channels, fake engagement)          |
| **Ranking**        | Hidden algorithm or basic sorting by follower count  | Every creator has a written explanation of their strategic relevance |
| **Pricing**        | Generic rate cards or no pricing data  | Per-creator valuation adjusted for industry, geo, and actual performance |

<br>

## ◈ System Architecture

### Campaign Generation Workflow

The user submits a campaign, Inngest runs the job in the background, LangGraph evaluates creators, and the frontend receives live progress through a signed, run-scoped Inngest Realtime subscription.

```mermaid
sequenceDiagram
  autonumber
  actor User
  participant UI as Next.js UI
  participant API as FastAPI
  participant DB as PostgreSQL
  participant Inngest
  participant Graph as LangGraph Agent
  participant YouTube as YouTube API
  participant Gemini

  User->>UI: Submit campaign brief
  UI->>API: POST /api/campaigns/{id}/generate
  API->>DB: Save brief and set status PENDING
  API->>Inngest: Send campaign/run event
  API-->>UI: Return campaign and run IDs
  UI->>API: Request signed Realtime token for run_id
  API-->>UI: Return signed token
  UI->>Inngest: Subscribe to campaign:{run_id} / status

  Inngest->>Graph: Start campaign workflow
  loop Each LangGraph node
    Graph->>Graph: Run current node
    opt Search or enrichment node
      Graph->>YouTube: Search channels and fetch metrics
      YouTube-->>Graph: Return creator data
    end
    opt Analysis or ranking node
      Graph->>Gemini: Analyze fit, safety, and performance
      Gemini-->>Graph: Return AI evaluation
    end
    Graph->>DB: Save current stage and progress
    Graph-->>Inngest: Publish campaign/stage event
    Inngest-->>UI: Deliver status update over Realtime
  end

  Graph->>DB: Save ranked leads and set COMPLETED
  Inngest-->>UI: Deliver completed event
  UI->>API: Reconcile state and fetch completed leads
  UI-->>User: Display ranked influencer leads
```

**Important:** Inngest handles both background execution and live progress delivery. The backend publishes run-scoped `campaign/stage` events, and the frontend subscribes to the `campaign:{run_id}` topic with the `status` event using a signed token. PostgreSQL remains the durable source of truth used for reconciliation and loading completed leads.

### LangGraph Processing Pipeline

The backend uses a **linear LangGraph StateGraph** with 9 nodes, automatic retry policies, PostgreSQL checkpointing, and in-memory caching.

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
    H --> I[LLM<br/>Reasoning]
    I --> END((END))

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
    style I fill:#ec4899,stroke:#db2777,color:#fff
```

<br>

## ◈ Project Structure

```text
  ReachAi-InfluencerMarketing/
  ├── backend/
  │   ├── app/
  │   │   ├── api/routes/           — Campaign, lead, and Realtime API routes
  │   │   ├── inngest/              — Inngest client and background functions
  │   │   ├── my_agent/             — LangGraph nodes and agent state
  │   │   ├── models/               — SQLAlchemy database models
  │   │   └── workflow/             — Graph runtime, checkpoints, and stage events
  │   ├── alembic/                  — Database migrations
  │   ├── requirements.txt
  │   └── Makefile
  ├── frontend/
  │   ├── app/                      — Next.js pages, campaign flow, and API routes
  │   ├── components/               — Reusable UI components
  │   ├── store/                    — Zustand campaign state and reconciliation
  │   └── package.json
  └── README.md
```

<br>

## ◈ Installation

**Prerequisites:** Python 3.11+, Node.js 20+, PostgreSQL, a Google Cloud project with YouTube Data API v3 enabled, and a Google AI Studio key.

<details>
<summary><b>Quick Setup</b></summary>

<br>

**1. Backend Setup**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
touch .env
uvicorn app.main:app --reload
```

**2. Inngest Dev Server**

In a second terminal:

```bash
cd backend
npx inngest-cli@latest dev -u http://localhost:8000/api/inngest
```

**3. Frontend Setup**

```bash
cd frontend
npm install
npm run dev
```

</details>

<br>

## ◈ API Configuration

Create a `.env` file in the `backend/` directory:

```dotenv
GOOGLE_API_KEY=your_google_ai_studio_key
YOUTUBE_API_KEY=your_youtube_data_api_key
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/reachai
LANGGRAPH_CHECKPOINTER_URL=postgresql://postgres:postgres@localhost:5432/reachai
INNGEST_DEV=1
INNGEST_APP_ID=reach-ai
CLERK_JWKS_URL=your_clerk_jwks_url
```

| Variable          | Description                               | Required |
| ----------------- | ----------------------------------------- | -------- |
| `GOOGLE_API_KEY`  | Google AI Studio key for Gemini 2.5 Flash | ✅       |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key                   | ✅       |
| `DATABASE_URL`    | PostgreSQL connection URL                 | ✅       |
| `INNGEST_DEV`     | Enables local Inngest signing defaults    | Local    |
| `APIFY_API_TOKEN` | Apify client token (for social scraping)  | Optional |

> [!IMPORTANT]
> The YouTube Data API has a daily quota of **10,000 units**. Each search query costs ~100 units. Running the full pipeline with 10 keywords consumes ~1,000 units from search alone, plus additional units for channel and video detail fetches. Monitor your usage in the Google Cloud Console.

<br>

---

<div align="center">
  <i>Built by <a href="https://github.com/Srijan76-code">Srijan Patel</a></i>
</div>

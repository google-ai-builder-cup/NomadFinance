# NomadFinance

AI-Powered Financial Protection for Migrant Workers

Google Cloud AI Builder Cup 2026

BFSI Track — Intelligent Risk, Fraud & Financial Experiences

Project Design Document v1.0

Date: September 20, 2026

Team Size: 3 | Prototype Deadline: October 18, 2026

## 1. Project Overview

### 1.1 What We're Building

NomadFinance is an AI-powered financial protection platform for the world's 280 million migrant workers. Built on Google Cloud with Gemini as its intelligence layer, it acts as a comprehensive financial protection agent — reading contracts workers cannot read, finding them the cheapest way to send money home, protecting them from exploitation through crowdsourced intelligence, and building them a portable financial identity that follows them across borders.

### 1.2 Problem Statement

280 million migrant workers globally send $650 billion in remittances annually, losing $41 billion to fees — many of them the poorest workers in the world. They face a complete financial protection gap:

- Remittance opacity — hidden costs in exchange rate markups and layered fees
- Contracts in foreign languages they cannot read, resulting in signed exploitation
- Wage theft, illegal deductions, and unlicensed recruitment agencies
- Zero financial identity — years of work leaves no credit history anywhere
- Isolation from support networks and no way to warn other workers about bad actors

### 1.3 Target Users

- Primary: Migrant workers across JAPAC corridors (Singapore, South Korea, Malaysia, Japan, Hong Kong, Australia as host countries)
- Secondary: NGOs, embassies, labor authorities, and MFIs supporting migrant populations

### 1.4 SDG Alignment

- SDG 8: Decent Work and Economic Growth
- SDG 10: Reduced Inequalities (specifically 10.c on remittance costs)
- SDG 16: Peace, Justice, and Strong Institutions

### 1.5 Competition Context

Google Cloud AI Builder Cup 2026 — JAPAC-wide hackathon. Prototype deadline October 18, 2026. Top 50 teams advance; finalists present at Grand Finale in Singapore on December 4, 2026. Prize pool: USD 30,000. Judging: Technical Merit & Gen AI (40%), Problem Alignment & Impact (25%), Innovation & Creativity (25%), UX & Solution Design (10%).

## 2. Current Pillars (POC Scope for October 18)

NomadFinance is built around 4 interconnected pillars. Each addresses a specific dimension of migrant worker financial vulnerability, and together they form an ecosystem where data from one pillar strengthens the others.

### Pillar 1: Remittance X-Ray Engine

Category: Data Product + Financial Intelligence

Real-time comparison of ALL available transfer options across major corridors, exposing hidden fees and exchange rate markups. This is data journalism plus financial intelligence, not a chatbot.

#### Features

- Real-time comparison of all available transfer options (Wise, Western Union, Remitly, local operators) across 6 core JAPAC corridors
- True total cost breakdown — flat fee + exchange rate markup vs mid-market rate + receiving fee + delivery time cost
- Historical price charts showing rate trends (e.g., 'Send on Wednesday, rates are consistently 0.3% better')
- Savings calculator: 'If you'd used [best option] for the last 12 months, you'd have saved $X'
- Gemini-generated personalized recommendation in the worker's native language
- Every transfer logged automatically feeds Financial Identity Builder

### Pillar 2: Contract Shield

Category: Document Intelligence + Legal Reasoning

The technical showcase. Upload any employment or financial document in any language and receive a full legal analysis in the worker's own language.

#### Features

- Upload any employment/financial document in any language — PDF, image, or phone camera capture
- Gemini translates the full document into the worker's native language
- AI flags concerning clauses (uncompensated overtime, illegal deductions, termination penalties)
- Side-by-side comparison — contract terms vs labor law minimums in that country
- Generates a 'Contract Health Report' with a risk score (Safe / Caution / Danger)
- If violations found, auto-generates a formal complaint template addressed to the appropriate labor authority

### Pillar 3: Exploitation Radar (Crowdsourced)

Category: Community Intelligence + Pattern Detection

A crowdsourced database of bad actors, powered by Gemini for validation and pattern detection. This is the network effect layer — every report makes the system smarter.

#### Features

- Workers report bad actors: money transfer operators with hidden fees, recruitment agencies charging illegal fees, employers violating contracts
- Gemini validates and categorizes reports (spam detection, duplicate detection, violation classification)
- Community-verified ratings for operators and agencies in each corridor
- Interactive heat map of exploitation patterns by region and corridor (react-leaflet + OpenStreetMap)
- Push notification alert system: '3 workers in your corridor reported [operator] adding hidden fees this month'

### Pillar 4: Financial Identity Builder

Category: Portable Credit Profile + Longitudinal Tracking

The long-term value story. Workers who migrate improve their skills and income but return home invisible to financial systems. This makes them visible.

#### Features

- Workers log their financial activity across borders — income, transfers, savings, bills paid
- Gemini Vision extracts structured data from uploaded bill photos and payslips
- System builds a portable financial profile over time (income stability, savings rate, remittance consistency, bill payment reliability)
- Gemini synthesizes longitudinal behavior into a narrative Financial Identity Report
- Exportable PDF that MFIs and banks in home countries can use for alternative credit scoring

## 3. Future / Scalable Pillars (Post-POC Roadmap)

These pillars are documented for the pitch deck's roadmap slides. They demonstrate future scale and enterprise potential without adding scope to the 4-week POC build.

### 3.1 Pre-Departure Financial Coach

- Multi-turn conversational Gemini agent that interviews a worker before they leave
- Assesses financial preparedness (salary, remittance obligations, debts, savings)
- Generates personalized pre-departure plan for the first 90 days in host country

### 3.2 Wage Theft Evidence Builder

- Workers upload fragmented evidence (WhatsApp messages, schedules, partial payslips)
- Gemini constructs a coherent timeline and formal wage claim
- Auto-generates filing instructions for local labor authorities

### 3.3 Real-Time Scam Message Analyzer

- Paste suspicious message or upload screenshot
- Gemini classifies scam type, manipulation tactics, and risk level
- Explains the psychology behind each scam in simple language

### 3.4 Multilingual Financial Glossary

- Tap any term in a contract for contextual legal explanation
- Country-specific interpretation (Singapore CPF vs Malaysia EPF vs Korean NPS)
- Compares stated amount against legal minimum

### 3.5 Government / NGO Partnership APIs

- Integration with ILO, IOM, Migrant Forum Asia
- Automated complaint filing with national labor authorities
- Anonymized aggregate data for policy makers

### 3.6 WhatsApp / Telegram Bot Interface

- Serve workers without smartphone apps
- Voice-first interface for low-literacy users

### 3.7 Cross-Corridor Analytics on BigQuery

- Pipe anonymized data from Firestore to BigQuery
- Large-scale exploitation pattern analytics for policymakers
- Predictive modeling for emerging exploitation patterns

## 4. Technology Stack

Complete stack, mapped to Google Cloud services where possible. Total cost through POC and evaluation: ₹0.

### 4.1 Google Cloud Platform Services

| Service | Purpose | Free Tier |
|---|---|---|
| Firebase Authentication | Google + phone OTP sign-in | 50K MAU |
| Cloud Firestore | Primary NoSQL DB | 1 GiB, 50K reads/day, 20K writes/day |
| Cloud Storage for Firebase | Uploaded contracts, PDFs | 5 GB, 1 GB/day download |
| Cloud Run | FastAPI backend container | 2M requests/month |
| Cloud Scheduler | Cron jobs (rate refresh, radar aggregation) | 3 jobs free |
| Cloud Build | CI/CD from GitHub → Cloud Run | 120 build-min/day |
| Firebase Hosting | React PWA hosting + CDN + SSL | 10 GB, 360 MB/day |
| Firebase App Check | Anti-abuse for Radar submissions | Free |
| Firebase Cloud Messaging | Push notifications for Radar alerts | Free unlimited |
| Cloud Logging | Structured observability | 50 GiB/month |
| Secret Manager | API keys, credentials vault | 6 secret versions |
| Google Artifact Registry | Docker image storage | 0.5 GB free |
| Firebase Analytics | Usage tracking | Free unlimited |
| Firestore Vector Search | Semantic clustering of reports | Included |

### 4.2 Google AI (Gemini Models)

| Model | Primary Use | Free Tier |
|---|---|---|
| Gemini 2.5 Flash | Contract legal reasoning, complaint generation, financial narrative | 500 RPD, 250K TPM |
| Gemini 1.5 Flash | Document extraction (Vision), transaction categorization | 1,500 RPD, 1M TPM |
| Gemini 2.0 Flash-Lite | Translations, radar validation, recommendations | 1,500 RPD, 1M TPM |
| Gemini text-embedding-004 | Vector embeddings for report clustering | 1,500 RPD |
| Google AI Studio | API key management | Free |

### 4.3 Backend Stack (Python / Cloud Run)

| Component | Technology | Purpose |
|---|---|---|
| Language | Python 3.11 | Core runtime |
| Web Framework | FastAPI | Async REST API, auto OpenAPI docs |
| ASGI Server | Uvicorn + Gunicorn | Production server |
| Container | Docker (multi-stage python:3.11-slim) | Cloud Run deployment |
| Gemini SDK | google-genai | Official Gen AI SDK |
| Firebase Admin | firebase-admin | Server-side Firestore + Auth |
| HTTP Client | httpx | Async external API calls |
| Data Validation | Pydantic v2 | Schemas + Gemini structured output |
| PDF Extraction | pypdf | Fallback text extraction |
| PDF Generation | weasyprint | Report + complaint letter PDFs |
| Excel Parsing | pandas + openpyxl | World Bank data ingest |
| Image Processing | Pillow | Resize before Gemini |
| Rate Limiting | slowapi | Abuse protection |
| Retry Logic | tenacity | Gemini resilience |
| String Utilities | python-slugify | Corridor/agency slugs |
| File Uploads | python-multipart | FastAPI form uploads |

### 4.4 Frontend Stack (React PWA)

| Component | Technology | Purpose |
|---|---|---|
| Framework | React 18 + Vite | Core frontend |
| Language | TypeScript | Type safety |
| Routing | React Router v6 | Client routing |
| Styling | Tailwind CSS | Utility-first CSS |
| UI Components | shadcn/ui + Radix UI | Accessible components |
| UI State | Zustand | Light global state |
| Server State | TanStack Query | API data caching |
| Forms | React Hook Form + Zod | Type-safe forms |
| Firebase SDK | firebase v10 | Auth + Firestore + Storage |
| File Upload | react-dropzone + input capture | Drag-drop + mobile camera |
| PDF Preview | react-pdf | Inline contract preview |
| Icons | lucide-react | Icon library |
| Charts | Recharts | Trends, financial scores, heatmaps |
| Maps (Radar) | react-leaflet + OpenStreetMap | Free interactive maps |
| i18n | react-i18next + i18next | 6-language UI |
| PWA | vite-plugin-pwa | Installable + offline |
| Notifications | Firebase Cloud Messaging Web SDK | Push alerts |
| Error Tracking | Sentry (free tier) | Frontend errors |

### 4.5 External Data Sources (All Free)

| Source | Purpose | Access | Storage |
|---|---|---|---|
| World Bank RPW | Provider fees, 367 corridors | Excel download, attribution | Firestore corridors/ |
| ILO NATLEX | National labor laws (6 countries) | Manual curation | Firestore labor_laws/ |
| ILO NORMLEX | International labor standards | Reference material | Not stored |
| Frankfurter API | Live mid-market FX rates | REST, no key | Firestore rates_cache/ |
| ExchangeRate-API | FX rates fallback | REST, free key | Firestore rates_cache/ |
| OpenStreetMap | Map tiles for Radar | Free with attribution | Client-side |

### 4.6 DevOps & CI/CD

| Component | Technology | Purpose |
|---|---|---|
| Version Control | GitHub (public repo) | Required for submission |
| CI/CD | GitHub Actions | Auto-deploy pipeline |
| Backend Deploy | GH Actions → Cloud Build → Cloud Run | Container pipeline |
| Frontend Deploy | GH Actions → Firebase Hosting | Static build pipeline |
| Local Emulation | Firebase Emulator Suite | Zero-cost local dev |
| API Testing | Postman / Bruno | Endpoint verification |
| Env Management | .env.local (dev), Secret Manager (prod) | No secrets in git |
| API Docs | FastAPI auto-Swagger /docs | Judges can inspect API |

### 4.7 Firestore Data Model

| Collection | Purpose | Pillar |
|---|---|---|
| users/{uid} | User profiles, preferences, language | All |
| users/{uid}/contracts/{id} | Uploaded contracts + analysis | Contract Shield |
| users/{uid}/transfers/{id} | Logged remittance transactions | Remittance X-Ray + FIB |
| users/{uid}/income/{id} | Income entries | Financial Identity |
| users/{uid}/bills/{id} | Bill payments logged | Financial Identity |
| users/{uid}/financial_profile | Computed financial identity | Financial Identity |
| users/{uid}/notifications/{id} | Radar alerts, reminders | Exploitation Radar |
| labor_laws/{country}/rules/{cat} | Curated labor law rules | Contract Shield |
| labor_laws/{country}/_meta | Version tracking for cache | Contract Shield |
| corridors/{corridor_id} | World Bank provider fees | Remittance X-Ray |
| rates_cache/{currency_pair} | Live FX rates | Remittance X-Ray |
| rates_history/{pair}/points | Historical rate snapshots | Remittance X-Ray |
| radar_reports/{id} | User-submitted reports | Exploitation Radar |
| radar_entities/{slug} | Aggregated risk profiles | Exploitation Radar |
| radar_alerts/{corridor}/current | Active alerts per corridor | Exploitation Radar |
| complaint_templates/{country}/{type} | Legal complaint templates | Contract Shield |
| report_embeddings/{id} | Vector embeddings | Exploitation Radar |

### 4.8 Cost Summary

| Category | Cost |
|---|---|
| All Google Cloud services | ₹0 |
| All Gemini API usage | ₹0 |
| All external data APIs | ₹0 |
| GitHub, Sentry, OpenStreetMap | ₹0 |
| TOTAL for POC + Evaluation | ₹0 |

## 5. System Workflow — Mermaid Diagram Codes

All diagrams below can be rendered by pasting the code into https://mermaid.live. Export each as PNG or SVG for the pitch deck and README.

### 5.1 Complete System Architecture (Full View)

The full system architecture showing user, frontend, backend, AI layer, data layer, external sources, and background jobs.

flowchart TB

User([Migrant Worker - Any Language, Any Device])

subgraph FE[FRONTEND - Firebase Hosting - React PWA]

Landing[Landing Page + Language Selector]

Auth[Firebase Auth - Google + Phone OTP]

Home[Dashboard - 4 Feature Cards]

end

User --> Landing

Landing --> Auth

Auth --> Home

Home --> P1[Remittance X-Ray]

Home --> P2[Contract Shield]

Home --> P3[Exploitation Radar]

Home --> P4[Financial Identity]

subgraph BE[BACKEND - Cloud Run - FastAPI]

API[REST API Gateway - Firebase Auth Verify]

Router{Route to Service}

end

P1 --> API

P2 --> API

P3 --> API

P4 --> API

API --> Router

Router --> RX[Remittance Engine]

Router --> CS[Contract Analysis Pipeline]

Router --> RD[Radar Aggregation]

Router --> FI[Financial Profile Builder]

subgraph AI[GEMINI AI LAYER]

G1[Gemini 1.5 Flash - Vision + Extraction]

G2[Gemini 2.5 Flash - Legal Reasoning + Synthesis]

G3[Gemini Flash-Lite - Translation + Classification]

G4[text-embedding-004 - Vector Embeddings]

end

RX --> G3

CS --> G1

CS --> G2

RD --> G3

RD --> G4

FI --> G1

FI --> G2

subgraph DB[FIRESTORE - Data Layer]

FS1[(users + contracts + transfers)]

FS2[(labor_laws - 6 countries)]

FS3[(corridors - World Bank)]

FS4[(rates_cache + rates_history)]

FS5[(radar_reports + radar_entities)]

FS6[(financial_profile)]

end

RX --> FS3

RX --> FS4

CS --> FS1

CS --> FS2

RD --> FS5

FI --> FS1

FI --> FS6

CS --> CST[(Cloud Storage - PDFs + Reports)]

subgraph EXT[EXTERNAL DATA SOURCES]

WB[World Bank RPW - Quarterly Excel]

ILO[ILO NATLEX - Labor Laws]

FRA[Frankfurter API - Live FX]

end

CRON[Cloud Scheduler - Every 2 Hours]

CRON --> FRA

FRA --> FS4

WB -.One-time load.-> FS3

ILO -.Manual curation.-> FS2

classDef userStyle fill:#4285F4,stroke:#1a73e8,color:#fff

classDef aiStyle fill:#EA4335,stroke:#c5221f,color:#fff

classDef dbStyle fill:#34A853,stroke:#188038,color:#fff

classDef extStyle fill:#FBBC04,stroke:#f9ab00,color:#000

class User userStyle

class G1,G2,G3,G4 aiStyle

class FS1,FS2,FS3,FS4,FS5,FS6,CST dbStyle

class WB,ILO,FRA extStyle

### 5.2 Pillar 1 — Remittance X-Ray Pipeline

Shows the flow when a worker compares remittance options for a corridor, plus the background cron job that keeps FX rates fresh.

flowchart LR

U([Worker])

U -->|1 - Select Corridor + Amount| API[Cloud Run API]

API -->|Step 1| S1[Verify Auth - Firebase]

S1 -->|Step 2| S2[Fetch Provider Fees - Firestore corridors]

S2 -->|Step 3| S3[Fetch Live FX Rate - Firestore rates_cache]

S3 -->|Step 4| S4[Fetch Historical Rates - rates_history]

S4 -->|Step 5| S5[Calculate True Total Cost per Provider]

S5 -->|Step 6| S6[Rank by Recipient Receives Most]

S6 -->|Step 7| S7[Detect Rate Trends - Best Day to Send]

S7 -->|Step 8| S8[Compute Historical Savings vs Choice]

S8 -->|Step 9| S9[Generate Recommendation - Gemini Flash-Lite]

S9 -->|Step 10| S10[Translate to User Language - Gemini Flash-Lite]

S10 --> R[Comparison Table + Trend Chart + Savings Insight]

R --> U

U -.Log Transfer.-> H[(Firestore - users transfers)]

H -.Feeds.-> FI[Financial Identity Builder]

subgraph CRON[Background Cron - Every 2 Hours]

CS[Cloud Scheduler]

CS -->|Trigger| RF[refresh_rates endpoint]

RF -->|Fetch| FR[Frankfurter API]

FR -->|On failure| ER[ExchangeRate-API]

FR -->|Write current| RC[(rates_cache)]

FR -->|Append point| RH[(rates_history)]

ER -->|Write current| RC

end

classDef gemini fill:#EA4335,stroke:#c5221f,color:#fff

classDef data fill:#34A853,stroke:#188038,color:#fff

classDef ext fill:#FBBC04,stroke:#f9ab00,color:#000

class S9,S10 gemini

class S2,S3,S4,H,RC,RH data

class FR,ER ext

### 5.3 Pillar 2 — Contract Shield Pipeline

The 6-step agentic pipeline. This is the technical showcase — multi-modal Vision plus multi-step legal reasoning plus multilingual generation.

flowchart LR

U([Worker])

U -->|1 - Upload Contract| CS[Cloud Storage]

CS -->|2 - File URL| API[Cloud Run API]

API -->|Step 1| S1[Verify Auth - Firebase]

S1 -->|Step 2| S2[Extract Text - Gemini 1.5 Vision]

S2 -->|Step 3| S3[Detect Language + Country + Type - Gemini 1.5 Flash]

S3 -->|Step 4| S4[Fetch Labor Laws - Firestore RAG]

S4 -->|Step 5| S5[Full Translation to User Language - Gemini Flash-Lite]

S5 -->|Step 6| S6[Clause-by-Clause Comparison - Gemini 2.5 Flash]

S6 -->|Step 7| S7[Flag Concerning Clauses]

S7 -->|Step 8| S8[Compute Contract Health Score]

S8 -->|Step 9a| S9a[Generate Complaint Letter if violations - Gemini 2.5 Flash]

S8 -->|Step 9b| S9b[Side-by-Side Report]

S9a --> R[Contract Health Report + Complaint Letter]

S9b --> R

R --> U

S8 -.Save Analysis.-> L[(Firestore - users contracts)]

S7 -.Anonymized Signal.-> RD[Feeds Exploitation Radar]

classDef gemini fill:#EA4335,stroke:#c5221f,color:#fff

classDef data fill:#34A853,stroke:#188038,color:#fff

class S2,S3,S5,S6,S9a gemini

class S4,L data

### 5.4 Pillar 3 — Exploitation Radar Pipeline

Crowdsourced report submission with Gemini validation, embedding-based clustering, aggregation cron, and push notification alerts.

flowchart LR

U([Worker])

U -->|1 - Submit Report - operator agency or employer| API[Cloud Run API]

API -->|Step 1| S1[Verify Auth + App Check]

S1 -->|Step 2| S2[Extract Entity Name + Corridor + Type - Gemini 1.5 Flash]

S2 -->|Step 3| S3[Validate Report - spam duplicate - Gemini Flash-Lite]

S3 -->|Step 4| S4[Categorize Violation Type - Gemini Flash-Lite]

S4 -->|Step 5| S5[Generate Embedding - text-embedding-004]

S5 -->|Step 6| S6[Similarity Search - Firestore Vector]

S6 -->|Step 7| S7[Save Report - radar_reports]

S7 -->|Step 8| S8[Update Entity Risk Profile - radar_entities]

S8 -->|Step 9| S9[Recompute Community Rating]

S9 --> R[Report Confirmation]

R --> U

subgraph AGG[Radar Aggregation - Every 6 Hours Cron]

CS[Cloud Scheduler]

CS --> AG[aggregate_radar endpoint]

AG -->|Detect surges| AL[Generate Alerts]

AL -->|Write| RA[(radar_alerts by corridor)]

AL -->|Push| FCM[Firebase Cloud Messaging]

FCM -->|Notify| SUB[Subscribed Workers]

end

subgraph MAP[Heat Map View]

U -->|View Corridor| HM[Fetch Aggregated Data]

HM --> LEAF[react-leaflet + OpenStreetMap]

LEAF --> U

end

S7 -.Data.-> HM

classDef gemini fill:#EA4335,stroke:#c5221f,color:#fff

classDef data fill:#34A853,stroke:#188038,color:#fff

classDef ext fill:#FBBC04,stroke:#f9ab00,color:#000

class S2,S3,S4,S5 gemini

class S7,S8,RA,HM data

class LEAF ext

### 5.5 Pillar 4 — Financial Identity Builder Pipeline

Longitudinal data collection across income, transfers, bills, and savings. Weekly cron synthesizes the portable Financial Identity Report.

flowchart LR

U([Worker])

U -->|Log Activity| IN{Input Type}

IN -->|Income Entry| E1[Add Income Record]

IN -->|Transfer Log| E2[Add Remittance - auto from Pillar 1]

IN -->|Bill Payment| E3[Upload Bill Photo]

IN -->|Savings| E4[Log Savings]

E1 --> API[Cloud Run API]

E2 --> API

E3 --> API

E4 --> API

API -->|Step 1| S1[Verify Auth - Firebase]

S1 -->|Bill Path - Step 2a| S2a[Extract Bill Data - Gemini 1.5 Vision]

S2a --> S3[Save to Firestore]

S1 -->|Other Paths - Step 2b| S2b[Validate Input - Pydantic]

S2b --> S3

S3 -->|Step 3| S4[Categorize Transaction - Gemini Flash-Lite]

S4 -->|Step 4| S5[Update Financial Timeline - Firestore]

S5 --> R[Activity Logged]

R --> U

subgraph SCORE[Financial Score Recompute - Weekly Cron]

CS[Cloud Scheduler] --> RC[recompute_profile endpoint]

RC --> ALL[Fetch All User Activity]

ALL --> METRICS[Compute Metrics]

METRICS --> SYN[Synthesize Financial Narrative - Gemini 2.5 Flash]

SYN --> PROF[(financial_profile)]

end

U -->|Request Portable Report| EXP[Export Financial Identity]

EXP --> PROF

PROF --> PDF[Generate PDF - weasyprint]

PDF --> DL[Download or Share Link]

DL --> U

classDef gemini fill:#EA4335,stroke:#c5221f,color:#fff

classDef data fill:#34A853,stroke:#188038,color:#fff

class S2a,S4,SYN gemini

class S3,S5,PROF,METRICS data

### 5.6 Cross-Pillar Data Flow

How the pillars strengthen each other. This is the ecosystem story — the pillars are not features, they are a system where data from one makes the others smarter.

flowchart TB

U([Migrant Worker])

U --> P1[Remittance X-Ray]

U --> P2[Contract Shield]

U --> P3[Exploitation Radar]

U --> P4[Financial Identity]

P1 -.Every transfer logged.-> P4

P2 -.Employer flags feed radar.-> P3

P3 -.Verified bad actors shown.-> P1

P3 -.Verified bad agencies shown.-> P2

P2 -.Verified employment adds.-> P4

P4 --> OUT([Portable Financial Identity])

OUT --> MFI[MFI or Bank in Home Country]

classDef pillar fill:#4285F4,stroke:#1a73e8,color:#fff

classDef output fill:#34A853,stroke:#188038,color:#fff

class P1,P2,P3,P4 pillar

class OUT output

## 6. Next Steps

Immediate action items after finalizing this document.

### 6.1 Phase 0 — Pre-Build Setup (Day 1)

- Create GitHub public repository with README, LICENSE, .gitignore
- Create Google Cloud project and enable APIs (Firestore, Cloud Run, Cloud Build, Secret Manager, Cloud Scheduler)
- Create Firebase project linked to the GCP project
- Generate Gemini API key from AI Studio and store in Secret Manager
- Enable Firebase Auth (Google + Phone), Firestore, Storage, App Check, Cloud Messaging
- Add all 3 team members as project owners

### 6.2 Documentation to Create Next

- README.md skeleton in repo root
- docs/architecture-diagram.png (export from mermaid.live)
- docs/data-model.md (Firestore collection schemas)
- docs/api-contract.md (REST endpoints)
- docs/gemini-prompts.md (system prompts per use case)
- docs/ui-wireframes.png (Excalidraw/Figma sketches)

### 6.3 Week-by-Week Build Timeline

- Week 1 (Sep 21–27): Foundation, data ingestion, first deploy
- Week 2 (Sep 28–Oct 4): Contract Shield + Remittance X-Ray core features
- Week 3 (Oct 5–11): Exploitation Radar + Financial Identity + polish
- Week 4 (Oct 12–18): Testing, demo video, pitch deck, submission

### 6.4 Submission Deliverables (October 18)

- Pitch deck PDF (prescribed template)
- 3–4 minute demo video (YouTube/Vimeo/Google Drive)
- Live deployed prototype link (Cloud Run + Firebase Hosting)
- Public GitHub repository
- Brief description mentioning Firebase, Firestore, Cloud Run, and Gemini usage
End of Document

NomadFinance — Google Cloud AI Builder Cup 2026

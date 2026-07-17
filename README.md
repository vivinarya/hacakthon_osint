# EVIDENCE — Explainable OSINT Investigative Agent

An autonomous investigative agent that researches entities, people, and organizations using open-source intelligence (OSINT) data. Every claim is linked to source evidence with confidence scoring, corroboration tracking, and contradiction detection.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    REACT FRONTEND (Vite)                    │
│  Header · SearchBar · InvestigationBoard · Contradiction   │
│  Panel · ReportView · ToolPanel · MagneticCursor           │
│  GSAP animations · Lenis smooth scroll                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP (POST /api/investigate)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│               FASTAPI BACKEND (api_server.py)               │
│  CORS · request validation · response serialization         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              INVESTIGATIVE AGENT (react_loop.py)             │
├───────────────┬────────────────┬────────────────────────────┤
│   PLANNER     │   EXECUTOR     │   CLAIM EXTRACTOR          │
│  (planner.py) │ (executor.py)  │ (claim_extractor.py)       │
│  LLM breaks   │ 13 tools,      │ Rule-based regex           │
│  query into   │ asyncio.gather │ extraction from            │
│  sub-questions│ parallel exec  │ tool results               │
└───────┬───────┴───────┬────────┴────────────┬───────────────┘
        │               │                     │
        ▼               ▼                     ▼
┌───────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ EVIDENCE      │ │ VERIFICATION │ │ REPORTING            │
│ LEDGER        │ │              │ │                      │
│ (schema.py)   │ │ Confidence   │ │ Report Generator     │
│ Ledger of     │ │ Scorer       │ │ (report_generator.py)│
│ claims +      │ │ (7 factors)  │ │ Markdown + HTML      │
│ sources with  │ │              │ │                      │
│ citations     │ │ Cross-       │ │ Evidence Explainer   │
│               │ │ Referencer   │ │ (evidence_           │
│               │ │ (heuristic   │ │  explainer.py)       │
│               │ │ + LLM)       │ │ Per-claim "why"      │
│               │ │              │ │                      │
│               │ │ Contradiction│ │                      │
│               │ │ Detector     │ │                      │
│               │ │ (severity    │ │                      │
│               │ │ scoring)     │ │                      │
└───────┬───────┘ └──────┬───────┘ └──────────┬───────────┘
        │                │                    │
        ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    OSINT DATA SOURCES                       │
├──────────┬──────────┬───────────┬──────────┬───────────────┤
│ Wikidata │ ICIJ     │ OFAC SDN  │ GDELT    │ Web Search    │
│ SPARQL   │ Offshore │ Sanctions │ Conflict │ (Firecrawl)   │
│ queries  │ Leaks DB │ List      │ Events   │               │
├──────────┼──────────┼───────────┼──────────┼───────────────┤
│ Open-    │ Wayback  │ OpenCorp  │ Web      │ STREAMLIT UI  │
│ Sanctions│ Machine  │ (paid,    │ Scraper  │ (standalone)  │
│ API      │ CDX API  │ degraded) │ (BS4)    │               │
└──────────┴──────────┴───────────┴──────────┴───────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Vite 6, GSAP 3.15, Lenis 1.2, React Router 7 |
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Agent** | LLM-based planner + tool executor + claim extractor |
| **LLM** | OpenRouter (`gpt-oss-20b:free`) / Anthropic Claude |
| **Data Layer** | Pandas, NetworkX, BeautifulSoup, httpx |
| **UI (alt)** | Streamlit (standalone, no frontend needed) |
| **Datasets** | Wikidata SPARQL, ICIJ Offshore Leaks (898MB), OFAC SDN List, GDELT Event Database, OpenSanctions |

## Quick Start

### Prerequisites
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration (Deployment Ready)
Create a `.env` file in the root directory (based on `.env.example`):
```env
# Leave empty to require client-supplied keys in the browser:
OPENAI_API_KEY=
OPENAI_BASE_URL=https://bazaarlink.ai/api/v1
OPENAI_MODEL=gpt-oss-20b

FIRECRAWL_API_KEY=
STEP_CAP=15
LOG_LEVEL=INFO
```
*Note: If `OPENAI_API_KEY` and `FIRECRAWL_API_KEY` are left blank on the server, the frontend will automatically lock the board and prompt the user to input their keys in the initialization setup screen. If configured on the server, the frontend will seamlessly use the server's keys with the option to override them locally.*

### API Credentials Required
1. **BazaarLink API Key**: Sign up at [bazaarlink.ai](https://bazaarlink.ai) to obtain your key. We recommend using fast, low-cost models like `gpt-oss-20b` or `gemma-3-12b-it`.
2. **Firecrawl API Key**: Sign up at [firecrawl.dev](https://firecrawl.dev) to get a web searching/scraping key.

### Run Backend (API Server)
```bash
python api_server.py
# → http://localhost:8000
```

### Run Frontend (separate terminal)
```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Run Standalone (Streamlit, no frontend needed)
```bash
streamlit run src/ui/app.py
```

### Run CLI Mode
```bash
python run.py --cli "Investigate Mossack Fonseca and related offshore entities"
```

## Data Sources

| Source | Type | Access | Coverage |
|--------|------|--------|----------|
| **Wikidata** | Structured entity data | SPARQL queries | 100M+ entities |
| **ICIJ Offshore Leaks** | Offshore entity DB | Local CSV (~898MB) | Panama/Pandora/Paradise Papers |
| **OFAC SDN List** | Sanctions list | Local CSV (19K+ entries) | US sanctions |
| **GDELT** | Global event database | Daily CSV files | Global news events |
| **OpenSanctions** | Sanctions/PEP data | Public API | 2.1M entities |
| **Firecrawl** | Web search + scrape | API key | Web search |
| **Wayback Machine** | Archived pages | CDX API | Web archiving |

## Features

- **LLM-powered planning**: Breaks investigative questions into parallel sub-queries
- **13 research tools**: Wikidata, ICIJ, OFAC, GDELT, OpenSanctions, web search, etc.
- **Evidence ledger**: Every claim recorded with source citation, confidence score, and extraction method
- **Confidence scoring**: Multi-agent geometric scoring pipeline (Source Authority × Temporal Factor × Corroboration Count × Network Independence) with echo chamber detection
- **Cross-referencing**: Heuristic + optional LLM-based claim comparison
- **Contradiction detection**: Severity-graded conflict identification
- **Explainability**: Per-claim reasoning replay ("why does the agent think this?")
- **Structured reports**: Markdown reports with inline citations and corroboration badges
- **React dashboard**: GSAP-animated investigation board with evidence cards, contradiction panels, terminal log
- **Streamlit UI**: Alternative standalone UI with evidence graph visualization

## Multi-Agent Confidence Scoring

EVIDENCE uses a highly decoupled, multi-agent geometric scoring formula to calculate the final Confidence Score (`CS`) for every claim:

**Formula**: `CS = (SA × TF) × (CC × NI) × 100`

The pipeline is orchestrated across four specialized agents:

1. **Source Tagger Agent (SA)**: Determines Source Authority (0.0 to 1.0) using TLD structural rules (e.g., `.gov`, `.mil`), social media ceilings, whitelists, and suspicion heuristics for unknown domains.
2. **Temporal Scoping Agent (TF)**: Computes the Temporal Factor using an exponential decay function (`TF = e^(-λ·t)`) based on the nature of the claim. Breaking news decays quickly (`λ = 0.5`) while static historical facts do not decay (`λ = 0`).
3. **Network Graph Agent (CC & NI)**: Builds a domain family cluster graph of all corroborating sources.
   - **Corroboration Count (CC)**: Evaluates corroboration saturation based on independent sources.
   - **Network Independence (NI)**: Measures domain diversity. Actively detects **echo chambers** (e.g., when multiple corroborating claims all come from subdomains of the same parent company) and applies a severe penalty to the NI score.
4. **Contradiction & Adversarial Agent**: Scans the entire evidence ledger for counter-claims using explicit cross-referencing and semantic negation scanning. Computes a `debunk_score` weighted by the counter-claim's source authority.

**Logic States**: 
Claims are ultimately classified into actionable states: `VERIFIED_FACT` (CS ≥ 65, no disputes), `BREAKING_CLAIM` (sole or fresh source, needs corroboration), `ACTIVE_DISPUTE` (conflicting evidence exists), or `DEBUNKED` (high-authority active contradiction).

## Project Structure

```
├── api_server.py          # FastAPI backend server
├── run.py                 # CLI/Streamlit entry point
├── pyproject.toml         # Python project config
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
├── .gitignore
├── src/
│   ├── config.py          # Environment configuration
│   ├── llm_client.py      # LLM abstraction (OpenAI/Anthropic)
│   ├── agent/
│   │   ├── planner.py           # Research plan generation
│   │   ├── executor.py          # Tool execution engine
│   │   ├── claim_extractor.py   # Claim extraction from results
│   │   └── react_loop.py        # Main agent orchestration
│   ├── evidence_ledger/
│   │   ├── schema.py            # Source & Claim dataclasses
│   │   └── store.py             # JSON persistence
│   ├── tools/
│   │   ├── base.py              # Tool base class
│   │   ├── wikidata.py          # Wikidata SPARQL queries
│   │   ├── icij_data.py         # ICIJ Offshore Leaks queries
│   │   ├── gdelt.py             # GDELT event queries
│   │   ├── ofac_sdn.py          # OFAC SDN sanctions queries
│   │   ├── opensanctions.py     # OpenSanctions API
│   │   ├── wayback.py           # Wayback Machine API
│   │   ├── web_search.py        # Web search (Firecrawl/Tavily/Serper)
│   │   ├── web_scraper.py       # HTML scraper
│   │   ├── firecrawl_scraper.py # Firecrawl scrape/search/map/extract
│   │   └── opencorporates.py    # OpenCorporates (paid, degraded)
│   ├── verification/
│   │   ├── orchestrator.py          # Central Scoring Orchestrator
│   │   ├── source_tagger.py         # Source Authority Agent
│   │   ├── temporal_agent.py        # Temporal Scoping Agent
│   │   ├── network_graph_agent.py   # Network Graph Agent
│   │   ├── adversarial_agent.py     # Contradiction & Adversarial Agent
│   │   ├── cross_referencer.py      # Claim corroboration linking
│   │   ├── contradiction_detector.py # Cross-claim conflict detection
│   │   └── confidence_scorer.py     # Legacy 4-factor model
│   ├── reporting/
│   │   ├── report_generator.py  # Structured markdown reports
│   │   └── evidence_explainer.py # Per-claim explainability
│   └── ui/
│       └── app.py               # Streamlit user interface
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx              # Main app with Lenis + GSAP
│       ├── main.jsx             # React entry
│       ├── index.css            # Dark theme, fonts, responsive
│       ├── lib/gsap.js          # GSAP + ScrollTrigger + useGSAP
│       └── components/
│           ├── Header.jsx              # Animated title
│           ├── SearchBar.jsx           # Investigation input
│           ├── InvestigationBoard.jsx   # Evidence card grid
│           ├── EvidenceCard.jsx        # Claim card with confidence
│           ├── ContradictionPanel.jsx   # Side-by-side conflicts
│           ├── ReportView.jsx          # Metrics + terminal log
│           ├── TerminalOutput.jsx      # Typewriter log display
│           ├── ToolPanel.jsx           # Methodology badges
│           ├── SourceBadge.jsx         # Source type tags
│           └── MagneticCursor.jsx      # Custom cursor
├── tests/
│   ├── test_evidence_ledger.py
│   ├── test_reporting.py
│   ├── test_tools.py
│   └── test_verification.py
└── examples/
    ├── demo_contradiction_query.py
    └── demo_corporate_query.py
```

## Screenshots

*(Screenshots of the setup screen, evidence cards, contradiction panels, and final reports)*

- **API Credentials Setup Screen**: `![Setup Screen Placeholder](docs/setup_screen.png)`
- **GSAP Evidence Board Grid**: `![Evidence Board Placeholder](docs/evidence_board.png)`
- **Side-by-Side Contradiction Panel**: `![Contradiction Panel Placeholder](docs/contradiction_panel.png)`
- **Metrics Dashboard & Narrative Report**: `![Narrative Report Placeholder](docs/report_view.png)`

# System Architecture
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│         (Web Browser - FastAPI served HTML)              │
└────────────────────┬────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────┐
│                 CITEGUARD API LAYER                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   /verify   │  │ /verify/pdf │  │  /verify/url    │ │
│  │  (Real APIs)│  │(PDF Upload) │  │ (Web Scraping)  │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
└─────────┼────────────────┼──────────────────┼──────────┘
│                │                  │
▼                ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
│  REAL API LAYER │ │ PDF PROCESSOR│ │  URL SCRAPER    │
│  ┌───────────┐  │ │              │ │                 │
│  │  PubMed   │  │ │ PyPDF2       │ │  urllib         │
│  │  (NCBI)   │  │ │ Text extract │ │  HTML parse     │
│  └───────────┘  │ │ Keyword search│ │ Content extract │
│  ┌───────────┐  │ └──────────────┘ └─────────────────┘
│  │  Semantic │  │
│  │  Scholar  │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │ Wikipedia │  │
│  │   (API)   │  │
│  └───────────┘  │
└─────────────────┘
│
▼
┌─────────────────────────────────────────────────────────┐
│              VERIFICATION ENGINE                         │
│  • Evidence extraction                                   │
│  • Relevance scoring                                     │
│  • Confidence calculation                                │
│  • Citation generation                                   │
└─────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────┐
│              RESPONSE FORMAT                             │
│  • Verified status                                       │
│  • Confidence score (0-100%)                            │
│  • Highlight-anchored citations                         │
│  • Source attribution with URLs                         │
│  • Human-readable explanation                           │
└─────────────────────────────────────────────────────────┘
Copy

## Data Flow

1. **User Input** → Claim + Source type (API/PDF/URL/Text)
2. **Source Retrieval** → Fetch from real APIs or process uploaded content
3. **Evidence Extraction** → Find relevant passages with keyword matching
4. **Scoring** → Calculate confidence based on source credibility + relevance
5. **Citation Generation** → Format results with exact quotes and source links
6. **Response** → JSON + Web interface display
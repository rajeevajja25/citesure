# Prompt Strategy

## Current (Non-LLM)
- Keyword extraction: `set(claim.lower().split())`
- Relevance scoring: `matches * 0.15`
- Negation detection: rule-based

## Future LLM Integration
### Prompt 1: Claim Decomposition
Break complex claims into atomic facts.

### Prompt 2: Evidence Extraction
Extract supporting evidence with exact quotes.

### Prompt 3: Confidence Calibration
Calculate confidence from source quality.

## Why This Strategy
| Approach | Pros | Cons |
|----------|------|------|
| Current | Fast, deterministic, free | Less nuanced |
| Future LLM | Better understanding | Higher cost, latency |

## Version History
- v1.0: Regex matching
- v2.0: Credibility scoring
- v3.0: Multi-source (current)
- v4.0: LLM-enhanced (planned)
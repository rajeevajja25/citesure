# Final Output Format

## API Response
```json
{
  "original_claim": "climate change is real",
  "status": "verified",
  "confidence": 0.87,
  "citations": [
    {
      "quote": "Research: Global temperature trends",
      "context": "Authors: Smith et al. Published: 2023",
      "source_title": "Global Temperature Trends",
      "source_publisher": "PubMed/NCBI",
      "source_type": "peer_reviewed",
      "source_url": "https://pubmed.ncbi.nlm.nih.gov/123456/",
      "relevance_score": 0.85
    }
  ],
  "sources_used": [
    {
      "name": "PubMed/NCBI",
      "type": "peer_reviewed",
      "url": "https://pubmed.ncbi.nlm.nih.gov/123456/",
      "credibility_score": 1.0
    }
  ],
  "explanation": "VERIFICATION RESULT\n...\nRECOMMENDATION: ✓ ACCEPT"
}
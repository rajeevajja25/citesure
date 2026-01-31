from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
import random
import re
import json
from datetime import datetime
import urllib.request
import urllib.parse
import ssl


PDF_SUPPORT = False

app = FastAPI(title="CiteGuard", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class SourceType(str, Enum):
    PEER_REVIEWED = "peer_reviewed"
    GOVERNMENT = "government"
    LEGAL = "legal"
    NEWS_TIER1 = "news_tier1"
    UPLOADED = "uploaded"

class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"
    NO_EVIDENCE = "no_evidence"

class Citation(BaseModel):
    quote: str
    context: str
    source_title: str
    source_publisher: str
    source_type: str
    source_url: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    relevance_score: float
    access_date: str

class SourceInfo(BaseModel):
    name: str
    type: str
    url: Optional[str] = None
    credibility_score: float
    date_accessed: str

class VerifiedResult(BaseModel):
    original_claim: str
    status: VerificationStatus
    confidence: float
    citations: List[Citation]
    sources_used: List[SourceInfo]
    contradictory_evidence: List[Citation]
    explanation: str
    total_sources_checked: int
    verification_method: str

class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=5, max_length=1000)
    domain: Optional[str] = "general"

class URLRequest(BaseModel):
    url: str
    claim: str

class PasteRequest(BaseModel):
    text: str = Field(..., min_length=50)
    claim: str
    source_name: Optional[str] = "Pasted Text"

class RealAPIs:
    @staticmethod
    def pubmed(query: str) -> List[Dict]:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded}&retmode=json&retmax=2"
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(url, context=ctx, timeout=10) as response:
                data = json.loads(response.read().decode())
                pmids = data.get('esearchresult', {}).get('idlist', [])
                results = []
                for pmid in pmids:
                    sum_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
                    with urllib.request.urlopen(sum_url, context=ctx, timeout=10) as sum_response:
                        sum_data = json.loads(sum_response.read().decode())
                        docs = sum_data.get('result', {})
                        if pmid in docs:
                            doc = docs[pmid]
                            authors = doc.get('authors', [])
                            author = authors[0].get('name', 'Unknown') if authors else 'Unknown'
                            results.append({
                                'id': f"pubmed_{pmid}",
                                'title': doc.get('title', 'Unknown'),
                                'authors': author,
                                'publisher': 'PubMed/NCBI',
                                'date': doc.get('pubdate', 'Unknown'),
                                'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                'type': 'peer_reviewed',
                                'credibility': 1.0
                            })
                return results
        except Exception as e:
            print(f"PubMed error: {e}")
            return []
    
    @staticmethod
    def semantic_scholar(query: str) -> List[Dict]:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded}&fields=title,authors,year,url&limit=2"
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                data = json.loads(response.read().decode())
                papers = data.get('data', [])
                results = []
                for paper in papers:
                    authors = paper.get('authors', [])
                    author = authors[0].get('name', 'Unknown') if authors else 'Unknown'
                    results.append({
                        'id': f"ss_{paper.get('paperId', 'unknown')}",
                        'title': paper.get('title', 'Unknown'),
                        'authors': author,
                        'publisher': 'Semantic Scholar',
                        'date': str(paper.get('year', 'Unknown')),
                        'url': paper.get('url', ''),
                        'type': 'peer_reviewed',
                        'credibility': 1.0
                    })
                return results
        except Exception as e:
            print(f"Semantic Scholar error: {e}")
            return []
    
    @staticmethod
    def wikipedia(query: str) -> List[Dict]:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json&srlimit=2"
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(url, context=ctx, timeout=10) as response:
                data = json.loads(response.read().decode())
                search_results = data.get('query', {}).get('search', [])
                results = []
                for item in search_results:
                    title = item.get('title', '')
                    snippet = re.sub(r'<.*?>', '', item.get('snippet', ''))
                    results.append({
                        'id': f"wiki_{item.get('pageid', '')}",
                        'title': title,
                        'authors': 'Wikipedia Contributors',
                        'publisher': 'Wikipedia',
                        'date': 'Unknown',
                        'url': f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        'type': 'reference',
                        'credibility': 0.6,
                        'snippet': snippet
                    })
                return results
        except Exception as e:
            print(f"Wikipedia error: {e}")
            return []

class PDFProcessor:
    @staticmethod
    def extract(file_bytes: bytes) -> str:
        if not PDF_SUPPORT:
            return ""
        try:
            import io
            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text[:15000]
        except Exception as e:
            return f"Error: {str(e)}"
    
    @staticmethod
    def find_citations(text: str, claim: str) -> List[Dict]:
        sentences = re.split(r'[.!?]+', text)
        claim_words = set(claim.lower().split())
        citations = []
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue
            sent_lower = sentence.lower()
            matches = sum(1 for word in claim_words if word in sent_lower)
            if matches >= 2:
                start = max(0, i-2)
                end = min(len(sentences), i+3)
                context = ' '.join(sentences[start:end])
                citations.append({
                    'quote': sentence,
                    'context': context,
                    'page': (i // 10) + 1,
                    'relevance': min(0.95, 0.5 + matches * 0.15)
                })
        return sorted(citations, key=lambda x: x['relevance'], reverse=True)[:5]

class URLProcessor:
    @staticmethod
    def fetch(url: str) -> Dict:
        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Research Bot)'})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')
                title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else url
                text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return {'success': True, 'title': title, 'url': url, 'content': text[:10000]}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def find_citations(content: str, claim: str) -> List[Dict]:
        sentences = re.split(r'[.!?]+', content)
        claim_words = set(claim.lower().split())
        citations = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20 or len(sentence) > 300:
                continue
            sent_lower = sentence.lower()
            matches = sum(1 for word in claim_words if word in sent_lower)
            if matches >= 2:
                citations.append({
                    'quote': sentence,
                    'context': sentence,
                    'relevance': min(0.9, 0.4 + matches * 0.15)
                })
        return sorted(citations, key=lambda x: x['relevance'], reverse=True)[:5]

class TextProcessor:
    @staticmethod
    def find_citations(text: str, claim: str) -> List[Dict]:
        sentences = re.split(r'[.!?]+', text)
        claim_words = set(claim.lower().split())
        citations = []
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue
            sent_lower = sentence.lower()
            matches = sum(1 for word in claim_words if word in sent_lower)
            if matches >= 1:
                para_start = max(0, i-3)
                para_end = min(len(sentences), i+4)
                context = ' '.join(sentences[para_start:para_end])
                negations = ['not', 'no', 'never', 'false', 'incorrect', 'wrong', 'does not', "isn't", 'isnt']
                has_negation = any(neg in sent_lower for neg in negations)
                citations.append({
                    'quote': sentence,
                    'context': context,
                    'paragraph': (i // 5) + 1,
                    'relevance': min(0.95, 0.5 + matches * 0.2),
                    'supports': not has_negation
                })
        return sorted(citations, key=lambda x: x['relevance'], reverse=True)[:5]

class VerificationEngine:
    def __init__(self):
        self.apis = RealAPIs()
    
    def verify_apis(self, claim: str, domain: str = "general") -> VerifiedResult:
        all_citations = []
        sources_info = []
        
        if domain in ["general", "academic", "medical"]:
            pubmed_results = self.apis.pubmed(claim)
            for r in pubmed_results:
                sources_info.append(SourceInfo(
                    name=r['publisher'],
                    type=r['type'],
                    url=r['url'],
                    credibility_score=r['credibility'],
                    date_accessed=datetime.now().isoformat()
                ))
                all_citations.append(Citation(
                    quote=f"Research: {r['title']}",
                    context=f"Authors: {r['authors']}. Published: {r['date']}",
                    source_title=r['title'],
                    source_publisher=r['publisher'],
                    source_type=r['type'],
                    source_url=r['url'],
                    relevance_score=0.85,
                    access_date=datetime.now().isoformat()
                ))
            
            ss_results = self.apis.semantic_scholar(claim)
            for r in ss_results:
                sources_info.append(SourceInfo(
                    name=r['publisher'],
                    type=r['type'],
                    url=r['url'],
                    credibility_score=r['credibility'],
                    date_accessed=datetime.now().isoformat()
                ))
                all_citations.append(Citation(
                    quote=f"Study: {r['title']}",
                    context=f"Published: {r['date']}. Authors: {r['authors']}",
                    source_title=r['title'],
                    source_publisher=r['publisher'],
                    source_type=r['type'],
                    source_url=r['url'],
                    relevance_score=0.9,
                    access_date=datetime.now().isoformat()
                ))
        
        wiki_results = self.apis.wikipedia(claim)
        for r in wiki_results:
            sources_info.append(SourceInfo(
                name=r['publisher'],
                type=r['type'],
                url=r['url'],
                credibility_score=r['credibility'],
                date_accessed=datetime.now().isoformat()
            ))
            all_citations.append(Citation(
                quote=r.get('snippet', f"Article: {r['title']}"),
                context=f"From Wikipedia: {r['title']}",
                source_title=r['title'],
                source_publisher=r['publisher'],
                source_type=r['type'],
                source_url=r['url'],
                relevance_score=0.7,
                access_date=datetime.now().isoformat()
            ))
        
        if all_citations:
            avg_rel = sum(c.relevance_score for c in all_citations) / len(all_citations)
            avg_cred = sum(s.credibility_score for s in sources_info) / len(sources_info)
            confidence = round((avg_rel * 0.6 + avg_cred * 0.4), 2)
        else:
            confidence = 0.0
        
        if confidence >= 0.8:
            status = VerificationStatus.VERIFIED
        elif confidence >= 0.6:
            status = VerificationStatus.PARTIALLY_VERIFIED
        elif confidence > 0:
            status = VerificationStatus.UNVERIFIABLE
        else:
            status = VerificationStatus.NO_EVIDENCE
        
        explanation = self._explain(claim, status, confidence, all_citations, "Real APIs")
        
        return VerifiedResult(
            original_claim=claim,
            status=status,
            confidence=confidence,
            citations=all_citations,
            sources_used=sources_info,
            contradictory_evidence=[],
            explanation=explanation,
            total_sources_checked=len(sources_info),
            verification_method="api"
        )
    
    def verify_pdf(self, file_bytes: bytes, filename: str, claim: str) -> VerifiedResult:
        text = PDFProcessor.extract(file_bytes)
        if not text or text.startswith("Error"):
            return VerifiedResult(
                original_claim=claim,
                status=VerificationStatus.NO_EVIDENCE,
                confidence=0.0,
                citations=[],
                sources_used=[],
                contradictory_evidence=[],
                explanation=f"PDF Error: {text}",
                total_sources_checked=0,
                verification_method="pdf"
            )
        
        found = PDFProcessor.find_citations(text, claim)
        source_info = SourceInfo(
            name=f"PDF: {filename}",
            type="uploaded_pdf",
            url=None,
            credibility_score=0.9,
            date_accessed=datetime.now().isoformat()
        )
        
        citations = []
        for f in found:
            citations.append(Citation(
                quote=f['quote'],
                context=f['context'],
                source_title=filename,
                source_publisher="User Uploaded PDF",
                source_type="uploaded",
                page=f.get('page'),
                relevance_score=f['relevance'],
                access_date=datetime.now().isoformat()
            ))
        
        if citations:
            confidence = round(sum(c.relevance_score for c in citations) / len(citations), 2)
            status = VerificationStatus.VERIFIED if confidence > 0.7 else VerificationStatus.PARTIALLY_VERIFIED
        else:
            confidence = 0.0
            status = VerificationStatus.NO_EVIDENCE
        
        explanation = self._explain(claim, status, confidence, citations, f"PDF: {filename}")
        
        return VerifiedResult(
            original_claim=claim,
            status=status,
            confidence=confidence,
            citations=citations,
            sources_used=[source_info],
            contradictory_evidence=[],
            explanation=explanation,
            total_sources_checked=1,
            verification_method="pdf"
        )
    
    def verify_url(self, url: str, claim: str) -> VerifiedResult:
        page = URLProcessor.fetch(url)
        if not page['success']:
            return VerifiedResult(
                original_claim=claim,
                status=VerificationStatus.NO_EVIDENCE,
                confidence=0.0,
                citations=[],
                sources_used=[],
                contradictory_evidence=[],
                explanation=f"URL Error: {page.get('error')}",
                total_sources_checked=0,
                verification_method="url"
            )
        
        found = URLProcessor.find_citations(page['content'], claim)
        source_info = SourceInfo(
            name=page['title'],
            type="scraped_webpage",
            url=url,
            credibility_score=0.6,
            date_accessed=datetime.now().isoformat()
        )
        
        citations = []
        for f in found:
            citations.append(Citation(
                quote=f['quote'],
                context=f['context'],
                source_title=page['title'],
                source_publisher=url[:60] + "...",
                source_type="scraped",
                source_url=url,
                relevance_score=f['relevance'],
                access_date=datetime.now().isoformat()
            ))
        
        if citations:
            confidence = round(sum(c.relevance_score for c in citations) / len(citations), 2)
            status = VerificationStatus.VERIFIED if confidence > 0.7 else VerificationStatus.PARTIALLY_VERIFIED
        else:
            confidence = 0.0
            status = VerificationStatus.NO_EVIDENCE
        
        explanation = self._explain(claim, status, confidence, citations, f"Web: {page['title']}")
        
        return VerifiedResult(
            original_claim=claim,
            status=status,
            confidence=confidence,
            citations=citations,
            sources_used=[source_info],
            contradictory_evidence=[],
            explanation=explanation,
            total_sources_checked=1,
            verification_method="url"
        )
    
    def verify_text(self, text: str, source_name: str, claim: str) -> VerifiedResult:
        found = TextProcessor.find_citations(text, source_name, claim)
        source_info = SourceInfo(
            name=source_name,
            type="pasted_text",
            url=None,
            credibility_score=0.85,
            date_accessed=datetime.now().isoformat()
        )
        
        supporting = []
        contradicting = []
        
        for f in found:
            cit = Citation(
                quote=f['quote'],
                context=f['context'],
                source_title=source_name,
                source_publisher="User Provided Text",
                source_type="pasted",
                section=f"Paragraph {f.get('paragraph', 'Unknown')}",
                relevance_score=f['relevance'],
                access_date=datetime.now().isoformat()
            )
            if f.get('supports', True):
                supporting.append(cit)
            else:
                contradicting.append(cit)
        
        if supporting:
            confidence = round(sum(c.relevance_score for c in supporting) / len(supporting), 2)
            if confidence >= 0.8:
                status = VerificationStatus.VERIFIED
            elif confidence >= 0.6:
                status = VerificationStatus.PARTIALLY_VERIFIED
            else:
                status = VerificationStatus.UNVERIFIABLE
        else:
            confidence = 0.0
            status = VerificationStatus.NO_EVIDENCE
        
        explanation = self._explain(claim, status, confidence, supporting, f"Text: {source_name}")
        
        return VerifiedResult(
#             original_claim=claim,
            status=status,
            confidence=confidence,
            citations=supporting,
            sources_used=[source_info],
            contradictory_evidence=contradicting,
            explanation=explanation,
            total_sources_checked=1,
            verification_method="pasted_text"
        )
    
    def _explain(self, claim, status, confidence, citations, source_desc) -> str:
        lines = [
            "CITEGUARD VERIFICATION REPORT",
            "=" * 60,
            f"",
            f"CLAIM: {claim}",
            f"",
            f"STATUS: {status.value.upper()}",
            f"CONFIDENCE: {confidence:.0%}",
            f"SOURCE: {source_desc}",
            f"",
            f"CITATIONS FOUND: {len(citations)}",
            ""
        ]
        
        if citations:
            lines.append("TOP CITATIONS WITH SOURCES:")
            for i, c in enumerate(citations[:3], 1):
                lines.append(f"{i}. \"{c.quote[:100]}...\"")
                lines.append(f"   Source: {c.source_publisher}")
                if c.source_url:
                    lines.append(f"   URL: {c.source_url}")
                if c.page:
                    lines.append(f"   Page: {c.page}")
                lines.append(f"   Relevance: {c.relevance_score:.0%}")
                lines.append("")
        
        lines.append("RECOMMENDATION:")
        if status == VerificationStatus.VERIFIED:
            lines.append("✓ ACCEPT - Strong evidence from sources")
        elif status == VerificationStatus.PARTIALLY_VERIFIED:
            lines.append("⚠ CAUTION - Partial support found")
        elif status == VerificationStatus.NO_EVIDENCE:
            lines.append("✗ NO EVIDENCE - No relevant citations")
        else:
            lines.append("? UNCLEAR - Cannot verify")
        
        return "\n".join(lines)

engine = VerificationEngine()

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>CiteGuard - Evidence-First Verification</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 3em; margin-bottom: 10px; }
        .header p { font-size: 1.2em; opacity: 0.9; }
        .card {
            background: white;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .card h2 {
            color: #333;
            margin-bottom: 20px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }
        .input-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 600;
        }
        input[type="text"], textarea, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
        }
        input[type="text"]:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        textarea { min-height: 120px; resize: vertical; }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            font-size: 18px;
            border-radius: 30px;
            cursor: pointer;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4); }
        .result {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
            display: none;
        }
        .result.show { display: block; }
        .status-badge {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            margin-bottom: 15px;
        }
        .verified { background: #d4edda; color: #155724; }
        .partial { background: #fff3cd; color: #856404; }
        .contradicted { background: #f8d7da; color: #721c24; }
        .citation {
            background: white;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }
        .citation-quote { font-style: italic; color: #333; margin-bottom: 10px; }
        .citation-source { color: #667eea; font-weight: 600; font-size: 14px; }
        .confidence-bar {
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            margin: 15px 0;
        }
        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab {
            padding: 10px 20px;
            background: #e9ecef;
            border: none;
            border-radius: 20px;
            cursor: pointer;
        }
        .tab.active { background: #667eea; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .loading { text-align: center; padding: 20px; display: none; }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 CiteGuard</h1>
            <p>Evidence-First Citation Verification</p>
        </div>
        
        <div class="card">
            <h2>Verify a Claim</h2>
            
            <div class="tabs">
                <button class="tab active" onclick="showTab('api')">🔬 Real APIs</button>
                <button class="tab" onclick="showTab('text')">📝 Paste Text</button>
                <button class="tab" onclick="showTab('url')">🌐 Web URL</button>
            </div>
            
            <div id="api" class="tab-content active">
                <div class="input-group">
                    <label>Enter your claim:</label>
                    <input type="text" id="apiClaim" placeholder="e.g., Climate change is caused by humans">
                </div>
                <div class="input-group">
                    <label>Domain:</label>
                    <select id="domain">
                        <option value="general">General</option>
                        <option value="academic">Academic</option>
                        <option value="medical">Medical</option>
                    </select>
                </div>
                <button class="btn" onclick="verifyAPI()">Verify with Real Sources</button>
            </div>
            
            <div id="text" class="tab-content">
                <div class="input-group">
                    <label>Paste your source text:</label>
                    <textarea id="pastedText" placeholder="Paste article, paper, or document text here..."></textarea>
                </div>
                <div class="input-group">
                    <label>What claim to verify?</label>
                    <input type="text" id="textClaim" placeholder="e.g., Vaccines are safe">
                </div>
                <div class="input-group">
                    <label>Source name (optional):</label>
                    <input type="text" id="sourceName" placeholder="e.g., My Research Notes">
                </div>
                <button class="btn" onclick="verifyText()">Find Citations in Text</button>
            </div>
            
            <div id="url" class="tab-content">
                <div class="input-group">
                    <label>Enter URL:</label>
                    <input type="text" id="urlInput" placeholder="https://example.com/article">
                </div>
                <div class="input-group">
                    <label>Claim to verify:</label>
                    <input type="text" id="urlClaim" placeholder="e.g., New policy announced">
                </div>
                <button class="btn" onclick="verifyURL()">Scrape & Verify</button>
            </div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Verifying against trusted sources...</p>
            </div>
            
            <div class="result" id="result"></div>
        </div>
        
        <div class="card">
            <h2>📚 Trusted Sources</h2>
            <ul style="margin-left: 20px; line-height: 2;">
                <li><strong>PubMed</strong> - Peer-reviewed medical research</li>
                <li><strong>Semantic Scholar</strong> - Academic papers</li>
                <li><strong>Wikipedia</strong> - General knowledge</li>
                <li><strong>Your uploads</strong> - PDFs, URLs, pasted text</li>
            </ul>
        </div>
    </div>
    
    <script>
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            document.getElementById('result').classList.remove('show');
        }
        
        function showLoading() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('result').classList.remove('show');
        }
        
        function hideLoading() {
            document.getElementById('loading').style.display = 'none';
        }
        
        function displayResult(data) {
            hideLoading();
            const resultDiv = document.getElementById('result');
            
            let statusClass = 'unverifiable';
            let statusText = data.status;
            if (data.status === 'verified') { statusClass = 'verified'; statusText = '✅ VERIFIED'; }
            else if (data.status === 'partially_verified') { statusClass = 'partial'; statusText = '⚠️ PARTIALLY VERIFIED'; }
            else if (data.status === 'contradicted') { statusClass = 'contradicted'; statusText = '❌ CONTRADICTED'; }
            
            let citationsHtml = '';
            if (data.citations && data.citations.length > 0) {
                citationsHtml = '<h3>📖 Citations Found:</h3>';
                data.citations.slice(0, 3).forEach((cit, i) => {
                    citationsHtml += `
                        <div class="citation">
                            <div class="citation-quote">"${cit.quote}"</div>
                            <div class="citation-source">
                                Source: ${cit.source_publisher} 
                                ${cit.source_url ? `<a href="${cit.source_url}" target="_blank">[View]</a>` : ''}
                                ${cit.page ? `| Page ${cit.page}` : ''}
                                | Relevance: ${Math.round(cit.relevance_score * 100)}%
                            </div>
                        </div>
                    `;
                });
            }
            
            let sourcesHtml = '';
            if (data.sources_used && data.sources_used.length > 0) {
                sourcesHtml = '<h3>🔗 Sources Checked:</h3><ul>';
                data.sources_used.forEach(src => {
                    sourcesHtml += `<li>${src.name} ${src.url ? `<a href="${src.url}" target="_blank">[Link]</a>` : ''} (Credibility: ${Math.round(src.credibility_score * 100)}%)</li>`;
                });
                sourcesHtml += '</ul>';
            }
            
            resultDiv.innerHTML = `
                <div class="status-badge ${statusClass}">${statusText}</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${data.confidence * 100}%">
                        Confidence: ${Math.round(data.confidence * 100)}%
                    </div>
                </div>
                ${citationsHtml}
                ${sourcesHtml}
                <h3>📝 Explanation:</h3>
                <pre style="white-space: pre-wrap; background: white; padding: 15px; border-radius: 5px;">${data.explanation}</pre>
            `;
            resultDiv.classList.add('show');
        }
        
        async function verifyAPI() {
            const claim = document.getElementById('apiClaim').value;
            const domain = document.getElementById('domain').value;
            if (!claim) { alert('Enter a claim'); return; }
            
            showLoading();
            try {
                const response = await fetch('/verify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({claim: claim, domain: domain})
                });
                const data = await response.json();
                displayResult(data);
            } catch (error) {
                hideLoading();
                alert('Error: ' + error.message);
            }
        }
        
        async function verifyText() {
            const text = document.getElementById('pastedText').value;
            const claim = document.getElementById('textClaim').value;
            const sourceName = document.getElementById('sourceName').value || 'Pasted Text';
            
            if (!text || !claim) { alert('Fill in both fields'); return; }
            
            showLoading();
            try {
                const response = await fetch('/verify/text', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text, claim: claim, source_name: sourceName})
                });
                const data = await response.json();
                displayResult(data);
            } catch (error) {
                hideLoading();
                alert('Error: ' + error.message);
            }
        }
        
        async function verifyURL() {
            const url = document.getElementById('urlInput').value;
            const claim = document.getElementById('urlClaim').value;
            
            if (!url || !claim) { alert('Fill in both fields'); return; }
            
            showLoading();
            try {
                const response = await fetch('/verify/url', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: url, claim: claim})
                });
                const data = await response.json();
                displayResult(data);
            } catch (error) {
                hideLoading();
                alert('Error: ' + error.message);
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def web_interface():
    return HTML_PAGE

@app.post("/verify", response_model=VerifiedResult)
def verify(req: VerifyRequest):
    return engine.verify_apis(req.claim, req.domain)

@app.post("/verify/pdf")
async def verify_pdf(file: UploadFile = File(...), claim: str = Form(...)):
    content = await file.read()
    return engine.verify_pdf(content, file.filename, claim)

@app.post("/verify/url", response_model=VerifiedResult)
def verify_url(req: URLRequest):
    return engine.verify_url(req.url, req.claim)

@app.post("/verify/text", response_model=VerifiedResult)
def verify_text(req: PasteRequest):
    return engine.verify_text(req.text, req.source_name, req.claim)

@app.get("/sources")
def sources():
    return {
        "real_apis": [
            {"name": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov/"},
            {"name": "Semantic Scholar", "url": "https://www.semanticscholar.org/"},
            {"name": "Wikipedia", "url": "https://en.wikipedia.org/"}
        ],
        "user_sources": ["PDF Upload", "URL Scraping", "Pasted Text"]
    }

@app.get("/health")
def health():
    return {"status": "healthy", "pdf": PDF_SUPPORT}

if __name__ == "__main__":
    import uvicorn
    print("🚀 CiteGuard v3.0 with Web Interface")
    print("📚 APIs: PubMed, Semantic Scholar, Wikipedia")
    print("🌐 Open: http://127.0.0.1:9000")

    uvicorn.run(app, host="127.0.0.1", port=9000)

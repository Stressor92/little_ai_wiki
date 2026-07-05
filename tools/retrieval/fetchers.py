"""
API-Clients für PubMed, PubMed Central, DOAJ, PLOS
Alle asynchron mit Rate-Limiting und Retry-Logik
"""

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime

import aiohttp

from tools.shared.config import NCBI_CONFIG, DOAJ_CONFIG, PLOS_CONFIG

log = logging.getLogger(__name__)


# ─── Basis-Client ─────────────────────────────────────────────────────────────

class RateLimitedClient:
    """Async HTTP-Client mit Rate-Limiting und Retry."""

    def __init__(self, rate_limit: float, session: aiohttp.ClientSession):
        self.rate_limit = rate_limit
        self.session = session
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def get(self, url: str, params: Dict = None, **kwargs) -> Optional[aiohttp.ClientResponse]:
        async with self._lock:
            # Rate-Limiting
            now = asyncio.get_event_loop().time()
            wait = (1.0 / self.rate_limit) - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = asyncio.get_event_loop().time()

        for attempt in range(3):
            try:
                resp = await self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30), **kwargs)
                if resp.status == 429:  # Too Many Requests
                    wait_time = 5 * (attempt + 1)
                    log.warning(f"Rate limit hit, warte {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                return resp
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                log.warning(f"Request fehlgeschlagen (Versuch {attempt+1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        return None


# ─── PubMed Fetcher ───────────────────────────────────────────────────────────

class PubMedFetcher:
    """Sucht in PubMed via E-Utilities API."""

    SOURCE = "pubmed"

    def __init__(self, client: RateLimitedClient):
        self.client = client
        self.base = NCBI_CONFIG["base_url"]
        self.email = NCBI_CONFIG["email"]
        self.api_key = NCBI_CONFIG["api_key"]

    def _base_params(self) -> Dict:
        p = {"tool": "health_wiki_builder", "email": self.email}
        if self.api_key:
            p["api_key"] = self.api_key
        return p

    async def search(self, query: str, max_results: int = 50) -> List[str]:
        """Gibt PMIDs zurück."""
        params = {
            **self._base_params(),
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
            # Nur englische Artikel
            "filter": "lang.english",
        }
        resp = await self.client.get(f"{self.base}/esearch.fcgi", params=params)
        if not resp:
            return []
        try:
            data = await resp.json(content_type=None)
            ids = data.get("esearchresult", {}).get("idlist", [])
            log.info(f"PubMed: {len(ids)} Treffer für '{query[:50]}'")
            return ids
        except Exception as e:
            log.error(f"PubMed search parse error: {e}")
            return []

    async def fetch_details(self, pmids: List[str]) -> List[Dict]:
        """Holt Metadaten für PMIDs via eFetch."""
        if not pmids:
            return []

        papers = []
        # In Batches von 100
        for i in range(0, len(pmids), 100):
            batch = pmids[i:i+100]
            params = {
                **self._base_params(),
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "rettype": "abstract",
            }
            resp = await self.client.get(f"{self.base}/efetch.fcgi", params=params)
            if not resp:
                continue
            text = await resp.text()
            papers.extend(self._parse_pubmed_xml(text))

        return papers

    def _parse_pubmed_xml(self, xml_text: str) -> List[Dict]:
        """Parst PubMed XML-Response."""
        papers = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            log.error(f"XML Parse Error: {e}")
            return []

        for article in root.findall(".//PubmedArticle"):
            try:
                p = self._parse_article(article)
                if p:
                    papers.append(p)
            except Exception as e:
                log.debug(f"Article parse error: {e}")
        return papers

    def _parse_article(self, article) -> Optional[Dict]:
        medline = article.find("MedlineCitation")
        if medline is None:
            return None

        pmid = self._text(medline, "PMID")
        art = medline.find("Article")
        if art is None:
            return None

        title = self._text(art, "ArticleTitle")
        abstract_parts = art.findall(".//AbstractText")
        abstract = " ".join(t.text or "" for t in abstract_parts if t.text)

        # Autoren
        authors = []
        for a in art.findall(".//Author"):
            last = self._text(a, "LastName") or ""
            first = self._text(a, "ForeName") or ""
            if last:
                authors.append(f"{last}, {first}".strip(", "))

        # Journal
        journal = self._text(art, ".//Title") or self._text(art, ".//ISOAbbreviation") or ""

        # Jahr
        year = None
        pub_date = art.find(".//PubDate")
        if pub_date is not None:
            year_elem = pub_date.find("Year")
            if year_elem is not None:
                try:
                    year = int(year_elem.text)
                except (ValueError, TypeError):
                    pass

        # DOI
        doi = None
        for id_elem in article.findall(".//ArticleId"):
            if id_elem.get("IdType") == "doi":
                doi = id_elem.text
            if id_elem.get("IdType") == "pmc":
                pmcid = id_elem.text

        # Open Access Check (PMC verfügbar)
        pmcid = None
        for id_elem in article.findall(".//ArticleId"):
            if id_elem.get("IdType") == "pmc":
                pmcid = id_elem.text
                break

        return {
            "source": self.SOURCE,
            "external_id": pmid,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal": journal,
            "year": year,
            "doi": doi,
            "pmid": pmid,
            "pmcid": pmcid,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "fulltext_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else None,
            "is_open_access": bool(pmcid),
            "fetched_at": datetime.now().isoformat(),
        }

    def _text(self, elem, path: str) -> Optional[str]:
        found = elem.find(path)
        return found.text.strip() if found is not None and found.text else None


# ─── PMC Full-Text Fetcher ────────────────────────────────────────────────────

class PMCFetcher:
    """Holt Open-Access Volltexte aus PubMed Central."""

    SOURCE = "pmc"

    def __init__(self, client: RateLimitedClient):
        self.client = client

    async def get_fulltext_url(self, pmcid: str) -> Optional[str]:
        """Gibt PDF-URL zurück falls verfügbar."""
        url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
        resp = await self.client.get(url, params={"id": pmcid})
        if not resp:
            return None
        text = await resp.text()
        try:
            root = ET.fromstring(text)
            for link in root.findall(".//link"):
                if link.get("format") == "pdf":
                    href = link.get("href", "")
                    # FTP zu HTTPS konvertieren
                    if href.startswith("ftp://"):
                        href = href.replace("ftp://", "https://", 1)
                    return href
        except ET.ParseError:
            pass
        return None


# ─── DOAJ Fetcher ─────────────────────────────────────────────────────────────

class DOAJFetcher:
    """Directory of Open Access Journals API."""

    SOURCE = "doaj"

    def __init__(self, client: RateLimitedClient):
        self.client = client
        self.base = DOAJ_CONFIG["base_url"]

    async def search(self, query: str, max_results: int = 50) -> List[Dict]:
        """Sucht im DOAJ und gibt direkt Paper-Dicts zurück."""
        params = {
            "q": query,
            "pageSize": min(max_results, 100),
            "sort": "score",
        }
        resp = await self.client.get(f"{self.base}/search/articles/{query}", params={"pageSize": min(max_results, 100)})
        if not resp:
            return []
        try:
            data = await resp.json(content_type=None)
            results = data.get("results", [])
            log.info(f"DOAJ: {len(results)} Treffer für '{query[:50]}'")
            return [self._parse_result(r) for r in results if r]
        except Exception as e:
            log.error(f"DOAJ parse error: {e}")
            return []

    def _parse_result(self, r: Dict) -> Dict:
        bibjson = r.get("bibjson", {})
        authors = [a.get("name", "") for a in bibjson.get("author", [])]
        
        year = None
        date = bibjson.get("year") or bibjson.get("start_page")
        if bibjson.get("year"):
            try:
                year = int(bibjson["year"])
            except (ValueError, TypeError):
                pass

        doi = None
        fulltext_url = None
        for id_entry in bibjson.get("identifier", []):
            if id_entry.get("type") == "doi":
                doi = id_entry.get("id")
        for link in bibjson.get("link", []):
            if link.get("type") in ("fulltext", "pdf"):
                fulltext_url = link.get("url")

        return {
            "source": self.SOURCE,
            "external_id": r.get("id", ""),
            "title": bibjson.get("title", ""),
            "abstract": bibjson.get("abstract", ""),
            "authors": authors,
            "journal": bibjson.get("journal", {}).get("title", ""),
            "year": year,
            "doi": doi,
            "url": fulltext_url or (f"https://doi.org/{doi}" if doi else ""),
            "fulltext_url": fulltext_url,
            "is_open_access": True,  # DOAJ = per Definition Open Access
            "fetched_at": datetime.now().isoformat(),
        }


# ─── PLOS Fetcher ─────────────────────────────────────────────────────────────

class PLOSFetcher:
    """Public Library of Science Solr API."""

    SOURCE = "plos"

    def __init__(self, client: RateLimitedClient):
        self.client = client
        self.base = PLOS_CONFIG["base_url"]

    async def search(self, query: str, max_results: int = 50) -> List[Dict]:
        params = {
            "q": query,
            "fl": "id,title_display,abstract,author_display,journal,publication_date,doi,article_type",
            "rows": min(max_results, 100),
            "wt": "json",
            "sort": "score desc",
        }
        resp = await self.client.get(f"{self.base}/search", params=params)
        if not resp:
            return []
        try:
            data = await resp.json(content_type=None)
            docs = data.get("response", {}).get("docs", [])
            log.info(f"PLOS: {len(docs)} Treffer für '{query[:50]}'")
            return [self._parse_doc(d) for d in docs]
        except Exception as e:
            log.error(f"PLOS parse error: {e}")
            return []

    def _parse_doc(self, d: Dict) -> Dict:
        year = None
        pub_date = d.get("publication_date", "")
        if pub_date:
            try:
                year = int(pub_date[:4])
            except (ValueError, TypeError):
                pass

        doi = d.get("doi", "")
        abstract = d.get("abstract", [])
        if isinstance(abstract, list):
            abstract = " ".join(abstract)

        return {
            "source": self.SOURCE,
            "external_id": d.get("id", doi),
            "title": d.get("title_display", ""),
            "abstract": abstract,
            "authors": d.get("author_display", []),
            "journal": d.get("journal", "PLOS"),
            "year": year,
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi else "",
            "fulltext_url": f"https://journals.plos.org/plosone/article?id={doi}" if doi else "",
            "pdf_url": f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable" if doi else "",
            "is_open_access": True,  # PLOS = komplett Open Access
            "fetched_at": datetime.now().isoformat(),
        }

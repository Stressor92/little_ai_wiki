"""
Pipeline: Fetch → Score → Store → Index → Download → Wiki
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List

import aiohttp

from tools.shared.config import DB_PATH, OUTPUT_DIR, RAW_DIR, INDEX_DIR, WIKI_DIR, RAW_SOURCES
from tools.shared.database import init_db, upsert_paper, get_all_papers, log_search, get_stats
from tools.retrieval.fetchers import PubMedFetcher, PMCFetcher, DOAJFetcher, PLOSFetcher, RateLimitedClient
from tools.shared.relevance import filter_and_rank
from tools.retrieval.downloader import download_batch
from tools.indexing.indexer import build_index
from tools.wiki.wiki_builder import WikiBuilder
from tools.shared.config import INDEX_JSON

log = logging.getLogger(__name__)


class WikiPipeline:

    def __init__(
        self,
        topics: Dict,
        user_profile: Dict,
        output_dir: Path,
        max_per_topic: int = 20,
        min_relevance_score: float = 0.4,
        dry_run: bool = False,
    ):
        self.topics    = topics
        self.profile   = user_profile
        self.out       = output_dir
        self.db        = DB_PATH
        self.max_pt    = max_per_topic
        self.min_score = min_relevance_score
        self.dry_run   = dry_run

    async def run(self) -> None:
        # Verzeichnisse
        for d in [INDEX_DIR, WIKI_DIR] + [RAW_DIR / s for s in RAW_SOURCES]:
            d.mkdir(parents=True, exist_ok=True)

        init_db(self.db)

        async with aiohttp.ClientSession() as session:
            pubmed_client = RateLimitedClient(rate_limit=3, session=session)
            doaj_client   = RateLimitedClient(rate_limit=2, session=session)
            plos_client   = RateLimitedClient(rate_limit=2, session=session)

            pubmed = PubMedFetcher(pubmed_client)
            pmc    = PMCFetcher(pubmed_client)
            doaj   = DOAJFetcher(doaj_client)
            plos   = PLOSFetcher(plos_client)

            total_new = 0
            for topic_id, topic_conf in self.topics.items():
                log.info(f"\n{'─'*60}")
                log.info(f"  {topic_conf['emoji']}  {topic_conf['label']}  [{topic_id}]")
                log.info(f"{'─'*60}")
                new = await self._process_topic(topic_id, topic_conf, pubmed, doaj, plos)
                total_new += new

        log.info(f"\n{'='*60}")
        log.info(f"Neue Paper: {total_new}")
        stats = get_stats(self.db)
        log.info(f"Gesamt: {stats['total']} | OA: {stats['open_access']} | Nach Quelle: {stats['by_source']}")

        if not self.dry_run:
            # ── Downloads ──────────────────────────────────────────────────
            log.info("\n[1/3] Open-Access-Downloads starten...")
            all_papers = get_all_papers(self.db, min_score=self.min_score)
            await download_batch(all_papers, self.db)

            # ── Strukturierter Index ───────────────────────────────────────
            log.info("\n[2/3] Strukturierten Index aufbauen...")
            build_index(self.db, INDEX_JSON, min_score=self.min_score)

            # ── Wiki ───────────────────────────────────────────────────────
            log.info("\n[3/3] Wiki generieren...")
            self.build_wiki_only()

    async def _process_topic(
        self,
        topic_id: str,
        topic_conf: Dict,
        pubmed: PubMedFetcher,
        doaj: DOAJFetcher,
        plos: PLOSFetcher,
    ) -> int:
        all_papers = []

        for query in topic_conf.get("queries", []):
            # PubMed
            pmids = await pubmed.search(query, max_results=30)
            if pmids:
                pm = await pubmed.fetch_details(pmids)
                all_papers.extend(pm)
                log_search(self.db, "pubmed", topic_id, query, len(pm))

            # DOAJ
            dj = await doaj.search(query, max_results=20)
            all_papers.extend(dj)
            log_search(self.db, "doaj", topic_id, query, len(dj))

            # PLOS
            pl = await plos.search(query, max_results=20)
            all_papers.extend(pl)
            log_search(self.db, "plos", topic_id, query, len(pl))

        all_papers = self._deduplicate(all_papers)
        log.info(f"  Gefunden (dedup): {len(all_papers)}")

        relevant = filter_and_rank(
            all_papers, topic_conf,
            min_score=self.min_score,
            max_results=self.max_pt,
        )
        log.info(f"  Relevant (≥{self.min_score}): {len(relevant)}")

        if self.dry_run:
            for p in relevant[:5]:
                log.info(f"    [{p['relevance_score']:.2f}] {p.get('title','')[:70]}")
            return 0

        new = 0
        for p in relevant:
            p["topics"]           = [topic_id]
            p["population_hint"]  = topic_conf.get("population_hint", "adults")
            if upsert_paper(self.db, p):
                new += 1
        return new

    def _deduplicate(self, papers: List[Dict]) -> List[Dict]:
        seen_doi, seen_title, unique = set(), set(), []
        for p in papers:
            doi   = (p.get("doi") or "").strip().lower()
            title = (p.get("title") or "").strip().lower()[:80]
            if doi and doi in seen_doi:
                continue
            if title and title in seen_title:
                continue
            if doi:   seen_doi.add(doi)
            if title: seen_title.add(title)
            unique.append(p)
        return unique

    def build_wiki_only(self) -> None:
        papers = get_all_papers(self.db, min_score=self.min_score)
        log.info(f"Wiki aus {len(papers)} Papern...")
        WikiBuilder(WIKI_DIR).build(papers, self.topics)

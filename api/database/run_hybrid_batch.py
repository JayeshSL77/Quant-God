"""
Hybrid RAG Batch Processor v3 — AI Native Supreme Hedge Fund
PageIndex + Vector + BM25 Pipeline

Architecture:
1. Semantic chunking (section-boundary-aware, table-protected, Q&A-preserved)
2. PageIndex tree generation (hierarchical structure for reasoning-based retrieval)
3. Contextual prefix enrichment (Anthropic-style, with sector + section descriptions)
4. Batch embedding with text-embedding-3-large (3072d)
5. BM25 tsvector auto-population via trigger
6. Resume-safe (skips already-processed documents)
"""

import os
import sys
import time
import json
import argparse
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv(override=True)

from api.database.chunking import SmartChunker, PageIndexBuilder, DocumentChunk
from api.database.embeddings import get_embedding, get_embeddings_batch
from api.database.raptor import RaptorBuilder, ensure_raptor_schema

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'hybrid_batch_v3_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("HybridBatchV3")

DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://postgres:analyezdb77**@analyezdb.cbimec0sg2ch.ap-south-1.rds.amazonaws.com:5432/analyezdb")


# ============================================================
# SECTION DESCRIPTIONS for contextual prefixes
# ============================================================

SECTION_DESCRIPTIONS = {
    # Leadership
    'chairman_letter': "discusses the chairman's vision, strategic direction, and key achievements",
    'md_letter': "contains the Managing Director's review of business performance and outlook",
    'ceo_letter': "presents the CEO's perspective on company strategy and results",
    'cfo_review': "covers the CFO's analysis of financial performance and capital allocation",
    'shareholder_letter': "addresses shareholders on company performance and value creation",
    'board_report': "provides board composition, meetings, and governance structure",
    'directors_report': "statutory report covering operations, financials, and compliance matters",
    'directors_responsibility': "states directors' responsibility for financial statements preparation",

    # Governance
    'corporate_governance': "covers board composition, committees, compliance, and governance practices",
    'committee_reports': "reports from board committees on their activities and findings",
    'audit_committee': "reports on audit committee activities, financial oversight, and auditor interactions",
    'nomination_committee': "covers director appointment criteria and remuneration policies",
    'stakeholder_committee': "addresses investor grievances and stakeholder relationship management",
    'risk_committee': "documents risk management committee activities and risk assessment",
    'csr_committee': "reports on CSR committee activities and social responsibility spending",
    'independent_directors': "contains independent directors' declaration of independence and views",

    # Business Analysis
    'mda': "provides management's analysis of financial condition, operations, and market position",
    'management_review': "contains management's commentary on business performance and trends",
    'business_review': "covers business operations, model, market position, and competitive advantages",
    'industry_overview': "analyzes industry structure, market dynamics, trends, and competitive landscape",
    'macro_economic': "reviews macroeconomic environment, GDP growth, monetary policy impact",
    'competitive_landscape': "analyzes competitive positioning, market share, and strategic advantages",
    'swot_analysis': "examines strengths, weaknesses, opportunities, and threats",

    # Segments & Operations
    'segment_analysis': "breaks down performance by business segment with revenue and margin data",
    'product_portfolio': "describes products, services, market positioning, and innovation pipeline",
    'operational_highlights': "covers operational metrics, efficiency improvements, and capacity utilization",
    'manufacturing': "details manufacturing facilities, capacity, utilization, and expansion plans",
    'geographical_presence': "maps geographical distribution of operations and market coverage",
    'order_book': "reports on order backlog, pipeline strength, and future revenue visibility",
    'key_projects': "highlights significant projects, contract wins, and strategic deals",
    'capex_plan': "details capital expenditure plans, investment priorities, and return expectations",

    # Financial Performance
    'financial_highlights': "summarizes key financial metrics, ratios, and year-over-year changes",
    'revenue_analysis': "analyzes revenue composition, growth drivers, and pricing trends",
    'profitability_analysis': "examines margins, cost structure, and profitability drivers",
    'cost_analysis': "breaks down cost components, optimization efforts, and efficiency gains",
    'working_capital': "covers working capital management, liquidity position, and cash conversion",
    'debt_profile': "analyzes borrowing structure, interest costs, credit ratings, and leverage ratios",
    'dividend_policy': "documents dividend history, payout ratios, and distribution policy",
    'multi_year_summary': "presents multi-year financial data for trend analysis",

    # Financial Statements
    'financial_statements': "contains the full standalone or consolidated financial statements",
    'balance_sheet': "shows assets, liabilities, and equity position at reporting date",
    'profit_loss': "reports revenue, expenses, and profit for the reporting period",
    'cash_flow': "tracks cash flows from operating, investing, and financing activities",
    'changes_in_equity': "shows movements in share capital, reserves, and retained earnings",
    'notes_to_fs': "provides detailed disclosures, accounting policies, and explanatory notes",
    'financial_schedule': "contains supplementary financial schedules and detailed breakdowns",
    'accounting_policies': "describes significant accounting policies and estimation methods",
    'accounting_standards': "covers Ind AS adoption, transitional impacts, and standard updates",

    # Audit & Compliance
    'auditors_report': "contains the independent auditor's opinion on financial statements",
    'auditors_certificate': "provides auditor's certification on specific matters",
    'secretarial_audit': "reports on compliance with corporate laws and governance standards",
    'cost_audit': "covers cost audit findings and cost competitiveness analysis",
    'internal_controls': "describes internal control systems, adequacy, and improvements",
    'compliance_report': "documents regulatory compliance status and certifications",
    'annual_return_extract': "provides extract of annual return as per Companies Act",
    'statutory_forms': "contains statutory forms (MGT, AOC, MGT series) as required by law",
    'particulars_disclosures': "discloses particulars of loans, guarantees, and investments",

    # Risk Management
    'risk_management': "covers enterprise risk management framework and mitigation strategies",
    'specific_risks': "analyzes specific risk categories (operational, financial, market, credit)",
    'risk_factors': "identifies key risks, concerns, and their potential business impact",
    'forex_risk': "details foreign exchange exposure, hedging strategies, and currency impact",
    'internal_financial_controls': "describes adequacy of internal financial control systems",

    # People & Culture
    'human_resources': "covers workforce strategy, talent management, and HR initiatives",
    'employee_engagement': "describes employee engagement programs, culture, and retention",
    'remuneration_details': "discloses director and key management compensation details",
    'esop_details': "provides employee stock option plan details and vesting schedules",
    'diversity_inclusion': "reports on diversity metrics, inclusion programs, and gender balance",
    'health_safety': "covers occupational health, safety performance, and incident metrics",

    # ESG & Sustainability
    'esg_report': "comprehensive ESG metrics, sustainability targets, and progress",
    'environmental': "covers environmental impact, carbon footprint, and green initiatives",
    'csr_report': "details CSR expenditure, projects, and social impact measurement",
    'energy_conservation': "reports on energy efficiency, renewable adoption, and conservation",
    'technology_rd': "covers R&D spending, innovation pipeline, and technology absorption",
    'waste_management': "details waste reduction, recycling rates, and pollution control",
    'social_impact': "reports on community development and social engagement programs",

    # Related Party & Structure
    'related_party_txn': "discloses all related party transactions and their arm's-length nature",
    'subsidiary_info': "provides information on subsidiaries, their performance, and consolidation",
    'joint_ventures': "reports on joint venture and associate company performance",
    'promoter_details': "covers promoter group shareholding, pledges, and restructuring",
    'intercorporate_loans': "discloses inter-corporate deposits, loans, and investments",

    # Shareholding & Investor
    'shareholding_pattern': "shows distribution of shareholding by category and changes",
    'share_capital': "details share capital structure, authorized and paid-up capital",
    'investor_info': "provides investor service details, registrar, and contact information",
    'shareholding_distribution': "breaks down shareholding by holding size and top holders",
    'listing_details': "covers stock exchange listing, trading data, and market performance",
    'general_meeting': "details of AGM/EGM proceedings and resolutions",
    'resolutions': "lists resolutions passed including special resolutions and postal ballots",

    # Strategy
    'outlook': "provides forward-looking statements on growth expectations and guidance",
    'strategic_priorities': "outlines strategic pillars, priorities, and execution roadmap",
    'digital_strategy': "covers digital transformation, technology adoption, and innovation",
    'mergers_acquisitions': "reports on M&A activity, integrations, and inorganic growth",
    'expansion_plans': "details geographic and market expansion plans and timelines",

    # Concall
    'quarterly_results': "presents quarterly financial results and period-specific performance",
    'period_results': "covers financial results for a specific reporting period",
    'opening_remarks': "management's opening statement in earnings call",
    'management_commentary': "management's detailed commentary on business performance",
    'qa_session': "analyst questions and management responses during earnings call",
    'analyst_question': "specific analyst queries on financial and operational metrics",
    'closing_remarks': "concluding statements and forward-looking comments",
    'guidance_update': "updated financial guidance, forecasts, and projections",
    'disclaimer': "forward-looking statement disclaimers and safe harbor notices",
    'moderator': "call operator managing the earnings call proceedings",

    # BSE Filings
    'investor_complaints': "data on investor complaints received, resolved, and pending",
    'meeting_outcome': "outcome of board or shareholder meetings",
    'bulk_block_deals': "disclosure of bulk and block deal transactions",
    'insider_trading': "SEBI insider trading disclosures and declarations",
    'corporate_action': "corporate action details (dividends, bonuses, splits, rights)",
    'integrated_filing': "integrated annual filing submitted to stock exchange",

    # Miscellaneous
    'brand_marketing': "brand strategy, marketing initiatives, and brand valuation",
    'supply_chain': "supply chain optimization, procurement strategy, and vendor management",
    'intellectual_property': "details of patents, trademarks, and IP portfolio",
    'it_infrastructure': "IT systems, cybersecurity, and digital infrastructure",
    'quality_management': "quality certifications, six sigma, and quality improvement programs",
    'awards_recognition': "awards, certifications, and industry recognition received",
    'glossary': "definitions, abbreviations, and terminology used in the document",
    'notice_agm': "notice of annual or extraordinary general meeting",
    'regulatory_disclosure': "specific regulatory disclosures under various laws and rules",
    'preamble': "introductory content, about the company, and document overview",
}


def build_context_prefix(symbol: str, fiscal_year: str, source_table: str,
                         section_type: Optional[str] = None,
                         quarter: Optional[str] = None,
                         company_name: Optional[str] = None,
                         sector: Optional[str] = None,
                         page_start: Optional[int] = None,
                         page_end: Optional[int] = None) -> str:
    """
    Build Anthropic-style contextual prefix for each chunk.
    This prefix gets embedded alongside the chunk, dramatically improving
    retrieval relevance (reduces failure rate by ~67%).
    
    Enhanced with:
    - Company name & sector
    - Section-specific description (what this section typically contains)
    - Page references for traceability
    """
    doc_type = "Annual Report" if source_table == "annual_reports" else \
               "Earnings Call Transcript" if source_table == "concalls" else \
               "BSE Filing"

    # Build company identity
    company_id = symbol
    if company_name:
        company_id = f"{symbol} ({company_name}"
        if sector:
            company_id += f", {sector} sector"
        company_id += ")"

    prefix = f"This is from {company_id}'s {doc_type} for FY{fiscal_year}"

    if quarter:
        prefix += f", {quarter}"

    if section_type:
        section_labels = {k: k.replace('_', ' ').title() for k in SECTION_DESCRIPTIONS}
        # Human-readable overrides
        section_labels.update({
            'mda': "Management Discussion & Analysis",
            'csr_report': "Corporate Social Responsibility Report",
            'esg_report': "ESG & Sustainability Report",
            'profit_loss': "Profit and Loss Statement",
            'cash_flow': "Cash Flow Statement",
            'notes_to_fs': "Notes to Financial Statements",
            'qa_session': "Question & Answer Session",
            'related_party_txn': "Related Party Transactions",
        })
        label = section_labels.get(section_type, section_type.replace('_', ' ').title())
        prefix += f", in the {label} section"

        # Add section description for richer context
        desc = SECTION_DESCRIPTIONS.get(section_type)
        if desc:
            prefix += f". This section {desc}"

    if page_start and page_end:
        if page_start == page_end:
            prefix += f" (page {page_start})"
        else:
            prefix += f" (pages {page_start}-{page_end})"

    prefix += "."
    return prefix


# ============================================================
# LLM CHUNK CONTEXT GENERATOR (Anthropic-Style)
# ============================================================

LLM_CONTEXT_PROMPT = """You are contextualizing a chunk from an Indian company's financial document.
Given the document overview and a specific chunk, write a 1-2 sentence context that:
- Places this chunk within the overall document
- Mentions specific financial figures, names, or metrics found in the chunk
- Helps a retrieval system understand what this chunk is about

Respond with ONLY the context sentence(s), nothing else."""

_llm_client = None

def _get_llm_client():
    global _llm_client
    if _llm_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            from openai import OpenAI
            _llm_client = OpenAI(api_key=api_key)
    return _llm_client


def generate_chunk_context(doc_overview: str, chunk_text: str, 
                           section_type: str = '') -> Optional[str]:
    """
    Generate LLM-powered contextual description for a single chunk.
    Uses GPT-4o-mini (~$0.0001 per chunk).
    
    This replaces the generic templated prefix with a chunk-specific,
    content-aware context sentence. Anthropic's research shows this
    reduces retrieval failure by ~67%.
    """
    client = _get_llm_client()
    if not client:
        return None
    
    try:
        user_msg = (
            f"Document overview:\n{doc_overview[:1000]}\n\n"
            f"Section type: {section_type}\n\n"
            f"Chunk to contextualize:\n{chunk_text[:2000]}"
        )
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": LLM_CONTEXT_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=150,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.debug(f"LLM context generation failed: {e}")
        return None


def generate_chunk_contexts_batch(doc_overview: str, chunks: list,
                                  max_concurrent: int = 5) -> list:
    """
    Generate LLM contexts for multiple chunks.
    Falls back to templated prefix if LLM fails.
    """
    contexts = []
    for chunk in chunks:
        ctx = generate_chunk_context(
            doc_overview, 
            chunk.chunk_text, 
            chunk.section_type or ''
        )
        contexts.append(ctx)
    return contexts


class HybridBatchProcessor:
    """
    Batch processor v4 for the Hybrid RAG pipeline.
    AI Native Supreme Hedge Fund — 11,000 Agent Swarm

    For each document:
    1. Smart chunk with section-awareness, table protection, Q&A preservation
    2. Build PageIndex tree (hierarchical structure index)
    3. Generate LLM chunk context (Anthropic-style) + templated prefix
    4. Batch embed with text-embedding-3-large (3072d)
    5. Store chunk + embedding + metadata + page_index_tree
    6. Build RAPTOR tree (L1 section + L2 document summaries)
    """

    SOURCE_TABLES = {
        'annual_reports': {'text_col': 'summary', 'doc_type': 'annual_report'},
        'concalls': {'text_col': 'transcript', 'doc_type': 'concall'},
    }

    def __init__(self, rate_limit: int = 500, batch_size: int = 10, 
                 use_llm_context: bool = True, use_raptor: bool = True):
        self.conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)
        self.chunker = SmartChunker()
        self.tree_builder = PageIndexBuilder()
        self.raptor_builder = RaptorBuilder(batch_size=batch_size) if use_raptor else None
        self.rate_limit = rate_limit
        self.batch_size = batch_size
        self.use_llm_context = use_llm_context
        self.use_raptor = use_raptor
        self.last_call_time = 0

        # Company metadata cache
        self._company_cache = {}

        self.stats = {
            "documents_processed": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "trees_built": 0,
            "raptor_trees": 0,
            "llm_contexts": 0,
            "errors": 0,
            "start_time": time.time()
        }

    def _rate_limit_wait(self):
        """Rate limit API calls."""
        min_interval = 60.0 / self.rate_limit
        elapsed = time.time() - self.last_call_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_call_time = time.time()

    def _get_company_meta(self, symbol: str) -> Dict:
        """Get company name from annual_reports table (via title)."""
        if symbol in self._company_cache:
            return self._company_cache[symbol]

        try:
            cur = self.conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT title 
                FROM annual_reports 
                WHERE symbol = %s AND title IS NOT NULL
                LIMIT 1
            """, (symbol,))
            row = cur.fetchone()
            cur.close()

            if row and row['title']:
                # Extract company name from title (e.g., "DLF Limited Annual Report 2024")
                meta = {'company_name': row['title'].split(' Annual')[0].split(' annual')[0].strip(), 'sector': ''}
            else:
                meta = {'company_name': symbol, 'sector': ''}
        except Exception:
            meta = {'company_name': symbol, 'sector': ''}

        self._company_cache[symbol] = meta
        return meta

    def get_document_ids(self, source_table: str, limit: Optional[int] = None,
                         symbol: Optional[str] = None) -> List[int]:
        """Get IDs of documents needing processing."""
        cur = self.conn.cursor()

        text_col = self.SOURCE_TABLES[source_table]['text_col']

        conditions = [
            f"{text_col} IS NOT NULL",
            f"LENGTH({text_col}) > 500",
            f"""ar.id NOT IN (
                SELECT DISTINCT source_id 
                FROM document_chunks 
                WHERE source_table = '{source_table}'
            )"""
        ]

        params = []
        if symbol:
            conditions.append("ar.symbol = %s")
            params.append(symbol)

        where = " AND ".join(conditions)
        query = f"""
            SELECT ar.id 
            FROM {source_table} ar
            WHERE {where}
            ORDER BY ar.id DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        cur.execute(query, params)
        ids = [row[0] for row in cur.fetchall()]
        cur.close()
        return ids

    def fetch_document(self, source_table: str, doc_id: int) -> Optional[Dict]:
        """Fetch a single document by ID."""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)

        text_col = self.SOURCE_TABLES[source_table]['text_col']

        query = f"""
            SELECT id, symbol, fiscal_year, 
                   {'quarter,' if source_table == 'concalls' else ''}
                   {text_col} as content,
                   LENGTH({text_col}) as content_length
            FROM {source_table} WHERE id = %s
        """

        cur.execute(query, (doc_id,))
        doc = cur.fetchone()
        cur.close()
        return dict(doc) if doc else None

    def process_document(self, doc: Dict, source_table: str) -> int:
        """
        Process a single document through the full pipeline:
        chunk → PageIndex → LLM context → embed → store → RAPTOR.
        """
        chunks_created = 0

        content = doc.get('content', '')
        if not content or len(content) < 500:
            return 0

        doc_type = self.SOURCE_TABLES[source_table]['doc_type']
        company_meta = self._get_company_meta(doc['symbol'])
        company_name = company_meta.get('company_name', doc['symbol'])

        # 1. SMART CHUNK
        chunks = self.chunker.chunk_document(content, doc_type=doc_type)

        if not chunks:
            return 0

        # 2. BUILD PAGEINDEX TREE
        doc_metadata = {
            'symbol': doc['symbol'],
            'company_name': company_name,
            'doc_type': doc_type,
            'fiscal_year': doc.get('fiscal_year', ''),
            'quarter': doc.get('quarter', ''),
        }
        page_index_tree = self.tree_builder.build_tree(chunks, doc_metadata)
        self.stats["trees_built"] += 1

        # 3. GENERATE CONTEXT (LLM or templated)
        doc_overview = (
            f"{company_name} ({doc['symbol']}) "
            f"{doc_type.replace('_', ' ').title()} FY{doc.get('fiscal_year', 'N/A')}. "
            f"Document has {len(chunks)} sections covering {len(content):,} characters."
        )

        enriched_texts = []
        prefixes = []

        for i, chunk in enumerate(chunks):
            # Templated prefix (always generated as fallback)
            template_prefix = build_context_prefix(
                symbol=doc['symbol'],
                fiscal_year=doc.get('fiscal_year', 'N/A'),
                source_table=source_table,
                section_type=chunk.section_type,
                quarter=doc.get('quarter'),
                company_name=company_name,
                sector=company_meta.get('sector'),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
            )

            # LLM chunk context (Anthropic-style) — content-specific
            llm_context = None
            if self.use_llm_context:
                llm_context = generate_chunk_context(
                    doc_overview, chunk.chunk_text, chunk.section_type or ''
                )
                if llm_context:
                    self.stats["llm_contexts"] += 1

            # Combine: LLM context (if available) + templated prefix
            if llm_context:
                prefix = f"{llm_context}\n{template_prefix}"
            else:
                prefix = template_prefix

            prefixes.append(prefix)
            enriched_text = f"{prefix}\n\n{chunk.chunk_text}"
            enriched_texts.append(enriched_text[:16000])  # Safe Model limit (~4K-8K tokens)

        # 4. BATCH EMBED
        self._rate_limit_wait()
        try:
            embeddings = get_embeddings_batch(enriched_texts, batch_size=self.batch_size)
        except Exception as e:
            logger.error(f"Batch embedding failed for {doc['symbol']}: {e}")
            return 0

        if len(embeddings) != len(chunks):
            logger.error(f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)} chunks")
            return 0

        # 5. STORE CHUNKS + PAGEINDEX TREE
        cur = self.conn.cursor()

        for i, (chunk, embedding, prefix, enriched_text) in enumerate(
                zip(chunks, embeddings, prefixes, enriched_texts)):
            try:
                if not embedding:
                    logger.warning(f"Empty embedding for {doc['symbol']} chunk {i}")
                    continue

                cur.execute("""
                    INSERT INTO document_chunks 
                    (source_table, source_id, symbol, fiscal_year, quarter, 
                     chunk_index, chunk_text, section_type, embedding,
                     doc_type, context_prefix, page_start, page_end)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_table, source_id, chunk_index) 
                    DO UPDATE SET 
                        embedding = EXCLUDED.embedding,
                        chunk_text = EXCLUDED.chunk_text,
                        section_type = EXCLUDED.section_type,
                        doc_type = EXCLUDED.doc_type,
                        context_prefix = EXCLUDED.context_prefix,
                        page_start = EXCLUDED.page_start,
                        page_end = EXCLUDED.page_end
                """, (
                    source_table,
                    doc['id'],
                    doc['symbol'],
                    doc.get('fiscal_year'),
                    doc.get('quarter'),
                    chunk.chunk_index,
                    enriched_text,
                    chunk.section_type,
                    embedding,
                    doc_type,
                    prefix,
                    chunk.page_start,
                    chunk.page_end,
                ))

                chunks_created += 1
                self.stats["embeddings_generated"] += 1

            except Exception as e:
                logger.error(f"Error storing chunk {chunk.chunk_index}: {e}")
                self.stats["errors"] += 1
                continue

        # Store PageIndex tree
        try:
            cur.execute("""
                INSERT INTO page_index_trees (source_table, source_id, symbol, fiscal_year, 
                                              doc_type, tree_json, total_chunks, total_sections)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_table, source_id) DO UPDATE SET
                    tree_json = EXCLUDED.tree_json,
                    total_chunks = EXCLUDED.total_chunks,
                    total_sections = EXCLUDED.total_sections
            """, (
                source_table,
                doc['id'],
                doc['symbol'],
                doc.get('fiscal_year'),
                doc_type,
                json.dumps(page_index_tree),
                page_index_tree['total_chunks'],
                page_index_tree['total_sections'],
            ))
        except Exception as e:
            logger.debug(f"PageIndex tree storage: {e}")

        self.conn.commit()
        cur.close()

        # 6. BUILD RAPTOR TREE (L1 section + L2 document summaries)
        if self.use_raptor and self.raptor_builder and chunks_created > 3:
            try:
                raptor_stats = self.raptor_builder.build_for_document(
                    source_table, doc['id'],
                    doc['symbol'], doc.get('fiscal_year', ''),
                    doc_type, self.conn
                )
                self.stats["raptor_trees"] += 1
            except Exception as e:
                logger.warning(f"RAPTOR tree build failed for {doc['symbol']}: {e}")

        self.stats["chunks_created"] += chunks_created
        return chunks_created

    def run_pipeline(self, source_table: str, limit: Optional[int] = None,
                     symbol: Optional[str] = None):
        """Run the pipeline for a source table."""
        logger.info(f"Fetching document IDs from {source_table}...")
        doc_ids = self.get_document_ids(source_table, limit, symbol)
        total = len(doc_ids)
        logger.info(f"Found {total} documents to process")

        for i, doc_id in enumerate(doc_ids):
            try:
                doc = self.fetch_document(source_table, doc_id)
                if not doc:
                    continue

                chunks = self.process_document(doc, source_table)
                self.stats["documents_processed"] += 1

                if (i + 1) % 5 == 0 or (i + 1) == total:
                    elapsed = time.time() - self.stats["start_time"]
                    rate = self.stats["embeddings_generated"] / elapsed * 60 if elapsed > 0 else 0
                    logger.info(
                        f"[{i+1}/{total}] {doc['symbol']} FY{doc.get('fiscal_year')} — "
                        f"{chunks} chunks | Total: {self.stats['chunks_created']:,} | "
                        f"Trees: {self.stats['trees_built']} | "
                        f"Rate: {rate:.0f} emb/min | Errors: {self.stats['errors']}"
                    )

            except Exception as e:
                logger.error(f"Error processing doc {doc_id}: {e}")
                self.stats["errors"] += 1
                # Reconnect if connection was lost
                try:
                    self.conn = psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=15)
                except:
                    pass
                continue

    def run(self, mode: str = 'all', limit: Optional[int] = None,
            symbol: Optional[str] = None):
        """Main entry point."""
        logger.info("=" * 70)
        logger.info("HYBRID RAG BATCH PROCESSOR v4 — HyDE + RAPTOR + PageIndex + Vector + BM25")
        logger.info("AI Native Supreme Hedge Fund — 11,000 Agent Swarm")
        logger.info(f"Embedding: text-embedding-3-large (3072d)")
        logger.info(f"LLM Context: {'ON' if self.use_llm_context else 'OFF'} | RAPTOR: {'ON' if self.use_raptor else 'OFF'}")
        logger.info(f"Mode: {mode} | Limit: {limit or 'Unlimited'} | Symbol: {symbol or 'ALL'}")
        logger.info("=" * 70)

        # Ensure pgvector
        cur = self.conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        self.conn.commit()
        cur.close()
        logger.info("✅ pgvector ready")

        # Ensure page_index_trees + raptor_summaries tables
        self._ensure_schema()
        if self.use_raptor:
            ensure_raptor_schema(self.conn)

        if mode in ['all', 'embeddings', 'test']:
            logger.info("\n📊 PROCESSING ANNUAL REPORTS")
            self.run_pipeline('annual_reports', limit, symbol)

            logger.info("\n📞 PROCESSING CONCALLS")
            self.run_pipeline('concalls', limit, symbol)

        # Final stats
        elapsed = time.time() - self.stats["start_time"]
        rate = self.stats['embeddings_generated'] / elapsed * 60 if elapsed > 0 else 0

        logger.info("\n" + "=" * 70)
        logger.info("BATCH PROCESSING COMPLETE")
        logger.info(f"  Documents: {self.stats['documents_processed']:,}")
        logger.info(f"  Chunks: {self.stats['chunks_created']:,}")
        logger.info(f"  Embeddings: {self.stats['embeddings_generated']:,}")
        logger.info(f"  PageIndex Trees: {self.stats['trees_built']:,}")
        logger.info(f"  RAPTOR Trees: {self.stats['raptor_trees']:,}")
        logger.info(f"  LLM Contexts: {self.stats['llm_contexts']:,}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"  Time: {elapsed/60:.1f} minutes")
        logger.info(f"  Rate: {rate:.0f} emb/min")

        # Cost estimate (embeddings + LLM context + RAPTOR)
        embed_cost = self.stats['embeddings_generated'] * 4000 / 1_000_000 * 0.13
        llm_cost = self.stats['llm_contexts'] * 0.0001  # ~$0.0001/context
        raptor_cost = self.stats['raptor_trees'] * 0.02  # ~$0.02/doc
        total_cost = embed_cost + llm_cost + raptor_cost
        logger.info(f"  Est. cost: ${total_cost:.2f} (embed: ${embed_cost:.2f}, LLM ctx: ${llm_cost:.2f}, RAPTOR: ${raptor_cost:.2f})")
        logger.info("=" * 70)

    def _ensure_schema(self):
        """Ensure page_index_trees table and vector(3072) column exist."""
        cur = self.conn.cursor()

        # Create page_index_trees table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS page_index_trees (
                id SERIAL PRIMARY KEY,
                source_table VARCHAR(50) NOT NULL,
                source_id INTEGER NOT NULL,
                symbol VARCHAR(20) NOT NULL,
                fiscal_year VARCHAR(10),
                doc_type VARCHAR(30),
                tree_json JSONB NOT NULL,
                total_chunks INTEGER DEFAULT 0,
                total_sections INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_table, source_id)
            );
        """)

        # Create indexes for fast tree retrieval
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_page_index_symbol 
            ON page_index_trees(symbol);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_page_index_tree_json 
            ON page_index_trees USING GIN(tree_json);
        """)

        self.conn.commit()
        cur.close()
        logger.info("✅ Schema ready (page_index_trees table + indexes)")


def main():
    parser = argparse.ArgumentParser(description='Hybrid RAG Batch Processor v3 — PageIndex Edition')
    parser.add_argument('--mode', choices=['all', 'embeddings', 'test'], default='all')
    parser.add_argument('--limit', type=int, help='Limit documents to process')
    parser.add_argument('--symbol', type=str, help='Process only this stock symbol')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size for embeddings')
    args = parser.parse_args()

    if args.mode == 'test':
        args.limit = 3
        logger.info("🧪 TEST MODE — Processing 3 documents")

    processor = HybridBatchProcessor(rate_limit=500, batch_size=args.batch_size)
    processor.run(mode=args.mode, limit=args.limit, symbol=args.symbol)


if __name__ == "__main__":
    main()

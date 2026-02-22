"""
Inwezt — Hedge-Fund-Grade Document Intelligence Engine
AI Native Supreme Hedge Fund — 11,000 Agent Swarm

Ultra-intelligent chunking with:
- 60+ section markers for every part of Indian financial documents
- PageIndex-style hierarchical tree building
- Table-aware splitting (never breaks mid-table)
- Concall Q&A turn detection (preserves analyst-management dialogue)
- Smart contextual overlap (section header + summary, not raw chars)
- Adaptive chunk sizing (2K-6K based on content density)
"""

import re
import json
import hashlib
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DocumentIntelligence")


# ============================================================
# SECTION TAXONOMY — 60+ section types for Indian financial docs
# ============================================================

SECTION_MARKERS = [
    # ── LEADERSHIP & GOVERNANCE ──
    (r"(?i)chairman['']?s?\s+(?:message|letter|statement|address|speech|review)", "chairman_letter"),
    (r"(?i)managing\s+director['']?s?\s+(?:message|letter|statement|address|review)", "md_letter"),
    (r"(?i)(?:ceo|chief\s+executive)['']?s?\s+(?:message|letter|statement|review|address)", "ceo_letter"),
    (r"(?i)(?:cfo|chief\s+financial)['']?s?\s+(?:message|letter|statement|review)", "cfo_review"),
    (r"(?i)letter\s+to\s+(?:the\s+)?shareholders", "shareholder_letter"),
    (r"(?i)board\s+of\s+directors?\s+(?:report|profile|composition)", "board_report"),
    (r"(?i)director['']?s?\s+report", "directors_report"),
    (r"(?i)director['']?s?\s+responsibility\s+statement", "directors_responsibility"),
    (r"(?i)corporate\s+governance\s+(?:report|certificate)", "corporate_governance"),
    (r"(?i)committee\s+(?:reports?|composition|meetings?)", "committee_reports"),
    (r"(?i)audit\s+committee\s+(?:report|composition|charter)", "audit_committee"),
    (r"(?i)nomination\s+(?:and|&)\s+remuneration\s+committee", "nomination_committee"),
    (r"(?i)stakeholder['']?s?\s+relationship\s+committee", "stakeholder_committee"),
    (r"(?i)risk\s+management\s+committee", "risk_committee"),
    (r"(?i)csr\s+committee", "csr_committee"),
    (r"(?i)independent\s+director['']?s?\s+(?:declaration|statement)", "independent_directors"),

    # ── MANAGEMENT DISCUSSION & ANALYSIS ──
    (r"(?i)management\s+discussion\s+(?:and|&)\s+analysis", "mda"),
    (r"(?i)management['']?s?\s+(?:review|commentary|perspective)", "management_review"),
    (r"(?i)business\s+(?:overview|review|performance|description|model)", "business_review"),
    (r"(?i)(?:industry|market)\s+(?:overview|structure|landscape|outlook|analysis)", "industry_overview"),
    (r"(?i)(?:macro[-\s]?economic|economic)\s+(?:overview|environment|review|scenario)", "macro_economic"),
    (r"(?i)competitive\s+(?:landscape|strengths?|advantage|position)", "competitive_landscape"),
    (r"(?i)(?:swot|strengths?\s+(?:and|&)\s+weakness)", "swot_analysis"),

    # ── SEGMENT & OPERATIONS ──
    (r"(?i)segment(?:al|[-\s]wise)?\s+(?:review|analysis|performance|information|reporting)", "segment_analysis"),
    (r"(?i)(?:product|service)\s+(?:portfolio|mix|range|overview|segment)", "product_portfolio"),
    (r"(?i)operational\s+(?:highlights?|review|performance|efficiency)", "operational_highlights"),
    (r"(?i)(?:manufacturing|production|capacity)\s+(?:highlights?|overview|facilities)", "manufacturing"),
    (r"(?i)(?:geographical|regional)\s+(?:presence|distribution|expansion|review)", "geographical_presence"),
    (r"(?i)order\s+(?:book|backlog|pipeline|inflow)", "order_book"),
    (r"(?i)(?:key|select)\s+(?:projects?|contracts?|wins?|deals?)", "key_projects"),
    (r"(?i)(?:capex|capital\s+expenditure|investment)\s+(?:plan|review|outlook)", "capex_plan"),

    # ── FINANCIAL PERFORMANCE ──
    (r"(?i)financial\s+(?:highlights?|summary|overview|performance|review|at\s+a\s+glance)", "financial_highlights"),
    (r"(?i)(?:revenue|sales|income)\s+(?:analysis|breakdown|from\s+operations)", "revenue_analysis"),
    (r"(?i)(?:profitability|margin)\s+(?:analysis|review|trends?)", "profitability_analysis"),
    (r"(?i)(?:cost|expenditure)\s+(?:analysis|structure|management|optimization)", "cost_analysis"),
    (r"(?i)(?:working\s+capital|liquidity|treasury)\s+(?:management|analysis|review)", "working_capital"),
    (r"(?i)(?:debt|borrowing|leverage|capital\s+structure)\s+(?:profile|analysis|management|review)", "debt_profile"),
    (r"(?i)(?:dividend|payout)\s+(?:history|policy|recommendation|distribution)", "dividend_policy"),
    (r"(?i)(?:ten|10|five|5)[-\s]?year\s+(?:financial\s+)?(?:summary|highlights?|data|review)", "multi_year_summary"),

    # ── FINANCIAL STATEMENTS ──
    (r"(?i)(?:standalone|consolidated)\s+(?:financial\s+)?statements?", "financial_statements"),
    (r"(?i)balance\s+sheet|statement\s+of\s+(?:financial\s+)?position", "balance_sheet"),
    (r"(?i)(?:profit\s+(?:and|&)\s+loss|income\s+statement|statement\s+of\s+(?:profit|income))", "profit_loss"),
    (r"(?i)cash\s+flow\s+statement|statement\s+of\s+cash\s+flows?", "cash_flow"),
    (r"(?i)statement\s+of\s+changes\s+in\s+equity", "changes_in_equity"),
    (r"(?i)notes\s+(?:to|forming\s+part\s+of)\s+(?:the\s+)?(?:financial\s+)?(?:statements?|accounts?)", "notes_to_fs"),
    (r"(?i)schedule\s+(?:[IVXLCDM]+|[0-9]+)(?:\s*[-–:])?\s", "financial_schedule"),
    (r"(?i)significant\s+accounting\s+polic(?:y|ies)", "accounting_policies"),
    (r"(?i)(?:accounting|as[-\s]?ind)\s+standards?\s+(?:update|impact|transition)", "accounting_standards"),

    # ── AUDIT & COMPLIANCE ──
    (r"(?i)(?:independent\s+)?auditor['']?s?\s+report", "auditors_report"),
    (r"(?i)(?:statutory\s+)?auditor['']?s?\s+(?:certificate|opinion)", "auditors_certificate"),
    (r"(?i)secretarial\s+audit\s+report", "secretarial_audit"),
    (r"(?i)cost\s+audit(?:or)?['']?s?\s+report", "cost_audit"),
    (r"(?i)internal\s+(?:control|audit)\s+(?:system|framework|report|adequacy)", "internal_controls"),
    (r"(?i)(?:compliance|regulatory)\s+(?:framework|report|certificate)", "compliance_report"),
    (r"(?i)(?:extract\s+of\s+)?annual\s+return", "annual_return_extract"),
    (r"(?i)form\s+(?:mgr|aoc|mgt)[-\s]?[0-9]+", "statutory_forms"),
    (r"(?i)particulars\s+of\s+(?:loan|guarantee|investment|contract)", "particulars_disclosures"),

    # ── RISK MANAGEMENT ──
    (r"(?i)risk\s+management\s+(?:framework|policy|report|review|overview)", "risk_management"),
    (r"(?i)(?:operational|financial|market|credit|liquidity)\s+risk", "specific_risks"),
    (r"(?i)(?:key\s+)?risks?\s+(?:and\s+)?(?:concerns?|factors?|mitigation|outlook)", "risk_factors"),
    (r"(?i)(?:forex|foreign\s+exchange|currency)\s+(?:risk|management|hedging|exposure)", "forex_risk"),
    (r"(?i)internal\s+financial\s+controls?", "internal_financial_controls"),

    # ── PEOPLE & CULTURE ──
    (r"(?i)human\s+(?:resource|capital)\s+(?:development|management|review|highlights?)", "human_resources"),
    (r"(?i)(?:employee|people|talent|workforce)\s+(?:engagement|development|overview|strength)", "employee_engagement"),
    (r"(?i)(?:remuneration|compensation)\s+(?:details?|policy|disclosure|philosophy)", "remuneration_details"),
    (r"(?i)(?:esop|esos|stock\s+option|employee\s+stock)", "esop_details"),
    (r"(?i)diversity\s+(?:and|&)\s+inclusion", "diversity_inclusion"),
    (r"(?i)(?:health|safety|hse|ehs)\s+(?:and|&)?\s*(?:safety|health|environment)?", "health_safety"),

    # ── ESG & SUSTAINABILITY ──
    (r"(?i)(?:esg|sustainability|sustainable\s+development)\s+(?:report|review|framework|goals?|strategy)", "esg_report"),
    (r"(?i)(?:environment(?:al)?|green|carbon|climate)\s+(?:initiatives?|performance|footprint|policy|impact)", "environmental"),
    (r"(?i)corporate\s+social\s+responsibility|csr\s+(?:report|activities|initiatives|expenditure|policy)", "csr_report"),
    (r"(?i)(?:energy\s+conservation|energy\s+audit|renewable\s+energy)", "energy_conservation"),
    (r"(?i)(?:technology|r\s*&\s*d|research\s+(?:and|&)\s+development)\s+(?:absorption|initiatives|spending)", "technology_rd"),
    (r"(?i)(?:water|waste|emission|pollution)\s+(?:management|treatment|reduction|recycling)", "waste_management"),
    (r"(?i)(?:social|community)\s+(?:impact|development|responsibility|engagement|initiatives?)", "social_impact"),

    # ── RELATED PARTY & DISCLOSURES ──
    (r"(?i)related\s+party\s+(?:transactions?|disclosures?)", "related_party_txn"),
    (r"(?i)(?:material\s+)?subsidiary\s+(?:companies|information|performance)", "subsidiary_info"),
    (r"(?i)(?:joint\s+venture|associate\s+compan)", "joint_ventures"),
    (r"(?i)(?:promoter|promotor)\s+(?:holding|group|details)", "promoter_details"),
    (r"(?i)(?:inter[-\s]?corporate|inter[-\s]?company)\s+(?:loan|deposit|investment)", "intercorporate_loans"),

    # ── SHAREHOLDING & INVESTOR ──
    (r"(?i)shareholding\s+pattern", "shareholding_pattern"),
    (r"(?i)(?:share\s+capital|capital\s+structure)\s+(?:history|details|information)", "share_capital"),
    (r"(?i)(?:investor|shareholder)\s+(?:information|communication|relations|grievance)", "investor_info"),
    (r"(?i)(?:distribution\s+of\s+shareholding|top\s+(?:10|ten)\s+shareholders?)", "shareholding_distribution"),
    (r"(?i)(?:stock\s+exchange|listing)\s+(?:information|details|compliance|data)", "listing_details"),
    (r"(?i)(?:general\s+body|agm|egm|annual\s+general)\s+meeting", "general_meeting"),
    (r"(?i)(?:postal\s+ballot|e[-\s]?voting|resolution)", "resolutions"),

    # ── OUTLOOK & STRATEGY ──
    (r"(?i)(?:future\s+)?(?:outlook|guidance|forward[-\s]looking|growth\s+strategy)", "outlook"),
    (r"(?i)(?:strategic\s+)?(?:priorities|initiatives|pillars|roadmap|vision|mission)", "strategic_priorities"),
    (r"(?i)(?:digital|technology|innovation)\s+(?:transformation|strategy|initiatives|journey)", "digital_strategy"),
    (r"(?i)(?:acquisition|merger|m\s*&\s*a|inorganic\s+growth)", "mergers_acquisitions"),
    (r"(?i)(?:expansion|growth|new\s+market)\s+(?:plans?|strategy|initiatives)", "expansion_plans"),

    # ── CONCALL-SPECIFIC ──
    (r"(?i)(?:q(?:uarter)?[-\s]*[1-4]|(?:first|second|third|fourth)\s+quarter)\s+(?:fy|fiscal)?[-\s]*\d{2,4}", "quarterly_results"),
    (r"(?i)(?:financial\s+)?(?:results?|performance)\s+(?:for\s+the\s+)?(?:quarter|q[1-4]|half[-\s]?year|fy)", "period_results"),
    (r"(?i)(?:opening|introductory|welcome)\s+(?:remarks?|comments?|statement)", "opening_remarks"),
    (r"(?i)(?:management|company)\s+(?:commentary|presentation|highlights?|overview)", "management_commentary"),
    (r"(?i)question\s+(?:and|&)\s+answer|q\s*(?:&|and)\s*a\s+session", "qa_session"),
    (r"(?i)(?:analyst|investor|participant)\s+(?:question|query|comment)", "analyst_question"),
    (r"(?i)(?:closing|concluding)\s+(?:remarks?|comments?|statement)", "closing_remarks"),
    (r"(?i)(?:guidance|forecast|projections?)\s+(?:for|update|revision|outlook)", "guidance_update"),
    (r"(?i)(?:disclaimer|safe\s+harbor|forward[-\s]looking\s+statements?)", "disclaimer"),
    (r"(?i)(?:operator|moderator)\s*:", "moderator"),

    # ── BSE FILINGS SPECIFIC ──
    (r"(?i)investor\s+complaints?\s+(?:summary|status|received|resolved|pending)", "investor_complaints"),
    (r"(?i)(?:board|shareholder)\s+meeting\s+(?:outcome|intimation|notice)", "meeting_outcome"),
    (r"(?i)(?:bulk|block)\s+deal\s+(?:disclosure|data|details)", "bulk_block_deals"),
    (r"(?i)(?:insider|sdd|pit)\s+(?:trading|disclosure|transactions?)", "insider_trading"),
    (r"(?i)(?:corporate\s+action|dividend|bonus|split|rights?\s+issue)", "corporate_action"),
    (r"(?i)(?:integrated\s+filing|annual\s+information)", "integrated_filing"),

    # ── MISCELLANEOUS ──
    (r"(?i)(?:brand|marketing|advertising)\s+(?:strategy|overview|initiatives|value)", "brand_marketing"),
    (r"(?i)(?:supply\s+chain|procurement|vendor)\s+(?:management|overview|optimization)", "supply_chain"),
    (r"(?i)(?:intellectual\s+property|patent|trademark)\s+(?:portfolio|details)", "intellectual_property"),
    (r"(?i)(?:information\s+technology|it\s+infrastructure|cyber[-\s]?security)", "it_infrastructure"),
    (r"(?i)(?:quality|six[-\s]?sigma|iso|certification)\s+(?:management|system|assurance)", "quality_management"),
    (r"(?i)(?:awards?|recognition|accolades?|achievements?)", "awards_recognition"),
    (r"(?i)(?:glossary|definitions?|abbreviations?|acronyms?)", "glossary"),
    (r"(?i)(?:notice\s+of|notice\s+for)\s+(?:annual|extra[-\s]?ordinary)", "notice_agm"),
    (r"(?i)(?:report\s+on|disclosure\s+under)\s+(?:section|rule|regulation|clause)", "regulatory_disclosure"),
]


@dataclass
class DocumentChunk:
    """A chunk of a document with rich metadata for hedge-fund-grade retrieval."""
    chunk_index: int
    chunk_text: str
    section_type: Optional[str] = None
    section_hierarchy: List[str] = field(default_factory=list)  # e.g. ["Financial Statements", "Balance Sheet"]
    char_start: int = 0
    char_end: int = 0
    page_start: int = 0
    page_end: int = 0
    is_table: bool = False
    is_qa_turn: bool = False
    speaker: Optional[str] = None  # for concall Q&A
    confidence: float = 1.0  # section detection confidence


@dataclass
class PageIndexNode:
    """A node in the PageIndex hierarchical tree — like an intelligent TOC."""
    node_id: str
    title: str
    level: int  # 0 = root, 1 = major section, 2 = subsection, etc.
    start_page: int
    end_page: int
    summary: str = ""
    section_type: Optional[str] = None
    children: List['PageIndexNode'] = field(default_factory=list)
    chunk_ids: List[int] = field(default_factory=list)  # chunks belonging to this node

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "level": self.level,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "summary": self.summary,
            "section_type": self.section_type,
            "chunk_ids": self.chunk_ids,
            "children": [c.to_dict() for c in self.children],
        }


# ============================================================
# TABLE DETECTION
# ============================================================

TABLE_PATTERNS = [
    # Markdown-style tables
    re.compile(r'(?:^|\n)\s*\|.*\|.*\|', re.MULTILINE),
    # Tab/comma separated data with numbers (financial tables)
    re.compile(r'(?:^|\n)[\w\s]+\t[\d,.\-()]+(?:\t[\d,.\-()]+)+', re.MULTILINE),
    # Repeated structure: label followed by numbers (common in financial statements)
    re.compile(r'(?:^|\n)\s*[A-Za-z][A-Za-z\s]{5,40}\s{2,}[\d,.\-()]+\s{2,}[\d,.\-()]+', re.MULTILINE),
    # Currency + number patterns (₹ or Rs or INR followed by numbers)
    re.compile(r'(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?(?:\s+(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?){2,}', re.MULTILINE),
]


def _detect_table_regions(text: str) -> List[Tuple[int, int]]:
    """Find contiguous table regions in text. Returns (start, end) pairs."""
    table_lines = set()

    for pattern in TABLE_PATTERNS:
        for match in pattern.finditer(text):
            line_start = text.rfind('\n', 0, match.start()) + 1
            line_end = text.find('\n', match.end())
            if line_end == -1:
                line_end = len(text)
            # Mark lines as table
            for i in range(line_start, line_end):
                table_lines.add(i)

    if not table_lines:
        return []

    # Merge into contiguous regions
    sorted_positions = sorted(table_lines)
    regions = []
    start = sorted_positions[0]
    prev = start

    for pos in sorted_positions[1:]:
        if pos - prev > 2:  # gap > 2 chars = new region
            regions.append((start, prev + 1))
            start = pos
        prev = pos
    regions.append((start, prev + 1))

    # Expand regions to include surrounding context (2 lines before/after)
    expanded = []
    for start, end in regions:
        # Only keep substantial tables (> 100 chars)
        if end - start > 100:
            # Find line boundaries
            line_start = text.rfind('\n', 0, max(0, start - 100))
            line_end = text.find('\n', min(len(text), end + 100))
            expanded.append((max(0, line_start + 1), min(len(text), line_end if line_end > 0 else len(text))))

    return expanded


# ============================================================
# CONCALL Q&A DETECTION
# ============================================================

QA_SPEAKER_PATTERNS = [
    # "Analyst Name -- Firm Name" or "Name - Firm"
    re.compile(r'^([A-Z][a-zA-Z.\s]+?)(?:\s+[-–—]+\s+.+?)?\s*$', re.MULTILINE),
    # "Q: question text" or "A: answer text"
    re.compile(r'^([QA])\s*[:\.]\s*(.+)', re.MULTILINE),
    # "Participant:" or "Management:" patterns
    re.compile(r'^((?:Analyst|Participant|Management|Operator|Moderator|Speaker|Mr\.|Mrs\.|Ms\.|Dr\.)\s*[A-Za-z\s.]+?)\s*[:]\s*', re.MULTILINE),
    # "Name (Designation):" pattern
    re.compile(r'^([A-Z][a-zA-Z.\s]+?)\s*\([^)]+\)\s*:\s*', re.MULTILINE),
]


def _detect_qa_turns(text: str) -> List[Dict]:
    """Detect Q&A turns in concall transcripts. Returns list of {start, end, speaker, is_question}."""
    turns = []

    # Check if this looks like a concall transcript
    qa_indicators = sum(1 for p in QA_SPEAKER_PATTERNS if p.search(text))
    if qa_indicators < 2:
        return []

    # Find all speaker changes
    speaker_positions = []
    for pattern in QA_SPEAKER_PATTERNS:
        for match in pattern.finditer(text):
            speaker_positions.append({
                'pos': match.start(),
                'speaker': match.group(1).strip(),
                'is_question': any(
                    kw in match.group(0).lower()
                    for kw in ['analyst', 'participant', 'q:', 'question']
                ),
            })

    speaker_positions.sort(key=lambda x: x['pos'])

    # Build turns from speaker positions
    for i, sp in enumerate(speaker_positions):
        end_pos = speaker_positions[i + 1]['pos'] if i + 1 < len(speaker_positions) else len(text)
        if end_pos - sp['pos'] > 50:  # minimum turn length
            turns.append({
                'start': sp['pos'],
                'end': end_pos,
                'speaker': sp['speaker'],
                'is_question': sp['is_question'],
            })

    return turns


# ============================================================
# SMART CHUNKER — Hedge-Fund Grade
# ============================================================

class SmartChunker:
    """
    Ultra-intelligent document chunker for the AI Native Supreme Hedge Fund.

    Key capabilities:
    1. Section-boundary-aware splitting (never breaks mid-section unnecessarily)
    2. Table protection (tables kept atomic)
    3. Q&A turn preservation (concall dialogue intact)
    4. Adaptive sizing (2K-6K chars based on content density)
    5. Smart overlap (section header + context sentence, not raw char overlap)
    6. 60+ section type detection for Indian financial documents
    7. PageIndex-style hierarchical tree generation
    """

    CHARS_PER_PAGE = 3000  # Average chars per page for page number estimation

    def __init__(self,
                 target_chunk_size: int = 4000,
                 min_chunk_size: int = 600,
                 max_chunk_size: int = 6000,
                 overlap_sentences: int = 2):
        self.target_chunk_size = target_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_sentences = overlap_sentences

    # ── Section Detection ──

    def _identify_section(self, text: str, check_chars: int = 800) -> Tuple[Optional[str], float]:
        """
        Identify section type from text with confidence score.
        Returns (section_type, confidence).
        """
        check_text = text[:check_chars]
        best_match = None
        best_pos = float('inf')

        for pattern, section_type in SECTION_MARKERS:
            match = re.search(pattern, check_text)
            if match and match.start() < best_pos:
                best_pos = match.start()
                best_match = section_type

        if best_match:
            # Higher confidence if match is at the very start
            confidence = 1.0 if best_pos < 50 else 0.8 if best_pos < 200 else 0.6
            return best_match, confidence

        return None, 0.0

    def _find_section_boundaries(self, text: str) -> List[Dict]:
        """
        Find all section boundaries in document.
        Returns sorted list of {pos, section_type, title, confidence}.
        """
        boundaries = []
        seen_positions = set()

        for pattern, section_type in SECTION_MARKERS:
            for match in re.finditer(pattern, text):
                # Deduplicate nearby matches (within 100 chars)
                pos = match.start()
                if any(abs(pos - sp) < 100 for sp in seen_positions):
                    continue
                seen_positions.add(pos)

                # Extract the actual section title (the line containing the match)
                line_start = text.rfind('\n', 0, pos)
                line_end = text.find('\n', pos)
                title = text[line_start + 1:line_end].strip() if line_end > 0 else text[line_start + 1:pos + 100].strip()
                title = title[:150]  # truncate long titles

                boundaries.append({
                    'pos': pos,
                    'section_type': section_type,
                    'title': title,
                    'confidence': 1.0 if pos == 0 or text[pos - 1] == '\n' else 0.7,
                })

        boundaries.sort(key=lambda x: x['pos'])
        return boundaries

    # ── Break Point Finding ──

    def _find_break_point(self, text: str, target_pos: int, table_regions: List[Tuple[int, int]]) -> int:
        """
        Find optimal break point near target_pos.
        NEVER breaks inside a table region.
        Priority: section boundary > paragraph > sentence > line > word
        """
        search_range = 800
        start = max(0, target_pos - search_range)
        end = min(len(text), target_pos + search_range)
        search_text = text[start:end]

        # Check if target is inside a table — if so, break AFTER the table
        for t_start, t_end in table_regions:
            if t_start < target_pos < t_end:
                return min(len(text), t_end + 1)

        # 1. Section boundary (strongest break)
        for pattern, _ in SECTION_MARKERS:
            match = re.search(pattern, search_text)
            if match:
                return start + match.start()

        # 2. Paragraph break (double newline)
        para_breaks = list(re.finditer(r'\n\s*\n', search_text))
        if para_breaks:
            # Pick the one closest to target
            best = min(para_breaks, key=lambda m: abs((start + m.start()) - target_pos))
            return start + best.end()

        # 3. Sentence break
        sent_breaks = list(re.finditer(r'[.!?]\s+(?=[A-Z])', search_text))
        if sent_breaks:
            best = min(sent_breaks, key=lambda m: abs((start + m.start()) - target_pos))
            return start + best.start() + 1

        # 4. Line break
        line_breaks = list(re.finditer(r'\n', search_text))
        if line_breaks:
            best = min(line_breaks, key=lambda m: abs((start + m.start()) - target_pos))
            return start + best.end()

        # 5. Word boundary (last resort)
        word_break = re.search(r'\s+', text[target_pos:target_pos + 200])
        if word_break:
            return target_pos + word_break.end()

        return target_pos

    # ── Smart Overlap ──

    def _build_overlap_prefix(self, previous_chunk: DocumentChunk, section_boundaries: List[Dict]) -> str:
        """
        Build smart overlap: section header + last 1-2 sentences from previous chunk.
        Much more informative than blind char overlap.
        """
        prefix_parts = []

        # Add current section header if known
        if previous_chunk.section_hierarchy:
            prefix_parts.append(f"[{' > '.join(previous_chunk.section_hierarchy)}]")

        # Add last 2 sentences from previous chunk
        prev_text = previous_chunk.chunk_text.strip()
        sentences = re.split(r'(?<=[.!?])\s+', prev_text)
        if len(sentences) >= 2:
            overlap_text = ' '.join(sentences[-self.overlap_sentences:])
            prefix_parts.append(overlap_text[:300])

        return '\n'.join(prefix_parts) + '\n\n' if prefix_parts else ''

    # ── Merge Small Chunks ──

    def _merge_small_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Merge fragments under min_chunk_size with adjacent chunks in same section."""
        if len(chunks) <= 1:
            return chunks

        merged = [chunks[0]]

        for chunk in chunks[1:]:
            prev = merged[-1]
            # Merge if either is too small AND they're in the same section
            if (len(chunk.chunk_text) < self.min_chunk_size or len(prev.chunk_text) < self.min_chunk_size) \
                    and prev.section_type == chunk.section_type \
                    and len(prev.chunk_text) + len(chunk.chunk_text) < self.max_chunk_size:
                # Merge into previous
                prev.chunk_text += '\n\n' + chunk.chunk_text
                prev.char_end = chunk.char_end
                prev.page_end = chunk.page_end
            else:
                merged.append(chunk)

        # Re-index
        for i, chunk in enumerate(merged):
            chunk.chunk_index = i

        return merged

    # ── Main Chunking Methods ──

    def chunk_document(self, text: str, doc_type: str = 'annual_report') -> List[DocumentChunk]:
        """
        Intelligently chunk a document with full structure awareness.

        Args:
            text: Full document text
            doc_type: 'annual_report', 'concall', or 'bse_filing'

        Returns:
            List of DocumentChunk objects with rich metadata
        """
        if not text or len(text.strip()) < 100:
            return [DocumentChunk(
                chunk_index=0, chunk_text=text or "",
                section_type="unknown", char_start=0, char_end=len(text or "")
            )]

        # For concalls: use Q&A-aware chunking
        if doc_type == 'concall':
            return self._chunk_concall(text)

        # For all other docs: section-boundary-aware chunking
        return self._chunk_structured_document(text)

    def _chunk_structured_document(self, text: str) -> List[DocumentChunk]:
        """Section-boundary-aware chunking for annual reports and BSE filings."""
        # 1. Find all section boundaries
        section_boundaries = self._find_section_boundaries(text)

        # 2. Detect table regions (to protect from splitting)
        table_regions = _detect_table_regions(text)

        # 3. If no sections detected, fall back to paragraph-aware chunking
        if not section_boundaries:
            return self._chunk_by_paragraphs(text, table_regions)

        # 4. Chunk by sections, then sub-chunk large sections
        chunks = []
        current_hierarchy = []

        for i, boundary in enumerate(section_boundaries):
            section_start = boundary['pos']
            section_end = section_boundaries[i + 1]['pos'] if i + 1 < len(section_boundaries) else len(text)
            section_text = text[section_start:section_end]
            section_type = boundary['section_type']

            # Update hierarchy
            current_hierarchy = [boundary['title']]

            if len(section_text) <= self.max_chunk_size:
                # Small enough to keep as single chunk
                page_start = max(1, section_start // self.CHARS_PER_PAGE + 1)
                page_end = max(page_start, section_end // self.CHARS_PER_PAGE + 1)

                chunks.append(DocumentChunk(
                    chunk_index=len(chunks),
                    chunk_text=section_text,
                    section_type=section_type,
                    section_hierarchy=current_hierarchy.copy(),
                    char_start=section_start,
                    char_end=section_end,
                    page_start=page_start,
                    page_end=page_end,
                    is_table=any(t_s <= section_start and section_end <= t_e for t_s, t_e in table_regions),
                    confidence=boundary['confidence'],
                ))
            else:
                # Sub-chunk large sections
                sub_chunks = self._sub_chunk_section(
                    section_text, section_start, section_type, current_hierarchy, table_regions
                )
                for sc in sub_chunks:
                    sc.chunk_index = len(chunks)
                    chunks.append(sc)

        # Handle text before first section
        if section_boundaries and section_boundaries[0]['pos'] > self.min_chunk_size:
            preamble = text[:section_boundaries[0]['pos']]
            if len(preamble.strip()) > self.min_chunk_size:
                chunks.insert(0, DocumentChunk(
                    chunk_index=0,
                    chunk_text=preamble,
                    section_type="preamble",
                    section_hierarchy=["Document Preamble"],
                    char_start=0,
                    char_end=section_boundaries[0]['pos'],
                    page_start=1,
                    page_end=max(1, section_boundaries[0]['pos'] // self.CHARS_PER_PAGE + 1),
                ))

        # 5. Merge small fragments
        chunks = self._merge_small_chunks(chunks)

        # 6. Add smart overlap
        final_chunks = []
        for i, chunk in enumerate(chunks):
            if i > 0 and chunks[i - 1].section_type == chunk.section_type:
                overlap = self._build_overlap_prefix(chunks[i - 1], section_boundaries)
                chunk.chunk_text = overlap + chunk.chunk_text
            final_chunks.append(chunk)

        # Re-index
        for i, chunk in enumerate(final_chunks):
            chunk.chunk_index = i

        logger.info(
            f"Chunked document: {len(text):,} chars → {len(final_chunks)} chunks "
            f"({sum(1 for c in final_chunks if c.section_type):,} with section type)"
        )
        return final_chunks

    def _sub_chunk_section(self, section_text: str, offset: int,
                           section_type: str, hierarchy: List[str],
                           table_regions: List[Tuple[int, int]]) -> List[DocumentChunk]:
        """Sub-chunk a large section while respecting table boundaries."""
        chunks = []
        pos = 0

        while pos < len(section_text):
            end_target = pos + self.target_chunk_size
            if end_target >= len(section_text):
                chunk_text = section_text[pos:]
            else:
                # Adjust table regions relative to section
                adj_tables = [(max(0, ts - offset), te - offset) for ts, te in table_regions]
                break_pos = self._find_break_point(section_text, end_target, adj_tables)
                break_pos = min(break_pos, len(section_text))
                chunk_text = section_text[pos:break_pos]

            abs_start = offset + pos
            abs_end = offset + pos + len(chunk_text)

            chunks.append(DocumentChunk(
                chunk_index=0,
                chunk_text=chunk_text,
                section_type=section_type,
                section_hierarchy=hierarchy.copy(),
                char_start=abs_start,
                char_end=abs_end,
                page_start=max(1, abs_start // self.CHARS_PER_PAGE + 1),
                page_end=max(1, abs_end // self.CHARS_PER_PAGE + 1),
                is_table=any(ts <= abs_start and abs_end <= te for ts, te in table_regions),
            ))

            pos += len(chunk_text)
            # Safety: force forward progress
            if pos <= chunks[-1].char_start - offset:
                pos = chunks[-1].char_end - offset

        return chunks

    def _chunk_by_paragraphs(self, text: str, table_regions: List[Tuple[int, int]]) -> List[DocumentChunk]:
        """Fallback: chunk by paragraphs when no sections detected."""
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current_text = ""
        current_start = 0
        pos = 0

        for para in paragraphs:
            if len(current_text) + len(para) > self.target_chunk_size and len(current_text) >= self.min_chunk_size:
                section_type, confidence = self._identify_section(current_text)
                chunks.append(DocumentChunk(
                    chunk_index=len(chunks),
                    chunk_text=current_text.strip(),
                    section_type=section_type,
                    char_start=current_start,
                    char_end=pos,
                    page_start=max(1, current_start // self.CHARS_PER_PAGE + 1),
                    page_end=max(1, pos // self.CHARS_PER_PAGE + 1),
                    confidence=confidence,
                ))
                current_text = para
                current_start = pos
            else:
                current_text += '\n\n' + para if current_text else para
            pos += len(para) + 2

        # Last chunk
        if current_text.strip():
            section_type, confidence = self._identify_section(current_text)
            chunks.append(DocumentChunk(
                chunk_index=len(chunks),
                chunk_text=current_text.strip(),
                section_type=section_type,
                char_start=current_start,
                char_end=len(text),
                page_start=max(1, current_start // self.CHARS_PER_PAGE + 1),
                page_end=max(1, len(text) // self.CHARS_PER_PAGE + 1),
                confidence=confidence,
            ))

        return self._merge_small_chunks(chunks)

    # ── Concall Q&A Chunking ──

    def _chunk_concall(self, text: str) -> List[DocumentChunk]:
        """
        Concall-aware chunking: preserves Q&A turns as complete units.
        Groups analyst question + management response into single chunks.
        """
        qa_turns = _detect_qa_turns(text)

        if not qa_turns:
            # No Q&A detected, fall back to structured chunking
            return self._chunk_structured_document(text)

        chunks = []

        # Handle preamble (before Q&A starts)
        first_qa_start = qa_turns[0]['start'] if qa_turns else len(text)
        if first_qa_start > self.min_chunk_size:
            preamble_chunks = self._chunk_structured_document(text[:first_qa_start])
            for chunk in preamble_chunks:
                if chunk.section_type is None:
                    chunk.section_type = "management_commentary"
            chunks.extend(preamble_chunks)

        # Group Q&A turns: question + response pairs
        i = 0
        while i < len(qa_turns):
            turn = qa_turns[i]
            group_text = text[turn['start']:turn['end']]
            group_end = turn['end']
            is_question = turn['is_question']
            speaker = turn['speaker']

            # If this is a question, try to group with the following response(s)
            if is_question and i + 1 < len(qa_turns):
                j = i + 1
                while j < len(qa_turns) and not qa_turns[j]['is_question']:
                    next_turn = qa_turns[j]
                    candidate = text[turn['start']:next_turn['end']]
                    if len(candidate) <= self.max_chunk_size:
                        group_text = candidate
                        group_end = next_turn['end']
                        j += 1
                    else:
                        break
                i = j
            else:
                i += 1

            # If still too long, sub-chunk
            if len(group_text) > self.max_chunk_size:
                sub_chunks = self._chunk_by_paragraphs(group_text, [])
                for sc in sub_chunks:
                    sc.section_type = "qa_session"
                    sc.is_qa_turn = True
                    sc.speaker = speaker
                    sc.char_start += turn['start']
                    sc.char_end += turn['start']
                    sc.chunk_index = len(chunks)
                    chunks.append(sc)
            else:
                chunks.append(DocumentChunk(
                    chunk_index=len(chunks),
                    chunk_text=group_text,
                    section_type="qa_session" if is_question else "management_commentary",
                    section_hierarchy=["Q&A Session", speaker],
                    char_start=turn['start'],
                    char_end=group_end,
                    page_start=max(1, turn['start'] // self.CHARS_PER_PAGE + 1),
                    page_end=max(1, group_end // self.CHARS_PER_PAGE + 1),
                    is_qa_turn=True,
                    speaker=speaker,
                ))

        # Re-index and merge small
        chunks = self._merge_small_chunks(chunks)
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i

        logger.info(
            f"Chunked concall: {len(text):,} chars → {len(chunks)} chunks "
            f"({sum(1 for c in chunks if c.is_qa_turn)} Q&A turns)"
        )
        return chunks


# ============================================================
# PAGEINDEX TREE BUILDER
# ============================================================

class PageIndexBuilder:
    """
    Build PageIndex-style hierarchical tree from document chunks.

    Creates a navigable tree structure (like an intelligent TOC) that enables:
    - LLM-driven tree traversal for complex queries
    - Page-level precision retrieval
    - Structure-aware context building

    Stored as JSONB in the database for reasoning-based retrieval.
    """

    def build_tree(self, chunks: List[DocumentChunk], doc_metadata: Dict = None) -> Dict:
        """
        Build a PageIndex tree from document chunks.

        Returns a JSON-serializable tree structure.
        """
        if not chunks:
            return {"nodes": [], "metadata": doc_metadata or {}}

        # Group chunks by section type
        section_groups = {}
        for chunk in chunks:
            section = chunk.section_type or "other"
            if section not in section_groups:
                section_groups[section] = []
            section_groups[section].append(chunk)

        # Build hierarchical tree
        root_nodes = []
        node_counter = 0

        # Define section hierarchy (which sections are "major" vs "sub")
        major_sections = {
            'chairman_letter', 'directors_report', 'mda', 'corporate_governance',
            'financial_statements', 'auditors_report', 'risk_management',
            'esg_report', 'csr_report', 'management_commentary', 'qa_session',
            'financial_highlights', 'business_review', 'outlook',
        }

        for section_type, section_chunks in section_groups.items():
            if not section_chunks:
                continue

            node_id = f"{node_counter:04d}"
            node_counter += 1

            # Build summary from first chunk
            first_text = section_chunks[0].chunk_text[:500]
            page_start = min(c.page_start for c in section_chunks)
            page_end = max(c.page_end for c in section_chunks)
            title = section_chunks[0].section_hierarchy[0] if section_chunks[0].section_hierarchy else section_type.replace('_', ' ').title()

            node = PageIndexNode(
                node_id=node_id,
                title=title,
                level=1 if section_type in major_sections else 2,
                start_page=page_start,
                end_page=page_end,
                summary=first_text.strip()[:300],
                section_type=section_type,
                chunk_ids=[c.chunk_index for c in section_chunks],
            )

            # If section has sub-sections, add children
            if len(section_chunks) > 3:
                for sub_chunk in section_chunks:
                    if sub_chunk.section_hierarchy and len(sub_chunk.section_hierarchy) > 1:
                        child_id = f"{node_counter:04d}"
                        node_counter += 1
                        child = PageIndexNode(
                            node_id=child_id,
                            title=sub_chunk.section_hierarchy[-1],
                            level=node.level + 1,
                            start_page=sub_chunk.page_start,
                            end_page=sub_chunk.page_end,
                            summary=sub_chunk.chunk_text[:200].strip(),
                            section_type=sub_chunk.section_type,
                            chunk_ids=[sub_chunk.chunk_index],
                        )
                        node.children.append(child)

            root_nodes.append(node)

        # Sort by page order
        root_nodes.sort(key=lambda n: n.start_page)

        # Build final tree
        tree = {
            "doc_description": self._build_doc_description(doc_metadata or {}),
            "total_pages": max((n.end_page for n in root_nodes), default=0),
            "total_chunks": len(chunks),
            "total_sections": len(root_nodes),
            "nodes": [n.to_dict() for n in root_nodes],
            "metadata": doc_metadata or {},
        }

        return tree

    def _build_doc_description(self, metadata: Dict) -> str:
        """Build a concise document description."""
        parts = []
        if metadata.get('symbol'):
            parts.append(f"{metadata['symbol']}")
        if metadata.get('company_name'):
            parts.append(f"({metadata['company_name']})")
        if metadata.get('doc_type'):
            dtype = 'Annual Report' if metadata['doc_type'] == 'annual_report' else 'Earnings Call Transcript'
            parts.append(dtype)
        if metadata.get('fiscal_year'):
            parts.append(f"FY{metadata['fiscal_year']}")
        return ' '.join(parts) if parts else "Financial Document"


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def estimate_chunks_for_corpus():
    """Estimate total chunks needed for the entire corpus."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import os
    from dotenv import load_dotenv

    load_dotenv(override=True)
    DATABASE_URL = os.getenv("DATABASE_URL")

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT 
            'annual_reports' as source,
            COUNT(*) as doc_count,
            AVG(LENGTH(summary))::int as avg_length,
            SUM(LENGTH(summary))::bigint as total_chars
        FROM annual_reports 
        WHERE summary IS NOT NULL AND LENGTH(summary) > 500
        UNION ALL
        SELECT 
            'concalls' as source,
            COUNT(*) as doc_count,
            AVG(LENGTH(transcript))::int as avg_length,
            SUM(LENGTH(transcript))::bigint as total_chars
        FROM concalls
        WHERE transcript IS NOT NULL AND LENGTH(transcript) > 500
    """)

    stats = cur.fetchall()
    cur.close()
    conn.close()

    chunker = SmartChunker()
    total_chunks = 0

    print("\n" + "=" * 60)
    print("CHUNK ESTIMATION FOR CORPUS")
    print("=" * 60)

    for stat in stats:
        avg_len = int(stat['avg_length'] or 0)
        doc_count = stat['doc_count']
        chunks_per_doc = max(1, avg_len // chunker.target_chunk_size)
        source_chunks = chunks_per_doc * doc_count
        total_chunks += source_chunks

        print(f"\n{stat['source'].upper()}")
        print(f"  Documents: {doc_count:,}")
        print(f"  Avg length: {avg_len:,} chars")
        print(f"  Est. chunks/doc: {chunks_per_doc}")
        print(f"  Total chunks: {source_chunks:,}")

    print(f"\n{'=' * 60}")
    print(f"TOTAL ESTIMATED CHUNKS: {total_chunks:,}")
    print(f"Embedding cost (OpenAI large): ~${total_chunks * 4000 / 1_000_000 * 0.13:.2f}")
    print("=" * 60)

    return total_chunks


if __name__ == "__main__":
    # Test chunking
    sample_ar = """
    CHAIRMAN'S MESSAGE
    
    Dear Shareholders,
    
    I am pleased to present the Annual Report for FY 2024. This year marked significant 
    achievements across all business segments. Our revenue grew by 18% to reach ₹50,000 crores,
    while maintaining healthy margins.
    
    """ + "Lorem ipsum dolor sit amet. " * 200 + """
    
    MANAGEMENT DISCUSSION AND ANALYSIS
    
    Industry Overview:
    The Indian real estate market showed strong recovery with residential demand at 
    multi-year highs. Commercial office space absorption reached 50 million sq ft.
    
    Business Performance:
    """ + "Detailed analysis of segment performance. " * 150 + """
    
    RISK MANAGEMENT
    
    The company identifies the following key risks:
    
    1. Foreign exchange volatility — mitigated through natural hedging
    2. Interest rate risk — managed through fixed-rate borrowings
    3. Regulatory risk — active engagement with regulators
    
    """ + "Risk mitigation details continue. " * 100 + """
    
    STANDALONE FINANCIAL STATEMENTS
    
    Balance Sheet as at March 31, 2024
    
    Particulars                      2024 (₹ Cr)    2023 (₹ Cr)
    ─────────────────────────────    ────────────    ────────────
    Share Capital                        247.34          247.34
    Reserves & Surplus                43,891.22       38,765.44
    Total Equity                     44,138.56       39,012.78
    
    """ + "Financial data continues. " * 100

    chunker = SmartChunker()
    chunks = chunker.chunk_document(sample_ar, doc_type='annual_report')

    print(f"\nDocument length: {len(sample_ar):,} chars")
    print(f"Generated {len(chunks)} chunks:")
    section_count = 0
    for chunk in chunks:
        marker = " 📊" if chunk.is_table else ""
        section_count += 1 if chunk.section_type else 0
        print(f"  Chunk {chunk.chunk_index}: {len(chunk.chunk_text):,} chars | "
              f"section: {chunk.section_type or 'None':25s} | "
              f"pages: {chunk.page_start}-{chunk.page_end}{marker}")

    print(f"\nSection detection rate: {section_count}/{len(chunks)} = {section_count / len(chunks) * 100:.0f}%")

    # Build PageIndex tree
    builder = PageIndexBuilder()
    tree = builder.build_tree(chunks, {"symbol": "TEST", "doc_type": "annual_report", "fiscal_year": "2024"})
    print(f"\nPageIndex Tree: {tree['total_sections']} sections, {tree['total_chunks']} chunks")
    for node in tree['nodes']:
        print(f"  [{node['node_id']}] {node['title'][:50]:50s} | pages {node['start_page']}-{node['end_page']} | {len(node['chunk_ids'])} chunks")

    # Estimate full corpus
    print("\n" + "-" * 60)
    estimate_chunks_for_corpus()

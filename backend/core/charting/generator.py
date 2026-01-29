"""
Visual RAG: Figure Extractor & Chart Generator

Extracts figures from annual report PDFs and generates clean institutional charts.
Uses PyMuPDF for PDF processing and Plotly for chart generation.
"""

import os
import base64
import logging
from io import BytesIO
from typing import List, Dict, Optional, Any
from datetime import datetime

import fitz  # PyMuPDF
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image

logger = logging.getLogger("VisualRAG")

# =============================================================================
# FISCAL.AI-INSPIRED CHART STYLE
# =============================================================================

CHART_STYLE = {
    # Typography
    "font_family": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
    
    # Colors - Fiscal.ai Dark Theme
    "background_color": "#1A1F2E",       # Dark blue-gray
    "text_color": "#FFFFFF",              # White text
    "subtitle_color": "#9CA3AF",          # Muted gray for subtitles
    
    # Bar colors (with gradient effect simulated)
    "primary_bar": "#EF4444",             # Coral red (for revenue/growth)
    "primary_bar_light": "#FCA5A5",       # Lighter red for gradient
    "secondary_bar": "#3B82F6",           # Blue (for bookings/orders)
    "secondary_bar_light": "#93C5FD",     # Lighter blue
    
    # Accent colors
    "positive_color": "#22C55E",          # Green for positive
    "negative_color": "#EF4444",          # Red for negative
    "neutral_color": "#6B7280",           # Gray
    
    # Grid and axes
    "grid_color": "#374151",              # Subtle dark grid
    "axis_color": "#4B5563",              # Axis line color
    
    # Chart dimensions
    "chart_width": 900,
    "chart_height": 500,
    
    # Branding
    "watermark": "Powered by Inwezt",
}


class FigureExtractor:
    """
    Extracts figures/charts from annual report PDFs.
    Smart filtering to identify real charts vs logos/icons.
    """
    
    def __init__(self, min_size: int = 30000, min_aspect_ratio: float = 0.5, max_aspect_ratio: float = 3.0):
        """
        Args:
            min_size: Minimum image size in bytes to consider (filters icons)
            min_aspect_ratio: Minimum width/height ratio (filters tall narrow images)
            max_aspect_ratio: Maximum width/height ratio (filters wide banners)
        """
        self.min_size = min_size
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
    
    def _is_likely_chart(self, width: int, height: int, size_bytes: int) -> bool:
        """Determine if image is likely a chart vs logo/icon."""
        if size_bytes < self.min_size:
            return False
        
        if height == 0:
            return False
        
        aspect_ratio = width / height
        if aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
            return False
        
        # Charts are usually reasonably sized
        if width < 200 or height < 150:
            return False
        
        return True
    
    def extract_from_pdf(self, pdf_path: str, max_figures: int = 5, start_page: int = 0) -> List[Dict]:
        """
        Extract figures from a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            max_figures: Maximum number of figures to extract
            start_page: Page to start extraction from (0-indexed)
        
        Returns:
            List of dicts with: base64, page, width, height, type
        """
        if not os.path.exists(pdf_path):
            logger.warning(f"PDF not found: {pdf_path}")
            return []
        
        figures = []
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(start_page, len(doc)):
                page = doc[page_num]
                images = page.get_images()
                
                for img_index, img in enumerate(images):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        width = base_image.get("width", 0)
                        height = base_image.get("height", 0)
                        
                        # Smart filtering for charts
                        if not self._is_likely_chart(width, height, len(image_bytes)):
                            continue
                        
                        # Convert to base64
                        b64 = base64.b64encode(image_bytes).decode('utf-8')
                        
                        figures.append({
                            "base64": b64,
                            "page": page_num + 1,
                            "width": width,
                            "height": height,
                            "format": base_image.get("ext", "png"),
                            "size_kb": len(image_bytes) // 1024,
                            "source": "pdf_extraction"
                        })
                        
                        if len(figures) >= max_figures:
                            break
                            
                    except Exception as e:
                        logger.debug(f"Failed to extract image: {e}")
                        continue
                
                if len(figures) >= max_figures:
                    break
            
            doc.close()
            logger.info(f"Extracted {len(figures)} chart figures from {pdf_path}")
            
        except Exception as e:
            logger.error(f"Failed to process PDF: {e}")
        
        return figures
    
    def extract_largest_figure(self, pdf_path: str) -> Optional[Dict]:
        """Extract the single largest figure (likely the most important chart)."""
        figures = self.extract_from_pdf(pdf_path, max_figures=20)
        if not figures:
            return None
        
        # Sort by size and return largest
        return max(figures, key=lambda f: f.get("size_kb", 0))
    
    def extract_from_annual_report(self, pdf_path: str) -> List[Dict]:
        """
        Extract key charts from annual report.
        Skips first 10 pages (usually cover/contents) and extracts up to 3 best charts.
        """
        return self.extract_from_pdf(pdf_path, max_figures=3, start_page=10)


class ChartGenerator:
    """
    Generates fiscal.ai-style charts for RAG responses.
    Dark theme, clean typography, branded footer with CAGR.
    """
    
    def __init__(self):
        self.style = CHART_STYLE
    
    def _apply_fiscal_style(self, fig: go.Figure, title: str, 
                            subtitle: str = None,
                            footer_left: str = None) -> go.Figure:
        """
        Apply pixel-perfect fiscal.ai styling.
        
        Key fixes:
        - Horizontal x-axis labels (no rotation)
        - Precise margins for alignment
        - Footer at bottom with proper spacing
        - Clean dotted grid lines
        """
        
        # Build title - clean format without emoji
        full_title = f"<b>{title}</b>"
        if subtitle:
            full_title += f"<br><span style='font-size:11px;color:{self.style['subtitle_color']}'>{subtitle}</span>"
        
        fig.update_layout(
            title={
                "text": full_title,
                "font": {"size": 15, "color": self.style["text_color"], "family": self.style["font_family"]},
                "x": 0.02,  # Slightly inset from left edge
                "xanchor": "left",
                "y": 0.96,
                "yanchor": "top"
            },
            font={"family": self.style["font_family"], "size": 10, "color": self.style["text_color"]},
            plot_bgcolor=self.style["background_color"],
            paper_bgcolor=self.style["background_color"],
            
            # Increased top margin for title clearance
            margin=dict(l=60, r=30, t=75, b=70),
            showlegend=False,
            
            # X-axis - HORIZONTAL labels, no rotation
            xaxis=dict(
                showgrid=False,
                showline=False,
                tickfont={"size": 9, "color": self.style["subtitle_color"], "family": self.style["font_family"]},
                tickangle=0,
                ticklabelposition="outside",
                side="bottom"
            ),
            
            # Y-axis - subtle dotted grid
            yaxis=dict(
                showgrid=True,
                gridcolor=self.style["grid_color"],
                gridwidth=0.5,
                griddash="dot",
                showline=False,
                tickfont={"size": 9, "color": self.style["subtitle_color"], "family": self.style["font_family"]},
                zeroline=False,
                ticklabelposition="outside",
                side="left"
            ),
            
            # Uniform padding
            uniformtext_minsize=8,
            uniformtext_mode='hide',
            bargap=0.15,
        )
        
        # Footer annotations - perfectly aligned at bottom
        annotations = []
        
        if footer_left:
            annotations.append(dict(
                text=footer_left,
                xref="paper", yref="paper",
                x=0.01, y=-0.15,
                showarrow=False,
                font={"size": 9, "color": self.style["positive_color"], "family": self.style["font_family"]},
                xanchor="left",
                yanchor="top"
            ))
        
        # Watermark - bottom right
        annotations.append(dict(
            text=self.style["watermark"],
            xref="paper", yref="paper",
            x=0.99, y=-0.15,
            showarrow=False,
            font={"size": 8, "color": self.style["subtitle_color"], "family": self.style["font_family"]},
            xanchor="right",
            yanchor="top"
        ))
        
        fig.update_layout(annotations=annotations)
        
        return fig
    
    def _to_base64(self, fig: go.Figure) -> str:
        """Convert Plotly figure to base64 PNG."""
        img_bytes = fig.to_image(
            format="png",
            width=self.style["chart_width"],
            height=self.style["chart_height"],
            scale=2  # Retina quality
        )
        return base64.b64encode(img_bytes).decode('utf-8')
    
    def _calculate_cagr(self, values: List[float], periods: int) -> float:
        """Calculate Compound Annual Growth Rate."""
        if not values or len(values) < 2 or values[0] == 0:
            return 0
        return ((values[-1] / values[0]) ** (1 / max(periods, 1)) - 1) * 100
    
    def _get_gradient_colors(self, base_color: str, n: int, reverse: bool = False) -> List[str]:
        """
        Generate gradient-like colors for bars.
        Creates a subtle progression from lighter to darker.
        """
        # Define gradient pairs
        gradients = {
            "#EF4444": ["#FCA5A5", "#F87171", "#EF4444", "#DC2626", "#B91C1C"],  # Red
            "#3B82F6": ["#93C5FD", "#60A5FA", "#3B82F6", "#2563EB", "#1D4ED8"],  # Blue
            "#22C55E": ["#86EFAC", "#4ADE80", "#22C55E", "#16A34A", "#15803D"],  # Green
        }
        
        if base_color in gradients:
            palette = gradients[base_color]
        else:
            palette = [base_color] * 5
        
        # Distribute colors across n items
        colors = []
        for i in range(n):
            idx = min(int(i * len(palette) / n), len(palette) - 1)
            colors.append(palette[idx])
        
        return colors[::-1] if reverse else colors
    
    def _premium_bar_style(self, base_color: str) -> dict:
        """Generate premium bar styling with subtle effects."""
        return {
            "color": base_color,
            "line": {"width": 0.5, "color": "rgba(255,255,255,0.2)"},  # Subtle white border
        }
    
    def revenue_trend(self, 
                      data: List[Dict], 
                      symbol: str,
                      company_name: str = None,
                      color: str = "primary",
                      title_prefix: str = "") -> Dict:
        """
        Generate fiscal.ai-style revenue bar chart.
        Data labels inside bars, short x-axis labels.
        """
        if not data:
            return {"error": "No data provided"}
        
        # Prepare data - use SHORT labels and FILTER FUTURE DATES
        import datetime
        now = datetime.datetime.now()
        current_fy_limit = now.year if now.month < 4 else now.year + 1
        
        filtered_data = []
        for d in data:
            period = str(d.get('quarter', d.get('period', '')))
            if "FY" in period:
                try:
                    # Extract year - handles "FY25" -> 2025
                    # DEFINITION: FY25 = April 1, 2024 to March 31, 2025
                    # DEFINITION: FY26 = April 1, 2025 to March 31, 2026
                    year_val = 2000 + int(period.split("FY")[-1])
                    
                    # LOGIC:
                    # If today is Jan 2026, we are in FY26.
                    # FY26 Annual Report cannot exist until AFTER March 31, 2026.
                    # Therefore, any Annual Report with year_val >= 2026 is a hallucination.
                    if year_val >= current_fy_limit and "Q" not in period: 
                        continue 
                except: pass
            filtered_data.append(d)
        
        data = filtered_data
        
        # Explicitly SORT by fiscal year/period to ensure chronological order
        def sort_key(d):
            p = str(d.get('quarter', d.get('period', '')))
            try:
                if "FY" in p:
                    # Sort by Year then Quarter
                    y = int(p.split("FY")[-1])
                    q = 0
                    if "Q" in p:
                        q = int(p.split("Q")[1].split()[0])
                    return (y, q)
            except: pass
            return (0, 0)
            
        data.sort(key=sort_key)
        labels = [f"{d.get('quarter', d.get('period', ''))}" for d in data]
        values = [d.get('value', d.get('revenue_cr', d.get('net_margin', 0))) for d in data]
        
        # Choose base color
        base_color = self.style["primary_bar"] if color == "primary" else self.style["secondary_bar"]
        
        # Get gradient colors for premium look
        gradient_colors = self._get_gradient_colors(base_color, len(values), reverse=False)
        
        # Create chart with polished styling
        fig = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker=dict(
                    color=gradient_colors,
                    line={"width": 0.5, "color": "rgba(255,255,255,0.15)"},  # Subtle white border
                ),
                text=[f"{v:,.0f}" if v >= 100 else f"{v:.1f}" for v in values],
                textposition="outside",
                textfont={"size": 8, "color": self.style["text_color"], "family": self.style["font_family"]},
                width=0.65,
                cliponaxis=False
            )
        ])
        
        # Calculate metrics for footer
        total_change = ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0
        cagr = self._calculate_cagr(values, len(values) - 1)
        
        # Title - fiscal.ai uses simple format
        title_text = f"{symbol}" if not company_name else f"{company_name} ({symbol})"
        
        # Apply fiscal.ai styling
        title_suffix = f"{title_prefix} Revenue" if title_prefix else "Revenue"
        fig = self._apply_fiscal_style(
            fig,
            title=f"{title_text} - {title_suffix}",
            subtitle="(in ₹ Crores)",
            footer_left=f"● Total Change: {total_change:+.0f}% | CAGR: {cagr:.1f}%"
        )
        
        return {
            "base64": self._to_base64(fig),
            "type": "revenue_trend",
            "title": f"{symbol} {'Annual ' if title_prefix == 'Annual' else 'Quarterly ' if title_prefix == 'Quarterly' else ''}Revenue Trend",
            "symbol": symbol,
            "metrics": {"total_change": total_change, "cagr": cagr},
            "insight": f"Revenue {'grew' if cagr >= 0 else 'declined'} from ₹{values[0]:,.0f} Cr to ₹{values[-1]:,.0f} Cr at {cagr:.1f}% CAGR over the period."
        }
    
    def margin_trend(self, 
                     data: List[Dict], 
                     symbol: str,
                     metric: str = "net_margin",
                     title_prefix: str = "") -> Dict:
        """
        Generate fiscal.ai-style margin trend bar chart.
        """
        if not data:
            return {"error": "No data provided"}
        
        import datetime
        now = datetime.datetime.now()
        current_fy_limit = now.year if now.month < 4 else now.year + 1
        
        filtered_data = []
        for d in data:
            period = str(d.get('quarter', d.get('period', '')))
            if "FY" in period:
                try:
                    year_val = 2000 + int(period.split("FY")[-1])
                    if year_val >= current_fy_limit and "Q" not in period: 
                        continue 
                except: pass
            filtered_data.append(d)
        
        data = filtered_data
        
        # Explicitly SORT by fiscal year to ensure chronological order
        def sort_key(d):
            p = str(d.get('quarter', d.get('period', '')))
            try:
                if "FY" in p:
                    y = int(p.split("FY")[-1])
                    q = 0
                    if "Q" in p:
                        q = int(p.split("Q")[1].split()[0])
                    return (y, q)
            except: pass
            return (0, 0)
            
        data.sort(key=sort_key)
        labels = [f"{d.get('quarter', d.get('period', ''))}" for d in data]
        values = [d.get('value', d.get(metric, 0)) for d in data]
        
        # Create gradient effect with color based on value
        colors = [self.style["secondary_bar"] for _ in values]
        
        fig = go.Figure(data=[
            go.Bar(
                x=labels,
                y=values,
                marker_color=colors,
                text=[f"{v:.1f}%" for v in values],
                textposition="outside",
                textfont={"size": 10, "color": self.style["text_color"]},
                width=0.6
            )
        ])
        
        # Calculate metrics
        if len(values) >= 2 and values[0] != 0:
            total_change = values[-1] - values[0]
        else:
            total_change = 0
        
        # Apply styling
        title_suffix = f"{title_prefix} Net Margin Trend" if title_prefix else "Net Margin Trend"
        fig = self._apply_fiscal_style(
            fig,
            title=f"{symbol} - {title_suffix}",
            subtitle="(%)",
            footer_left=f"● Change: {total_change:+.1f}pp over period"
        )
        
        fig.update_yaxes(ticksuffix="%")
        
        return {
            "base64": self._to_base64(fig),
            "type": "margin_trend",
            "title": f"{symbol} {'Annual ' if title_prefix == 'Annual' else 'Quarterly ' if title_prefix == 'Quarterly' else ''}Net Margin Trend",
            "symbol": symbol,
            "metrics": {"total_change": total_change},
            "insight": f"Net margin {'expanded' if total_change >= 0 else 'contracted'} from {values[0]:.1f}% to {values[-1]:.1f}% ({total_change:+.1f}pp change)."
        }
    
    def peer_comparison(self, 
                        peers: List[Dict], 
                        metric: str = "pe_ratio",
                        highlight_symbol: str = None) -> Dict:
        """
        Generate horizontal bar chart comparing peers.
        """
        if not peers:
            return {"error": "No peer data"}
        
        symbols = [p.get("symbol", "?") for p in peers]
        values = [p.get(metric, 0) for p in peers]
        
        # Highlight the main stock with primary color
        colors = [
            self.style["primary_bar"] if s == highlight_symbol 
            else self.style["secondary_bar"] 
            for s in symbols
        ]
        
        fig = go.Figure(data=[
            go.Bar(
                x=values,
                y=symbols,
                orientation='h',
                marker_color=colors,
                text=[f"{v:.1f}x" for v in values],
                textposition="outside",
                textfont={"size": 10, "color": self.style["text_color"]},
                width=0.6
            )
        ])
        
        metric_labels = {
            "pe_ratio": "P/E Ratio",
            "pb_ratio": "P/B Ratio",
            "roe": "ROE (%)",
            "net_margin": "Net Margin (%)"
        }
        
        title = f"Peer Comparison - {metric_labels.get(metric, metric)}"
        fig = self._apply_fiscal_style(fig, title, footer_left=f"● {highlight_symbol} highlighted")
        fig.update_xaxes(tickfont={"size": 10, "color": self.style["subtitle_color"]})
        
        return {
            "base64": self._to_base64(fig),
            "type": "peer_comparison",
            "title": title,
            "metric": metric,
            "symbol": highlight_symbol,
            "insight": f"Comparison of {len(peers)} peers based on {metric_labels.get(metric, metric)}. {highlight_symbol} performs relative to sector peers."
        }
    
    def valuation_gauge(self, 
                        current_pe: float, 
                        sector_pe: float,
                        historical_low: float,
                        historical_high: float,
                        symbol: str) -> Dict:
        """
        Generate a gauge chart showing where current PE sits in historical range.
        Fiscal.ai dark theme styling.
        """
        # Calculate premium/discount
        premium = ((current_pe - sector_pe) / sector_pe * 100) if sector_pe != 0 else 0
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=current_pe,
            delta={"reference": sector_pe, "suffix": "x", "valueformat": ".1f"},
            title={"text": f"<b>{symbol} P/E Valuation</b>", "font": {"size": 18, "color": self.style["text_color"]}},
            number={"font": {"size": 48, "color": self.style["text_color"]}, "suffix": "x"},
            gauge={
                "axis": {
                    "range": [historical_low * 0.8, historical_high * 1.2],
                    "tickcolor": self.style["subtitle_color"],
                    "tickfont": {"color": self.style["subtitle_color"]}
                },
                "bar": {"color": self.style["secondary_bar"]},
                "bgcolor": self.style["grid_color"],
                "steps": [
                    {"range": [historical_low * 0.8, sector_pe * 0.8], 
                     "color": self.style["positive_color"]},
                    {"range": [sector_pe * 0.8, sector_pe * 1.2], 
                     "color": self.style["neutral_color"]},
                    {"range": [sector_pe * 1.2, historical_high * 1.2], 
                     "color": self.style["negative_color"]}
                ],
                "threshold": {
                    "line": {"color": self.style["text_color"], "width": 2},
                    "thickness": 0.75,
                    "value": sector_pe
                }
            }
        ))
        
        fig.update_layout(
            font={"family": self.style["font_family"], "color": self.style["text_color"]},
            paper_bgcolor=self.style["background_color"],
            plot_bgcolor=self.style["background_color"],
            height=400,
            margin=dict(l=40, r=40, t=80, b=60),
            annotations=[
                dict(
                    text=f"▲ {premium:+.0f}% vs sector" if premium > 0 else f"▼ {premium:.0f}% vs sector",
                    x=0.5, y=0.25,
                    xref="paper", yref="paper",
                    showarrow=False,
                    font={"size": 14, "color": self.style["positive_color"] if premium < 0 else self.style["negative_color"]}
                ),
                dict(
                    text=self.style["watermark"],
                    x=0.98, y=0.02,
                    xref="paper", yref="paper",
                    showarrow=False,
                    font={"size": 9, "color": self.style["subtitle_color"]},
                    xanchor="right"
                )
            ]
        )
        
        return {
            "base64": self._to_base64(fig),
            "type": "valuation_gauge",
            "title": f"{symbol} Valuation",
            "symbol": symbol,
            "insight": f"Current PE is {current_pe:.1f}x vs Sector PE {sector_pe:.1f}x. The stock is trading at a {((current_pe-sector_pe)/sector_pe)*100:+.0f}% premium/discount to sector."
        }
    
    def segment_breakdown(self, 
                          segments: List[Dict], 
                          symbol: str,
                          chart_type: str = "stacked") -> Dict:
        """
        Generate segment revenue breakdown chart.
        
        Args:
            segments: List of dicts with 'name', 'value', optional 'periods' for multi-period
                     e.g. [{"name": "O2C", "Q1": 50000, "Q2": 52000}, ...]
            symbol: Stock symbol
            chart_type: "stacked", "grouped", or "pie"
        """
        if not segments:
            return {"error": "No segment data"}
        
        # Color palette for segments
        segment_colors = [
            "#EF4444",  # Red
            "#3B82F6",  # Blue
            "#22C55E",  # Green
            "#F59E0B",  # Amber
            "#8B5CF6",  # Purple
            "#06B6D4",  # Cyan
            "#EC4899",  # Pink
        ]
        
        # Check if multi-period data
        if "Q1" in segments[0] or "periods" in segments[0]:
            # Multi-period stacked bar
            periods = ["Q1", "Q2", "Q3", "Q4"]
            fig = go.Figure()
            
            for i, seg in enumerate(segments):
                values = [seg.get(p, 0) for p in periods]
                fig.add_trace(go.Bar(
                    name=seg.get("name", f"Segment {i+1}"),
                    x=periods,
                    y=values,
                    marker_color=segment_colors[i % len(segment_colors)],
                    text=[f"₹{v/1000:.0f}K" if v >= 1000 else f"₹{v:.0f}" for v in values],
                    textposition="inside",
                    textfont={"size": 8, "color": "#FFFFFF"},
                ))
            
            fig.update_layout(barmode="stack" if chart_type == "stacked" else "group")
        else:
            # Single period - horizontal bars or pie
            names = [s.get("name", "?") for s in segments]
            values = [s.get("value", 0) for s in segments]
            colors = [segment_colors[i % len(segment_colors)] for i in range(len(segments))]
            
            fig = go.Figure(data=[
                go.Bar(
                    x=values,
                    y=names,
                    orientation='h',
                    marker_color=colors,
                    text=[f"₹{v:,.0f} Cr" for v in values],
                    textposition="outside",
                    textfont={"size": 9, "color": self.style["text_color"]},
                )
            ])
        
        # Calculate total for footer
        if "Q1" in segments[0]:
            total = sum(seg.get("Q4", 0) for seg in segments)
        else:
            total = sum(s.get("value", 0) for s in segments)
        
        fig = self._apply_fiscal_style(
            fig,
            title=f"{symbol} - Revenue by Segment",
            subtitle="(in ₹ Crores)",
            footer_left=f"● Total: ₹{total:,.0f} Cr"
        )
        
        # Only show legend for multi-period charts (stacked/grouped)
        if "Q1" in segments[0] or "periods" in segments[0]:
            fig.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="center",
                    x=0.5,
                    font={"size": 9, "color": self.style["subtitle_color"]}
                )
            )
        else:
            # Hide legend for single-period horizontal bars
            fig.update_layout(showlegend=False)
        
        return {
            "base64": self._to_base64(fig),
            "type": "segment_breakdown",
            "title": f"{symbol} Segment Breakdown",
            "symbol": symbol,
            "insight": f"Segment breakdown analysis shows total revenue contribution of ₹{total:,.0f} Cr across business verticals."
        }
    
    def quarterly_comparison(self,
                             current_q: Dict,
                             prev_q: Dict,
                             symbol: str) -> Dict:
        """
        Generate side-by-side quarterly comparison chart.
        
        Args:
            current_q: Dict with metrics for current quarter
            prev_q: Dict with metrics for previous quarter
            symbol: Stock symbol
        """
        metrics = ["Revenue", "EBITDA", "Net Profit", "PAT"]
        
        current_vals = [
            current_q.get("revenue_cr", 0),
            current_q.get("ebitda_cr", 0),
            current_q.get("net_profit_cr", 0),
            current_q.get("pat_cr", 0)
        ]
        
        prev_vals = [
            prev_q.get("revenue_cr", 0),
            prev_q.get("ebitda_cr", 0),
            prev_q.get("net_profit_cr", 0),
            prev_q.get("pat_cr", 0)
        ]
        
        current_label = f"Q{current_q.get('quarter', '?')} FY{str(current_q.get('fiscal_year', ''))[-2:]}"
        prev_label = f"Q{prev_q.get('quarter', '?')} FY{str(prev_q.get('fiscal_year', ''))[-2:]}"
        
        fig = go.Figure()
        
        # Previous quarter
        fig.add_trace(go.Bar(
            name=prev_label,
            x=metrics,
            y=prev_vals,
            marker_color=self.style["secondary_bar"],
            text=[f"{v:,.0f}" for v in prev_vals],
            textposition="outside",
            textfont={"size": 8, "color": self.style["subtitle_color"]},
            width=0.35
        ))
        
        # Current quarter
        fig.add_trace(go.Bar(
            name=current_label,
            x=metrics,
            y=current_vals,
            marker_color=self.style["primary_bar"],
            text=[f"{v:,.0f}" for v in current_vals],
            textposition="outside",
            textfont={"size": 8, "color": self.style["text_color"]},
            width=0.35
        ))
        
        fig.update_layout(barmode="group")
        
        # Calculate revenue growth for footer
        if prev_vals[0] > 0:
            growth = ((current_vals[0] - prev_vals[0]) / prev_vals[0]) * 100
        else:
            growth = 0
        
        fig = self._apply_fiscal_style(
            fig,
            title=f"{symbol} - Quarterly Comparison",
            subtitle=f"{prev_label} vs {current_label}",
            footer_left=f"● Revenue Growth: {growth:+.1f}% QoQ"
        )
        
        fig.update_layout(
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font={"size": 9, "color": self.style["subtitle_color"]}
            )
        )
        
        return {
            "base64": self._to_base64(fig),
            "type": "quarterly_comparison",
            "title": f"{symbol} Quarterly Comparison",
            "symbol": symbol,
            "growth": growth,
            "insight": f"Comparing {prev_label} vs {current_label}: Revenue changed by {growth:+.1f}% QoQ."
        }
    
    def simple_metric_card(self, 
                           value: float, 
                           label: str,
                           change: float = None,
                           symbol: str = "") -> Dict:
        """
        Generate a simple metric card (like fiscal.ai's key stats).
        """
        # Determine color based on change
        if change is not None:
            if change > 0:
                color = self.style["positive_color"]
                arrow = "▲"
            elif change < 0:
                color = self.style["negative_color"]
                arrow = "▼"
            else:
                color = self.style["neutral_color"]
                arrow = "—"
            delta_text = f"{arrow} {abs(change):.1f}%"
        else:
            color = self.style["primary_color"]
            delta_text = ""
        
        fig = go.Figure(go.Indicator(
            mode="number+delta" if change is not None else "number",
            value=value,
            delta={"reference": value / (1 + change/100) if change else None, 
                   "relative": True, "valueformat": ".1%"} if change else None,
            title={"text": label},
            number={"font": {"size": 48, "color": color}},
        ))
        
        fig.update_layout(
            font={"family": self.style["font_family"]},
            paper_bgcolor=self.style["background_color"],
            height=200,
            width=300,
            margin=dict(l=20, r=20, t=60, b=20)
        )
        
        return {
            "base64": self._to_base64(fig),
            "type": "metric_card",
            "label": label,
            "value": value
        }


# =============================================================================
# HELPER FUNCTIONS FOR ORCHESTRATOR INTEGRATION
# =============================================================================

def detect_chart_intent(query: str) -> Optional[str]:
    """
    Smart chart selection based on query keywords.
    Returns the most appropriate chart type for the query.
    """
    q = query.lower()
    
    CHART_TRIGGERS = {
        # Segment/breakdown charts
        "segment_breakdown": [
            "segment", "breakdown", "division", "by business", "by segment",
            "revenue mix", "business mix", "contribution", "o2c", "retail",
            "jio", "digital", "oil and gas", "refining"
        ],
        
        # Quarterly comparison
        "quarterly_comparison": [
            "quarter", "qoq", "q-o-q", "quarterly", "q1", "q2", "q3", "q4",
            "this quarter", "last quarter", "sequential"
        ],
        
        # Revenue trend
        "revenue_trend": [
            "revenue trend", "revenue growth", "revenue over",
            "sales trend", "sales growth", "topline"
        ],
        
        # Margin trend
        "margin_trend": [
            "margin trend", "margin over time", "margin history", 
            "margin guidance", "margins changing", "profitability"
        ],
        
        # Peer comparison
        "peer_comparison": [
            "compare", "vs", "versus", "peers", "competitors",
            "relative to", "better than", "worse than", "industry"
        ],
        
        # Valuation
        "valuation_gauge": [
            "valuation", "expensive", "cheap", "undervalued", "overvalued",
            "pe ratio", "trading at", "fairly valued"
        ]
    }
    
    for chart_type, triggers in CHART_TRIGGERS.items():
        if any(t in q for t in triggers):
            return chart_type
    
    return None


def generate_relevant_chart(
    query: str, 
    market_data: Dict, 
    filings_data: Dict,
    symbol: str
) -> Optional[Dict]:
    """
    Smart chart generation based on query intent.
    Automatically selects and generates the most relevant chart.
    
    Returns:
        Chart dict with base64 image and metadata, or None
    """
    chart_type = detect_chart_intent(query)
    generator = ChartGenerator()
    
    try:
        # === SEGMENT BREAKDOWN ===
        if chart_type == "segment_breakdown":
            segments = filings_data.get("segments", [])
            if segments:
                return generator.segment_breakdown(segments, symbol)
            # Fallback: create mock segments from available data
            segments = [
                {"name": "Core Business", "value": market_data.get("market_cap", 0) * 0.6},
                {"name": "Others", "value": market_data.get("market_cap", 0) * 0.4}
            ]
            return generator.segment_breakdown(segments, symbol)
        
        # === QUARTERLY COMPARISON ===
        if chart_type == "quarterly_comparison":
            quarterly = filings_data.get("quarterly_results", [])
            if quarterly and len(quarterly) >= 2:
                # Sort by date and get last two quarters
                sorted_q = sorted(quarterly, 
                    key=lambda x: (x.get("fiscal_year", 0), x.get("quarter", 0)))
                if len(sorted_q) >= 2:
                    return generator.quarterly_comparison(
                        sorted_q[-1], sorted_q[-2], symbol
                    )
        
        # === REVENUE TREND ===
        if chart_type == "revenue_trend":
            annual = filings_data.get("annual_results", [])
            quarterly = sorted(filings_data.get("quarterly_results", []), 
                              key=lambda x: (x.get("fiscal_year", 0), x.get("quarter", 0)))
            
            if len(annual) >= 3:
                data = [{"period": f"FY{str(a.get('fiscal_year', ''))[-2:]}", 
                         "value": a.get("revenue_cr", 0)} for a in annual]
                if any(d["value"] > 0 for d in data):
                    return generator.revenue_trend(data, symbol, title_prefix="Annual")
            
            if quarterly:
                data = [{"period": f"Q{q.get('quarter', '?')} FY{str(q.get('fiscal_year', ''))[-2:]}", 
                         "value": q.get("revenue_cr", 0)} for q in quarterly]
                data = [d for d in data if d["value"] > 0]
                if len(data) >= 2:
                    return generator.revenue_trend(data, symbol, title_prefix="Quarterly")
        
        # === MARGIN TREND ===
        if chart_type == "margin_trend":
            annual = filings_data.get("annual_results", [])
            quarterly = sorted(filings_data.get("quarterly_results", []), 
                              key=lambda x: (x.get("fiscal_year", 0), x.get("quarter", 0)))
            
            if len(annual) >= 3:
                data = [{"period": f"FY{str(a.get('fiscal_year', ''))[-2:]}", 
                         "value": a.get("net_margin", 0)} for a in annual]
                for d, a in zip(data, annual):
                    if d["value"] == 0:
                        rev = a.get("revenue_cr", 0)
                        prof = a.get("net_profit_cr", 0)
                        if rev and prof:
                            d["value"] = (prof / rev) * 100
                
                if any(d["value"] != 0 for d in data):
                    return generator.margin_trend(data, symbol, title_prefix="Annual")

            if quarterly:
                data = []
                for q in quarterly:
                    margin = q.get("net_margin", 0)
                    if not margin:
                        rev = q.get("revenue_cr", 0)
                        prof = q.get("net_profit_cr", 0)
                        if rev and prof:
                            margin = (prof / rev) * 100
                    if margin:
                        data.append({"period": f"Q{q.get('quarter', '?')} FY{str(q.get('fiscal_year', ''))[-2:]}", 
                                     "value": margin})
                
                if len(data) >= 2:
                    return generator.margin_trend(data, symbol, title_prefix="Quarterly")
        
        # === PEER COMPARISON ===
        if chart_type == "peer_comparison":
            peers = market_data.get("peers", [])
            if peers:
                return generator.peer_comparison(peers, "pe_ratio", symbol)
        
        # === VALUATION GAUGE ===
        if chart_type == "valuation_gauge":
            pe = market_data.get("pe_ratio")
            sector_pe = market_data.get("sector_pe", market_data.get("industry_pe", 15))
            if pe:
                return generator.valuation_gauge(
                    current_pe=float(pe),
                    sector_pe=float(sector_pe),
                    historical_low=float(sector_pe) * 0.6,
                    historical_high=float(sector_pe) * 2.0,
                    symbol=symbol
                )
        
        # === DEFAULT FALLBACK ===
        # If no specific chart type detected, try valuation gauge
        pe = market_data.get("pe_ratio")
        sector_pe = market_data.get("sector_pe", market_data.get("industry_pe", 15))
        if pe:
            return generator.valuation_gauge(
                current_pe=float(pe),
                sector_pe=float(sector_pe),
                historical_low=float(sector_pe) * 0.6,
                historical_high=float(sector_pe) * 2.0,
                symbol=symbol
            )
    
    except Exception as e:
        logger.error(f"Chart generation failed: {e}")
    
    return None


def get_hybrid_visuals(
    query: str,
    symbol: str,
    market_data: Dict,
    filings_data: Dict,
    annual_report_path: Optional[str] = None
) -> Dict:
    """
    HYBRID VISUAL RAG (like fiscal.ai):
    1. Extract existing charts from annual reports PDFs
    2. Generate fresh data visualizations
    
    Returns:
        Dict with 'extracted' (from PDF) and 'generated' (from data) charts
    """
    result = {
        "extracted": [],      # Charts pulled from PDFs
        "generated": None,    # Chart generated from data
        "symbol": symbol
    }
    
    # 1. Extract charts from annual report if path provided
    if annual_report_path and os.path.exists(annual_report_path):
        extractor = FigureExtractor()
        extracted = extractor.extract_from_annual_report(annual_report_path)
        result["extracted"] = extracted
        logger.info(f"Extracted {len(extracted)} charts from annual report")
    
    # 2. Generate data-driven chart
    generated = generate_relevant_chart(query, market_data, filings_data, symbol)
    if generated:
        generated["source"] = "data_generated"
        result["generated"] = generated
    
    return result


# Test function
if __name__ == "__main__":
    # Quick test of chart generation
    gen = ChartGenerator()
    
    test_data = [
        {"quarter": 1, "fiscal_year": 2024, "net_margin": 12.5},
        {"quarter": 2, "fiscal_year": 2024, "net_margin": 13.2},
        {"quarter": 3, "fiscal_year": 2024, "net_margin": 11.8},
        {"quarter": 4, "fiscal_year": 2024, "net_margin": 14.1},
    ]
    
    result = gen.margin_trend(test_data, "RELIANCE")
    print(f"Generated chart: {result['type']}")
    print(f"Base64 length: {len(result['base64'])} chars")
    
    # Test valuation gauge
    gauge = gen.valuation_gauge(
        current_pe=25.5,
        sector_pe=13.0,
        historical_low=8.0,
        historical_high=35.0,
        symbol="RELIANCE"
    )
    print(f"\nGenerated gauge: {gauge['type']}")
    print(f"Base64 length: {len(gauge['base64'])} chars")
    
    # Save for viewing
    import base64 as b64
    with open("test_gauge_chart.png", "wb") as f:
        f.write(b64.b64decode(gauge["base64"]))
    print("Saved to test_gauge_chart.png")

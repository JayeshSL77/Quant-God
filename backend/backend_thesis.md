# Analyez Backend Thesis: Institutional-Grade AI Financial Analysis

This document consolidates the methodology, findings, and technical architecture of the Analyez AI backend, synthesized from extensive testing and debug logs.

## 核心 Methodology: Multi-Layered RAG

Analyez employs a sophisticated Retrieval-Augmented Generation (RAG) pipeline designed for institutional-grade equity research. Unlike basic RAG, it decomposes queries and synchronizes data across four specialized analytical layers:

1.  **Quantitative Layer (MarketDataAgent)**: Fetches real-time and historical valuation metrics (P/E, P/B), trading data (52W High/Low, Beta), and peer comparisons.
2.  **Structural Layer (FilingsAgent)**: Performs deep extraction from quarterly results, annual reports, and conference call transcripts. It prioritizes management guidance and strategic pivots.
3.  **Dynamic Layer (NewsAgent)**: Captures recent developments and market sentiment from verified financial news sources.
4.  **Technical Layer (TechnicalAgent)**: Calculates trend signals using indicators like RSI and Moving Averages (50-day / 200-day DMA).

## Analytical Framework for Equity Research

All synthesized responses follow a strict institutional framework:

-   **VALUATION CONTEXT**: Comparing current multiples against 10-year historical CAGRs and sector averages.
-   **MANAGEMENT SIGNALS**: Direct extraction of guidance on revenue, EBITDA, and capital allocation (dividends/buybacks) from concalls.
-   **RISK FRAMEWORK**: Identification of material business and macroeconomic risks (e.g., regulatory shifts, margin compression).
-   **INVESTMENT THESIS**: A clear rating (Overweight/Neutral/Underweight) supported by a fair value range and key catalysts.

## Key Findings from RIL & HDFCBANK Case Studies

-   **Deep Document Nuance**: Testing revealed that truncating concalls to ~60,000 characters for LLM summarization preserves the "nuance" of management tones while maintaining computational efficiency.
-   **Data Conflicts**: The backend implements a precedence logic where direct exchange filings (NSE/BSE) override third-party aggregators for fundamental data.
-   **Prompt Engineering**: Institutional responses require a "no emojis, no markdown headers" rule in intermediate analysis to ensure strictly factual synthesis before the final UI formatting.

## Evolution of AI Insights

The Analyez AI has evolved from a basic conversational summarizer to a high-fidelity equity research engine. Below is a comparison of the response quality across versions:

### 1. Previous (MVP / V1 - Conversational Summary)
**Characteristics**: Plain text, conversational tone, lacks quantitative depth, focused on broad sentiment.
> "Reliance is everywhere—petrol pumps, Jio SIM cards, even the local store. At ₹1,404, the PE is 23x which is a bit higher than the sector average. Jio is growing fast. Good for long-term. Strong company, fair price. 💰"

### 2. Current (V3 / Institutional - Structured Analysis)
**Characteristics**: Markdown structured, strictly quantitative, management-led, quantified risks, and explicit investment rating.
> **VALUATION CONTEXT**:
> - Current P/E of 25.54x is 97% above sector average (12.95x), signaling premium valuation.
> - Price at Rs 1401.80 is 13% below 52-week high, suggesting potential upside.
> 
> **MANAGEMENT SIGNALS**:
> - Guidance highlights confidence in S&P upgrade to A- due to diversified consumer earnings.
> - Strategic pivots include 5G monetization (253M subscribers) and Quick Commerce leadership (1.6M orders/month).
> 
> **RISK FRAMEWORK**:
> - E&P decline: KG-D6 field drop and LNG price volatility could pressure margins.
> - Petrochemical overcapacity: Asian operating rates at 80% compression.
> 
> **THESIS**:
> - Rating: **Overweight**. Premium justified by diversified growth levers and strong execution.
> - Fair value range: Rs 1550–1700.

## Technical Requirements for Production

-   **LLM Provider**: Priority given to Mistral (mistral-large-latest) for its performance in financial reasoning, with fallbacks to Gemini and OpenAI.
-   **Async Parallelism**: Sub-agents must execute in parallel using `ThreadPoolExecutor` to keep total processing time under 5-7 seconds for complex RAG queries.
-   **Guardrails**: Implementation of `ScopeGuardrail` and `ResponseFactChecker` to ensure numerical claims are supported by the retrieved context.

# PRD-151: LLM Sentiment Engine

## Overview
AI-powered financial sentiment analysis using the multi-model provider system (PRD-132). Adds nuanced sentiment extraction with aspect-level decomposition, entity resolution, and predictive momentum forecasting beyond what keyword-based or FinBERT approaches can achieve.

## Architecture
```
Text Input → LLMSentimentAnalyzer → ProviderRouter → Claude/GPT/Gemini
                     ↓
              AspectExtractor → product/financials/management/regulatory
                     ↓
              EntityResolver → per-company, per-person sentiment
                     ↓
           SentimentPredictor → momentum forecasting (no LLM needed)
```

## Components

### LLM Sentiment Analyzer (`analyzer.py`)
- **Structured JSON extraction**: Sentiment label, score (-1 to +1), confidence, reasoning, themes, tickers
- **Urgency classification**: low/medium/high for breaking news detection
- **Time horizon**: short/medium/long for temporal relevance
- **Batch mode**: Analyze multiple texts in a single LLM call
- **Fallback chain**: Claude Haiku → GPT-4o Mini → Gemini Flash → keyword-based
- **Result caching**: In-memory cache to avoid duplicate analysis
- **Cost estimation**: Pre-compute analysis cost per text

### Aspect Extractor (`aspects.py`)
- **8 financial aspects**: product, financials, management, competitive, market, regulatory, growth, risk
- **Per-aspect scoring**: Independent sentiment score and confidence per aspect
- **Conflict detection**: Flags when aspects disagree (e.g., strong product + regulatory risk)
- **Evidence extraction**: Quotes from text supporting each aspect score
- **Rule-based fallback**: Keyword detection when no LLM available

### Entity Resolver (`entity.py`)
- **7 entity types**: company, person, sector, product, index, currency, commodity
- **Ticker mapping**: Resolves entity names to stock ticker symbols
- **Relationship extraction**: competition, partnership, subsidiary, comparison
- **Disambiguated sentiment**: Separates "AAPL good, GOOGL bad" into distinct signals
- **Rule fallback**: Known company name → ticker lookup + proximity sentiment

### Sentiment Predictor (`predictor.py`)
- **EMA-based forecasting**: Fast (5) and slow (20) exponential moving averages
- **Momentum tracking**: Rate of change over configurable window
- **Reversal detection**: EMA crossover + deceleration + extremity signals
- **Half-life estimation**: How quickly sentiment decays toward neutral
- **4 forecast horizons**: 4h, 24h, 3d, 7d
- **Mean reversion**: Exponential decay toward zero over forecast horizon
- **No LLM required**: Pure computation from historical observations

## Database Tables
- `llm_sentiment_results`: Raw LLM analysis outputs with cost tracking
- `llm_entity_sentiments`: Per-entity sentiment linked to analysis results
- `llm_sentiment_forecasts`: Point-in-time sentiment predictions

## Dashboard
4-tab Streamlit interface:
1. **Sentiment Analysis**: Text input → structured sentiment result with batch mode
2. **Aspect Extraction**: Per-aspect breakdown with conflict indicators
3. **Entity Resolution**: Company/person-level sentiment with relationship graph
4. **Prediction**: Momentum forecasting with improving/deteriorating/stable classification

## Integration Points
- **model_providers** (PRD-132): ModelRouter with fallback chains for LLM access
- **sentiment** (existing): Compatible SentimentScore format via sentiment_label property
- **social_intelligence** (PRD-141): Feeds social posts through LLM for nuanced analysis
- **alert_network** (PRD-142): High-urgency results can trigger alerts

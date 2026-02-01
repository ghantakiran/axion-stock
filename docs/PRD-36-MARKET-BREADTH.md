# PRD-36: Market Breadth Analytics

**Priority**: P1 | **Phase**: 25 | **Status**: Draft

---

## Problem Statement

Market breadth measures the degree of participation across a broad set of stocks. Indices can rise on a narrow set of leaders while most stocks decline — a bearish divergence. Breadth indicators help traders gauge the underlying health of a rally or selloff, providing early warnings of trend reversals and confirmation of momentum.

---

## Goals

1. **Advance-Decline Analysis** — Track advancing vs declining stocks and cumulative AD line
2. **New Highs/Lows** — Monitor 52-week new highs and new lows counts
3. **McClellan Oscillator & Summation** — Industry-standard breadth momentum indicators
4. **Breadth Thrust** — Detect rare breadth thrust signals that confirm strong trend starts
5. **Market Health Scoring** — Composite score combining multiple breadth signals
6. **Sector Breadth** — Breakdown of breadth by sector for rotation analysis

---

## Detailed Requirements

### R1: Advance-Decline Indicators

#### R1.1: Daily Breadth Snapshot
- Count of advancing, declining, and unchanged stocks
- Advance-decline ratio
- Cumulative advance-decline line
- Up volume vs down volume

#### R1.2: AD Line Signals
- AD line trend (rising/falling/flat)
- Divergence vs index (bullish/bearish divergence)
- AD line moving average crossovers

### R2: New Highs / New Lows

#### R2.1: NH/NL Tracking
- Daily 52-week new highs and new lows counts
- NH-NL difference and ratio
- 10-day moving average of NH-NL

#### R2.2: Signals
- High Pole: NH spike above threshold
- Low Pole: NL spike above threshold
- Divergence vs index price

### R3: McClellan Oscillator

#### R3.1: Calculation
- 19-day EMA and 39-day EMA of daily net advances
- McClellan Oscillator = 19-EMA - 39-EMA
- McClellan Summation Index = cumulative sum of Oscillator

#### R3.2: Signals
- Zero-line crossovers
- Overbought (>100) / Oversold (<-100) levels
- Summation Index trend

### R4: Breadth Thrust

#### R4.1: Thrust Detection
- Breadth thrust: 10-day EMA of (advances / (advances + declines)) moves from <0.40 to >0.615
- Track days since last thrust
- Historical thrust dates and subsequent returns

### R5: Market Health Score

#### R5.1: Composite Score
- Combine AD line, NH/NL, McClellan, thrust signals
- Score from 0 (extreme bearish) to 100 (extreme bullish)
- Health levels: Very Bearish / Bearish / Neutral / Bullish / Very Bullish

### R6: Sector Breadth

#### R6.1: Per-Sector Metrics
- AD ratio per GICS sector
- Sector breadth ranking
- Sector breadth momentum (improving/deteriorating)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Divergence detection accuracy | >75% |
| Thrust signal hit rate | >80% (historically validated) |
| Composite score correlation with forward returns | >0.3 |
| Calculation latency | <500ms for full market |

---

## Dependencies

- Data infrastructure (PRD-01)
- Sector rotation (PRD-33)
- Market scanner (PRD-30)

---

*Owner: Product Engineering Lead*
*Last Updated: January 2026*

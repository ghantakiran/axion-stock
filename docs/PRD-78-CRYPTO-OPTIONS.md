# PRD-78: Crypto Options Platform

## Overview
Crypto derivatives platform with Black-76 option pricing, greeks computation, implied volatility solver, volatility surface construction, perpetual futures tracking, funding rate analysis, spot-futures basis analytics, put/call ratio, and max pain calculation.

## Components

### 1. Crypto Option Pricer (`src/crypto_options/pricing.py`)
- **CryptoOptionPricer** — Black-76 model pricing for crypto options
- Forward price calculation with cost of carry
- Full greeks: delta, gamma, theta (per day), vega (per 1% vol)
- **Implied Volatility** — Newton-Raphson solver with clamping (0.01-5.0)
- **Volatility Surface** — Build IV surface from market quotes across strikes and expiries
- Intrinsic value computation for expired options

### 2. Derivatives Analyzer (`src/crypto_options/analytics.py`)
- **CryptoDerivativesAnalyzer** — Market analytics for crypto derivatives
- **Funding Rate** — Record, query history, compute average over N periods
- **Basis Analysis** — Spot-futures basis, perpetual premium, annualized basis
- **Put/Call Ratio** — By open interest from option quotes
- **Max Pain** — Calculate strike with minimum option seller payout
- **Perpetual Management** — CRUD for perpetual contract data

### 3. Configuration (`src/crypto_options/config.py`)
- **CryptoOptionType** — CALL, PUT
- **CryptoDerivativeType** — SPOT, PERPETUAL, FUTURES, OPTION, INVERSE_PERPETUAL, INVERSE_FUTURES
- **CryptoExchange** — DERIBIT, BINANCE, OKX, BYBIT, CME
- **SettlementType** — CASH, PHYSICAL, INVERSE
- **MarginType** — CROSS, ISOLATED, PORTFOLIO
- **SUPPORTED_UNDERLYINGS** — BTC, ETH, SOL with tick sizes and contract sizes
- **CryptoOptionsConfig** — Leverage, funding interval, risk-free rate, IV smoothing, delta/gamma limits

### 4. Models (`src/crypto_options/models.py`)
- **CryptoOptionContract** — Underlying, type, strike, expiry, exchange, settlement; properties: instrument_name, days_to_expiry, time_to_expiry, is_expired
- **CryptoOptionQuote** — Bid/ask/mark/last, volume, OI, underlying price, greeks; properties: spread, mid, moneyness
- **CryptoOptionGreeks** — delta, gamma, theta, vega, rho, IV
- **CryptoPerpetual** — Mark/index price, funding rate, OI, volume, leverage; properties: basis, basis_pct, annualized_funding
- **CryptoFundingRate** — Rate snapshot with annualized computation
- **CryptoBasisSpread** — Spot/futures/perp prices with basis analysis; properties: futures_basis, annualized_basis, perp_premium

## Database Tables
- `crypto_option_contracts` — Option contract definitions with exchange and settlement (migration 078)
- `crypto_funding_rates` — Historical funding rate snapshots (migration 078)

## Dashboard
4-tab Streamlit dashboard (`app/pages/crypto_options.py`):
1. **Option Pricer** — Interactive Black-76 pricing with greeks display
2. **Perpetuals & Funding** — BTC/ETH/SOL perpetual tracking with funding rates
3. **Basis Analysis** — Spot-futures basis with annualized rate
4. **Vol Surface** — Implied volatility surface across strikes

## Test Coverage
60 tests in `tests/test_crypto_options.py` covering enums/config, model properties/serialization (greeks, contracts, quotes, perpetuals, funding rates, basis spreads), pricing (call/put pricing, deep ITM/OTM, greeks signs, expired options, implied vol solver, vol surface), analytics (funding rate tracking/averaging, basis computation, put/call ratio, max pain, perpetual CRUD), and module imports.

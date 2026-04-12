# Project Context: Chase VSS Engine

## Core Identity
A sophisticated trend-following trading bot for the Indian derivatives market. Built to be fully autonomous but equipped with manual override safety features for the fund manager.

## Key Differentiators to Maintain
1. **Synthetic 09:20 Candles:** The system ignores the 09:15-09:20 timeframe to avoid opening volatility. Never revert to standard hourly resamples without this offset.
2. **Strict State Separation:** The UI does not execute trades; it only updates Firestore. The `/cron/evaluate` endpoint reads Firestore and executes. Never bind Kite execution directly to a UI button click (except Force Close).
3. **Paper vs. Real Isolation:** The system seamlessly handles Paper Trading alongside Real Trading. Mode is tracked at the trade-level snapshot, not globally.
4. **Broker Truth:** Zerodha Kite's actual position book is the ultimate source of truth. The engine reconciles against it before making entry/exit decisions.

## Future Enhancements Roadmap
1. Multi-day P&L equity curve charting on the frontend.
2. Slack/Discord webhook integrations for trade alerts.
3. Support for TradingView webhook ingestion to bypass the internal pandas-ta engine.
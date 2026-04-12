### ADR 001: Serverless vs. Always-On
**Date:** April 12, 2026
**Context:** Need an execution environment for the Chase strategy. Serverless requires pulling historical data hourly.
**Decision:** Selected GCP Cloud Run (Serverless) because Zerodha reduced the Historical API cost to ₹500/mo. 
**Consequences:** Saves server maintenance time; guarantees 100% uptime; requires paying the ₹500 add-on fee.

### ADR 002: Synthetic Hourly Candles
**Context:** Indian markets have massive volatility at the 09:15 open, distorting standard hourly EMA calculations.
**Decision:** We fetch 5-minute data and synthesize custom 60-minute candles starting at 09:20.
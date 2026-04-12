# Technical Architecture & State Management

## 1. Technology Stack
- **Backend:** Python 3, FastAPI.
- **Frontend:** HTML5, Tailwind CSS, Vue.js 3 (CDN).
- **Database:** Google Cloud Firestore (NoSQL).
- **Brokerage API:** Zerodha KiteConnect.
- **Quantitative Lib:** `pandas`, `pandas-ta-classic`.

## 2. Firestore Database Schema
The database acts as the central source of truth, completely decoupling the UI from the execution engine.

* `config/global`
  * `system_regime`: (String) NORMAL, VOLATILE, EXTREME.
  * `total_trading_capital`: (Float) Master account capital.
  * `manual_override.halt_all_trading`: (Bool) The Global Killswitch.
* `instruments/{id}` (e.g., NIFTY_FUT)
  * `symbol`, `instrument_token`, `lot_size`, `active` (Armed/Halted), `trade_mode` (PAPER/REAL).
  * `strategies`: Nested parameters for EMA period, sizing mode, and tolerances.
* `trades/{id}` (Transient Collection)
  * Exists *only* when a trade is active. Acts as the "Position Lock."
  * Stores the "Snapshot State": `symbol`, `type`, `quantity`, `entry_price`, `mode`.
* `history/` (Ledger Collection)
  * Append-only ledger recording all closed trades, tracking execution mode and calculated P&L.

## 3. Critical State Guardrails

### A. The "Baked-In" Execution Mode
When a trade is created, the UI's `trade_mode` (Paper/Real) is permanently stamped onto the `trades` document. The `execute_exit` function references this stamped mode, *not* the UI toggle. This prevents ghost positions if a user toggles the UI mode while a trade is running.

### B. Auto-Reconciliation (The Ghost Buster)
At the start of every cron cycle, the backend fetches live `net` positions from the Zerodha API. If Firestore indicates an active `REAL` trade exists, but the Kite API reports `quantity == 0` for that symbol, the engine assumes manual intervention occurred via the Kite App. The engine deletes its internal `trades` document, logging a "RECONCILED" event.

### C. The Global Killswitch
If `halt_all_trading` is `True`, the execution loop bypasses the Entry block entirely. Crucially, it continues to evaluate the Exit block, ensuring active trades are not stranded during a system halt.

## 4. API Endpoints
- `GET /cron/evaluate`: The master loop. Triggered hourly (09:20 - 15:20) by GCP Cloud Scheduler.
- `GET /api/sync-tokens`: Automatically fetches active NFO instruments from Kite and updates Firestore tokens based on Expiry Intelligence.
- `POST /api/force-close/{doc_id}`: Bypasses TA logic to immediately Market-Exit an active position.
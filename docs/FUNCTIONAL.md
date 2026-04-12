# Functional Specification: Chase Algo Engine

## 1. Product Overview
The Chase Engine is an automated, trend-following quantitative trading system designed exclusively for the Indian NFO (Derivatives) market, specifically targeting Nifty and Midcap Nifty futures. It features institutional-grade risk management, dynamic regime-based sizing, and lifecycle automation (rollovers).

## 2. Quantitative Strategy: The "Chase"
- **Evaluation Frequency:** Hourly (Triggered by Cron).
- **Data Formulation:** Generates synthetic 60-minute candles starting explicitly at 09:20 IST to filter out the high-volatility 09:15-09:20 AM opening print.
- **Indicators:** - 40-period EMA based on `HLC3` (High + Low + Close / 3).
  - 14-period ATR (Average True Range) for volatility measurement.
- **Entry Logic:**
  - **Long:** Hourly Close > EMA(40) + Signal Tolerance %. (Entry via SL-M at High).
  - **Short:** Hourly Close < EMA(40) - Signal Tolerance %. (Entry via SL-M at Low).
- **Exit Logic:**
  - Position is closed at Market when the hourly close crosses back over the EMA(40).

## 3. Position Sizing & Risk Management
The system supports two sizing models:
1. **FIXED Mode:** Executes a static, user-defined lot multiplier.
2. **VOLATILITY_ADJUSTED Mode:** - Uses the formula: `Lots = (Capital * Risk %) / (ATR * Lot Size)`.
   - Normalizes risk so the account risks exactly the targeted percentage (e.g., 1%) regardless of whether the market is moving 50 points a day or 200 points a day.

## 4. Market Regime Intelligence
The engine pulls the India VIX (Volatility Index) to define the trading environment and dynamically scales risk down in hostile conditions:
- **NORMAL (VIX < 18):** 1.0x Risk Multiplier.
- **VOLATILE (VIX 18 - 25):** 0.7x Risk Multiplier.
- **EXTREME (VIX > 25):** 0.4x Risk Multiplier.

## 5. Expiry & Rollover Automation
- **Post-20th of the Month:** The system automatically shifts focus to the *Next Month* contract for all **new** trade entries.
- **Post-24th of the Month:** If an active position is still open in the current month contract, the engine forces a simultaneous Market Exit (Current Month) and Market Entry (Next Month) to roll the position forward without manual intervention.
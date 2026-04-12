# Chase Algo Engine ⚡

An institutional-grade, trend-following quantitative trading system for the Indian NFO (Derivatives) market. Built with FastAPI, Vue.js, and Google Cloud Firestore.

## 📌 Features
- **Synthetic Hourly Candles:** Engine calculates custom hourly candles starting at 09:20 IST to filter out opening volatility.
- **Dynamic Regime Sizing:** Integrates with India VIX to automatically scale risk down during VOLATILE and EXTREME market conditions.
- **Automated Rollovers:** Expiry intelligence automatically switches to Next Month contracts post-20th, and rolls active positions post-24th.
- **Reconciliation Engine:** Cross-references the Zerodha Kite order book to prevent ghost positions if trades are closed manually on the Kite App.
- **Global Killswitch:** Single-click UI toggle to halt all new entries during black-swan events.

---

## 🛠️ Prerequisites

1. Python 3.9+ installed locally.
2. Google Cloud SDK (gcloud) installed and authenticated.
3. A Zerodha Kite Connect Developer Account (API Key + Secret).
4. A Google Cloud Project with Firestore (Native Mode) enabled. Database name: chase-vss.

---

## 💻 Local Development Setup

1. Initialize a Virtual Environment:
   python3 -m venv venv
   source venv/bin/activate

2. Install Dependencies:
   pip install -r requirements.txt

3. Set Environment Variables:
   export KITE_API_KEY="your_api_key_here"
   export KITE_API_SECRET="your_api_secret_here"

4. Seed the Database:
   python3 seed.py

5. Run the Server:
   uvicorn main:app --host 0.0.0.0 --port 8080 --reload

---

## 🚀 Google Cloud Deployment

### 1. Deploy the Engine to Cloud Run
gcloud run deploy chase-algo-engine \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars KITE_API_KEY="your_api_key",KITE_API_SECRET="your_api_secret"

### 2. Configure the Kite Redirect URL
Set the Redirect URL in Kite Console to:
https://<YOUR_CLOUD_RUN_URL>/auth/kite-redirect

### 3. Setup the Cron Job (Cloud Scheduler)
gcloud scheduler jobs create http chase-algo-cron \
  --schedule="20 9-15 * * 1-5" \
  --uri="https://<YOUR_CLOUD_RUN_URL>/cron/evaluate" \
  --http-method=GET \
  --time-zone="Asia/Kolkata" \
  --location="asia-south1"

---

## 📋 Daily Operations Playbook

1. Open Dashboard before 09:15 AM IST.
2. Click Broker Auth to generate daily token.
3. Ensure Global Status is ⚡ Live.
4. Ensure target instruments are Armed.
5. Verify Global Capital is correctly set.

---

## 🚨 Emergency Procedures

- Ghost Position: Manually close on Kite. Bot reconciles automatically on next run.
- Market Crash: Toggle Global Killswitch (⏸️ Trading Paused).
- Force Close: Click red Force Exit button on dashboard for immediate market exit.
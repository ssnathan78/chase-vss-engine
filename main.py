from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from kiteconnect import KiteConnect
from google.cloud import firestore
import os
import logging
from datetime import datetime, timedelta
from engine import evaluate_chase_strategy, calculate_market_regime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chase Algo Engine")
db = firestore.Client(database="chase-vss")
templates = Jinja2Templates(directory="templates")

KITE_API_KEY = os.environ.get("KITE_API_KEY")
KITE_API_SECRET = os.environ.get("KITE_API_SECRET")

# --- CORE UTILITIES ---

def log_to_db(doc_id, msg):
    db.collection("instruments").document(doc_id).collection("logs").add({
        "msg": msg, "time": datetime.now()
    })

def get_target_expiry_symbol(base_symbol="NIFTY"):
    now = datetime.now()
    curr_m = now.strftime('%y%b').upper()
    next_m = (now.replace(day=28) + timedelta(days=7)).strftime('%y%b').upper()
    is_expiry_week = now.day > 20
    is_rollover_zone = now.day >= 24
    return {
        "trade_this": f"{base_symbol}{next_m}" if is_expiry_week else f"{base_symbol}{curr_m}",
        "next_symbol": f"{base_symbol}{next_m}",
        "is_rollover_zone": is_rollover_zone
    }

def execute_exit(kite, trade, exit_price, doc_id, reason):
    if trade.get("mode") == "REAL":
        try:
            kite.place_order(
                tradingsymbol=trade['symbol'], exchange="NFO",
                transaction_type="SELL" if trade['type'] == "BUY" else "BUY",
                quantity=trade['quantity'], order_type="MARKET", 
                product="NRML", variety="regular"
            )
        except Exception as e:
            logger.error(f"Broker Exit Failed: {e}")

    pnl = (exit_price - trade['entry_price']) * trade['quantity']
    if trade['type'] == "SELL": pnl = -pnl
    
    db.collection("history").add({
        "symbol": trade['symbol'], "pnl": round(pnl, 2), "mode": trade['mode'],
        "entry": trade['entry_price'], "exit": exit_price, "reason": reason, "time": datetime.now()
    })
    db.collection("trades").document(doc_id).delete()
    log_to_db(doc_id, f"EXIT ({trade['mode']}): {reason} | P&L: ₹{round(pnl, 2)}")

# --- API ENDPOINTS ---

@app.get("/")
def command_center(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/config")
def get_config():
    global_doc = db.collection("config").document("global").get()
    instruments = []
    for doc in db.collection("instruments").stream():
        data = doc.to_dict()
        data['id'] = doc.id
        trade_doc = db.collection("trades").document(doc.id).get()
        data['active_trade'] = trade_doc.to_dict() if trade_doc.exists else None
        logs = db.collection("instruments").document(doc.id).collection("logs") \
                 .order_by("time", direction=firestore.Query.DESCENDING).limit(10).stream()
        data['logs'] = [{"msg": l.to_dict()['msg'], "time": l.to_dict()['time'].strftime('%H:%M:%S')} for l in logs]
        instruments.append(data)
    return {"global": global_doc.to_dict(), "instruments": instruments}

@app.post("/api/global-config")
async def update_global_config(request: Request):
    """Update global settings like the Killswitch."""
    data = await request.json()
    db.collection("config").document("global").set(data, merge=True)
    return {"status": "success"}

@app.post("/api/config/{doc_id}")
async def update_instrument_config(doc_id: str, request: Request):
    data = await request.json()
    db.collection("instruments").document(doc_id).set(data, merge=True)
    return {"status": "success"}

@app.post("/api/force-close/{doc_id}")
async def force_close_trade(doc_id: str):
    trade_ref = db.collection("trades").document(doc_id).get()
    if not trade_ref.exists: return {"status": "error", "msg": "No trade found"}
    trade = trade_ref.to_dict()
    auth_doc = db.collection("system_state").document("auth").get().to_dict()
    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(auth_doc["access_token"])
    quote = kite.quote(f"NFO:{trade['symbol']}")
    ltp = quote.get(f"NFO:{trade['symbol']}", {}).get("last_price", trade['entry_price'])
    execute_exit(kite, trade, ltp, doc_id, "MANUAL_FORCE_CLOSE")
    return {"status": "success"}

@app.get("/api/sync-tokens")
def sync_tokens():
    auth_doc = db.collection("system_state").document("auth").get().to_dict()
    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(auth_doc["access_token"])
    nfo_inst = kite.instruments("NFO")
    for doc in db.collection("instruments").stream():
        inst = doc.to_dict()
        base = "NIFTY" if "NIFTY" in inst['symbol'] else "MIDCPNIFTY"
        target_symbol = get_target_expiry_symbol(base)['trade_this']
        match = next((x for x in nfo_inst if x['tradingsymbol'] == target_symbol), None)
        if match:
            db.collection("instruments").document(doc.id).update({
                "symbol": target_symbol, "instrument_token": match['instrument_token']
            })
    return {"status": "success"}

# --- CRON EVALUATION ---

@app.get("/cron/evaluate")
def run_evaluation_cycle():
    global_doc = db.collection("config").document("global").get().to_dict()
    auth_doc = db.collection("system_state").document("auth").get().to_dict()
    if not auth_doc: return {"status": "error", "msg": "Auth Required"}
    
    kite = KiteConnect(api_key=KITE_API_KEY)
    kite.set_access_token(auth_doc["access_token"])
    
    # Update Market Regime
    regime = calculate_market_regime(kite)
    db.collection("config").document("global").update({"system_regime": regime})
    
    # Check Manual Pause (Global Killswitch)
    halt_active = global_doc.get("manual_override", {}).get("halt_all_trading", False)
    
    try: live_pos = kite.positions().get("net", [])
    except: live_pos = []

    for doc in db.collection("instruments").where("active", "==", True).stream():
        inst = doc.to_dict()
        doc_id, ui_mode = doc.id, inst.get("trade_mode", "PAPER")
        base_name = "NIFTY" if "NIFTY" in inst['symbol'] else "MIDCPNIFTY"
        expiry_info = get_target_expiry_symbol(base_name)
        
        trade_ref = db.collection("trades").document(doc_id).get()
        active_trade = trade_ref.to_dict() if trade_ref.exists else None
        
        try:
            analysis = evaluate_chase_strategy(kite, inst, global_doc.get("total_trading_capital", 1000000), regime)
            cur_p, ema = analysis.get("close"), analysis.get("ema")

            # 1. Reconciliation
            if active_trade and active_trade.get("mode") == "REAL":
                broker_p = next((p for p in live_pos if p['tradingsymbol'] == active_trade['symbol']), None)
                if not broker_p or int(broker_p['quantity']) == 0:
                    db.collection("trades").document(doc_id).delete()
                    log_to_db(doc_id, "RECONCILED: Position closed on Kite. Bot cleared.")
                    continue

            # 2. Execution Logic
            if active_trade:
                # Exits are always allowed for safety
                if (active_trade['type'] == 'BUY' and cur_p < ema) or (active_trade['type'] == 'SELL' and cur_p > ema):
                    execute_exit(kite, active_trade, cur_p, doc_id, "STRATEGY_EXIT")
                else:
                    log_to_db(doc_id, f"HOLDING {active_trade['type']} ({active_trade['mode']}) | Price: {cur_p}")

            elif analysis['signal'] in ["LONG_SETUP", "SHORT_SETUP"]:
                # BLOCK NEW ENTRIES IF GLOBAL HALT IS ON
                if halt_active:
                    log_to_db(doc_id, f"⏸️ ENTRY BLOCKED: Global Killswitch is ACTIVE. Signal: {analysis['signal']}")
                else:
                    side = "BUY" if analysis['signal'] == "LONG_SETUP" else "SELL"
                    trigger = int(analysis["trigger"]) + (1 if side == "BUY" else -1)
                    qty = analysis['lots'] * inst.get('lot_size', 1)
                    target_sym = expiry_info['trade_this']
                    oid = "PAPER_LOG"
                    if ui_mode == "REAL":
                        oid = kite.place_order(tradingsymbol=target_sym, exchange="NFO", transaction_type=side, quantity=qty, order_type="SL-M", trigger_price=trigger, product="NRML")
                    db.collection("trades").document(doc_id).set({"symbol": target_sym, "type": side, "quantity": qty, "entry_price": cur_p, "mode": ui_mode, "timestamp": datetime.now(), "order_id": oid})
                    log_to_db(doc_id, f"ENTRY ({ui_mode}): {side} on {target_sym} @ {trigger}")
            else:
                log_to_db(doc_id, f"SCANNING: No Setup. Price: {cur_p}")

        except Exception as e:
            log_to_db(doc_id, f"ERROR: {str(e)}")
    return {"status": "success"}

@app.get("/auth/login")
def login_redirect():
    return RedirectResponse(url=KiteConnect(api_key=KITE_API_KEY).login_url())

@app.get("/auth/kite-redirect")
def kite_callback(request_token: str):
    data = KiteConnect(api_key=KITE_API_KEY).generate_session(request_token, api_secret=KITE_API_SECRET)
    db.collection("system_state").document("auth").set({"access_token": data["access_token"], "time": datetime.now()})
    return RedirectResponse(url="/?auth=success")


import gspread
from google.oauth2.service_account import Credentials

import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

@app.get("/cron/summary")
def record_daily_summary():
    try:
        # 1. Authorize with Google Sheets using the default Service Account
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        gc = gspread.service_account(scopes=scopes)

        # 2. Open your existing "Liquidity Status" sheet
        spreadsheet = gc.open("Liquidity Status")
        
        # 3. Access or create a tab named "VSS Logs"
        try:
            worksheet = spreadsheet.worksheet("VSS Logs")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="VSS Logs", rows="100", cols="10")
            # Optional: Add headers if creating for the first time
            worksheet.append_row(["Date", "Total Trades", "Daily P&L", "Status"])

        # 4. Gather metrics from your bot's database 
        # (Replace these placeholders with your actual DB query logic)
        date_str = datetime.now().strftime("%Y-%m-%d")
        total_trades = 0 # Query your 'trades' table for today's count
        daily_pnl = 0.0   # Sum 'pnl' from today's closed trades 
        bot_status = "Success"

        # 5. Append the row to the sheet
        worksheet.append_row([date_str, total_trades, daily_pnl, bot_status])
        
        return {"status": "success", "message": "Daily summary updated in Google Sheets"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}
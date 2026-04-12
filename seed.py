from google.cloud import firestore
db = firestore.Client(database="chase-vss")

print("🌱 Injecting Global Config with Killswitch...")
db.collection("config").document("global").set({
    "system_regime": "NORMAL", 
    "total_trading_capital": 1000000, 
    "manual_override": {
        "halt_all_trading": False # Initial state: LIVE
    }
})

def seed_inst(id, sym, token, lot):
    db.collection("instruments").document(id).set({
        "symbol": sym, "instrument_token": token, "lot_size": lot, "active": True, "trade_mode": "PAPER",
        "execution_rules": {"use_synthetic_candles": True, "ignore_first_n_minutes": 5},
        "strategies": {"chase": {"params": {"ema_period": 40, "signal_tolerance_pct": 0.002}, "position_sizing": {"mode": "FIXED", "fixed_lots": 30}}}
    })

seed_inst("NIFTY_FUT", "NIFTY26APR", 256265, 65)
seed_inst("MIDCPNIFTY_FUT", "MIDCPNIFTY26APR", 256266, 120)
print("✅ Seed complete.")
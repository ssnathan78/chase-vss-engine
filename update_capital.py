from google.cloud import firestore

db = firestore.Client(database="chase-vss")

# This updates ONLY the capital without touching your Killswitch or Regime
db.collection("config").document("global").update({
    "total_trading_capital": 10000000
})

print("✅ Global Capital updated to 1 Cr (10,000,000).")
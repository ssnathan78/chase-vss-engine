import pandas as pd
import pandas_ta_classic as ta
import datetime
from kiteconnect import KiteConnect

VIX_TOKEN = 264969 # India VIX

def calculate_market_regime(kite: KiteConnect):
    try:
        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=5)
        records = kite.historical_data(VIX_TOKEN, from_date, to_date, "day")
        if not records: return "NORMAL"
        vix_ltp = records[-1]['close']
        if vix_ltp > 25: return "EXTREME"
        if vix_ltp > 18: return "VOLATILE"
        return "NORMAL"
    except:
        return "NORMAL"

def fetch_data(kite: KiteConnect, config: dict):
    token = config.get("instrument_token")
    rules = config.get("execution_rules", {})
    use_synthetic = rules.get("use_synthetic_candles", False)
    ignore_mins = rules.get("ignore_first_n_minutes", 0)
    to_date = datetime.datetime.now()
    from_date = to_date - datetime.timedelta(days=20) 
    records = kite.historical_data(token, from_date, to_date, "5minute" if use_synthetic else "60minute")
    if not records: return None
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    if use_synthetic:
        if ignore_mins > 0:
            df = df[~((df.index.hour == 9) & (df.index.minute < 15 + ignore_mins))]
        df = df.resample('1h', label='right', closed='right').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).dropna()
    return df

def evaluate_chase_strategy(kite: KiteConnect, config: dict, total_capital: float, regime: str):
    df = fetch_data(kite, config)
    if df is None or len(df) < 40:
        return {"signal": "INSUFFICIENT_DATA"}
    df['hlc3'] = (df['high'] + df['low'] + df['close']) / 3
    df['ema_40'] = ta.ema(df['hlc3'], length=40)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    latest = df.iloc[-1]
    ema = latest['ema_40']
    atr = latest['atr']
    close_price = latest['close']
    sizing_cfg = config.get("position_sizing", {})
    mode = sizing_cfg.get("mode", "FIXED")
    if mode == "VOLATILITY_ADJUSTED":
        risk_pct = sizing_cfg.get("vol_adjusted_params", {}).get("risk_per_trade_pct", 0.01)
        regime_multiplier = 0.7 if regime == "VOLATILE" else (0.4 if regime == "EXTREME" else 1.0)
        risk_amount = (total_capital * risk_pct) * regime_multiplier
        raw_lots = risk_amount / (atr * config.get("lot_size", 1))
        final_lots = min(max(1, int(raw_lots)), sizing_cfg.get("vol_adjusted_params", {}).get("max_lots", 10))
    else:
        final_lots = sizing_cfg.get("fixed_lots", 1)
    sig_tol = config.get("strategies", {}).get("chase", {}).get("params", {}).get("signal_tolerance_pct", 0.002)
    if close_price > ema * (1 + sig_tol):
        return {"signal": "LONG_SETUP", "ema": ema, "trigger": latest['high'], "lots": final_lots, "close": close_price}
    elif close_price < ema * (1 - sig_tol):
        return {"signal": "SHORT_SETUP", "ema": ema, "trigger": latest['low'], "lots": final_lots, "close": close_price}
    return {"signal": "NO_SETUP", "ema": ema, "close": close_price, "lots": final_lots}
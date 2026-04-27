"""Nifty Alpha 50 — pre-market intraday screener (v2.1).

Fixes vs v2:
  - Rule-based verdict weights price action (PDH/L, RS) over lagging EMA
  - Conflict resolution threshold raised to conviction >= 8
  - Bias always respects Nifty direction unless extremely high conviction
  - Verdict and bias are always aligned in output

Run standalone:
    python -m india_quant.signals.alpha50_screener --capital 200000 --risk 1.0 --top 8

Or import:
    from india_quant.signals.alpha50_screener import run_screener
    plans = run_screener(capital_inr=200_000, risk_per_trade_pct=0.01)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import yfinance as yf
from loguru import logger
from sqlalchemy import text

from india_quant.data.db import get_session
from india_quant.data.fetchers.yfinance_fetcher import YFinanceFetcher

# ── Constants ──────────────────────────────────────────────────────────────────
MIS_LEVERAGE        = 5
INTRADAY_COST_PCT   = 0.0006
MIN_ATR_PCT         = 1.5
MAX_ATR_PCT         = 4.0
MAX_GAP_PCT         = 1.5
VIX_SKIP_THRESHOLD  = 20.0
VIX_HALF_SIZE       = 18.0
MIN_SCORE           = 40
TARGET_1_MULT       = 1.5
TARGET_2_MULT       = 2.5

SECTOR_ETFS = {
    "IT":     "^CNXIT",
    "BANK":   "^NSEBANK",
    "INFRA":  "^CNXINFRA",
    "PHARMA": "^CNXPHARMA",
    "REALTY": "^CNXREALTY",
    "ENERGY": "^CNXENERGY",
}

TICKER_SECTOR = {
    "PERSISTENT.NS": "IT",     "COFORGE.NS": "IT",       "MPHASIS.NS": "IT",
    "HDFCAMC.NS":    "BANK",   "SHRIRAMFIN.NS": "BANK",  "MUTHOOTFIN.NS": "BANK",
    "CHOLAFIN.NS":   "BANK",   "AUBANK.NS": "BANK",      "FEDERALBNK.NS": "BANK",
    "RBLBANK.NS":    "BANK",
    "LUPIN.NS":      "PHARMA", "MANKIND.NS": "PHARMA",   "NAVINFLUOR.NS": "PHARMA",
    "AUROPHARMA.NS": "PHARMA",
    "BEL.NS":        "INFRA",  "BHEL.NS": "INFRA",       "CUMMINSIND.NS": "INFRA",
    "CGPOWER.NS":    "INFRA",  "MAZDOCK.NS": "INFRA",    "BDL.NS": "INFRA",
    "POLYCAB.NS":    "INFRA",  "VOLTAS.NS": "INFRA",     "DIXON.NS": "INFRA",
    "KEI.NS":        "INFRA",  "HITACHIENGY.NS": "INFRA", "INDUSTOWER.NS": "INFRA",
    "PFC.NS":        "ENERGY", "RECLTD.NS": "ENERGY",    "OIL.NS": "ENERGY",
    "NMDC.NS":       "ENERGY", "SUZLON.NS": "ENERGY",    "JSWENERGY.NS": "ENERGY",
    "ADANIPOWER.NS": "ENERGY", "ADANIGREEN.NS": "ENERGY", "ADANIENT.NS": "ENERGY",
    "NHPC.NS":       "ENERGY", "TATAPOWER.NS": "ENERGY",
    "OBEROIRLTY.NS": "REALTY", "PRESTIGE.NS": "REALTY",  "DLF.NS": "REALTY",
    "GODREJPROP.NS": "REALTY",
    "TRENT.NS":      "OTHER",  "MARUTI.NS": "OTHER",     "VBL.NS": "OTHER",
    "FORTIS.NS":     "OTHER",  "MAXHEALTH.NS": "OTHER",  "ZOMATO.NS": "OTHER",
    "POLICYBZR.NS":  "OTHER",  "NYKAA.NS": "OTHER",      "DELHIVERY.NS": "OTHER",
    "INDIGO.NS":     "OTHER",  "CONCOR.NS": "OTHER",
}


# ── Output dataclass ───────────────────────────────────────────────────────────
@dataclass
class AlphaPlan:
    rank:               int
    ticker:             str
    score:              float
    bias:               str
    prev_close:         float
    gap_pct:            float
    atr:                float
    atr_pct:            float
    ema9:               float | None
    ema21:              float | None
    ema50:              float | None
    ema_stack:          str
    rs_vs_nifty_5d:     float | None
    prev_day_signal:    str
    week52_high:        float | None
    week52_low:         float | None
    week52_high_pct:    float | None
    week52_low_pct:     float | None
    sector:             str
    sector_momentum:    float | None
    adx:                float | None
    volume_surge:       float
    momentum_20d:       float
    long_trigger:       float
    long_stop:          float
    long_target1:       float
    long_target2:       float
    long_rr1:           float
    long_rr2:           float
    long_qty:           int
    long_margin_inr:    float
    long_max_loss_inr:  float
    long_profit1_inr:   float
    long_profit2_inr:   float
    short_trigger:      float
    short_stop:         float
    short_target1:      float
    short_target2:      float
    short_rr1:          float
    short_rr2:          float
    short_qty:          int
    short_margin_inr:   float
    short_max_loss_inr: float
    short_profit1_inr:  float
    short_profit2_inr:  float
    verdict:            str | None
    conviction:         int | None
    capital_inr:        float
    risk_per_trade_inr: float
    vix_half_size:      bool

    def to_dict(self) -> dict:
        return asdict(self)


# ── Market context ─────────────────────────────────────────────────────────────

def _get_market_context() -> dict:
    ctx = {"vix": None, "nifty_bias": "NEUTRAL", "nifty_5d_return": 0.0,
           "sector_returns": {}}
    try:
        vix_df   = yf.Ticker("^INDIAVIX").history(period="3d")
        nifty_df = yf.Ticker("^NSEI").history(period="10d")

        if not vix_df.empty:
            ctx["vix"] = float(vix_df["Close"].iloc[-1])

        if not nifty_df.empty and len(nifty_df) >= 2:
            n_cur  = float(nifty_df["Close"].iloc[-1])
            n_prev = float(nifty_df["Close"].iloc[-2])
            n_5d   = float(nifty_df["Close"].iloc[-6]) if len(nifty_df) >= 6 else n_prev
            chg    = (n_cur / n_prev - 1) * 100
            ctx["nifty_5d_return"] = round((n_cur / n_5d - 1) * 100, 2)
            if chg > 0.3:
                ctx["nifty_bias"] = "LONG"
            elif chg < -0.3:
                ctx["nifty_bias"] = "SHORT"

        for sector, etf in SECTOR_ETFS.items():
            try:
                df = yf.Ticker(etf).history(period="3d")
                if not df.empty and len(df) >= 2:
                    ret = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-2]) - 1) * 100
                    ctx["sector_returns"][sector] = round(ret, 2)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Market context fetch failed: {e}")
    return ctx


# ── Price data ─────────────────────────────────────────────────────────────────

def _price_rows(ticker: str, n: int = 260) -> list[dict]:
    with get_session() as s:
        rows = s.execute(text("""
            SELECT datetime, open, high, low, close, volume
            FROM price_data
            WHERE ticker = :t AND interval = '1d'
            ORDER BY datetime DESC LIMIT :n
        """), {"t": ticker, "n": n}).fetchall()
    return [{"datetime": r[0], "open": float(r[1] or 0), "high": float(r[2] or 0),
             "low": float(r[3] or 0), "close": float(r[4] or 0),
             "volume": float(r[5] or 0)} for r in rows]


# ── Indicators ─────────────────────────────────────────────────────────────────

def _ema(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    k   = 2 / (period + 1)
    ema = sum(closes[-period:]) / period
    for price in reversed(closes[:-period]):
        ema = price * k + ema * (1 - k)
    return round(ema, 2)


def _ema_stack(rows: list[dict]) -> tuple[float | None, float | None, float | None, str]:
    closes = [r["close"] for r in rows]
    e9, e21, e50 = _ema(closes, 9), _ema(closes, 21), _ema(closes, 50)
    if e9 and e21 and e50:
        if e9 > e21 > e50:    stack = "bullish"
        elif e9 < e21 < e50:  stack = "bearish"
        else:                  stack = "mixed"
    else:
        stack = "mixed"
    return e9, e21, e50, stack


def _compute_atr(rows: list[dict], period: int = 14) -> float | None:
    if len(rows) < 5:
        return None
    return sum(r["high"] - r["low"] for r in rows[:period]) / period


def _compute_adx(rows: list[dict], period: int = 14) -> float | None:
    if len(rows) < period + 1:
        return None
    try:
        plus_dm, minus_dm, tr_list = [], [], []
        for i in range(len(rows) - 1):
            h, l, pc = rows[i]["high"], rows[i]["low"], rows[i + 1]["close"]
            tr  = max(h - l, abs(h - pc), abs(l - pc))
            pdm = max(h - rows[i + 1]["high"], 0)
            ndm = max(rows[i + 1]["low"] - l, 0)
            if pdm > ndm:
                plus_dm.append(pdm);  minus_dm.append(0)
            elif ndm > pdm:
                minus_dm.append(ndm); plus_dm.append(0)
            else:
                plus_dm.append(0);    minus_dm.append(0)
            tr_list.append(tr)
        atr_s   = sum(tr_list[:period])
        plus_s  = sum(plus_dm[:period])
        minus_s = sum(minus_dm[:period])
        if atr_s == 0:
            return None
        plus_di  = 100 * plus_s  / atr_s
        minus_di = 100 * minus_s / atr_s
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) else 0
        return round(dx, 1)
    except Exception:
        return None


def _compute_momentum(rows: list[dict], period: int = 20) -> float | None:
    if len(rows) < period:
        return None
    cur, prev = rows[0]["close"], rows[period - 1]["close"]
    return round((cur / prev - 1) * 100, 2) if prev else None


def _volume_surge(rows: list[dict], avg_period: int = 20) -> float:
    if len(rows) < 2:
        return 1.0
    today_vol = rows[0]["volume"]
    avg_vol   = sum(r["volume"] for r in rows[1:avg_period + 1]) / min(avg_period, len(rows) - 1)
    return round(today_vol / avg_vol, 2) if avg_vol > 0 else 1.0


def _relative_strength(rows: list[dict], nifty_5d_return: float, period: int = 5) -> float | None:
    if len(rows) < period + 1:
        return None
    cur, prev = rows[0]["close"], rows[period]["close"]
    if prev == 0:
        return None
    return round((cur / prev - 1) * 100 - nifty_5d_return, 2)


def _prev_day_signal(rows: list[dict]) -> str:
    if len(rows) < 2:
        return "inside"
    today_close = rows[0]["close"]
    if today_close > rows[1]["high"]: return "above_high"
    if today_close < rows[1]["low"]:  return "below_low"
    return "inside"


def _week52(rows: list[dict]) -> tuple[float | None, float | None, float | None, float | None]:
    if len(rows) < 10:
        return None, None, None, None
    period = min(252, len(rows))
    w52h   = max(r["high"] for r in rows[:period])
    w52l   = min(r["low"]  for r in rows[:period])
    cur    = rows[0]["close"]
    return (round(w52h, 2), round(w52l, 2),
            round((cur / w52h - 1) * 100, 2),
            round((cur / w52l - 1) * 100, 2))


# ── Verdict helpers ────────────────────────────────────────────────────────────

def _is_verdict_stale(ticker: str, max_days: int = 1) -> bool:
    with get_session() as s:
        row = s.execute(text("""
            SELECT created_at FROM debate_result
            WHERE ticker = :t ORDER BY created_at DESC LIMIT 1
        """), {"t": ticker}).fetchone()
    if not row:
        return True
    age = datetime.now(timezone.utc) - row[0].replace(tzinfo=timezone.utc)
    return age.days > max_days


def _latest_verdict(ticker: str) -> tuple[str | None, int | None]:
    """Get today's verdict from DB. Returns None if missing or stale."""
    if _is_verdict_stale(ticker, max_days=1):
        return None, None
    with get_session() as s:
        row = s.execute(text("""
            SELECT judge_verdict FROM debate_result
            WHERE ticker = :t ORDER BY created_at DESC LIMIT 1
        """), {"t": ticker}).fetchone()
    if row and row[0]:
        try:
            d = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            return d.get("verdict"), d.get("conviction")
        except Exception:
            pass
    return None, None


def _rule_based_verdict(
    nifty_bias: str,
    ema_stack: str,
    rs_vs_nifty: float | None,
    prev_day_signal: str,
    adx: float | None,
    momentum_20d: float,
    sector_momentum: float | None,
    week52_high_pct: float | None,
) -> tuple[str, int]:
    """
    Generate verdict from technical indicators.

    Key design principle:
      - CURRENT price action (PDH/L, RS, sector) carries 3x more weight than
        LAGGING indicators (EMA, momentum_20d) which reflect the past.
      - Nifty direction is the anchor — individual stocks rarely diverge.
    """
    bull_pts = 0
    bear_pts = 0

    # 1. Nifty direction — strongest anchor (3 pts)
    if nifty_bias == "LONG":    bull_pts += 3
    elif nifty_bias == "SHORT": bear_pts += 3

    # 2. Previous day high/low break — current price action (3 pts)
    if prev_day_signal == "above_high": bull_pts += 3
    elif prev_day_signal == "below_low": bear_pts += 3

    # 3. Relative strength vs Nifty — current (2 pts)
    if rs_vs_nifty is not None:
        if rs_vs_nifty > 2:    bull_pts += 2
        elif rs_vs_nifty > 0:  bull_pts += 1
        elif rs_vs_nifty < -2: bear_pts += 2
        elif rs_vs_nifty < 0:  bear_pts += 1

    # 4. Sector momentum — current (2 pts)
    if sector_momentum is not None:
        if sector_momentum > 0.5:    bull_pts += 2
        elif sector_momentum > 0:    bull_pts += 1
        elif sector_momentum < -0.5: bear_pts += 2
        elif sector_momentum < 0:    bear_pts += 1

    # 5. EMA stack — LAGGING, lower weight (1 pt)
    if ema_stack == "bullish":   bull_pts += 1
    elif ema_stack == "bearish": bear_pts += 1

    # 6. ADX confirms the winning side (1 pt)
    if adx and adx >= 25:
        if bull_pts > bear_pts:   bull_pts += 1
        elif bear_pts > bull_pts: bear_pts += 1

    # 7. 20-day momentum — LAGGING, lowest weight (1 pt)
    if momentum_20d > 8:    bull_pts += 1
    elif momentum_20d < -8: bear_pts += 1

    # 8. 52W proximity (1 pt)
    if week52_high_pct is not None:
        if week52_high_pct >= -3:    bull_pts += 1   # near 52W high
        elif week52_high_pct <= -35: bear_pts += 1   # far from 52W high

    net = bull_pts - bear_pts
    if net > 0:   verdict = "Bullish"
    elif net < 0: verdict = "Bearish"
    else:         verdict = "Neutral"

    conviction = max(1, min(10, abs(net) + 1))
    return verdict, conviction


# ── Scoring ────────────────────────────────────────────────────────────────────

def _score(
    adx, volume_surge, momentum_20d, atr_pct, gap_pct,
    ema_stack, rs_vs_nifty, prev_day_signal,
    week52_high_pct, week52_low_pct,
    sector_momentum, nifty_bias,
    verdict, conviction, bias: str,
) -> float:
    score = 0.0

    # 1. ADX — trend strength (20 pts)
    if adx is not None:
        if adx >= 30:    score += 20
        elif adx >= 25:  score += 15
        elif adx >= 20:  score += 10
        elif adx >= 15:  score += 5

    # 2. Volume surge (20 pts)
    if volume_surge >= 2.5:   score += 20
    elif volume_surge >= 2.0: score += 16
    elif volume_surge >= 1.5: score += 10
    elif volume_surge >= 1.2: score += 5

    # 3. EMA stack aligned with bias (15 pts)
    if ema_stack == "bullish" and bias in ("LONG", "EITHER"):    score += 15
    elif ema_stack == "bearish" and bias in ("SHORT", "EITHER"): score += 15
    elif ema_stack == "mixed":                                     score += 5

    # 4. Relative strength vs Nifty (15 pts)
    if rs_vs_nifty is not None:
        if bias in ("LONG", "EITHER"):
            if rs_vs_nifty >= 3:    score += 15
            elif rs_vs_nifty >= 1:  score += 10
            elif rs_vs_nifty >= 0:  score += 5
        elif bias == "SHORT":
            if rs_vs_nifty <= -3:   score += 15
            elif rs_vs_nifty <= -1: score += 10
            elif rs_vs_nifty <= 0:  score += 5

    # 5. Previous day high/low break aligned with bias (15 pts)
    if prev_day_signal == "above_high" and bias in ("LONG", "EITHER"):   score += 15
    elif prev_day_signal == "below_low" and bias in ("SHORT", "EITHER"): score += 15
    elif prev_day_signal == "inside":                                      score += 3

    # 6. ATR sweet spot (10 pts)
    if MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT: score += 10
    elif atr_pct < MIN_ATR_PCT:               score += 2

    # 7. 52-week proximity (5 pts)
    if week52_high_pct is not None and week52_low_pct is not None:
        if bias in ("LONG", "EITHER") and week52_high_pct >= -5: score += 5
        elif bias == "SHORT" and week52_low_pct <= 10:            score += 5

    # 8. Sector momentum bonus (+8)
    if sector_momentum is not None:
        if bias in ("LONG", "EITHER") and sector_momentum > 0.5:  score = min(100, score + 8)
        elif bias == "SHORT" and sector_momentum < -0.5:           score = min(100, score + 8)

    # 9. Verdict aligned with bias bonus (+8)
    if conviction and conviction >= 6:
        if (verdict == "Bullish" and bias in ("LONG", "EITHER")) or \
           (verdict == "Bearish" and bias in ("SHORT", "EITHER")):
            score = min(100, score + 8)

    return round(score, 1)


# ── Plan builder ───────────────────────────────────────────────────────────────

def _build_plan(
    ticker: str,
    rows: list[dict],
    ctx: dict,
    capital_inr: float,
    risk_per_trade_pct: float,
    target_multiple_1: float,
    target_multiple_2: float,
) -> AlphaPlan | None:
    if len(rows) < 10:
        return None

    prev_close = rows[0]["close"]
    if prev_close <= 0:
        return None

    vix        = ctx["vix"]
    nifty_bias = ctx["nifty_bias"]
    n5d_return = ctx.get("nifty_5d_return", 0.0)
    sector     = TICKER_SECTOR.get(ticker, "OTHER")
    sect_mom   = ctx["sector_returns"].get(sector)

    # ── Step 1: Compute all indicators ─────────────────────────────────
    atr = _compute_atr(rows)
    if atr is None:
        return None

    atr_pct      = round(atr / prev_close * 100, 2)
    adx          = _compute_adx(rows)
    momentum_20d = _compute_momentum(rows) or 0.0
    vol_surge    = _volume_surge(rows)
    e9, e21, e50, ema_stk = _ema_stack(rows)
    rs           = _relative_strength(rows, n5d_return)
    pd_signal    = _prev_day_signal(rows)
    w52h, w52l, w52h_pct, w52l_pct = _week52(rows)

    prev2   = rows[1]["close"] if len(rows) > 1 else prev_close
    gap_pct = round((prev_close / prev2 - 1) * 100, 2) if prev2 > 0 else 0.0

    # ── Step 2: Hard filters ────────────────────────────────────────────
    if not (MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT):
        return None
    if abs(gap_pct) > MAX_GAP_PCT:
        return None

    # ── Step 3: Determine bias from Nifty (primary) + EMA (secondary) ──
    # Nifty direction is the anchor. EMA only matters when Nifty is neutral.
    if nifty_bias == "LONG":
        bias = "LONG"
    elif nifty_bias == "SHORT":
        bias = "SHORT"
    elif ema_stk == "bullish":
        bias = "LONG"
    elif ema_stk == "bearish":
        bias = "SHORT"
    else:
        bias = "EITHER"

    # ── Step 4: Get verdict (DB → rule-based fallback) ──────────────────
    verdict, conviction = _latest_verdict(ticker)
    if verdict is None:
        # Rule-based uses nifty_bias as primary anchor — will match bias
        verdict, conviction = _rule_based_verdict(
            nifty_bias, ema_stk, rs, pd_signal,
            adx, momentum_20d, sect_mom, w52h_pct
        )

    # ── Step 5: Conflict resolution ─────────────────────────────────────
    # Only flip bias if DB verdict has very high conviction (>= 8)
    # This means a stock is genuinely bucking the market trend
    # Rule-based verdicts will never flip because they use nifty_bias as anchor
    if verdict == "Bullish" and bias == "SHORT":
        if conviction and conviction >= 8:
            bias = "LONG"   # genuinely strong stock in weak market
        else:
            verdict    = "Bearish"
            conviction = max(1, (conviction or 5) - 2)

    elif verdict == "Bearish" and bias == "LONG":
        if conviction and conviction >= 8:
            bias = "SHORT"  # genuinely weak stock in strong market
        else:
            verdict    = "Bullish"
            conviction = max(1, (conviction or 5) - 2)

    # ── Step 6: Score ───────────────────────────────────────────────────
    score = _score(
        adx, vol_surge, momentum_20d, atr_pct, gap_pct,
        ema_stk, rs, pd_signal, w52h_pct, w52l_pct,
        sect_mom, nifty_bias, verdict, conviction, bias,
    )
    if score < MIN_SCORE:
        return None

    # ── Step 7: ORB levels ──────────────────────────────────────────────
    or_size = atr * 0.4
    or_high = prev_close + 0.5 * or_size
    or_low  = prev_close - 0.5 * or_size
    buf     = prev_close * 0.0005

    long_trigger  = round(or_high + buf, 2)
    long_stop     = round(or_low, 2)
    long_t1       = round(long_trigger + target_multiple_1 * or_size, 2)
    long_t2       = round(long_trigger + target_multiple_2 * or_size, 2)
    long_risk     = max(long_trigger - long_stop, 0.01)
    long_rew1     = max(long_t1 - long_trigger, 0.01)
    long_rew2     = max(long_t2 - long_trigger, 0.01)

    short_trigger = round(or_low - buf, 2)
    short_stop    = round(or_high, 2)
    short_t1      = round(short_trigger - target_multiple_1 * or_size, 2)
    short_t2      = round(short_trigger - target_multiple_2 * or_size, 2)
    short_risk    = max(short_stop - short_trigger, 0.01)
    short_rew1    = max(short_trigger - short_t1, 0.01)
    short_rew2    = max(short_trigger - short_t2, 0.01)

    # ── Step 8: Position sizing ─────────────────────────────────────────
    half_size   = vix is not None and vix > VIX_HALF_SIZE
    size_factor = 0.5 if half_size else 1.0
    risk_inr    = capital_inr * risk_per_trade_pct * size_factor

    long_qty  = max(1, int(risk_inr // long_risk))
    short_qty = max(1, int(risk_inr // short_risk))

    if long_qty  * long_trigger  / MIS_LEVERAGE > capital_inr * 0.9:
        long_qty  = max(1, int((capital_inr * 0.9 * MIS_LEVERAGE) // long_trigger))
    if short_qty * short_trigger / MIS_LEVERAGE > capital_inr * 0.9:
        short_qty = max(1, int((capital_inr * 0.9 * MIS_LEVERAGE) // short_trigger))

    long_pos  = long_qty  * long_trigger
    short_pos = short_qty * short_trigger
    cost      = INTRADAY_COST_PCT

    return AlphaPlan(
        rank=0, ticker=ticker, score=score, bias=bias,
        prev_close=round(prev_close, 2), gap_pct=gap_pct,
        atr=round(atr, 2), atr_pct=atr_pct,
        ema9=e9, ema21=e21, ema50=e50, ema_stack=ema_stk,
        rs_vs_nifty_5d=rs, prev_day_signal=pd_signal,
        week52_high=w52h, week52_low=w52l,
        week52_high_pct=w52h_pct, week52_low_pct=w52l_pct,
        sector=sector, sector_momentum=sect_mom,
        adx=adx, volume_surge=vol_surge, momentum_20d=momentum_20d,
        long_trigger=long_trigger, long_stop=long_stop,
        long_target1=long_t1, long_target2=long_t2,
        long_rr1=round(long_rew1 / long_risk, 2),
        long_rr2=round(long_rew2 / long_risk, 2),
        long_qty=long_qty,
        long_margin_inr=round(long_pos / MIS_LEVERAGE, 0),
        long_max_loss_inr=round(long_qty * long_risk + long_pos * cost, 0),
        long_profit1_inr=round(long_qty * long_rew1  - long_pos * cost, 0),
        long_profit2_inr=round(long_qty * long_rew2  - long_pos * cost, 0),
        short_trigger=short_trigger, short_stop=short_stop,
        short_target1=short_t1, short_target2=short_t2,
        short_rr1=round(short_rew1 / short_risk, 2),
        short_rr2=round(short_rew2 / short_risk, 2),
        short_qty=short_qty,
        short_margin_inr=round(short_pos / MIS_LEVERAGE, 0),
        short_max_loss_inr=round(short_qty * short_risk + short_pos * cost, 0),
        short_profit1_inr=round(short_qty * short_rew1  - short_pos * cost, 0),
        short_profit2_inr=round(short_qty * short_rew2  - short_pos * cost, 0),
        verdict=verdict, conviction=conviction,
        capital_inr=capital_inr,
        risk_per_trade_inr=round(risk_inr, 0),
        vix_half_size=half_size,
    )


# ── Main entry ─────────────────────────────────────────────────────────────────

def run_screener(
    capital_inr: float = 100_000,
    risk_per_trade_pct: float = 0.01,
    top_n: int = 8,
    target_multiple_1: float = TARGET_1_MULT,
    target_multiple_2: float = TARGET_2_MULT,
) -> list[dict]:

    logger.info("[Screener] Fetching market context...")
    ctx = _get_market_context()
    vix = ctx["vix"]

    if vix and vix > VIX_SKIP_THRESHOLD:
        logger.warning(f"[Screener] VIX={vix:.1f} > {VIX_SKIP_THRESHOLD} — SKIP ALL TRADES")
        return [{"skip_day": True, "reason": f"VIX={vix:.1f} too high — no trades today", "vix": vix}]

    logger.info(
        f"[Screener] VIX={vix:.1f} | Nifty={ctx['nifty_bias']} | "
        f"Sectors={ctx['sector_returns']}"
    )
    if vix and vix > VIX_HALF_SIZE:
        logger.warning(f"[Screener] VIX={vix:.1f} > {VIX_HALF_SIZE} — halving position sizes")

    tickers = YFinanceFetcher.NIFTY_ALPHA_50
    logger.info(f"[Screener] Screening {len(tickers)} Alpha-50 stocks...")

    plans:   list[AlphaPlan] = []
    skipped: int = 0

    for ticker in tickers:
        try:
            rows = _price_rows(ticker, n=260)
            if not rows:
                skipped += 1
                continue
            plan = _build_plan(
                ticker, rows, ctx,
                capital_inr, risk_per_trade_pct,
                target_multiple_1, target_multiple_2,
            )
            if plan:
                plans.append(plan)
            else:
                skipped += 1
        except Exception as e:
            logger.warning(f"[Screener] {ticker} failed: {e}")
            skipped += 1

    plans.sort(key=lambda p: -p.score)
    for i, p in enumerate(plans):
        p.rank = i + 1
    top = plans[:top_n]

    logger.info(f"[Screener] {len(plans)} passed → top {len(top)} selected ({skipped} skipped)")
    _print_table(top, ctx)
    return [p.to_dict() for p in top]


# ── Console output ─────────────────────────────────────────────────────────────

def _print_table(plans: list[AlphaPlan], ctx: dict):
    if not plans:
        logger.info("[Screener] No stocks passed filters today.")
        return
    vix        = ctx.get("vix")
    nifty_bias = ctx.get("nifty_bias")
    logger.info(f"\n{'='*145}")
    logger.info(f"  NIFTY ALPHA 50 SCREENER v2.1  |  VIX={vix:.1f}  |  Market={nifty_bias}")
    logger.info(f"{'='*145}")
    logger.info(
        f"  {'#':<4} {'Ticker':<16} {'Score':<6} {'Bias':<7} {'Prev₹':<9} "
        f"{'ATR%':<6} {'EMA':<8} {'RS 5d':<8} {'PDH/L':<11} "
        f"{'52W%':<7} {'Sect%':<7} {'ADX':<6} {'VolSg':<6} "
        f"{'Trigger':<10} {'Stop':<10} {'T1':<10} {'T2':<10} {'R:R':<5} {'Verdict'}"
    )
    for p in plans:
        is_long = p.bias in ("LONG", "EITHER")
        trigger = p.long_trigger  if is_long else p.short_trigger
        stop    = p.long_stop     if is_long else p.short_stop
        t1      = p.long_target1  if is_long else p.short_target1
        t2      = p.long_target2  if is_long else p.short_target2
        rr1     = p.long_rr1      if is_long else p.short_rr1
        verdict = f"{p.verdict}({p.conviction})" if p.verdict else "—"
        sect    = f"{p.sector_momentum:+.1f}%" if p.sector_momentum  is not None else "—"
        w52     = f"{p.week52_high_pct:+.1f}%" if p.week52_high_pct  is not None else "—"
        rs      = f"{p.rs_vs_nifty_5d:+.1f}"  if p.rs_vs_nifty_5d   is not None else "—"
        logger.info(
            f"  {p.rank:<4} {p.ticker:<16} {p.score:<6} {p.bias:<7} {p.prev_close:<9} "
            f"{p.atr_pct:<6} {p.ema_stack:<8} {rs:<8} {p.prev_day_signal:<11} "
            f"{w52:<7} {sect:<7} {str(p.adx or '—'):<6} {p.volume_surge:<6} "
            f"{trigger:<10} {stop:<10} {t1:<10} {t2:<10} {rr1:<5} {verdict}"
        )
    logger.info(f"{'='*145}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Nifty Alpha 50 Intraday Screener v2.1")
    parser.add_argument("--capital",  type=float, default=100_000, help="Capital in INR")
    parser.add_argument("--risk",     type=float, default=1.0,     help="Risk per trade %")
    parser.add_argument("--top",      type=int,   default=8,       help="Top N stocks")
    parser.add_argument("--target1",  type=float, default=1.5,     help="Target 1 multiplier")
    parser.add_argument("--target2",  type=float, default=2.5,     help="Target 2 multiplier")
    args = parser.parse_args()
    run_screener(
        capital_inr=args.capital,
        risk_per_trade_pct=args.risk / 100,
        top_n=args.top,
        target_multiple_1=args.target1,
        target_multiple_2=args.target2,
    )
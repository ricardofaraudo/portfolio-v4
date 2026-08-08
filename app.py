"""
PORTFOLIO INTELLIGENCE v4
- All v3 features retained
- NEW: BTC Tracker tab with full stack breakdown and 10 BTC goal
- NEW: BTC ratio columns on every position (shares/BTC, vs BTC %)
- NEW: mNAV live calculation
- Storage: Railway Environment Variables
- Quotes: Yahoo Finance server-side
- AI: Claude Sonnet via Anthropic API
"""
import os, json, asyncio, time, threading
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def get_anthropic_key(): return os.environ.get("ANTHROPIC_API_KEY","")
def get_margin():
    try: return float(os.environ.get("PORTFOLIO_MARGIN","120000"))
    except: return 120000.0

FUND = {
    "MSTR": {"pe":None,"ps":22,"peg":None,"dilution":"~32%/yr","growth":"N/A","sector":"Bitcoin Treasury","sats_per_share":219900},
    "AMZN": {"pe":38,"ps":3.5,"peg":1.8,"dilution":"~1.4%/yr","growth":"+11%","sector":"E-Commerce/Cloud","sats_per_share":0},
    "HIMS": {"pe":45,"ps":4.2,"peg":0.9,"dilution":"~2.7%/yr","growth":"+15%","sector":"Digital Health","sats_per_share":0},
    "LLY":  {"pe":52,"ps":14,"peg":1.4,"dilution":"~-1%/yr","growth":"+32%","sector":"Pharma/GLP-1","sats_per_share":0},
    "OSCR": {"pe":12,"ps":0.8,"peg":0.4,"dilution":"~4.6%/yr","growth":"+30%","sector":"Health Insurance","sats_per_share":0},
    "SOFI": {"pe":28,"ps":2.8,"peg":0.8,"dilution":"~13%/yr","growth":"+41%","sector":"Fintech","sats_per_share":0},
    "ZETA": {"pe":None,"ps":2.5,"peg":0.8,"dilution":"~3%/yr","growth":"+37%","sector":"AI Marketing Cloud","sats_per_share":0},
    "ASTS": {"pe":None,"ps":120,"peg":None,"dilution":"~8%/yr (convert risk)","growth":"N/A — pre-revenue scale","sector":"Satellite/Defense","sats_per_share":0},
    "PLTR": {"pe":145,"ps":40,"peg":None,"dilution":"~2%/yr","growth":"+71%","sector":"Defense/Data Analytics","sats_per_share":0},
    "ELMT": {"pe":None,"ps":2.2,"peg":None,"dilution":"~2%/yr","growth":"N/A","sector":"Space Materials","sats_per_share":0},
}

DEFAULT_PRICES = {
    "MSTR":{"price":120.44,"change_pct":0.0}, "AMZN":{"price":262.06,"change_pct":0.0},
    "HIMS":{"price":28.78,"change_pct":0.0},  "LLY": {"price":1125.00,"change_pct":0.0},
    "OSCR":{"price":22.00,"change_pct":0.0},  "SOFI":{"price":16.20,"change_pct":0.0},
    "ZETA":{"price":18.00,"change_pct":0.0},  "BTC": {"price":61000.0,"change_pct":0.0},
    "ASTS":{"price":66.00,"change_pct":0.0},
}

PORTFOLIO_CONTEXT = """
INVESTOR: Ricardo Faraudo, founding partner DENFAB Law, Panama City.
STRATEGY: Two-bucket system — (1) On-chain Bitcoin (cold storage + Binance trading) targeting 10 BTC by 2028, (2) Stock portfolio for compounding wealth.
CRITICAL — YOU HAVE WEB SEARCH. USE IT.
This context file is written by hand and goes stale. Prices, earnings results, FDA
outcomes and news below may be out of date. Before making any claim about a
catalyst, earnings result, regulatory decision or recent price action, SEARCH THE
WEB and use what you find over what is written here.
- A "Today's date" line appears above. Reason relative to that date only.
- Never describe an event as "upcoming" without first confirming it hasn't happened.
- If a date below is in the past, search for the actual outcome and report that.
- Live prices in the POSITIONS block are real-time; trust those over any price text.
MSTR STRATEGY: Use mNAV cycles — buy MSTR when mNAV below 1x/1.3x, sell when mNAV above 2x, convert profits to BTC. Gradually exiting MSTR from brokerages; accumulating tokenized MSTR on Binance (no leverage) specifically to convert to cold-storage BTC when mNAV re-rates in the next bull cycle (~2028 target).
PORTFOLIO ARCHITECTURE: Compounders (AMZN, LLY) + High-beta convictions (HIMS) + small speculative satellite/defense position (ASTS) — no MSTR in BG account going forward.
LLY: Retatrutide/TRIUMPH-1 confirmed. Multi-indication platform drug — obesity, T2D, osteoarthritis, sleep apnea, cardiovascular, oncology (Retevmo/Jaypirca EU approval), Medicare GLP-1 Bridge Program (from July 2026). THIS IS AN UNCAPPED CORE ANCHOR POSITION — Ricardo explicitly wants as much LLY as possible with NO allocation ceiling, even above 30% of portfolio. NEVER recommend trimming or selling LLY for portfolio-balance reasons. Add aggressively below $1,100; add on any weakness regardless of current %.
HIMS: Healthcare subscription platform (Netflix of health). Eucalyptus international acquisition closed. Harvard peptide CMO hired. California peptide manufacturing facility built. Core thesis is GLP-1 distribution (Wegovy pill/pen, Zepbound, Foundayo), labs, hormones and dermatology — NOT peptides. Peptide compounding is upside optionality only; even after the favourable PCAC vote, FDA rulemaking runs 8-12+ months, so peptide revenue is a 2027+ story with zero contribution to current financials. Novo Nordisk has publicly called HIMS a valued telehealth partner. See CATALYSTS for dated events — search the web to confirm outcomes. Never add above $30-32 (avoid chasing breakouts); add meaningfully on pullbacks to $28-32, aggressively below $24-28; never sell unless $40 becomes confirmed resistance with rejection — even then only trim a small tactical portion, and proceeds stay within the Bitcoin/margin ecosystem (never redirected to fund OSCR/ZETA/other new positions).
AMZN: Core compounder. Margin anchor in MMG, building toward 300 shares. Leave alone; add in value zones (~$230 or lower) or when funded by MSTR brokerage bounces.
ASTS: Small (~100 share) speculative long-duration position in AST SpaceMobile — satellite direct-to-device + emerging government/defense (SHIELD/Golden Dome) optionality. Deliberately small sizing given pre-revenue-scale valuation, convertible-note dilution risk, and Aug earnings binary risk. 1-3 year thesis tied to satellite deployment; not a conviction-tier position — do not recommend adding significantly without fresh, explicitly-designated capital.
BTC GOAL: 10 BTC in cold storage by 2028. Using MSTR mNAV arbitrage (in Binance, no leverage) to accumulate more BTC over time, especially during bear-market/low-mNAV periods — deliberately not chasing MSTR strength in bullish periods.
ACCOUNTS: MMG Bank (~$80K margin) + Banco General (~$40K margin). BG = non-Bitcoin stocks only going forward (no MSTR in BG).
WATCHLIST PRIORITIES (fresh capital only, never funded by trimming existing conviction positions): OSCR — target ~$23 (re-entry after prior $21 exit; thesis strengthened since — MLR improvement, Barclays upgrade); ZETA — target $15-17 or pre-earnings weakness (real cash flow, ~30-40% growth, OpenAI ad-revenue optionality not yet in most models); PLTR — only on a real pullback toward $105-115, not at stretched valuations; ELMT — molybdenum/space materials, target ~$42.
CAPITAL PRIORITY WHEN FRESH MONEY IS AVAILABLE (in order): LLY (uncapped, always first priority especially below $1,100) > HIMS on genuine pullback to $28-32 or lower > AMZN in value zones > MSTR/Binance-BTC-conversion opportunistically at low mNAV > OSCR/ZETA/other watchlist names only with capital explicitly not needed elsewhere (e.g., after the household renovation budget is funded).
"""

# ── CATALYST CALENDAR ─────────────────────────────────────────────────────────
# Dated events. The app works out past vs upcoming itself, so nothing goes stale.
# Add a new line whenever a date is known. Format: (ticker, ISO date, description)
CATALYSTS = [
    ("HIMS","2026-07-24","FDA PCAC peptide vote (503A Bulks List)"),
    ("HIMS","2026-08-10","Q2 2026 earnings — first full Eucalyptus quarter, churn test"),
    ("LLY", "2026-08-05","Q2 2026 earnings"),
    ("MSTR","2026-07-30","Q2 2026 earnings"),
    ("MSTR","2026-11-04","Q3 2026 earnings"),
    ("AMZN","2026-07-30","Q2 2026 earnings — AWS growth + capex guide"),
    ("OSCR","2026-08-05","Q2 2026 earnings"),
    ("ZETA","2026-08-05","Q2 2026 earnings — OpenAI ad revenue contribution"),
    ("ASTS","2026-08-10","Q2 2026 earnings"),
]

def catalyst_lines(days_ahead=120):
    """Returns human-readable catalyst status computed against today's real date."""
    today=datetime.now().date(); out=[]
    for tk,d,desc in sorted(CATALYSTS,key=lambda x:x[1]):
        try: dt=datetime.strptime(d,"%Y-%m-%d").date()
        except: continue
        delta=(dt-today).days
        if delta<0:
            if delta>-180:
                out.append(f"{tk} — {desc}: HAPPENED {abs(delta)}d ago ({d}). SEARCH for the actual outcome; do NOT call this upcoming.")
        elif delta<=days_ahead:
            out.append(f"{tk} — {desc}: upcoming in {delta}d ({d})")
    return "\n".join(out) if out else "No dated catalysts in window."

_store = {"holdings": None, "watchlist": None}

def get_holdings_data():
    raw = os.environ.get("PORTFOLIO_HOLDINGS")
    if raw:
        try: return json.loads(raw)
        except: pass
    return [
        {"id":1,"ticker":"MSTR","shares":525,"avg_cost":250.00,"type":"high-beta","account":"MMG","notes":"Bitcoin treasury. Gradually exiting. Buy low mNAV, sell high mNAV, convert to BTC."},
        {"id":2,"ticker":"AMZN","shares":225,"avg_cost":218.00,"type":"compounder","account":"MMG","notes":"Core compounder. Margin anchor. Leave alone."},
        {"id":3,"ticker":"HIMS","shares":2850,"avg_cost":30.41,"type":"high-beta","account":"MMG","notes":"Healthcare platform. Building toward 5,000 shares on pullbacks only."},
        {"id":5,"ticker":"HIMS","shares":1000,"avg_cost":30.44,"type":"high-beta","account":"BG","notes":"Healthcare platform position in BG."},
        {"id":6,"ticker":"LLY","shares":65,"avg_cost":1039.96,"type":"compounder","account":"BG","notes":"Retatrutide thesis. Uncapped core anchor — no allocation ceiling. Add aggressively below $1,100. Target 100 shares."},
        {"id":7,"ticker":"ASTS","shares":100,"avg_cost":66.00,"type":"speculative","account":"MMG","notes":"Small long-duration satellite/defense bet. Not conviction-tier — deliberately small, no aggressive adds."},
    ]

def get_watchlist_data():
    raw = os.environ.get("PORTFOLIO_WATCHLIST")
    if raw:
        try: return json.loads(raw)
        except: pass
    return [
        {"id":1,"ticker":"OSCR","target_price":23.00,"notes":"Health insurance platform. Re-entry after prior $21 exit — thesis strengthened since (MLR improvement, Barclays upgrade). Complete healthcare trifecta with LLY/HIMS. Fresh capital only."},
        {"id":3,"ticker":"ZETA","target_price":16.00,"notes":"AI Marketing Cloud. Target $15-17 or pre-earnings weakness. Real FCF, ~30-40% growth, OpenAI ad-revenue deal not yet in most models. Fresh capital only."},
        {"id":4,"ticker":"ELMT","target_price":42.00,"notes":"Molybdenum manufacturer. Sole US producer. Space infrastructure materials."},
        {"id":5,"ticker":"PLTR","target_price":110.00,"notes":"Elite fundamentals but priced for perfection. Only add on a real pullback toward $105-115, not while extended."},
    ]

def holdings():
    if _store["holdings"] is None: _store["holdings"] = get_holdings_data()
    return _store["holdings"]

def watchlist():
    if _store["watchlist"] is None: _store["watchlist"] = get_watchlist_data()
    return _store["watchlist"]

_quote_cache = {}
_cache_time = {}
CACHE_TTL = 60   # 60s — matches frontend auto-refresh cadence

# ── QUOTE PROVIDER CHAIN ──────────────────────────────────────────────────────
# Providers are tried in order until one returns a usable quote. Each is fully
# isolated: a failure in one never affects the others, and the winning provider
# is recorded on the quote so the UI can show where the number came from.
#
#   1. Finnhub    — real documented API. Set FINNHUB_API_KEY in Railway to enable.
#                   Free tier = 60 calls/min, ample for this portfolio.
#   2. Yahoo      — undocumented but reliable; no key required.
#   3. Stooq      — public CSV endpoint, no key, works when the others are blocked.
#
# Adding a provider = write one async fn returning {price, prev_close} and add
# it to PROVIDERS. Nothing else needs to change.

def _norm(ticker, style):
    """Map internal ticker to each provider's symbol convention."""
    if ticker == "BTC":
        return {"yahoo":"BTC-USD","finnhub":"BINANCE:BTCUSDT","stooq":"btcusd"}[style]
    return {"yahoo":ticker,"finnhub":ticker,"stooq":f"{ticker.lower()}.us"}[style]

async def _p_finnhub(ticker):
    key = os.environ.get("FINNHUB_API_KEY","").strip()
    if not key: return None
    sym = _norm(ticker,"finnhub")
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get("https://finnhub.io/api/v1/quote",
                        params={"symbol":sym,"token":key})
        if r.status_code != 200: return None
        d = r.json()
        # Finnhub: c=current, pc=previous close. Zeroes mean "no data".
        if d.get("c") and d.get("pc"):
            return {"price":float(d["c"]),"prev_close":float(d["pc"])}
    return None

async def _p_yahoo(ticker):
    sym  = _norm(ticker,"yahoo")
    now  = int(time.time())
    data = await fetch_yahoo(sym, now-86400*10, now)   # 10d window spans weekends
    if not data: return None
    res  = data["chart"]["result"][0]
    meta = res["meta"]
    price = meta.get("regularMarketPrice") or meta.get("currentPrice")
    # NOT chartPreviousClose — that's the close before the window starts, which
    # is what produced multi-day values in the "day change" column.
    prev  = meta.get("regularMarketPreviousClose") or meta.get("previousClose")
    if not prev:
        try:
            closes=[c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            if len(closes)>=2: prev=closes[-2]
        except: pass
    if price and prev:
        return {"price":float(price),"prev_close":float(prev)}
    return None

async def _p_stooq(ticker):
    sym = _norm(ticker,"stooq")
    async with httpx.AsyncClient(timeout=10.0,follow_redirects=True) as c:
        r = await c.get(f"https://stooq.com/q/l/",
                        params={"s":sym,"f":"sd2t2ohlcv","h":"","e":"csv"})
        if r.status_code != 200: return None
        lines=[l for l in r.text.strip().split("\n") if l]
        if len(lines) < 2: return None
        cols=lines[0].split(","); vals=lines[1].split(",")
        row=dict(zip(cols,vals))
        try:
            close=float(row.get("Close","")); openp=float(row.get("Open",""))
        except (ValueError,TypeError):
            return None
        if close<=0: return None
        # Stooq's free endpoint has no prior close, so intraday open is the best
        # available proxy. Flagged as approximate via the provider name.
        return {"price":close,"prev_close":openp if openp>0 else close}

PROVIDERS = [("finnhub",_p_finnhub),("yahoo",_p_yahoo),("stooq",_p_stooq)]

async def fetch_yahoo(ticker, period1, period2):
    for base in ["https://query1.finance.yahoo.com","https://query2.finance.yahoo.com"]:
        try:
            async with httpx.AsyncClient(headers=YAHOO_HEADERS,timeout=12.0,follow_redirects=True) as c:
                r = await c.get(f"{base}/v8/finance/chart/{ticker}",params={"interval":"1d","period1":period1,"period2":period2})
                if r.status_code==200:
                    d=r.json()
                    if d.get("chart",{}).get("result"): return d
        except: continue
    return None

async def get_quote(ticker):
    now=time.time()
    if ticker in _quote_cache and now-_cache_time.get(ticker,0)<CACHE_TTL:
        return {**_quote_cache[ticker],"age_sec":int(now-_cache_time.get(ticker,0))}

    tried=[]
    for name, fn in PROVIDERS:
        try:
            q = await fn(ticker)
        except Exception as e:
            tried.append(f"{name}:err"); continue
        if not q:
            tried.append(f"{name}:none"); continue
        price = float(q["price"]); prev = float(q.get("prev_close") or 0)
        chg = round((price-prev)/prev*100,2) if prev else 0.0
        result={"price":round(price,2),"change_pct":chg,"source":name,
                "prev_close":round(prev,2) if prev else None,
                "tried":tried,
                "fetched_at":datetime.now().isoformat(timespec="seconds")}
        _quote_cache[ticker]=result; _cache_time[ticker]=now
        return {**result,"age_sec":0}

    # Every provider failed.
    d=DEFAULT_PRICES.get(ticker)
    if d is None:
        return {"price":0.0,"change_pct":0.0,"source":"unknown","stale":True,
                "tried":tried,"fetched_at":None}
    return {**d,"source":"default","stale":True,"tried":tried,"fetched_at":None}

async def get_all_quotes(tickers):
    """Fetch all quotes concurrently. A single bad ticker must not poison the
    whole response — each failure degrades to its own fallback and is flagged."""
    tickers=[t for t in tickers if t and isinstance(t,str)]
    if not tickers: return {}
    results=await asyncio.gather(*[get_quote(t) for t in tickers],return_exceptions=True)
    out={}
    for i,r in enumerate(results):
        tk=tickers[i]
        if isinstance(r,Exception):
            d=DEFAULT_PRICES.get(tk,{"price":0.0,"change_pct":0.0})
            out[tk]={**d,"source":"error","stale":True,"error":str(r)[:120]}
        else:
            out[tk]=r
    return out

async def get_historical(ticker):
    now=datetime.now()
    from datetime import timedelta
    jan1=datetime(now.year,1,1); m1st=datetime(now.year,now.month,1); m3ago=now-timedelta(days=90)
    data=await fetch_yahoo(ticker,int(jan1.timestamp())-86400*5,int(time.time()))
    if not data: return {"ytd":None,"mtd":None,"m3":None}
    try:
        result=data["chart"]["result"][0]
        ts=result.get("timestamp",[]); closes=result["indicators"]["quote"][0].get("close",[])
        pm={}
        for t,p in zip(ts,closes):
            if p: pm[datetime.fromtimestamp(t).date()]=p
        def nearest(dt):
            for off in range(6):
                from datetime import timedelta as td
                p=pm.get((dt+td(days=off)).date()) or pm.get((dt-td(days=off)).date())
                if p: return p
            return None
        q=await get_quote(ticker); cur=q["price"]
        def pct(b): return round((cur-b)/b*100,2) if b and b>0 else None
        return {"ytd":pct(nearest(jan1)),"mtd":pct(nearest(m1st)),"m3":pct(nearest(m3ago))}
    except: return {"ytd":None,"mtd":None,"m3":None}

# ── STRATEGY RULES ────────────────────────────────────────────────────────────
# Edit these numbers to change behaviour. Nothing else needs touching.
# buy_below / add_below : price levels that trigger accumulation signals
# no_chase_above        : never add above this price
# trim_above            : only consider trimming above this price
# ladder                : MSTR-style staged exit rungs
RULES = {
    "LLY":  {"label":"Uncapped core anchor","buy_below":1100,"add_below":1160,"no_cap":True,"never_trim":True},
    "HIMS": {"label":"High-conviction platform","buy_below":28,"add_below":32,"no_chase_above":32,"trim_above":40},
    "AMZN": {"label":"Margin anchor / compounder","buy_below":230,"add_below":245,"target_shares":300},
    "MSTR": {"label":"mNAV cycle — exit to BTC","ladder":[135,150,170],"accumulate_below_mnav":1.0},
    "ASTS": {"label":"Small speculative satellite bet","max_position":True},
    "OSCR": {"label":"Watchlist — healthcare trifecta","buy_below":23},
    "ZETA": {"label":"Watchlist — AI marketing infra","buy_below":17},
    "PLTR": {"label":"Watchlist — only on real pullback","buy_below":115},
}

def compute_signal(ticker,price,avg_cost,change_pct,mnav=None):
    """Signals derive from LIVE price vs strategy levels. Rules adjust the score,
    they never replace it — so output changes as the market changes."""
    f=FUND.get(ticker,{}); r=RULES.get(ticker,{})
    pnl=((price-avg_cost)/avg_cost*100) if avg_cost else 0
    score,reasons=0,[]

    # ── Live price vs your own trigger levels (the primary driver) ──
    if r.get("buy_below") and price<r["buy_below"]:
        score+=3; reasons.append(f"${price:,.2f} is BELOW your ${r['buy_below']:,.0f} buy trigger — accumulate")
    elif r.get("add_below") and price<r["add_below"]:
        score+=1; reasons.append(f"${price:,.2f} approaching ${r.get('buy_below',r['add_below']):,.0f} trigger")
    if r.get("no_chase_above") and price>r["no_chase_above"]:
        score-=1; reasons.append(f"Above ${r['no_chase_above']:,.0f} — do not chase, wait for pullback")
    if r.get("trim_above") and price>r["trim_above"]:
        score-=2; reasons.append(f"Above ${r['trim_above']:,.0f} — trim zone if it confirms as resistance")

    # ── MSTR ladder, evaluated against live price ──
    if r.get("ladder"):
        nxt=next((x for x in r["ladder"] if price<x),None)
        hit=[x for x in r["ladder"] if price>=x]
        if hit: score-=2; reasons.append(f"Ladder rung ${hit[-1]} REACHED — sell tranche, convert to BTC")
        elif nxt: reasons.append(f"${price:,.2f} — next exit rung ${nxt} ({(nxt-price)/price*100:+.1f}% away)")
        if mnav is not None:
            if mnav<r.get("accumulate_below_mnav",1.0):
                score+=1; reasons.append(f"mNAV {mnav:.2f}x — BTC at a {(1-mnav)*100:.0f}% discount")
            elif mnav>2: score-=2; reasons.append(f"mNAV {mnav:.2f}x — premium, sell zone")

    # ── Valuation & momentum ──
    if f.get("peg") and f["peg"]<1.0: score+=1; reasons.append("PEG < 1 — undervalued growth")
    if f.get("ps") and f["ps"]<3: score+=1; reasons.append("P/S attractive")
    if change_pct<=-5: score+=2; reasons.append(f"Down {change_pct:.1f}% today — sharp dip")
    elif change_pct<=-3: score+=1; reasons.append(f"Down {change_pct:.1f}% today — dip opportunity")
    elif change_pct>=5: reasons.append(f"Up {change_pct:.1f}% today — strength, don't chase")
    if avg_cost:
        if pnl<-20: score+=1; reasons.append(f"{pnl:.0f}% below cost — accumulation zone")
        elif pnl>30 and not r.get("never_trim"): score-=1; reasons.append(f"{pnl:+.0f}% gain — review sizing")

    # ── Standing convictions (adjust, never overwrite) ──
    if r.get("no_cap"): score=max(score,1); reasons.insert(0,"Uncapped core anchor — no allocation ceiling")
    if r.get("never_trim") and score<0: score=0
    if r.get("max_position") and score>0:
        score=0; reasons.append("Speculative sizing cap — no adds without fresh capital")
    if r.get("label"): reasons.append(f"Rule: {r['label']}")

    sig="ADD" if score>=3 else "ACCUMULATE" if score>=1 else "TRIM" if score<=-2 else "HOLD"
    return {"signal":sig,"score":score,"reasons":reasons}

async def build_snapshot():
    hs=holdings(); wl=watchlist()
    tickers=list(set([h["ticker"] for h in hs]+["BTC"]))
    quotes=await get_all_quotes(tickers)
    margin=get_margin()
    total_value=sum(quotes.get(h["ticker"],{}).get("price",0)*h["shares"] for h in hs)
    total_cost=sum(h["avg_cost"]*h["shares"] for h in hs)
    positions=[]
    for h in hs:
        q=quotes.get(h["ticker"],{})
        price=q.get("price") or h["avg_cost"]; value=price*h["shares"]
        pl=(price-h["avg_cost"])*h["shares"]; plp=((price-h["avg_cost"])/h["avg_cost"]*100) if h["avg_cost"] else 0
        pp=(value/total_value*100) if total_value else 0
        btc_price=quotes.get("BTC",{}).get("price",61000)
        sats=FUND.get(h["ticker"],{}).get("sats_per_share",0)
        mnav=round(price/(sats/100000000*btc_price),3) if sats and btc_price else None
        sig=compute_signal(h["ticker"],price,h["avg_cost"],q.get("change_pct",0),mnav=mnav)
        shares_per_btc_now=round(btc_price/price,2) if price else 0
        shares_per_btc_buy=round(btc_price/h["avg_cost"],2) if h["avg_cost"] else 0
        vs_btc_pct=round((shares_per_btc_buy-shares_per_btc_now)/shares_per_btc_buy*100,2) if shares_per_btc_buy else 0
        pos_value_btc=round(value/btc_price,4) if btc_price else 0
        positions.append({**h,"price":price,"change_pct":q.get("change_pct",0),"value":value,
                          "quote_source":q.get("source","default"),"quote_age":q.get("age_sec"),
                          "pl":pl,"pl_pct":plp,"port_pct":pp,"signal":sig,
                          "fundamentals":FUND.get(h["ticker"],{}),"mnav":mnav,
                          "shares_per_btc_now":shares_per_btc_now,"shares_per_btc_buy":shares_per_btc_buy,
                          "vs_btc_pct":vs_btc_pct,"pos_value_btc":pos_value_btc})
    total_pl=total_value-total_cost
    btc_price=quotes.get("BTC",{}).get("price",61000)
    return {"total_value":total_value,"total_cost":total_cost,"total_pl":total_pl,
            "total_pl_pct":(total_pl/total_cost*100) if total_cost else 0,
            "net_equity":total_value-margin,"lvr":(margin/total_value*100) if total_value else 0,
            "margin":margin,"positions":positions,"btc_price":btc_price,
            "quotes":quotes}

WEB_SEARCH_TOOL=[{"type":"web_search_20250305","name":"web_search","max_uses":5}]

async def call_claude(prompt,max_tokens=1024,web=True):
    """web=True lets the model look up current news/prices instead of relying on
    its training data — this is what stops it describing past events as upcoming."""
    key=get_anthropic_key()
    if not key: raise ValueError("ANTHROPIC_API_KEY not set in Railway Variables")
    payload={"model":"claude-sonnet-4-6","max_tokens":max_tokens,
             "messages":[{"role":"user","content":prompt}]}
    if web: payload["tools"]=WEB_SEARCH_TOOL
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                r=await c.post(ANTHROPIC_URL,headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"},json=payload)
                if r.status_code in (429,500,502,503,529) and attempt<2:
                    await asyncio.sleep((attempt+1)*5); continue
                r.raise_for_status()
                # Response may contain text, server_tool_use and web_search_tool_result
                # blocks — take only the text the model actually wrote.
                return "".join(b.get("text","") for b in r.json().get("content",[]) if b.get("type")=="text")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429,500,502,503,529) and attempt<2:
                await asyncio.sleep((attempt+1)*5); continue
            raise
        except httpx.TimeoutException:
            if attempt<2: await asyncio.sleep(5); continue
            raise ValueError("Request timed out after 3 attempts — try again shortly.")
    raise ValueError("Anthropic API busy (529). Try again in ~30 seconds.")

async def ai_analyze_position(ticker):
    snap=await build_snapshot()
    pos=next((p for p in snap["positions"] if p["ticker"]==ticker),None)
    if not pos: return f"{ticker} not found."
    hist=await get_historical(ticker); f=pos["fundamentals"]
    def hs(v): return f"{v:+.2f}%" if v is not None else "N/A"
    prompt=f"""Portfolio advisor for Ricardo Faraudo, Panama City. Today's date: {datetime.now().strftime('%A, %B %d, %Y')}.
Portfolio: ${snap['total_value']:,.0f} | ${snap['net_equity']:,.0f} net equity | LVR {snap['lvr']:.1f}% | BTC ${snap['btc_price']:,.0f}
{PORTFOLIO_CONTEXT}\n\nDATED CATALYST STATUS (computed from today's real date):\n{catalyst_lines()}
ANALYZING: {ticker} ({pos['type']}) — Account: {pos.get('account','—')}
Shares: {pos['shares']} | Avg: ${pos['avg_cost']:.2f} | Price: ${pos['price']:.2f}
Value: ${pos['value']:,.0f} | P&L: ${pos['pl']:,.0f} ({pos['pl_pct']:.1f}%) | Weight: {pos['port_pct']:.1f}%
Today: {pos['change_pct']:+.2f}% | MTD: {hs(hist.get('mtd'))} | 3M: {hs(hist.get('m3'))} | YTD: {hs(hist.get('ytd'))}
VS BTC: {pos['vs_btc_pct']:+.2f}% | Position value in BTC: ₿{pos['pos_value_btc']:.4f}
{f'mNAV: {pos["mnav"]}x' if pos.get("mnav") else ''}
P/E: {f.get('pe','N/A')} | P/S: {f.get('ps','N/A')} | PEG: {f.get('peg','N/A')} | Dilution: {f.get('dilution','N/A')}
Signal: {pos['signal']['signal']} | Notes: {pos['notes']}
Provide: (1) assessment (2) risks/catalysts next 6 months (3) recommendation with sizing (4) one metric to watch. Max 300 words."""
    return await call_claude(prompt,1200)

async def ai_analyze_portfolio():
    snap=await build_snapshot()
    hist_list=await asyncio.gather(*[get_historical(p["ticker"]) for p in snap["positions"]],return_exceptions=True)
    hist_map={snap["positions"][i]["ticker"]:h for i,h in enumerate(hist_list) if not isinstance(h,Exception)}
    def ys(t): v=hist_map.get(t,{}).get("ytd"); return f"{v:+.1f}%" if v is not None else "N/A"
    pos_lines="\n".join([f"{p['ticker']} ({p.get('account','')}) {p['port_pct']:.1f}% | P&L {p['pl_pct']:+.1f}% | YTD {ys(p['ticker'])} | vs BTC {p['vs_btc_pct']:+.1f}% | {p['signal']['signal']}" for p in snap["positions"]])
    prompt=f"""Portfolio advisor for Ricardo Faraudo, Panama City. Today's date: {datetime.now().strftime('%A, %B %d, %Y')}. BTC price: ${snap['btc_price']:,.0f}
Total: ${snap['total_value']:,.0f} | Net equity: ${snap['net_equity']:,.0f} | LVR: {snap['lvr']:.1f}%
POSITIONS:\n{pos_lines}\n{PORTFOLIO_CONTEXT}\n\nDATED CATALYST STATUS (computed from today's real date):\n{catalyst_lines()}
6-month strategy: (1) biggest risk (2) biggest opportunity (3) capital priority (4) key catalysts (5) one action this week. Max 400 words."""
    return await call_claude(prompt,1500)

async def ai_daily_brief():
    snap=await build_snapshot()
    hist_list=await asyncio.gather(*[get_historical(p["ticker"]) for p in snap["positions"]],return_exceptions=True)
    hist_map={snap["positions"][i]["ticker"]:h for i,h in enumerate(hist_list) if not isinstance(h,Exception)}
    def ys(t): v=hist_map.get(t,{}).get("ytd"); return f"{v:+.1f}%" if v is not None else "N/A"
    def wr(f):
        s,w=0,0
        for p in snap["positions"]:
            v=hist_map.get(p["ticker"],{}).get(f)
            if v is not None:
                wt=p["value"]/snap["total_value"] if snap["total_value"] else 0
                s+=v*wt; w+=wt
        return round(s,2) if w>0 else None
    wl=watchlist(); wl_quotes=await get_all_quotes([w["ticker"] for w in wl]) if wl else {}
    pos_lines="\n".join([f"{p['ticker']}: ${p['price']:.2f} ({p['change_pct']:+.2f}% today, YTD {ys(p['ticker'])}, vs BTC {p['vs_btc_pct']:+.1f}%) — {p['signal']['signal']}" for p in snap["positions"]])
    wl_lines="\n".join([f"{w['ticker']}: ${wl_quotes.get(w['ticker'],{}).get('price',0):.2f}, target ${w['target_price'] or 'N/A'}" for w in wl])
    ytd=wr("ytd"); mtd=wr("mtd"); m3=wr("m3")
    lly_pct=next((p["port_pct"] for p in snap["positions"] if p["ticker"]=="LLY"),0)
    mstr_q=snap["quotes"].get("MSTR",{}); btc_p=snap["btc_price"]
    mnav=round(mstr_q.get("price",120)/(219900/100000000*btc_p),3) if btc_p else 0
    prompt=f"""Ricardo's portfolio intelligence assistant. Today: {datetime.now().strftime('%A, %B %d, %Y')}. BTC: ${btc_p:,.0f} | MSTR mNAV: {mnav:.2f}x
Portfolio: ${snap['total_value']:,.0f} | LVR {snap['lvr']:.1f}% | MTD: {f"{mtd:+.2f}%" if mtd else "—"} | YTD: {f"{ytd:+.2f}%" if ytd else "—"}
POSITIONS:\n{pos_lines}\nWATCHLIST:\n{wl_lines}\n{PORTFOLIO_CONTEXT}\n\nDATED CATALYST STATUS (computed from today's real date):\n{catalyst_lines()}
Morning brief:
1. MARKET PULSE — one sentence
2. PORTFOLIO TODAY — what matters
3. BTC & MSTR — mNAV {mnav:.2f}x, accumulation status
4. CATALYST WATCH — next 30 days
5. LLY STATUS — at {lly_pct:.1f}% of portfolio (uncapped core anchor, no target ceiling — do not suggest trimming for balance reasons)
6. TODAY'S FOCUS — one specific action or watch
Direct analyst tone. Max 400 words."""
    return await call_claude(prompt,1500)

async def ai_chat(message,history):
    snap=await build_snapshot()
    pos_summary="\n".join([f"{p['ticker']} ({p.get('account','')}): ${p['price']:.2f}, {p['port_pct']:.1f}% portfolio, P&L {p['pl_pct']:+.1f}%, vs BTC {p['vs_btc_pct']:+.1f}%, signal: {p['signal']['signal']}" for p in snap["positions"]])
    btc_p=snap["btc_price"]
    mstr_q=snap["quotes"].get("MSTR",{}); mnav=round(mstr_q.get("price",120)/(219900/100000000*btc_p),3) if btc_p else 0
    system=f"""You are Ricardo's personal portfolio intelligence assistant. Full portfolio knowledge. Today's date: {datetime.now().strftime('%A, %B %d, %Y')}.
Portfolio: ${snap['total_value']:,.0f} | LVR {snap['lvr']:.1f}% | BTC ${btc_p:,.0f} | MSTR mNAV {mnav:.2f}x
POSITIONS:\n{pos_summary}\n{PORTFOLIO_CONTEXT}\n\nDATED CATALYST STATUS (computed from today's real date):\n{catalyst_lines()}
Answer questions about portfolio, positions, BTC accumulation strategy, market conditions. Be direct and specific. Under 200 words unless detailed analysis needed."""
    messages=[]
    for h in history[-10:]:
        messages.append({"role":"user","content":h["user"]})
        messages.append({"role":"assistant","content":h["assistant"]})
    messages.append({"role":"user","content":message})
    key=get_anthropic_key()
    if not key: raise ValueError("ANTHROPIC_API_KEY not set")
    payload={"model":"claude-sonnet-4-6","max_tokens":1500,"system":system,
             "messages":messages,"tools":WEB_SEARCH_TOOL}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as c:
                r=await c.post(ANTHROPIC_URL,headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"},json=payload)
                if r.status_code in (429,500,502,503,529) and attempt<2:
                    await asyncio.sleep((attempt+1)*5); continue
                r.raise_for_status()
                return "".join(b.get("text","") for b in r.json().get("content",[]) if b.get("type")=="text")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429,500,502,503,529) and attempt<2:
                await asyncio.sleep((attempt+1)*5); continue
            raise
        except httpx.TimeoutException:
            if attempt<2: await asyncio.sleep(5); continue
            raise ValueError("Request timed out — try again shortly.")
    raise ValueError("API busy (529). Try again in ~30 seconds.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    holdings(); watchlist(); yield

app = FastAPI(title="Portfolio Intelligence v4",lifespan=lifespan)

class HoldingIn(BaseModel):
    ticker: str; shares: float; avg_cost: float; type: str="position"; account: str="MMG"; notes: str=""
class WatchlistIn(BaseModel):
    ticker: str; target_price: Optional[float]=None; notes: str=""
class AnalyzeRequest(BaseModel):
    ticker: str
class ChatRequest(BaseModel):
    message: str; history: list=[]
class UpdateHolding(BaseModel):
    shares: float; avg_cost: float; notes: str=""; account: str="MMG"

@app.get("/api/quotes")
async def api_quotes(extra: str = ""):
    hs=holdings(); wl=watchlist()
    tickers=list(set([h["ticker"] for h in hs]+[w["ticker"] for w in wl]+["BTC"]))
    if extra:
        for t in extra.split(","):
            t = t.strip().upper()
            if t and t not in tickers:
                tickers.append(t)
    return await get_all_quotes(tickers)

@app.get("/api/historical")
async def api_historical():
    hs=holdings()
    tickers = list(set([h["ticker"] for h in hs])) + ["BTC-USD"]
    results=await asyncio.gather(*[get_historical(t) for t in tickers],return_exceptions=True)
    out = {}
    for i,t in enumerate(tickers):
        if not isinstance(results[i],Exception):
            key = "BTC" if t=="BTC-USD" else t
            out[key] = results[i]
    return out

@app.get("/api/snapshot")
async def api_snapshot():
    return await build_snapshot()

@app.get("/api/holdings")
async def api_get_holdings(): return holdings()

@app.post("/api/holdings")
async def api_add_holding(h: HoldingIn):
    hs=holdings(); new_id=max([x["id"] for x in hs],default=0)+1
    new_h={"id":new_id,"ticker":h.ticker.upper(),"shares":h.shares,"avg_cost":h.avg_cost,"type":h.type,"account":h.account,"notes":h.notes}
    hs.append(new_h); return new_h

@app.put("/api/holdings/{hid}")
async def api_update_holding(hid: int, h: UpdateHolding):
    hs=holdings()
    for item in hs:
        if item["id"]==hid:
            item["shares"]=h.shares; item["avg_cost"]=h.avg_cost; item["notes"]=h.notes; item["account"]=h.account
            return item
    return JSONResponse({"error":"Not found"},404)

@app.delete("/api/holdings/{hid}")
async def api_delete_holding(hid: int):
    cur=holdings(); remaining=[h for h in cur if h["id"]!=hid]
    if len(remaining)==len(cur):
        return JSONResponse({"error":f"Holding {hid} not found"},status_code=404)
    _store["holdings"]=remaining
    return {"ok":True,"deleted":hid}

@app.get("/api/watchlist")
async def api_get_watchlist(): return watchlist()

@app.post("/api/watchlist")
async def api_add_watchlist(w: WatchlistIn):
    wl=watchlist(); new_id=max([x["id"] for x in wl],default=0)+1
    new_w={"id":new_id,"ticker":w.ticker.upper(),"target_price":w.target_price,"notes":w.notes}
    wl.append(new_w); return new_w

@app.delete("/api/watchlist/{wid}")
async def api_delete_watchlist(wid: int):
    cur=watchlist(); remaining=[w for w in cur if w["id"]!=wid]
    if len(remaining)==len(cur):
        return JSONResponse({"error":f"Watchlist item {wid} not found"},status_code=404)
    _store["watchlist"]=remaining
    return {"ok":True,"deleted":wid}

@app.post("/api/analyze/position")
async def api_analyze_position(req: AnalyzeRequest):
    if not get_anthropic_key(): return JSONResponse({"error":"ANTHROPIC_API_KEY not set in Railway Variables tab."},400)
    try: return {"analysis":await ai_analyze_position(req.ticker),"ticker":req.ticker}
    except Exception as e: return JSONResponse({"error":str(e)},500)

@app.post("/api/analyze/portfolio")
async def api_analyze_portfolio():
    if not get_anthropic_key(): return JSONResponse({"error":"ANTHROPIC_API_KEY not set."},400)
    try: return {"analysis":await ai_analyze_portfolio()}
    except Exception as e: return JSONResponse({"error":str(e)},500)

@app.post("/api/brief")
async def api_brief():
    if not get_anthropic_key(): return JSONResponse({"error":"ANTHROPIC_API_KEY not set."},400)
    try: return {"brief":await ai_daily_brief()}
    except Exception as e: return JSONResponse({"error":str(e)},500)

@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    if not get_anthropic_key(): return JSONResponse({"error":"ANTHROPIC_API_KEY not set."},400)
    try: return {"response":await ai_chat(req.message,req.history)}
    except Exception as e: return JSONResponse({"error":str(e)},500)

@app.get("/api/fundamentals")
async def api_fundamentals():
    """Single source of truth for fundamentals + strategy rules.
    The frontend fetches this instead of keeping its own hardcoded copy,
    which previously drifted out of sync whenever only one side was updated."""
    return {"fundamentals":FUND,"rules":RULES}

@app.get("/api/status")
async def api_status():
    return {"api_key_set":bool(get_anthropic_key()),"holdings_count":len(holdings()),"watchlist_count":len(watchlist()),"margin":get_margin()}

# ─── FRONTEND ─────────────────────────────────────────────────────────────────
FRONTEND = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Portfolio Intelligence v4</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#080c10;--s1:#0d1318;--s2:#111820;--s3:#161e28;--b1:#1e2d3d;--b2:#243545;--ac:#00d4ff;--ac2:#0098cc;--gr:#00e676;--rd:#ff3d57;--yw:#ffd740;--pu:#b388ff;--btc:#f7931a;--tx:#e8f0f8;--t2:#8fa8c0;--t3:#4a6378;}
*{margin:0;padding:0;box-sizing:border-box;}
body{background:var(--bg);color:var(--tx);font-family:'DM Sans',sans-serif;min-height:100vh;}
body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}
.app{position:relative;z-index:1;}
header{display:flex;align-items:center;justify-content:space-between;padding:14px 28px;border-bottom:1px solid var(--b1);background:rgba(8,12,16,0.96);backdrop-filter:blur(20px);position:sticky;top:0;z-index:100;}
.logo{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:3px;color:var(--ac);text-shadow:0 0 20px rgba(0,212,255,0.4);}
.logo span{color:var(--t3);}
.hdr-r{display:flex;align-items:center;gap:10px;}
.lu{font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);}
.tabs{display:flex;padding:0 28px;border-bottom:1px solid var(--b1);background:var(--s1);overflow-x:auto;}
.tab{padding:13px 16px;font-size:12px;font-weight:500;color:var(--t3);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;}
.tab:hover{color:var(--t2);}
.tab.on{color:var(--ac);border-bottom-color:var(--ac);}
.tab.btctab.on{color:var(--btc);border-bottom-color:var(--btc);}
.bdg{background:var(--rd);color:#fff;border-radius:10px;padding:1px 6px;font-size:10px;font-family:'DM Mono',monospace;margin-left:4px;}
.main{padding:20px 28px;max-width:1800px;margin:0 auto;}
.tc{display:none;}.tc.on{display:block;}
.sgrid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:20px;}
.sc{background:var(--s1);border:1px solid var(--b1);border-radius:10px;padding:14px 16px;position:relative;overflow:hidden;}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--ac);opacity:0.35;}
.sc.gr::before{background:var(--gr);}.sc.rd::before{background:var(--rd);}.sc.yw::before{background:var(--yw);}.sc.btc::before{background:var(--btc);}
.cl{font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px;}
.cv{font-family:'DM Mono',monospace;font-size:18px;font-weight:500;}
.cs{font-family:'DM Mono',monospace;font-size:11px;margin-top:3px;}
.pos{color:var(--gr);}.neg{color:var(--rd);}.neu{color:var(--yw);}
.sh{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}
.st{font-family:'Bebas Neue',sans-serif;font-size:17px;letter-spacing:2px;color:var(--t2);}
.st span{color:var(--ac);margin-right:6px;}
.pn{background:var(--s1);border:1px solid var(--b1);border-radius:12px;overflow:hidden;}
.ph{padding:12px 18px;border-bottom:1px solid var(--b1);background:var(--s2);display:flex;align-items:center;justify-content:space-between;}
.pt{font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);letter-spacing:2px;text-transform:uppercase;}
.pb{padding:18px;}
.tw{background:var(--s1);border:1px solid var(--b1);border-radius:12px;overflow:hidden;margin-bottom:20px;}
.ts{overflow-x:auto;}
table{width:100%;border-collapse:collapse;}
th{padding:10px 12px;text-align:right;font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:1.5px;text-transform:uppercase;border-bottom:1px solid var(--b1);background:var(--s2);white-space:nowrap;}
th:first-child{text-align:left;}
td{padding:12px 12px;text-align:right;font-family:'DM Mono',monospace;font-size:11px;border-bottom:1px solid var(--b1);white-space:nowrap;}
td:first-child{text-align:left;}
tr:last-child td{border-bottom:none;}
tr:hover td{background:rgba(0,212,255,0.025);}
.tb{font-family:'Bebas Neue',sans-serif;font-size:14px;letter-spacing:1px;color:var(--ac);}
.tt{font-size:9px;color:var(--t3);margin-top:1px;}
.ta{font-size:9px;color:var(--yw);margin-top:1px;}
.sg{display:inline-flex;align-items:center;gap:3px;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600;white-space:nowrap;}
.sg-a{background:rgba(0,230,118,0.15);color:var(--gr);border:1px solid rgba(0,230,118,0.3);}
.sg-h{background:rgba(255,215,64,0.1);color:var(--yw);border:1px solid rgba(255,215,64,0.2);}
.sg-t{background:rgba(255,61,87,0.1);color:var(--rd);border:1px solid rgba(255,61,87,0.2);}
.sg-w{background:rgba(0,212,255,0.1);color:var(--ac);border:1px solid rgba(0,212,255,0.2);}
.sg-b{background:rgba(247,147,26,0.15);color:var(--btc);border:1px solid rgba(247,147,26,0.3);}
.sg-ac{background:rgba(0,230,118,0.08);color:#5de89b;border:1px solid rgba(0,230,118,0.2);}
.ai{display:flex;align-items:center;gap:10px;margin-bottom:12px;}
.at{font-family:'Bebas Neue',sans-serif;font-size:13px;color:var(--ac);min-width:48px;}
.ab{flex:1;height:5px;background:var(--s3);border-radius:3px;overflow:hidden;}
.af{height:100%;border-radius:3px;}
.ap{font-family:'DM Mono',monospace;font-size:11px;color:var(--t2);min-width:38px;text-align:right;}
.mr{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--b1);font-size:12px;}
.mr:last-child{border-bottom:none;}
.ml{color:var(--t3);font-family:'DM Mono',monospace;font-size:10px;}
.mv{font-family:'DM Mono',monospace;font-size:12px;}
.g2{display:grid;grid-template-columns:2fr 1fr;gap:18px;margin-bottom:20px;}
.g3{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:20px;}
.pg{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px;}
.pc{background:var(--s1);border:1px solid var(--b1);border-radius:10px;padding:18px;text-align:center;}
.pl{font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:1.5px;margin-bottom:8px;}
.pv{font-family:'DM Mono',monospace;font-size:26px;font-weight:500;}
.btn{background:var(--s3);border:1px solid var(--b2);color:var(--ac);padding:7px 14px;border-radius:6px;font-family:'DM Mono',monospace;font-size:11px;cursor:pointer;transition:all 0.2s;letter-spacing:1px;white-space:nowrap;}
.btn:hover{background:var(--ac);color:var(--bg);}
.btn:disabled{opacity:0.5;cursor:not-allowed;}
.btp{background:linear-gradient(135deg,var(--ac),var(--ac2));color:var(--bg);border:none;padding:10px 22px;border-radius:8px;font-family:'DM Mono',monospace;font-size:12px;font-weight:600;cursor:pointer;letter-spacing:1px;}
.btp:hover{opacity:0.9;}.btp:disabled{opacity:0.5;cursor:not-allowed;}
.btpu{background:linear-gradient(135deg,#7c3aed,#5b21b6);color:#fff;border:none;padding:10px 22px;border-radius:8px;font-family:'DM Mono',monospace;font-size:12px;font-weight:600;cursor:pointer;letter-spacing:1px;}
.btg{background:var(--gr);color:var(--bg);border:none;padding:5px 12px;border-radius:4px;font-family:'DM Mono',monospace;font-size:11px;font-weight:600;cursor:pointer;}
.bts{background:none;border:1px solid var(--b2);color:var(--t3);padding:4px 9px;border-radius:4px;font-size:10px;cursor:pointer;font-family:'DM Mono',monospace;}
.bts:hover{border-color:var(--ac);color:var(--ac);}
.btd{border-color:var(--rd)!important;color:var(--rd)!important;}
.inp{background:var(--s2);border:1px solid var(--b2);color:var(--tx);padding:7px 11px;border-radius:6px;font-family:'DM Mono',monospace;font-size:11px;outline:none;}
.inp:focus{border-color:var(--ac);}
.inp::placeholder{color:var(--t3);}
.ied{background:var(--s3);border:1px solid var(--ac);color:var(--tx);padding:4px 7px;border-radius:4px;font-family:'DM Mono',monospace;font-size:11px;outline:none;}
.fr{display:flex;gap:7px;flex-wrap:wrap;}
.aip{background:var(--s1);border:1px solid var(--b1);border-radius:12px;overflow:hidden;margin-bottom:20px;}
.aih{padding:14px 18px;border-bottom:1px solid var(--b1);background:linear-gradient(135deg,rgba(0,212,255,0.07),transparent);display:flex;align-items:center;justify-content:space-between;}
.ait{display:flex;align-items:center;gap:8px;font-family:'DM Mono',monospace;font-size:10px;color:var(--ac);letter-spacing:2px;text-transform:uppercase;}
.dot{width:7px;height:7px;background:var(--gr);border-radius:50%;box-shadow:0 0 7px var(--gr);animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1);}50%{opacity:0.6;transform:scale(0.8);}}
.aitx{font-size:13px;line-height:1.8;color:var(--t2);white-space:pre-wrap;}
.tpil{padding:5px 13px;border-radius:20px;font-family:'DM Mono',monospace;font-size:11px;cursor:pointer;border:1px solid var(--b2);color:var(--t2);background:var(--s2);transition:all 0.2s;}
.tpil.on{background:var(--ac);color:var(--bg);border-color:var(--ac);}
.ld{display:flex;align-items:center;gap:8px;color:var(--t3);font-family:'DM Mono',monospace;font-size:11px;padding:18px 0;}
.ld span{animation:blink 1.4s infinite;font-size:16px;}
.ld span:nth-child(2){animation-delay:0.2s;}.ld span:nth-child(3){animation-delay:0.4s;}
@keyframes blink{0%,80%,100%{opacity:0;}40%{opacity:1;}}
.toast{position:fixed;bottom:90px;right:22px;z-index:9998;background:var(--s3);border:1px solid var(--b2);border-radius:8px;padding:11px 16px;font-family:'DM Mono',monospace;font-size:11px;color:var(--t2);max-width:300px;pointer-events:none;}
/* BTC TRACKER STYLES */
.btc-banner{background:linear-gradient(135deg,rgba(247,147,26,0.1),transparent);border:1px solid rgba(247,147,26,0.25);border-radius:12px;padding:20px 24px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;}
.btc-price-display{font-family:'Bebas Neue',sans-serif;font-size:42px;color:var(--btc);line-height:1;}
.btc-stat{text-align:center;}
.btc-stat-label{font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:1px;margin-bottom:4px;}
.btc-stat-val{font-family:'DM Mono',monospace;font-size:18px;}
.btc-goal-bar{height:14px;background:var(--s3);border-radius:7px;overflow:hidden;margin:8px 0;}
.btc-goal-fill{height:100%;background:linear-gradient(90deg,var(--btc),#ffb84d);border-radius:7px;transition:width 1s ease;}
.mnav-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:20px;font-family:'DM Mono',monospace;font-size:12px;font-weight:600;}
.mnav-good{background:rgba(0,230,118,0.15);color:var(--gr);border:1px solid rgba(0,230,118,0.3);}
.mnav-ok{background:rgba(255,215,64,0.1);color:var(--yw);border:1px solid rgba(255,215,64,0.2);}
.mnav-high{background:rgba(255,61,87,0.1);color:var(--rd);border:1px solid rgba(255,61,87,0.2);}
/* CHAT */
#chatBtn{position:fixed;bottom:24px;right:24px;z-index:9999;width:54px;height:54px;border-radius:50%;background:linear-gradient(135deg,var(--ac),var(--ac2));border:none;cursor:pointer;box-shadow:0 4px 20px rgba(0,212,255,0.4);display:flex;align-items:center;justify-content:center;font-size:22px;transition:transform 0.2s;}
#chatBtn:hover{transform:scale(1.1);}
#chatWin{position:fixed;bottom:90px;right:24px;z-index:9999;width:390px;height:520px;background:var(--s1);border:1px solid var(--b2);border-radius:16px;display:none;flex-direction:column;box-shadow:0 8px 40px rgba(0,0,0,0.6);overflow:hidden;}
#chatWin.open{display:flex;}
#chatHead{padding:14px 18px;border-bottom:1px solid var(--b1);background:linear-gradient(135deg,rgba(0,212,255,0.08),transparent);display:flex;align-items:center;justify-content:space-between;}
#chatClose{background:none;border:none;color:var(--t3);font-size:18px;cursor:pointer;}
#chatClose:hover{color:var(--tx);}
#chatMsgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;}
.cmsg{max-width:88%;padding:9px 12px;border-radius:10px;font-size:12px;line-height:1.6;font-family:'DM Mono',monospace;}
.cmsg.user{background:rgba(0,212,255,0.12);color:var(--tx);border:1px solid rgba(0,212,255,0.2);align-self:flex-end;border-bottom-right-radius:3px;}
.cmsg.ai{background:var(--s2);color:var(--t2);border:1px solid var(--b1);align-self:flex-start;border-bottom-left-radius:3px;white-space:pre-wrap;}
.cmsg.err{background:rgba(255,61,87,0.1);color:var(--rd);border:1px solid rgba(255,61,87,0.2);align-self:flex-start;}
#chatFoot{padding:12px;border-top:1px solid var(--b1);display:flex;gap:8px;}
#chatInput{flex:1;background:var(--s2);border:1px solid var(--b2);color:var(--tx);padding:8px 11px;border-radius:8px;font-family:'DM Mono',monospace;font-size:11px;outline:none;resize:none;height:38px;}
#chatInput:focus{border-color:var(--ac);}
#chatSend{background:var(--ac);color:var(--bg);border:none;width:38px;height:38px;border-radius:8px;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;}
#chatSend:disabled{opacity:0.5;cursor:not-allowed;}
.sf{margin-bottom:14px;}
.sl{font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);letter-spacing:1px;margin-bottom:5px;}
.sdot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:5px;}
.sok{background:var(--gr);}.sno{background:var(--t3);}
.ep{background:var(--s2);border:1px solid var(--b2);border-radius:8px;padding:12px;display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end;}
.eg{display:flex;flex-direction:column;gap:3px;}
.egl{font-family:'DM Mono',monospace;font-size:8px;color:var(--t3);letter-spacing:1.5px;text-transform:uppercase;}
.sgr{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;}
::-webkit-scrollbar{width:5px;height:5px;}::-webkit-scrollbar-track{background:var(--s1);}::-webkit-scrollbar-thumb{background:var(--b2);border-radius:3px;}
@media(max-width:1400px){.sgrid{grid-template-columns:repeat(3,1fr);}}
@media(max-width:900px){.sgrid{grid-template-columns:repeat(2,1fr);}.g2,.g3,.sgr{grid-template-columns:1fr;}header,.tabs,.main{padding-left:14px;padding-right:14px;}#chatWin{width:calc(100vw - 32px);right:16px;}}

/* ── PHONE (≤600px) ─────────────────────────────────────────────────────────
   Previously the smallest breakpoint was 900px, so phones (~390px) got a
   desktop layout. Key fix: the ticker column now sticks while the rest of the
   table scrolls horizontally, so you always know which row you're reading. */
@media(max-width:600px){
  .sgrid{grid-template-columns:repeat(2,1fr);gap:8px;}
  header,.tabs,.main{padding-left:10px;padding-right:10px;}
  .main{padding-top:12px;}
  th{padding:8px 8px;font-size:8px;letter-spacing:1px;}
  td{padding:9px 8px;font-size:10.5px;}
  /* Freeze the ticker column so horizontal scroll stays legible */
  .ts{-webkit-overflow-scrolling:touch;position:relative;}
  .ts table th:first-child,
  .ts table td:first-child{
    position:sticky;left:0;z-index:2;
    background:var(--s1);
    box-shadow:2px 0 4px rgba(0,0,0,0.35);
  }
  .ts table th:first-child{background:var(--s2);z-index:3;}
  /* Touch targets: 32px min height for reliable tapping */
  .bts,.btg,.btn{min-height:32px;padding:7px 11px;font-size:10px;}
  .tabs{gap:2px;}
  .tab{padding:11px 12px;font-size:10px;}
  .inp,.ied{font-size:16px;}   /* 16px stops iOS auto-zoom on focus */
  #chatWin{width:calc(100vw - 20px);right:10px;height:70vh;}
  .toast{right:10px;left:10px;max-width:none;bottom:78px;}
}
</style></head>
<body><div class="app">

<header>
  <div class="logo">PORTFOLIO<span> // </span>INTELLIGENCE <span style="font-size:12px;color:var(--t3);">v4</span></div>
  <div class="hdr-r">
    <div class="lu" id="lu">LOADING...</div>
    <button class="btn" onclick="loadAll()">⟳ REFRESH</button>
  </div>
</header>

<div class="tabs">
  <div class="tab on"    onclick="sw('dashboard',this)">DASHBOARD</div>
  <div class="tab"       onclick="sw('performance',this)">PERFORMANCE</div>
  <div class="tab"       onclick="sw('holdings',this)">HOLDINGS</div>
  <div class="tab"       onclick="sw('watchlist',this)">WATCHLIST<span class="bdg" id="wbdg" style="display:none">0</span></div>
  <div class="tab btctab" onclick="sw('btc',this)">₿ BTC TRACKER</div>
  <div class="tab"       onclick="sw('analysis',this)">AI ANALYSIS</div>
  <div class="tab"       onclick="sw('brief',this)">DAILY BRIEF</div>
  <div class="tab"       onclick="sw('settings',this)">SETTINGS ⚙</div>
</div>

<div class="main">

<!-- DASHBOARD -->
<div class="tc on" id="tc-dashboard">
  <div class="sgrid" id="scards"></div>
  <div class="g2">
    <div>
      <div class="sh"><div class="st"><span>//</span>POSITIONS</div></div>
      <div class="tw"><div class="ts"><table>
        <thead><tr>
          <th>TICKER</th><th>PRICE USD</th><th>SATS/SHARE</th><th>DAY%</th><th>VALUE</th><th>P&L</th>
          <th>P/E</th><th>P/S</th><th>PEG</th><th>DILUTION</th><th>SIGNAL</th>
        </tr></thead>
        <tbody id="dtb"></tbody>
      </table></div></div>
    </div>
    <div>
      <div class="sh"><div class="st"><span>//</span>ALLOCATION</div></div>
      <div class="pn"><div class="pb" id="alloc"></div></div>
      <div style="height:16px"></div>
      <div class="sh"><div class="st"><span>//</span>MARGIN</div></div>
      <div class="pn"><div class="pb" id="margin"></div></div>
    </div>
  </div>
  <div class="sh"><div class="st"><span>//</span>SIGNALS</div></div>
  <div id="sigs" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;"></div>
</div>

<!-- PERFORMANCE -->
<div class="tc" id="tc-performance">
  <div class="sh"><div class="st"><span>//</span>PORTFOLIO RETURNS</div></div>
  <div class="pg" id="pcards"></div>
  <div class="sh"><div class="st"><span>//</span>RETURNS BY POSITION</div></div>
  <div class="tw"><div class="ts"><table>
    <thead><tr><th>TICKER</th><th>ACCT</th><th>DAY% USD</th><th>DAY% SATS</th><th>MTD% USD</th><th>MTD% SATS</th><th>3M% USD</th><th>3M% SATS</th><th>YTD% USD</th><th>YTD% SATS</th><th>TOTAL% USD</th></tr></thead>
    <tbody id="ptb"></tbody>
  </table></div></div>
</div>

<!-- HOLDINGS -->
<div class="tc" id="tc-holdings">
  <div class="sh">
    <div class="st"><span>//</span>MANAGE HOLDINGS</div>
    <button class="btn" onclick="tog('ahf')">+ ADD POSITION</button>
  </div>
  <div id="ahf" style="display:none;margin-bottom:18px;">
    <div class="pn"><div class="ph"><div class="pt">NEW POSITION</div></div><div class="pb">
      <div class="fr">
        <input class="inp" id="nti" placeholder="TICKER" style="max-width:90px;text-transform:uppercase">
        <input class="inp" id="nsh" placeholder="SHARES" type="number" style="max-width:100px">
        <input class="inp" id="nco" placeholder="AVG COST $" type="number" step="0.01" style="max-width:120px">
        <input class="inp" id="nac" placeholder="ACCOUNT (MMG/BG)" style="max-width:130px">
        <input class="inp" id="nty" placeholder="TYPE" style="max-width:130px">
        <input class="inp" id="nno" placeholder="Notes" style="flex:2;min-width:180px">
        <button class="btp" onclick="addH()">ADD</button>
        <button class="btn" onclick="tog('ahf')" style="color:var(--t3)">CANCEL</button>
      </div>
    </div></div>
  </div>
  <div class="tw"><div class="ts"><table>
    <thead><tr><th>TICKER</th><th>ACCT</th><th>SHARES</th><th>AVG COST</th><th>PRICE</th><th>DAY%</th><th>VALUE</th><th>P&L</th><th>%PORT</th><th>ACTIONS</th></tr></thead>
    <tbody id="htb"></tbody>
  </table></div></div>
</div>

<!-- WATCHLIST -->
<div class="tc" id="tc-watchlist">
  <div class="sh"><div class="st"><span>//</span>WATCHLIST</div></div>
  <div class="pn" style="margin-bottom:18px;"><div class="ph"><div class="pt">ADD TO WATCHLIST</div></div><div class="pb">
    <div class="fr">
      <input class="inp" id="wti" placeholder="TICKER" style="max-width:90px;text-transform:uppercase">
      <input class="inp" id="wtp" placeholder="TARGET PRICE $" type="number" step="0.01" style="max-width:130px">
      <input class="inp" id="wno" placeholder="Thesis / notes" style="flex:3;min-width:180px">
      <button class="btp" onclick="addW()">ADD</button>
    </div>
  </div></div>
  <div class="tw"><div class="ts"><table>
    <thead><tr><th>TICKER</th><th>PRICE</th><th>TARGET</th><th>%TO TARGET</th><th>DAY%</th><th>P/E</th><th>P/S</th><th>STATUS</th><th>NOTES</th><th>DEL</th></tr></thead>
    <tbody id="wtb"></tbody>
  </table></div></div>
</div>

<!-- BTC TRACKER -->
<div class="tc" id="tc-btc">
  <div class="sh"><div class="st" style="color:var(--btc);">₿<span style="color:var(--btc);"> BTC TRACKER & ACCUMULATION</span></div></div>

  <!-- Main BTC Banner -->
  <div class="btc-banner">
    <div>
      <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:2px;margin-bottom:4px;">BITCOIN PRICE</div>
      <div class="btc-price-display" id="btcPriceBig">$—</div>
      <div id="btcDayChg" style="font-family:'DM Mono',monospace;font-size:12px;margin-top:4px;"></div>
    </div>
    <div style="display:flex;gap:20px;flex-wrap:wrap;">
      <div class="btc-stat"><div class="btc-stat-label">TOTAL STACK</div><div class="btc-stat-val" id="btcTotalStat" style="color:var(--btc);">—</div></div>
      <div class="btc-stat"><div class="btc-stat-label">STACK VALUE</div><div class="btc-stat-val" id="btcValStat">—</div></div>
      <div class="btc-stat"><div class="btc-stat-label">TARGET</div><div class="btc-stat-val" style="color:var(--gr);">10.00 BTC</div></div>
      <div class="btc-stat"><div class="btc-stat-label">REMAINING</div><div class="btc-stat-val" id="btcRemStat" style="color:var(--yw);">—</div></div>
      <div class="btc-stat"><div class="btc-stat-label">mNAV</div><div id="mnavBadge">—</div></div>
    </div>
  </div>

  <!-- Progress to 10 BTC -->
  <div class="pn" style="margin-bottom:20px;"><div class="pb">
    <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
      <span style="font-family:'DM Mono',monospace;font-size:11px;color:var(--t3);">PROGRESS TO 10 BTC GOAL</span>
      <span style="font-family:'DM Mono',monospace;font-size:11px;color:var(--btc);" id="btcProgressPct">—</span>
    </div>
    <div class="btc-goal-bar"><div class="btc-goal-fill" id="btcGoalFill" style="width:0%"></div></div>
    <div style="display:flex;justify-content:space-between;margin-top:4px;">
      <span style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);">0 BTC</span>
      <span style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);">10 BTC TARGET</span>
    </div>
  </div></div>

  <div class="g3">
    <!-- Stack breakdown -->
    <div>
      <div class="sh"><div class="st"><span style="color:var(--btc);">₿</span> STACK BREAKDOWN</div></div>
      <div class="pn"><div class="pb" id="btcStackBreak"></div></div>
    </div>
    <!-- Update holdings -->
    <div>
      <div class="sh"><div class="st"><span style="color:var(--btc);">₿</span> UPDATE BTC HOLDINGS</div></div>
      <div class="pn"><div class="pb">
        <div class="sf"><div class="sl">COLD STORAGE (BTC)</div>
          <input class="inp" id="inp_cold" type="number" step="0.001" placeholder="6.0" style="width:100%;"></div>
        <div class="sf"><div class="sl">BINANCE WALLET (BTC)</div>
          <input class="inp" id="inp_binance" type="number" step="0.001" placeholder="0.477" style="width:100%;"></div>
        <div class="sf"><div class="sl">BTC PRICE OVERRIDE (leave blank for auto)</div>
          <input class="inp" id="inp_btcprice" type="number" step="100" placeholder="auto" style="width:100%;"></div>
        <button class="btp" onclick="saveBtcHoldings()" style="width:100%;margin-top:4px;">SAVE & UPDATE</button>
      </div></div>
    </div>
  </div>

  <!-- BINANCE WALLET -->
  <div class="sh">
    <div class="st"><span style="color:var(--btc);">₿</span> BINANCE WALLET — BTC ACCUMULATION ACCOUNT</div>
    <button class="btn" onclick="tog('bnbAddForm')">+ ADD POSITION</button>
  </div>

  <!-- Add binance position form -->
  <div id="bnbAddForm" style="display:none;margin-bottom:16px;">
    <div class="pn"><div class="ph"><div class="pt">NEW BINANCE POSITION</div></div><div class="pb">
      <div class="fr">
        <input class="inp" id="bnbTi" placeholder="TICKER" style="max-width:90px;text-transform:uppercase">
        <input class="inp" id="bnbSh" placeholder="SHARES" type="number" step="0.0001" style="max-width:110px">
        <input class="inp" id="bnbCo" placeholder="AVG COST $" type="number" step="0.01" style="max-width:130px">
        <input class="inp" id="bnbNo" placeholder="Notes" style="flex:2;min-width:180px">
        <button class="btp" onclick="addBnbPos()">ADD</button>
        <button class="btn" onclick="tog('bnbAddForm')" style="color:var(--t3)">CANCEL</button>
      </div>
    </div></div>
  </div>

  <!-- Binance wallet summary -->
  <div class="pn" style="margin-bottom:16px;"><div class="pb">
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;" id="bnbSummary"></div>
  </div></div>

  <!-- Binance positions table -->
  <div class="tw" style="margin-bottom:24px;"><div class="ts"><table>
    <thead><tr>
      <th>TICKER</th><th>SHARES</th><th>AVG COST</th><th>PRICE</th><th>VALUE $</th>
      <th>VALUE BTC</th><th>P&L</th><th>VS BTC TODAY</th><th>NOTES</th><th>ACTIONS</th>
    </tr></thead>
    <tbody id="bnbTb"></tbody>
  </table></div></div>

  <!-- Stock vs BTC table -->
  <div class="sh"><div class="st"><span style="color:var(--btc);">₿</span> STOCKS vs BITCOIN (MAIN PORTFOLIO)</div></div>
  <div class="tw"><div class="ts"><table>
    <thead><tr>
      <th>TICKER</th><th>ACCT</th>
      <th>SATS/SHARE</th>
      <th>DAY% SATS</th>
      <th>POSITION (BTC)</th>
      <th>VERDICT TODAY</th>
    </tr></thead>
    <tbody id="btcRatioTb"></tbody>
  </table></div></div>

  <!-- mNAV guide -->
  <div class="sh"><div class="st"><span style="color:var(--btc);">₿</span> mNAV STRATEGY GUIDE</div></div>
  <div class="pn"><div class="pb">
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;">
      <div style="background:rgba(0,230,118,0.08);border:1px solid rgba(0,230,118,0.2);border-radius:8px;padding:14px;text-align:center;">
        <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--gr);letter-spacing:1px;margin-bottom:6px;">BUY ZONE</div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:24px;color:var(--gr);">mNAV &lt; 1.3x</div>
        <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);margin-top:4px;">Buy MSTR — below/near NAV<br>Convert to BTC on recovery</div>
      </div>
      <div style="background:rgba(255,215,64,0.08);border:1px solid rgba(255,215,64,0.2);border-radius:8px;padding:14px;text-align:center;">
        <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--yw);letter-spacing:1px;margin-bottom:6px;">HOLD ZONE</div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:24px;color:var(--yw);">1.3x — 2.0x</div>
        <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);margin-top:4px;">Hold MSTR — premium expanding<br>Watch for sell signal</div>
      </div>
      <div style="background:rgba(255,61,87,0.08);border:1px solid rgba(255,61,87,0.2);border-radius:8px;padding:14px;text-align:center;">
        <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--rd);letter-spacing:1px;margin-bottom:6px;">SELL ZONE</div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:24px;color:var(--rd);">mNAV &gt; 2.0x</div>
        <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);margin-top:4px;">Sell MSTR — high premium<br>Convert proceeds to BTC</div>
      </div>
    </div>
  </div></div>
</div>

<!-- AI ANALYSIS -->
<div class="tc" id="tc-analysis">
  <div class="sh"><div class="st"><span>//</span>AI ANALYSIS</div></div>
  <div class="aip">
    <div class="aih">
      <div class="ait"><div class="dot"></div>CLAUDE INTELLIGENCE ENGINE</div>
      <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);">ANTHROPIC_API_KEY → Railway Variables</div>
    </div>
    <div class="pb">
      <div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px;" id="aticks"></div>
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:18px;flex-wrap:wrap;">
        <button class="btp" onclick="anaPos()" id="abtn">ANALYZE POSITION</button>
        <button class="btpu" onclick="anaPort()">ANALYZE FULL PORTFOLIO</button>
      </div>
      <div id="aout"><div style="color:var(--t3);font-family:'DM Mono',monospace;font-size:11px;padding:16px 0;">Select a position above and click ANALYZE POSITION.</div></div>
    </div>
  </div>
</div>

<!-- DAILY BRIEF -->
<div class="tc" id="tc-brief">
  <div class="sh">
    <div class="st"><span>//</span>DAILY BRIEF</div>
    <button class="btp" onclick="genBrief()" id="bbtn">GENERATE BRIEF</button>
  </div>
  <div class="aip">
    <div class="aih">
      <div class="ait"><div class="dot"></div>MORNING INTELLIGENCE REPORT</div>
      <div id="bdate" style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);"></div>
    </div>
    <div class="pb" id="bout"><div style="color:var(--t3);font-family:'DM Mono',monospace;font-size:11px;padding:16px 0;">Click GENERATE BRIEF for your daily intelligence report.</div></div>
  </div>
</div>

<!-- SETTINGS -->
<div class="tc" id="tc-settings">
  <div class="sh"><div class="st"><span>//</span>SETTINGS</div></div>
  <div class="pn" style="margin-bottom:18px;"><div class="ph"><div class="pt">STATUS</div></div>
    <div class="pb" id="sstatus"></div></div>
  <div class="pn"><div class="ph"><div class="pt">HOW TO SET API KEY</div></div>
    <div class="pb">
      <div style="font-size:12px;color:var(--t2);line-height:1.9;">
        <div>1. Go to <a href="https://railway.app" target="_blank" style="color:var(--ac)">railway.app</a> → your project → your service</div>
        <div>2. Click the <strong style="color:var(--tx)">Variables</strong> tab</div>
        <div>3. Add <code style="color:var(--ac);background:var(--s3);padding:2px 6px;border-radius:3px;">ANTHROPIC_API_KEY</code> = your sk-ant-... key</div>
        <div>4. Add <code style="color:var(--yw);background:var(--s3);padding:2px 6px;border-radius:3px;">PORTFOLIO_MARGIN</code> = 120000</div>
        <div>5. Railway redeploys automatically</div>
        <div style="margin-top:8px;color:var(--t3);">Get key at <a href="https://console.anthropic.com/settings/keys" target="_blank" style="color:var(--ac)">console.anthropic.com</a></div>
      </div>
    </div></div>
</div>

</div></div>

<!-- FLOATING CHAT -->
<button id="chatBtn" onclick="togChat()" title="Chat with Portfolio AI">💬</button>
<div id="chatWin">
  <div id="chatHead">
    <div class="ait"><div class="dot"></div>PORTFOLIO ASSISTANT</div>
    <button id="chatClose" onclick="togChat()">×</button>
  </div>
  <div id="chatMsgs">
    <div class="cmsg ai">Hi Ricardo! I know your full portfolio, BTC accumulation strategy, and all position theses. Ask me anything.</div>
  </div>
  <div id="chatFoot">
    <textarea id="chatInput" placeholder="Ask about your portfolio, BTC strategy, positions..." onkeydown="chatKey(event)"></textarea>
    <button id="chatSend" onclick="sendChat()">↑</button>
  </div>
</div>

<script>
// ─── CONSTANTS ────────────────────────────────────────────────────────────────
const SATS_PER_MSTR = 219900;
const BTC_KEY = 'pf_btc_v4';
const BNB_POS_KEY = 'pf_binance_positions_v4';
// ── FUNDAMENTALS: fetched from backend, NOT hardcoded ─────────────────────────
// Previously this object duplicated the Python FUND dict. Updating one and not
// the other caused silent drift — the exact bug class that made the app feel
// stale. Now the backend owns the data; this is populated at boot.
let F = {};
let RULES_FE = {};
async function loadFundamentals(){
  try{
    const d = await api('GET','/fundamentals');
    F = d.fundamentals || {};
    RULES_FE = d.rules || {};
  }catch(e){
    console.warn('fundamentals fetch failed, cards will show —', e);
    F = {};
  }
}

// ─── STATE ────────────────────────────────────────────────────────────────────
let S = {h:[],w:[],q:{},hist:{},sel:null};
let btcHold = JSON.parse(localStorage.getItem(BTC_KEY) || '{"cold":6.0,"binance":0.477}');
let binancePos = JSON.parse(localStorage.getItem(BNB_POS_KEY) || JSON.stringify([
  {id:1, ticker:"AMZN", shares:76, avg_cost:270.61, notes:"AMZNon tokenized — for BTC accumulation"}
]));
let chatHistory = [];
let chatOpen = false;

// ─── API ──────────────────────────────────────────────────────────────────────
async function api(m,p,b){
  const o={method:m,headers:{"Content-Type":"application/json"}};
  if(b)o.body=JSON.stringify(b);
  const r=await fetch("/api"+p,o);
  const d=await r.json();
  if(!r.ok)throw new Error(d.error||d.detail||r.statusText);
  return d;
}

// ─── BTC HELPERS ─────────────────────────────────────────────────────────────
function getBtcPrice(){
  const override = parseFloat(document.getElementById('inp_btcprice')?.value);
  if(override && override>1000) return override;
  return S.q['BTC']?.price || 61000;
}

function getMstrBtc(){
  // MSTR BTC value at MARKET PRICE (if sold today, how much BTC could you buy)
  const totalShares = S.h.filter(h=>h.ticker==='MSTR').reduce((sum,h)=>sum+h.shares,0);
  const mstrPrice = S.q['MSTR']?.price || 0;
  const btcPrice = getBtcPrice();
  if(!mstrPrice || !btcPrice) return 0;
  return (totalShares * mstrPrice) / btcPrice;
}

function getMstrNavBtc(){
  // MSTR BTC at NAV (theoretical holding via sats per share)
  const totalShares = S.h.filter(h=>h.ticker==='MSTR').reduce((sum,h)=>sum+h.shares,0);
  return (totalShares * SATS_PER_MSTR) / 100000000;
}

function getBinancePosBtc(){
  const btcP = getBtcPrice();
  if(!btcP) return 0;
  return binancePos.reduce((sum, p)=>{
    const q = S.q[p.ticker] || {price: p.avg_cost};
    return sum + (q.price * p.shares) / btcP;
  }, 0);
}

function getTotalBtc(){ return btcHold.cold + btcHold.binance + getMstrBtc() + getBinancePosBtc(); }

function getMnav(){
  const btcP = getBtcPrice();
  const mstrP = S.q['MSTR']?.price;
  if(!btcP || !mstrP) return null;
  const navPerShare = (SATS_PER_MSTR / 100000000) * btcP;
  return mstrP / navPerShare;
}

function saveBtcHoldings(){
  const cold = parseFloat(document.getElementById('inp_cold').value);
  const binance = parseFloat(document.getElementById('inp_binance').value);
  if(!isNaN(cold)) btcHold.cold = cold;
  if(!isNaN(binance)) btcHold.binance = binance;
  localStorage.setItem(BTC_KEY, JSON.stringify(btcHold));
  renderBtcTab();
  toast('BTC holdings saved ✓');
}

// ─── BINANCE POSITIONS ──────────────────────────────────────────────────────
function saveBnbPos(){
  localStorage.setItem(BNB_POS_KEY, JSON.stringify(binancePos));
}

async function addBnbPos(){
  const ti = document.getElementById('bnbTi').value.toUpperCase().trim();
  const sh = parseFloat(document.getElementById('bnbSh').value);
  const co = parseFloat(document.getElementById('bnbCo').value);
  const no = document.getElementById('bnbNo').value.trim();
  if(!ti || !sh || !co){toast('Ticker, shares and cost required','err');return;}
  const newId = Math.max(...binancePos.map(p=>p.id||0), 0) + 1;
  binancePos.push({id:newId, ticker:ti, shares:sh, avg_cost:co, notes:no});
  saveBnbPos();
  // Ensure quotes for this ticker are loaded
  try{
    const newQ = await api('GET','/quotes');
    S.q = {...S.q, ...newQ};
  }catch(e){}
  tog('bnbAddForm');
  ['bnbTi','bnbSh','bnbCo','bnbNo'].forEach(id=>document.getElementById(id).value='');
  renderBtcTab();
  toast(`${ti} added to Binance wallet`);
}

function editBnbPos(id){
  const p = binancePos.find(x=>x.id===id);
  if(!p) return;
  EditState.begin('bnb:'+id);
  const tr = document.getElementById(`bnb_${id}`);
  if(!tr) return;
  tr.innerHTML = `
    <td><span class="tb">${p.ticker}</span></td>
    <td><input class="ied" id="bes_${id}" type="number" step="0.0001" value="${p.shares}" style="width:90px;"></td>
    <td><input class="ied" id="bec_${id}" type="number" step="0.01" value="${p.avg_cost}" style="width:90px;"></td>
    <td colspan="6"><input class="ied" id="ben_${id}" value="${p.notes||''}" style="width:100%;"></td>
    <td><div style="display:flex;gap:4px;justify-content:flex-end;">
      <button class="btg" onclick="saveBnbEdit(${id})">SAVE</button>
      <button class="bts" onclick="EditState.end('bnb:${id}');renderBtcTab()">CANCEL</button>
    </div></td>`;
}

function saveBnbEdit(id){
  EditState.end('bnb:'+id);
  const p = binancePos.find(x=>x.id===id);
  if(!p) return;
  const shares = parseFloat(document.getElementById(`bes_${id}`).value);
  const avg_cost = parseFloat(document.getElementById(`bec_${id}`).value);
  const notes = document.getElementById(`ben_${id}`).value;
  if(!shares || shares<=0){toast('Shares > 0','err');return;}
  p.shares = shares; p.avg_cost = avg_cost; p.notes = notes;
  saveBnbPos();
  renderBtcTab();
  toast(`${p.ticker} updated`);
}

function delBnbPos(id){
  const p = binancePos.find(x=>x.id===id);
  if(!p) return;
  if(!confirm(`Remove ${p.ticker} from Binance wallet?`)) return;
  binancePos = binancePos.filter(x=>x.id!==id);
  saveBnbPos();
  renderBtcTab();
  toast(`${p.ticker} removed`);
}

// ─── LOAD ────────────────────────────────────────────────────────────────────
async function loadAll(opts){
  const silent = opts && opts.silent;
  if(!silent) document.getElementById('lu').textContent='REFRESHING...';
  try{
    const extraTickers = binancePos.map(p=>p.ticker).join(',');
    const quotesUrl = '/quotes' + (extraTickers ? '?extra='+encodeURIComponent(extraTickers) : '');
    const[h,w,q,st,snap]=await Promise.all([api('GET','/holdings'),api('GET','/watchlist'),api('GET',quotesUrl),api('GET','/status'),api('GET','/snapshot')]);
    S.h=h; S.w=w; S.q=q; S.snap=snap;
    if(!S.sel&&h.length) S.sel=h[0].ticker;
    // Flag when Yahoo failed and we're serving hardcoded fallback prices
    const vals=Object.values(q||{});
    const STALE=['default','error','unknown'];
    const bad=vals.filter(x=>x&&STALE.includes(x.source)).length;
    // Which provider actually served the data (finnhub > yahoo > stooq)
    const live=vals.filter(x=>x&&!STALE.includes(x.source));
    const provider=live.length?[...new Set(live.map(x=>x.source))].join('/'):'';
    const lu=document.getElementById('lu');
    const t=new Date().toLocaleTimeString();
    if(bad>0){
      lu.textContent=`⚠ ${bad} STALE — ${t}`;
      lu.style.color='#f5a623';
    }else{
      lu.textContent=`LIVE (${provider}) — ${t}`;
      lu.style.color='';
    }
    // Never rebuild the DOM while the user is mid-edit — it would wipe their input.
    if(EditState.active){
      renderSCards(); renderAlloc(); renderMargin(); renderSigs();
      renderPerfCards(); renderPerfTable();
    }else{
      renderAll();
    }
    loadHist();
    renderStatus(st);
  }catch(e){
    // A failed background poll must not blank the dashboard — keep last-good
    // data on screen and just mark the timestamp.
    const lu=document.getElementById('lu');
    lu.textContent='⚠ OFFLINE — retrying';
    lu.style.color='#ff5252';
    if(!silent) toast(e.message,'err');   // only surface errors on manual refresh
  }
}

async function loadHist(){
  try{const h=await api('GET','/historical');S.hist=h;renderPerfCards();renderPerfTable();renderSCards();renderBtcTab();}
  catch(e){console.warn('Hist failed',e);}
}

// ─── HELPERS ─────────────────────────────────────────────────────────────────
const gq=t=>S.q[t]||{price:0,change_pct:0};
const gf=t=>({...F[t],...(S.q[t]?.fundamentals||{})});
function ps(){
  let tv=0,tc=0;
  S.h.forEach(h=>{const q=gq(h.ticker);tv+=q.price*h.shares;tc+=h.avg_cost*h.shares;});
  const m=120000;
  return{tv,tc,pl:tv-tc,plp:tc?(tv-tc)/tc*100:0,ne:tv-m,lvr:tv?m/tv*100:0,m};
}
function tpl(){
  let pl=0,pv=0;
  S.h.forEach(h=>{const q=gq(h.ticker);const p=q.price/(1+q.change_pct/100);pl+=(q.price-p)*h.shares;pv+=p*h.shares;});
  return{pl,pct:pv?pl/pv*100:0};
}
function wr(f){
  let s=0,w=0;const st=ps();
  S.h.forEach(h=>{const hist=S.hist[h.ticker];const q=gq(h.ticker);if(hist?.[f]!=null){const wt=st.tv?q.price*h.shares/st.tv:0;s+=hist[f]*wt;w+=wt;}});
  return w>0?+s.toFixed(2):null;
}
const fmt$=n=>"$"+Math.abs(n).toLocaleString("en-US",{minimumFractionDigits:0,maximumFractionDigits:0});
function fmtP(v,l=false){if(l)return'<span style="color:var(--t3)">...</span>';if(v==null)return'<span style="color:var(--t3)">—</span>';return`<span class="${v>=0?"pos":"neg"}">${v>=0?"+":""}${v.toFixed(2)}%</span>`;}
function sgc(s){return{ADD:"sg-a",ACCUMULATE:"sg-ac",HOLD:"sg-h",TRIM:"sg-t"}[s]||"sg-w";}
function sgi(s){return{ADD:"▲",HOLD:"■",TRIM:"▼"}[s]||"◆";}
const tog=id=>{const e=document.getElementById(id);e.style.display=e.style.display==="none"?"block":"none";};

// ─── RENDER ALL ───────────────────────────────────────────────────────────────
function renderAll(){
  renderSCards(); renderDash(); renderAlloc(); renderMargin(); renderSigs();
  renderPerfCards(); renderPerfTable(); renderHoldings(); renderWatchlist();
  renderATickers(); updateWBadge(); renderBtcTab();
}

// ─── SUMMARY CARDS ────────────────────────────────────────────────────────────
function renderSCards(){
  const s=ps(),t=tpl(),lev=s.ne?s.tv/s.ne:0;
  const ytd=wr("ytd"),mtd=wr("mtd"),m3=wr("m3"),hl=Object.keys(S.hist).length===0&&Object.keys(S.q).length>0;
  const fv=(v,l)=>v!=null?`${v>=0?"+":""}${v.toFixed(2)}%`:l?"...":"—";
  const btcP=getBtcPrice(); const mnav=getMnav();
  const cards=[
    {l:"PORTFOLIO VALUE",v:fmt$(s.tv),sub:`${t.pl>=0?"+":""}${fmt$(t.pl)} today (${t.pct>=0?"+":""}${t.pct.toFixed(2)}%)`,sc:t.pl>=0?"pos":"neg",ac:""},
    {l:"TOTAL P&L",v:(s.pl>=0?"+":"")+fmt$(s.pl),sub:`${s.plp.toFixed(2)}% all-time`,sc:s.pl>=0?"pos":"neg",ac:s.pl>=0?"gr":"rd"},
    {l:"NET EQUITY",v:fmt$(s.ne),sub:`Leverage ${lev.toFixed(2)}×`,sc:lev>2?"neg":lev>1.5?"neu":"pos",ac:""},
    {l:"MTD RETURN",v:fv(mtd,hl),sub:"Month to date",sc:mtd!=null?(mtd>=0?"pos":"neg"):"neu",ac:mtd!=null?(mtd>=0?"gr":"rd"):"yw"},
    {l:"YTD RETURN",v:fv(ytd,hl),sub:`Since Jan 1 ${new Date().getFullYear()}`,sc:ytd!=null?(ytd>=0?"pos":"neg"):"neu",ac:ytd!=null?(ytd>=0?"gr":"rd"):"yw"},
    {l:"MSTR mNAV",v:mnav?`${mnav.toFixed(3)}x`:"—",sub:mnav?(mnav<1?"BELOW NAV — BUY SIGNAL":mnav<1.5?"Near NAV":mnav<2?"Premium OK":"HIGH — Consider Selling"):"Loading",sc:mnav?(mnav<1?"pos":mnav<1.5?"pos":mnav<2?"neu":"neg"):"neu",ac:"btc"},
  ];
  document.getElementById("scards").innerHTML=cards.map(c=>`<div class="sc ${c.ac}"><div class="cl">${c.l}</div><div class="cv ${c.sc}">${c.v}</div><div class="cs ${c.sc}">${c.sub}</div></div>`).join("");
}

// ─── DASHBOARD TABLE ──────────────────────────────────────────────────────────
function renderDash(){
  const st=ps(); const btcP=getBtcPrice();
  // Consolidate holdings by ticker (combine MMG + BG positions of same stock)
  const grouped = {};
  S.h.forEach(h=>{
    if(!grouped[h.ticker]){
      grouped[h.ticker] = {ticker:h.ticker,type:h.type,shares:0,total_cost:0,accounts:[],notes:h.notes,signal:h.signal};
    }
    grouped[h.ticker].shares += h.shares;
    grouped[h.ticker].total_cost += h.avg_cost * h.shares;
    if(h.account && !grouped[h.ticker].accounts.includes(h.account)){
      grouped[h.ticker].accounts.push(h.account);
    }
  });
  const consolidated = Object.values(grouped).map(g=>({
    ...g,
    avg_cost: g.shares ? g.total_cost/g.shares : 0,
    account: g.accounts.join("+")
  }));

  document.getElementById("dtb").innerHTML=consolidated.map(h=>{
    const q=gq(h.ticker),f=gf(h.ticker),val=q.price*h.shares,pl=(q.price-h.avg_cost)*h.shares,plp=h.avg_cost?(q.price-h.avg_cost)/h.avg_cost*100:0;
    const sig=h.signal||{signal:"HOLD"};
    // Sats per share calculation: (stock USD / BTC USD) * 100,000,000
    const satsPerShare = btcP && q.price ? Math.round((q.price/btcP)*100000000) : 0;
    const satsFormatted = satsPerShare > 1000000
      ? (satsPerShare/1000000).toFixed(2)+"M"
      : satsPerShare > 1000
        ? (satsPerShare/1000).toFixed(1)+"K"
        : satsPerShare.toLocaleString();

    return`<tr>
      <td><div class="tb">${h.ticker}</div><div class="tt">${h.type} <span style="color:var(--yw);">${h.account||""}</span> · ${h.shares.toLocaleString()} sh</div></td>
      <td style="color:var(--tx)">$${q.price.toFixed(2)}</td>
      <td style="color:var(--btc);font-family:'DM Mono',monospace;">${satsFormatted} sats</td>
      <td class="${q.change_pct>=0?"pos":"neg"}">${q.change_pct>=0?"+":""}${q.change_pct.toFixed(2)}%</td>
      <td>${fmt$(val)}</td>
      <td class="${pl>=0?"pos":"neg"}">${pl>=0?"+":""}${fmt$(pl)} (${plp.toFixed(1)}%)</td>
      <td>${f.pe||"—"}</td><td>${f.ps||"—"}</td>
      <td class="${f.peg&&f.peg<1?"pos":f.peg&&f.peg>2.5?"neg":""}">${f.peg||"—"}</td>
      <td style="color:${h.ticker==="MSTR"?"var(--rd)":h.ticker==="LLY"?"var(--gr)":"var(--t2)"}">${f.dilution||"—"}</td>
      <td><span class="sg ${sgc(sig.signal)}">${sgi(sig.signal)} ${sig.signal}</span></td>
    </tr>`;
  }).join("");
}

// ─── ALLOCATION & MARGIN ─────────────────────────────────────────────────────
function renderAlloc(){
  const st=ps();const cols=["#00d4ff","#00e676","#ffd740","#ff6d00","#ff3d57","#b388ff","#f7931a"];
  // Consolidate by ticker for allocation
  const grouped = {};
  S.h.forEach(h=>{
    if(!grouped[h.ticker]) grouped[h.ticker] = {ticker:h.ticker,shares:0};
    grouped[h.ticker].shares += h.shares;
  });
  const consolidated = Object.values(grouped);
  document.getElementById("alloc").innerHTML=consolidated.map((h,i)=>{
    const q=gq(h.ticker),pct=st.tv?q.price*h.shares/st.tv*100:0;
    return`<div class="ai"><div class="at">${h.ticker}</div><div class="ab"><div class="af" style="width:${pct}%;background:${cols[i%cols.length]};"></div></div><div class="ap">${pct.toFixed(1)}%</div></div>`;
  }).join("");
}

function renderMargin(){
  const s=ps(),lev=s.ne?s.tv/s.ne:0,h=s.lvr>50?{l:"DANGER",c:"neg"}:s.lvr>35?{l:"ELEVATED",c:"neu"}:{l:"HEALTHY",c:"pos"};
  document.getElementById("margin").innerHTML=`
    <div class="mr"><div class="ml">MARGIN</div><div class="mv">${fmt$(s.m)}</div></div>
    <div class="mr"><div class="ml">NET EQUITY</div><div class="mv">${fmt$(s.ne)}</div></div>
    <div class="mr"><div class="ml">LVR</div><div class="mv ${h.c}">${s.lvr.toFixed(1)}%</div></div>
    <div class="mr"><div class="ml">LEVERAGE</div><div class="mv">${lev.toFixed(2)}×</div></div>
    <div class="mr"><div class="ml">STATUS</div><div class="mv ${h.c}">${h.l}</div></div>`;
}

function renderSigs(){
  // Signals are computed server-side in build_snapshot() and exposed via
  // /api/snapshot. They are NOT on /api/holdings — reading h.signal there was
  // always undefined, which is why this panel rendered empty cards.
  const el=document.getElementById("sigs");
  const positions=(S.snap&&S.snap.positions)||[];
  if(!positions.length){
    el.innerHTML='<div style="font-size:11px;color:var(--t3);padding:8px;">No signals yet — waiting for quote data.</div>';
    return;
  }
  // Consolidate multi-account holdings into one card per ticker
  const seen=new Set();
  const consolidated=positions.filter(p=>{
    if(seen.has(p.ticker)) return false;
    seen.add(p.ticker); return true;
  });
  el.innerHTML=consolidated.map(p=>{
    const sig=p.signal||{signal:"HOLD",reasons:[]};
    const accounts=[...new Set(positions.filter(x=>x.ticker===p.ticker).map(x=>x.account||""))].filter(Boolean).join("+");
    const reasons=(sig.reasons||[]);
    const body=reasons.length
      ? reasons.map(r=>`• ${r}`).join("<br>")
      : '<span style="color:var(--t3);">No active triggers</span>';
    return`<div class="pn" style="flex:1;min-width:190px;max-width:260px;">
      <div class="ph"><div class="pt">${p.ticker} <span style="color:var(--yw);font-size:9px;">${accounts}</span></div><span class="sg ${sgc(sig.signal)}">${sig.signal}</span></div>
      <div class="pb" style="padding:10px 14px;"><div style="font-size:11px;color:var(--t3);line-height:1.7;">${body}</div></div>
    </div>`;
  }).join("");
}

// ─── PERFORMANCE ──────────────────────────────────────────────────────────────
function renderPerfCards(){
  const t=tpl(),ytd=wr("ytd"),mtd=wr("mtd"),m3=wr("m3"),hl=Object.keys(S.hist).length===0;
  const fv=(v,l)=>v!=null?`<span class="${v>=0?"pos":"neg"}" style="font-size:26px">${v>=0?"+":""}${v.toFixed(2)}%</span>`:l?`<span style="color:var(--t3);font-size:16px">...</span>`:`<span style="color:var(--t3)">—</span>`;
  document.getElementById("pcards").innerHTML=[
    {l:"TODAY",v:t.pct,sub:`${t.pl>=0?"+":""}${fmt$(t.pl)}`},
    {l:"MTD",v:mtd,sub:"Month to date"},{l:"3-MONTH",v:m3,sub:"Rolling 90 days"},
    {l:`YTD ${new Date().getFullYear()}`,v:ytd,sub:"Since Jan 1"},
  ].map(c=>`<div class="pc"><div class="pl">${c.l}</div><div class="pv">${fv(c.v,hl&&c.l!=="TODAY")}</div><div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);margin-top:4px;">${c.sub}</div></div>`).join("");
}

function renderPerfTable(){
  const hl=Object.keys(S.hist).length===0;
  const btcQ = S.q['BTC']||{};
  const btcHist = S.hist['BTC']||{};
  const btcDay = btcQ.change_pct;

  // Consolidate by ticker
  const grouped = {};
  S.h.forEach(h=>{
    if(!grouped[h.ticker]){
      grouped[h.ticker] = {ticker:h.ticker,type:h.type,shares:0,total_cost:0,accounts:[]};
    }
    grouped[h.ticker].shares += h.shares;
    grouped[h.ticker].total_cost += h.avg_cost * h.shares;
    if(h.account && !grouped[h.ticker].accounts.includes(h.account)){
      grouped[h.ticker].accounts.push(h.account);
    }
  });
  const consolidated = Object.values(grouped).map(g=>({
    ...g,
    avg_cost: g.shares ? g.total_cost/g.shares : 0,
    account: g.accounts.join("+")
  }));

  // % change in sats = stock_USD_change - BTC_USD_change
  // (since sats_now/sats_then = (S1/B1)/(S0/B0), and small-change approximation
  //  gives % change as difference of % changes)
  const satsChg = (stockPct,btcPct)=>{
    if(stockPct==null || btcPct==null) return null;
    return stockPct - btcPct;
  };
  const renderPct = (v,l=false)=>{
    if(l) return '<span style="color:var(--t3)">...</span>';
    if(v==null) return '<span style="color:var(--t3)">—</span>';
    return `<span class="${v>=0?"pos":"neg"}">${v>=0?"+":""}${v.toFixed(2)}%</span>`;
  };

  document.getElementById("ptb").innerHTML=consolidated.map(h=>{
    const q=gq(h.ticker),hist=S.hist[h.ticker]||{},plp=h.avg_cost?(q.price-h.avg_cost)/h.avg_cost*100:0;
    const daySats = satsChg(q.change_pct,btcDay);
    const mtdSats = satsChg(hist.mtd,btcHist.mtd);
    const m3Sats = satsChg(hist.m3,btcHist.m3);
    const ytdSats = satsChg(hist.ytd,btcHist.ytd);
    return`<tr>
      <td><div class="tb">${h.ticker}</div><div class="tt">${h.type} · ${h.shares.toLocaleString()} sh</div></td>
      <td style="color:var(--yw);text-align:left;font-size:10px;">${h.account||"—"}</td>
      <td class="${q.change_pct>=0?"pos":"neg"}">${q.change_pct>=0?"+":""}${q.change_pct.toFixed(2)}%</td>
      <td>${renderPct(daySats)}</td>
      <td>${renderPct(hist.mtd,hl)}</td>
      <td>${renderPct(mtdSats,hl)}</td>
      <td>${renderPct(hist.m3,hl)}</td>
      <td>${renderPct(m3Sats,hl)}</td>
      <td>${renderPct(hist.ytd,hl)}</td>
      <td>${renderPct(ytdSats,hl)}</td>
      <td class="${plp>=0?"pos":"neg"}">${plp>=0?"+":""}${plp.toFixed(2)}%</td>
    </tr>`;
  }).join("");

  // BTC reference row
  if(!hl && btcQ.price){
    document.getElementById("ptb").innerHTML += `<tr style="background:rgba(247,147,26,0.05);">
      <td><div class="tb" style="color:var(--btc);">₿ BTC</div><div class="tt">$${btcQ.price.toLocaleString('en-US',{maximumFractionDigits:0})}</div></td>
      <td style="color:var(--btc);font-size:10px;">BENCHMARK</td>
      <td class="${btcDay>=0?"pos":"neg"}">${btcDay>=0?"+":""}${btcDay?btcDay.toFixed(2):"—"}%</td>
      <td style="color:var(--t3);text-align:center;font-style:italic;">—</td>
      <td>${renderPct(btcHist.mtd,hl)}</td>
      <td style="color:var(--t3);text-align:center;font-style:italic;">—</td>
      <td>${renderPct(btcHist.m3,hl)}</td>
      <td style="color:var(--t3);text-align:center;font-style:italic;">—</td>
      <td>${renderPct(btcHist.ytd,hl)}</td>
      <td style="color:var(--t3);text-align:center;font-style:italic;">—</td>
      <td style="color:var(--btc);font-size:10px;">BENCHMARK</td>
    </tr>`;
  }
}

// ─── HOLDINGS TABLE ──────────────────────────────────────────────────────────
function renderHoldings(){
  const st=ps();
  document.getElementById("htb").innerHTML=S.h.map(h=>{
    const q=gq(h.ticker),val=q.price*h.shares,pl=(q.price-h.avg_cost)*h.shares,plp=h.avg_cost?(q.price-h.avg_cost)/h.avg_cost*100:0,pp=st.tv?val/st.tv*100:0;
    return`<tr id="hr${h.id}">
      <td><span class="tb">${h.ticker}</span></td>
      <td style="color:var(--yw);font-size:10px;">${h.account||"—"}</td>
      <td>${h.shares.toLocaleString()}</td><td>$${h.avg_cost.toFixed(2)}</td>
      <td>$${q.price.toFixed(2)}</td>
      <td class="${q.change_pct>=0?"pos":"neg"}">${q.change_pct>=0?"+":""}${q.change_pct.toFixed(2)}%</td>
      <td>${fmt$(val)}</td>
      <td class="${pl>=0?"pos":"neg"}">${pl>=0?"+":""}${fmt$(pl)} (${plp.toFixed(1)}%)</td>
      <td>${pp.toFixed(1)}%</td>
      <td><div style="display:flex;gap:5px;justify-content:flex-end;">
        <button class="bts" onclick="editH(${h.id})">EDIT</button>
        <button class="bts btd" onclick="delH(${h.id},'${h.ticker}')">DEL</button>
      </div></td>
    </tr>`;
  }).join("");
}

// ─── WATCHLIST ───────────────────────────────────────────────────────────────
function renderWatchlist(){
  if(!S.w.length){document.getElementById("wtb").innerHTML=`<tr><td colspan="10" style="text-align:center;color:var(--t3);padding:24px;">No watchlist items.</td></tr>`;return;}
  document.getElementById("wtb").innerHTML=S.w.map(w=>{
    const q=gq(w.ticker),f=gf(w.ticker),diff=w.target_price?((q.price-w.target_price)/w.target_price*100):null;
    const sl=diff==null?"sg-w":diff<=0?"sg-a":diff<=5?"sg-h":"sg-w";
    const st=diff==null?"WATCHING":diff<=0?"✓ AT TARGET":diff<=5?"CLOSE":`${diff.toFixed(1)}% ABOVE`;
    return`<tr>
      <td><span class="tb">${w.ticker}</span></td>
      <td>$${q.price.toFixed(2)}</td><td>${w.target_price?"$"+w.target_price.toFixed(2):"—"}</td>
      <td class="${diff!=null?(diff<=0?"pos":diff<=5?"neu":"neg"):""}">${diff!=null?`${diff>=0?"+":""}${diff.toFixed(1)}%`:"—"}</td>
      <td class="${q.change_pct>=0?"pos":"neg"}">${q.change_pct>=0?"+":""}${q.change_pct.toFixed(2)}%</td>
      <td>${f.pe||"—"}</td><td>${f.ps||"—"}</td>
      <td><span class="sg ${sl}">${st}</span></td>
      <td style="color:var(--t3);font-size:10px;max-width:180px;white-space:normal;text-align:left;">${w.notes||"—"}</td>
      <td><button class="bts btd" onclick="delW(${w.id})">DEL</button></td>
    </tr>`;
  }).join("");
}

// ─── BTC TRACKER TAB ─────────────────────────────────────────────────────────
function renderBtcTab(){
  const btcP = getBtcPrice();
  const btcQ = S.q['BTC'] || {};
  const mstrBtc = getMstrBtc();
  const totalBtc = getTotalBtc();
  const progress = Math.min((totalBtc/10)*100,100);
  const remaining = Math.max(10-totalBtc,0);
  const mnav = getMnav();

  // Banner
  document.getElementById('btcPriceBig').textContent = '$'+btcP.toLocaleString('en-US',{maximumFractionDigits:0});
  const dayChg = btcQ.change_pct;
  document.getElementById('btcDayChg').innerHTML = dayChg!=null?`<span class="${dayChg>=0?"pos":"neg"}">${dayChg>=0?"+":""}${dayChg.toFixed(2)}% today</span>`:"";
  document.getElementById('btcTotalStat').textContent = totalBtc.toFixed(4)+' BTC';
  document.getElementById('btcValStat').textContent = '$'+(totalBtc*btcP).toLocaleString('en-US',{maximumFractionDigits:0});
  document.getElementById('btcRemStat').textContent = remaining.toFixed(4)+' BTC';
  document.getElementById('btcProgressPct').textContent = progress.toFixed(1)+'%';
  document.getElementById('btcGoalFill').style.width = progress+'%';

  // mNAV badge
  if(mnav){
    const mnavCls = mnav<1?"mnav-good":mnav<1.5?"mnav-good":mnav<2?"mnav-ok":"mnav-high";
    const mnavTxt = mnav<1?"BELOW NAV — BUY":mnav<1.3?"NEAR NAV — BUY":mnav<2?"HOLD":">2x — SELL";
    document.getElementById('mnavBadge').innerHTML = `<span class="mnav-badge ${mnavCls}">${mnav.toFixed(3)}x ${mnavTxt}</span>`;
  }

  // Stack breakdown
  const totalMstrShares = S.h.filter(h=>h.ticker==="MSTR").reduce((s,h)=>s+h.shares,0);
  const mstrPrice = S.q['MSTR']?.price || 0;
  const marketSatsPerShare = btcP ? Math.round((mstrPrice/btcP)*100000000) : 0;
  const navSatsPerShare = SATS_PER_MSTR; // 219,900
  const satsDiscount = marketSatsPerShare && navSatsPerShare ? ((marketSatsPerShare - navSatsPerShare)/navSatsPerShare*100) : 0;
  const mstrNote = `${totalMstrShares} sh × $${mstrPrice.toFixed(2)} = ${marketSatsPerShare.toLocaleString()} mkt sats vs ${navSatsPerShare.toLocaleString()} NAV sats (${satsDiscount>=0?"+":""}${satsDiscount.toFixed(1)}%)`;

  // Binance positions BTC equivalent
  const bnbPosBtc = getBinancePosBtc();
  const bnbPosNote = binancePos.length > 0
    ? binancePos.map(p=>{
        const q = S.q[p.ticker] || {price:p.avg_cost};
        return `${p.shares} ${p.ticker} @ $${q.price.toFixed(2)}`;
      }).join(' + ')
    : "No positions";

  const stackItems = [
    {label:"COLD STORAGE",btc:btcHold.cold,color:"#f7931a",note:"Long-term hold"},
    {label:"BINANCE BTC",btc:btcHold.binance,color:"#ffb84d",note:"Active trading wallet"},
    {label:"BINANCE STOCKS",btc:bnbPosBtc,color:"#ffd740",note:bnbPosNote},
    {label:"MSTR (MARKET VALUE)",btc:mstrBtc,color:"#00d4ff",note:mstrNote},
  ];
  document.getElementById('btcStackBreak').innerHTML = stackItems.map(item=>`
    <div style="margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
        <div>
          <span style="font-family:'DM Mono',monospace;font-size:11px;color:${item.color};">${item.label}</span>
          <span style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);margin-left:8px;">${item.note}</span>
        </div>
        <span style="font-family:'DM Mono',monospace;font-size:12px;color:${item.color};">${item.btc.toFixed(4)} BTC</span>
      </div>
      <div class="ab"><div class="af" style="width:${totalBtc?(item.btc/totalBtc*100):0}%;background:${item.color};height:8px;border-radius:4px;"></div></div>
      <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);margin-top:3px;">${totalBtc?(item.btc/totalBtc*100).toFixed(1):0}% of stack | $${(item.btc*btcP).toLocaleString('en-US',{maximumFractionDigits:0})}</div>
    </div>`).join('');

  // Populate input fields
  document.getElementById('inp_cold').value = btcHold.cold;
  document.getElementById('inp_binance').value = btcHold.binance;

  // Stocks vs BTC table — consolidated by ticker
  const grouped = {};
  S.h.forEach(h=>{
    if(!grouped[h.ticker]){
      grouped[h.ticker] = {ticker:h.ticker,type:h.type,shares:0,total_cost:0,accounts:[]};
    }
    grouped[h.ticker].shares += h.shares;
    grouped[h.ticker].total_cost += h.avg_cost * h.shares;
    if(h.account && !grouped[h.ticker].accounts.includes(h.account)){
      grouped[h.ticker].accounts.push(h.account);
    }
  });
  const consolidatedBtc = Object.values(grouped).map(g=>({
    ...g,
    avg_cost: g.shares ? g.total_cost/g.shares : 0,
    account: g.accounts.join("+")
  }));

  const btcDayChg = S.q['BTC']?.change_pct || 0;
  document.getElementById('btcRatioTb').innerHTML = consolidatedBtc.map(h=>{
    const q = gq(h.ticker);
    const price = q.price;
    if(!price || !btcP) return '';
    // Sats per share = (stock USD / BTC USD) * 100M
    const satsNow = Math.round((price/btcP)*100000000);
    // Day% in sats = stock day% - BTC day%
    const daySatsPct = (q.change_pct||0) - btcDayChg;
    const posValueBtc = (price*h.shares)/btcP;
    const fmt = n => n>1000000?(n/1000000).toFixed(2)+"M":n>1000?(n/1000).toFixed(1)+"K":n.toLocaleString();
    const gainedSats = daySatsPct >= 0;
    const verdictCls = gainedSats?"sg-a":"sg-t";
    const verdictTxt = gainedSats?"▲ GAINING SATS":"▼ LOSING SATS";

    return`<tr>
      <td><div class="tb">${h.ticker}</div><div class="tt">${h.type} · ${h.shares.toLocaleString()} sh</div></td>
      <td style="color:var(--yw);font-size:10px;">${h.account||"—"}</td>
      <td style="color:var(--btc)">${fmt(satsNow)} sats</td>
      <td class="${gainedSats?"pos":"neg"}">${daySatsPct>=0?"+":""}${daySatsPct.toFixed(2)}%</td>
      <td style="color:var(--btc)">₿ ${posValueBtc.toFixed(4)}</td>
      <td><span class="sg ${verdictCls}">${verdictTxt}</span></td>
    </tr>`;
  }).join('');

  // Render Binance wallet section
  renderBinanceWallet();
}

// ─── BINANCE WALLET RENDER ──────────────────────────────────────────────────
function renderBinanceWallet(){
  const btcP = getBtcPrice();
  const btcDayChg = S.q['BTC']?.change_pct || 0;

  // Compute totals
  let totalValue = btcHold.binance * btcP;  // BTC portion
  let totalCost = 0;
  let positionsValue = 0;
  binancePos.forEach(p=>{
    const q = S.q[p.ticker] || {price:p.avg_cost,change_pct:0};
    const val = q.price * p.shares;
    positionsValue += val;
    totalValue += val;
    totalCost += p.avg_cost * p.shares;
  });
  totalCost += btcHold.binance * btcP; // BTC bought at current price (treated as 0 PnL for BTC portion)
  const totalBtcEquiv = btcP ? totalValue / btcP : 0;

  // Today's weighted % change vs BTC
  let weightedStockChg = 0;
  let totalPosValue = 0;
  binancePos.forEach(p=>{
    const q = S.q[p.ticker] || {price:p.avg_cost,change_pct:0};
    const val = q.price * p.shares;
    if(val > 0){
      weightedStockChg += (q.change_pct||0) * val;
      totalPosValue += val;
    }
  });
  const avgStockChg = totalPosValue > 0 ? weightedStockChg / totalPosValue : 0;
  const wsDayVsBtc = avgStockChg - btcDayChg;

  // Summary cards
  document.getElementById('bnbSummary').innerHTML = `
    <div style="text-align:center;padding:12px;background:var(--s2);border-radius:8px;">
      <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:1px;">TOTAL VALUE</div>
      <div style="font-family:'DM Mono',monospace;font-size:18px;color:var(--tx);margin-top:4px;">$${totalValue.toLocaleString('en-US',{maximumFractionDigits:0})}</div>
      <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--btc);margin-top:2px;">₿ ${totalBtcEquiv.toFixed(4)}</div>
    </div>
    <div style="text-align:center;padding:12px;background:var(--s2);border-radius:8px;">
      <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:1px;">BTC HOLDING</div>
      <div style="font-family:'DM Mono',monospace;font-size:18px;color:var(--btc);margin-top:4px;">${btcHold.binance.toFixed(4)} BTC</div>
      <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);margin-top:2px;">$${(btcHold.binance*btcP).toLocaleString('en-US',{maximumFractionDigits:0})}</div>
    </div>
    <div style="text-align:center;padding:12px;background:var(--s2);border-radius:8px;">
      <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:1px;">STOCKS VALUE</div>
      <div style="font-family:'DM Mono',monospace;font-size:18px;color:var(--ac);margin-top:4px;">$${positionsValue.toLocaleString('en-US',{maximumFractionDigits:0})}</div>
      <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);margin-top:2px;">${binancePos.length} position${binancePos.length===1?'':'s'}</div>
    </div>
    <div style="text-align:center;padding:12px;background:var(--s2);border-radius:8px;">
      <div style="font-family:'DM Mono',monospace;font-size:9px;color:var(--t3);letter-spacing:1px;">STOCKS vs BTC TODAY</div>
      <div style="font-family:'DM Mono',monospace;font-size:18px;margin-top:4px;" class="${wsDayVsBtc>=0?'pos':'neg'}">${wsDayVsBtc>=0?'+':''}${wsDayVsBtc.toFixed(2)}%</div>
      <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);margin-top:2px;">${wsDayVsBtc>=0?'GAINING':'LOSING'} SATS</div>
    </div>`;

  // Positions table
  if(binancePos.length === 0){
    document.getElementById('bnbTb').innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--t3);padding:24px;">No Binance positions yet. Click "+ ADD POSITION" above.</td></tr>`;
    return;
  }
  document.getElementById('bnbTb').innerHTML = binancePos.map(p=>{
    const q = S.q[p.ticker] || {price:p.avg_cost,change_pct:0};
    const val = q.price * p.shares;
    const pl = (q.price - p.avg_cost) * p.shares;
    const plp = p.avg_cost ? (q.price - p.avg_cost)/p.avg_cost*100 : 0;
    const valBtc = btcP ? val/btcP : 0;
    const dayVsBtc = (q.change_pct||0) - btcDayChg;
    return `<tr id="bnb_${p.id}">
      <td><div class="tb">${p.ticker}</div></td>
      <td>${p.shares.toLocaleString()}</td>
      <td>$${p.avg_cost.toFixed(2)}</td>
      <td>$${q.price.toFixed(2)}</td>
      <td>$${val.toLocaleString('en-US',{maximumFractionDigits:0})}</td>
      <td style="color:var(--btc)">₿ ${valBtc.toFixed(4)}</td>
      <td class="${pl>=0?'pos':'neg'}">${pl>=0?'+':''}$${Math.abs(pl).toLocaleString('en-US',{maximumFractionDigits:0})} (${plp.toFixed(1)}%)</td>
      <td class="${dayVsBtc>=0?'pos':'neg'}">${dayVsBtc>=0?'+':''}${dayVsBtc.toFixed(2)}%</td>
      <td style="color:var(--t3);font-size:10px;max-width:140px;white-space:normal;text-align:left;">${p.notes||'—'}</td>
      <td><div style="display:flex;gap:4px;justify-content:flex-end;">
        <button class="bts" onclick="editBnbPos(${p.id})">EDIT</button>
        <button class="bts btd" onclick="delBnbPos(${p.id})">DEL</button>
      </div></td>
    </tr>`;
  }).join('');
}

// ─── STATUS ──────────────────────────────────────────────────────────────────
function renderStatus(st){
  document.getElementById("sstatus").innerHTML=`
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:12px;">
      <div style="font-family:'DM Mono',monospace;font-size:11px;"><span class="sdot ${st.api_key_set?"sok":"sno"}"></span>ANTHROPIC — ${st.api_key_set?'<span style="color:var(--gr)">✓ SET</span>':'<span style="color:var(--rd)">NOT SET</span>'}</div>
      <div style="font-family:'DM Mono',monospace;font-size:11px;"><span class="sdot sok"></span>QUOTES — <span style="color:var(--gr)">YAHOO FINANCE LIVE</span></div>
      <div style="font-family:'DM Mono',monospace;font-size:11px;"><span class="sdot sok"></span>BTC — <span style="color:var(--gr)">LIVE PRICE</span></div>
    </div>
    <div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);">
      Holdings: ${st.holdings_count} | Watchlist: ${st.watchlist_count} | Margin: $${st.margin.toLocaleString()}
    </div>`;
}

function renderATickers(){
  document.getElementById("aticks").innerHTML=S.h.map(h=>`<div class="tpil ${S.sel===h.ticker?"on":""}" onclick="selT('${h.ticker}')">${h.ticker} <span style="font-size:9px;opacity:0.6;">${h.account||""}</span></div>`).join("");
}

function updateWBadge(){
  const n=S.w.filter(w=>{const q=gq(w.ticker);return w.target_price&&q.price<=w.target_price*1.02;}).length;
  const b=document.getElementById("wbdg");b.textContent=n;b.style.display=n?"inline":"none";
}

// ─── HOLDINGS CRUD ────────────────────────────────────────────────────────────
async function addH(){
  const ti=document.getElementById("nti").value.toUpperCase().trim();
  const sh=parseFloat(document.getElementById("nsh").value);
  const co=parseFloat(document.getElementById("nco").value);
  const ac=document.getElementById("nac").value.trim()||"MMG";
  const ty=document.getElementById("nty").value.trim()||"position";
  const no=document.getElementById("nno").value.trim();
  if(!ti||!sh||!co){toast("Ticker, shares and avg cost required","err");return;}
  try{const h=await api("POST","/holdings",{ticker:ti,shares:sh,avg_cost:co,account:ac,type:ty,notes:no});S.h.push(h);tog("ahf");["nti","nsh","nco","nac","nty","nno"].forEach(id=>document.getElementById(id).value="");await loadAll();toast(`${ti} added`);}
  catch(e){toast(e.message,"err");}
}

// ── EDIT-STATE GUARD ──────────────────────────────────────────────────────────
// Auto-refresh calls renderAll(), which rebuilds table rows from scratch. If an
// edit form is open, that silently destroys whatever the user has typed. We track
// open editors and skip the re-render (but still update prices) while any is open.
const EditState = {
  open: new Set(),
  begin(key){ this.open.add(key); },
  end(key){ this.open.delete(key); },
  get active(){ return this.open.size > 0; }
};

function editH(id){
  const h=S.h.find(x=>x.id===id);if(!h)return;
  EditState.begin('holding:'+id);
  document.getElementById(`hr${id}`).innerHTML=`
    <td><span class="tb">${h.ticker}</span></td>
    <td style="color:var(--yw);font-size:10px;">${h.account||"—"}</td>
    <td colspan="6"><div class="ep">
      <div class="eg"><div class="egl">TOTAL SHARES</div><input class="ied" id="es${id}" value="${h.shares}" type="number" step="1" style="width:95px;"></div>
      <div class="eg"><div class="egl">AVG COST $</div><input class="ied" id="ec${id}" value="${h.avg_cost}" type="number" step="0.01" style="width:95px;"></div>
      <div style="width:1px;background:var(--b1);align-self:stretch;margin:0 4px;"></div>
      <div class="eg"><div class="egl">+ ADD (qty / price $)</div><div style="display:flex;gap:5px;">
        <input class="ied" id="ea${id}" placeholder="qty" type="number" style="width:60px;">
        <input class="ied" id="ep${id}" placeholder="price" type="number" step="0.01" style="width:75px;">
        <button class="btg" onclick="qadd(${id})" style="font-size:10px;padding:4px 8px;">ADD</button>
      </div></div>
      <div class="eg"><div class="egl">− REDUCE (qty)</div><div style="display:flex;gap:5px;">
        <input class="ied" id="er${id}" placeholder="qty" type="number" style="width:65px;">
        <button onclick="qred(${id})" style="background:none;border:1px solid var(--rd);color:var(--rd);padding:4px 8px;border-radius:4px;font-family:'DM Mono',monospace;font-size:10px;cursor:pointer;">REDUCE</button>
      </div></div>
    </div></td>
    <td><div style="display:flex;gap:5px;justify-content:flex-end;">
      <button class="btg" onclick="saveH(${id})">SAVE</button>
      <button class="bts" onclick="EditState.end('holding:${id}');renderHoldings()">CANCEL</button>
    </div></td>`;
}

function qadd(id){
  const qty=parseFloat(document.getElementById(`ea${id}`).value);
  const price=parseFloat(document.getElementById(`ep${id}`).value);
  if(!qty||qty<=0){toast("Enter shares to add","err");return;}
  if(!price||price<=0){toast("Enter purchase price","err");return;}
  const curS=parseFloat(document.getElementById(`es${id}`).value);
  const curC=parseFloat(document.getElementById(`ec${id}`).value);
  const newS=curS+qty; const newC=((curS*curC)+(qty*price))/newS;
  document.getElementById(`es${id}`).value=newS;
  document.getElementById(`ec${id}`).value=newC.toFixed(2);
  document.getElementById(`ea${id}`).value=""; document.getElementById(`ep${id}`).value="";
  toast(`Added ${qty} shares — new avg $${newC.toFixed(2)}`);
}

function qred(id){
  const cur=parseFloat(document.getElementById(`es${id}`).value);
  const qty=parseFloat(document.getElementById(`er${id}`).value);
  if(!qty||qty<=0){toast("Enter qty","err");return;}
  if(qty>=cur){toast("Cannot reduce to zero — use DEL","err");return;}
  document.getElementById(`es${id}`).value=cur-qty;
  document.getElementById(`er${id}`).value="";
  toast(`Reduced by ${qty} — ${cur-qty} remaining`);
}

async function saveH(id){
  EditState.end('holding:'+id);
  const h=S.h.find(x=>x.id===id);
  const shares=parseFloat(document.getElementById(`es${id}`).value);
  const avg_cost=parseFloat(document.getElementById(`ec${id}`).value);
  if(!shares||shares<=0){toast("Shares > 0","err");return;}
  try{await api("PUT",`/holdings/${id}`,{shares,avg_cost,notes:h.notes,account:h.account||"MMG"});await loadAll();toast(`${h.ticker} updated`);}
  catch(e){toast(e.message,"err");}
}

async function delH(id,ticker){
  if(!confirm(`Remove ${ticker}?`))return;
  try{await api("DELETE",`/holdings/${id}`);await loadAll();toast(`${ticker} removed`);}
  catch(e){toast(e.message,"err");}
}

// ─── WATCHLIST CRUD ───────────────────────────────────────────────────────────
async function addW(){
  const ti=document.getElementById("wti").value.toUpperCase().trim();
  const tp=parseFloat(document.getElementById("wtp").value)||null;
  const no=document.getElementById("wno").value.trim();
  if(!ti){toast("Enter a ticker","err");return;}
  try{const w=await api("POST","/watchlist",{ticker:ti,target_price:tp,notes:no});S.w.push(w);["wti","wtp","wno"].forEach(id=>document.getElementById(id).value="");await loadAll();toast(`${ti} added`);}
  catch(e){toast(e.message,"err");}
}

async function delW(id){
  try{await api("DELETE",`/watchlist/${id}`);S.w=S.w.filter(w=>w.id!==id);renderWatchlist();updateWBadge();toast("Removed");}
  catch(e){toast(e.message,"err");}
}

// ─── AI ANALYSIS ─────────────────────────────────────────────────────────────
function selT(t){S.sel=t;renderATickers();}

async function anaPos(){
  if(!S.sel){toast("Select a position","err");return;}
  const out=document.getElementById("aout"),btn=document.getElementById("abtn");
  btn.disabled=true;
  out.innerHTML=`<div class="ld">Analyzing ${S.sel}<span>.</span><span>.</span><span>.</span></div>`;
  try{
    const r=await api("POST","/analyze/position",{ticker:S.sel});
    const h=S.h.find(x=>x.ticker===S.sel)||{};
    const sig=(h.signal&&h.signal.signal)?h.signal:{signal:"HOLD"};
    out.innerHTML=`<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--b1);">
      <span class="tb" style="font-size:18px;">${S.sel}</span>
      <span class="sg ${sgc(sig.signal)}">${sig.signal}</span>
      <span style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);">${new Date().toLocaleDateString()}</span>
    </div><div class="aitx">${r.analysis}</div>`;
  }catch(e){
    out.innerHTML=`<div style="color:var(--rd);font-family:'DM Mono',monospace;font-size:11px;padding:14px;border:1px solid var(--rd);border-radius:8px;">Error: ${e.message}<br><small style="color:var(--t3)">Check ANTHROPIC_API_KEY in Railway Variables</small></div>`;
  }
  btn.disabled=false;
}

async function anaPort(){
  const out=document.getElementById("aout");
  out.innerHTML=`<div class="ld">Analyzing full portfolio<span>.</span><span>.</span><span>.</span></div>`;
  try{
    const r=await api("POST","/analyze/portfolio");
    out.innerHTML=`<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--b1);">
      <span style="font-family:'Bebas Neue',sans-serif;font-size:17px;color:var(--ac);letter-spacing:2px;">FULL PORTFOLIO ANALYSIS</span>
      <span style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);">${new Date().toLocaleDateString()}</span>
    </div><div class="aitx">${r.analysis}</div>`;
  }catch(e){out.innerHTML=`<div style="color:var(--rd);font-family:'DM Mono',monospace;font-size:11px;padding:14px;border:1px solid var(--rd);border-radius:8px;">Error: ${e.message}</div>`;}
}

// ─── DAILY BRIEF ─────────────────────────────────────────────────────────────
async function genBrief(){
  const out=document.getElementById("bout"),btn=document.getElementById("bbtn");
  document.getElementById("bdate").textContent=new Date().toLocaleDateString("en-US",{weekday:"long",year:"numeric",month:"long",day:"numeric"}).toUpperCase();
  btn.disabled=true;
  out.innerHTML=`<div class="ld">Generating brief<span>.</span><span>.</span><span>.</span></div>`;
  try{
    const r=await api("POST","/brief");
    out.innerHTML=`<div style="font-family:'DM Mono',monospace;font-size:10px;color:var(--t3);margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid var(--b1);">
      MORNING BRIEF — ${new Date().toLocaleDateString("en-US",{weekday:"long",year:"numeric",month:"long",day:"numeric"}).toUpperCase()}
    </div><div class="aitx">${r.brief}</div>`;
  }catch(e){out.innerHTML=`<div style="color:var(--rd);font-family:'DM Mono',monospace;font-size:11px;padding:14px;border:1px solid var(--rd);border-radius:8px;">Error: ${e.message}</div>`;}
  btn.disabled=false;
}

// ─── FLOATING CHAT ────────────────────────────────────────────────────────────
function togChat(){chatOpen=!chatOpen;document.getElementById("chatWin").classList.toggle("open",chatOpen);if(chatOpen)document.getElementById("chatInput").focus();}
function chatKey(e){if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendChat();}}
function addChatMsg(text,role){
  const msgs=document.getElementById("chatMsgs");
  const div=document.createElement("div");div.className=`cmsg ${role}`;div.textContent=text;
  msgs.appendChild(div);msgs.scrollTop=msgs.scrollHeight;return div;
}
async function sendChat(){
  const inp=document.getElementById("chatInput");const msg=inp.value.trim();if(!msg)return;
  inp.value="";document.getElementById("chatSend").disabled=true;
  addChatMsg(msg,"user");const typing=addChatMsg("...","ai");
  try{
    const r=await api("POST","/chat",{message:msg,history:chatHistory});
    typing.remove();addChatMsg(r.response,"ai");
    chatHistory.push({user:msg,assistant:r.response});
    if(chatHistory.length>20)chatHistory=chatHistory.slice(-20);
  }catch(e){typing.remove();addChatMsg("Error: "+e.message,"err");}
  document.getElementById("chatSend").disabled=false;inp.focus();
}

// ─── UTILS ───────────────────────────────────────────────────────────────────
function sw(n,el){
  document.querySelectorAll(".tc").forEach(t=>t.classList.remove("on"));
  document.querySelectorAll(".tab").forEach(t=>t.classList.remove("on"));
  document.getElementById(`tc-${n}`).classList.add("on");el.classList.add("on");
}
function toast(msg,type="ok"){
  const t=document.createElement("div");t.className="toast";
  t.style.borderColor=type==="err"?"var(--rd)":"var(--gr)";
  t.style.color=type==="err"?"var(--rd)":"var(--gr)";
  t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.remove(),4000);
}

// ─── INIT ────────────────────────────────────────────────────────────────────
// Fetch fundamentals first (single source of truth), then load everything.
loadFundamentals().then(loadAll);

// ── AUTO-REFRESH ──────────────────────────────────────────────────────────────
// Quotes refresh every 60s while the tab is visible.
const REFRESH_MS = 60000;
setInterval(()=>{ if(!document.hidden) loadAll({silent:true}); }, REFRESH_MS);
document.addEventListener('visibilitychange', ()=>{ if(!document.hidden) loadAll({silent:true}); });
</script></body></html>"""

@app.get("/")
async def root(): return HTMLResponse(content=FRONTEND)
@app.get("/{full_path:path}")
async def catch_all(full_path: str): return HTMLResponse(content=FRONTEND)

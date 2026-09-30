import io, os, time
import requests, pandas as pd, yfinance as yf
from flask import Flask, jsonify, request, Response

app = Flask(__name__)
ACCESS_KEY = os.environ.get("ACCESS_KEY", "")  # optional password for personal use
UA = {"User-Agent": "Mozilla/5.0"}
# --- Built-in stock lists -------------------------------------------------
# niftyindices.com / nseindia.com block requests from cloud servers (Render,
# AWS, etc.) with a 403, even with browser-like headers. To keep this app
# working reliably, the index/sector lists are bundled here instead of being
# fetched live. Composition changes a few times a year - see the note in the
# chat reply for how to refresh this list later.
# Format: symbol -> (Company Name, Industry)

_NIFTY50 = {
 "RELIANCE":("Reliance Industries","Energy"),"TCS":("Tata Consultancy Services","IT"),
 "HDFCBANK":("HDFC Bank","Financial Services"),"ICICIBANK":("ICICI Bank","Financial Services"),
 "INFY":("Infosys","IT"),"BHARTIARTL":("Bharti Airtel","Telecom"),"ITC":("ITC","FMCG"),
 "SBIN":("State Bank of India","Financial Services"),"LT":("Larsen & Toubro","Construction"),
 "HINDUNILVR":("Hindustan Unilever","FMCG"),"KOTAKBANK":("Kotak Mahindra Bank","Financial Services"),
 "BAJFINANCE":("Bajaj Finance","Financial Services"),"AXISBANK":("Axis Bank","Financial Services"),
 "M&M":("Mahindra & Mahindra","Auto"),"MARUTI":("Maruti Suzuki","Auto"),
 "SUNPHARMA":("Sun Pharmaceutical","Pharma"),"HCLTECH":("HCL Technologies","IT"),
 "ULTRACEMCO":("UltraTech Cement","Cement"),"TITAN":("Titan Company","Consumer Durables"),
 "NTPC":("NTPC","Power"),"TATAMOTORS":("Tata Motors","Auto"),
 "BAJAJFINSV":("Bajaj Finserv","Financial Services"),"ONGC":("Oil & Natural Gas Corp","Energy"),
 "ADANIENT":("Adani Enterprises","Diversified"),"POWERGRID":("Power Grid Corp","Power"),
 "WIPRO":("Wipro","IT"),"NESTLEIND":("Nestle India","FMCG"),
 "ADANIPORTS":("Adani Ports & SEZ","Infrastructure"),"JSWSTEEL":("JSW Steel","Metal"),
 "COALINDIA":("Coal India","Mining"),"TATASTEEL":("Tata Steel","Metal"),
 "BEL":("Bharat Electronics","Capital Goods"),"GRASIM":("Grasim Industries","Cement"),
 "TRENT":("Trent","Retail"),"HINDALCO":("Hindalco Industries","Metal"),
 "TECHM":("Tech Mahindra","IT"),"SBILIFE":("SBI Life Insurance","Insurance"),
 "HDFCLIFE":("HDFC Life Insurance","Insurance"),"CIPLA":("Cipla","Pharma"),
 "BAJAJ-AUTO":("Bajaj Auto","Auto"),"EICHERMOT":("Eicher Motors","Auto"),
 "DRREDDY":("Dr Reddy's Laboratories","Pharma"),"APOLLOHOSP":("Apollo Hospitals","Healthcare"),
 "HEROMOTOCO":("Hero MotoCorp","Auto"),"INDUSINDBK":("IndusInd Bank","Financial Services"),
 "SHRIRAMFIN":("Shriram Finance","Financial Services"),"TATACONSUM":("Tata Consumer Products","FMCG"),
 "BPCL":("Bharat Petroleum","Energy"),"LTIM":("LTIMindtree","IT"),
 "ASIANPAINT":("Asian Paints","Consumer Durables"),"BRITANNIA":("Britannia Industries","FMCG"),
}
_NEXT50 = {
 "ABB":("ABB India","Capital Goods"),"ADANIENSOL":("Adani Energy Solutions","Power"),
 "ADANIGREEN":("Adani Green Energy","Power"),"ADANIPOWER":("Adani Power","Power"),
 "AMBUJACEM":("Ambuja Cements","Cement"),"BAJAJHLDNG":("Bajaj Holdings","Financial Services"),
 "BANKBARODA":("Bank of Baroda","Financial Services"),"BERGEPAINT":("Berger Paints","Consumer Durables"),
 "BOSCHLTD":("Bosch","Auto"),"CHOLAFIN":("Cholamandalam Investment","Financial Services"),
 "COLPAL":("Colgate-Palmolive India","FMCG"),"DLF":("DLF","Realty"),
 "DABUR":("Dabur India","FMCG"),"DIVISLAB":("Divi's Laboratories","Pharma"),
 "GAIL":("GAIL India","Energy"),"GODREJCP":("Godrej Consumer Products","FMCG"),
 "HAL":("Hindustan Aeronautics","Capital Goods"),"HINDZINC":("Hindustan Zinc","Metal"),
 "ICICIGI":("ICICI Lombard General Insurance","Insurance"),"ICICIPRULI":("ICICI Prudential Life","Insurance"),
 "INDHOTEL":("Indian Hotels Company","Hospitality"),"IOC":("Indian Oil Corp","Energy"),
 "INDUSTOWER":("Indus Towers","Telecom"),"INDIGO":("InterGlobe Aviation","Aviation"),
 "JINDALSTEL":("Jindal Steel & Power","Metal"),"JSWENERGY":("JSW Energy","Power"),
 "LICI":("Life Insurance Corp of India","Insurance"),"MARICO":("Marico","FMCG"),
 "MOTHERSON":("Samvardhana Motherson","Auto"),"MUTHOOTFIN":("Muthoot Finance","Financial Services"),
 "PIDILITIND":("Pidilite Industries","Chemicals"),"PIIND":("PI Industries","Chemicals"),
 "PFC":("Power Finance Corp","Financial Services"),"RECLTD":("REC Limited","Financial Services"),
 "SRF":("SRF","Chemicals"),"SIEMENS":("Siemens","Capital Goods"),
 "TATAPOWER":("Tata Power","Power"),"TVSMOTOR":("TVS Motor Company","Auto"),
 "UNITDSPR":("United Spirits","FMCG"),"VEDL":("Vedanta","Metal"),
 "ZOMATO":("Eternal (Zomato)","Retail"),"ZYDUSLIFE":("Zydus Lifesciences","Pharma"),
}
_BANK = {k:_NIFTY50.get(k) or _NEXT50.get(k) or v for k,v in {
 "HDFCBANK":0,"ICICIBANK":0,"SBIN":0,"KOTAKBANK":0,"AXISBANK":0,"INDUSINDBK":0,"BANKBARODA":0,
 "PNB":("Punjab National Bank","Financial Services"),"AUBANK":("AU Small Finance Bank","Financial Services"),
 "IDFCFIRSTB":("IDFC First Bank","Financial Services"),"FEDERALBNK":("Federal Bank","Financial Services"),
 "CANBK":("Canara Bank","Financial Services"),
}.items()}
_IT = {k:_NIFTY50.get(k) or v for k,v in {
 "TCS":0,"INFY":0,"HCLTECH":0,"WIPRO":0,"TECHM":0,"LTIM":0,
 "PERSISTENT":("Persistent Systems","IT"),"COFORGE":("Coforge","IT"),
 "MPHASIS":("Mphasis","IT"),"LTTS":("L&T Technology Services","IT"),
}.items()}
_AUTO = {k:_NIFTY50.get(k) or _NEXT50.get(k) or v for k,v in {
 "MARUTI":0,"M&M":0,"TATAMOTORS":0,"BAJAJ-AUTO":0,"EICHERMOT":0,"HEROMOTOCO":0,"TVSMOTOR":0,
 "BOSCHLTD":0,"MOTHERSON":0,
 "ASHOKLEY":("Ashok Leyland","Auto"),"BHARATFORG":("Bharat Forge","Auto"),
 "BALKRISIND":("Balkrishna Industries","Auto"),"MRF":("MRF","Auto"),
 "EXIDEIND":("Exide Industries","Auto"),"TIINDIA":("Tube Investments of India","Auto"),
}.items()}
_PHARMA = {k:_NIFTY50.get(k) or _NEXT50.get(k) or v for k,v in {
 "SUNPHARMA":0,"CIPLA":0,"DRREDDY":0,"DIVISLAB":0,"ZYDUSLIFE":0,
 "TORNTPHARM":("Torrent Pharmaceuticals","Pharma"),"LUPIN":("Lupin","Pharma"),
 "AUROPHARMA":("Aurobindo Pharma","Pharma"),"ALKEM":("Alkem Laboratories","Pharma"),
 "MANKIND":("Mankind Pharma","Pharma"),"GLENMARK":("Glenmark Pharmaceuticals","Pharma"),
 "ABBOTINDIA":("Abbott India","Pharma"),"IPCALAB":("IPCA Laboratories","Pharma"),
 "LAURUSLABS":("Laurus Labs","Pharma"),"BIOCON":("Biocon","Pharma"),
}.items()}
_FMCG = {k:_NIFTY50.get(k) or _NEXT50.get(k) or v for k,v in {
 "HINDUNILVR":0,"ITC":0,"NESTLEIND":0,"TATACONSUM":0,"BRITANNIA":0,"DABUR":0,"GODREJCP":0,
 "MARICO":0,"COLPAL":0,"UNITDSPR":0,
 "VBL":("Varun Beverages","FMCG"),"UBL":("United Breweries","FMCG"),
 "EMAMILTD":("Emami","FMCG"),"RADICO":("Radico Khaitan","FMCG"),
}.items()}
_METAL = {k:_NIFTY50.get(k) or _NEXT50.get(k) or v for k,v in {
 "TATASTEEL":0,"JSWSTEEL":0,"HINDALCO":0,"VEDL":0,"JINDALSTEL":0,"HINDZINC":0,"COALINDIA":0,
 "SAIL":("Steel Authority of India","Metal"),"NMDC":("NMDC","Mining"),
 "NATIONALUM":("National Aluminium Company","Metal"),"APLAPOLLO":("APL Apollo Tubes","Metal"),
 "RATNAMANI":("Ratnamani Metals & Tubes","Metal"),"HINDCOPPER":("Hindustan Copper","Metal"),
}.items()}
_ENERGY = {k:_NIFTY50.get(k) or _NEXT50.get(k) or v for k,v in {
 "RELIANCE":0,"ONGC":0,"NTPC":0,"POWERGRID":0,"COALINDIA":0,"BPCL":0,"IOC":0,"GAIL":0,
 "TATAPOWER":0,"ADANIGREEN":0,
}.items()}
_REALTY = {k:_NEXT50.get(k) or v for k,v in {
 "DLF":0,
 "GODREJPROP":("Godrej Properties","Realty"),"OBEROIRLTY":("Oberoi Realty","Realty"),
 "PRESTIGE":("Prestige Estates Projects","Realty"),"PHOENIXLTD":("Phoenix Mills","Realty"),
 "LODHA":("Macrotech Developers","Realty"),"BRIGADE":("Brigade Enterprises","Realty"),
 "SOBHA":("Sobha","Realty"),"SUNTECK":("Sunteck Realty","Realty"),
 "IBREALEST":("Indiabulls Real Estate","Realty"),
}.items()}

_SENSEX30 = {k:_NIFTY50.get(k) or v for k,v in {
 "RELIANCE":0,"TCS":0,"HDFCBANK":0,"ICICIBANK":0,"INFY":0,"BHARTIARTL":0,"ITC":0,"SBIN":0,
 "LT":0,"HINDUNILVR":0,"KOTAKBANK":0,"BAJFINANCE":0,"AXISBANK":0,"M&M":0,"MARUTI":0,
 "SUNPHARMA":0,"HCLTECH":0,"ULTRACEMCO":0,"TITAN":0,"NTPC":0,"TATAMOTORS":0,"BAJAJFINSV":0,
 "POWERGRID":0,"ADANIPORTS":0,"JSWSTEEL":0,"TATASTEEL":0,"TECHM":0,"ASIANPAINT":0,
 "INDUSINDBK":0,
}.items()}

GROUPS = {
    "Nifty 50 (Large cap)": _NIFTY50, "Nifty Next 50": _NEXT50,
    "Nifty Bank": _BANK, "Nifty IT": _IT, "Nifty Auto": _AUTO,
    "Nifty Pharma": _PHARMA, "Nifty FMCG": _FMCG, "Nifty Metal": _METAL,
    "Nifty Energy": _ENERGY, "Nifty Realty": _REALTY,
    "Sensex 30 (Large cap)": _SENSEX30,
}
CUSTOM_LABEL = "Custom (paste your own symbols)"
NIFTY500_LABEL = "Nifty 500 (paste once, saved in your browser)"
PASTE_GROUPS = {CUSTOM_LABEL, NIFTY500_LABEL}
TF = {"15m": ("15m", "30d"), "1h": ("1h", "6mo"), "4h": ("1h", "6mo"), "1d": ("1d", "2y")}
_cache = {}


def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


def load_group(name):
    d = GROUPS[name]
    rows = [(nm, ind, sym) for sym, (nm, ind) in d.items()]
    return pd.DataFrame(rows, columns=["Company Name", "Industry", "Symbol"])


def analyze(d, n):
    """Swing-pivot market structure. BOS = close beyond last swing in trend direction
    (sets a protected level). CHoCH = close beyond that protected level (trend flips)."""
    h, l, c = d["High"].values, d["Low"].values, d["Close"].values
    idx = d.index
    lastH = lastL = None
    trend, prot, bos_bar, ev = 0, None, None, None
    for t in range(len(c)):
        p = t - n
        if p >= n:
            if h[p] == max(h[p - n:p + n + 1]): lastH = (h[p], p)
            if l[p] == min(l[p - n:p + n + 1]): lastL = (l[p], p)
        if trend >= 0 and lastH and c[t] > lastH[0]:      # bullish BOS
            trend, bos_bar = 1, t
            prot = lastL[0] if lastL else None
            lastH = None
        elif trend <= 0 and lastL and c[t] < lastL[0]:    # bearish BOS
            trend, bos_bar = -1, t
            prot = lastH[0] if lastH else None
            lastL = None
        elif trend == 1 and prot is not None and c[t] < prot and bos_bar is not None:
            ev = ("Bearish CHoCH", t, prot, bos_bar)
            trend, prot, lastL = -1, lastH[0] if lastH else None, None
        elif trend == -1 and prot is not None and c[t] > prot and bos_bar is not None:
            ev = ("Bullish CHoCH", t, prot, bos_bar)
            trend, prot, lastH = 1, lastL[0] if lastL else None, None
    if not ev:
        return None
    k, t, lvl, b = ev
    return dict(event=k, bars_ago=len(c) - 1 - t, level=round(float(lvl), 2),
                bos_ago=t - b, close=round(float(c[-1]), 2), time=str(idx[t])[:16])


def fetch(tickers, tf):
    interval, period = TF[tf]
    out = {}
    for i in range(0, len(tickers), 100):
        chunk = tickers[i:i + 100]
        try:
            data = yf.download(chunk, interval=interval, period=period, group_by="ticker",
                               auto_adjust=False, threads=True, progress=False)
        except Exception:
            continue
        # yfinance's column shape depends on the ACTUAL data returned, not on how many
        # tickers were requested (a chunk of 1 can still come back multi-indexed) - so we
        # check the real structure instead of assuming based on len(chunk).
        multi = isinstance(data.columns, pd.MultiIndex)
        for t in chunk:
            try:
                d = data[t] if multi else data
                d = d.dropna(subset=["Close"])
                if tf == "4h":
                    d = d.resample("4h").agg({"Open": "first", "High": "max", "Low": "min",
                                              "Close": "last"}).dropna()
                if len(d) > 30: out[t] = d
            except Exception:
                pass
    return out


@app.before_request
def guard():
    if ACCESS_KEY and request.path.startswith("/api") and request.headers.get("X-Key") != ACCESS_KEY:
        return jsonify(error="Wrong access key"), 401


@app.route("/api/meta")
def meta():
    gi = {g: sorted({v[1] for v in d.values()}) for g, d in GROUPS.items()}
    inds = sorted({v[1] for g in GROUPS.values() for v in g.values()})
    return jsonify(groups=list(GROUPS) + [NIFTY500_LABEL, CUSTOM_LABEL], industries=inds,
                   group_industries=gi, custom_label=CUSTOM_LABEL, nifty500_label=NIFTY500_LABEL)


@app.route("/api/scan")
def scan():
    a = request.args
    ex, grp, ind = a.get("exchange", "NSE"), a.get("group", "Nifty 50 (Large cap)"), a.get("industry", "")
    tf, want = a.get("tf", "1d"), a.get("type", "both")
    within, n = int(a.get("within", 3)), int(a.get("swing", 3))
    if grp in PASTE_GROUPS:
        raw = a.get("symbols", "")
        syms, names_, inds_ = [], [], []
        for line in raw.replace("\r", "").split("\n"):
            line = line.strip()
            if not line: continue
            parts = [p.strip() for p in (line.split("\t") if "\t" in line else line.split(","))]
            sym = parts[0].upper().strip()
            # strip common suffixes people accidentally paste (series/exchange tags)
            for bad in ("-EQ", "-BE", ".NS", ".BO"):
                if sym.endswith(bad): sym = sym[: -len(bad)]
            if not sym or sym in ("SYMBOL", "NSE SYMBOL"): continue
            syms.append(sym)
            names_.append(parts[1] if len(parts) > 1 and parts[1] else sym)
            inds_.append(parts[2] if len(parts) > 2 and parts[2] else "Custom")
        if not syms:
            return jsonify(error="Paste at least one symbol first."), 400
        u = pd.DataFrame({"Symbol": syms, "Company Name": names_, "Industry": inds_}).drop_duplicates("Symbol")
        if ind: u = u[u["Industry"] == ind]
    else:
        try:
            u = load_group(grp)
        except Exception as e:
            return jsonify(error=f"Could not load index list: {e}"), 502
        if ind: u = u[u["Industry"] == ind]
    sfx = ".NS" if ex == "NSE" else ".BO"
    names = {s + sfx: (nm, i) for s, nm, i in zip(u["Symbol"], u["Company Name"], u["Industry"])}
    key = f"scan:{ex}:{tf}:{hash(tuple(names))}"
    data = cached(key, 300, lambda: fetch(list(names), tf))
    rows = []
    for t, d in data.items():
        r = analyze(d, n)
        if not r or r["bars_ago"] > within: continue
        if want == "bull" and r["event"] != "Bullish CHoCH": continue
        if want == "bear" and r["event"] != "Bearish CHoCH": continue
        rows.append(dict(symbol=t.split(".")[0], name=names[t][0], industry=names[t][1], **r))
    rows.sort(key=lambda r: r["bars_ago"])
    return jsonify(rows=rows, scanned=len(data), total=len(names))


@app.route("/api/candles")
def candles():
    a = request.args
    sym, ex, tf = (a.get("symbol") or "").strip().upper(), a.get("exchange", "NSE"), a.get("tf", "1d")
    if not sym:
        return jsonify(error="Missing symbol."), 400
    sfx = ".NS" if ex == "NSE" else ".BO"
    ticker = sym + sfx
    key = f"cnd:{ticker}:{tf}"
    data = cached(key, 120, lambda: fetch([ticker], tf))
    d = data.get(ticker)
    if d is None or len(d) == 0:
        return jsonify(error="No price data available for this symbol/timeframe."), 404
    rows = [dict(time=int(pd.Timestamp(idx).timestamp()), open=round(float(o), 2), high=round(float(h), 2),
                 low=round(float(l), 2), close=round(float(c), 2))
            for idx, o, h, l, c in zip(d.index, d["Open"], d["High"], d["Low"], d["Close"])]
    return jsonify(candles=rows)


@app.route("/")
def home():
    return Response(PAGE, mimetype="text/html")


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CHoCH Screener</title><style>
:root{--bg:#000;--panel:#0a0a0a;--card:#111;--bd:#232323;--tx:#eef0e8;--mu:#8a8f86;--ac:#ff9f1c;--up:#1fc25a;--dn:#ff4d4d}
*{box-sizing:border-box}body{margin:0;font:14px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--tx);height:100vh;overflow:hidden}
.layout{display:flex;height:100vh}
.left{width:340px;min-width:280px;display:flex;flex-direction:column;border-right:1px solid var(--bd);background:var(--panel)}
.filters{padding:16px;border-bottom:1px solid var(--bd);overflow-y:auto;max-height:62vh}
.results{flex:1;padding:14px;overflow-y:auto;min-height:0}
.right{flex:1;display:flex;flex-direction:column;padding:16px;gap:12px;min-width:0}
h1{font-size:15px;margin:0 0 2px;letter-spacing:.3px}h1 span{color:var(--ac)}
.sub{color:var(--mu);margin:0 0 16px;font-size:11.5px}
.step{margin-bottom:14px;animation:fade .2s ease}
.hidden{display:none!important}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
label{display:block;font-size:11px;color:var(--mu);margin-bottom:4px;text-transform:uppercase;letter-spacing:.4px}
select,input,textarea{width:100%;padding:9px;border-radius:6px;border:1px solid var(--bd);background:#000;color:var(--tx);font-size:13.5px;font-family:inherit}
select:focus,input:focus,textarea:focus{outline:none;border-color:var(--ac)}
textarea{resize:vertical}
.row2{display:flex;gap:8px}.row2>div{flex:1}
button.primary{padding:10px;border:0;border-radius:6px;background:var(--ac);color:#000;font-weight:700;font-size:13.5px;cursor:pointer;width:100%;margin-top:4px}
button.primary:disabled{opacity:.45;cursor:default}
.hint{font-size:11px;color:var(--mu);margin:6px 0 0;line-height:1.5}
.hint a{color:var(--ac)}
#st{color:var(--mu);font-size:12px;margin-bottom:10px}
.rescard{border:1px solid var(--bd);border-radius:8px;padding:10px 11px;margin-bottom:8px;cursor:pointer;background:var(--card);transition:border-color .15s}
.rescard:hover{border-color:#3a3a3a}
.rescard.active{border-color:var(--ac);background:#161208}
.rc-top{display:flex;justify-content:space-between;align-items:baseline}
.rc-sym{font-weight:700;font-size:13.5px}
.rc-ago{color:var(--mu);font-size:11px}
.rc-name{color:var(--mu);font-size:11.5px;margin-top:2px}
.pill{display:inline-block;font-size:11px;font-weight:700;padding:1px 6px;border-radius:4px;margin-top:5px}
.pill.bull{color:var(--up);background:#0d2216}
.pill.bear{color:var(--dn);background:#2a1010}
.emptynote{color:var(--mu);font-size:12.5px;padding:20px 4px;text-align:center}
#infoCard{border:1px solid var(--bd);border-radius:10px;padding:14px;background:var(--card);display:none}
#infoCard.show{display:block}
.info-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:8px}
.info-grid div{background:#000;border:1px solid var(--bd);border-radius:6px;padding:8px 10px}
.info-grid .l{font-size:10.5px;color:var(--mu);text-transform:uppercase;letter-spacing:.3px}
.info-grid .v{font-size:15px;font-weight:700;margin-top:2px}
#chartWrap{flex:1;border:1px solid var(--bd);border-radius:10px;overflow:hidden;background:#000;min-height:0}
#chartPlaceholder{height:100%;display:flex;align-items:center;justify-content:center;color:var(--mu);font-size:13px;text-align:center;padding:20px}
.keyw{margin-top:10px}
</style></head><body>
<div class="layout">
  <div class="left">
    <div class="filters">
      <h1>CHo<span>CH</span> Screener</h1>
      <p class="sub">Structure-break scanner for NSE stocks</p>

      <div class="step" id="s_grp">
        <label>1. Segment / Index</label>
        <select id="grpSel"><option value="" disabled selected>Select segment</option></select>
      </div>

      <div class="step hidden" id="s_ind">
        <label>2. Sector / Industry</label>
        <select id="indSel"><option value="">All industries</option></select>
        <div id="custwrap" class="hidden">
          <textarea id="custom" rows="4" placeholder="RELIANCE, TCS, INFY ...&#10;or paste Symbol,Company Name,Industry rows"></textarea>
          <input id="customInd" placeholder="Industry filter (optional, only works if you pasted 3 columns)" style="margin-top:8px">
          <p class="hint" id="pasteHint"></p>
        </div>
      </div>

      <div class="step hidden" id="s_final">
        <label>3. Timeframe</label>
        <select id="tf"><option value="15m">15 min</option><option value="1h">1 hour</option><option value="4h">4 hour</option><option value="1d" selected>Daily</option></select>
        <div class="row2" style="margin-top:10px">
          <div><label>CHoCH type</label><select id="type"><option value="both">Both</option><option value="bull">Bullish</option><option value="bear">Bearish</option></select></div>
          <div><label>Within (candles)</label><input id="within" type="number" value="3" min="0" max="50"></div>
        </div>
        <div style="margin-top:10px"><label>Swing size (candles each side)</label><input id="swing" type="number" value="3" min="2" max="10"></div>
        <div class="keyw hidden" id="keyw"><label>Access key</label><input id="key" type="password"></div>
        <button class="primary" id="go">Scan</button>
      </div>
    </div>
    <div class="results">
      <div id="st"></div>
      <div id="resList"><p class="emptynote">Results will appear here after you scan.</p></div>
    </div>
  </div>

  <div class="right">
    <div id="infoCard"></div>
    <div id="chartWrap"><div id="chartPlaceholder">Select a stock from the results list to load its chart here.</div></div>
  </div>
</div>
<script>
const $=i=>document.getElementById(i);
const H=()=>({'X-Key':$('key').value||localStorage.k||''});
let META={groups:[],industries:[],group_industries:{},custom_label:'Custom',nifty500_label:'Nifty500'};
let LAST_ROWS=[];

fetch('/api/meta').then(r=>r.json()).then(m=>{
  META=m;
  m.groups.forEach(g=>{const o=document.createElement('option');o.textContent=g;o.value=g;$('grpSel').appendChild(o)});
}).catch(()=>{$('keyw').classList.remove('hidden')});
$('key').value=localStorage.k||'';

function show(id){$(id).classList.remove('hidden')}
function hide(id){$(id).classList.add('hidden')}
function resetFrom(step){
  if(step<=1){hide('s_ind')}
  if(step<=2){hide('s_final')}
  $('resList').innerHTML='<p class="emptynote">Results will appear here after you scan.</p>';
  $('st').textContent='';
  clearChart();
}

function pasteKey(g){return 'paste:'+g}

$('grpSel').onchange=()=>{
  const g=$('grpSel').value;
  resetFrom(1);show('s_ind');
  if(g===META.custom_label||g===META.nifty500_label){
    hide_ind_select();show('custwrap');show('s_final');
    $('custom').value=localStorage.getItem(pasteKey(g))||'';
    if(g===META.nifty500_label){
      $('pasteHint').innerHTML='Open <a href="https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv" target="_blank">this link</a> in your own browser (it blocks bots, not you), open the CSV in Excel, select the Symbol, Company Name and Industry columns, copy, and paste them above. Saved automatically in this browser — you only need to do this once.';
    }else{
      $('pasteHint').textContent='Paste symbols one per line or comma-separated. Optionally add ",Company Name,Industry" per line for sector filtering.';
    }
  }else{
    show_ind_select();hide('custwrap');
    $('indSel').innerHTML='<option value="">All industries</option>';
    (META.group_industries[g]||[]).forEach(v=>{const o=document.createElement('option');o.textContent=v;o.value=v;$('indSel').appendChild(o)});
    show('s_final');
  }
};
function hide_ind_select(){$('indSel').classList.add('hidden')}
function show_ind_select(){$('indSel').classList.remove('hidden')}

$('custom').oninput=()=>{
  const g=$('grpSel').value;
  if(g===META.custom_label||g===META.nifty500_label){localStorage.setItem(pasteKey(g),$('custom').value)}
  show('s_final');
};

function clearChart(){
  $('infoCard').classList.remove('show');$('infoCard').innerHTML='';
  $('chartWrap').innerHTML='<div id="chartPlaceholder">Select a stock from the results list to load its chart here.</div>';
  document.querySelectorAll('.rescard').forEach(r=>r.classList.remove('active'));
}

$('go').onclick=async()=>{
  localStorage.k=$('key').value;
  $('go').disabled=true;$('st').textContent='Scanning… first run can take up to a minute.';
  $('resList').innerHTML='';clearChart();
  const isPaste=($('grpSel').value===META.custom_label||$('grpSel').value===META.nifty500_label);
  const q=new URLSearchParams({exchange:'NSE',group:$('grpSel').value,
    industry:isPaste?$('customInd').value:$('indSel').value,
    tf:$('tf').value,type:$('type').value,within:$('within').value,swing:$('swing').value,symbols:$('custom').value});
  try{
    const r=await fetch('/api/scan?'+q,{headers:H()});const d=await r.json();
    if(d.error){$('st').textContent=d.error;if(r.status==401)show('keyw');}
    else{
      LAST_ROWS=d.rows;
      $('st').textContent=`${d.rows.length} match(es) · scanned ${d.scanned} of ${d.total} stocks`;
      if(!d.rows.length){$('resList').innerHTML='<p class="emptynote">No CHoCH found in this selection. Try a wider "within" window or a different timeframe.</p>'}
      else{
        $('resList').innerHTML=d.rows.map((x,i)=>{
          const bull=x.event.startsWith('Bull');
          return `<div class="rescard" data-i="${i}">
            <div class="rc-top"><span class="rc-sym">${x.symbol}</span><span class="rc-ago">${x.bars_ago} candle(s) ago</span></div>
            <div class="rc-name">${x.name} · ${x.industry}</div>
            <span class="pill ${bull?'bull':'bear'}">${x.event}</span>
          </div>`;
        }).join('');
        document.querySelectorAll('.rescard').forEach(el=>el.onclick=()=>selectRow(parseInt(el.dataset.i)));
      }
    }
  }catch(e){$('st').textContent='Request failed: '+e}
  $('go').disabled=false;
};

function selectRow(i){
  const x=LAST_ROWS[i];
  document.querySelectorAll('.rescard').forEach(r=>r.classList.remove('active'));
  document.querySelector(`.rescard[data-i="${i}"]`).classList.add('active');
  const bull=x.event.startsWith('Bull');
  $('infoCard').classList.add('show');
  $('infoCard').innerHTML=`
    <div style="display:flex;justify-content:space-between;align-items:baseline">
      <div style="font-size:16px;font-weight:700">${x.symbol} <span style="color:var(--mu);font-weight:400;font-size:12.5px">${x.name}</span></div>
      <span class="pill ${bull?'bull':'bear'}" style="font-size:12px">${x.event}</span>
    </div>
    <div class="info-grid">
      <div><div class="l">Last Close</div><div class="v">${x.close}</div></div>
      <div><div class="l">Broken Level</div><div class="v">${x.level}</div></div>
      <div><div class="l">Candles Ago</div><div class="v">${x.bars_ago}</div></div>
      <div><div class="l">BOS Before (candles)</div><div class="v">${x.bos_ago}</div></div>
      <div><div class="l">Event Bar Time</div><div class="v" style="font-size:12px">${x.time}</div></div>
      <div><div class="l">Industry</div><div class="v" style="font-size:12px">${x.industry}</div></div>
    </div>
    <p class="hint">Last Close is the most recent completed candle (Yahoo data, ~15 min delayed) — not a live tick. TradingView's free widget is not licensed to show NSE data on outside websites at all (confirmed directly from TradingView's own docs), so the chart below is drawn from the same price data your scan used, with the broken level marked as a dashed line — look for price crossing that line around the Event Bar Time. Use the link under the chart if you want to inspect the same stock on TradingView.com itself.</p>`;
  loadChart(x.symbol,'NSE',$('tf').value,x.level);
}

let CHART=null, SERIES=null;
function loadChart(symbol,exchange,tf,level){
  $('chartWrap').innerHTML='<div id="cchart" style="height:calc(100% - 26px);width:100%"></div><div style="text-align:right;padding:4px 6px"><a href="https://www.tradingview.com/chart/?symbol=NSE:'+encodeURIComponent(symbol)+'" target="_blank" style="color:var(--ac);font-size:11.5px;text-decoration:none">Inspect on TradingView.com ↗</a></div>';
  const el=$('cchart');
  function fail(msg){el.innerHTML='<div style="height:100%;display:flex;align-items:center;justify-content:center;color:var(--mu);font-size:13px;padding:20px;text-align:center">'+msg+'</div>'}
  function draw(){
    try{
      if(!window.LightweightCharts||typeof LightweightCharts.createChart!=='function'){fail('Chart library failed to load. Check your internet connection and reload.');return}
      CHART=LightweightCharts.createChart(el,{
        layout:{background:{color:'#000'},textColor:'#eef0e8'},
        grid:{vertLines:{color:'#181818'},horzLines:{color:'#181818'}},
        timeScale:{timeVisible:true,borderColor:'#232323'},
        rightPriceScale:{borderColor:'#232323'},
      });
      if(typeof CHART.addCandlestickSeries!=='function'){fail('Chart library version mismatch (addCandlestickSeries missing). Try a hard refresh (Ctrl/Cmd+Shift+R).');return}
      SERIES=CHART.addCandlestickSeries({upColor:'#1fc25a',downColor:'#ff4d4d',borderVisible:false,wickUpColor:'#1fc25a',wickDownColor:'#ff4d4d'});
      new ResizeObserver(()=>{try{CHART.applyOptions({width:el.clientWidth,height:el.clientHeight})}catch(e){}}).observe(el);
    }catch(e){fail('Chart failed to initialize: '+e);return}
    fetch('/api/candles?'+new URLSearchParams({symbol,exchange,tf}),{headers:H()}).then(r=>r.json()).then(d=>{
      if(d.error){fail(d.error);return}
      if(!d.candles||!d.candles.length){fail('No candle data returned for this symbol/timeframe.');return}
      try{
        SERIES.setData(d.candles);
        SERIES.createPriceLine({price:level,color:'#ff9f1c',lineWidth:2,lineStyle:2,axisLabelVisible:true,title:'Broken level'});
        CHART.timeScale().fitContent();
      }catch(e){fail('Chart failed to render: '+e)}
    }).catch(e=>fail('Data request failed: '+e));
  }
  if(window.LightweightCharts){draw();}
  else{
    const s=document.createElement('script');
    s.src='https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js';
    s.onload=draw;
    s.onerror=()=>fail('Could not load the charting library from the CDN. Check your internet connection.');
    document.body.appendChild(s);
  }
}
</script></body></html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

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

GROUPS = {
    "Nifty 50 (Large cap)": _NIFTY50, "Nifty Next 50": _NEXT50,
    "Nifty Bank": _BANK, "Nifty IT": _IT, "Nifty Auto": _AUTO,
    "Nifty Pharma": _PHARMA, "Nifty FMCG": _FMCG, "Nifty Metal": _METAL,
    "Nifty Energy": _ENERGY, "Nifty Realty": _REALTY,
}
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
        for t in chunk:
            try:
                d = data[t] if len(chunk) > 1 else data
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
    inds = sorted({v[1] for g in GROUPS.values() for v in g.values()})
    return jsonify(groups=list(GROUPS), industries=inds)


@app.route("/api/scan")
def scan():
    a = request.args
    ex, grp, ind = a.get("exchange", "NSE"), a.get("group", "Nifty 50 (Large cap)"), a.get("industry", "")
    tf, want = a.get("tf", "1d"), a.get("type", "both")
    within, n = int(a.get("within", 3)), int(a.get("swing", 3))
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


@app.route("/")
def home():
    return Response(PAGE, mimetype="text/html")


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CHoCH Screener</title><style>
:root{--bg:#f6f7f9;--card:#fff;--tx:#14181f;--mu:#667085;--bd:#e3e6eb;--ac:#2557d6;--up:#0a8f4d;--dn:#d02c3a}
@media(prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#181c24;--tx:#e8ebf0;--mu:#8b93a3;--bd:#272d38;--ac:#6b93ff;--up:#35c47a;--dn:#ff6b78}}
*{box-sizing:border-box}body{margin:0;font:15px system-ui,sans-serif;background:var(--bg);color:var(--tx)}
main{max-width:1100px;margin:0 auto;padding:20px 14px}h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mu);margin:0 0 16px;font-size:13px}
.panel{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px;display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}
label{display:block;font-size:12px;color:var(--mu);margin-bottom:4px}select,input{width:100%;padding:9px;border-radius:8px;border:1px solid var(--bd);background:var(--bg);color:var(--tx);font-size:14px}
button{padding:10px 18px;border:0;border-radius:8px;background:var(--ac);color:#fff;font-weight:600;font-size:15px;cursor:pointer;align-self:end}button:disabled{opacity:.6}
#st{margin:14px 2px;color:var(--mu);font-size:13px}.tw{overflow-x:auto;background:var(--card);border:1px solid var(--bd);border-radius:12px}
table{width:100%;border-collapse:collapse;min-width:720px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--bd);white-space:nowrap}th{font-size:12px;color:var(--mu);cursor:pointer}
.b{color:var(--up);font-weight:600}.s{color:var(--dn);font-weight:600}a{color:var(--ac);text-decoration:none}
</style></head><body><main>
<h1>CHoCH Screener &middot; NSE / BSE</h1><p class="sub">Finds stocks where price closed through the level protected by the latest BOS (change of character).</p>
<div class="panel">
<div><label>Exchange</label><select id="ex"><option>NSE</option><option>BSE</option></select></div>
<div><label>Segment / Index</label><select id="grp"></select></div>
<div><label>Sector / Industry</label><select id="ind"><option value="">All</option></select></div>
<div><label>Timeframe</label><select id="tf"><option value="15m">15 min</option><option value="1h">1 hour</option><option value="4h">4 hour</option><option value="1d" selected>Daily</option></select></div>
<div><label>CHoCH type</label><select id="type"><option value="both">Both</option><option value="bull">Bullish</option><option value="bear">Bearish</option></select></div>
<div><label>Within last (candles)</label><input id="within" type="number" value="3" min="0" max="50"></div>
<div><label>Swing size (candles each side)</label><input id="swing" type="number" value="3" min="2" max="10"></div>
<div id="keyw" style="display:none"><label>Access key</label><input id="key" type="password"></div>
<button id="go">Scan</button></div>
<div id="st"></div><div class="tw"><table><thead><tr><th>Symbol</th><th>Company</th><th>Industry</th><th>Signal</th><th>Candles ago</th><th>Broken level</th><th>Close</th><th>BOS before (candles)</th><th>Chart</th></tr></thead><tbody id="tb"></tbody></table></div>
</main><script>
const $=i=>document.getElementById(i);const H=()=>({'X-Key':$('key').value||localStorage.k||''});
function fill(sel,arr){arr.forEach(v=>{const o=document.createElement('option');o.textContent=v;o.value=v;$(sel).appendChild(o)})}
fetch('/api/meta').then(r=>r.json()).then(m=>{fill('grp',m.groups);fill('ind',m.industries)}).catch(()=>{$('keyw').style.display='block'});
$('key').value=localStorage.k||'';
$('go').onclick=async()=>{localStorage.k=$('key').value;$('go').disabled=true;$('st').textContent='Scanning… first run can take up to a minute.';$('tb').innerHTML='';
const q=new URLSearchParams({exchange:$('ex').value,group:$('grp').value,industry:$('ind').value,tf:$('tf').value,type:$('type').value,within:$('within').value,swing:$('swing').value});
try{const r=await fetch('/api/scan?'+q,{headers:H()});const d=await r.json();
if(d.error){$('st').textContent=d.error;if(r.status==401)$('keyw').style.display='block';}
else{$('st').textContent=`${d.rows.length} match(es) · scanned ${d.scanned} of ${d.total} stocks`;
$('tb').innerHTML=d.rows.map(x=>`<tr><td><b>${x.symbol}</b></td><td>${x.name}</td><td>${x.industry}</td><td class="${x.event[0]=='B'&&x.event.startsWith('Bull')?'b':'s'}">${x.event}</td><td>${x.bars_ago}</td><td>${x.level}</td><td>${x.close}</td><td>${x.bos_ago}</td><td><a target="_blank" href="https://www.tradingview.com/chart/?symbol=${$('ex').value}:${x.symbol}">Open</a></td></tr>`).join('')}}
catch(e){$('st').textContent='Request failed: '+e}$('go').disabled=false};
</script></body></html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

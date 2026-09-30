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
    "Sensex 30 (BSE)": _SENSEX30,
}
CUSTOM_LABEL = "Custom (paste your own symbols)"
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
    gi = {g: sorted({v[1] for v in d.values()}) for g, d in GROUPS.items()}
    inds = sorted({v[1] for g in GROUPS.values() for v in g.values()})
    return jsonify(groups=list(GROUPS) + [CUSTOM_LABEL], industries=inds,
                   group_industries=gi, custom_label=CUSTOM_LABEL)


@app.route("/api/scan")
def scan():
    a = request.args
    ex, grp, ind = a.get("exchange", "NSE"), a.get("group", "Nifty 50 (Large cap)"), a.get("industry", "")
    tf, want = a.get("tf", "1d"), a.get("type", "both")
    within, n = int(a.get("within", 3)), int(a.get("swing", 3))
    if grp == CUSTOM_LABEL:
        raw = a.get("symbols", "")
        syms = sorted({s.strip().upper() for s in raw.replace(",", "\n").split("\n") if s.strip()})
        if not syms:
            return jsonify(error="Paste at least one symbol first."), 400
        u = pd.DataFrame({"Symbol": syms, "Company Name": syms, "Industry": ["Custom"] * len(syms)})
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
      <p class="sub">Structure-break scanner for NSE &amp; BSE</p>

      <div class="step" id="s_ex">
        <label>1. Exchange</label>
        <select id="exSel"><option value="" disabled selected>Select exchange</option><option>NSE</option><option>BSE</option></select>
      </div>

      <div class="step hidden" id="s_grp">
        <label>2. Segment / Index</label>
        <select id="grpSel"><option value="" disabled selected>Select segment</option></select>
      </div>

      <div class="step hidden" id="s_ind">
        <label>3. Sector / Industry</label>
        <select id="indSel"><option value="">All industries</option></select>
        <div id="custwrap" class="hidden">
          <textarea id="custom" rows="3" placeholder="RELIANCE, TCS, INFY ..."></textarea>
          <p class="hint">Get the full Nifty 500 list: open <a href="https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv" target="_blank">this link</a> in your own browser (it blocks bots, not you), open the CSV in Excel, copy the Symbol column, paste it above.</p>
        </div>
      </div>

      <div class="step hidden" id="s_final">
        <label>4. Timeframe</label>
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
let META={groups:[],industries:[],group_industries:{},custom_label:'Custom'};
let LAST_ROWS=[];

fetch('/api/meta').then(r=>r.json()).then(m=>{
  META=m;
  m.groups.forEach(g=>{const o=document.createElement('option');o.textContent=g;o.value=g;$('grpSel').appendChild(o)});
}).catch(()=>{$('keyw').classList.remove('hidden')});
$('key').value=localStorage.k||'';

function show(id){$(id).classList.remove('hidden')}
function hide(id){$(id).classList.add('hidden')}
function resetFrom(step){
  if(step<=1){hide('s_grp');$('grpSel').selectedIndex=0}
  if(step<=2){hide('s_ind')}
  if(step<=3){hide('s_final')}
  $('resList').innerHTML='<p class="emptynote">Results will appear here after you scan.</p>';
  $('st').textContent='';
  clearChart();
}

$('exSel').onchange=()=>{resetFrom(1);show('s_grp')};

$('grpSel').onchange=()=>{
  const g=$('grpSel').value;
  resetFrom(2);show('s_ind');
  if(g===META.custom_label){
    hide_ind_select();show('custwrap');show('s_final');
  }else{
    show_ind_select();hide('custwrap');
    $('indSel').innerHTML='<option value="">All industries</option>';
    (META.group_industries[g]||[]).forEach(v=>{const o=document.createElement('option');o.textContent=v;o.value=v;$('indSel').appendChild(o)});
  }
};
function hide_ind_select(){$('indSel').classList.add('hidden')}
function show_ind_select(){$('indSel').classList.remove('hidden')}

$('indSel').onchange=()=>{show('s_final')};

function clearChart(){
  $('infoCard').classList.remove('show');$('infoCard').innerHTML='';
  $('chartWrap').innerHTML='<div id="chartPlaceholder">Select a stock from the results list to load its chart here.</div>';
  document.querySelectorAll('.rescard').forEach(r=>r.classList.remove('active'));
}

$('go').onclick=async()=>{
  localStorage.k=$('key').value;
  $('go').disabled=true;$('st').textContent='Scanning… first run can take up to a minute.';
  $('resList').innerHTML='';clearChart();
  const q=new URLSearchParams({exchange:$('exSel').value,group:$('grpSel').value,industry:$('indSel').value,
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
    <p class="hint">Last Close is the most recent completed candle (Yahoo data, ~15 min delayed) — not a live tick. The TradingView chart on the right is the real live chart; look for price near the Broken Level above around the Event Bar Time to see the CHoCH visually.</p>`;
  loadTV(x.symbol,$('exSel').value,$('tf').value);
}

function loadTV(symbol,exchange,tf){
  $('chartWrap').innerHTML='<div id="tvc" style="height:100%;width:100%"></div>';
  const ivmap={'15m':'15','1h':'60','4h':'240','1d':'D'};
  function mk(){
    new TradingView.widget({autosize:true,symbol:exchange+':'+symbol,interval:ivmap[tf]||'D',
      timezone:'Asia/Kolkata',theme:'dark',style:'1',locale:'in',toolbar_bg:'#000000',
      enable_publishing:false,hide_top_toolbar:false,withdateranges:true,container_id:'tvc'});
  }
  if(window.TradingView){mk();}
  else{const s=document.createElement('script');s.src='https://s3.tradingview.com/tv.js';s.onload=mk;document.body.appendChild(s);}
}
</script></body></html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

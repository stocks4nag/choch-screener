import io, os, time
import requests, pandas as pd, yfinance as yf
from flask import Flask, jsonify, request, Response

app = Flask(__name__)
ACCESS_KEY = os.environ.get("ACCESS_KEY", "")  # optional password for personal use
UA = {"User-Agent": "Mozilla/5.0"}
GROUPS = {
    "Nifty 500 (All)": "ind_nifty500list", "Nifty 50 (Large cap)": "ind_nifty50list",
    "Nifty Next 50": "ind_niftynext50list", "Nifty 100": "ind_nifty100list",
    "Nifty 200": "ind_nifty200list", "Nifty Midcap 150": "ind_niftymidcap150list",
    "Nifty Smallcap 250": "ind_niftysmallcap250list", "Nifty Bank": "ind_niftybanklist",
    "Nifty IT": "ind_niftyitlist", "Nifty Auto": "ind_niftyautolist",
    "Nifty Pharma": "ind_niftypharmalist", "Nifty FMCG": "ind_niftyfmcglist",
    "Nifty Metal": "ind_niftymetallist", "Nifty Energy": "ind_niftyenergylist",
    "Nifty Realty": "ind_niftyrealtylist",
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
    def go():
        url = f"https://niftyindices.com/IndexConstituent/{GROUPS[name]}.csv"
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        return df[["Company Name", "Industry", "Symbol"]]
    return cached("g:" + name, 86400, go)


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
    try:
        inds = sorted(load_group("Nifty 500 (All)")["Industry"].dropna().unique().tolist())
    except Exception:
        inds = []
    return jsonify(groups=list(GROUPS), industries=inds)


@app.route("/api/scan")
def scan():
    a = request.args
    ex, grp, ind = a.get("exchange", "NSE"), a.get("group", "Nifty 500 (All)"), a.get("industry", "")
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

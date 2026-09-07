import html as htmlmod
import json

import config


def _cell(on: bool) -> str:
    return '<td class="on">■</td>' if on else '<td class="off">■</td>'


def render_html(payload: dict) -> str:
    pw = htmlmod.escape(config.BOARD_PASSWORD)
    rows_html = []
    hist = {i: 0 for i in range(11)}
    for r in payload.get("rows") or []:
        hist[int(r["pop"])] = hist.get(int(r["pop"]), 0) + 1
        sig = r.get("signal") or ""
        cls = "bull" if sig == "BULL" else ("bear" if sig == "BEAR" else "")
        mods = r.get("mods") or {}
        boxes = "".join(_cell(bool(mods.get(name))) for name in config.MODULES)
        coin = htmlmod.escape(str(r["symbol"]).replace("USDT", ""))
        rows_html.append(
            f"<tr class='{cls}'>"
            f"<td class='coin'>{coin}</td>"
            f"<td>{r['price']}</td>"
            f"<td>{r['state']}</td>"
            f"<td>{r['pop']}</td>"
            f"{boxes}"
            f"<td>{r['weight']:.3f}</td>"
            f"<td>{r['combo']:.3f}</td>"
            f"<td class='sig'>{sig or '—'}</td>"
            f"</tr>"
        )
    maxh = max(hist.values()) or 1
    bars = "".join(
        f"<div class='bar'><span>{hist[i]}</span><i style='height:{int(hist[i]/maxh*80)}px'></i><b>{i}</b></div>"
        for i in range(10, 5, -1)
    )
    logs = []
    for r in payload.get("rows") or []:
        if r.get("signal"):
            logs.append(
                f"<div>{htmlmod.escape(r['symbol'])} · {r['signal']} · pop {r['pop']} · {r['combo']}</div>"
            )
    log_html = "".join(logs[:18]) or "<div>Sinyal yok</div>"
    heads = "".join(f"<th>{n}</th>" for n in config.MODULES)
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>State Board</title>
<style>
:root {{ --bg:#03080c; --cyan:#39e7c3; --dim:#245e55; --red:#ff4d6d; --text:#c8fff2; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font-family: ui-monospace, Menlo, Consolas, monospace; font-size:12px; }}
#gate {{ min-height:100vh; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:12px; }}
#gate input, #gate button {{ padding:10px 12px; font-size:16px; border-radius:8px; border:1px solid var(--dim); background:#061016; color:#fff; }}
#app {{ display:none; }}
header {{ padding:10px 12px; border-bottom:1px solid #123; position:sticky; top:0; background:#03080ce6; z-index:2; }}
header b {{ color:var(--cyan); }}
.meta {{ color:#7ad; margin-top:4px; font-size:11px; }}
.wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
table {{ border-collapse:collapse; width:100%; min-width:920px; }}
th,td {{ padding:5px 6px; border-bottom:1px solid #0c1c1c; text-align:center; white-space:nowrap; }}
th {{ color:#6fd; font-weight:600; position:sticky; top:52px; background:#041016; }}
.coin {{ text-align:left; color:#fff; }}
.on {{ color:var(--cyan); }}
.off {{ color:#1a3330; }}
tr.bull td.sig {{ color:var(--cyan); font-weight:700; }}
tr.bear td.sig {{ color:var(--red); font-weight:700; }}
aside {{ padding:12px; }}
.bars {{ display:flex; gap:8px; align-items:flex-end; height:110px; }}
.bar {{ display:flex; flex-direction:column; align-items:center; justify-content:flex-end; width:28px; }}
.bar i {{ display:block; width:16px; background:var(--cyan); }}
.bar b {{ color:#689; }}
h3 {{ color:var(--cyan); font-size:12px; }}
</style>
</head>
<body>
<div id="gate">
  <div style="color:#39e7c3;font-size:18px">STATE BOARD</div>
  <input id="pw" type="password" placeholder="sifre" />
  <button onclick="go()">Gir</button>
</div>
<div id="app">
<header>
  <b>STATE · ADAPTIVE WEIGHT · BITGET USDT-M</b>
  <div class="meta">
    taranan {payload.get('scanned')}/{payload.get('total')}
    · sinyal {payload.get('signals')}
    · bull {payload.get('bull')}
    · bear {payload.get('bear')}
    · pop≥{payload.get('min_pop')}
    · combo≥{payload.get('min_combo')}
    · {payload.get('updated_at')}
  </div>
</header>
<div class="wrap">
<table>
<thead><tr>
<th>COIN</th><th>FIYAT</th><th>STATE</th><th>POP</th>{heads}<th>AGIRLIK</th><th>C.SCORE</th><th>SINYAL</th>
</tr></thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</div>
<aside>
<h3>POPCOUNT</h3>
<div class="bars">{bars}</div>
<h3>SINYAL LOG</h3>
{log_html}
</aside>
</div>
<script>
const KEY={json.dumps(config.BOARD_PASSWORD)};
function go(){{
  const v=document.getElementById('pw').value;
  if(v===KEY){{ localStorage.setItem('sb',v); show(); }}
  else alert('sifre yanlis');
}}
function show(){{ document.getElementById('gate').style.display='none'; document.getElementById('app').style.display='block'; }}
if(localStorage.getItem('sb')===KEY) show();
document.getElementById('pw').addEventListener('keydown',e=>{{if(e.key==='Enter')go();}});
</script>
</body></html>
"""

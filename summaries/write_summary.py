from __future__ import annotations
import argparse, json, os, math, html
from pathlib import Path
from datetime import datetime

def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def _esc(s: str) -> str:
    return html.escape(s or "")

def main():
    p = argparse.ArgumentParser(description="Write a delightful HTML report")
    p.add_argument("--results", type=str, required=True)
    p.add_argument("--out", type=str, required=True)
    p.add_argument("--viz", choices=["on","off"], default="on")
    p.add_argument("--title", type=str, default=None)
    p.add_argument("--label", type=str, default=None)
    args = p.parse_args()

    res = _read_json(Path(args.results))
    checks = res.get("checks", [])
    summary = res.get("summary", {})
    passed = summary.get("passed", sum(1 for c in checks if c.get("status")=="pass"))
    failed = summary.get("failed", sum(1 for c in checks if c.get("status")=="fail"))
    dataset = summary.get("dataset", "data/sample.csv")
    mode = summary.get("mode", "plain")
    stamp = summary.get("timestamp", datetime.now().strftime("%Y%m%d-%H%M"))
    top_failing = summary.get("top_failing", sorted([c for c in checks if c.get("status")=="fail"], key=lambda c:c.get("count",0), reverse=True)[:5])

    # optional fix info
    out_dir = Path(args.out).parent
    fix_report_path = out_dir / "fix_report.json"
    fixes = None
    if fix_report_path.exists():
        try:
            fixes = _read_json(fix_report_path)
        except Exception:
            fixes = None

    page_title = args.title or f"Data Quality Report • {Path(dataset).name} • {mode.upper()}"
    label = f" • {args.label}" if args.label else ""

    # simple inline style + embedded charts (no CDN)
    html_out = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{_esc(page_title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{
  --bg:#0b1220; --panel:#111a2b; --muted:#7a8aa0; --text:#e7eef8; --accent:#68d391; --warn:#f6ad55; --danger:#fc8181; --blue:#63b3ed;
}}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: Inter, system-ui, Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--text); }}
.header {{ padding:24px 24px 0; }}
.h1 {{ font-size:20px; font-weight:700; margin:0 0 8px; }}
.sub {{ color:var(--muted); font-size:14px; }}
.container {{ padding: 24px; display:grid; gap:16px; }}
.grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap:16px; }}
.card {{ background:var(--panel); border:1px solid rgba(255,255,255,0.06); border-radius:14px; padding:16px; }}
.kpi .val {{ font-size:28px; font-weight:700; }}
.kpi .lab {{ color:var(--muted); font-size:12px; }}
.table {{ width:100%; border-collapse: collapse; font-size:14px; }}
.table th, .table td {{ padding:10px 8px; border-bottom:1px solid rgba(255,255,255,0.06); text-align:left; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; }}
.badge.pass {{ background:#234f3e; color:#9ae6b4; }}
.badge.fail {{ background:#54202a; color:#feb2b2; }}
a, a:visited {{ color:var(--blue); text-decoration:none }}
.hstack {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; }}
code.small {{ font-size:12px; color:var(--muted); }}
.footer {{ color:var(--muted); font-size:12px; padding: 8px 24px 24px; }}
canvas {{ background:transparent; width:100%; height:280px; }}
</style>
</head>
<body>
  <div class="header">
    <div class="h1">{_esc(page_title)}{_esc(label)}</div>
    <div class="sub">{_esc(Path(dataset).name)} • {_esc(mode.upper())} • {_esc(stamp)}</div>
  </div>

  <div class="container">
    <div class="grid">
      <div class="card kpi"><div class="val">{len(checks)}</div><div class="lab">Total checks</div></div>
      <div class="card kpi"><div class="val">{passed}</div><div class="lab">Checks passed</div></div>
      <div class="card kpi"><div class="val">{failed}</div><div class="lab">Checks failed</div></div>
      {"<div class='card kpi'><div class='val'>"+str(fixes.get('total_rows_before','-'))+"</div><div class='lab'>Rows before</div></div>" if fixes else ""}
      {"<div class='card kpi'><div class='val'>"+str(fixes.get('total_rows_after','-'))+"</div><div class='lab'>Rows after</div></div>" if fixes else ""}
      {"<div class='card kpi'><div class='val'>"+str(next((a['affected'] for a in fixes.get('actions',[]) if a.get('action')=='drop_duplicates'), 0))+"</div><div class='lab'>Duplicates dropped</div></div>" if fixes else ""}
    </div>

    <div class="grid">
      <div class="card">
        <h3>Pass vs Fail</h3>
        <canvas id="donut"></canvas>
      </div>
      <div class="card">
        <h3>Top failing checks</h3>
        <canvas id="bar"></canvas>
      </div>
    </div>

    <div class="card">
      <h3>Top failing checks (details)</h3>
      <table class="table" id="fails">
        <thead><tr><th>Rule</th><th>Table</th><th>Column</th><th>Type</th><th>Count</th></tr></thead>
        <tbody>
          {"".join(f"<tr><td>{_esc(c.get('name',''))}</td><td>{_esc(c.get('table',''))}</td><td>{_esc(str(c.get('column','')))}</td><td>{_esc(c.get('type',''))}</td><td>{int(c.get('count',0))}</td></tr>" for c in top_failing)}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>Failure samples</h3>
      <div class="sub">Up to 200 sample rows saved per failing rule.</div>
      <div class="hstack">
        {"".join(f"<a href='failures/{_esc(v)}'>{_esc(k)}</a>" for k,v in (res.get('failure_samples',{}) or {}).items()) or "<span class='sub'>No samples saved.</span>"}
      </div>
    </div>

    {"<div class='card'><h3>Fixes applied</h3><pre style='white-space:pre-wrap'>"+_esc(json.dumps(fixes, indent=2))+"</pre><div class='hstack'><a href='cleaned.csv'>cleaned.csv</a><a href='quarantine/'>quarantine/</a></div></div>" if fixes else ""}
  </div>

  <div class="footer">Generated by Data Quality Sentry</div>

<script>
(function() {{
  // Tiny chart lib: inline Canvas drawing for donut and bar (no CDN)
  function donut(id, parts, colors) {{
    var c = document.getElementById(id), ctx = c.getContext('2d'), w=c.width, h=c.height, r=Math.min(w,h)/2-10, cx=w/2, cy=h/2;
    var total = parts.reduce((a,b)=>a+b,0); var ang0=-Math.PI/2;
    parts.forEach(function(v,i) {{
      var ang = (v/Math.max(1,total))*2*Math.PI;
      ctx.beginPath(); ctx.moveTo(cx,cy); ctx.arc(cx,cy,r,ang0,ang0+ang); ctx.closePath();
      ctx.fillStyle = colors[i%colors.length]; ctx.fill(); ang0 += ang;
    }});
  }}
  function bar(id, labels, values) {{
    var c = document.getElementById(id), ctx=c.getContext('2d'), w=c.width, h=c.height;
    var max = Math.max.apply(null, values.concat([1])); var pad=32; var bw = (w-2*pad)/Math.max(1,labels.length);
    ctx.strokeStyle='rgba(255,255,255,0.15)'; ctx.beginPath(); ctx.moveTo(pad, h-pad); ctx.lineTo(w-pad, h-pad); ctx.stroke();
    for (var i=0;i<labels.length;i++) {{
      var x = pad + i*bw + 8; var vh = (values[i]/max)*(h-2*pad); var y=h-pad-vh;
      ctx.fillStyle = '#63b3ed'; ctx.fillRect(x, y, Math.max(8, bw-16), vh);
    }}
  }}
  // Data from server-side render
  var passed = {passed}, failed = {failed};
  donut('donut', [passed, failed], ['#68d391','#fc8181']);

  var labels = [{",".join(f"'{_esc(c.get('type',''))}'" for c in top_failing)}];
  var values = [{",".join(str(int(c.get('count',0))) for c in top_failing)}];
  bar('bar', labels, values);
}})();
</script>
</body></html>
"""
    Path(args.out).write_text(html_out, encoding="utf-8")

if __name__ == "__main__":
    main()

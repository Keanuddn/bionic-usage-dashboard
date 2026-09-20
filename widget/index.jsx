// Bionic Usage — Übersicht desktop widget (Nothing style, light mode)
// Click the widget to open the full dashboard.
// Data: extract.py reads the local Bionic session databases.

import { run } from "uebersicht";

// Where extract.py / dashboard.html live. Set this to your folder.
const BASE = "/path/to/bionic-usage-dashboard";

export const refreshFrequency = 60000; // 1 min

export const command = `cd "${BASE}" && /usr/bin/python3 extract.py --quiet && cat data.json`;

export const className = `
  @import url("https://fonts.googleapis.com/css2?family=Doto:wght@900&family=Space+Grotesk:wght@300;400;500&family=Space+Mono:wght@400;700&display=swap");
  top: 48px;
  left: 48px;
  font-family: "Space Grotesk", system-ui, sans-serif;
  color: #1A1A1A;
  user-select: none;
  cursor: pointer;

  .card {
    width: 380px;
    background: rgba(245, 245, 245, 0.97);
    border: 1px solid #CCCCCC;
    padding: 24px;
  }
  .label {
    font-family: "Space Mono", monospace;
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #666666;
  }
  .dim { color: #999999; }
  .head { display: flex; justify-content: space-between; margin-bottom: 16px; }
  .hero {
    font-family: "Doto", "Space Mono", monospace;
    font-weight: 900;
    font-size: 44px;
    line-height: 1.0;
    letter-spacing: -0.02em;
    color: #000000;
    font-variant-numeric: tabular-nums;
  }
  .subhead {
    display: flex; gap: 16px;
    font-family: "Space Mono", monospace;
    font-size: 11px;
    color: #666666;
    margin: 8px 0 16px;
  }
  .bar { display: flex; gap: 2px; height: 8px; }
  .bar span { flex: 1; background: #E8E8E8; }
  .bar span.f { background: #1A1A1A; }
  .bar.warn span.f { background: #D4A843; }
  .bar.over span.f { background: #D71921; }
  .note {
    font-family: "Space Mono", monospace;
    font-size: 10px;
    letter-spacing: 0.06em;
    color: #666666;
    margin: 8px 0 20px;
  }
  .tops { margin-bottom: 16px; }
  .trow {
    display: grid;
    grid-template-columns: 1fr 72px 48px;
    gap: 8px;
    align-items: center;
    padding: 4px 0;
  }
  .tname {
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tbar { position: relative; height: 5px; background: #E8E8E8; }
  .tbar i { position: absolute; top: 0; bottom: 0; left: 0; background: #1A1A1A; }
  .tval {
    font-family: "Space Mono", monospace;
    font-size: 10px;
    text-align: right;
    color: #666666;
    font-variant-numeric: tabular-nums;
  }
  .foot { text-align: right; }
`;

const kfmt = n => n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M"
               : n >= 1e3 ? Math.round(n / 1e3) + "k" : String(n);

export const render = ({ output }) => {
  let d;
  try { d = JSON.parse(output); } catch (e) {
    return <div style={{ textAlign: "right" }}><span className="label">[LADEN…]</span></div>;
  }
  const t = d.totals.week;
  const total = t.input + t.output;
  const L = d.limit;
  const budget = d.config.weekly_token_budget;
  // Official weekly limit when available, local token count otherwise
  const usedPct = L ? 100 - L.remaining_basis_points / 100 : Math.min(100, total / budget * 100);
  const pct = usedPct;
  const over = usedPct >= 100;
  const warn = !over && usedPct > 75;
  const segs = 24;
  const top = (d.top_sessions.week || []).slice(0, 3);
  const maxTok = Math.max(...top.map(s => s.tokens), 1);
  const gen = new Date(d.generated_at * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="card" onClick={() => run(`open "${BASE}/dashboard.html"`)}>
      <div className="head">
        <span className="label">BIONIC // TOKENS · WOCHE</span>
        <span className="label dim">{L ? "LIMIT LIVE" : gen}</span>
      </div>
      <div className="hero">{total.toLocaleString("de-DE")}</div>
      <div className="subhead">
        <span>IN {kfmt(t.input)}</span>
        <span>OUT {kfmt(t.output)}</span>
        <span>CALLS {t.tool_calls}</span>
      </div>
      <div className={"bar" + (over ? " over" : warn ? " warn" : "")}>
        {Array.from({ length: segs }).map((_, i) => (
          <span key={i} className={i / segs * 100 < pct ? "f" : ""} />
        ))}
      </div>
      <div className="note">
        {L
          ? `${(L.remaining_basis_points / 100).toFixed(1)}% ÜBRIG${over ? " · LEER" : ""}`
          : over ? "LIMIT ÜBERSCHRITTEN" : `${kfmt(budget - total)} ÜBRIG · ${pct.toFixed(0)}%`}
      </div>
      <div className="tops">
        {top.map((s, i) => (
          <div className="trow" key={i}>
            <span className="tname">{s.name}</span>
            <span className="tbar"><i style={{ width: (s.tokens / maxTok * 100) + "%" }} /></span>
            <span className="tval">{kfmt(s.tokens)}</span>
          </div>
        ))}
      </div>
      <div className="foot label dim">KLICKEN FÜR VOLLANSICHT →</div>
    </div>
  );
};



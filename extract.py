#!/usr/bin/env python3
"""
Bionic Usage Extractor
Reads LM Studio Bionic session databases (ng-sessions.sqlite) and produces
aggregated usage data as data.json + data.js (for file:// dashboards).

Stdlib only. Run manually or via the Übersicht widget command.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
PROJECTS_ROOT = os.path.expanduser("~/.lmstudio/apps/bionic/projects")

CLOUD_ACCOUNT_PATH = os.path.expanduser(
    "~/.lmstudio/apps/bionic/.internal/cloud-account.json"
)

DEFAULT_CONFIG = {
    "weekly_token_budget": 1000000,
    "monthly_token_budget": 4000000,
    "deep_dive_context_tokens": 100000,
}

LOCAL_TZ = datetime.now().astimezone().tzinfo


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def read_cloud_limit():
    """Read the official weekly limit from Bionic's own local cache
    (~/.lmstudio/apps/bionic/.internal/cloud-account.json). The app refreshes
    this file itself whenever it syncs billing context."""
    try:
        with open(CLOUD_ACCOUNT_PATH) as f:
            d = json.load(f)
        for lim in d["payload"].get("limits") or []:
            w = lim.get("weekly")
            if w:
                return {
                    "remaining_basis_points": w["remainingBasisPoints"],
                    "limit_microcredits": int(w["limitMicrocredits"]),
                    "remaining_microcredits": int(w["remainingMicrocredits"]),
                    "resets_at_iso": w["resetsAtIso"],
                    "generated_at_iso": d["payload"]["generatedAtIso"],
                    "plan": (d["payload"].get("plan") or {}).get("name"),
                }
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        pass
    return None


def find_dbs():
    dbs = []
    if not os.path.isdir(PROJECTS_ROOT):
        return dbs
    for proj in sorted(os.listdir(PROJECTS_ROOT)):
        db = os.path.join(PROJECTS_ROOT, proj, ".internal", "ng-sessions.sqlite")
        if os.path.isfile(db):
            dbs.append(db)
    return dbs


def extract():
    cfg = load_config()
    now = datetime.now(LOCAL_TZ)

    sessions = []        # session metadata dicts
    all_entries = {}     # entry_id -> prev (full chain, incl. non-message entries)
    messages = {}        # entry_id -> parsed message entry

    for db_path in find_dbs():
        project_id = os.path.basename(os.path.dirname(os.path.dirname(db_path)))
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            sess_rows = conn.execute(
                "SELECT session_id, session_name, suggested_session_name, "
                "session_json, is_temporary, is_transient, committed_head_entry_id "
                "FROM sessions"
            ).fetchall()
            entry_rows = conn.execute(
                "SELECT id, previous_id, entry_json FROM chat_entries"
            ).fetchall()
            conn.close()
        except sqlite3.Error:
            continue

        for sid, name, suggested, sj, is_temp, is_transient, head in sess_rows:
            if is_temp or is_transient:
                continue
            model = None
            try:
                spec = json.loads(sj).get("modelSpecifier") or {}
                if spec.get("type") == "cloudInference":
                    model = spec.get("model")
            except (json.JSONDecodeError, AttributeError):
                pass
            sessions.append({
                "session_id": sid,
                "name": name or suggested,
                "model": model,
                "project": project_id,
                "head": head,
            })

        for eid, prev, raw in entry_rows:
            all_entries[eid] = prev
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("type") != "message":
                continue
            msg = data.get("message") or {}
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            ts = data.get("createdTimestamp")
            if not ts:
                continue
            ctx = data.get("context") or {}
            tools = [p.get("name") for p in (msg.get("parts") or [])
                     if isinstance(p, dict) and p.get("type") == "toolCallRequest" and p.get("name")]
            messages[eid] = {
                "id": eid, "role": role, "ts": ts / 1000.0,
                "before": ctx.get("before") or 0, "self": ctx.get("self") or 0,
                "total": ctx.get("total") or 0, "tools": tools, "session": None,
            }

    # Walk each session's chain from the head, attribute entries (dedup: an
    # entry shared by forked sessions is counted for the first session only).
    sess_by_id = {s["session_id"]: s for s in sessions}
    for s in sessions:
        cur = s["head"]
        while cur and cur in all_entries:
            m = messages.get(cur)
            if m is not None and m["session"] is None:
                m["session"] = s["session_id"]
            cur = all_entries[cur]

    msgs = sorted((e for e in messages.values() if e["session"]), key=lambda e: e["ts"])

    for s in sessions:
        s["input"] = s["output"] = s["tool_calls"] = 0
        s["last_active"] = None
    for e in msgs:
        s = sess_by_id[e["session"]]
        if e["role"] == "assistant":
            s["input"] += e["before"]
            s["output"] += e["self"]
        s["tool_calls"] += len(e["tools"])
        s["last_active"] = max(s["last_active"] or 0, e["ts"])

    # ---- Time buckets --------------------------------------------------
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    prev_week_start = monday - timedelta(days=7)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    def new_bucket():
        return {"input": 0, "output": 0, "tool_calls": 0, "messages": 0}

    periods = {"week": monday, "prev_week": prev_week_start,
               "month": month_start, "prev_month": prev_month_start}
    totals = {k: new_bucket() for k in ("week", "prev_week", "month", "prev_month", "all")}

    per_day = {}
    per_model_week, per_model_month = {}, {}
    per_tool_week = {}
    session_week, session_month = set(), set()
    deep_dive = night_owl = False
    top_context = 0

    for e in msgs:
        d = datetime.fromtimestamp(e["ts"], LOCAL_TZ).date()
        dk = d.strftime("%Y-%m-%d")
        bucket = per_day.setdefault(dk, {"input": 0, "output": 0, "tool_calls": 0})
        model = (sess_by_id[e["session"]].get("model") or "local")

        is_asst = e["role"] == "assistant"
        tokens = (e["before"] + e["self"]) if is_asst else 0

        totals["all"]["input"] += e["before"] if is_asst else 0
        totals["all"]["output"] += e["self"] if is_asst else 0
        totals["all"]["messages"] += 1
        totals["all"]["tool_calls"] += len(e["tools"])
        bucket["input"] += e["before"] if is_asst else 0
        bucket["output"] += e["self"] if is_asst else 0
        bucket["tool_calls"] += len(e["tools"])

        for pname, pstart in periods.items():
            if d >= pstart:
                t = totals[pname]
                t["messages"] += 1
                t["tool_calls"] += len(e["tools"])
                if is_asst:
                    t["input"] += e["before"]
                    t["output"] += e["self"]

        if d >= monday:
            per_model_week[model] = per_model_week.get(model, 0) + tokens
            per_tool_week.update(per_tool_week)
            for tname in e["tools"]:
                per_tool_week[tname] = per_tool_week.get(tname, 0) + 1
            session_week.add(e["session"])
            top_context = max(top_context, e["total"])
            if e["total"] >= cfg["deep_dive_context_tokens"]:
                deep_dive = True
            hr = datetime.fromtimestamp(e["ts"], LOCAL_TZ).hour
            if hr >= 23 or hr < 5:
                night_owl = True
        if d >= month_start:
            per_model_month[model] = per_model_month.get(model, 0) + tokens
            session_month.add(e["session"])

    # Streak: consecutive active days ending today or yesterday
    day_set = set(per_day.keys())
    streak = 0
    probe = today
    if probe.strftime("%Y-%m-%d") not in day_set:
        probe -= timedelta(days=1)
    while probe.strftime("%Y-%m-%d") in day_set:
        streak += 1
        probe -= timedelta(days=1)

    daily_series = []
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        b = per_day.get(d, {"input": 0, "output": 0, "tool_calls": 0})
        daily_series.append({"day": d, **b})

    def sess_view(s, active_set):
        return {
            "name": s["name"] or "UNNAMED SESSION",
            "model": s["model"] or "local",
            "tokens": s["input"] + s["output"],
            "input": s["input"], "output": s["output"],
            "tool_calls": s["tool_calls"],
            "last_active": s["last_active"],
            "active_in_period": s["session_id"] in active_set,
        }

    def top_list(active_set, require_active):
        rows = [sess_view(s, active_set) for s in sessions]
        if require_active:
            rows = [r for r in rows if r["active_in_period"]]
        rows = [r for r in rows if r["tokens"] > 0]
        rows.sort(key=lambda r: r["tokens"], reverse=True)
        return rows[:8]

    data = {
        "generated_at": now.timestamp(),
        "config": {
            "weekly_token_budget": cfg["weekly_token_budget"],
            "monthly_token_budget": cfg["monthly_token_budget"],
        },
        "totals": totals,
        "daily_series": daily_series,
        "per_model_week": per_model_week,
        "per_model_month": per_model_month,
        "per_tool_week": per_tool_week,
        "top_sessions": {
            "week": top_list(session_week, True),
            "month": top_list(session_month, True),
            "all": top_list(set(), False),
        },
        "streak_days": streak,
        "limit": read_cloud_limit(),
        "flags": {"deep_dive": deep_dive, "night_owl": night_owl,
                  "top_context_tokens": top_context},
    }
    return data


def main():
    data = extract()
    with open(os.path.join(BASE, "data.json"), "w") as f:
        json.dump(data, f)
    with open(os.path.join(BASE, "data.js"), "w") as f:
        f.write("window.BIONIC_DATA = ")
        json.dump(data, f)
        f.write(";")
    if "--stdout" in sys.argv:
        json.dump(data, sys.stdout)
    elif "--quiet" not in sys.argv:
        wk = data["totals"]["week"]
        print(f"OK week: in={wk['input']:,} out={wk['output']:,} tools={wk['tool_calls']}")


if __name__ == "__main__":
    main()

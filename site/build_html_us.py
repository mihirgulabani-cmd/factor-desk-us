#!/usr/bin/env python3
"""build_html_us.py — inline model + backtest JSON into the template -> the site."""
import json, os

tpl = open("site/template_us.html").read()
model = open("data/model_us.json").read()
bt = open("data/backtest_us.json").read() if os.path.exists("data/backtest_us.json") else "null"
doss = sorted(f[:-5] for f in os.listdir("dossiers") if f.endswith(".html")) if os.path.isdir("dossiers") else []
out = (tpl.replace("__DATA__", model)
          .replace("__BT__", bt)
          .replace("__DOSSIERS__", json.dumps(doss)))
open("site/US-Factor-Desk.html", "w").write(out)
print(f"wrote site/US-Factor-Desk.html ({len(out)/1e6:.1f} MB, {len(doss)} dossiers)")

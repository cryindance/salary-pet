# -*- coding: utf-8 -*-
import importlib.util, os, sys
from datetime import datetime

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("appmod", os.path.join(here, "app.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

cfg = {
    "monthly_salary": 10000.0, "work_days": 22,
    "work_start": "08:30", "lunch_start": "12:00",
    "lunch_end": "13:00", "work_end": "18:00", "goal": 0.0,
}
print("日薪", round(m.compute(datetime.now(), cfg)["daily"], 2))

cases = ["07:00", "08:00", "08:30", "09:30", "11:59", "12:00", "12:30",
         "13:00", "13:30", "17:59", "18:00", "18:30", "23:00"]
for t in cases:
    h, mi = map(int, t.split(":"))
    d = m.compute(datetime(2026, 11, 10, h, mi, 0), cfg)
    hours = d["earned"] / d["per_sec"] / 3600 if d["per_sec"] else 0
    print("%s phase=%-6s earned=%8.2f  计费时长=%.2fh pct=%.1f%% reached=%s" %
          (t, d["phase"], d["earned"], hours, d["pct"] * 100, d["reached"]))

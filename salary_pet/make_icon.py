# -*- coding: utf-8 -*-
"""生成应用图标 app.ico"""
import os
import importlib.util

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("appmod", os.path.join(here, "app.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

os.makedirs(os.path.join(here, "assets"), exist_ok=True)
big = m.make_tray_image(256)
out = os.path.join(here, "assets", "app.ico")
big.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
big.save(os.path.join(here, "assets", "app.png"))
print("ok", out, os.path.getsize(out))

# -*- coding: utf-8 -*-
"""测试驱动：打开设置窗口并截图，可选模拟达标"""
import os
import sys
import importlib.util
from datetime import datetime

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("appmod", os.path.join(here, "app.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

mode = sys.argv[1] if len(sys.argv) > 1 else "settings"
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "shot3.png")

if mode == "reached":
    m.CONFIG_FILE = os.path.join(here, "test_config.json")
    import json
    cfg = dict(m.DEFAULTS)
    cfg["goal"] = 1.0
    cfg["pos"] = [1200, 500]
    with open(m.CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f)

root = __import__("tkinter").Tk()
app = m.SalaryPet(root)

if mode == "settings":
    root.after(800, app.open_settings)

def snap():
    from PIL import ImageGrab
    x, y = root.winfo_rootx(), root.winfo_rootx() + 0  # noqa
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    img = ImageGrab.grab(bbox=(x - 20, y - 20, x + w + 20, y + h + 20))
    img.save(out)
    try:
        app.quit_app()
    except Exception:
        pass
    root.destroy()
    os._exit(0)

root.after(2600, snap)
root.mainloop()
print("saved", out)

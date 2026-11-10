# -*- coding: utf-8 -*-
"""上班鼓励器 —— 桌面薪资实时跳动小挂件"""

import ctypes
import json
import math
import os
import sys
import time
import traceback
from datetime import datetime

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
from tkinter import ttk

APP_NAME = "上班鼓励器"
APP_ID = "WorkBuddySalaryHappy"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_ID)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_FILE = os.path.join(CONFIG_DIR, "error.log")

DEFAULTS = {
    "monthly_salary": 10000.0,
    "work_days": 22,
    "work_start": "08:30",
    "lunch_start": "12:00",
    "lunch_end": "13:00",
    "work_end": "18:00",
    "goal": 0.0,          # 0 表示用日薪作为目标
    "always_on_top": True,
    "lock_pos": False,
    "autostart": True,
    "opacity": 0.5,       # 窗口不透明度 0.3~1.0
    "pos": None,
}

# ---------- 主题 ----------
W, H = 330, 196
CLEAR = "#010203"          # 透明色键
BG = "#12141b"
BORDER = "#252a38"
TEXT = "#e9eef8"
SUB = "#78829a"
DIM = "#565f75"
ACCENT = "#3ee0c8"
ACCENT_DIM = "#1f6b62"
GOLD = "#ffc94d"
GOLD_DIM = "#6d5420"
DANGER = "#ff6b6b"


def log_error(msg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


# ---------- 配置 ----------
def load_cfg():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_error("save_cfg: %r" % e)


# ---------- 开机自启 ----------
def autostart_command():
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    return None


def set_autostart(enable):
    cmd = autostart_command()
    if not cmd:
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
        )
        if enable:
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_ID)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        log_error("set_autostart: %r" % e)
        return False


def get_autostart():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_QUERY_VALUE,
        )
        try:
            winreg.QueryValueEx(key, APP_ID)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


# ---------- 时间与计算 ----------
def to_sec(hhmm, fallback):
    try:
        parts = str(hhmm).strip().replace("：", ":").split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        return h * 3600 + m * 60
    except Exception:
        return fallback


def fmt_hm(sec):
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m = rem // 60
    if h and m:
        return "%dh%02dm" % (h, m)
    if h:
        return "%dh" % h
    if m:
        return "%dm" % m
    return "%ds" % (sec % 60)


def fmt_clock(sec):
    sec = int(sec) % 86400
    return "%02d:%02d" % (sec // 3600, (sec % 3600) // 60)


def compute(now, cfg):
    """返回当前时刻的薪资与状态数据"""
    start = to_sec(cfg.get("work_start"), 8 * 3600 + 1800)
    lunch_s = to_sec(cfg.get("lunch_start"), 12 * 3600)
    lunch_e = to_sec(cfg.get("lunch_end"), 13 * 3600)
    end = to_sec(cfg.get("work_end"), 18 * 3600)

    if end <= start:
        end = start + 9 * 3600
    lunch_s = min(max(lunch_s, start), end)
    lunch_e = min(max(lunch_e, lunch_s), end)

    lunch_len = lunch_e - lunch_s
    total = max(1, (end - start) - lunch_len)

    try:
        days = max(1, int(float(cfg.get("work_days") or 22)))
    except Exception:
        days = 22
    try:
        monthly = max(0.0, float(cfg.get("monthly_salary") or 0))
    except Exception:
        monthly = 0.0

    daily = monthly / days
    per_sec = daily / total

    t = now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1e6

    if t < start:
        elapsed = 0.0
        phase = "before"
    elif t < lunch_s:
        elapsed = t - start
        phase = "work"
    elif t < lunch_e:
        elapsed = lunch_s - start
        phase = "lunch"
    elif t < end:
        elapsed = (t - start) - lunch_len
        phase = "work"
    else:
        elapsed = total
        phase = "done"

    earned = per_sec * elapsed
    if earned > daily:
        earned = daily
    if earned < 0:
        earned = 0.0

    try:
        goal = float(cfg.get("goal") or 0)
    except Exception:
        goal = 0.0
    if goal <= 0:
        goal = daily

    pct = (earned / goal) if goal > 0 else 0.0
    reached = goal > 0 and earned >= goal - 1e-9

    return {
        "start": start, "end": end, "lunch_s": lunch_s, "lunch_e": lunch_e,
        "total": total, "daily": daily, "monthly": monthly, "days": days,
        "per_sec": per_sec, "earned": earned, "phase": phase,
        "goal": goal, "pct": pct, "reached": reached,
        "to_start": max(0, start - t), "to_end": max(0, end - t),
        "to_lunch": max(0, lunch_s - t), "to_lunch_end": max(0, lunch_e - t),
    }


def round_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return c.create_polygon(pts, smooth=True, **kw)


def make_tray_image(size=64):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, size - 3, size - 3], radius=int(size * 0.24),
                        fill=(20, 160, 148, 255))
    d.rounded_rectangle([2, 2, size - 3, size - 3], radius=int(size * 0.24),
                        outline=(62, 224, 200, 255), width=max(1, size // 32))
    font = None
    for path in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\segoeuib.ttf",
                 r"C:\Windows\Fonts\arialbd.ttf"):
        try:
            font = ImageFont.truetype(path, int(size * 0.58))
            break
        except Exception:
            continue
    txt = "¥"
    if font is None:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), txt, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), txt,
           font=font, fill=(255, 255, 255, 255))
    return img


class SalaryPet:
    def __init__(self, root):
        self.root = root
        self.cfg = load_cfg()
        self.hidden = False
        self.tray = None
        self._drag = None
        self._pulse = 0.0
        self._last_sec_key = None

        root.overrideredirect(True)
        root.wm_attributes("-transparentcolor", CLEAR)
        root.configure(bg=CLEAR)
        root.attributes("-topmost", bool(self.cfg.get("always_on_top", True)))
        self.apply_opacity()

        self.canvas = tk.Canvas(root, width=W, height=H, bg=CLEAR,
                                highlightthickness=0, bd=0)
        self.canvas.pack()

        self._build_ui()
        self._bind_events()
        self._place_window()

        self.set_autostart_state()
        self.start_tray()

        self.tick()

    # ---------- 界面 ----------
    def _build_ui(self):
        c = self.canvas
        f = lambda size, weight="normal", family="Microsoft YaHei UI": (
            family, size, weight)

        self.card = round_rect(c, 1, 1, W - 1, H - 1, 20, fill=BG,
                               outline=BORDER, width=1)
        self.glow = round_rect(c, 3, 3, W - 3, H - 3, 18, fill="",
                               outline=GOLD_DIM, width=1, state="hidden")

        self.dot = c.create_oval(24, 20, 32, 28, fill=ACCENT, outline="")
        self.status_txt = c.create_text(39, 24, text="", anchor="w",
                                        fill=SUB, font=f(9))

        # 菜单按钮
        self.menu_btn = c.create_rectangle(264, 12, 292, 36, fill="", outline="",
                                           tags=("menubtn",))
        for i, y in enumerate((19, 24, 29)):
            c.create_line(271, y, 285, y, fill=DIM, width=2,
                          capstyle="round", tags=("menubtn",))
        # 关闭按钮
        self.close_btn = c.create_rectangle(296, 12, 320, 36, fill="", outline="",
                                            tags=("closebtn",))
        c.create_line(302, 19, 314, 31, fill=DIM, width=2,
                      capstyle="round", tags=("closebtn",))
        c.create_line(314, 19, 302, 31, fill=DIM, width=2,
                      capstyle="round", tags=("closebtn",))

        c.create_text(26, 80, text="¥", anchor="w", fill=SUB, font=f(17, "bold"))
        self.amount = c.create_text(47, 80, text="0.000", anchor="w",
                                    fill=TEXT, font=f(33, "bold"))

        c.create_text(26, 106, text="今日进度", anchor="w", fill=DIM, font=f(8))
        self.pct_txt = c.create_text(W - 26, 106, text="0.0%", anchor="e",
                                     fill=SUB, font=f(8))

        c.create_line(30, 122, W - 30, 122, fill="#232733", width=8,
                      capstyle="round")
        self.bar = c.create_line(30, 122, 30, 122, fill=ACCENT, width=8,
                                 capstyle="round")
        self.bar_w = W - 60

        self.daily_txt = c.create_text(26, 148, text="", anchor="w",
                                       fill=SUB, font=f(9))
        self.per_txt = c.create_text(W - 26, 148, text="", anchor="e",
                                     fill=SUB, font=f(9))

        self.hint_txt = c.create_text(26, 172, text="", anchor="w",
                                      fill=DIM, font=f(8))
        self.goal_txt = c.create_text(W - 26, 172, text="", anchor="e",
                                      fill=DIM, font=f(8))

    def _bind_events(self):
        c = self.canvas
        c.bind("<Button-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Button-3>", self.popup_menu)
        c.bind("<Double-Button-1>", lambda e: self.open_settings())
        c.tag_bind("closebtn", "<Button-1>", lambda e: self.hide_window())
        c.tag_bind("menubtn", "<Button-1>", self.popup_menu)

    def _place_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        pos = self.cfg.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            x, y = int(pos[0]), int(pos[1])
            x = max(-50, min(x, sw - 80))
            y = max(0, min(y, sh - 60))
        else:
            x, y = sw - W - 40, sh - H - 110
        self.root.geometry("%dx%d+%d+%d" % (W, H, x, y))

    def save_pos(self):
        self.cfg["pos"] = [self.root.winfo_x(), self.root.winfo_y()]
        save_cfg(self.cfg)

    # ---------- 交互 ----------
    def on_press(self, event):
        self._drag = (event.x_root, event.y_root,
                      self.root.winfo_x(), self.root.winfo_y())

    def on_drag(self, event):
        if not self._drag or self.cfg.get("lock_pos"):
            return
        dx = event.x_root - self._drag[0]
        dy = event.y_root - self._drag[1]
        self.root.geometry("+%d+%d" % (self._drag[2] + dx, self._drag[3] + dy))

    def on_release(self, event):
        if self._drag and not self.cfg.get("lock_pos"):
            self.save_pos()
        self._drag = None

    def popup_menu(self, event=None):
        m = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 9))
        m.add_command(label="设置…", command=self.open_settings)
        m.add_checkbutton(label="窗口置顶", onvalue=1, offvalue=0,
                          variable=self._var_top())
        m.add_checkbutton(label="锁定位置", onvalue=1, offvalue=0,
                          variable=self._var_lock())
        m.add_checkbutton(label="开机自动启动", onvalue=1, offvalue=0,
                          variable=self._var_auto())
        m.add_separator()
        m.add_command(label="隐藏到托盘", command=self.hide_window)
        m.add_command(label="退出", command=self.quit_app)
        try:
            m.tk_popup(event.x_root if event else self.root.winfo_pointerx(),
                       event.y_root if event else self.root.winfo_pointery())
        finally:
            m.grab_release()

    def _var_top(self):
        v = tk.IntVar(value=1 if self.cfg.get("always_on_top") else 0)
        v.trace_add("write", lambda *a: self.set_topmost(bool(v.get())))
        return v

    def _var_lock(self):
        v = tk.IntVar(value=1 if self.cfg.get("lock_pos") else 0)
        v.trace_add("write", lambda *a: self.set_lock(bool(v.get())))
        return v

    def _var_auto(self):
        v = tk.IntVar(value=1 if self.cfg.get("autostart") else 0)
        v.trace_add("write", lambda *a: self.set_autostart(bool(v.get())))
        return v

    def set_topmost(self, on):
        self.cfg["always_on_top"] = bool(on)
        self.root.attributes("-topmost", bool(on))
        save_cfg(self.cfg)

    def apply_opacity(self):
        try:
            op = float(self.cfg.get("opacity", 0.5))
        except Exception:
            op = 0.5
        op = min(1.0, max(0.2, op))
        self.cfg["opacity"] = op
        try:
            self.root.attributes("-alpha", op)
        except Exception:
            pass

    def set_lock(self, on):
        self.cfg["lock_pos"] = bool(on)
        save_cfg(self.cfg)

    def set_autostart(self, on):
        self.cfg["autostart"] = bool(on)
        save_cfg(self.cfg)
        ok = set_autostart(bool(on))
        if not ok and on and getattr(sys, "frozen", False):
            log_error("开机自启写入失败")

    def set_autostart_state(self):
        # 打包运行时，首次启动按配置写入注册表
        if getattr(sys, "frozen", False):
            want = bool(self.cfg.get("autostart", True))
            if want != get_autostart():
                set_autostart(want)

    # ---------- 显示/隐藏 ----------
    def hide_window(self):
        self.hidden = True
        self.save_pos()
        self.root.withdraw()

    def show_window(self):
        self.hidden = False
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", bool(self.cfg.get("always_on_top", True)))

    def toggle_window(self, icon=None, item=None):
        self.root.after(0, self._toggle_ui)

    def _toggle_ui(self):
        if self.hidden:
            self.show_window()
        else:
            self.hide_window()

    # ---------- 托盘 ----------
    def start_tray(self):
        try:
            import pystray
            img = make_tray_image()
            menu = pystray.Menu(
                pystray.MenuItem("显示 / 隐藏", self.toggle_window, default=True),
                pystray.MenuItem("设置…", lambda i, it: self.root.after(0, self.open_settings)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "开机自动启动",
                    lambda i, it: self.root.after(0, self._toggle_autostart),
                    checked=lambda it: bool(self.cfg.get("autostart")),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", lambda i, it: self.root.after(0, self.quit_app)),
            )
            self.tray = pystray.Icon(APP_ID, img, APP_NAME, menu)
            self.tray.run_detached()
        except Exception as e:
            log_error("tray: %r" % e)
            self.tray = None

    def _toggle_autostart(self):
        self.set_autostart(not self.cfg.get("autostart"))
        if self.tray:
            try:
                self.tray.update_menu()
            except Exception:
                pass

    def quit_app(self):
        try:
            self.save_pos()
        except Exception:
            pass
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    # ---------- 设置窗口 ----------
    def open_settings(self):
        if self.hidden:
            self.show_window()

        win = tk.Toplevel(self.root)
        win.title("设置 - " + APP_NAME)
        win.configure(bg="#f6f7fa")
        win.resizable(False, False)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        pad = {"padx": 12, "pady": 6}
        body = tk.Frame(win, bg="#f6f7fa")
        body.pack(fill="both", expand=True, padx=18, pady=14)

        title = tk.Label(body, text="薪资参数", bg="#f6f7fa", fg="#1b1f2a",
                         font=("Microsoft YaHei UI", 12, "bold"))
        title.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        entries = {}

        def add_row(r, label, key, hint="", init=None):
            tk.Label(body, text=label, bg="#f6f7fa", fg="#3c4354",
                     font=("Microsoft YaHei UI", 9)).grid(row=r, column=0,
                                                          sticky="w", pady=6)
            e = ttk.Entry(body, width=14, font=("Microsoft YaHei UI", 10))
            e.insert(0, str(init if init is not None else self.cfg.get(key, "")))
            e.grid(row=r, column=1, sticky="w", padx=(10, 6), pady=6)
            entries[key] = e
            if hint:
                tk.Label(body, text=hint, bg="#f6f7fa", fg="#8b93a7",
                         font=("Microsoft YaHei UI", 8)).grid(row=r, column=2,
                                                              columnspan=2,
                                                              sticky="w")
            return e

        add_row(1, "月薪（元）", "monthly_salary", "税后到手，按实际填")
        add_row(2, "每月工作天数", "work_days", "例如 22 天")
        add_row(3, "上班时间", "work_start", "格式 08:30")
        add_row(4, "午休开始", "lunch_start", "12:00")
        add_row(5, "午休结束", "lunch_end", "13:00 之后继续计费")
        add_row(6, "下班时间", "work_end", "18:00 之后按全勤计")
        add_row(7, "今日目标（元）", "goal", "留 0 表示按日薪自动算")
        try:
            op_init = int(round(float(self.cfg.get("opacity", 0.5)) * 100))
        except Exception:
            op_init = 50
        add_row(8, "不透明度（%）", "opacity", "50 = 半透明", init=op_init)

        options = tk.Frame(body, bg="#f6f7fa")
        options.grid(row=9, column=0, columnspan=4, sticky="w", pady=(8, 4))
        v_top = tk.IntVar(value=1 if self.cfg.get("always_on_top") else 0)
        v_lock = tk.IntVar(value=1 if self.cfg.get("lock_pos") else 0)
        v_auto = tk.IntVar(value=1 if self.cfg.get("autostart") else 0)
        for i, (txt, var) in enumerate((("窗口置顶", v_top),
                                        ("锁定位置", v_lock),
                                        ("开机自动启动", v_auto))):
            tk.Checkbutton(options, text=txt, variable=var, bg="#f6f7fa",
                           activebackground="#f6f7fa", fg="#3c4354",
                           font=("Microsoft YaHei UI", 9),
                           highlightthickness=0, bd=0).grid(row=0, column=i,
                                                            padx=(0, 14))

        err = tk.Label(body, text="", bg="#f6f7fa", fg="#e5484d",
                       font=("Microsoft YaHei UI", 8))
        err.grid(row=10, column=0, columnspan=4, sticky="w", pady=(6, 0))

        btns = tk.Frame(body, bg="#f6f7fa")
        btns.grid(row=11, column=0, columnspan=4, sticky="e", pady=(12, 0))

        def do_save():
            try:
                monthly = float(str(entries["monthly_salary"].get()).strip())
                if monthly <= 0:
                    raise ValueError("月薪需要大于 0")
                days = int(float(str(entries["work_days"].get()).strip()))
                if not 1 <= days <= 31:
                    raise ValueError("工作天数需在 1-31 之间")
                goal = float(str(entries["goal"].get()).strip() or 0)
                if goal < 0:
                    raise ValueError("目标不能为负数")
                opacity = int(float(str(entries["opacity"].get()).strip() or 50))
                if not 20 <= opacity <= 100:
                    raise ValueError("不透明度需在 20-100 之间")
                times = {}
                for k in ("work_start", "lunch_start", "lunch_end", "work_end"):
                    s = str(entries[k].get()).strip().replace("：", ":")
                    se = to_sec(s, -1)
                    if se < 0:
                        raise ValueError("时间格式应为 HH:MM，例如 08:30")
                    times[k] = "%02d:%02d" % (se // 3600, (se % 3600) // 60)
            except ValueError as e:
                err.config(text="填写有误：%s" % e)
                return
            except Exception:
                err.config(text="填写有误，请检查输入")
                return

            self.cfg["monthly_salary"] = monthly
            self.cfg["work_days"] = days
            self.cfg["goal"] = goal
            self.cfg.update(times)
            self.cfg["always_on_top"] = bool(v_top.get())
            self.cfg["lock_pos"] = bool(v_lock.get())
            self.cfg["autostart"] = bool(v_auto.get())
            self.cfg["opacity"] = opacity / 100.0
            save_cfg(self.cfg)
            self.root.attributes("-topmost", bool(self.cfg["always_on_top"]))
            self.apply_opacity()
            set_autostart(bool(self.cfg["autostart"]))
            if self.tray:
                try:
                    self.tray.update_menu()
                except Exception:
                    pass
            win.destroy()
            self.refresh()

        def do_reset():
            for k, v in DEFAULTS.items():
                if k in ("pos",):
                    continue
                self.cfg[k] = v

        ttk.Button(btns, text="恢复默认", command=do_reset).grid(row=0, column=0,
                                                                padx=(0, 8))
        ttk.Button(btns, text="取消", command=win.destroy).grid(row=0, column=1,
                                                              padx=(0, 8))
        ttk.Button(btns, text="保存", command=do_save).grid(row=0, column=2)

        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        x = self.root.winfo_x() + (W - w) // 2
        y = self.root.winfo_y() + (H - h) // 2
        win.geometry("+%d+%d" % (max(0, x), max(0, y)))
        win.transient(self.root)
        win.focus_force()
        try:
            win.grab_set()
        except Exception:
            pass

    # ---------- 刷新 ----------
    def refresh(self):
        self.tick(once=True)

    def tick(self, once=False):
        try:
            now = datetime.now()
            d = compute(now, self.cfg)
            self._render(d, now)
        except Exception:
            log_error("tick: " + traceback.format_exc())

        if not once:
            self.root.after(50, self.tick)

    def _render(self, d, now):
        c = self.canvas
        reached = d["reached"]
        phase = d["phase"]

        main = GOLD if reached else ACCENT
        sub_accent = GOLD if reached else ACCENT

        # 金额
        earned = d["earned"]
        s = "%.3f" % earned
        size = 33 if len(s) <= 8 else (27 if len(s) <= 10 else 21)
        c.itemconfig(self.amount, text=s, fill=(GOLD if reached else TEXT),
                     font=("Microsoft YaHei UI", size, "bold"))

        # 进度条
        pct = max(0.0, min(1.0, d["pct"]))
        fill_w = max(0.0, self.bar_w * pct)
        x1 = 30
        c.coords(self.bar, x1, 122, x1 + fill_w, 122)
        c.itemconfig(self.bar, fill=main)
        pct_text = "%.1f%%" % (pct * 100)
        if pct >= 1:
            pct_text = "100%"
        c.itemconfig(self.pct_txt, text=pct_text,
                     fill=(GOLD if reached else SUB))

        # 状态
        if phase == "before":
            status, color = "还没上班", DIM
        elif phase == "lunch":
            status, color = "午休中 · 不计费", "#f0b429"
        elif phase == "done":
            status, color = "下班啦 · 已全额到账", ACCENT if not reached else GOLD
        else:
            status, color = "搬砖中 · 钱在涨", ACCENT if not reached else GOLD

        if reached:
            status = "今日目标达成"

        c.itemconfig(self.status_txt, text=status, fill=color)
        c.itemconfig(self.dot, fill=color)

        # 主题（达标后金色化）
        if reached:
            c.itemconfig(self.card, fill="#1a1609", outline=GOLD_DIM)
            self._pulse += 0.22
            k = (math.sin(self._pulse) + 1) / 2
            r1, g1, b1 = 0x6d, 0x54, 0x20
            r2, g2, b2 = 0xff, 0xc9, 0x4d
            col = "#%02x%02x%02x" % (
                int(r1 + (r2 - r1) * k),
                int(g1 + (g2 - g1) * k),
                int(b1 + (b2 - b1) * k))
            c.itemconfig(self.glow, state="normal", outline=col)
        else:
            c.itemconfig(self.card, fill=BG, outline=BORDER)
            c.itemconfig(self.glow, state="hidden")

        # 底部信息
        c.itemconfig(self.daily_txt, text="日薪 ¥%.2f" % d["daily"],
                     fill=SUB)
        c.itemconfig(self.per_txt, text="每秒 +¥%.4f" % d["per_sec"], fill=SUB)

        if phase == "before":
            hint = "%s 开始 · 还有 %s" % (fmt_clock(d["start"]), fmt_hm(d["to_start"]))
        elif phase == "lunch":
            hint = "%s 继续 · 还剩 %s" % (fmt_clock(d["lunch_e"]), fmt_hm(d["to_lunch_end"]))
        elif phase == "done":
            hint = "今天辛苦了，钱已到位"
        else:
            hint = "距下班 %s" % fmt_hm(d["to_end"])

        if reached:
            hint = "🎉 今日目标达成，摸鱼有理"
            c.itemconfig(self.hint_txt, text=hint, fill=GOLD)
        else:
            c.itemconfig(self.hint_txt, text=hint, fill=DIM)

        c.itemconfig(self.goal_txt, text="目标 ¥%.0f" % d["goal"], fill=DIM)


def main():
    try:
        root = tk.Tk()
        root.title(APP_NAME)
        app = SalaryPet(root)
        root.protocol("WM_DELETE_WINDOW", app.quit_app)
        root.mainloop()
    except Exception:
        log_error("main: " + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()

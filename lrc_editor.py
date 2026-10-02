# -*- coding: utf-8 -*-
"""
LRC 智能歌词编辑器
功能：打开/保存 LRC、元数据标签编辑、逐行编辑、批量平移时间戳、
     排序、去重、清理空行/无效行、查找替换(正则)、增强型LRC清理、
     时间戳格式标准化、一键智能修复、多编码保存、
     音乐播放打轴（空格播放/暂停、回车打轴）、时长跳转、
     打开音频自动加载同名 LRC（反向亦然）。
依赖：Python 标准库 + pygame（播放音频）。exe 版已内置全部依赖。
"""

import json
import re
import os
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, simpledialog

META_KEYS = ("ti", "ar", "al", "by", "offset", "length", "re", "ve", "tool")

# 匹配一个时间戳: [mm:ss.xx] / [mm:ss.xxx] / [mm:ss] / [hh:mm:ss.xx]
TIME_RE = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[:.](\d{1,3}))?\]")
# 增强型 LRC 的逐字时间戳 <mm:ss.xx>
WORD_TIME_RE = re.compile(r"<\d{1,3}:\d{1,2}(?:[:.]\d{1,3})?>")
# 元数据行 [key:value]
META_RE = re.compile(r"^\[(ti|ar|al|by|offset|length|re|ve|tool):(.*)\]\s*$")

AUDIO_EXTS = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")
ENCODINGS = ["utf-8", "gbk", "utf-8-sig", "big5", "shift_jis", "latin-1"]

# ---------------------------------------------------------------- 外观 / 动画

DEFAULT_THEME = "Windows 浅色"
THEMES = {
    # Windows 原生浅色（最初版本的白色外观）
    "Windows 浅色": dict(
        bg="#f0f0f0", panel="#ffffff", field="#ffffff", field2="#e9ecef",
        border="#b6bcc6", fg="#1a1a1a", fg_muted="#5b6472", fg_dim="#9aa1ad",
        accent="#ea580c", accent_hi="#fb923c", accent_lo="#c2410c",
        sel="#0078d7", sel_fg="#ffffff", zebra="#f4f7fb", warn="#ffe9c8",
        bad="#ffd6d6", preview_bg="#fbfcfe", preview_fg="#1a1a1a",
        link="#2563eb", paused_a="#dc2626", paused_b="#fb7185",
        native=True, darkbar=False),
    "深邃黑": dict(
        bg="#16171b", panel="#1f2127", field="#252833", field2="#2b2f3a",
        border="#363b48", fg="#e7e9ee", fg_muted="#9aa1ad", fg_dim="#6b7280",
        accent="#f59e0b", accent_hi="#fbbf24", accent_lo="#b45309",
        sel="#3b4252", sel_fg="#fde68a", zebra="#22242b", warn="#3a3220",
        bad="#3c2226", preview_bg="#1a1c22", preview_fg="#c9d1dc",
        link="#60a5fa", paused_a="#dc2626", paused_b="#fb7185",
        native=False, darkbar=True),
    "墨蓝夜曲": dict(
        bg="#0f1526", panel="#151d33", field="#1b2540", field2="#223052",
        border="#31446e", fg="#e2e8f0", fg_muted="#8fa0bd", fg_dim="#5f6f8f",
        accent="#38bdf8", accent_hi="#7dd3fc", accent_lo="#0369a1",
        sel="#1e3a5f", sel_fg="#bae6fd", zebra="#182138", warn="#3a3520",
        bad="#3c2226", preview_bg="#131b30", preview_fg="#c4cede",
        link="#fbbf24", paused_a="#f43f5e", paused_b="#fb7185",
        native=False, darkbar=True),
    "暖沙护眼": dict(
        bg="#f1ebe0", panel="#faf7f0", field="#ffffff", field2="#e7dfd0",
        border="#d5c9b2", fg="#3a3226", fg_muted="#7a6f5d", fg_dim="#a89c87",
        accent="#b45309", accent_hi="#d97706", accent_lo="#92400e",
        sel="#e7d8bd", sel_fg="#3a3226", zebra="#f5efe4", warn="#f3e4c2",
        bad="#f3d4d4", preview_bg="#fbf8f1", preview_fg="#3a3226",
        link="#b45309", paused_a="#dc2626", paused_b="#f87171",
        native=False, darkbar=False),
}
PAL = dict(THEMES[DEFAULT_THEME])


def _settings_path():
    """设置文件：优先放在程序同目录（exe 免安装便携），不可写则退回家目录"""
    for base in (os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv[0] else None,
                 os.path.expanduser("~")):
        if not base:
            continue
        try:
            p = os.path.join(base, "lrc_editor_settings.json")
            with open(p, "a", encoding="utf-8"):
                pass
            return p
        except OSError:
            continue
    return None


def load_settings():
    p = _settings_path()
    if p and os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {}


def save_settings(d):
    p = _settings_path()
    if not p:
        return
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

_SCALE = 1.0  # 显示缩放系数（DPI/96），在 LrcEditor.__init__ 中测定


def px(v):
    """像素尺寸按缩放系数放大，保证高 DPI 下布局比例不变"""
    return max(1, round(v * _SCALE))


def enable_high_dpi():
    """让进程 DPI 感知：Windows 高缩放不再位图拉伸，文字界面恢复清晰"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def dark_titlebar(win, enable=True):
    """Windows 深色标题栏（enable=False 恢复浅色）"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        value = 1 if enable else 0
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE（新版/旧版）
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(ctypes.c_int(value)), 4) == 0:
                break
    except Exception:
        pass


def fade_in(win, ms=180, steps=10):
    """窗口/对话框淡入"""
    try:
        win.attributes("-alpha", 0.0)
    except tk.TclError:
        return

    def step(i=0):
        try:
            if not win.winfo_exists():
                return
            win.attributes("-alpha", min(1.0, (i + 1) / steps))
        except tk.TclError:
            return
        if i + 1 < steps:
            win.after(ms // steps, step, i + 1)

    win.after(10, step)


def fade_out_then(win, callback, ms=160, steps=8):
    """淡出后执行 callback（用于关闭窗口）"""
    def step(i=0):
        try:
            win.attributes("-alpha", max(0.0, 1 - (i + 1) / steps))
        except tk.TclError:
            return
        if i + 1 < steps:
            win.after(ms // steps, step, i + 1)
        else:
            callback()

    step()


def lerp_color(c1, c2, t):
    """两种 #rrggbb 颜色线性插值，t∈[0,1]"""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


class LrcLine:
    """一行歌词：可携带多个时间戳（毫秒），text 为歌词文本。"""

    def __init__(self, times=None, text=""):
        self.times = times or []  # list[int] 毫秒
        self.text = text

    @property
    def first_time(self):
        return self.times[0] if self.times else None


def time_to_ms(m, s, frac):
    ms = int(frac.ljust(3, "0")) if frac else 0
    return int(m) * 60000 + int(s) * 1000 + ms


def ms_to_stamp(t, digits=2):
    """毫秒 -> [mm:ss.xx]，digits 控制小数位(2 或 3)"""
    t = max(0, int(t))
    m, rem = divmod(t, 60000)
    s, ms = divmod(rem, 1000)
    if digits == 3:
        return f"[{m:02d}:{s:02d}.{ms:03d}]"
    return f"[{m:02d}:{s:02d}.{ms // 10:02d}]"


def fmt_clock(ms):
    """毫秒 -> m:ss.d 显示格式"""
    ms = max(0, int(ms))
    return f"{ms // 60000}:{ms % 60000 // 1000:02d}.{ms % 1000 // 100}"


def parse_lrc(text):
    """解析 LRC 文本 -> (metadata dict, list[LrcLine])。
    兼容：一行多时间戳、无时间戳行、增强型逐字时间戳（自动剥离）。"""
    meta = {}
    lines = []
    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        m = META_RE.match(line.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
            continue
        times = [time_to_ms(*mm.groups()) for mm in TIME_RE.finditer(line)]
        body = TIME_RE.sub("", line)
        body = WORD_TIME_RE.sub("", body).strip()  # 剥离增强型逐字时间戳
        if times:
            lines.append(LrcLine(times, body))
        elif body:
            lines.append(LrcLine([], body))  # 无时间戳行，保留待用户处理
    return meta, lines


def build_lrc(meta, lines, digits=2, sort=True, keep_no_time=False):
    """metadata + 歌词行 -> LRC 文本"""
    out = []
    for k in META_KEYS:
        if k in meta and str(meta[k]).strip():
            out.append(f"[{k}:{meta[k]}]")
    body = [ln for ln in lines if ln.times or keep_no_time]
    if sort:
        body = sorted(body, key=lambda l: l.times[0] if l.times else 10**9)
    for ln in body:
        stamps = "".join(ms_to_stamp(t, digits) for t in sorted(ln.times))
        out.append(stamps + ln.text)
    return "\n".join(out) + ("\n" if out else "")


class AudioPlayer:
    """基于 pygame.mixer.music 的音频播放器，手动跟踪播放位置（毫秒），
    以便暂停/跳转时位置准确。懒加载 pygame，未安装时给出提示。"""

    def __init__(self):
        self.pygame = None
        self.loaded_path = None
        self.length_ms = None  # 尽力获取
        self._base = 0.0       # 上次锚定的播放位置（毫秒）
        self._t0 = None        # monotonic 锚点（播放中才有）
        self._paused = False
        self.seek_ok = True    # 当前音频是否支持跳转

    @property
    def loaded(self):
        return self.loaded_path is not None

    @property
    def playing(self):
        return self._t0 is not None and not self._paused

    def _ensure_pygame(self):
        if self.pygame is None:
            try:
                import pygame
            except ImportError:
                raise RuntimeError("未安装 pygame，无法播放音频。\n"
                                   "请执行：pip install pygame\n"
                                   "（打包的 exe 已内置，无此问题）")
            # 小缓冲 = 低输出延迟（默认约 70ms，1024 样本 ≈ 23ms），
            # 打轴所听即所打的关键之一；失败则退回默认配置
            try:
                pygame.mixer.pre_init(44100, -16, 2, 1024)
                pygame.mixer.init()
            except pygame.error:
                pygame.mixer.init()
            self.pygame = pygame

    def load(self, path):
        self._ensure_pygame()
        self.stop()
        self.pygame.mixer.music.load(path)
        self.loaded_path = path
        self._base = 0.0
        self._t0 = None
        self._paused = False
        self.seek_ok = True
        self.length_ms = None
        try:  # 解码后 PCM 的精确总长（SDL_mixer 2.6+ 支持 mp3 等格式）
            self.length_ms = self.pygame.mixer.Sound(path).get_length() * 1000
        except Exception:
            if path.lower().endswith(".wav"):
                try:  # WAV 用标准库直接读帧数，零开销
                    import wave
                    with wave.open(path) as w:
                        self.length_ms = w.getnframes() / w.getframerate() * 1000
                except Exception:
                    pass

    def _play_from(self, ms):
        try:
            self.pygame.mixer.music.play(start=ms / 1000)
            self.seek_ok = True
        except Exception:  # 该格式不支持按位置起播
            self.pygame.mixer.music.play()
            self._base = 0.0
            self._t0 = time.monotonic()
            self.seek_ok = False
            return
        self._t0 = time.monotonic()

    def play(self):
        if not self.loaded:
            return
        self._play_from(self._base)
        self._paused = False

    def pause(self):
        if self.playing:
            self._base = self.get_pos()
            self.pygame.mixer.music.pause()
            self._t0 = None
            self._paused = True

    def resume(self):
        if self._paused:
            self.pygame.mixer.music.unpause()
            self._t0 = time.monotonic()
            self._paused = False

    def toggle(self):
        if self._paused:
            self.resume()
        elif self._t0 is None:  # 从未播放过 → 直接开始（修复首次按播放无效）
            self.play()
        else:
            self.pause()

    def stop(self):
        if self.pygame:
            self.pygame.mixer.music.stop()
        self._base = 0.0
        self._t0 = None
        self._paused = False

    def seek(self, ms):
        ms = max(0.0, ms)
        if not self.loaded or not self.seek_ok:
            return
        was_paused = self._paused
        vol = self.pygame.mixer.music.get_volume()
        if was_paused:  # 暂停中 seek 需短暂起播再暂停：静音避免漏出声音
            self.pygame.mixer.music.set_volume(0)
        self._base = ms
        self._play_from(ms)
        self._paused = False
        if was_paused:
            self.pygame.mixer.music.pause()
            self.pygame.mixer.music.set_volume(vol)
            self._t0 = None
            self._paused = True

    def get_pos(self):
        if self._t0 is None:
            return self._base
        return self._base + (time.monotonic() - self._t0) * 1000

    def ended(self):
        """自然播放结束（非暂停导致的静默）"""
        return (self.loaded and self._t0 is not None and not self._paused
                and not self.pygame.mixer.music.get_busy())

    def set_volume(self, v):
        if self.pygame:
            self.pygame.mixer.music.set_volume(max(0.0, min(1.0, v)))


# ---------------------------------------------------------------- GUI

class LrcEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LRC 智能歌词编辑器")
        try:
            dpi = self.winfo_fpixels("1i")
        except Exception:
            dpi = 96.0
        self.S = min(max(dpi / 96.0, 1.0), 4.0)
        global _SCALE
        _SCALE = self.S
        try:  # 字体按点数自动随 DPI 缩放
            self.tk.call("tk", "scaling", dpi / 72.0)
        except Exception:
            pass
        s = load_settings()
        self._saved = s
        self.theme_name = s.get("theme") if s.get("theme") in THEMES else DEFAULT_THEME
        global PAL
        PAL = dict(THEMES[self.theme_name])
        self.theme_var = tk.StringVar(value=self.theme_name)
        self.configure(background=PAL["bg"])
        if PAL["darkbar"]:
            dark_titlebar(self)
        self.geometry(f"{px(1080)}x{px(720)}")
        self.minsize(px(980), px(600))

        self.file_path = None
        self.encoding = tk.StringVar(value="utf-8")
        self.meta = {}
        self.lines = []
        self.audio = AudioPlayer()
        self.playlist = []       # 文件夹播放列表（音频文件绝对路径）
        self._pl_index = -1      # 当前位置
        self._meta_loading = False  # 程序化填充元数据输入框时屏蔽 trace
        self._row_tags = {}      # tree item -> 基础 tags（斑马纹/异常标记）
        self._singing_item = None
        self._slider_dragging = False
        self._undo_stack = []    # 快照栈（撤销/重做）
        self._redo_stack = []
        self._manual_scroll = 0.0  # 最近一次手动滚动歌词列表的时间

        self._setup_style()
        self._build_menu()
        self._build_ui()
        self.calib.set(int(self._saved.get("calib", 0) or 0))  # 需在状态栏创建后
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_modified(False)
        self._tick()
        fade_in(self, 220)

    # ---------- 撤销 / 重做 ----------

    def _snapshot(self):
        return (dict(self.meta),
                [LrcLine(list(l.times), l.text) for l in self.lines],
                self.file_path)

    @staticmethod
    def _snap_equal(a, b):
        if a[0] != b[0] or a[2] != b[2] or len(a[1]) != len(b[1]):
            return False
        return all(x.times == y.times and x.text == y.text for x, y in zip(a[1], b[1]))

    def _push_undo(self):
        snap = self._snapshot()
        if self._undo_stack and self._snap_equal(self._undo_stack[-1], snap):
            return
        self._undo_stack.append(snap)
        if len(self._undo_stack) > 60:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self, event=None):
        if not self._undo_stack:
            self.status.set("没有可撤销的操作")
            return "break"
        snap = self._undo_stack.pop()
        self._redo_stack.append(self._snapshot())
        self._restore(snap)
        self.status.set("↶ 已撤销")
        return "break"

    def redo(self, event=None):
        if not self._redo_stack:
            self.status.set("没有可重做的操作")
            return "break"
        snap = self._redo_stack.pop()
        self._undo_stack.append(self._snapshot())
        self._restore(snap)
        self.status.set("↷ 已重做")
        return "break"

    def _restore(self, snap):
        self.meta = snap[0]
        self.lines = [LrcLine(list(l.times), l.text) for l in snap[1]]
        self.file_path = snap[2]
        self._meta_loading = True
        try:
            for k, v in self.meta_vars.items():
                v.set(self.meta.get(k, ""))
        finally:
            self._meta_loading = False
        self.refresh()
        self._set_modified()

    # ---------- 外观 ----------

    def _setup_style(self):
        style = ttk.Style(self)
        if PAL["native"]:
            for t in ("vista", "xpnative", "winnative", "clam"):
                if t in style.theme_names():
                    style.theme_use(t)
                    break
        else:
            try:
                style.theme_use("clam")  # clam 允许完全自定义配色
            except tk.TclError:
                pass
        fams = set(tkfont.families())
        base = "Microsoft YaHei UI" if "Microsoft YaHei UI" in fams else "Segoe UI"
        self.font_base = (base, 10)
        self.option_add("*Font", self.font_base)
        if PAL["native"]:
            style.configure(".", font=self.font_base)
            style.configure("Treeview", rowheight=px(28), font=self.font_base)
            style.configure("Treeview.Heading", font=(base, 10, "bold"))
            style.configure("TLabelframe.Label", font=(base, 10, "bold"))
            return
        self.option_add("*TCombobox*Listbox.background", PAL["field"])
        self.option_add("*TCombobox*Listbox.foreground", PAL["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", PAL["sel"])
        self.option_add("*TCombobox*Listbox.selectForeground", PAL["sel_fg"])

        style.configure(".", background=PAL["bg"], foreground=PAL["fg"],
                        fieldbackground=PAL["field"], bordercolor=PAL["border"],
                        lightcolor=PAL["border"], darkcolor=PAL["border"],
                        troughcolor=PAL["field"], selectbackground=PAL["sel"],
                        selectforeground=PAL["sel_fg"], font=self.font_base)
        style.configure("TFrame", background=PAL["bg"])
        style.configure("TLabelframe", background=PAL["bg"], bordercolor=PAL["border"],
                        lightcolor=PAL["border"], darkcolor=PAL["border"])
        style.configure("TLabelframe.Label", background=PAL["bg"], foreground=PAL["accent"],
                        font=(base, 10, "bold"))
        style.configure("TLabel", background=PAL["bg"], foreground=PAL["fg"])
        style.configure("TButton", background=PAL["field2"], foreground=PAL["fg"],
                        bordercolor=PAL["border"], lightcolor=PAL["field2"],
                        darkcolor=PAL["field2"], focusthickness=0, relief="flat",
                        padding=(px(10), px(3)))
        style.map("TButton",
                  background=[("pressed", PAL["sel"]), ("active", "#343945")],
                  foreground=[("disabled", PAL["fg_dim"])])
        style.configure("Accent.TButton", background=PAL["accent_lo"], foreground="#fff7ed",
                        lightcolor=PAL["accent_lo"], darkcolor=PAL["accent_lo"],
                        bordercolor=PAL["accent_lo"], focusthickness=0)
        style.map("Accent.TButton",
                  background=[("pressed", PAL["accent"]), ("active", PAL["accent"])],
                  foreground=[("pressed", "#1b1d22"), ("active", "#1b1d22")])
        style.configure("TEntry", fieldbackground=PAL["field"], foreground=PAL["fg"],
                        insertcolor=PAL["fg"], bordercolor=PAL["border"],
                        lightcolor=PAL["border"], darkcolor=PAL["border"])
        style.configure("TCombobox", fieldbackground=PAL["field"], foreground=PAL["fg"],
                        background=PAL["field2"], arrowcolor=PAL["fg"],
                        bordercolor=PAL["border"], lightcolor=PAL["border"],
                        darkcolor=PAL["border"])
        style.map("TCombobox", fieldbackground=[("readonly", PAL["field"])],
                  foreground=[("readonly", PAL["fg"])])
        style.configure("TSpinbox", fieldbackground=PAL["field"], foreground=PAL["fg"],
                        arrowcolor=PAL["fg"], bordercolor=PAL["border"],
                        lightcolor=PAL["border"], darkcolor=PAL["border"])
        style.configure("TCheckbutton", background=PAL["bg"], foreground=PAL["fg"],
                        indicatorcolor=PAL["field"], bordercolor=PAL["border"],
                        lightcolor=PAL["border"], darkcolor=PAL["border"])
        style.map("TCheckbutton", background=[("active", PAL["bg"])],
                  indicatorcolor=[("selected", PAL["accent_lo"])])
        style.configure("TScale", background=PAL["accent"], troughcolor=PAL["field"],
                        bordercolor=PAL["bg"], lightcolor=PAL["accent"],
                        darkcolor=PAL["accent"])
        style.map("TScale", background=[("active", PAL["accent_hi"])])
        style.configure("TScrollbar", background=PAL["field2"], troughcolor=PAL["bg"],
                        bordercolor=PAL["bg"], arrowcolor=PAL["fg_muted"],
                        lightcolor=PAL["field2"], darkcolor=PAL["field2"], relief="flat")
        style.map("TScrollbar", background=[("active", PAL["sel"])])
        style.configure("Treeview", background=PAL["panel"], fieldbackground=PAL["panel"],
                        foreground=PAL["fg"], rowheight=px(28), bordercolor=PAL["border"],
                        lightcolor=PAL["border"], darkcolor=PAL["border"],
                        font=self.font_base)
        style.configure("Treeview.Heading", background=PAL["field"], foreground=PAL["fg_muted"],
                        font=(base, 10, "bold"), relief="flat", bordercolor=PAL["border"],
                        lightcolor=PAL["border"], darkcolor=PAL["border"])
        style.map("Treeview", background=[("selected", PAL["sel"])],
                  foreground=[("selected", PAL["sel_fg"])])
        style.map("Treeview.Heading", background=[("active", PAL["field2"])])

    def _style_menu(self, m):
        m.configure(bg=PAL["panel"], fg=PAL["fg"], activebackground=PAL["field2"],
                    activeforeground=PAL["accent_hi"], bd=0, relief="flat")

    def _apply_menu_theme(self, m):
        if PAL["native"]:
            m.configure(bg="SystemMenu", fg="SystemButtonText",
                        activebackground="SystemHighlight",
                        activeforeground="SystemHighlightText")
        else:
            self._style_menu(m)

    def _build_custom_menubar(self):
        old = getattr(self, "_mbar", None)
        if old:
            old.destroy()
        bar = tk.Frame(self, bg=PAL["panel"])
        self._mbar = bar
        items = (("文件", 1), ("编辑", 2), ("时间戳", 3), ("播放打轴", 4),
                 ("清理", 5), ("视图", 6), ("帮助", 7))
        for text, mi in items:
            lbl = tk.Label(bar, text=text, bg=PAL["panel"], fg=PAL["fg"],
                           padx=px(12), pady=px(7), font=self.font_base, cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>",
                     lambda e, m=self._menus[mi], l=lbl: self._post_menu(m, l))
            lbl.bind("<Enter>", lambda e, l=lbl: l.config(bg=PAL["field2"]))
            lbl.bind("<Leave>", lambda e, l=lbl: l.config(bg=PAL["panel"]))
        target = None
        for w in self.winfo_children():
            if w is old or isinstance(w, tk.Menu) or not w.winfo_manager():
                continue
            target = w  # 第一个被 pack 管理的控件 = 当前内容区顶部
            break
        if target:
            bar.pack(fill="x", before=target)
        else:
            bar.pack(fill="x")

    def _post_menu(self, menu, lbl):
        try:
            menu.tk_popup(lbl.winfo_rootx(),
                          lbl.winfo_rooty() + lbl.winfo_height())
        finally:
            menu.grab_release()

    def set_theme(self, name):
        """切换皮肤：更新样式引擎、全局调色板与已创建控件的配色，并记忆选择"""
        if name not in THEMES:
            return
        self.theme_name = name
        global PAL
        PAL = dict(THEMES[name])
        self.theme_var.set(name)
        self._setup_style()
        self._apply_theme_widgets()
        self._build_menu()  # 菜单整体重建，确保菜单栏配色生效（Tk 菜单栏不支持动态改色）
        save_settings({"theme": name, "calib": self.calib.get()})
        self.status.set(f"已切换皮肤：{name}")

    def _apply_theme_widgets(self):
        # DWM 标题栏属性在窗口映射后设置才稳定生效，稍作延迟
        self.after(60, lambda: dark_titlebar(self, PAL["darkbar"]))
        self.configure(background=PAL["bg"])
        self.preview.configure(background=PAL["preview_bg"], fg=PAL["preview_fg"],
                               insertbackground=PAL["fg"],
                               selectbackground=PAL["sel"],
                               selectforeground=PAL["sel_fg"])
        self.pl_list.configure(bg=PAL["panel"], fg=PAL["fg"],
                               selectbackground=PAL["sel"],
                               selectforeground=PAL["sel_fg"])
        self.wv_note.configure(foreground=PAL["accent"])
        self.wv_singing.configure(foreground=PAL["accent"])
        self.wv_seek_preview.configure(foreground=PAL["link"])
        self.wv_hint.configure(foreground=PAL["fg_dim"])
        self.empty_state.configure(foreground=PAL["fg_dim"])
        self.tree.tag_configure("odd", background=PAL["zebra"])
        self.tree.tag_configure("warn", background=PAL["warn"])
        self.tree.tag_configure("bad", background=PAL["bad"])
        self.tree.tag_configure("singing", foreground=PAL["accent"])
        for m in self._menus:
            self._apply_menu_theme(m)

    # ---------- UI 构建 ----------

    def _build_menu(self):
        mb = tk.Menu(self)
        m_file = tk.Menu(mb, tearoff=0)
        m_file.add_command(label="打开 LRC…（同名音频一起加载）", accelerator="Ctrl+O",
                           command=self.open_file)
        m_file.add_command(label="打开音频…（同名 LRC 一起加载）", command=self.open_audio)
        m_file.add_command(label="打开文件夹…（建立播放列表）", command=self.open_folder)
        m_file.add_separator()
        m_file.add_command(label="保存", accelerator="Ctrl+S", command=self.save_file)
        m_file.add_command(label="另存为…", accelerator="Ctrl+Shift+S", command=self.save_as)
        m_file.add_separator()
        m_file.add_command(label="退出", command=self._on_close)
        mb.add_cascade(label="文件", menu=m_file)

        m_edit = tk.Menu(mb, tearoff=0)
        m_edit.add_command(label="添加歌词行", command=self.add_line)
        m_edit.add_command(label="编辑选中行", command=self.edit_line)
        m_edit.add_command(label="删除选中行", accelerator="Del", command=self.delete_lines)
        m_edit.add_separator()
        m_edit.add_command(label="查找替换…", accelerator="Ctrl+H", command=self.find_replace)
        mb.add_cascade(label="编辑", menu=m_edit)

        m_time = tk.Menu(mb, tearoff=0)
        m_time.add_command(label="平移时间戳…（整体/选中行）", command=self.shift_times)
        m_time.add_command(label="按时间排序", command=self.sort_lines)
        m_time.add_command(label="时间戳格式标准化", command=self.normalize_stamps)
        mb.add_cascade(label="时间戳", menu=m_time)

        m_play = tk.Menu(mb, tearoff=0)
        m_play.add_command(label="播放 / 暂停", accelerator="空格", command=self.toggle_play)
        m_play.add_command(label="停止", command=lambda: self._audio_stop())
        m_play.add_separator()
        m_play.add_command(label="快退 2 秒", accelerator="Ctrl+←", command=lambda: self._audio_seek(-2000))
        m_play.add_command(label="快进 2 秒", accelerator="Ctrl+→", command=lambda: self._audio_seek(2000))
        m_play.add_command(label="跳转到指定时长…", accelerator="Ctrl+G", command=self.jump_to_time)
        m_play.add_command(label="跳到选中句", accelerator="Ctrl+J", command=self.jump_to_selected)
        m_play.add_separator()
        m_play.add_command(label="上一首", accelerator="Ctrl+PgUp", command=self.prev_track)
        m_play.add_command(label="下一首", accelerator="Ctrl+PgDn", command=self.next_track)
        m_play.add_separator()
        m_play.add_command(label="打轴选中行", accelerator="回车", command=self.stamp_selected)
        m_play.add_command(label="设选中句为首句开头（后续句同步平移）", command=self.set_as_first)
        mb.add_cascade(label="播放打轴", menu=m_play)

        m_clean = tk.Menu(mb, tearoff=0)
        m_clean.add_command(label="删除空文本行", command=lambda: self.clean_lines("empty"))
        m_clean.add_command(label="删除无时间戳行", command=lambda: self.clean_lines("no_time"))
        m_clean.add_command(label="删除重复时间戳", command=lambda: self.clean_lines("dup"))
        m_clean.add_separator()
        m_clean.add_command(label="★ 一键智能修复", accelerator="F9", command=self.smart_fix)
        mb.add_cascade(label="清理", menu=m_clean)

        m_view = tk.Menu(mb, tearoff=0)
        for _name in THEMES:
            m_view.add_radiobutton(label=_name, variable=self.theme_var, value=_name,
                                   command=lambda: self.set_theme(self.theme_var.get()))
        mb.add_cascade(label="视图", menu=m_view)

        m_help = tk.Menu(mb, tearoff=0)
        m_help.add_command(label="关于", command=lambda: messagebox.showinfo(
            "关于", "LRC 智能歌词编辑器\n\n"
                    "歌词编辑：多时间戳、增强型逐字LRC清理、批量平移、\n"
                    "正则替换、智能修复、多编码保存\n"
                    "打轴：空格播放/暂停，回车打轴，进度条/时长跳转，\n"
                    "打开音频自动加载同名 LRC"))
        mb.add_cascade(label="帮助", menu=m_help)
        self._menus = (mb, m_file, m_edit, m_time, m_play, m_clean, m_view, m_help)
        for m in self._menus:
            self._apply_menu_theme(m)
        if PAL["native"]:
            if getattr(self, "_mbar", None):
                self._mbar.destroy()
                self._mbar = None
            self.config(menu=mb)
        else:
            # Windows 的菜单栏条纹由系统绘制，不受 tk 配色影响；
            # 深色皮肤改用自绘菜单栏（下拉菜单本身按 tk 配色正常绘制）
            self.config(menu="")
            self._build_custom_menubar()

    def _build_ui(self):
        # 顶部：文件 & 元数据
        top = ttk.LabelFrame(self, text="歌曲信息（元数据标签）")
        top.pack(fill="x", padx=px(10), pady=(px(10), px(4)))
        self.meta_vars = {}
        for i, (key, label) in enumerate([("ti", "标题"), ("ar", "歌手"),
                                          ("al", "专辑"), ("by", "制作"), ("offset", "偏移ms")]):
            ttk.Label(top, text=label).grid(row=0, column=i * 2, padx=(px(8), px(2)), pady=px(6))
            v = tk.StringVar()
            e = ttk.Entry(top, textvariable=v, width=14)
            e.grid(row=0, column=i * 2 + 1, padx=(px(0), px(8)))
            v.trace_add("write", lambda *a, k=key: self._meta_changed(k))
            e.bind("<FocusIn>", lambda ev: self._push_undo())  # 元数据改动可撤销
            self.meta_vars[key] = v

        # 音频 / 打轴栏
        audio = ttk.LabelFrame(
            self, text="音乐播放打轴　—　空格 播放/暂停 ｜ 回车 给选中行打当前时间戳并跳到下一行")
        audio.pack(fill="x", padx=px(10), pady=px(4))

        row1 = ttk.Frame(audio)
        row1.pack(fill="x", padx=px(8), pady=(px(6), px(0)))
        ttk.Button(row1, text="📂 打开文件夹", command=self.open_folder).pack(side="left")
        ttk.Button(row1, text="⏮ 上一首", width=9, command=self.prev_track).pack(side="left", padx=(px(6), px(0)))
        ttk.Button(row1, text="下一首 ⏭", width=9, command=self.next_track).pack(side="left", padx=px(2))
        ttk.Button(row1, text="📁 打开音频", command=self.open_audio).pack(side="left", padx=(px(6), px(0)))
        self.btn_play = ttk.Button(row1, text="▶ 播放", width=9, style="Accent.TButton",
                                   command=self.toggle_play)
        self.btn_play.pack(side="left", padx=px(5))
        ttk.Button(row1, text="⏹ 停止", width=7, command=lambda: self._audio_stop()).pack(side="left", padx=px(5))
        ttk.Button(row1, text="⇤ 2s", width=5, command=lambda: self._audio_seek(-2000)).pack(side="left", padx=px(2))
        ttk.Button(row1, text="2s ⇥", width=5, command=lambda: self._audio_seek(2000)).pack(side="left", padx=px(2))
        ttk.Button(row1, text="⏱ 跳转时长…", command=self.jump_to_time).pack(side="left", padx=(px(10), px(2)))
        ttk.Button(row1, text="▶ 选中句", command=self.jump_to_selected).pack(side="left", padx=px(2))
        self.time_lbl = ttk.Label(row1, text="--:--.- / --:--.-", font=("Consolas", 12))
        self.time_lbl.pack(side="right", padx=px(6))
        ttk.Label(row1, text="音量").pack(side="right")
        self.vol = tk.DoubleVar(value=0.8)
        ttk.Scale(row1, from_=0, to=1, variable=self.vol, length=90,
                  command=lambda v: self.audio.set_volume(float(v))).pack(side="right", padx=(px(0), px(6)))

        row2 = ttk.Frame(audio)
        row2.pack(fill="x", padx=px(8), pady=(px(2), px(8)))
        self.seek_var = tk.DoubleVar(value=0)
        self.seek_scale = ttk.Scale(row2, from_=0, to=1, variable=self.seek_var,
                                    command=self._slider_moved)
        self.seek_scale.pack(side="left", fill="x", expand=True, padx=(px(2), px(10)))
        self.seek_scale.bind("<ButtonPress-1>", lambda e: setattr(self, "_slider_dragging", True))
        self.seek_scale.bind("<ButtonRelease-1>", self._slider_seek)
        self.seek_preview = tk.StringVar(value="")
        self.wv_seek_preview = ttk.Label(row2, textvariable=self.seek_preview,
                                         foreground=PAL["link"], width=30)
        self.wv_seek_preview.pack(side="left")
        self.follow = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="跟随当前句", variable=self.follow).pack(side="left")
        self.btn_stamp = ttk.Button(row2, text="◎ 打轴 (回车)", style="Accent.TButton",
                                    command=self.stamp_selected)
        self.btn_stamp.pack(side="left", padx=(px(10), px(0)))

        row3 = ttk.Frame(audio)
        row3.pack(fill="x", padx=px(10), pady=(px(0), px(6)))
        self.wv_note = ttk.Label(row3, text="♪", foreground=PAL["accent"],
                                 font=(self.font_base[0], 11, "bold"))
        self.wv_note.pack(side="left")
        self.now_singing = tk.StringVar(value="（未加载音频 — 点『打开音频』，同名 LRC 会自动一起加载）")
        self.wv_singing = ttk.Label(row3, textvariable=self.now_singing,
                                    foreground=PAL["accent"])
        self.wv_singing.pack(
            side="left", fill="x", expand=True, padx=(px(6), px(0)))
        # 打轴校准：补偿固定偏差（人耳反应/系统输出延迟），正=延后，负=提前
        ttk.Label(row3, text="打轴校准(ms)").pack(side="left", padx=(px(8), px(2)))
        self.calib = tk.IntVar(value=0)
        ttk.Spinbox(row3, from_=-2000, to=2000, increment=10, width=6,
                    textvariable=self.calib).pack(side="left")
        self.calib.trace_add("write", lambda *a: (
            self.status.set(
                f"打轴校准 = {self.calib.get():+d}ms（回车打轴/设为首句的时间点会加上此值）"),
            save_settings({"theme": self.theme_name, "calib": self.calib.get()})))

        # 中部：歌词行列表 + 播放列表面板（打开文件夹后出现）
        midwrap = ttk.Frame(self)
        midwrap.pack(fill="both", expand=True, padx=px(10), pady=px(4))

        self.pl_frame = ttk.LabelFrame(midwrap, text="播放列表")
        self.pl_list = tk.Listbox(self.pl_frame, width=30, exportselection=False,
                                  font=self.font_base, activestyle="none",
                                  bg=PAL["panel"], fg=PAL["fg"],
                                  selectbackground=PAL["sel"], selectforeground=PAL["sel_fg"],
                                  highlightthickness=0)
        plsb = ttk.Scrollbar(self.pl_frame, orient="vertical", command=self.pl_list.yview)
        self.pl_list.configure(yscrollcommand=plsb.set)
        self.pl_list.pack(side="left", fill="both", expand=True)
        plsb.pack(side="right", fill="y")
        self.pl_list.bind("<Double-1>", lambda e: self.switch_track(self.pl_list.nearest(e.y)))

        mid = ttk.LabelFrame(midwrap, text="歌词行（双击编辑 ｜ Ctrl/Shift 多选批量操作 ｜ 右键菜单：从某句开始播放）")
        mid.pack(side="left", fill="both", expand=True)
        cols = ("no", "time", "text", "play")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("no", text="#")
        self.tree.heading("time", text="时间戳")
        self.tree.heading("text", text="歌词文本")
        self.tree.heading("play", text="▶")
        self.tree.column("no", width=px(50), anchor="center", stretch=False)
        self.tree.column("time", width=px(190), anchor="center", stretch=False)
        self.tree.column("text", width=px(590))
        self.tree.column("play", width=px(44), anchor="center", stretch=False)
        vs = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.vsb = vs
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        # 无歌词时的占位提示
        self.empty_state = ttk.Label(
            mid, justify="center", foreground=PAL["fg_dim"],
            font=(self.font_base[0], 13),
            text="［ 无 LRC 文件 ］\n\n"
                 "打开音频会自动查找同名歌词；没有则显示本提示\n"
                 "打轴创建：按空格播放，每句开始时按回车\n"
                 "手工录入：点下方『＋ 添加行』")
        self.empty_state.place(relx=0.5, rely=0.42, anchor="center")
        self.tree.bind("<Double-1>", lambda e: self.edit_line())
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Motion>", self._on_tree_motion)
        # 手动滚动歌词时暂停自动跟随
        self.tree.bind("<MouseWheel>", self._note_manual_scroll)
        vs.bind("<ButtonPress-1>", self._note_manual_scroll)
        vs.bind("<B1-Motion>", self._note_manual_scroll)
        self.tree.tag_configure("odd", background=PAL["zebra"])
        self.tree.tag_configure("warn", background=PAL["warn"])
        self.tree.tag_configure("bad", background=PAL["bad"])
        self.tree.tag_configure("singing", foreground=PAL["accent"],
                                font=(self.font_base[0], 10, "bold"))

        # 右键菜单
        self.ctx = tk.Menu(self, tearoff=0)
        self.tree.bind("<Button-3>", self._show_ctx)

        # 按钮条
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=px(10), pady=px(2))
        for text, cmd in [("＋ 添加行", self.add_line), ("✎ 编辑行", self.edit_line),
                          ("－ 删除行", self.delete_lines), ("⇅ 排序", self.sort_lines),
                          ("⇄ 平移时间…", self.shift_times), ("🔍 查找替换", self.find_replace),
                          ("★ 智能修复", self.smart_fix)]:
            ttk.Button(btns, text=text, command=cmd).pack(side="left", padx=px(3))
        ttk.Button(btns, text="↶ 撤销 (Ctrl+Z)", command=self.undo).pack(side="left", padx=(px(14), px(3)))

        # 快速平移条（直接在主页完成，无需二级窗口）
        shifts = ttk.Frame(self)
        shifts.pack(fill="x", padx=px(10), pady=px(2))
        ttk.Label(shifts, text="快速平移：").pack(side="left")
        for text, ms in [("⇤ 1s", -1000), ("⇤ 0.5s", -500), ("⇤ 0.25s", -250),
                         ("0.25s ⇥", 250), ("0.5s ⇥", 500), ("1s ⇥", 1000)]:
            ttk.Button(shifts, text=text, width=8,
                       command=lambda d=ms: self.quick_shift(d)).pack(side="left", padx=px(2))
        self.wv_hint = ttk.Label(shifts,
                                 text="（提前 ⇤ / 延后 ⇥；选中行只平移选中行，否则全部；Ctrl+Z 可撤销）",
                                 foreground=PAL["fg_dim"])
        self.wv_hint.pack(side="left", padx=px(8))

        # 底部：预览 + 编码
        bottom = ttk.Frame(self)
        bottom.pack(fill="both", padx=px(10), pady=(px(2), px(4)))
        pvf = ttk.LabelFrame(bottom, text="LRC 预览（实时）")
        pvf.pack(side="left", fill="both", expand=True)
        self.preview = tk.Text(pvf, height=7, wrap="none", state="disabled",
                               font=("Consolas", 10), background=PAL["preview_bg"],
                               fg=PAL["preview_fg"], insertbackground=PAL["fg"],
                               selectbackground=PAL["sel"], selectforeground=PAL["sel_fg"],
                               relief="flat", highlightthickness=0)
        self.preview.pack(fill="both", expand=True)
        optf = ttk.Frame(bottom)
        optf.pack(side="right", fill="y", padx=(px(8), px(0)))
        lf = ttk.LabelFrame(optf, text="保存选项")
        lf.pack(fill="y")
        ttk.Label(lf, text="编码").grid(row=0, column=0, padx=px(6), pady=px(4), sticky="e")
        ttk.Combobox(lf, textvariable=self.encoding, values=ENCODINGS,
                     width=10, state="readonly").grid(row=0, column=1, pady=px(4))
        ttk.Label(lf, text="毫秒位数").grid(row=1, column=0, padx=px(6), sticky="e")
        self.digits = tk.StringVar(value="2")
        ttk.Combobox(lf, textvariable=self.digits, values=["2", "3"],
                     width=10, state="readonly").grid(row=1, column=1, pady=px(4))
        self.keep_no_time = tk.BooleanVar(value=False)
        ttk.Checkbutton(lf, text="保留无时间戳行", variable=self.keep_no_time,
                        command=self.refresh).grid(row=2, columnspan=2, padx=px(6), sticky="w")
        ttk.Button(lf, text="刷新预览", command=self.refresh).grid(row=3, columnspan=2, pady=px(6))

        # 状态栏
        bar = ttk.Frame(self, relief="sunken")
        bar.pack(fill="x", side="bottom")
        self.status = tk.StringVar(value="就绪 — 打开音频或 LRC 文件开始")
        ttk.Label(bar, textvariable=self.status, anchor="w").pack(side="left", fill="x", expand=True)
        self.count_lbl = ttk.Label(bar, anchor="e")
        self.count_lbl.pack(side="right", padx=px(6))

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.open_file())
        self.bind("<Control-Prior>", lambda e: None if self._typing() else self.prev_track())
        self.bind("<Control-Next>", lambda e: None if self._typing() else self.next_track())
        self.bind("<Control-s>", lambda e: self.save_file())
        self.bind("<Control-S>", lambda e: self.save_as())
        self.bind("<Control-h>", lambda e: self.find_replace())
        self.bind("<Control-f>", lambda e: self.find_replace())
        self.bind("<Control-g>", lambda e: self.jump_to_time())
        self.bind("<Control-j>", lambda e: self.jump_to_selected())
        self.bind("<Control-Left>", lambda e: None if self._typing() else self._audio_seek(-2000))
        self.bind("<Control-Right>", lambda e: None if self._typing() else self._audio_seek(2000))
        self.bind("<F9>", lambda e: self.smart_fix())
        self.bind("<Delete>", lambda e: self.delete_lines())
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-y>", self.redo)
        self.bind("<Control-Z>", self.redo)  # Ctrl+Shift+Z
        self.bind("<space>", self._on_space)
        self.bind("<Return>", self._on_return)
        self.bind("<KP_Enter>", self._on_return)

    def _typing(self):
        w = self.focus_get()
        return w is not None and w.winfo_class() in ("Entry", "Text", "TCombobox", "Spinbox")

    def _on_space(self, event):
        if self._typing() or not self.audio.loaded:
            return
        self.toggle_play()
        return "break"

    def _on_return(self, event):
        if self._typing() or not self.audio.loaded:
            return
        self.stamp_selected()
        return "break"

    # ---------- 状态辅助 ----------

    def _set_modified(self, flag=True):
        self._modified = flag
        name = os.path.basename(self.file_path) if self.file_path else "未命名"
        self.title(f"LRC 智能歌词编辑器 — {name}{' *' if flag else ''}")

    def _meta_changed(self, key):
        if self._meta_loading:  # 程序化填充不当作用户修改
            return
        v = self.meta_vars[key].get()
        if v.strip():  # 空标签不进模型，避免污染 meta dict
            self.meta[key] = v
        else:
            self.meta.pop(key, None)
        self._set_modified()
        self._schedule_preview()

    def _schedule_preview(self):
        if not getattr(self, "_pv_job", None):
            self._pv_job = self.after(300, self.refresh)

    def _on_close(self):
        if self._modified:
            r = messagebox.askyesnocancel("退出", "歌词已修改但未保存，是否保存？")
            if r is None:
                return
            if r and not self.save_file():
                return
        self.audio.stop()
        fade_out_then(self, self.destroy)

    # ---------- 打开 / 保存 ----------

    def _read_text_auto(self, path):
        """按 BOM/UTF-8/GBK 依次尝试解码"""
        raw = open(path, "rb").read()
        for e in ("utf-8-sig", "utf-8", "gbk"):
            try:
                return raw.decode(e), e
            except UnicodeDecodeError:
                continue
        return raw.decode("gbk", errors="replace"), "gbk"

    def _load_lrc(self, path):
        text, enc = self._read_text_auto(path)
        self.file_path = path
        self.encoding.set(enc if enc != "utf-8-sig" else "utf-8")
        self.meta, self.lines = parse_lrc(text)
        self._meta_loading = True
        try:
            for k, v in self.meta_vars.items():
                v.set(self.meta.get(k, ""))
        finally:
            self._meta_loading = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.refresh()
        self._set_modified(False)
        return len(self.lines)

    def _confirm_save(self, action):
        """有未保存修改时询问：是=保存后继续，否=放弃，取消=中止。返回是否可继续"""
        if not self._modified:
            return True
        r = messagebox.askyesnocancel("未保存", f"当前歌词已修改未保存。\n\n是否保存后{action}？")
        if r is None:
            return False
        if r:
            return self.save_file()
        return True

    def open_file(self):
        if not self._confirm_save("打开新文件"):
            return
        path = filedialog.askopenfilename(
            title="打开 LRC 文件", filetypes=[("LRC 歌词", "*.lrc"), ("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            n = self._load_lrc(path)
        except OSError as ex:
            messagebox.showerror("错误", f"无法读取文件：\n{ex}")
            return
        msg = f"已打开 {path}（编码 {self.encoding.get()}，{n} 行歌词）"
        msg += self._auto_load_matching_audio(path)
        self.status.set(msg)

    def open_audio(self):
        path = filedialog.askopenfilename(
            title="打开音频文件", filetypes=[("音频", "*.mp3 *.wav *.ogg *.flac *.m4a *.aac"),
                                             ("所有文件", "*.*")])
        if not path:
            return
        try:
            self.audio.load(path)
        except Exception as ex:
            messagebox.showerror("错误", f"无法加载音频：\n{ex}")
            return
        self.audio.set_volume(self.vol.get())
        self._update_slider_range()
        self.now_singing.set(f"♪ {os.path.basename(path)}")
        if path in self.playlist:  # 同步播放列表选中
            self._pl_index = self.playlist.index(path)
            self._sync_playlist_selection()
        msg = f"已加载音频 {os.path.basename(path)}"
        msg += self._auto_load_matching_lrc(path)
        self.status.set(msg)

    # ---------- 文件夹播放列表 ----------

    def open_folder(self):
        d = filedialog.askdirectory(title="选择音乐文件夹")
        if not d:
            return
        files = [os.path.join(d, n) for n in sorted(os.listdir(d), key=str.lower)
                 if n.lower().endswith(AUDIO_EXTS)]
        if not files:
            messagebox.showinfo("提示", "该文件夹中没有音频文件\n（支持 mp3/wav/ogg/flac/m4a/aac）")
            return
        self.playlist = files
        self.pl_frame.pack(side="right", fill="y", padx=(px(6), px(0)))
        self._sync_playlist_selection()
        self.switch_track(0, force=True)

    def _sync_playlist_selection(self):
        self.pl_list.delete(0, "end")
        for i, p in enumerate(self.playlist):
            mark = "▶ " if i == self._pl_index else "　 "
            self.pl_list.insert("end", mark + os.path.basename(p))
        if 0 <= self._pl_index < len(self.playlist):
            self.pl_list.selection_clear(0, "end")
            self.pl_list.selection_set(self._pl_index)
            self.pl_list.see(self._pl_index)
        self.pl_frame.config(text=f"播放列表（{self._pl_index + 1}/{len(self.playlist)}）"
                             if self.playlist else "播放列表")

    def prev_track(self):
        self._step_track(-1)

    def next_track(self):
        self._step_track(1)

    def _step_track(self, d):
        if not self.playlist:
            self.status.set("请先打开文件夹建立播放列表（文件菜单 → 打开文件夹）")
            return
        self.switch_track(self._pl_index + d)

    def switch_track(self, idx, force=False):
        """切换到播放列表第 idx 首（循环）；有未保存修改先确认保存。
        每首歌对应自己的歌词：切换时先收起当前内容，再加载新曲的同名 LRC（如有）"""
        if not self.playlist:
            return
        n = len(self.playlist)
        idx %= n
        if idx == self._pl_index and not force:
            return
        if self._modified and not self._confirm_save("切换到其他歌曲"):
            return
        # 收起当前歌词（每首曲子各自的歌词互不混杂）
        self.meta, self.lines = {}, []
        self.file_path = None
        self._meta_loading = True
        try:
            for k, v in self.meta_vars.items():
                v.set("")
        finally:
            self._meta_loading = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.refresh()
        self._set_modified(False)  # 旧内容已收起，不算未保存修改
        path = self.playlist[idx]
        try:
            self.audio.load(path)
        except Exception as ex:
            self._pl_index = idx
            self._sync_playlist_selection()
            messagebox.showerror("错误", f"无法加载音频：\n{ex}")
            return
        self.audio.set_volume(self.vol.get())
        self._update_slider_range()
        self._pl_index = idx
        self._sync_playlist_selection()
        self.now_singing.set(f"♪ {os.path.basename(path)}")
        msg = f"▶ {idx + 1}/{n} {os.path.basename(path)}"
        msg += self._auto_load_matching_lrc(path)
        self.status.set(msg)

    def _auto_load_matching_audio(self, lrc_path):
        """打开 LRC 时自动加载同名音频，返回附加状态文本"""
        stem = os.path.splitext(lrc_path)[0]
        for ext in AUDIO_EXTS:
            p = stem + ext
            if os.path.exists(p):
                try:
                    self.audio.load(p)
                except Exception:
                    return ""
                self.audio.set_volume(self.vol.get())
                self._update_slider_range()
                self.now_singing.set(f"♪ {os.path.basename(p)}")
                return f"　＋ 已自动加载同名音频 {os.path.basename(p)}"
        return ""

    def _auto_load_matching_lrc(self, audio_path):
        """打开音频时自动加载同名 LRC，返回附加状态文本"""
        stem = os.path.splitext(audio_path)[0]
        for ext in (".lrc", ".LRC"):
            p = stem + ext
            if os.path.exists(p):
                if self._modified and (self.lines or self.meta):
                    if not messagebox.askyesno("加载同名歌词",
                                               "当前歌词未保存，加载同名 LRC 将覆盖，是否继续？"):
                        return "　（同名 LRC 存在，未加载）"
                try:
                    n = self._load_lrc(p)
                except OSError:
                    return ""
                return f"　＋ 已自动加载同名歌词 {os.path.basename(p)}（{n} 行）"
        if not self.lines and not self.meta:
            return "　（未找到同名 LRC — 按空格播放，回车即可打轴）"
        return ""

    def save_as(self):
        path = filedialog.asksaveasfilename(
            title="另存为 LRC", defaultextension=".lrc",
            filetypes=[("LRC 歌词", "*.lrc")],
            initialfile=os.path.basename(self.file_path or "lyrics.lrc"))
        if not path:
            return False
        self.file_path = path
        return self.save_file()

    def save_file(self):
        if not self.file_path:
            return self.save_as()
        text = build_lrc(self.meta, self.lines, digits=int(self.digits.get()),
                         sort=True, keep_no_time=self.keep_no_time.get())
        try:
            with open(self.file_path, "w", encoding=self.encoding.get(), newline="\n") as f:
                f.write(text)
        except (OSError, UnicodeEncodeError) as ex:
            messagebox.showerror("错误", f"保存失败：\n{ex}\n\n可尝试更换编码（如 gbk → utf-8）")
            return False
        self._set_modified(False)
        self.status.set(f"已保存到 {self.file_path}（编码 {self.encoding.get()}）")
        return True

    # ---------- 列表刷新 ----------

    def refresh(self):
        self._pv_job = None
        self._singing_item = None
        self.tree.delete(*self.tree.get_children())
        self._row_tags.clear()
        sorted_lines = sorted(self.lines, key=lambda l: l.first_time if l.times else 10**9)
        prev = None
        for i, ln in enumerate(sorted_lines, 1):
            stamp = (" / ".join(ms_to_stamp(t, int(self.digits.get())) for t in sorted(ln.times))
                     if ln.times else "⚠ 无时间戳")
            tags = []
            if i % 2 == 0:
                tags.append("odd")
            if not ln.times:
                tags.append("bad")
            elif prev is not None and ln.times[0] == prev:
                tags.append("warn")
            if ln.times:
                prev = ln.times[0]
            if not ln.text.strip():
                tags.append("warn")
            item = self.tree.insert("", "end",
                                    values=(i, stamp, ln.text, "▶" if ln.times else ""),
                                    tags=tuple(tags))
            self._row_tags[item] = tuple(tags)
        # 预览
        text = build_lrc(self.meta, self.lines, digits=int(self.digits.get()),
                         sort=True, keep_no_time=self.keep_no_time.get())
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")
        self.count_lbl.config(text=f"{len(self.lines)} 行")
        # 无歌词占位提示的显隐
        if self.lines or self.meta:
            self.empty_state.place_forget()
        else:
            self.empty_state.place(relx=0.5, rely=0.42, anchor="center")

    def _sorted_index(self):
        return sorted(range(len(self.lines)),
                      key=lambda i: self.lines[i].first_time if self.lines[i].times else 10**9)

    def _selected_lines(self):
        sel = set(self.tree.selection())
        children = self.tree.get_children()
        return [self.lines[self._sorted_index()[children.index(item)]] for item in sel]

    # ---------- 行编辑 ----------

    def _parse_stamp_input(self, s):
        """'mm:ss.xx' 或 'mm:ss' -> 毫秒；非法返回 None"""
        m = re.fullmatch(r"\s*(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\s*", s)
        if not m:
            return None
        return time_to_ms(*m.groups())

    def add_line(self):
        s = simpledialog.askstring(
            "添加歌词行", "输入时间戳和歌词，格式：mm:ss.xx 歌词文本\n"
            "（可多个时间戳：00:12.00 / 00:30.50 合唱部分）", parent=self)
        if not s:
            return
        m = re.match(r"\s*((?:\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?[\s,/]*)+)\s*(.*)", s)
        if not m:
            messagebox.showwarning("格式错误", "无法识别，请按 mm:ss.xx 歌词 格式输入")
            return
        times = [self._parse_stamp_input(t) for t in re.split(r"[\s,/]+", m.group(1)) if t]
        times = [t for t in times if t is not None]
        self._push_undo()
        self.lines.append(LrcLine(times, m.group(2)))
        self._set_modified()
        self.refresh()
        self.status.set(f"已添加 1 行（{len(times)} 个时间戳）")

    def edit_line(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选中（或双击）一行")
            return
        idx = self.tree.index(sel[0])
        ln = self.lines[self._sorted_index()[idx]]
        stamp_str = "/".join(f"{t // 60000:02d}:{t % 60000 / 1000:04.2f}" for t in sorted(ln.times))
        dlg = EditLineDialog(self, stamp_str, ln.text)
        self.wait_window(dlg)
        if dlg.result:
            self._push_undo()
            times = [self._parse_stamp_input(t) for t in re.split(r"[\s,/]+", dlg.result[0]) if t]
            ln.times = [t for t in times if t is not None]
            ln.text = dlg.result[1]
            self._set_modified()
            self.refresh()

    def delete_lines(self):
        targets = self._selected_lines()
        if not targets:
            return
        self._push_undo()
        for ln in targets:
            self.lines.remove(ln)
        self._set_modified()
        self.refresh()
        self.status.set(f"已删除 {len(targets)} 行")

    # ---------- 播放 / 跳转 / 打轴 ----------

    def toggle_play(self):
        if not self.audio.loaded:
            self.open_audio()
            return
        if self.audio.ended():
            self.audio.stop()
            self.audio.play()
            return
        self.audio.toggle()
        if self.audio._paused:  # 暂停横幅即时显示，不等轮询
            pos = self.audio.get_pos()
            cur = self._lyric_at(pos)
            self.now_singing.set(
                f"⏸ 已暂停于 {fmt_clock(pos)}：{cur or '（间奏）'}"
                f" — 可右键歌词句『设为首句开头』")
        self._refresh_time_display()  # 暂停/播放瞬间立即刷新，不等下一次轮询

    def _refresh_time_display(self):
        a = self.audio
        if not a.loaded:
            return
        pos = a.get_pos()
        total = fmt_clock(a.length_ms) if a.length_ms else "--:--.-"
        self.time_lbl.config(text=f"{fmt_clock(pos)} / {total}")
        if not self._slider_dragging and a.length_ms:
            self.seek_var.set(min(pos, a.length_ms))

    def _audio_stop(self):
        self.audio.stop()
        self.btn_play.config(text="▶ 播放")

    def _audio_seek(self, delta_ms):
        self._try_seek(self.audio.get_pos() + delta_ms)

    def _try_seek(self, ms):
        """统一跳转入口；格式不支持跳转时明确提示，绝不静默错位"""
        if not self.audio.loaded:
            return False
        if not self.audio.seek_ok:
            self.status.set("⚠ 该音频格式不支持跳转，请转存为 mp3/wav/ogg/flac 后使用")
            return False
        self.audio.seek(ms)
        return True

    def _update_slider_range(self):
        if self.audio.length_ms:
            self.seek_scale.config(to=self.audio.length_ms, state="normal")
        else:
            self.seek_scale.config(state="disabled")

    def _slider_seek(self, _event):
        self._slider_dragging = False
        self.seek_preview.set("")
        if self.audio.length_ms:
            self._try_seek(self.seek_var.get())

    def _slider_moved(self, value):
        """拖动进度条时实时预览目标时间戳与对应歌词"""
        if not self._slider_dragging:
            return
        ms = float(value)
        lyric = self._lyric_at(ms)
        self.seek_preview.set(f"⇢ {fmt_clock(ms)}" + (f" ｜ {lyric}" if lyric else ""))

    def _lyric_at(self, ms):
        cur = ""
        for ln in sorted(self.lines, key=lambda l: l.first_time if l.times else 10**9):
            if ln.times and ln.first_time <= ms:
                cur = ln.text
            elif ln.times:
                break
        return cur

    def jump_to_selected(self):
        if not self.audio.loaded:
            messagebox.showinfo("提示", "请先打开音频文件")
            return
        sel = self.tree.selection()
        if not sel:
            self.status.set("请先选中一句歌词")
            return
        self._jump_row(sel[0])

    def jump_to_time(self):
        if not self.audio.loaded:
            messagebox.showinfo("提示", "请先打开音频文件")
            return
        pos = self.audio.get_pos()
        s = simpledialog.askstring(
            "跳转到指定时长",
            f"输入要跳转到的位置（mm:ss 或 mm:ss.xx）\n当前 {fmt_clock(pos)}，总长 "
            f"{fmt_clock(self.audio.length_ms) if self.audio.length_ms else '未知'}",
            initialvalue=f"{pos // 60000:02d}:{pos % 60000 // 1000:02d}."
                         f"{int(pos) % 1000 // 10:02d}",
            parent=self)
        if not s:
            return
        ms = self._parse_stamp_input(s)
        if ms is None:
            messagebox.showwarning("格式错误", "请按 mm:ss 或 mm:ss.xx 格式输入，如 01:23.50")
            return
        if self._try_seek(ms):
            self.status.set(f"已跳转到 {fmt_clock(ms)}")

    def _on_tree_click(self, event):
        self._note_manual_scroll()
        if self.tree.identify_column(event.x) == "#4":  # 行尾 ▶ 按键列
            item = self.tree.identify_row(event.y)
            if item:
                self._jump_row(item)

    def _on_tree_motion(self, event):
        self.tree.config(cursor="hand2" if self.tree.identify_column(event.x) == "#4" else "")

    def _note_manual_scroll(self, _event=None):
        self._manual_scroll = time.monotonic()

    def _jump_row(self, item):
        if not self.audio.loaded:
            self.status.set("未加载音频 — 点『打开音频』后即可点击 ▶ 从该句播放")
            return
        ln = self.lines[self._sorted_index()[self.tree.index(item)]]
        if not ln.times:
            self.status.set("该行没有时间戳，无法跳转")
            return
        if self._try_seek(ln.first_time):
            self.status.set(f"▶ 从 {ms_to_stamp(ln.first_time)} 开始：{ln.text or '(空行)'}")

    def set_as_first(self):
        """把选中句的时间戳设为当前播放位置，其后所有句按差值同步平移。
        用途：暂停在第一句开口处，右键第一句 → 整首歌词对齐。"""
        if not self.audio.loaded:
            messagebox.showinfo("提示", "请先打开音频文件")
            return
        sel = self.tree.selection()
        if not sel:
            self.status.set("请先选中一句歌词（暂停后右键目标句）")
            return
        anchor = self.lines[self._sorted_index()[self.tree.index(sel[0])]]
        if not anchor.times:
            self.status.set("该行没有时间戳，无法作为基准；请先用回车给它打轴")
            return
        self._push_undo()
        t = max(0, int(self.audio.get_pos()) + self.calib.get())
        anchor_orig = anchor.first_time  # 必须先存常量：锚点平移后 first_time 会变
        delta = t - anchor_orig
        for ln in self.lines:
            if ln.first_time is not None and ln.first_time >= anchor_orig:
                ln.times = [max(0, x + delta) for x in ln.times]
        self._set_modified()
        self.refresh()
        self.status.set(
            f"⏱ 已将 {fmt_clock(t)} 设为该句开头，后续句平移 {delta / 1000:+g}s"
            f"（Ctrl+Z 可撤销）")

    def _show_ctx(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.focus(item)
        self.tree.selection_set(item)
        self.ctx.delete(0, "end")
        self.ctx.add_command(label="✎ 编辑此行", command=self.edit_line)
        self.ctx.add_command(label="▶ 从此句开始播放", command=self.jump_to_selected)
        self.ctx.add_command(label="⏱ 设为首句开头（当前句=暂停时间点，后续句同步平移）",
                             command=self.set_as_first)
        self.ctx.add_command(label="◎ 打轴到此行（当前播放时间）", command=self.stamp_selected)
        self.ctx.add_separator()
        self.ctx.add_command(label="－ 删除此行", command=self.delete_lines)
        self.ctx.tk_popup(event.x_root, event.y_root)

    def stamp_selected(self):
        if not self.audio.loaded:
            messagebox.showinfo("提示", "请先打开音频文件")
            return
        pos = max(0, int(self.audio.get_pos()) + self.calib.get())
        children = self.tree.get_children()
        sel = self.tree.selection()
        sorted_idx = self._sorted_index()
        if sel:
            row = children.index(sel[0])
            ln = self.lines[sorted_idx[row]]
            nxt = row + 1
        else:  # 未选中：自动找第一个无时间戳行
            ln, nxt = None, None
            for r, li in enumerate(sorted_idx):
                if not self.lines[li].times:
                    ln, nxt = self.lines[li], r + 1
                    self.tree.selection_set(children[r])
                    break
            if ln is None:
                self.status.set("所有行都有时间戳了；请先选中一行再打轴")
                return
        self._push_undo()
        ln.times = [pos]
        self._set_modified()
        self.refresh()
        children = self.tree.get_children()
        if nxt is not None and nxt < len(children):
            self.tree.selection_set(children[nxt])
            self.tree.see(children[nxt])
        self.status.set(f"◎ 已打轴 {ms_to_stamp(pos)} → {ln.text or '(空行)'}")

    def _mark_singing(self, item):
        """切换高亮到 item（None 清除）"""
        old = self._singing_item
        if old == item:
            return
        if old and self.tree.exists(old) and old in self._row_tags:
            self.tree.item(old, tags=self._row_tags[old])
        self._singing_item = None
        if item and self.tree.exists(item) and item in self._row_tags:
            self.tree.item(item, tags=self._row_tags[item] + ("singing",))
            self._singing_item = item

    def _tick(self):
        """100ms 轮询：刷新播放时间、进度条、当前句高亮、按钮文案"""
        try:
            alive = self.winfo_exists()
        except tk.TclError:
            return
        if not alive:
            return
        a = self.audio
        if a.loaded:
            self._refresh_time_display()
            pos = a.get_pos()
            if a.ended():
                a.stop()
                self.btn_play.config(text="▶ 播放")
                self._mark_singing(None)
            else:
                self.btn_play.config(text="⏸ 暂停" if a.playing else "▶ 播放")
                if a.playing:
                    self.time_lbl.config(foreground="")
                    item = self._find_singing_item(pos)
                    self._mark_singing(item)
                    self.tree.tag_configure(
                        "singing", foreground=lerp_color(PAL["accent"], PAL["accent_hi"],
                                                         self._pulse(1.4)))
                    cur = self._lyric_at(pos)
                    self.now_singing.set("♪ " + cur if cur else "♪ （前奏）")
                    # 手动滚动/点击歌词后 2 秒内不自动跟随，方便人工浏览
                    if item and self.follow.get() and time.monotonic() - self._manual_scroll > 2.0:
                        self.tree.see(item)
                elif a._paused:
                    # 暂停：红色脉冲醒目显示当前时间点
                    self.time_lbl.config(foreground=lerp_color(PAL["paused_a"],
                                                               PAL["paused_b"],
                                                               self._pulse(1.0)))
                    cur = self._lyric_at(pos)
                    self.now_singing.set(
                        f"⏸ 已暂停于 {fmt_clock(pos)}：{cur or '（间奏）'}"
                        f" — 可右键歌词句『设为首句开头』")
                else:
                    self.time_lbl.config(foreground="")
        try:
            self.after(100, self._tick)
        except tk.TclError:  # 窗口已销毁
            pass

    @staticmethod
    def _pulse(period=1.2):
        """0→1→0 三角波，用于呼吸/脉冲动画"""
        ph = (time.monotonic() % period) / period
        return 1 - abs(2 * ph - 1)

    def _find_singing_item(self, pos):
        """当前播放位置对应的 tree item"""
        best_item, best_t = None, -1
        for item, li in zip(self.tree.get_children(), self._sorted_index()):
            t = self.lines[li].first_time
            if t is not None and t <= pos and t >= best_t:
                best_item, best_t = item, t
        return best_item

    # ---------- 批量功能 ----------

    def shift_times(self):
        sel = self._selected_lines()
        scope = f"选中的 {len(sel)} 行" if sel else "全部歌词行"
        dlg = ShiftDialog(self, scope)
        self.wait_window(dlg)
        if not dlg.result:
            return
        self._push_undo()
        targets = sel if sel else self.lines
        self._apply_shift(int(dlg.result * 1000), targets)
        self._set_modified()
        self.refresh()
        self.status.set(f"已将{scope}平移 {dlg.result:+g} 秒")

    def quick_shift(self, delta_ms):
        """主页快速平移按钮：选中行则只平移选中行，否则全部"""
        if not self.lines:
            return
        self._push_undo()
        targets = self._selected_lines() or self.lines
        self._apply_shift(delta_ms, targets)
        self._set_modified()
        self.refresh()
        self.status.set(f"已平移 {len(targets)} 行 {delta_ms / 1000:+g} 秒（Ctrl+Z 可撤销）")

    @staticmethod
    def _apply_shift(delta_ms, targets):
        for ln in targets:
            ln.times = [t + delta_ms for t in ln.times if t + delta_ms >= 0] or [0]

    def sort_lines(self):
        self._push_undo()
        self.lines.sort(key=lambda l: l.first_time if l.times else 10**9)
        self._set_modified()
        self.refresh()
        self.status.set("已按时间戳排序")

    def normalize_stamps(self):
        self.refresh()
        self._set_modified()
        self.status.set("时间戳已按当前毫秒位数标准化（保存时生效）")

    def clean_lines(self, mode):
        before = len(self.lines)
        self._push_undo()
        if mode == "empty":
            self.lines = [l for l in self.lines if l.text.strip()]
        elif mode == "no_time":
            self.lines = [l for l in self.lines if l.times]
        elif mode == "dup":
            seen = set()
            kept = []
            for l in sorted(self.lines, key=lambda x: x.first_time if x.times else 10**9):
                key = tuple(l.times)
                if key in seen and key:
                    continue
                seen.add(key)
                kept.append(l)
            self.lines = kept
        if removed:
            self._set_modified()
        self.refresh()
        names = {"empty": "空文本行", "no_time": "无时间戳行", "dup": "重复时间戳行"}
        self.status.set(f"已删除 {removed} 个{names[mode]}")

    def smart_fix(self):
        """一键智能修复：剥离逐字标签 → 删空行/无效行 → 去重 → 排序 → 标准化"""
        if not self.lines and not self.meta:
            messagebox.showinfo("提示", "请先打开或录入歌词内容")
            return
        before = len(self.lines)
        for ln in self.lines:
            ln.text = WORD_TIME_RE.sub("", ln.text).strip()
        self._push_undo()
        self.lines = [l for l in self.lines if l.text.strip() and l.times]
        seen, kept = set(), []
        for l in sorted(self.lines, key=lambda x: x.first_time):
            if tuple(l.times) in seen:
                continue
            seen.add(tuple(l.times))
            kept.append(l)
        self.lines = kept
        self._set_modified()
        self.refresh()
        self.status.set("★ 智能修复完成")
        messagebox.showinfo(
            "智能修复",
            f"智能修复完成：{before} → {len(self.lines)} 行\n\n"
            "✓ 剥离逐字时间戳  ✓ 删除空行/无时间戳行\n"
            "✓ 去除重复时间戳  ✓ 排序  ✓ 标准化时间戳")

    def find_replace(self):
        dlg = FindReplaceDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        pat, rep, use_re = dlg.result
        try:
            regex = re.compile(pat if use_re else re.escape(pat))
        except re.error as ex:
            messagebox.showerror("正则错误", str(ex))
            return
        self._push_undo()
        n = 0
        for ln in self.lines:
            new = regex.sub(rep, ln.text)
            if new != ln.text:
                n += 1
                ln.text = new
        self._set_modified()
        self.refresh()
        self.status.set(f"查找替换完成：{n} 行被修改（模式：{pat} → {rep}）")


# ---------------------------------------------------------------- 对话框

class EditLineDialog(tk.Toplevel):
    def __init__(self, parent, stamp, text):
        super().__init__(parent)
        self.title("编辑歌词行")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        ttk.Label(self, text="时间戳（多个用 / 分隔，mm:ss.xx）").pack(padx=px(12), pady=(px(12), px(2)), anchor="w")
        self.e_time = ttk.Entry(self, width=46)
        self.e_time.insert(0, stamp)
        self.e_time.pack(padx=px(12), pady=px(2))
        ttk.Label(self, text="歌词文本").pack(padx=px(12), pady=(px(6), px(2)), anchor="w")
        self.e_text = ttk.Entry(self, width=46)
        self.e_text.insert(0, text)
        self.e_text.pack(padx=px(12), pady=px(2))
        f = ttk.Frame(self)
        f.pack(pady=px(10))
        ttk.Button(f, text="确定", command=self._ok).pack(side="left", padx=px(6))
        ttk.Button(f, text="取消", command=self.destroy).pack(side="left", padx=px(6))
        self.bind("<Return>", lambda e: self._ok())
        self.e_time.focus_set()
        self.configure(background=PAL["bg"])
        if PAL["darkbar"]:
            dark_titlebar(self)
        fade_in(self, 140)

    def _ok(self):
        self.result = (self.e_time.get(), self.e_text.get())
        self.destroy()


class ShiftDialog(tk.Toplevel):
    def __init__(self, parent, scope):
        super().__init__(parent)
        self.title("平移时间戳")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        ttk.Label(self, text=f"作用范围：{scope}\n正值 = 延后显示，负值 = 提前显示").pack(
            padx=px(14), pady=(px(12), px(6)))
        f = ttk.Frame(self)
        f.pack(padx=px(14))
        ttk.Label(f, text="平移秒数：").pack(side="left")
        self.e = ttk.Entry(f, width=10)
        self.e.insert(0, "-1.5")
        self.e.pack(side="left", padx=px(4))
        self.e.focus_set()
        self.e.selection_range(0, "end")
        self.configure(background=PAL["bg"])
        if PAL["darkbar"]:
            dark_titlebar(self)
        fade_in(self, 140)
        f2 = ttk.Frame(self)
        f2.pack(pady=px(10))
        ttk.Button(f2, text="确定", command=self._ok).pack(side="left", padx=px(6))
        ttk.Button(f2, text="取消", command=self.destroy).pack(side="left", padx=px(6))
        self.bind("<Return>", lambda e: self._ok())

    def _ok(self):
        try:
            v = float(self.e.get())
        except ValueError:
            messagebox.showwarning("输入错误", "请输入数字，例如 -1.5 或 2", parent=self)
            return
        self.result = v
        self.destroy()


class FindReplaceDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("查找替换")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self.e_find = ttk.Entry(self, width=44)
        self.e_rep = ttk.Entry(self, width=44)
        self.use_re = tk.BooleanVar(value=False)
        ttk.Label(self, text="查找：").grid(row=0, column=0, padx=px(12), pady=(px(14), px(4)), sticky="e")
        self.e_find.grid(row=0, column=1, padx=(px(0), px(12)), pady=(px(14), px(4)))
        ttk.Label(self, text="替换为：").grid(row=1, column=0, padx=px(12), sticky="e")
        self.e_rep.grid(row=1, column=1, padx=(px(0), px(12)))
        ttk.Checkbutton(self, text="使用正则表达式", variable=self.use_re).grid(
            row=2, column=1, sticky="w", pady=px(6))
        f = ttk.Frame(self)
        f.grid(row=3, columnspan=2, pady=(px(4), px(12)))
        ttk.Button(f, text="全部替换", command=self._ok).pack(side="left", padx=px(6))
        ttk.Button(f, text="取消", command=self.destroy).pack(side="left", padx=px(6))
        self.e_find.focus_set()
        self.configure(background=PAL["bg"])
        if PAL["darkbar"]:
            dark_titlebar(self)
        fade_in(self, 140)

    def _ok(self):
        if not self.e_find.get():
            messagebox.showwarning("提示", "请输入查找内容", parent=self)
            return
        self.result = (self.e_find.get(), self.e_rep.get(), self.use_re.get())
        self.destroy()


# ---------------------------------------------------------------- 入口

def run_self_test():
    """无 GUI 自测：解析/构建/修复逻辑"""
    sample = """[ti:测试歌曲]
[ar:张三]
[offset:0]
[00:01.5]第一句
[00:01.500]重复行
[00:10.20][00:20.00]多时间戳行
[00:05.00]<00:05.00>带<00:05.50>逐字<00:06.00>标签
没有时间戳的行
[00:30.00]
[00:40.2]  空格行  """
    meta, lines = parse_lrc(sample)
    assert meta["ti"] == "测试歌曲" and meta["ar"] == "张三"
    assert len(lines) == 7
    assert lines[2].times == [10200, 20000] and lines[2].text == "多时间戳行"
    assert lines[3].text == "带逐字标签" and lines[3].times == [5000]
    out = build_lrc(meta, lines, digits=2)
    assert "[ti:测试歌曲]" in out and "[ar:张三]" in out
    assert "[00:01.50]第一句" in out
    assert "[00:10.20][00:20.00]多时间戳行" in out
    assert "没有时间戳的行" not in out
    assert "[00:40.20]空格行" in out
    assert out.index("[00:01.50]") < out.index("[00:05.00]") < out.index("[00:10.20]")
    print("self-test OK")
    print(out)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        run_self_test()
    else:
        enable_high_dpi()
        LrcEditor().mainloop()

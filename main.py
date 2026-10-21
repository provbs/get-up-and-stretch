import ctypes
import json
import math
import os
import queue
import random
import time
import tkinter as tk
import webbrowser
import winsound
from tkinter import ttk

import pystray
from PIL import Image, ImageDraw, ImageTk

from facts import FACTS

APP_NAME = "Get Up and Stretch"
VERSION = "1.0.0"
# 저장소 주소. 비워두면 프로그램 하단의 GitHub 링크가 숨겨진다.
GITHUB_URL = "https://github.com/provbs/get-up-and-stretch"
MIN_INTERVAL = 5  # 초
SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "GetUpAndStretch")
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "settings.json")
DEFAULTS = {
    "minutes": 30,
    "seconds": 0,
    "repeat_forever": True,
    "repeat_count": 5,
    "sound": False,
    "bring_front": True,
    "lang": "ko",
}

FONT = "Malgun Gothic"
BG = "#F7F9FA"
CARD = "#FFFFFF"
INK = "#1F2D3A"
MUTED = "#6B7A88"
ACCENT = "#2FA394"
ACCENT_DARK = "#24877A"
RING_BG = "#E3EAEE"
ALERT = "#F08A4B"
GOOD = "#2FA394"
BAD = "#E05555"

TEXT = {
    "ko": {
        "subtitle": "정해진 시간마다 일어나서 몸을 풀어요",
        "next_alarm": "다음 알림까지",
        "paused": "일시정지됨",
        "ready": "시작을 눌러주세요",
        "alarming": "알림 중!",
        "done": "모든 알림 완료!",
        "start": "시작",
        "pause": "일시정지",
        "resume": "계속",
        "reset": "초기화",
        "settings": "설정",
        "interval": "알림 간격",
        "unit_min": "분",
        "unit_sec": "초",
        "repeat": "반복",
        "forever": "계속 반복",
        "times": "회만 반복",
        "sound": "알림 소리 켜기",
        "front": "알림 시 창을 맨 앞으로",
        "language": "언어",
        "progress_forever": "{n}번째 알림 · 계속 반복",
        "progress_count": "{n} / {total}번째 알림",
        "progress_done": "총 {total}회 완료",
        "alarm_title": "일어나서 스트레칭할 시간이에요!",
        "alarm_fact": "오늘의 신기한 사실",
        "alarm_hint": "아래 칸에 위 문장을 그대로 입력하면 알람이 꺼지고 다음 알림이 시작돼요.",
        "alarm_ok": "확인",
        "alarm_wrong": "문장이 일치하지 않아요. 다시 확인해 주세요.",
        "tray_show": "열기",
        "tray_quit": "완전히 종료",
        "tray_title": "트레이로 숨겨졌어요",
        "tray_msg": "타이머는 계속 돌아가요. 완전히 종료하려면 트레이 아이콘을 우클릭 → '완전히 종료'를 누르세요.",
        "tray_done": "설정한 알림을 모두 마쳤어요. 수고하셨어요!",
    },
    "en": {
        "subtitle": "Stand up and move at regular intervals",
        "next_alarm": "Next alarm in",
        "paused": "Paused",
        "ready": "Press Start",
        "alarming": "Alarm!",
        "done": "All alarms done!",
        "start": "Start",
        "pause": "Pause",
        "resume": "Resume",
        "reset": "Reset",
        "settings": "Settings",
        "interval": "Interval",
        "unit_min": "min",
        "unit_sec": "sec",
        "repeat": "Repeat",
        "forever": "Repeat forever",
        "times": "times only",
        "sound": "Play alarm sound",
        "front": "Bring window to front on alarm",
        "language": "Language",
        "progress_forever": "Alarm #{n} · repeating forever",
        "progress_count": "Alarm {n} of {total}",
        "progress_done": "{total} alarms completed",
        "alarm_title": "Time to get up and stretch!",
        "alarm_fact": "Fun fact of the moment",
        "alarm_hint": "Type the sentence above exactly to dismiss the alarm and start the next one.",
        "alarm_ok": "OK",
        "alarm_wrong": "That doesn't match. Please check the sentence again.",
        "tray_show": "Open",
        "tray_quit": "Quit completely",
        "tray_title": "Minimized to the tray",
        "tray_msg": "The timer keeps running. To quit completely, right-click the tray icon and choose 'Quit completely'.",
        "tray_done": "All scheduled alarms are done. Nice work!",
    },
}
LANG_NAMES = {"ko": "한국어", "en": "English"}


def make_icon(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size * 0.04
    d.ellipse([pad, pad, size - pad, size - pad], fill=ACCENT)
    w = max(2, int(size * 0.11))
    inner = size * 0.22
    box = [inner, inner, size - inner, size - inner]
    d.arc(box, 0, 360, fill=(255, 255, 255, 90), width=w)
    d.arc(box, -90, 180, fill="white", width=w)
    return img


def normalize(s):
    return " ".join(s.split()).rstrip(".!。 ").lower()


def load_settings():
    data = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data.update(json.load(f))
    except (OSError, ValueError):
        pass
    if data.get("lang") not in TEXT:
        data["lang"] = "ko"
    return data


class AlarmWindow:
    def __init__(self, app, fact):
        self.app = app
        self.fact = fact
        s = app.scale

        self.top = tk.Toplevel(app.root, bg=BG)
        self.top.resizable(False, False)
        self.top.iconphoto(False, app.icon_photo)
        # 문장을 입력하기 전에는 닫을 수 없게 한다.
        self.top.protocol("WM_DELETE_WINDOW", self.top.bell)

        wrap = int(440 * s)
        self.lbl_title = tk.Label(self.top, font=(FONT, 16, "bold"), fg=ALERT, bg=BG)
        self.lbl_title.pack(padx=int(24 * s), pady=(int(22 * s), int(6 * s)))

        card = tk.Frame(self.top, bg=CARD, highlightthickness=1, highlightbackground=RING_BG)
        card.pack(padx=int(24 * s), pady=int(8 * s), fill="x")
        self.lbl_fact_head = tk.Label(card, font=(FONT, 9, "bold"), fg=MUTED, bg=CARD)
        self.lbl_fact_head.pack(anchor="w", padx=int(16 * s), pady=(int(12 * s), 0))
        self.lbl_fact = tk.Label(card, font=(FONT, 13), fg=INK, bg=CARD, wraplength=wrap, justify="left")
        self.lbl_fact.pack(anchor="w", padx=int(16 * s), pady=(int(4 * s), int(14 * s)))

        self.lbl_hint = tk.Label(self.top, font=(FONT, 9), fg=MUTED, bg=BG, wraplength=wrap, justify="left")
        self.lbl_hint.pack(anchor="w", padx=int(24 * s))

        self.var = tk.StringVar()
        self.entry = tk.Entry(
            self.top, textvariable=self.var, font=(FONT, 13), relief="flat",
            highlightthickness=2, highlightbackground=RING_BG, highlightcolor=ACCENT,
        )
        self.entry.pack(fill="x", padx=int(24 * s), pady=(int(8 * s), int(4 * s)), ipady=int(6 * s))
        # 붙여넣기 금지: 직접 타이핑해야 한다.
        self.entry.bind("<<Paste>>", lambda e: "break")
        self.entry.bind("<Return>", lambda e: self.submit())
        self.var.trace_add("write", lambda *a: self._on_type())

        self.lbl_error = tk.Label(self.top, font=(FONT, 9), fg=BAD, bg=BG)
        self.lbl_error.pack(anchor="w", padx=int(24 * s))

        self.btn = tk.Button(
            self.top, font=(FONT, 11, "bold"), fg="white", bg=ACCENT, activebackground=ACCENT_DARK,
            activeforeground="white", relief="flat", cursor="hand2", command=self.submit,
        )
        self.btn.pack(pady=(int(4 * s), int(22 * s)), ipadx=int(24 * s), ipady=int(4 * s))

        self.apply_texts()
        self.top.update_idletasks()
        w, h = self.top.winfo_reqwidth(), self.top.winfo_reqheight()
        x = (self.top.winfo_screenwidth() - w) // 2
        y = (self.top.winfo_screenheight() - h) // 3
        self.top.geometry(f"+{x}+{y}")
        self.raise_up()

    def apply_texts(self):
        t = self.app.t
        lang = self.app.lang
        self.top.title(f"{APP_NAME} - {t('alarm_title')}")
        self.lbl_title.config(text=t("alarm_title"))
        self.lbl_fact_head.config(text=t("alarm_fact"))
        self.lbl_fact.config(text=self.fact[lang])
        self.lbl_hint.config(text=t("alarm_hint"))
        self.btn.config(text=t("alarm_ok"))
        self.lbl_error.config(text="")

    def raise_up(self):
        self.top.deiconify()
        if self.app.var_front.get():
            self.top.attributes("-topmost", True)
            self.top.lift()
            self.top.focus_force()
            self.entry.focus_set()
        else:
            self.top.attributes("-topmost", False)

    def _target(self):
        return normalize(self.fact[self.app.lang])

    def _on_type(self):
        typed = normalize(self.var.get())
        ok = self._target().startswith(typed)
        color = ACCENT if ok else BAD
        self.entry.config(highlightcolor=color, highlightbackground=color if typed else RING_BG)
        if ok:
            self.lbl_error.config(text="")

    def submit(self):
        if normalize(self.var.get()) == self._target():
            self.top.destroy()
            self.app.on_alarm_dismissed()
        else:
            self.lbl_error.config(text=self.app.t("alarm_wrong"))
            self.top.bell()

    def destroy(self):
        if self.top.winfo_exists():
            self.top.destroy()


class App:
    def __init__(self):
        self.settings = load_settings()
        self.lang = self.settings["lang"]
        self.queue = queue.Queue()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.icon_image = make_icon(256)
        self.icon_photo = ImageTk.PhotoImage(self.icon_image.resize((64, 64)))
        self.root.iconphoto(True, self.icon_photo)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self.var_minutes = tk.StringVar(value=str(self.settings["minutes"]))
        self.var_seconds = tk.StringVar(value=str(self.settings["seconds"]))
        self.var_forever = tk.BooleanVar(value=self.settings["repeat_forever"])
        self.var_count = tk.StringVar(value=str(self.settings["repeat_count"]))
        self.var_sound = tk.BooleanVar(value=self.settings["sound"])
        self.var_front = tk.BooleanVar(value=self.settings["bring_front"])

        # state: idle | running | paused | alarm | done
        self.state = "idle"
        self.completed = 0
        self.cycle_total = self.interval()
        self.remaining = self.cycle_total
        self.end_time = 0.0
        self.last_beep = 0.0
        self.alarm = None
        self.last_fact = None
        self.tray_tooltip = ""

        self._build_ui()
        self.apply_texts()
        self._update_controls()
        self._setup_tray()

        self.root.update_idletasks()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 3
        self.root.geometry(f"+{x}+{y}")
        self.root.deiconify()
        self._tick()

    # ---------- helpers ----------
    def t(self, key):
        return TEXT[self.lang][key]

    def px(self, v):
        return int(v * self.scale)

    def minutes(self):
        try:
            return max(0, min(600, int(self.var_minutes.get())))
        except ValueError:
            return self.settings["minutes"]

    def seconds(self):
        try:
            return max(0, min(59, int(self.var_seconds.get())))
        except ValueError:
            return self.settings["seconds"]

    def interval(self):
        return max(MIN_INTERVAL, self.minutes() * 60 + self.seconds())

    def repeat_count(self):
        try:
            return max(1, min(999, int(self.var_count.get())))
        except ValueError:
            return self.settings["repeat_count"]

    def save_settings(self):
        self.settings.update(
            minutes=self.minutes(),
            seconds=self.seconds(),
            repeat_forever=self.var_forever.get(),
            repeat_count=self.repeat_count(),
            sound=self.var_sound.get(),
            bring_front=self.var_front.get(),
            lang=self.lang,
        )
        try:
            os.makedirs(SETTINGS_DIR, exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ---------- UI ----------
    def _build_ui(self):
        px = self.px
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(padx=px(24), pady=px(20))

        head = tk.Frame(outer, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text=APP_NAME, font=(FONT, 17, "bold"), fg=INK, bg=BG).pack(side="left")
        self.cmb_lang = ttk.Combobox(head, values=list(LANG_NAMES.values()), state="readonly", width=8, font=(FONT, 9))
        self.cmb_lang.set(LANG_NAMES[self.lang])
        self.cmb_lang.pack(side="right")
        self.cmb_lang.bind("<<ComboboxSelected>>", self._on_lang)
        self.lbl_lang = tk.Label(head, font=(FONT, 9), fg=MUTED, bg=BG)
        self.lbl_lang.pack(side="right", padx=(0, px(6)))
        self.lbl_subtitle = tk.Label(outer, font=(FONT, 9), fg=MUTED, bg=BG)
        self.lbl_subtitle.pack(anchor="w")

        # 진행 원
        size = px(250)
        self.canvas = tk.Canvas(outer, width=size, height=size, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=(px(14), px(6)))
        ring = px(16)
        m = ring / 2 + px(4)
        box = (m, m, size - m, size - m)
        self.canvas.create_oval(*box, outline=RING_BG, width=ring)
        c = size / 2
        # create_arc는 두꺼운 선에서 작은 각도를 크게 그리는 문제가 있어 직접 선으로 그린다.
        self.ring_center, self.ring_radius = c, c - m
        self.arc = self.canvas.create_line(
            0, 0, 0, 0, fill=ACCENT, width=ring, capstyle="round", joinstyle="round", state="hidden",
        )
        self.txt_top = self.canvas.create_text(c, c - px(36), font=(FONT, 10), fill=MUTED)
        self.txt_time = self.canvas.create_text(c, c + px(2), font=(FONT, 34, "bold"), fill=INK)
        self.txt_bottom = self.canvas.create_text(c, c + px(44), font=(FONT, 9), fill=MUTED)

        btns = tk.Frame(outer, bg=BG)
        btns.pack(pady=(px(4), px(14)))
        self.btn_start = tk.Button(
            btns, font=(FONT, 11, "bold"), fg="white", bg=ACCENT, activebackground=ACCENT_DARK,
            activeforeground="white", relief="flat", cursor="hand2", width=10, command=self.on_start_pause,
        )
        self.btn_start.pack(side="left", padx=px(4), ipady=px(4))
        self.btn_reset = tk.Button(
            btns, font=(FONT, 11), fg=INK, bg=RING_BG, activebackground="#D3DCE1",
            relief="flat", cursor="hand2", width=10, command=self.on_reset,
        )
        self.btn_reset.pack(side="left", padx=px(4), ipady=px(4))

        card = tk.Frame(outer, bg=CARD, highlightthickness=1, highlightbackground=RING_BG)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=px(16), pady=px(12))
        self.lbl_settings = tk.Label(inner, font=(FONT, 10, "bold"), fg=INK, bg=CARD)
        self.lbl_settings.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, px(6)))

        self.lbl_interval = tk.Label(inner, font=(FONT, 10), fg=INK, bg=CARD)
        self.lbl_interval.grid(row=1, column=0, sticky="w", pady=px(3))
        itv = tk.Frame(inner, bg=CARD)
        itv.grid(row=1, column=1, columnspan=2, sticky="w", padx=(px(10), 0))
        self.spn_minutes = tk.Spinbox(
            itv, from_=0, to=600, textvariable=self.var_minutes, width=4, font=(FONT, 10), justify="center",
        )
        self.spn_minutes.pack(side="left")
        self.lbl_unit_min = tk.Label(itv, font=(FONT, 10), fg=INK, bg=CARD)
        self.lbl_unit_min.pack(side="left", padx=(px(4), px(10)))
        self.spn_seconds = tk.Spinbox(
            itv, from_=0, to=59, textvariable=self.var_seconds, width=3, font=(FONT, 10), justify="center",
            wrap=True,
        )
        self.spn_seconds.pack(side="left")
        self.lbl_unit_sec = tk.Label(itv, font=(FONT, 10), fg=INK, bg=CARD)
        self.lbl_unit_sec.pack(side="left", padx=(px(4), 0))
        self.var_minutes.trace_add("write", lambda *a: self._on_interval())
        self.var_seconds.trace_add("write", lambda *a: self._on_interval())

        self.lbl_repeat = tk.Label(inner, font=(FONT, 10), fg=INK, bg=CARD)
        self.lbl_repeat.grid(row=2, column=0, sticky="nw", pady=px(3))
        rep = tk.Frame(inner, bg=CARD)
        rep.grid(row=2, column=1, columnspan=2, sticky="w", padx=(px(10), 0))
        self.rb_forever = tk.Radiobutton(
            rep, variable=self.var_forever, value=True, font=(FONT, 10), bg=CARD, activebackground=CARD,
            command=self._on_setting,
        )
        self.rb_forever.grid(row=0, column=0, columnspan=3, sticky="w")
        self.rb_count = tk.Radiobutton(
            rep, variable=self.var_forever, value=False, bg=CARD, activebackground=CARD, command=self._on_setting,
        )
        self.rb_count.grid(row=1, column=0, sticky="w")
        self.spn_count = tk.Spinbox(
            rep, from_=1, to=999, textvariable=self.var_count, width=4, font=(FONT, 10), justify="center",
        )
        self.spn_count.grid(row=1, column=1, sticky="w")
        self.lbl_times = tk.Label(rep, font=(FONT, 10), fg=INK, bg=CARD)
        self.lbl_times.grid(row=1, column=2, sticky="w", padx=(px(4), 0))
        self.var_count.trace_add("write", lambda *a: self._on_setting())

        self.chk_sound = tk.Checkbutton(
            inner, variable=self.var_sound, font=(FONT, 10), bg=CARD, activebackground=CARD, command=self._on_setting,
        )
        self.chk_sound.grid(row=3, column=0, columnspan=3, sticky="w", pady=(px(6), 0))
        self.chk_front = tk.Checkbutton(
            inner, variable=self.var_front, font=(FONT, 10), bg=CARD, activebackground=CARD, command=self._on_setting,
        )
        self.chk_front.grid(row=4, column=0, columnspan=3, sticky="w")

        foot = tk.Frame(outer, bg=BG)
        foot.pack(fill="x", pady=(px(10), 0))
        tk.Label(foot, text=f"v{VERSION}", font=(FONT, 8), fg=MUTED, bg=BG).pack(side="left")
        if GITHUB_URL:
            link = tk.Label(foot, text="GitHub ↗", font=(FONT, 8, "underline"), fg=ACCENT, bg=BG, cursor="hand2")
            link.pack(side="right")
            link.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_URL))

    def apply_texts(self):
        t = self.t
        self.lbl_subtitle.config(text=t("subtitle"))
        self.lbl_lang.config(text=t("language"))
        self.btn_reset.config(text=t("reset"))
        self.lbl_settings.config(text=t("settings"))
        self.lbl_interval.config(text=t("interval"))
        self.lbl_unit_min.config(text=t("unit_min"))
        self.lbl_unit_sec.config(text=t("unit_sec"))
        self.lbl_repeat.config(text=t("repeat"))
        self.rb_forever.config(text=t("forever"))
        self.lbl_times.config(text=t("times"))
        self.chk_sound.config(text=t("sound"))
        self.chk_front.config(text=t("front"))
        self._update_controls()
        if self.alarm:
            self.alarm.apply_texts()
        if hasattr(self, "tray"):
            self.tray.update_menu()

    def _update_controls(self):
        t = self.t
        if self.state == "running":
            label = t("pause")
        elif self.state == "paused":
            label = t("resume")
        else:
            label = t("start")
        self.btn_start.config(text=label, state="disabled" if self.state == "alarm" else "normal")
        locked = self.state in ("running", "paused", "alarm")
        st = "disabled" if locked else "normal"
        for w in (self.spn_minutes, self.spn_seconds, self.rb_forever, self.rb_count):
            w.config(state=st)
        self.spn_count.config(state="disabled" if locked or self.var_forever.get() else "normal")

    def _on_lang(self, _event=None):
        name = self.cmb_lang.get()
        self.lang = next(k for k, v in LANG_NAMES.items() if v == name)
        self.save_settings()
        self.apply_texts()

    def _on_interval(self):
        if self.state in ("idle", "done"):
            self.cycle_total = self.interval()
            self.remaining = self.cycle_total
        self._on_setting()

    def _on_setting(self):
        self._update_controls()
        self.save_settings()
        if self.alarm and self.var_front.get():
            self.alarm.raise_up()

    # ---------- timer ----------
    def on_start_pause(self):
        now = time.monotonic()
        if self.state in ("idle", "done"):
            self.completed = 0
            self._start_cycle()
        elif self.state == "running":
            self.remaining = max(0.0, self.end_time - now)
            self.state = "paused"
        elif self.state == "paused":
            self.end_time = now + self.remaining
            self.state = "running"
        self._update_controls()

    def on_reset(self):
        if self.alarm:
            self.alarm.destroy()
            self.alarm = None
        self.state = "idle"
        self.completed = 0
        self.cycle_total = self.interval()
        self.remaining = self.cycle_total
        self._update_controls()

    def _start_cycle(self):
        self.cycle_total = self.interval()
        self.remaining = self.cycle_total
        self.end_time = time.monotonic() + self.cycle_total
        self.state = "running"

    def _trigger_alarm(self):
        self.state = "alarm"
        self.remaining = 0
        self.last_beep = 0.0
        choices = [f for f in FACTS if f is not self.last_fact]
        self.last_fact = random.choice(choices)
        self.alarm = AlarmWindow(self, self.last_fact)
        self._update_controls()

    def on_alarm_dismissed(self):
        self.alarm = None
        self.completed += 1
        if not self.var_forever.get() and self.completed >= self.repeat_count():
            self.state = "done"
            self.notify(APP_NAME, self.t("tray_done"))
        else:
            self._start_cycle()
        self._update_controls()

    def _tick(self):
        while not self.queue.empty():
            cmd = self.queue.get_nowait()
            if cmd == "show":
                self.show_window()
            elif cmd == "quit":
                self.quit()
                return
        now = time.monotonic()
        if self.state == "running":
            self.remaining = max(0.0, self.end_time - now)
            if self.remaining <= 0:
                self._trigger_alarm()
        if self.state == "alarm" and self.var_sound.get() and now - self.last_beep >= 2.5:
            self.last_beep = now
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
        self._draw()
        self.root.after(100, self._tick)

    def _draw(self):
        t = self.t
        total = None if self.var_forever.get() else self.repeat_count()
        n = self.completed + 1
        secs = int(self.remaining + 0.999)
        time_txt = f"{secs // 60:02d}:{secs % 60:02d}"
        color = ACCENT
        if self.state == "idle":
            progress, top = 0.0, t("ready")
        elif self.state == "done":
            progress, top, time_txt = 1.0, t("done"), "00:00"
        elif self.state == "alarm":
            progress, top, color = 1.0, t("alarming"), ALERT
        else:
            progress = 1 - self.remaining / self.cycle_total if self.cycle_total else 0
            top = t("paused") if self.state == "paused" else t("next_alarm")
        if self.state == "done":
            bottom = t("progress_done").format(total=self.completed)
        elif total is None:
            bottom = t("progress_forever").format(n=n)
        else:
            bottom = t("progress_count").format(n=min(n, total), total=total)

        self._draw_ring(max(0.0, min(1.0, progress)), color)
        self.canvas.itemconfig(self.txt_top, text=top)
        self.canvas.itemconfig(self.txt_time, text=time_txt, fill=MUTED if self.state == "paused" else INK)
        self.canvas.itemconfig(self.txt_bottom, text=bottom)

        tooltip = f"{APP_NAME} - {top} {time_txt}"
        if tooltip != self.tray_tooltip:
            self.tray_tooltip = tooltip
            self.tray.title = tooltip

    def _draw_ring(self, progress, color):
        deg = 360 * progress
        if deg < 0.5:
            self.canvas.itemconfig(self.arc, state="hidden")
            return
        c, r = self.ring_center, self.ring_radius
        steps = max(2, int(deg / 2) + 1)
        coords = []
        for i in range(steps + 1):
            a = math.radians(90 - deg * i / steps)  # 12시 방향에서 시계방향
            coords += [c + r * math.cos(a), c - r * math.sin(a)]
        self.canvas.coords(self.arc, *coords)
        self.canvas.itemconfig(self.arc, state="normal", fill=color)

    # ---------- tray ----------
    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem(lambda item: self.t("tray_show"), lambda icon, item: self.queue.put("show"), default=True),
            pystray.MenuItem(lambda item: self.t("tray_quit"), lambda icon, item: self.queue.put("quit")),
        )
        self.tray = pystray.Icon("GetUpAndStretch", self.icon_image.resize((64, 64)), APP_NAME, menu)
        self.tray.run_detached()

    def notify(self, title, msg):
        try:
            self.tray.notify(msg, title)
        except Exception:
            pass

    def hide_to_tray(self):
        self.root.withdraw()
        self.notify(self.t("tray_title"), self.t("tray_msg"))

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self.alarm:
            self.alarm.raise_up()

    def quit(self):
        self.save_settings()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GetUpAndStretch")
    except Exception:
        pass
    App().root.mainloop()


if __name__ == "__main__":
    main()

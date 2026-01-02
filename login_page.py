import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import font as tkfont, messagebox
from typing import Dict, Optional, Tuple

import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

BASE_WIDTH = 1328
BASE_HEIGHT = 800

LOGO_POS = (BASE_WIDTH / 2, 156)
TITLE_POS = (BASE_WIDTH / 2, 267)
API_LABEL_POS = (267, 295)
API_ENTRY_POS = (267, 324)
SECRET_LABEL_POS = (267, 400)
SECRET_ENTRY_POS = (267, 429)
NOTE_POS = (BASE_WIDTH / 2, 492)
LOGIN_BTN_POS = (BASE_WIDTH / 2, 545)
CHECK_POS = (BASE_WIDTH / 2, 620)
REQUIRED_POS = (BASE_WIDTH / 2, 655)

INFO_PANEL_POS = (29, 32)
INFO_PANEL_SIZE = (371, 174)
HELP_PANEL_POS = (944, 93)
HELP_PANEL_SIZE = (348, 220)

FORM_OFFSET_Y = 32

ENTRY_W = 811
ENTRY_H = 51
LOGIN_W = 417
LOGIN_H = 60
HELP_BTN_W = 278
HELP_BTN_H = 39

ANIM_DURATION_MS = 500
ANIM_OFFSET = 40
FPS = 60

CANVAS_BG = "#0b1020"
BG_COLOR = "#ffffff"
BORDER_COLOR = "#1a2233"
TEXT_COLOR = "#111217"
UI_TEXT_COLOR = "#f6f8fc"
NOTE_COLOR = "#d2d8e4"
BUTTON_BG = "#000000"
BUTTON_FG = "white"
BUTTON_DISABLED_BG = "#3a3a3a"
BUTTON_DISABLED_FG = "#9a9a9a"
PANEL_FILL = "#0b1220"
PANEL_BORDER = "#c4cedf"
PANEL_ALPHA = 165
PANEL_BORDER_ALPHA = 210
MONTH_COLOR = "#f4c36a"

FONT_FAMILY = "Malgun Gothic"


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _hex_to_rgba(color: str, alpha: int) -> Tuple[int, int, int, int]:
    color = color.lstrip("#")
    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    return r, g, b, alpha


def _round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float, **kwargs):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r,
        y1,
        x2 - r,
        y1,
        x2,
        y1,
        x2,
        y1 + r,
        x2,
        y2 - r,
        x2,
        y2,
        x2 - r,
        y2,
        x1 + r,
        y2,
        x1,
        y2,
        x1,
        y2 - r,
        x1,
        y1 + r,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=36, **kwargs)


class RoundedPanel(tk.Canvas):
    def __init__(
        self,
        master: tk.Widget,
        radius: int = 14,
        border_width: int = 2,
        border_color: str = "#000000",
        fill_color: str = "white",
    ) -> None:
        super().__init__(master, bg=CANVAS_BG, highlightthickness=0)
        self.radius = radius
        self.border_width = border_width
        self.border_color = border_color
        self.fill_color = fill_color
        self.content = tk.Frame(self, bg=fill_color)
        self._window = self.create_window(0, 0, window=self.content, anchor="nw")

    def resize(self, width: float, height: float, scale: float) -> None:
        self.configure(width=width, height=height)
        self.delete("shape")
        radius = int(self.radius * scale)
        _round_rect(
            self,
            0,
            0,
            width,
            height,
            radius,
            fill=self.fill_color,
            outline=self.border_color,
            width=self.border_width,
            tags="shape",
        )
        pad = self.border_width
        self.coords(self._window, pad, pad)
        self.itemconfigure(self._window, width=max(1, width - pad * 2), height=max(1, height - pad * 2))
        self.tag_lower("shape")


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        master: tk.Widget,
        text: str,
        font: tkfont.Font,
        radius: int = 12,
        bg: str = BUTTON_BG,
        fg: str = BUTTON_FG,
        disabled_bg: str = BUTTON_DISABLED_BG,
        disabled_fg: str = BUTTON_DISABLED_FG,
        command=None,
    ) -> None:
        super().__init__(master, bg=CANVAS_BG, highlightthickness=0)
        self._text = text
        self._font = font
        self._radius = radius
        self._bg = bg
        self._fg = fg
        self._disabled_bg = disabled_bg
        self._disabled_fg = disabled_fg
        self._command = command
        self._state = "normal"
        self._width = 0
        self._height = 0
        self.bind("<Button-1>", self._on_click)

    def set_state(self, state: str) -> None:
        self._state = state
        self.configure(cursor="hand2" if state == "normal" else "")
        self._redraw()

    def resize(self, width: float, height: float, scale: float) -> None:
        self._width = int(width)
        self._height = int(height)
        self.configure(width=width, height=height)
        self._redraw(scale, width, height)

    def _redraw(self, scale: float = 1.0, width: Optional[float] = None, height: Optional[float] = None) -> None:
        width = max(1, int(width or self._width or self.winfo_width()))
        height = max(1, int(height or self._height or self.winfo_height()))
        self.delete("all")
        radius = int(self._radius * scale)
        fill = self._bg if self._state == "normal" else self._disabled_bg
        fg = self._fg if self._state == "normal" else self._disabled_fg
        _round_rect(self, 0, 0, width, height, radius, fill=fill, outline=fill)
        self.create_text(width / 2, height / 2, text=self._text, font=self._font, fill=fg)

    def _on_click(self, _event: tk.Event) -> None:
        if self._state != "normal" or self._command is None:
            return
        self._command()


class EntryRow:
    def __init__(
        self,
        master: tk.Widget,
        fonts: Dict[str, tkfont.Font],
        with_eye: bool = False,
        on_eye=None,
        on_paste=None,
    ) -> None:
        self.outer = tk.Frame(master, bg=BORDER_COLOR, highlightthickness=0)
        self.inner = tk.Frame(self.outer, bg=BG_COLOR, highlightthickness=0)
        self.entry = tk.Entry(
            self.inner,
            bd=0,
            relief="flat",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            font=fonts["entry"],
        )
        self.eye_button: Optional[tk.Button] = None
        if with_eye:
            self.eye_button = tk.Button(
                self.inner,
                text="👁",
                bg=BG_COLOR,
                fg=TEXT_COLOR,
                font=fonts["icon"],
                bd=0,
                relief="flat",
                highlightthickness=0,
                activebackground=BG_COLOR,
                activeforeground=TEXT_COLOR,
                cursor="hand2",
                command=on_eye,
            )
        self.paste_button = tk.Button(
            self.inner,
            text="📋",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            font=fonts["icon"],
            bd=0,
            relief="flat",
            highlightthickness=0,
            activebackground=BG_COLOR,
            activeforeground=TEXT_COLOR,
            cursor="hand2",
            command=on_paste,
        )

    def place(self, x: float, y: float, width: float, height: float, scale: float) -> None:
        self.outer.place(x=x, y=y, width=width, height=height, anchor="nw")
        border = max(1, int(2 * scale))
        inner_w = max(1, int(width - 2 * border))
        inner_h = max(1, int(height - 2 * border))
        self.inner.place(x=border, y=border, width=inner_w, height=inner_h, anchor="nw")

        pad_x = max(6, int(8 * scale))
        icon_w = max(20, int(inner_h * 0.7))
        icon_pad = max(4, int(4 * scale))

        right_x = inner_w - pad_x
        self.paste_button.place(
            x=right_x,
            y=inner_h / 2,
            width=icon_w,
            height=icon_w,
            anchor="e",
        )
        right_x -= icon_w + icon_pad

        if self.eye_button is not None:
            self.eye_button.place(
                x=right_x,
                y=inner_h / 2,
                width=icon_w,
                height=icon_w,
                anchor="e",
            )
            right_x -= icon_w + icon_pad

        entry_w = max(1, int(right_x - pad_x))
        self.entry.place(x=pad_x, y=0, width=entry_w, height=inner_h, anchor="nw")


class LoginPage(tk.Frame):
    def __init__(self, master: tk.Widget, current_version: str = "", latest_version: str = "") -> None:
        super().__init__(master, bg=CANVAS_BG)
        self.root = self.winfo_toplevel()
        self._supports_alpha = self._init_alpha_support()
        self._anim_offset = 0
        self._secret_visible = False
        self._current_version = current_version or "--"
        self._latest_version = latest_version or "--"
        self._remember_var = tk.BooleanVar(value=True)
        self._required_var = tk.BooleanVar(value=False)

        self._base_fonts = {
            "title": (16, "bold"),
            "label": (12, "bold"),
            "entry": (12, "normal"),
            "note": (10, "normal"),
            "button": (14, "bold"),
            "checkbox": (11, "normal"),
            "icon": (12, "normal"),
            "info": (11, "bold"),
            "time": (11, "bold"),
            "help": (11, "bold"),
            "help_button": (11, "bold"),
        }
        self.fonts: Dict[str, tkfont.Font] = {
            name: tkfont.Font(self, family=FONT_FAMILY, size=size, weight=weight)
            for name, (size, weight) in self._base_fonts.items()
        }

        self.canvas = tk.Canvas(self, bg=CANVAS_BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.bg_original = self._load_background()
        self.bg_photo: Optional[ImageTk.PhotoImage] = None
        self._last_bg_size: Optional[Tuple[int, int]] = None
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw")

        self.logo_original = self._load_logo()
        self.logo_photo: Optional[ImageTk.PhotoImage] = None
        self._last_logo_scale: Optional[float] = None
        self.logo_item = self.canvas.create_image(0, 0, anchor="center")

        self.info_panel_photo: Optional[ImageTk.PhotoImage] = None
        self._last_info_panel_size: Optional[Tuple[int, int]] = None
        self.info_panel_item = self.canvas.create_image(0, 0, anchor="nw")
        self.info_status_id = self.canvas.create_text(
            0,
            0,
            text="",
            fill=UI_TEXT_COLOR,
            font=self.fonts["info"],
            anchor="center",
        )
        self.info_price_id = self.canvas.create_text(
            0,
            0,
            text="",
            fill=UI_TEXT_COLOR,
            font=self.fonts["info"],
            anchor="center",
        )
        self.info_version_current_id = self.canvas.create_text(
            0,
            0,
            text=f"현재 버전 : {self._current_version}",
            fill=UI_TEXT_COLOR,
            font=self.fonts["info"],
            anchor="center",
        )
        self.info_version_latest_id = self.canvas.create_text(
            0,
            0,
            text=f"최신 버전 : {self._latest_version}",
            fill=UI_TEXT_COLOR,
            font=self.fonts["info"],
            anchor="center",
        )
        self.time_month_id = self.canvas.create_text(
            0,
            0,
            text="",
            fill=MONTH_COLOR,
            font=self.fonts["time"],
            anchor="e",
        )
        self.time_rest_id = self.canvas.create_text(
            0,
            0,
            text="",
            fill=UI_TEXT_COLOR,
            font=self.fonts["time"],
            anchor="w",
        )

        self.help_title1_id = self.canvas.create_text(
            0,
            0,
            text="🔑 아직 API 키가 없으신가요?",
            fill=UI_TEXT_COLOR,
            font=self.fonts["help"],
            anchor="nw",
        )
        self.help_title2_id = self.canvas.create_text(
            0,
            0,
            text="💎 API키는 있지만 로그인이 안되시나요?",
            fill=UI_TEXT_COLOR,
            font=self.fonts["help"],
            anchor="nw",
        )

        self.title_text_id = self.canvas.create_text(
            0,
            0,
            text="연결하실 API키를 입력하십시오",
            fill=UI_TEXT_COLOR,
            font=self.fonts["title"],
            anchor="center",
        )
        self.api_label_id = self.canvas.create_text(
            0,
            0,
            text="API Key",
            fill=UI_TEXT_COLOR,
            font=self.fonts["label"],
            anchor="nw",
        )
        self.secret_label_id = self.canvas.create_text(
            0,
            0,
            text="SECRET KEY  (Private)",
            fill=UI_TEXT_COLOR,
            font=self.fonts["label"],
            anchor="nw",
        )
        self.note_text_id = self.canvas.create_text(
            0,
            0,
            text="* Secret Key는 서버에 저장되지 않으며 암호화 되어 로컬에만 남습니다.",
            fill=NOTE_COLOR,
            font=self.fonts["note"],
            anchor="center",
        )
        self.remember_text_id = self.canvas.create_text(
            0,
            0,
            text=self._remember_text(),
            fill=UI_TEXT_COLOR,
            font=self.fonts["checkbox"],
            anchor="center",
        )
        self.required_text_id = self.canvas.create_text(
            0,
            0,
            text=self._required_text(),
            fill=UI_TEXT_COLOR,
            font=self.fonts["checkbox"],
            anchor="center",
        )

        self.api_row = EntryRow(self.canvas, self.fonts, on_paste=self._paste_api)
        self.secret_row = EntryRow(
            self.canvas,
            self.fonts,
            with_eye=True,
            on_eye=self._toggle_secret,
            on_paste=self._paste_secret,
        )
        self.secret_row.entry.configure(show="*")

        self.login_button = RoundedButton(
            self.canvas,
            text="Login",
            font=self.fonts["button"],
            radius=18,
        )
        self.help_button1 = RoundedButton(
            self.canvas,
            text="🔑 API Key 발급 가이드",
            font=self.fonts["help_button"],
            radius=12,
            command=self._open_api_guide,
        )
        self.help_button2 = RoundedButton(
            self.canvas,
            text="💎 구독자 등록 요청",
            font=self.fonts["help_button"],
            radius=12,
        )
        self.help_button1.set_state("normal")
        self.help_button2.set_state("normal")

        self._bind_checkbox(self.remember_text_id, self._toggle_remember)
        self._bind_checkbox(self.required_text_id, self._toggle_required)

        self._update_login_state()
        self._refresh_market_info()
        self._refresh_clock()

        self.canvas.bind("<Configure>", self._on_resize)
        self._layout()

    def _load_logo(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        logo_path = base_dir / "image" / "login_page" / "logo1.png"
        return Image.open(logo_path).convert("RGBA")

    def _load_background(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        bg_path = base_dir / "image" / "login_page" / "login_bg.png"
        return Image.open(bg_path).convert("RGBA")

    def _open_api_guide(self) -> None:
        base_dir = Path(__file__).resolve().parent
        pdf_path = base_dir / "image" / "login_page" / "binance_copy_api_guide.pdf"
        if not pdf_path.exists():
            messagebox.showerror("파일 없음", f"PDF 파일을 찾을 수 없습니다:\n{pdf_path}")
            return
        try:
            self._open_file(pdf_path)
        except Exception as exc:
            messagebox.showerror("열기 실패", f"PDF를 열 수 없습니다:\n{exc}")

    def _open_file(self, path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _bind_checkbox(self, item_id: int, callback) -> None:
        self.canvas.tag_bind(item_id, "<Button-1>", callback)
        self.canvas.tag_bind(item_id, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(item_id, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _init_alpha_support(self) -> bool:
        try:
            self.root.attributes("-alpha", 1.0)
        except tk.TclError:
            return False
        return True

    def _remember_text(self) -> str:
        return ("[ v ] " if self._remember_var.get() else "[   ] ") + "계정 정보 기억하기 (Auto-fill)"

    def _toggle_remember(self, _event: Optional[tk.Event] = None) -> None:
        self._remember_var.set(not self._remember_var.get())
        self.canvas.itemconfigure(self.remember_text_id, text=self._remember_text())

    def _required_text(self) -> str:
        prefix = "[ v ] " if self._required_var.get() else "[   ] "
        return prefix + "(필수) 자동매매로 인한 손실에 대한 책임은 본인에게 있음을 확인합니다."

    def _toggle_required(self, _event: Optional[tk.Event] = None) -> None:
        self._required_var.set(not self._required_var.get())
        self.canvas.itemconfigure(self.required_text_id, text=self._required_text())
        self._update_login_state()

    def _update_login_state(self) -> None:
        self.login_button.set_state("normal" if self._required_var.get() else "disabled")

    def _paste_text(self, entry: tk.Entry) -> None:
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        entry.delete(0, tk.END)
        entry.insert(0, text)

    def _paste_api(self) -> None:
        self._paste_text(self.api_row.entry)

    def _paste_secret(self) -> None:
        self._paste_text(self.secret_row.entry)

    def _toggle_secret(self) -> None:
        self._secret_visible = not self._secret_visible
        self.secret_row.entry.configure(show="" if self._secret_visible else "*")

    def _fetch_market_info(self) -> dict:
        try:
            import ccxt  # type: ignore
        except Exception:
            return {"online": False}

        try:
            exchange = ccxt.binance({"enableRateLimit": True})
            start = time.perf_counter()
            ticker = exchange.fetch_ticker("BTC/USDT")
            ping_ms = int((time.perf_counter() - start) * 1000)
            last = ticker.get("last") or ticker.get("close")
            percent = ticker.get("percentage")
            if percent is None:
                open_price = ticker.get("open")
                if open_price:
                    percent = (last - open_price) / open_price * 100
            return {
                "online": True,
                "ping_ms": ping_ms,
                "last": last,
                "percent": percent,
            }
        except Exception:
            return {"online": False}

    def _refresh_market_info(self) -> None:
        info = self._fetch_market_info()
        if not info.get("online"):
            status_text = "❌ Offline (--)"
            price_text = "$--"
            change_text = "(--%)"
        else:
            ping_ms = info.get("ping_ms", 0)
            status_text = f"📡 Online ({ping_ms}ms)"
            last = info.get("last") or 0
            price_text = f"$ {last:,.2f}"
            percent = info.get("percent")
            if percent is None:
                change_text = "(--%)"
            else:
                sign = "+" if percent >= 0 else ""
                change_text = f"({sign}{percent:.1f}%)"
        self.canvas.itemconfigure(self.info_status_id, text=status_text)
        self.canvas.itemconfigure(self.info_price_id, text=f"BTC/USDT : {price_text} {change_text}")
        self.after(30000, self._refresh_market_info)

    def _refresh_clock(self) -> None:
        now = datetime.now(timezone(timedelta(hours=9)))
        month = now.strftime("%b")
        hour = now.strftime("%I").lstrip("0") or "12"
        rest = f" {now.day} {now.year} {hour}:{now.strftime('%M')} {now.strftime('%p')}"
        self.canvas.itemconfigure(self.time_month_id, text=month)
        self.canvas.itemconfigure(self.time_rest_id, text=rest)
        self.after(1000, self._refresh_clock)

    def animate_in(self) -> None:
        self._anim_offset = ANIM_OFFSET
        if self._supports_alpha:
            try:
                self.root.attributes("-alpha", 0.0)
            except tk.TclError:
                self._supports_alpha = False

        frame_interval = int(1000 / FPS)
        total_frames = max(1, int(ANIM_DURATION_MS / frame_interval))

        def step(frame: int = 0) -> None:
            t = min(1.0, frame / total_frames)
            eased = _ease_out_cubic(t)
            self._anim_offset = ANIM_OFFSET * (1 - eased)
            if self._supports_alpha:
                try:
                    self.root.attributes("-alpha", eased)
                except tk.TclError:
                    self._supports_alpha = False
            self._layout()
            if frame < total_frames:
                self.after(frame_interval, step, frame + 1)
            else:
                if self._supports_alpha:
                    try:
                        self.root.attributes("-alpha", 1.0)
                    except tk.TclError:
                        self._supports_alpha = False
                self._anim_offset = 0
                self._layout()

        step()

    def _on_resize(self, _event: tk.Event) -> None:
        self._layout()

    def _set_font_scale(self, scale: float) -> None:
        for name, (base_size, _weight) in self._base_fonts.items():
            size = max(8, int(base_size * scale))
            self.fonts[name].configure(size=size)

    def _update_logo(self, scale: float) -> None:
        if self._last_logo_scale == scale:
            return
        self._last_logo_scale = scale
        logo_scale = 0.5
        target_w = max(1, int(self.logo_original.width * scale * logo_scale))
        target_h = max(1, int(self.logo_original.height * scale * logo_scale))
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        resized = self.logo_original.resize((target_w, target_h), resample)
        self.logo_photo = ImageTk.PhotoImage(resized)
        self.canvas.itemconfigure(self.logo_item, image=self.logo_photo)

    def _update_background(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        size = (width, height)
        if self._last_bg_size == size:
            return
        self._last_bg_size = size
        scale = max(width / self.bg_original.width, height / self.bg_original.height)
        target_w = max(1, int(self.bg_original.width * scale))
        target_h = max(1, int(self.bg_original.height * scale))
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        resized = self.bg_original.resize((target_w, target_h), resample)
        left = max(0, (target_w - width) // 2)
        top = max(0, (target_h - height) // 2)
        cropped = resized.crop((left, top, left + width, top + height))
        self.bg_photo = ImageTk.PhotoImage(cropped)
        self.canvas.itemconfigure(self.bg_item, image=self.bg_photo)
        self.canvas.coords(self.bg_item, 0, 0)

    def _update_info_panel(self, width: int, height: int, scale: float) -> None:
        size = (max(1, int(width)), max(1, int(height)))
        if self._last_info_panel_size == size:
            return
        self._last_info_panel_size = size
        radius = max(6, int(18 * scale))
        border = max(1, int(2 * scale))
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        inset = max(0, border // 2)
        rect = (inset, inset, size[0] - inset - 1, size[1] - inset - 1)
        if hasattr(draw, "rounded_rectangle"):
            draw.rounded_rectangle(
                rect,
                radius=radius,
                fill=_hex_to_rgba(PANEL_FILL, PANEL_ALPHA),
                outline=_hex_to_rgba(PANEL_BORDER, PANEL_BORDER_ALPHA),
                width=border,
            )
        else:
            draw.rectangle(
                rect,
                fill=_hex_to_rgba(PANEL_FILL, PANEL_ALPHA),
                outline=_hex_to_rgba(PANEL_BORDER, PANEL_BORDER_ALPHA),
                width=border,
            )
        self.info_panel_photo = ImageTk.PhotoImage(img)
        self.canvas.itemconfigure(self.info_panel_item, image=self.info_panel_photo)

    def _layout(self) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        self._update_background(width, height)
        scale = min(width / BASE_WIDTH, height / BASE_HEIGHT)
        pad_x = (width - BASE_WIDTH * scale) / 2
        pad_y = (height - BASE_HEIGHT * scale) / 2

        self._set_font_scale(scale)
        self._update_logo(scale)

        info_w = INFO_PANEL_SIZE[0] * scale
        info_h = INFO_PANEL_SIZE[1] * scale
        info_x = pad_x + INFO_PANEL_POS[0] * scale
        info_y = pad_y + (INFO_PANEL_POS[1] + self._anim_offset) * scale
        self._update_info_panel(int(info_w), int(info_h), scale)
        self.canvas.coords(self.info_panel_item, info_x, info_y)

        info_center_x = info_x + info_w / 2
        self.canvas.coords(self.info_status_id, info_center_x, info_y + info_h * 0.22)
        self.canvas.coords(self.info_price_id, info_center_x, info_y + info_h * 0.42)
        time_y = info_y + info_h * 0.62
        time_x = info_center_x - max(0, int(50 * scale))
        self.canvas.coords(self.time_month_id, time_x, time_y)
        self.canvas.coords(self.time_rest_id, time_x, time_y)
        self.canvas.coords(self.info_version_current_id, info_center_x, info_y + info_h * 0.80)
        self.canvas.coords(self.info_version_latest_id, info_center_x, info_y + info_h * 0.92)

        help_x = pad_x + HELP_PANEL_POS[0] * scale
        help_y = pad_y + (HELP_PANEL_POS[1] + self._anim_offset) * scale
        help_pad_x = max(8, int(12 * scale))
        help_cursor_y = help_y
        self.canvas.coords(self.help_title1_id, help_x + help_pad_x, help_cursor_y)
        help_cursor_y += max(10, int(22 * scale))
        btn_w = HELP_BTN_W * scale
        btn_h = HELP_BTN_H * scale
        self.help_button1.place(x=help_x + help_pad_x, y=help_cursor_y, width=btn_w, height=btn_h, anchor="nw")
        self.help_button1.resize(btn_w, btn_h, scale)
        help_cursor_y += btn_h + max(10, int(16 * scale))
        self.canvas.coords(self.help_title2_id, help_x + help_pad_x, help_cursor_y)
        help_cursor_y += max(10, int(22 * scale))
        self.help_button2.place(x=help_x + help_pad_x, y=help_cursor_y, width=btn_w, height=btn_h, anchor="nw")
        self.help_button2.resize(btn_w, btn_h, scale)

        self.canvas.coords(
            self.logo_item,
            pad_x + LOGO_POS[0] * scale,
            pad_y + (LOGO_POS[1] + self._anim_offset) * scale,
        )
        self.canvas.coords(
            self.title_text_id,
            pad_x + TITLE_POS[0] * scale,
            pad_y + (TITLE_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.canvas.coords(
            self.api_label_id,
            pad_x + API_LABEL_POS[0] * scale,
            pad_y + (API_LABEL_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.api_row.place(
            pad_x + API_ENTRY_POS[0] * scale,
            pad_y + (API_ENTRY_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
            ENTRY_W * scale,
            ENTRY_H * scale,
            scale,
        )
        self.canvas.coords(
            self.secret_label_id,
            pad_x + SECRET_LABEL_POS[0] * scale,
            pad_y + (SECRET_LABEL_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.secret_row.place(
            pad_x + SECRET_ENTRY_POS[0] * scale,
            pad_y + (SECRET_ENTRY_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
            ENTRY_W * scale,
            ENTRY_H * scale,
            scale,
        )
        self.canvas.coords(
            self.note_text_id,
            pad_x + NOTE_POS[0] * scale,
            pad_y + (NOTE_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        login_w = LOGIN_W * scale
        login_h = LOGIN_H * scale
        self.login_button.place(
            x=pad_x + LOGIN_BTN_POS[0] * scale,
            y=pad_y + (LOGIN_BTN_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
            width=login_w,
            height=login_h,
            anchor="center",
        )
        self.login_button.resize(login_w, login_h, scale)
        self.canvas.coords(
            self.remember_text_id,
            pad_x + CHECK_POS[0] * scale,
            pad_y + (CHECK_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )
        self.canvas.coords(
            self.required_text_id,
            pad_x + REQUIRED_POS[0] * scale,
            pad_y + (REQUIRED_POS[1] + FORM_OFFSET_Y + self._anim_offset) * scale,
        )

        wrap = max(240, int(ENTRY_W * scale))
        self.canvas.itemconfigure(self.title_text_id, width=wrap)
        self.canvas.itemconfigure(self.note_text_id, width=wrap)
        self.canvas.itemconfigure(self.required_text_id, width=wrap)

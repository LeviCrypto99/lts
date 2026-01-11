from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont, ttk
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageTk

try:
    from tkwebview2.tkwebview2 import WebView2, have_runtime  # type: ignore
except Exception:
    WebView2 = None
    have_runtime = None

BASE_WIDTH = 1328
BASE_HEIGHT = 800

FONT_FAMILY = "Malgun Gothic"
CANVAS_BG = "#0b1020"
BACKGROUND_OFF_COLOR = "#222226"

BG_TOGGLE_POS = (BASE_WIDTH - 24, 28)
BG_TOGGLE_SIZE = 34

ANIM_DURATION_MS = 500
ANIM_OFFSET = 40
FPS = 60

PANEL_FILL = "#0b1220"
PANEL_BORDER = "#c4cedf"
PANEL_ALPHA = 165
PANEL_BORDER_ALPHA = 210
PANEL_RADIUS = 18
PANEL_BORDER_WIDTH = 2

TAB_ACTIVE_FILL = "#e6f0ff"
TAB_ACTIVE_BORDER = "#1f5eff"
TAB_INACTIVE_FILL = "#ffffff"
TAB_TEXT_COLOR = "#000000"

START_FILL = "#00b050"
STOP_FILL = "#ff0000"
BUTTON_TEXT_COLOR = "#ffffff"
BUTTON_ACTIVE_BORDER = "#1f5eff"

UI_TEXT_COLOR = "#f6f8fc"
HIGHLIGHT_TEXT = "#ff0000"
WALLET_VALUE_COLOR = "#0070c0"

# Base layout coordinates (scaled from image/ex_image/ex_image.png).
CHART_RECT = (49, 112, 770, 446)
TABLE_RECT = (47, 466, 765, 753)
TAB_DIVIDER_Y = 505

CAUTION_RECT = (791, 80, 1309, 256)
WALLET_RECT = (819, 263, 1292, 560)
PNL_RECT = (821, 586, 1290, 753)

START_BUTTON_RECT = (872, 475, 1042, 527)
STOP_BUTTON_RECT = (1090, 475, 1260, 527)

PNL_DROPDOWN_RECT = (841, 594, 1111, 621)
PNL_TOGGLE_RECT = (1186, 594, 1233, 621)
ROI_TOGGLE_RECT = (1233, 594, 1280, 621)


def _hex_to_rgba(value: str, alpha: int) -> Tuple[int, int, int, int]:
    value = value.lstrip("#")
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return r, g, b, alpha


def _round_rect_points(x1: float, y1: float, x2: float, y2: float, radius: float) -> list:
    r = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
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


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


class TradePage(tk.Frame):
    def __init__(self, master: tk.Widget) -> None:
        super().__init__(master, bg=CANVAS_BG)
        self.root = self.winfo_toplevel()
        self._supports_alpha = self._init_alpha_support()
        self._anim_offset = 0
        self._background_enabled = True
        self._bg_toggle_original = self._load_background_toggle_icon()
        self._bg_toggle_photo: Optional[ImageTk.PhotoImage] = None
        self._last_bg_toggle_size: Optional[int] = None
        self._last_bg_toggle_enabled: Optional[bool] = None

        self._base_fonts = {
            "tab": (12, "normal"),
            "caution_title": (12, "bold"),
            "caution_body": (11, "normal"),
            "caution_highlight": (11, "bold"),
            "wallet": (12, "normal"),
            "wallet_value": (12, "bold"),
            "button": (14, "bold"),
            "dropdown": (10, "normal"),
            "pnl_toggle": (9, "bold"),
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

        self.bg_toggle_item = self.canvas.create_image(0, 0, anchor="ne", tags=("bg_toggle",))
        self.canvas.tag_bind("bg_toggle", "<Button-1>", self._toggle_background)
        self.canvas.tag_bind("bg_toggle", "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("bg_toggle", "<Leave>", lambda _event: self.canvas.configure(cursor=""))

        self._panel_photos: Dict[str, ImageTk.PhotoImage] = {}
        self._panel_sizes: Dict[str, Tuple[int, int]] = {}

        self._position_tab = "active"
        self._trade_state = "start"
        self._pnl_mode = "PNL"
        self._chart_placeholder: Optional[tk.Label] = None

        self._style = ttk.Style(self)
        self._style.configure("Trade.TCombobox", font=self.fonts["dropdown"])

        self._create_widgets()
        self._bind_clickables()
        self._apply_background_mode()

        self.canvas.bind("<Configure>", self._on_resize)
        self._layout()

    def _create_widgets(self) -> None:
        self.chart_container = tk.Frame(self.canvas, bg="#ffffff", highlightthickness=0, bd=0)
        self.chart_window = self.canvas.create_window(0, 0, window=self.chart_container, anchor="nw")
        self.chart_widget: Optional[tk.Widget] = self._init_tradingview_widget(self.chart_container)

        self.pnl_dropdown = ttk.Combobox(
            self.canvas,
            values=["7 Days PNL History Chart", "30 Days PNL History Chart", "90 Days PNL History Chart"],
            state="readonly",
            style="Trade.TCombobox",
        )
        self.pnl_dropdown.set("7 Days PNL History Chart")
        self.pnl_dropdown_window = self.canvas.create_window(0, 0, window=self.pnl_dropdown, anchor="nw")

    def _load_background(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        bg_path = base_dir / "image" / "trade_page" / "trade_page_bg.png"
        return Image.open(bg_path).convert("RGBA")

    def _load_background_toggle_icon(self) -> Image.Image:
        base_dir = Path(__file__).resolve().parent
        icon_path = base_dir / "image" / "login_page" / "background_on_off.png"
        return Image.open(icon_path).convert("RGBA")

    def _toggle_background(self, _event: Optional[tk.Event] = None) -> None:
        self._background_enabled = not self._background_enabled
        self._apply_background_mode()
        self._layout()

    def _apply_background_mode(self) -> None:
        bg_color = CANVAS_BG if self._background_enabled else BACKGROUND_OFF_COLOR
        self.configure(bg=bg_color)
        self.canvas.configure(bg=bg_color)
        if self._background_enabled:
            self._last_bg_size = None
        else:
            self.canvas.itemconfigure(self.bg_item, image="")

    def _init_tradingview_widget(self, parent: tk.Widget) -> Optional[tk.Widget]:
        html_path = Path(__file__).resolve().parent / "image" / "trade_page" / "main_page_tradingview_widget.html"
        try:
            if WebView2 is None:
                return self._chart_placeholder_label(
                    parent,
                    "WebView2 위젯이 필요합니다.\n`pip install tkwebview2 pythonnet` 후 다시 실행하세요.",
                )
            if have_runtime is not None and not have_runtime():
                return self._chart_placeholder_label(
                    parent,
                    "WebView2 Runtime이 필요합니다.\nMicrosoft Edge WebView2 Runtime 설치 후 다시 실행하세요.",
                )
            widget = WebView2(parent, 1, 1)
            url = html_path.as_uri()
            if hasattr(widget, "load_url"):
                widget.load_url(url)
            elif hasattr(widget, "load_website"):
                widget.load_website(url)
            elif hasattr(widget, "load_file"):
                widget.load_file(str(html_path))
            widget.pack(fill="both", expand=True)
            return widget
        except Exception:
            return self._chart_placeholder_label(parent, "트뷰 위젯 초기화에 실패했습니다.")

    def _chart_placeholder_label(self, parent: tk.Widget, text: str) -> Optional[tk.Widget]:
        placeholder = tk.Label(
            parent,
            text=text,
            bg="#ffffff",
            fg="#000000",
            font=self.fonts["caution_body"],
            justify="center",
        )
        placeholder.pack(fill="both", expand=True)
        self._chart_placeholder = placeholder
        return None

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

    def _init_alpha_support(self) -> bool:
        try:
            self.root.attributes("-alpha", 1.0)
        except tk.TclError:
            return False
        return True

    def _bind_clickables(self) -> None:
        self._bind_tag("tab_active", lambda _e: self._set_position_tab("active"))
        self._bind_tag("tab_orders", lambda _e: self._set_position_tab("orders"))
        self._bind_tag("tab_history", lambda _e: self._set_position_tab("history"))

        self._bind_tag("trade_start", lambda _e: self._set_trade_state("start"))
        self._bind_tag("trade_stop", lambda _e: self._set_trade_state("stop"))

        self._bind_tag("toggle_pnl", lambda _e: self._set_pnl_mode("PNL"))
        self._bind_tag("toggle_roi", lambda _e: self._set_pnl_mode("ROI"))

    def _bind_tag(self, tag: str, handler) -> None:
        self.canvas.tag_bind(tag, "<Button-1>", handler)
        self.canvas.tag_bind(tag, "<Enter>", lambda _e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.configure(cursor=""))

    def _set_position_tab(self, value: str) -> None:
        if self._position_tab != value:
            self._position_tab = value
            self._layout()

    def _set_trade_state(self, value: str) -> None:
        if self._trade_state != value:
            self._trade_state = value
            self._layout()

    def _set_pnl_mode(self, value: str) -> None:
        if self._pnl_mode != value:
            self._pnl_mode = value
            self._layout()

    def _on_resize(self, _event: tk.Event) -> None:
        self._layout()

    def _set_font_scale(self, scale: float) -> None:
        for name, (base_size, weight) in self._base_fonts.items():
            size = max(8, int(base_size * scale))
            self.fonts[name].configure(size=size, weight=weight)
        self._style.configure("Trade.TCombobox", font=self.fonts["dropdown"])
        if self._chart_placeholder is not None:
            self._chart_placeholder.configure(font=self.fonts["caution_body"])

    def _update_background(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        if not self._background_enabled:
            self.canvas.itemconfigure(self.bg_item, image="")
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
        self.canvas.tag_lower(self.bg_item)

    def _update_background_toggle_icon(self, scale: float) -> None:
        size = max(16, int(BG_TOGGLE_SIZE * scale))
        if self._last_bg_toggle_size == size and self._last_bg_toggle_enabled == self._background_enabled:
            return
        self._last_bg_toggle_size = size
        self._last_bg_toggle_enabled = self._background_enabled
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        resized = self._bg_toggle_original.resize((size, size), resample)
        if not self._background_enabled:
            overlay = Image.new("RGBA", resized.size, (0, 0, 0, 140))
            resized = Image.alpha_composite(resized, overlay)
        self._bg_toggle_photo = ImageTk.PhotoImage(resized)
        self.canvas.itemconfigure(self.bg_toggle_item, image=self._bg_toggle_photo)

    def _panel_image(self, name: str, width: int, height: int, scale: float) -> ImageTk.PhotoImage:
        size = (max(1, int(width)), max(1, int(height)))
        if self._panel_sizes.get(name) == size:
            return self._panel_photos[name]
        self._panel_sizes[name] = size
        radius = max(6, int(PANEL_RADIUS * scale))
        border = max(1, int(PANEL_BORDER_WIDTH * scale))
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
        self._panel_photos[name] = ImageTk.PhotoImage(img)
        return self._panel_photos[name]

    def _scale_rect(self, rect: Tuple[int, int, int, int], scale: float, pad_x: float, pad_y: float) -> Tuple[float, float, float, float]:
        x1, y1, x2, y2 = rect
        return (
            pad_x + x1 * scale,
            pad_y + y1 * scale,
            pad_x + x2 * scale,
            pad_y + y2 * scale,
        )

    def _layout(self) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        scale = min(width / BASE_WIDTH, height / BASE_HEIGHT)
        pad_x = (width - BASE_WIDTH * scale) / 2
        pad_y = (height - BASE_HEIGHT * scale) / 2

        self._set_font_scale(scale)
        self._update_background(width, height)
        self._update_background_toggle_icon(scale)

        self.canvas.delete("ui")

        content_pad_y = pad_y + self._anim_offset * scale
        self._draw_chart(scale, pad_x, content_pad_y)
        self._draw_table(scale, pad_x, content_pad_y)
        self._draw_caution(scale, pad_x, content_pad_y)
        self._draw_wallet(scale, pad_x, content_pad_y)
        self._draw_pnl(scale, pad_x, content_pad_y)

        self.canvas.coords(
            self.bg_toggle_item,
            pad_x + BG_TOGGLE_POS[0] * scale,
            pad_y + (BG_TOGGLE_POS[1] + self._anim_offset) * scale,
        )
        self.canvas.tag_raise(self.bg_toggle_item)

    def _draw_chart(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(CHART_RECT, scale, pad_x, pad_y)
        border = max(1, int(2 * scale))
        self.canvas.create_rectangle(x1, y1, x2, y2, outline="#000000", width=border, fill="#ffffff", tags="ui")

        inset = max(2, int(3 * scale))
        self.canvas.coords(self.chart_window, x1 + inset, y1 + inset)
        self.canvas.itemconfigure(
            self.chart_window,
            width=max(1, int((x2 - x1) - inset * 2)),
            height=max(1, int((y2 - y1) - inset * 2)),
        )
        self.canvas.tag_raise(self.chart_window)

    def _draw_table(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(TABLE_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("table", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        divider_y = pad_y + TAB_DIVIDER_Y * scale
        border = max(1, int(1 * scale))
        self.canvas.create_line(x1, divider_y, x2, divider_y, fill="#000000", width=border, tags="ui")

        tab_width = (x2 - x1) / 3
        tab_height = divider_y - y1
        tabs = [
            ("active", "활성화된 포지션"),
            ("orders", "미체결 주문"),
            ("history", "포지션 히스토리"),
        ]
        for idx, (key, label) in enumerate(tabs):
            tx1 = x1 + tab_width * idx
            tx2 = tx1 + tab_width
            fill = TAB_ACTIVE_FILL if self._position_tab == key else TAB_INACTIVE_FILL
            outline = TAB_ACTIVE_BORDER if self._position_tab == key else "#000000"
            width = max(1, int((2 if self._position_tab == key else 1) * scale))
            self.canvas.create_rectangle(
                tx1,
                y1,
                tx2,
                y1 + tab_height,
                fill=fill,
                outline=outline,
                width=width,
                tags=("ui", f"tab_{key}"),
            )
            self.canvas.create_text(
                (tx1 + tx2) / 2,
                y1 + tab_height / 2,
                text=label,
                font=self.fonts["tab"],
                fill=TAB_TEXT_COLOR,
                anchor="center",
                tags=("ui", f"tab_{key}"),
            )

    def _draw_caution(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(CAUTION_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("caution", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        center_x = (x1 + x2) / 2
        box_h = y2 - y1
        line_gap = max(2, int(4 * scale))
        title_font = self.fonts["caution_title"]
        body_font = self.fonts["caution_body"]
        highlight_font = self.fonts["caution_highlight"]
        title_h = title_font.metrics("linespace")
        body_h = body_font.metrics("linespace")

        lines = [
            ("⚠️ 주의사항 ⚠️", title_font, "#ff0000"),
            ("보안을 위해 중앙서버 방식으로 통제되는 프로그램이 아니므로", body_font, UI_TEXT_COLOR),
            ("진행중인 포지션은 프로그램을 종료하셔도", body_font, UI_TEXT_COLOR),
            ("포지션이 자동으로 종료되지 않습니다.", highlight_font, HIGHLIGHT_TEXT),
            ("바이낸스 모바일 혹은 PC에서 포지션을 닫아주세요.", body_font, UI_TEXT_COLOR),
        ]
        total_height = title_h + body_h * 4 + line_gap * (len(lines) - 1)
        start_y = y1 + (box_h - total_height) / 2

        cursor_y = start_y
        for text, font, color in lines:
            self.canvas.create_text(
                center_x,
                cursor_y,
                text=text,
                font=font,
                fill=color,
                anchor="n",
                tags="ui",
            )
            cursor_y += font.metrics("linespace") + line_gap

    def _draw_wallet(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(WALLET_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("wallet", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        center_x = (x1 + x2) / 2
        label = "나의 지갑 잔고 :"
        value = "N"
        suffix = "USDT"
        font = self.fonts["wallet"]
        value_font = self.fonts["wallet_value"]

        label_w = font.measure(label + " ")
        value_w = value_font.measure(value + " ")
        suffix_w = font.measure(suffix)
        total_w = label_w + value_w + suffix_w
        text_y = y1 + (y2 - y1) * 0.35
        start_x = center_x - total_w / 2

        self.canvas.create_text(
            start_x + label_w / 2,
            text_y,
            text=label,
            font=font,
            fill=UI_TEXT_COLOR,
            anchor="center",
            tags="ui",
        )
        self.canvas.create_text(
            start_x + label_w + value_w / 2,
            text_y,
            text=value,
            font=value_font,
            fill=WALLET_VALUE_COLOR,
            anchor="center",
            tags="ui",
        )
        self.canvas.create_text(
            start_x + label_w + value_w + suffix_w / 2,
            text_y,
            text=suffix,
            font=font,
            fill=UI_TEXT_COLOR,
            anchor="center",
            tags="ui",
        )

        self._draw_trade_buttons(scale, pad_x, pad_y)

    def _draw_trade_buttons(self, scale: float, pad_x: float, pad_y: float) -> None:
        self._draw_rounded_button(
            START_BUTTON_RECT,
            "START",
            START_FILL,
            "trade_start",
            active=self._trade_state == "start",
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )
        self._draw_rounded_button(
            STOP_BUTTON_RECT,
            "Stop",
            STOP_FILL,
            "trade_stop",
            active=self._trade_state == "stop",
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )

    def _draw_rounded_button(
        self,
        rect: Tuple[int, int, int, int],
        text: str,
        fill: str,
        tag: str,
        active: bool,
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> None:
        x1, y1, x2, y2 = self._scale_rect(rect, scale, pad_x, pad_y)
        radius = max(6, int(10 * scale))
        border = max(1, int((3 if active else 1) * scale))
        outline = BUTTON_ACTIVE_BORDER if active else "#000000"
        points = _round_rect_points(x1, y1, x2, y2, radius)
        self.canvas.create_polygon(
            points,
            fill=fill,
            outline=outline,
            width=border,
            smooth=True,
            splinesteps=36,
            tags=("ui", tag),
        )
        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            font=self.fonts["button"],
            fill=BUTTON_TEXT_COLOR,
            anchor="center",
            tags=("ui", tag),
        )

    def _draw_pnl(self, scale: float, pad_x: float, pad_y: float) -> None:
        x1, y1, x2, y2 = self._scale_rect(PNL_RECT, scale, pad_x, pad_y)
        panel = self._panel_image("pnl", int(x2 - x1), int(y2 - y1), scale)
        self.canvas.create_image(x1, y1, image=panel, anchor="nw", tags="ui")

        # Dropdown
        dx1, dy1, dx2, dy2 = self._scale_rect(PNL_DROPDOWN_RECT, scale, pad_x, pad_y)
        self.canvas.coords(self.pnl_dropdown_window, dx1, dy1)
        self.canvas.itemconfigure(
            self.pnl_dropdown_window,
            width=max(1, int(dx2 - dx1)),
            height=max(1, int(dy2 - dy1)),
        )
        self.canvas.tag_raise(self.pnl_dropdown_window)

        # PNL/ROI toggles
        self._draw_toggle_button(
            PNL_TOGGLE_RECT,
            "PNL",
            "toggle_pnl",
            active=self._pnl_mode == "PNL",
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )
        self._draw_toggle_button(
            ROI_TOGGLE_RECT,
            "ROI",
            "toggle_roi",
            active=self._pnl_mode == "ROI",
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )

        # Chart grid + sample line
        plot_left = x1 + (x2 - x1) * 0.09
        plot_right = x2 - (x2 - x1) * 0.09
        plot_top = y1 + (y2 - y1) * 0.42
        plot_bottom = y2 - (y2 - y1) * 0.16
        grid_color = "#c4cedf"
        grid_width = max(1, int(1 * scale))
        for i in range(3):
            y = plot_top + (plot_bottom - plot_top) * (i / 2)
            self.canvas.create_line(plot_left, y, plot_right, y, fill=grid_color, width=grid_width, tags="ui")

        points = [
            (plot_left, plot_bottom),
            (plot_left + (plot_right - plot_left) * 0.12, plot_bottom - (plot_bottom - plot_top) * 0.55),
            (plot_left + (plot_right - plot_left) * 0.20, plot_bottom - (plot_bottom - plot_top) * 0.35),
            (plot_left + (plot_right - plot_left) * 0.28, plot_bottom - (plot_bottom - plot_top) * 0.45),
            (plot_left + (plot_right - plot_left) * 0.40, plot_bottom - (plot_bottom - plot_top) * 0.15),
            (plot_left + (plot_right - plot_left) * 0.55, plot_bottom - (plot_bottom - plot_top) * 0.35),
            (plot_left + (plot_right - plot_left) * 0.70, plot_bottom - (plot_bottom - plot_top) * 0.20),
        ]
        flat = [coord for point in points for coord in point]
        self.canvas.create_line(*flat, fill="#f0b400", width=max(1, int(2 * scale)), tags="ui")

    def _draw_toggle_button(
        self,
        rect: Tuple[int, int, int, int],
        text: str,
        tag: str,
        active: bool,
        scale: float,
        pad_x: float,
        pad_y: float,
    ) -> None:
        x1, y1, x2, y2 = self._scale_rect(rect, scale, pad_x, pad_y)
        fill = TAB_ACTIVE_FILL if active else "#ffffff"
        outline = TAB_ACTIVE_BORDER if active else "#000000"
        border = max(1, int((2 if active else 1) * scale))
        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill=fill,
            outline=outline,
            width=border,
            tags=("ui", tag),
        )
        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            font=self.fonts["pnl_toggle"],
            fill="#000000",
            anchor="center",
            tags=("ui", tag),
        )

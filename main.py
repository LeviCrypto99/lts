import json
import os
import re
import tempfile
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from itertools import zip_longest
from pathlib import Path
from tkinter import messagebox
from typing import Optional, Tuple

from PIL import Image, ImageTk

import config
from login_page import LoginPage

BASE_WIDTH = 1328
BASE_HEIGHT = 800

LOGO1_CENTER = (BASE_WIDTH / 2, BASE_HEIGHT * 0.35)
LOGO2_CENTER = (BASE_WIDTH / 2, BASE_HEIGHT * 0.70)

LOGO1_FADE_MS = 500
LOGO2_FADE_MS = 500
HOLD_AFTER_LOGO2_MS = 2000
FPS = 60
START_OFFSET = 60


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _parse_version(value: str) -> Tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", value)]
    return tuple(numbers) if numbers else (0,)


def _is_version_outdated(local: str, required: str) -> bool:
    local_parts = _parse_version(local)
    required_parts = _parse_version(required)
    for local_part, required_part in zip_longest(local_parts, required_parts, fillvalue=0):
        if local_part < required_part:
            return True
        if local_part > required_part:
            return False
    return False


def _fetch_version_info() -> dict:
    headers = {"User-Agent": "LTS-Updater"}
    token = os.getenv(config.UPDATE_AUTH_TOKEN_ENV)
    if token:
        headers["Authorization"] = f"token {token}"
    request = urllib.request.Request(config.UPDATE_INFO_URL, headers=headers)
    with urllib.request.urlopen(request, timeout=config.UPDATE_TIMEOUT_SEC) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected status: {response.status}")
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _download_file(url: str, target_path: Path) -> None:
    headers = {"User-Agent": "LTS-Updater"}
    token = os.getenv(config.UPDATE_AUTH_TOKEN_ENV)
    if token:
        headers["Authorization"] = f"token {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=config.UPDATE_TIMEOUT_SEC) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected status: {response.status}")
        with open(target_path, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)


def _download_and_run_updater(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    filename = Path(parsed.path).name or "LTS-Updater.exe"
    target_path = Path(tempfile.gettempdir()) / filename
    _download_file(url, target_path)
    if hasattr(os, "startfile"):
        os.startfile(str(target_path))
        return
    raise RuntimeError("Updater can only run on Windows.")


def _apply_alpha(img: Image.Image, alpha: float) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    r, g, b, a = img.split()
    a = a.point(lambda p: int(p * alpha))
    return Image.merge("RGBA", (r, g, b, a))


class LogoSprite:
    def __init__(self, canvas: tk.Canvas, path: Path, base_center: Tuple[float, float]):
        self.canvas = canvas
        self.original = Image.open(path).convert("RGBA")
        self.base_center = base_center
        self.alpha = 0.0
        self.offset = START_OFFSET
        self.photo: Optional[ImageTk.PhotoImage] = None
        self.item = self.canvas.create_image(0, 0, image=None)

    def render(self, scale: float, pad_x: float, pad_y: float) -> None:
        target_w = max(1, int(self.original.width * scale))
        target_h = max(1, int(self.original.height * scale))
        img = self.original
        if scale != 1.0:
            resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
            img = img.resize((target_w, target_h), resample)
        if self.alpha < 1.0:
            img = _apply_alpha(img, self.alpha)
        self.photo = ImageTk.PhotoImage(img)
        x = pad_x + self.base_center[0] * scale
        y = pad_y + (self.base_center[1] + self.offset) * scale
        self.canvas.itemconfigure(self.item, image=self.photo)
        self.canvas.coords(self.item, x, y)


class SplashApp:
    def __init__(self) -> None:
        self._latest_version = ""
        self.root = tk.Tk()
        self.root.title("LeviaAutoTradeSystem")
        self.root.configure(bg="white")
        self.root.withdraw()
        self._should_run = self._preflight_or_exit()
        if not self._should_run:
            self.root.destroy()
            return
        self.root.deiconify()

        self._setup_ui()

    def _setup_ui(self) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        scale = min(screen_w * 0.8 / BASE_WIDTH, screen_h * 0.8 / BASE_HEIGHT, 1.0)
        width = int(BASE_WIDTH * scale)
        height = int(BASE_HEIGHT * scale)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(int(BASE_WIDTH * 0.5), int(BASE_HEIGHT * 0.5))

        self.canvas = tk.Canvas(self.root, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        base_dir = Path(__file__).resolve().parent
        logo_dir = base_dir / "image" / "opening_page"
        self.logo1 = LogoSprite(self.canvas, logo_dir / "logo1.png", LOGO1_CENTER)
        self.logo2 = LogoSprite(self.canvas, logo_dir / "logo2.png", LOGO2_CENTER)
        self.logos = [self.logo1, self.logo2]

        self.canvas.bind("<Configure>", self._on_resize)
        self.root.after(0, self.start_sequence)

    def _layout(self) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        scale = min(width / BASE_WIDTH, height / BASE_HEIGHT)
        pad_x = (width - BASE_WIDTH * scale) / 2
        pad_y = (height - BASE_HEIGHT * scale) / 2
        for logo in self.logos:
            logo.render(scale, pad_x, pad_y)

    def _on_resize(self, _event: tk.Event) -> None:
        self._layout()

    def _animate_logo(self, logo: LogoSprite, duration_ms: int, on_done=None) -> None:
        frame_interval = int(1000 / FPS)
        total_frames = max(1, int(duration_ms / frame_interval))

        def step(frame: int = 0) -> None:
            t = min(1.0, frame / total_frames)
            eased = _ease_out_cubic(t)
            logo.alpha = eased
            logo.offset = START_OFFSET * (1 - eased)
            self._layout()
            if frame < total_frames:
                self.root.after(frame_interval, step, frame + 1)
            elif on_done is not None:
                on_done()

        step()

    def _show_blank(self) -> None:
        for logo in self.logos:
            logo.alpha = 0.0
            logo.offset = START_OFFSET
        self._layout()

    def start_sequence(self) -> None:
        self.logo1.alpha = 0.0
        self.logo1.offset = START_OFFSET
        self.logo2.alpha = 0.0
        self.logo2.offset = START_OFFSET
        self._layout()
        self._animate_logo(self.logo1, LOGO1_FADE_MS)
        self._animate_logo(self.logo2, LOGO2_FADE_MS)
        total_ms = max(LOGO1_FADE_MS, LOGO2_FADE_MS) + HOLD_AFTER_LOGO2_MS
        self.root.after(total_ms, self._show_login_page)

    def _show_login_page(self) -> None:
        self.canvas.destroy()
        self.root.title(f"LTS Launcher v{config.VERSION}")
        login_page = LoginPage(self.root, current_version=config.VERSION, latest_version=self._latest_version)
        login_page.pack(fill="both", expand=True)
        login_page.animate_in()

    def run(self) -> None:
        if self._should_run:
            self.root.mainloop()
    
    def _preflight_or_exit(self) -> bool:
        try:
            info = _fetch_version_info()
        except urllib.error.HTTPError as exc:
            messagebox.showerror(
                "업데이트 오류",
                f"업데이트 서버에 접근할 수 없습니다. (HTTP {exc.code})",
            )
            return False
        except urllib.error.URLError:
            messagebox.showerror("네트워크 오류", "인터넷에 연결되어 있지 않습니다. 인터넷 연결을 확인해주세요.")
            return False
        except json.JSONDecodeError:
            messagebox.showerror("업데이트 오류", "업데이트 정보 형식이 올바르지 않습니다.")
            return False
        except Exception:
            messagebox.showerror("업데이트 오류", "업데이트 정보를 확인할 수 없습니다.")
            return False

        required_version = info.get("min_version") or info.get("version")
        if not required_version:
            messagebox.showerror("업데이트 오류", "업데이트 버전 정보가 없습니다.")
            return False
        self._latest_version = str(required_version)

        if _is_version_outdated(config.VERSION, required_version):
            messagebox.showinfo("업데이트", "현재 실행중인 파일의 버전이 구버전이므로 패치를 진행합니다.")
            updater_url = info.get("updater_url") or config.UPDATER_URL
            if not updater_url:
                messagebox.showerror("업데이트 오류", "업데이트 파일 주소가 없습니다.")
                return False
            try:
                _download_and_run_updater(updater_url)
            except Exception:
                messagebox.showerror("업데이트 오류", "업데이트 파일 다운로드에 실패했습니다.")
            return False

        return True


if __name__ == "__main__":
    SplashApp().run()

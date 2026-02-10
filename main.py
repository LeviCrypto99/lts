import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
import time
import urllib.error
import urllib.parse
import urllib.request
from itertools import zip_longest
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image, ImageTk
except ModuleNotFoundError as exc:
    if exc.name in {"PIL", "PIL.Image", "PIL.ImageTk"}:
        raise SystemExit(
            "Pillow 모듈을 찾을 수 없습니다. "
            "`python -m pip install -r requirements.txt` 후 다시 실행해 주세요."
        ) from exc
    raise

import config
from exit import ExitManager
from update_security import extract_sha256_from_metadata, verify_file_sha256

try:
    import tkinter as tk
    from tkinter import messagebox
except ModuleNotFoundError as exc:
    if exc.name == "tkinter":
        raise SystemExit(
            "tkinter 모듈을 찾을 수 없습니다. "
            "Windows Python 환경에서 실행하거나 tkinter가 포함된 Python을 사용해 주세요."
        ) from exc
    raise


def _ensure_sta_thread() -> None:
    if sys.platform != "win32":
        return
    try:
        ole32 = ctypes.windll.ole32
    except Exception:
        return
    COINIT_APARTMENTTHREADED = 0x2
    hr = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    if hr not in (0, 1):
        if hr & 0xFFFFFFFF == 0x80010106:  # RPC_E_CHANGED_MODE
            return


_ensure_sta_thread()

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
SINGLE_INSTANCE_MUTEX_NAME = "Local\\LeviaAutoTradeSystem_Launcher"
LOG_PATH = Path(tempfile.gettempdir()) / "LTS-Launcher-update.log"
LOCAL_LOG_PATH = Path(__file__).resolve().parent / "LTS-Launcher-startup.log"
SINGLE_INSTANCE_LOCK_PATH = Path(tempfile.gettempdir()) / "LTS-Launcher.lock"

_SINGLE_INSTANCE_HANDLE = None
_SINGLE_INSTANCE_LOCKFILE = None
_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


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


def _log_update(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        for path in (LOG_PATH, LOCAL_LOG_PATH):
            try:
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(line)
            except Exception:
                pass
    except Exception:
        pass


def _show_already_running_message() -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("LTS", "LTS가 이미 실행중입니다.")
        root.destroy()
    except Exception:
        pass


def _acquire_single_instance_lock() -> bool:
    global _SINGLE_INSTANCE_HANDLE, _SINGLE_INSTANCE_LOCKFILE
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            mutex = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
            if not mutex:
                return True
            already_exists = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
            if already_exists:
                return False
            _SINGLE_INSTANCE_HANDLE = mutex
            return True
        except Exception:
            return True
    try:
        import fcntl

        handle = open(SINGLE_INSTANCE_LOCK_PATH, "w", encoding="utf-8")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _SINGLE_INSTANCE_LOCKFILE = handle
        return True
    except BlockingIOError:
        return False
    except Exception:
        return True


def _ensure_single_instance_or_exit() -> bool:
    if _acquire_single_instance_lock():
        return True
    _log_update("Detected existing launcher instance; exit new launch.")
    _show_already_running_message()
    return False


def _is_truthy_env_value(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in _TRUTHY_ENV_VALUES


def _should_allow_launch_on_update_check_failure() -> bool:
    strict_mode = _is_truthy_env_value(os.getenv(config.UPDATE_CHECK_STRICT_MODE_ENV))
    allow_launch = bool(config.ALLOW_LAUNCH_ON_UPDATE_CHECK_FAILURE) and not strict_mode
    _log_update(
        "Update-check failure policy: "
        f"allow_launch_default={config.ALLOW_LAUNCH_ON_UPDATE_CHECK_FAILURE} "
        f"strict_env={strict_mode} "
        f"result_allow_launch={allow_launch}"
    )
    return allow_launch


def _resolve_updater_sha256(version_info: dict, updater_url: str) -> Optional[str]:
    return extract_sha256_from_metadata(
        version_info,
        keys=(
            "updater_sha256",
            "updater_hash",
            "updater",
        ),
        file_url=updater_url,
    )


def _resolve_app_sha256(version_info: dict, app_url: str) -> Optional[str]:
    return extract_sha256_from_metadata(
        version_info,
        keys=(
            "app_sha256",
            "app_hash",
            "launcher_sha256",
            "launcher_hash",
            "app",
            "launcher",
        ),
        file_url=app_url,
    )


def _fetch_version_info() -> dict:
    headers = {
        "User-Agent": "LTS-Updater",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    token = os.getenv(config.UPDATE_AUTH_TOKEN_ENV)
    if token:
        headers["Authorization"] = f"token {token}"
    url = config.UPDATE_INFO_URL
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}t={int(time.time())}"
    request = urllib.request.Request(url, headers=headers)
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


def _download_and_run_updater(
    url: str,
    *,
    updater_sha256: str,
    app_sha256: str,
) -> None:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Updater must run from a packaged exe.")
    parsed = urllib.parse.urlparse(url)
    filename = Path(parsed.path).name or "LTS-Updater.exe"
    target_path = Path(tempfile.gettempdir()) / filename
    _log_update(f"Downloading updater: {url} -> {target_path}")
    _download_file(url, target_path)
    verified, actual_sha256 = verify_file_sha256(target_path, updater_sha256)
    if not verified:
        _log_update(
            "Updater SHA256 mismatch: "
            f"expected={updater_sha256} actual={actual_sha256} file={target_path}"
        )
        try:
            target_path.unlink()
        except Exception:
            pass
        raise RuntimeError("Updater SHA256 verification failed.")
    _log_update(
        f"Updater SHA256 verified: expected={updater_sha256} actual={actual_sha256}"
    )
    args = [
        str(target_path),
        "--target",
        sys.executable,
        "--version-url",
        config.UPDATE_INFO_URL,
        "--token-env",
        config.UPDATE_AUTH_TOKEN_ENV,
        "--expected-sha256",
        app_sha256,
    ]
    _log_update(f"Launching updater: {' '.join(args)}")
    subprocess.Popen(args, close_fds=True)


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
        self._exit_manager: Optional[ExitManager] = None
        self.root = tk.Tk()
        self.root.title("LeviaAutoTradeSystem")
        self.root.configure(bg="white")
        self.root.withdraw()
        self._should_run = self._preflight_or_exit()
        if not self._should_run and not getattr(sys, "frozen", False):
            _log_update("Preflight blocked; continue in dev mode.")
            self._should_run = True
        if not self._should_run:
            self.root.destroy()
            return
        self._exit_manager = ExitManager(self.root, app_name="LTS Launcher")
        self.root._exit_manager = self._exit_manager
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

    def _handle_update_check_failure(
        self,
        *,
        title: str,
        user_message: str,
        failure_code: str,
    ) -> bool:
        allow_launch = _should_allow_launch_on_update_check_failure()
        _log_update(
            f"Update preflight failure: code={failure_code} allow_launch={allow_launch}"
        )
        if allow_launch:
            messagebox.showwarning(
                "업데이트 확인 실패",
                (
                    f"{user_message}\n\n"
                    f"업데이트 확인에 실패했지만 현재 버전(v{config.VERSION})으로 실행을 계속합니다.\n"
                    f"네트워크가 복구되면 재실행 후 업데이트를 확인해 주세요.\n"
                    f"로그: {LOG_PATH}"
                ),
            )
            return True
        messagebox.showerror(
            title,
            f"{user_message}\n로그: {LOG_PATH}",
        )
        return False

    def _preflight_or_exit(self) -> bool:
        if os.getenv("LTS_SKIP_UPDATE") == "1":
            _log_update("Skip update preflight (LTS_SKIP_UPDATE=1).")
            return True
        try:
            info = _fetch_version_info()
        except urllib.error.HTTPError as exc:
            _log_update(f"Version info HTTPError: {exc.code} {exc.reason}")
            return self._handle_update_check_failure(
                title="업데이트 오류",
                user_message=f"업데이트 서버에 접근할 수 없습니다. (HTTP {exc.code})",
                failure_code=f"HTTP_{exc.code}",
            )
        except urllib.error.URLError:
            _log_update("Version info URLError")
            return self._handle_update_check_failure(
                title="네트워크 오류",
                user_message="인터넷에 연결되어 있지 않습니다. 인터넷 연결을 확인해주세요.",
                failure_code="URL_ERROR",
            )
        except json.JSONDecodeError:
            _log_update("Version info JSONDecodeError")
            return self._handle_update_check_failure(
                title="업데이트 오류",
                user_message="업데이트 정보 형식이 올바르지 않습니다.",
                failure_code="JSON_DECODE_ERROR",
            )
        except Exception:
            _log_update("Version info unexpected error:\n" + traceback.format_exc())
            return self._handle_update_check_failure(
                title="업데이트 오류",
                user_message="업데이트 정보를 확인할 수 없습니다.",
                failure_code="UNEXPECTED_ERROR",
            )

        if not isinstance(info, dict):
            _log_update(f"Version info invalid type: {type(info).__name__}")
            return self._handle_update_check_failure(
                title="업데이트 오류",
                user_message="업데이트 정보 응답 형식이 올바르지 않습니다.",
                failure_code="INVALID_RESPONSE_TYPE",
            )

        required_version = info.get("min_version") or info.get("version")
        if not required_version:
            _log_update("Missing required version in update info.")
            return self._handle_update_check_failure(
                title="업데이트 오류",
                user_message="업데이트 버전 정보가 없습니다.",
                failure_code="MISSING_REQUIRED_VERSION",
            )
        self._latest_version = str(required_version)
        _log_update(
            f"Update info: url={config.UPDATE_INFO_URL} local={config.VERSION} required={self._latest_version}"
        )

        if _is_version_outdated(config.VERSION, required_version):
            _log_update(f"Outdated: local={config.VERSION} required={required_version}")
            if not getattr(sys, "frozen", False):
                messagebox.showerror(
                    "업데이트 오류",
                    "업데이트는 배포된 exe에서만 진행됩니다. exe로 실행해 주세요.",
                )
                return False
            messagebox.showinfo("업데이트", "현재 실행중인 파일의 버전이 구버전이므로 패치를 진행합니다.")
            updater_url = info.get("updater_url") or config.UPDATER_URL
            if not updater_url:
                _log_update("Missing updater_url.")
                messagebox.showerror("업데이트 오류", "업데이트 파일 주소가 없습니다.")
                return False
            app_url = info.get("app_url") or info.get("download_url") or info.get("latest_url") or ""
            updater_sha256 = _resolve_updater_sha256(info, updater_url)
            app_sha256 = _resolve_app_sha256(info, app_url)
            if not updater_sha256:
                _log_update("Missing updater SHA256 in update metadata.")
                messagebox.showerror("업데이트 오류", "업데이트 파일 해시 정보(updater_sha256)가 없습니다.")
                return False
            if not app_sha256:
                _log_update("Missing app SHA256 in update metadata.")
                messagebox.showerror("업데이트 오류", "앱 파일 해시 정보(app_sha256)가 없습니다.")
                return False
            try:
                _download_and_run_updater(
                    updater_url,
                    updater_sha256=updater_sha256,
                    app_sha256=app_sha256,
                )
            except Exception:
                _log_update("Updater download/launch failed:\n" + traceback.format_exc())
                messagebox.showerror(
                    "업데이트 오류",
                    f"업데이트 파일 다운로드에 실패했습니다.\n로그: {LOG_PATH}",
                )
            return False

        _log_update("Preflight OK.")
        return True


if __name__ == "__main__":
    _log_update("Launcher main entry.")
    if not _ensure_single_instance_or_exit():
        sys.exit(0)
    try:
        SplashApp().run()
    except Exception:
        _log_update("Fatal error:\n" + traceback.format_exc())
        raise

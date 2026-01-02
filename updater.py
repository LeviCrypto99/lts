import argparse
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import Tk, messagebox


def _show_error(message: str) -> None:
    root = Tk()
    root.withdraw()
    messagebox.showerror("업데이트 오류", message)
    root.destroy()


def _show_info(message: str) -> None:
    root = Tk()
    root.withdraw()
    messagebox.showinfo("업데이트", message)
    root.destroy()


def _fetch_json(url: str, token_env: str, timeout: int) -> dict:
    headers = {
        "User-Agent": "LTS-Updater",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    token = os.getenv(token_env)
    if token:
        headers["Authorization"] = f"token {token}"
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}t={int(time.time())}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected status: {response.status}")
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _download_file(url: str, target_path: Path, token_env: str, timeout: int) -> None:
    headers = {"User-Agent": "LTS-Updater"}
    token = os.getenv(token_env)
    if token:
        headers["Authorization"] = f"token {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected status: {response.status}")
        with open(target_path, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)


def _resolve_download_url(download_url: str | None, version_url: str | None, token_env: str, timeout: int) -> str:
    if download_url:
        return download_url
    if not version_url:
        raise RuntimeError("Missing download URL.")
    info = _fetch_json(version_url, token_env, timeout)
    return info.get("app_url") or info.get("download_url") or info.get("latest_url") or ""


def _wait_for_unlock(path: Path, timeout_sec: int = 30) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with open(path, "rb"):
                return True
        except PermissionError:
            time.sleep(0.5)
        except FileNotFoundError:
            return True
    return False


def _replace_file(target_path: Path, new_path: Path) -> None:
    backup_path = target_path.with_suffix(target_path.suffix + ".bak")
    if backup_path.exists():
        try:
            backup_path.unlink()
        except Exception:
            pass
    os.replace(target_path, backup_path)
    os.replace(new_path, target_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="Path to the app executable to replace.")
    parser.add_argument("--download-url", help="Direct URL to the latest app executable.")
    parser.add_argument("--version-url", help="URL to version.json that contains app_url.")
    parser.add_argument("--token-env", default="LTS_UPDATE_TOKEN", help="Env var for optional auth token.")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        _show_error("업데이트 대상 파일을 찾을 수 없습니다.")
        return 1

    try:
        download_url = _resolve_download_url(args.download_url, args.version_url, args.token_env, args.timeout)
        if not download_url:
            _show_error("업데이트 파일 주소가 없습니다.")
            return 1
    except (urllib.error.URLError, urllib.error.HTTPError):
        _show_error("업데이트 서버에 접근할 수 없습니다.")
        return 1
    except json.JSONDecodeError:
        _show_error("업데이트 정보 형식이 올바르지 않습니다.")
        return 1
    except Exception:
        _show_error("업데이트 정보를 확인할 수 없습니다.")
        return 1

    temp_dir = Path(tempfile.gettempdir())
    temp_path = temp_dir / f"{target_path.stem}.new{target_path.suffix}"
    try:
        _download_file(download_url, temp_path, args.token_env, args.timeout)
    except Exception:
        _show_error("업데이트 파일 다운로드에 실패했습니다.")
        return 1

    time.sleep(1.5)
    if not _wait_for_unlock(target_path):
        _show_error("업데이트 적용을 위해 프로그램을 종료해 주세요.")
        return 1

    try:
        _replace_file(target_path, temp_path)
    except Exception:
        _show_error("업데이트 파일 적용에 실패했습니다.")
        return 1

    _show_info("업데이트가 완료되었습니다.")
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(target_path))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

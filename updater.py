import argparse
import json
import os
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from log_rotation import append_rotating_log_line
from runtime_paths import get_log_path
from update_security import extract_sha256_from_metadata, normalize_sha256, verify_file_sha256

try:
    from tkinter import Tk, messagebox
except ModuleNotFoundError:
    Tk = None
    messagebox = None

LOG_PATH = get_log_path("LTS-Updater.log")


def _log_update(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        append_rotating_log_line(LOG_PATH, f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _set_log_path_for_target(target_path: Path) -> None:
    global LOG_PATH
    LOG_PATH = get_log_path("LTS-Updater.log", target_executable=target_path)


def _show_error(message: str) -> None:
    if Tk is None or messagebox is None:
        _log_update("Tkinter unavailable for error dialog; fallback to console output.")
        print(f"[업데이트 오류] {message}")
        return
    try:
        root = Tk()
        root.withdraw()
        messagebox.showerror("업데이트 오류", message)
        root.destroy()
    except Exception:
        _log_update("Error dialog failed; fallback to console output.")
        print(f"[업데이트 오류] {message}")


def _show_info(message: str) -> None:
    if Tk is None or messagebox is None:
        _log_update("Tkinter unavailable for info dialog; fallback to console output.")
        print(f"[업데이트] {message}")
        return
    try:
        root = Tk()
        root.withdraw()
        messagebox.showinfo("업데이트", message)
        root.destroy()
    except Exception:
        _log_update("Info dialog failed; fallback to console output.")
        print(f"[업데이트] {message}")


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


def _resolve_download_plan(
    download_url: str | None,
    expected_sha256: Optional[str],
    version_url: str | None,
    token_env: str,
    timeout: int,
) -> tuple[str, str]:
    normalized_expected = normalize_sha256(expected_sha256) if expected_sha256 else None
    if download_url:
        if not normalized_expected:
            raise RuntimeError("Direct download requires --expected-sha256.")
        return download_url, normalized_expected
    if not version_url:
        raise RuntimeError("Missing download URL.")
    info = _fetch_json(version_url, token_env, timeout)
    if not isinstance(info, dict):
        raise RuntimeError("Invalid version metadata type.")

    resolved_url = info.get("app_url") or info.get("download_url") or info.get("latest_url") or ""
    if not resolved_url:
        raise RuntimeError("Missing app download URL in version metadata.")

    resolved_sha256 = normalized_expected or extract_sha256_from_metadata(
        info,
        keys=(
            "app_sha256",
            "app_hash",
            "launcher_sha256",
            "launcher_hash",
            "app",
            "launcher",
        ),
        file_url=resolved_url,
    )
    if not resolved_sha256:
        raise RuntimeError("Missing app SHA256 in version metadata.")
    return resolved_url, resolved_sha256


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


def _remove_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except Exception:
        return


def _derive_filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    filename = Path(parsed.path).name
    return urllib.parse.unquote(filename) if filename else ""


def _swap_in_new_file(
    target_path: Path,
    new_path: Path,
    desired_path: Path,
) -> Path | None:
    backup_path = target_path.with_suffix(target_path.suffix + ".bak")
    if backup_path.exists():
        _remove_file(backup_path)
    if desired_path == target_path:
        os.replace(target_path, backup_path)
        os.replace(new_path, target_path)
        return backup_path
    os.replace(target_path, backup_path)
    os.replace(new_path, desired_path)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="Path to the app executable to replace.")
    parser.add_argument("--download-url", help="Direct URL to the latest app executable.")
    parser.add_argument("--version-url", help="URL to version.json that contains app_url.")
    parser.add_argument("--expected-sha256", help="Expected SHA256 for downloaded app executable.")
    parser.add_argument("--token-env", default="LTS_UPDATE_TOKEN", help="Env var for optional auth token.")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    _set_log_path_for_target(target_path)
    _log_update(f"Updater log path resolved: {LOG_PATH}")
    _log_update(f"Start updater: target={target_path} version_url={args.version_url}")
    if not target_path.exists():
        _log_update("Target exe not found.")
        _show_error(f"업데이트 대상 파일을 찾을 수 없습니다.\n로그: {LOG_PATH}")
        return 1

    try:
        download_url, expected_sha256 = _resolve_download_plan(
            args.download_url,
            args.expected_sha256,
            args.version_url,
            args.token_env,
            args.timeout,
        )
        _log_update(
            "Resolved update plan: "
            f"url={download_url} expected_sha256={expected_sha256}"
        )
        if not download_url:
            _log_update("Missing download_url after resolve.")
            _show_error(f"업데이트 파일 주소가 없습니다.\n로그: {LOG_PATH}")
            return 1
    except (urllib.error.URLError, urllib.error.HTTPError):
        _log_update("Version info HTTP/URLError.")
        _show_error(f"업데이트 서버에 접근할 수 없습니다.\n로그: {LOG_PATH}")
        return 1
    except json.JSONDecodeError:
        _log_update("Version info JSONDecodeError.")
        _show_error(f"업데이트 정보 형식이 올바르지 않습니다.\n로그: {LOG_PATH}")
        return 1
    except Exception:
        _log_update("Version info unexpected error:\n" + traceback.format_exc())
        _show_error(f"업데이트 정보를 확인할 수 없습니다.\n로그: {LOG_PATH}")
        return 1

    download_name = _derive_filename_from_url(download_url)
    desired_path = target_path
    if download_name:
        desired_path = target_path.with_name(download_name)
    if desired_path != target_path:
        _log_update(f"Renaming target: {target_path.name} -> {desired_path.name}")

    temp_dir = Path(tempfile.gettempdir())
    temp_path = temp_dir / f"{desired_path.stem}.new{desired_path.suffix}"
    try:
        _log_update(f"Downloading app: {download_url} -> {temp_path}")
        _download_file(download_url, temp_path, args.token_env, args.timeout)
    except Exception:
        _log_update("App download failed:\n" + traceback.format_exc())
        _show_error(f"업데이트 파일 다운로드에 실패했습니다.\n로그: {LOG_PATH}")
        return 1

    try:
        verified, actual_sha256 = verify_file_sha256(temp_path, expected_sha256)
    except Exception:
        _log_update("SHA256 verification error:\n" + traceback.format_exc())
        _remove_file(temp_path)
        _show_error(f"업데이트 파일 무결성 검증 중 오류가 발생했습니다.\n로그: {LOG_PATH}")
        return 1

    if not verified:
        _log_update(
            "SHA256 mismatch: "
            f"expected={expected_sha256} actual={actual_sha256} file={temp_path}"
        )
        _remove_file(temp_path)
        _show_error(f"업데이트 파일 무결성 검증에 실패했습니다.\n로그: {LOG_PATH}")
        return 1
    _log_update(
        f"SHA256 verified: expected={expected_sha256} actual={actual_sha256}"
    )

    time.sleep(1.5)
    if not _wait_for_unlock(target_path):
        _log_update("Target file still locked.")
        _show_error(f"업데이트 적용을 위해 프로그램을 종료해 주세요.\n로그: {LOG_PATH}")
        return 1

    backup_path: Path | None = None
    try:
        backup_path = _swap_in_new_file(target_path, temp_path, desired_path)
    except Exception:
        _log_update("Replace file failed:\n" + traceback.format_exc())
        _show_error(f"업데이트 파일 적용에 실패했습니다.\n로그: {LOG_PATH}")
        return 1

    _log_update("Update completed.")
    _show_info("업데이트가 완료되었습니다.")
    try:
        if hasattr(os, "startfile"):
            os.startfile(str(desired_path))
            if backup_path:
                _remove_file(backup_path)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

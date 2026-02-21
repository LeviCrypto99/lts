import argparse
import os
import shlex
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import config


def _data_arg(src: Path, dest: str) -> str:
    sep = ";" if os.name == "nt" else ":"
    return f"{src}{sep}{dest}"


def _run_pyinstaller(args: list[str]) -> None:
    subprocess.check_call([sys.executable, "-m", "PyInstaller", *args])


def _write_single_png_ico(*, source_png: Path, target_ico: Path) -> None:
    png_bytes = source_png.read_bytes()
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"invalid_png_signature:{source_png}")
    if png_bytes[12:16] != b"IHDR":
        raise ValueError(f"invalid_png_ihdr:{source_png}")
    width = int.from_bytes(png_bytes[16:20], "big")
    height = int.from_bytes(png_bytes[20:24], "big")
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid_png_size:{source_png} width={width} height={height}")
    icon_width = width if width < 256 else 0
    icon_height = height if height < 256 else 0

    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack(
        "<BBBBHHII",
        icon_width,
        icon_height,
        0,
        0,
        1,
        32,
        len(png_bytes),
        6 + 16,
    )
    target_ico.write_bytes(header + entry + png_bytes)


def _resolve_shared_exe_icon(base_dir: Path) -> Path | None:
    source_icon = base_dir / "image" / "login_page" / "logo2.png"
    if not source_icon.exists():
        print(f"[build] Shared icon source missing, icon build skipped: {source_icon}")
        return None

    icon_dir = Path(tempfile.gettempdir()) / "lts_build_icons"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_path = icon_dir / "logo2_tray_shared.ico"
    try:
        _write_single_png_ico(source_png=source_icon, target_ico=icon_path)
    except Exception as exc:
        print(f"[build] Shared icon conversion failed, icon build skipped: {exc!r}")
        return None

    print(f"[build] Shared exe icon prepared from tray source: {icon_path}")
    return icon_path


def _build_launcher(
    base_dir: Path,
    clean: bool,
    console: bool,
    extra_args: list[str],
    shared_icon: Path | None,
) -> None:
    name = f"LTS V{config.VERSION}"
    args = [
        "--onefile",
        "--name",
        name,
        "--add-data",
        _data_arg(base_dir / "image", "image"),
    ]
    if clean:
        args.append("--clean")
    if not console:
        args.append("--noconsole")
    if shared_icon is not None:
        args.extend(["--icon", str(shared_icon)])
    args.extend(extra_args)
    args.append(str(base_dir / "main.py"))
    _run_pyinstaller(args)


def _build_updater(
    base_dir: Path,
    clean: bool,
    console: bool,
    extra_args: list[str],
    shared_icon: Path | None,
) -> None:
    args = [
        "--onefile",
        "--name",
        "LTS-Updater",
    ]
    if clean:
        args.append("--clean")
    if not console:
        args.append("--noconsole")
    if shared_icon is not None:
        args.extend(["--icon", str(shared_icon)])
    args.extend(extra_args)
    args.append(str(base_dir / "updater.py"))
    _run_pyinstaller(args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LTS launcher/updater with versioned launcher name.")
    parser.add_argument(
        "--target",
        choices=("launcher", "updater", "all"),
        default="all",
        help="Which artifact to build.",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Build with a console window (omit --noconsole).",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Skip PyInstaller --clean.",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    extra = shlex.split(os.getenv("PYINSTALLER_EXTRA_ARGS", ""))
    clean = not args.no_clean
    shared_icon = _resolve_shared_exe_icon(base_dir)

    if args.target in ("launcher", "all"):
        _build_launcher(base_dir, clean, args.console, extra, shared_icon)
    if args.target in ("updater", "all"):
        _build_updater(base_dir, clean, args.console, extra, shared_icon)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

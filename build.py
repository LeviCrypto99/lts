import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

import config


def _data_arg(src: Path, dest: str) -> str:
    sep = ";" if os.name == "nt" else ":"
    return f"{src}{sep}{dest}"


def _run_pyinstaller(args: list[str]) -> None:
    subprocess.check_call([sys.executable, "-m", "PyInstaller", *args])


def _build_launcher(base_dir: Path, clean: bool, console: bool, extra_args: list[str]) -> None:
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
    args.extend(extra_args)
    args.append(str(base_dir / "main.py"))
    _run_pyinstaller(args)


def _build_updater(base_dir: Path, clean: bool, console: bool, extra_args: list[str]) -> None:
    args = [
        "--onefile",
        "--name",
        "LTS-Updater",
    ]
    if clean:
        args.append("--clean")
    if not console:
        args.append("--noconsole")
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

    if args.target in ("launcher", "all"):
        _build_launcher(base_dir, clean, args.console, extra)
    if args.target in ("updater", "all"):
        _build_updater(base_dir, clean, args.console, extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

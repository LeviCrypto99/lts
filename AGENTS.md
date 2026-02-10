# Repository Guidelines

## Project Structure & Module Organization
- `main.py` is the launcher entry point (splash, version check, handoff to login).
- `login_page.py` and `trade_page.py` contain the main Tkinter UI flows.
- `updater.py` is the standalone updater executable logic; `build.py` wraps PyInstaller builds.
- `config.py` and `version.json` control versioning, update URLs, and timeout behavior.
- `indicators.py` and `exit.py` provide trading/exit support logic used by UI flows.
- `image/` stores runtime assets (PNG/JPG) and reference PDFs; keep relative paths stable.
- Built binaries (for example `LTS V1.9.1.exe`, `LTS-Updater.exe`) are produced at repo root.

## Build, Test, and Development Commands
- `python -m pip install -r requirements.txt`: install runtime dependencies.
- `python main.py`: run the launcher locally for manual validation.
- `python build.py --target launcher`: build launcher EXE with versioned name.
- `python build.py --target updater`: build updater EXE.
- `python build.py --target all`: build both artifacts.
- `PYINSTALLER_EXTRA_ARGS="--log-level DEBUG" python build.py --target all`: pass extra PyInstaller flags.

## Coding Style & Naming Conventions
- Use 4-space indentation and PEP 8 style as the default.
- Use `snake_case` for functions/variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Keep UI geometry/constants near the top of each UI module for quick layout tuning.
- Prefer small, focused functions and explicit imports over wildcard imports.

## Testing Guidelines
- There is no automated test suite yet.
- Run manual smoke tests before merging:
  - Start app with `python main.py` and verify splash/login flow.
  - Confirm image assets load from `image/` without missing-file errors.
  - Trigger update path and check logs in OS temp (for example `LTS-Launcher-update.log`).

## Commit & Pull Request Guidelines
- Recent commits use generic messages (`update`); prefer descriptive imperative messages instead (for example `Fix updater timeout retry`).
- Keep commits scoped to one logical change.
- PRs should include: summary, affected files, manual test steps/results, and UI screenshots when visuals change.

## Security & Configuration Tips
- Never commit secrets; use `LTS_UPDATE_TOKEN` from environment when needed.
- Review `config.py` and `version.json` carefully before release, especially update URLs/timeouts/version fields.


# Ruels

- Every single feature, regardless of size, must include logging statements.
- Features should never be implemented all at once. Always remember to build them step-by-step.
- Coding means strictly adhering to 100% of user requirements, not relying on AI inference. AI must consistently double-check if its proposed direction matches the user’s actual intent before proceeding.
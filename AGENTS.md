# Repository Guidelines

## Project Structure & Module Organization
- `main.py` launches the splash flow and hands off to the login UI.
- `login_page.py` owns the login window and UI layout constants.
- `updater.py` is the standalone updater executable logic.
- `config.py` centralizes versioning and update endpoints.
- `build.py` wraps PyInstaller builds.
- `image/` contains UI assets (PNG/JPG) and reference docs (PDF).
- Built artifacts like `LTS V1.4.0.exe` and `LTS-Updater.exe` live at repo root.

## Build, Test, and Development Commands
- `python -m pip install -r requirements.txt` installs Pillow and ccxt.
- `python main.py` runs the app locally (Tkinter UI).
- `python build.py --target launcher|updater|all` builds executables with PyInstaller.
- `PYINSTALLER_EXTRA_ARGS="..." python build.py` passes extra flags to PyInstaller.

## Coding Style & Naming Conventions
- 4-space indentation; keep a PEP 8–style layout.
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants (e.g., `BASE_WIDTH`).
- Keep UI geometry/constants grouped near the top of UI modules.

## Testing Guidelines
- No automated tests currently exist in this repo.
- Manual smoke tests: run `python main.py`, verify assets load from `image/`, and confirm update logs appear in the OS temp directory when triggered.

## Commit & Pull Request Guidelines
- Recent history uses short, generic commit messages like `update`; no formal convention is established.
- Prefer concise, descriptive imperative messages (e.g., `Fix updater timeout handling`).
- PRs should include a brief summary, test/validation steps, and screenshots for UI changes.

## Security & Configuration
- Updates can use the `LTS_UPDATE_TOKEN` env var (see `config.py`); never commit secrets.
- `version.json` and `config.py` control update URLs and timeouts—review before release.

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


### Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One tack per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fizing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimat Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

ㅡ
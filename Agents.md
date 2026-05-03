## Security Rules — NEVER PUSH PRIVATE DATA

- `settings.json` is in `.gitignore` — if it ever appears in `git status` as tracked, remove it with `git rm --cached settings.json`
- Never include endpoint URLs, API keys, or IP addresses in commit messages, code, or documentation
- If a user provides private credentials, store them only in `settings.json` (local) — never in code or pushed files
- Before every `git push`, run `git diff --cached` to verify no sensitive data is staged

## Git Workflow

This project uses two branches: `main` (stable) and `dev` (active development).

- Always work on the `dev` branch
- Before starting work, confirm we are on the `dev` branch
- After completing a task, commit changes with a descriptive message
- Do not merge to `main` unless explicitly asked
- Use conventional commit format: feat:, fix:, chore:, etc.

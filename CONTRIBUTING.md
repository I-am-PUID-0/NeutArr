# Contributing to NeutArr

Thanks for contributing.

## Branch Model

- `dev` is the default collaboration branch — open all feature and bugfix PRs here.
- `main` is the production and release branch — only release-please PRs land here.

## Basic Workflow

1. Fork the repository.
2. Create a branch from `dev`.
3. Make focused changes with clear commit messages ([Conventional Commits](https://www.conventionalcommits.org/) style).
4. Run checks locally before opening a PR (see below).
5. Open your PR to `dev`.

## Commit Style

NeutArr uses [Conventional Commits](https://www.conventionalcommits.org/). PR titles and commits are validated automatically.

Allowed types: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `revert`, `breaking`

Examples:
```
feat: add readarr quality upgrade support
fix: correct ipaddress CIDR validation for local bypass
chore: update pyjwt to 2.10.0
```

## Local Checks

```bash
# Lint
ruff check .
ruff format --check .

# Security scan (install once: pip install bandit)
bandit -r src/ main.py -ll
```

## Pull Request Expectations

- Use a Conventional Commit style title.
- Include a concise summary and testing notes in the PR description.
- Link related issues.
- Add or update documentation when behaviour changes.

## CI

The following checks run automatically on every PR:

| Check | Tool |
|:------|:-----|
| Conventional commit title | webiny/action-conventional-commits |
| Lint | Ruff |
| Python security scan | Bandit |
| Dependency vulnerabilities | pip-audit |

All checks must pass before merging.

## Dependabot

Dependabot sends weekly PRs for GitHub Actions and Python dependency updates, targeted to `dev`.

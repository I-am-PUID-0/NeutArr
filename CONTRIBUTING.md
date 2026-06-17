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
# Install dependencies
poetry install --no-root --with dev

# Run lint, format check, compile smoke check, and tests
make verify

# Optional: install git hooks
make pre-commit-install

# Optional security scan
make security
```

NeutArr does not use a Node/pnpm frontend build. The UI is Flask templates and static assets, so Python tooling is the source of truth for local checks.

The devcontainer uses a repo-local `.venv`. Keep Poetry virtualenvs enabled; disabling them can make dependency updates try to modify root-owned system packages in the base image.

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

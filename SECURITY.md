# Security policy

OpsBridge AI is a local portfolio demo, not a publicly deployed service. Run it only on a trusted workstation and keep the default loopback bindings.

## Reporting

Do not include passwords, session cookies, real personal data, internal documents, database files, or exploit payloads containing secrets in a report. Contact the repository owner privately before any future public disclosure. No public tracker or security mailbox has been established yet.

## Safe operation

- Never bind the API or Vite server to a non-loopback address without a separate threat review.
- Create accounts interactively; do not commit `.env`, databases, cookies, tokens, logs, screenshots with secrets, or demo passwords.
- Use only synthetic `DEMO-VPN-NNN` identities. The simulator must never be replaced with a real corporate connector without new design and authorization.
- Keep exact Origin, CSRF, HttpOnly/SameSite cookies, RBAC, version/hash/caducity checks, and separation of duties enabled.
- Treat ticket text and knowledge documents as untrusted data.
- Apply Alembic migrations after backing up any valuable local demo data; scripts never delete databases automatically.

## Known limitations

The open P2 list is maintained in `docs/ISSUES_PENDIENTES.md`. In particular: SQLite single-writer behavior, no verified LLM, limited browser coverage, and a single synthetic tool. `pip-audit 2.10.1` and `pnpm audit` found no known vulnerabilities in published dependencies at the 2026-10-29 cut; the editable local package is not on PyPI and was skipped. Local audit records are not tamper-proof.

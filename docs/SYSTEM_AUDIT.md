# System audit — 2026-11-21

The repository contained a static HTML/CSS/JS MVP only: no PHP, JavaScript runtime, controllers, migrations, database, routes, or existing business data. It was therefore safe to introduce a new local backend without overwriting legacy logic.

Implemented foundation: a dependency-free Python 3.9 HTTP API, SQLite test database, seed data, role-aware endpoint guards, branch-scoped queries, audit log writes and static client hosting. The API is intentionally local/testing only; production needs a framework, server-side sessions, CSRF protection, password reset, object storage and operational backups.

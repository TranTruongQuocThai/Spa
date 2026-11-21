# SpaFlow — local test system

SpaFlow is a local, dependency-free test application for spa and training management. The original repository had no backend or database, so this project introduces a Python 3.9 + SQLite implementation without replacing any legacy system.

## Run locally

```bash
cd "/Users/titus/CRM Quản Lý Spa"
python3 server.py --reset-db --port 8765
```

Open http://localhost:8765. First run creates `database/spaflow_test.sqlite3` and fictional seed data. Omit `--reset-db` to retain local changes; include it to reset test data.

Demo accounts: `admin/admin`, `cskh/cskh`, `manager.q1/manager`, and `student.mai/student`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests rebuild a disposable SQLite database and verify login, manager branch isolation, CRM creation, appointment creation, and duplicate-attendance protection.

## Included now

- Responsive SpaFlow UI and role-specific menus.
- Local API and SQLite schema/seed records for users, branches, customers, appointments, services, products, invoices, courses, classes, students, sessions, attendance, and audit logs.
- API login, branch-scoped RBAC foundation, dashboard/CRM data wiring, class/student history APIs, and attendance validation for enrollment and duplicate records.
- Camera/GPS check-in interface and manual-verification fallback.
- Audit, database, workflow, checklist and test documentation in `docs/`.

## Known limits

This is not production-ready. Payment/stock/commission write workflows, messaging, assignments, certificates and full CRUD screens for every module remain incomplete; see `docs/MODULE_CHECKLIST.md`. Production requires a selected framework, MySQL 8, private file storage, CSRF/session hardening, transaction-based financial and stock operations, backups, and browser E2E testing.

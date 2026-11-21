# Test report

Automated API regression tests live in `tests/test_api.py`. Run `python3 -m unittest discover -s tests -v`. They rebuild a disposable SQLite database and currently pass 9 tests covering login, role/branch isolation, customer create/update, appointment create/cancel, duplicate training attendance, payment status update, prevention of negative stock, CSKH authorization, services, products, reports, admin-only settings, and the staff lifecycle.

The staff workflow test creates a persisted employee with an account and multiple branches, creates a work shift, signs in as that employee, records photo/GPS staff check-in, verifies the record as Admin, and verifies that a branch manager cannot assign the Admin role.

Browser E2E has not run: Node/Playwright are not installed in this execution environment. Static UI wiring now also covers mobile drawer ARIA, overlay, Escape, navigation close, focus return and responsive CSS; manual viewport verification remains required. See `RESPONSIVE_TEST.md`.

Latest local regression run: 9/9 tests pass after introducing the dedicated personnel/RBAC workflow. Browser E2E has not run because Node/Playwright are unavailable in this environment.

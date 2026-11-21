# Test report

Automated API regression tests live in `tests/test_api.py`. Run `python3 -m unittest discover -s tests -v`. They rebuild a disposable SQLite database and currently pass 7 tests covering login, role/branch isolation, customer create/update, appointment create/cancel, duplicate attendance, payment status update, prevention of negative stock, CSKH authorization, services, products, reports and admin-only settings.

Browser E2E has not run: Node/Playwright are not installed in this execution environment. Static UI wiring now also covers mobile drawer ARIA, overlay, Escape, navigation close, focus return and responsive CSS; manual viewport verification remains required. See `RESPONSIVE_TEST.md`.

Latest local regression run: 8/8 tests pass after introducing the generic module CRUD API. Static route checks confirm that no navigation item uses the former generic “no API” placeholder.

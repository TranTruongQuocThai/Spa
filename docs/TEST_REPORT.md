# Test report

Automated API regression tests live in `tests/test_api.py`. Run `python3 -m unittest discover -s tests -v`. They rebuild a disposable SQLite database and currently pass 6 tests covering login, role/branch isolation, customer create/update, appointment create/cancel, duplicate attendance, payment status update, prevention of negative stock, and CSKH authorization.

Browser E2E has not run: Node/Playwright are not installed in this execution environment. Static UI wiring was checked for CRM and appointment API handlers, but manual viewport verification remains required after frontend API wiring.

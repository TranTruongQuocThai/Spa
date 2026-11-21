# Test report

Automated API regression tests live in `tests/test_api.py`. Run `python3 -m unittest discover -s tests -v`. They rebuild a disposable SQLite database and cover login, role/branch isolation, customer create, appointment create and duplicate attendance.

Browser E2E has not run: Node/Playwright are not installed in this execution environment. Manual viewport verification remains required after frontend API wiring.

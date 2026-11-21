# Database design

`server.py` creates `database/spaflow_test.sqlite3` on first run. Foreign keys are enabled for every connection. Core relations: branch → customer/service/product/class; course → class → session; student ↔ class through enrollment; session + student → one attendance record. The unique attendance constraint enforces one official check-in per student/session. The server seeds only fictional records.

For production, migrate this model to MySQL 8 with decimal money values, encrypted/private check-in files, retained audit history, server-side validation, scoped database queries and transaction wrappers for invoice/payment/stock operations.

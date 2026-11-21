# Module checklist

| Area | Status | Scope |
|---|---|---|
| Authentication / four demo roles | Working | API login, session token, logout API |
| Multiple branches / scope | Working foundation | API restricts CSKH/manager data by `branch_id`; Admin is global |
| CRM | Working foundation | List/search/create customer API |
| Appointment | Working foundation | List/create appointment API |
| Classes / students | Working read workflow | Class list, students, student attendance profile APIs |
| Attendance | Working foundation | Server validation: enrollment, one result/session; camera/GPS supplied by client |
| Inventory / invoices | Working read workflow | Branch-scoped list APIs and seeded data |
| Payments, commissions, cash, messages, assignments, certificates | Not implemented | Database/API work remains |
| UI integration with API | In progress | Existing dashboard remains MVP UI; API is ready for progressive wiring |

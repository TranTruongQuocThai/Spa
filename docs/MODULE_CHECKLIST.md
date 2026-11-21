# Module checklist

| Area | Status | Scope |
|---|---|---|
| Authentication / four demo roles | Working | API login, session token, logout API |
| Multiple branches / scope | Working foundation | API restricts CSKH/manager data by `branch_id`; Admin is global |
| CRM | Working | List/search/create/update customer API; UI create/edit form wired to API |
| Appointment | Working | List/create/cancel appointment API; UI create/cancel workflow wired to API |
| Classes / students | Working read workflow | Class list, students, student attendance profile APIs |
| Attendance | Working foundation | Server validation: enrollment, one result/session; camera/GPS supplied by client |
| Services & price list | Working foundation | Branch-scoped list/create/update, search/filter, form validation and role guard |
| Inventory | Working foundation | Branch-scoped product list/create/update plus transactional in/out/adjustment; negative stock is rejected |
| Invoices / payments | Working foundation | Branch-scoped invoice list, search/filter, payment form and transactional partial/full payment API |
| Reports | Working foundation | Branch-scoped revenue, paid/debt, appointment status and low-stock overview |
| System settings | Working foundation | Admin-only persisted spa name, support number and currency configuration |
| Shared module records | Working foundation | API-backed CRUD/search/filter for branches, staff, rooms, leads, aftercare, messages, schedules, results, tuition, materials and profile; role/branch scope enforced |
| Commissions, cash, assignments, certificates | Not implemented | Domain-specific database/API work remains |
| UI integration with API | In progress | No navigation item shows the former generic “no API” placeholder; specialized and generic module screens use API |
| Shared responsive shell | Code complete | Mobile sidebar overlay/close/Escape/navigation close, focus return, scroll lock, safe-area drawer/modal rules; browser viewport run pending |

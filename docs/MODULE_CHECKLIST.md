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
| Invoices / payments | Working foundation | Branch-scoped list plus transactional partial/full payment API |
| Reports | Working foundation | Branch-scoped revenue, paid/debt, appointment status and low-stock overview |
| System settings | Working foundation | Admin-only persisted spa name, support number and currency configuration |
| Commissions, cash, messages, assignments, certificates | Not implemented | Database/API work remains |
| UI integration with API | In progress | Dashboard, CRM, appointment, services, inventory, reports and settings use API; remaining modules use existing MVP screens |
| Shared responsive shell | Code complete | Mobile sidebar overlay/close/Escape/navigation close, focus return, scroll lock, safe-area drawer/modal rules; browser viewport run pending |

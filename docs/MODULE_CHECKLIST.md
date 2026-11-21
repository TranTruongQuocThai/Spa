# Module checklist

| Area | Status | Scope |
|---|---|---|
| Authentication / four demo roles | Working | API login, session token, logout API |
| Multiple branches / scope | Working foundation | API restricts CSKH/manager data by `branch_id`; Admin is global |
| CRM | Working | List/search/create/update customer API; UI create/edit form wired to API |
| Appointment | Working | List/create/cancel appointment API; UI create/cancel workflow wired to API |
| Classes / students | Working read workflow | Class list, students, student attendance profile APIs |
| Attendance | Working foundation | Server validation: enrollment, one result/session; camera/GPS supplied by client |
| Inventory | Working foundation | Branch-scoped list plus transactional in/out/adjustment API; negative stock is rejected |
| Invoices / payments | Working foundation | Branch-scoped list plus transactional partial/full payment API |
| Commissions, cash, messages, assignments, certificates | Not implemented | Database/API work remains |
| UI integration with API | In progress | Dashboard and CRM use API; appointment UI now creates/cancels records; remaining modules use existing MVP screens |

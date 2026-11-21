# SpaFlow MVP

Bản khởi tạo có thể chạy cục bộ cho hệ thống quản lý Spa/đào tạo đa vai trò. Source repository ban đầu trống, nên đây là nền tảng mới bằng HTML/CSS/JavaScript, không ghi đè hệ thống cũ.

## Chạy local

```bash
cd "/Users/titus/CRM Quản Lý Spa"
python3 -m http.server 8080 --directory dist
```

Mở `http://localhost:8080`. Dữ liệu demo (vai trò, chi nhánh, lần điểm danh) dùng `localStorage` để các tương tác không phải UI tĩnh. Camera/GPS hoạt động trên localhost hoặc HTTPS khi trình duyệt cấp quyền.

## Đã có

- Layout responsive theo thương hiệu SpaFlow và các vai trò Admin, CSKH, Quản lý chi nhánh, Học viên.
- Chuyển role/chi nhánh, dashboard KPI, CRM, lịch hẹn, lớp học và học viên.
- Luồng lớp → hồ sơ học viên → lịch sử điểm danh.
- Check-in camera/GPS, chụp ảnh khi xác nhận, fallback yêu cầu xác minh thủ công, ngăn UI tĩnh bằng lưu local.
- SQL schema khởi đầu cho bản PHP 8.3/MySQL ở `database/001_spaflow_schema.sql`.

## Giới hạn hiện tại

Chưa có source PHP/Laravel, MySQL, API, cơ chế đăng nhập hoặc hạ tầng lưu file trong repository ban đầu, do đó không thể tuyên bố các phần này đã hoàn thành. SQL migration là nền móng để triển khai backend thật; cần lựa chọn framework/connection MySQL trước khi đưa production.

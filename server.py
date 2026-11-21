#!/usr/bin/env python3
"""SpaFlow local server. Uses only Python stdlib and SQLite for demo/testing."""
import json, os, secrets, sqlite3, hashlib, hmac
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent
DB = Path(os.getenv("SPAFLOW_DATABASE", str(ROOT / "database" / "spaflow_test.sqlite3")))
SESSIONS = {}
ROLES = {"admin", "cskh", "manager", "student"}
MODULE_ACCESS = {
    "branches": {"admin"}, "staff": {"admin","manager"}, "rooms": {"admin","manager"},
    "leads": {"admin","cskh","manager"}, "aftercare": {"admin","cskh"}, "messages": {"admin","cskh"},
    "schedule": {"admin","manager","student"}, "results": {"admin","manager","student"},
    "tuition": {"admin","manager","student"}, "materials": {"admin","manager","student"},
    "profile": {"admin","cskh","manager","student"}, "finance": {"admin","manager"},
    "reports": {"admin","manager","cskh"}, "settings": {"admin"}
}

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def password(value):
    return hashlib.pbkdf2_hmac("sha256", value.encode(), b"spaflow-demo-v1", 120000).hex()

def init_db(reset=False):
    if reset and DB.exists(): DB.unlink()
    first = not DB.exists()
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS branches(id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, address TEXT, latitude REAL, longitude REAL, radius_m INTEGER DEFAULT 150, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, branch_id INTEGER, username TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','cskh','manager','student')), active INTEGER DEFAULT 1, FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, code TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, phone TEXT NOT NULL, customer_group TEXT DEFAULT 'Tiềm năng', status TEXT DEFAULT 'Mới tư vấn', created_at TEXT NOT NULL, FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, name TEXT NOT NULL, duration_min INTEGER NOT NULL, price REAL NOT NULL, active INTEGER DEFAULT 1, FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, sku TEXT NOT NULL, name TEXT NOT NULL, stock INTEGER NOT NULL DEFAULT 0, reorder_level INTEGER DEFAULT 5, price REAL NOT NULL, UNIQUE(branch_id,sku), FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, customer_id INTEGER NOT NULL, service_id INTEGER, starts_at TEXT NOT NULL, staff_name TEXT, status TEXT NOT NULL DEFAULT 'confirmed', note TEXT, created_at TEXT NOT NULL, FOREIGN KEY(branch_id) REFERENCES branches(id), FOREIGN KEY(customer_id) REFERENCES customers(id), FOREIGN KEY(service_id) REFERENCES services(id));
    CREATE TABLE IF NOT EXISTS service_rooms(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, name TEXT NOT NULL, active INTEGER DEFAULT 1, FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS appointment_events(id INTEGER PRIMARY KEY, appointment_id INTEGER NOT NULL, event_type TEXT NOT NULL, from_status TEXT, to_status TEXT, reason TEXT, actor_user_id INTEGER, created_at TEXT NOT NULL, FOREIGN KEY(appointment_id) REFERENCES appointments(id), FOREIGN KEY(actor_user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, tuition REAL NOT NULL, FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS classes(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, course_id INTEGER NOT NULL, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, teacher_name TEXT NOT NULL, starts_on TEXT, ends_on TEXT, schedule_text TEXT, status TEXT NOT NULL DEFAULT 'active', FOREIGN KEY(branch_id) REFERENCES branches(id), FOREIGN KEY(course_id) REFERENCES courses(id));
    CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, code TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, phone TEXT, branch_id INTEGER NOT NULL, enrolled_on TEXT, status TEXT DEFAULT 'active', FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS enrollments(id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, student_id INTEGER NOT NULL, status TEXT DEFAULT 'active', UNIQUE(class_id,student_id), FOREIGN KEY(class_id) REFERENCES classes(id), FOREIGN KEY(student_id) REFERENCES students(id));
    CREATE TABLE IF NOT EXISTS class_sessions(id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, room TEXT, is_open INTEGER DEFAULT 1, FOREIGN KEY(class_id) REFERENCES classes(id));
    CREATE TABLE IF NOT EXISTS attendance_records(id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, student_id INTEGER NOT NULL, status TEXT CHECK(status IN ('present','late','absent','excused','pending_verification')) NOT NULL, checked_in_at TEXT, photo_data TEXT, latitude REAL, longitude REAL, accuracy_m REAL, note TEXT, created_at TEXT NOT NULL, UNIQUE(session_id,student_id), FOREIGN KEY(session_id) REFERENCES class_sessions(id), FOREIGN KEY(student_id) REFERENCES students(id));
    CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, customer_id INTEGER, code TEXT UNIQUE NOT NULL, total REAL NOT NULL, paid REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'unpaid', created_at TEXT NOT NULL, FOREIGN KEY(branch_id) REFERENCES branches(id), FOREIGN KEY(customer_id) REFERENCES customers(id));
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, amount REAL NOT NULL, method TEXT NOT NULL, paid_at TEXT NOT NULL, FOREIGN KEY(invoice_id) REFERENCES invoices(id));
    CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY, branch_id INTEGER NOT NULL, product_id INTEGER NOT NULL, movement_type TEXT NOT NULL, quantity INTEGER NOT NULL, note TEXT, created_at TEXT NOT NULL, FOREIGN KEY(branch_id) REFERENCES branches(id), FOREIGN KEY(product_id) REFERENCES products(id));
    CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY, user_id INTEGER, branch_id INTEGER, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER, payload TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS application_settings(setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS module_records(id INTEGER PRIMARY KEY, branch_id INTEGER, owner_user_id INTEGER, module_key TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', details TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(branch_id) REFERENCES branches(id), FOREIGN KEY(owner_user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS staff_profiles(id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, employee_code TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT, birth_date TEXT, hire_date TEXT NOT NULL, employment_status TEXT NOT NULL DEFAULT 'active' CHECK(employment_status IN ('active','leave','terminated')), department TEXT, position_title TEXT, manager_staff_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(manager_staff_id) REFERENCES staff_profiles(id));
    CREATE TABLE IF NOT EXISTS staff_branches(staff_id INTEGER NOT NULL, branch_id INTEGER NOT NULL, is_primary INTEGER DEFAULT 0, PRIMARY KEY(staff_id,branch_id), FOREIGN KEY(staff_id) REFERENCES staff_profiles(id), FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS access_roles(id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, description TEXT, scope_type TEXT NOT NULL DEFAULT 'branch', active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS permissions(id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, module_key TEXT NOT NULL, action TEXT NOT NULL, description TEXT);
    CREATE TABLE IF NOT EXISTS role_permissions(role_id INTEGER NOT NULL, permission_id INTEGER NOT NULL, PRIMARY KEY(role_id,permission_id), FOREIGN KEY(role_id) REFERENCES access_roles(id), FOREIGN KEY(permission_id) REFERENCES permissions(id));
    CREATE TABLE IF NOT EXISTS user_role_assignments(user_id INTEGER NOT NULL, role_id INTEGER NOT NULL, branch_id INTEGER, assigned_by INTEGER, assigned_at TEXT NOT NULL, PRIMARY KEY(user_id,role_id,branch_id), FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(role_id) REFERENCES access_roles(id), FOREIGN KEY(branch_id) REFERENCES branches(id), FOREIGN KEY(assigned_by) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS work_shifts(id INTEGER PRIMARY KEY, staff_id INTEGER NOT NULL, branch_id INTEGER NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, shift_status TEXT NOT NULL DEFAULT 'scheduled' CHECK(shift_status IN ('scheduled','completed','cancelled')), note TEXT, created_at TEXT NOT NULL, FOREIGN KEY(staff_id) REFERENCES staff_profiles(id), FOREIGN KEY(branch_id) REFERENCES branches(id));
    CREATE TABLE IF NOT EXISTS staff_attendance_records(id INTEGER PRIMARY KEY, staff_id INTEGER NOT NULL, shift_id INTEGER, check_type TEXT NOT NULL CHECK(check_type IN ('check_in','check_out')), checked_at TEXT NOT NULL, photo_data TEXT, latitude REAL, longitude REAL, accuracy_m REAL, verification_status TEXT NOT NULL DEFAULT 'pending' CHECK(verification_status IN ('verified','pending','rejected')), note TEXT, created_at TEXT NOT NULL, FOREIGN KEY(staff_id) REFERENCES staff_profiles(id), FOREIGN KEY(shift_id) REFERENCES work_shifts(id));
    """)
    columns={x[1] for x in con.execute("PRAGMA table_info(appointments)")}
    for name,definition in [('staff_id','INTEGER'),('room_id','INTEGER'),('duration_min','INTEGER DEFAULT 60'),('checked_in_at','TEXT'),('started_at','TEXT'),('completed_at','TEXT'),('cancel_reason','TEXT'),('invoice_id','INTEGER')]:
        if name not in columns: con.execute(f"ALTER TABLE appointments ADD COLUMN {name} {definition}")
    if first:
        seed(con)
    else:
        now=datetime.now().isoformat(timespec="seconds")
        con.executemany("INSERT OR IGNORE INTO application_settings(setting_key,setting_value,updated_at) VALUES(?,?,?)",[("spa_name","SpaFlow",now),("support_phone","0900 000 000",now),("currency","VND",now)])
        if not con.execute("SELECT 1 FROM module_records LIMIT 1").fetchone():
            defaults={"branches":"Chi nhánh mẫu","staff":"Nhân sự mẫu","rooms":"Phòng dịch vụ mẫu","leads":"Lead tư vấn mẫu","aftercare":"Chăm sóc sau điều trị mẫu","messages":"Tin nhắn mẫu","schedule":"Lịch học mẫu","results":"Kết quả học tập mẫu","tuition":"Học phí mẫu","materials":"Tài liệu học tập mẫu","profile":"Hồ sơ cá nhân"}
            for key,title in defaults.items():
                owner=4 if key in {"schedule","results","tuition","materials","profile"} else None
                con.execute("INSERT INTO module_records(branch_id,owner_user_id,module_key,title,status,details,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(1,owner,key,title,'active','Dữ liệu mẫu',now,now))
        seed_staff_access(con)
    seed_staff_access(con)
    seed_appointment_rooms(con)
    con.commit(); con.close()

def seed_staff_access(con):
    now=datetime.now().isoformat(timespec="seconds")
    roles=[('admin','Admin','Quản trị toàn hệ thống','chain'),('manager','Quản lý chi nhánh','Điều hành dữ liệu trong chi nhánh được giao','branch'),('cskh','CSKH','Chăm sóc khách hàng và lịch hẹn','branch'),('employee','Nhân viên','Hồ sơ, ca làm và chấm công cá nhân','self')]
    con.executemany("INSERT OR IGNORE INTO access_roles(code,name,description,scope_type) VALUES(?,?,?,?)",roles)
    permissions=[
        ('staff.view','staff','view','Xem nhân sự'),('staff.create','staff','create','Tạo nhân sự'),('staff.update','staff','update','Cập nhật nhân sự'),('staff.terminate','staff','terminate','Khóa tài khoản/nghỉ việc'),
        ('shift.manage','shifts','manage','Phân ca'),('staff_attendance.checkin','staff_attendance','checkin','Tự chấm công'),('staff_attendance.review','staff_attendance','review','Duyệt/chỉnh chấm công'),
        ('roles.view','roles','view','Xem vai trò và quyền'),('roles.manage','roles','manage','Thiết lập quyền'),('audit.view','audit','view','Xem nhật ký')]
    con.executemany("INSERT OR IGNORE INTO permissions(code,module_key,action,description) VALUES(?,?,?,?)",permissions)
    grants={
        'admin':[p[0] for p in permissions],
        'manager':['staff.view','staff.create','staff.update','shift.manage','staff_attendance.review','roles.view'],
        'cskh':['staff_attendance.checkin'],
        'employee':['staff_attendance.checkin']}
    for role_code, permission_codes in grants.items():
        role_id=con.execute("SELECT id FROM access_roles WHERE code=?",(role_code,)).fetchone()[0]
        for permission_code in permission_codes:
            permission_id=con.execute("SELECT id FROM permissions WHERE code=?",(permission_code,)).fetchone()[0]
            con.execute("INSERT OR IGNORE INTO role_permissions(role_id,permission_id) VALUES(?,?)",(role_id,permission_id))
    if not con.execute("SELECT 1 FROM staff_profiles LIMIT 1").fetchone():
        people=[(1,'NV001','Admin SpaFlow','0901000001','admin@spaflow.vn','1988-01-10','2023-01-01','active','Ban điều hành','Quản trị hệ thống',None),
                (2,'NV002','Ngọc Anh CSKH','0901000002','ngocanh@spaflow.vn','1995-03-12','2024-02-01','active','Chăm sóc khách hàng','CSKH',1),
                (3,'NV003','Quản lý Quận 1','0901000003','manager.q1@spaflow.vn','1990-08-22','2022-06-15','active','Vận hành','Quản lý chi nhánh',1),
                (None,'NV004','KTV Lan Hương','0901000004','lanhuong@spaflow.vn','1997-10-04','2025-01-05','active','Dịch vụ','Kỹ thuật viên Spa',3),
                (None,'NV005','Lê Thu Hà','0901000005','thuha@spaflow.vn','1992-11-18','2023-05-20','leave','Đào tạo','Giảng viên',3)]
        for user_id,code,name,phone,email,birth,hire,status,dept,title,manager in people:
            cur=con.execute("INSERT INTO staff_profiles(user_id,employee_code,full_name,phone,email,birth_date,hire_date,employment_status,department,position_title,manager_staff_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(user_id,code,name,phone,email,birth,hire,status,dept,title,manager,now,now))
            staff_id=cur.lastrowid; branch_id=1 if code!='NV005' else 2
            con.execute("INSERT INTO staff_branches(staff_id,branch_id,is_primary) VALUES(?,?,1)",(staff_id,branch_id))
            if code=='NV004': con.execute("INSERT INTO staff_branches(staff_id,branch_id,is_primary) VALUES(?,?,0)",(staff_id,2))
    for user_id,role_code,branch_id in [(1,'admin',None),(2,'cskh',1),(3,'manager',1)]:
        role_id=con.execute("SELECT id FROM access_roles WHERE code=?",(role_code,)).fetchone()[0]
        con.execute("INSERT OR IGNORE INTO user_role_assignments(user_id,role_id,branch_id,assigned_at) VALUES(?,?,?,?)",(user_id,role_id,branch_id,now))

def seed_appointment_rooms(con):
    for branch_id in range(1,4):
        for name in ('Phòng 1','Phòng 2','Phòng VIP'):
            con.execute("INSERT INTO service_rooms(branch_id,name,active) SELECT ?,?,1 WHERE NOT EXISTS(SELECT 1 FROM service_rooms WHERE branch_id=? AND name=?)",(branch_id,name,branch_id,name))

def seed(con):
    branches=[("Q1","SpaFlow Quận 1","123 Nguyễn Trãi, Quận 1",10.7749,106.7009), ("Q7","SpaFlow Quận 7","56 Trần Xuân Soạn, Quận 7",10.7350,106.7050), ("TD","SpaFlow Thủ Đức","9 Võ Văn Ngân, Thủ Đức",10.8506,106.7719)]
    con.executemany("INSERT INTO branches(code,name,address,latitude,longitude) VALUES(?,?,?,?,?)",branches)
    users=[(None,"admin","Admin SpaFlow","admin","admin"),(1,"cskh","Ngọc Anh CSKH","cskh","cskh"),(1,"manager.q1","Quản lý Quận 1","manager","manager"),(1,"student.mai","Nguyễn Thị Mai","student","student")]
    con.executemany("INSERT INTO users(branch_id,username,full_name,password_hash,role) VALUES(?,?,?,?,?)",[(b,u,n,password(p),r) for b,u,n,r,p in users])
    now=datetime.now().isoformat(timespec="seconds")
    for i in range(1,51):
        branch=(i-1)%3+1
        con.execute("INSERT INTO customers(branch_id,code,full_name,phone,customer_group,status,created_at) VALUES(?,?,?,?,?,?,?)",(branch,f"KH{i:04d}",f"Khách hàng demo {i:02d}",f"090{i:07d}","Khách VIP" if i%7==0 else "Khách thân thiết", "Đang điều trị" if i%3==0 else "Mới tư vấn",now))
    for b in range(1,4):
        for i,name in enumerate(["Chăm sóc da chuyên sâu","Massage trị liệu","Điều trị mụn","Gội đầu dưỡng sinh","Cấy collagen","Triệt lông công nghệ cao","Phun xăm thẩm mỹ"]):
            con.execute("INSERT INTO services(branch_id,name,duration_min,price) VALUES(?,?,?,?)",(b,name,60+(i%3)*30,350000+i*120000))
        for i in range(10): con.execute("INSERT INTO products(branch_id,sku,name,stock,reorder_level,price) VALUES(?,?,?,?,?,?)",(b,f"SP{b}{i:02d}",f"Sản phẩm Spa {i+1}",3+i*4,8,95000+i*25000))
    for i in range(1,101):
        b=(i-1)%3+1; start=(datetime.now().replace(hour=9+(i%8),minute=0,second=0,microsecond=0)+timedelta(days=(i%7)-3)).isoformat(timespec="seconds")
        con.execute("INSERT INTO appointments(branch_id,customer_id,service_id,starts_at,staff_name,status,created_at) VALUES(?,?,?,?,?,?,?)",(b,(i-1)%50+1,(i-1)%21+1,start,"KTV Lan Hương",["confirmed","pending","completed"][i%3],now))
    for i in range(1,11): con.execute("INSERT INTO courses(branch_id,code,name,tuition) VALUES(?,?,?,?)",((i-1)%3+1,f"KH{i:02d}",f"Khóa đào tạo Spa {i:02d}",8000000+i*500000))
    for i in range(1,16):
        b=(i-1)%3+1; con.execute("INSERT INTO classes(branch_id,course_id,code,name,teacher_name,starts_on,ends_on,schedule_text,status) VALUES(?,?,?,?,?,?,?,?,?)",(b,(i-1)%10+1,f"SPA-K{i:02d}",f"Lớp Spa chuyên sâu K{i:02d}","Nguyễn Thu Hà","2026-11-01","2026-12-30","T2-T6 (08:30)","active" if i<10 else "upcoming"))
    for i in range(1,101):
        b=(i-1)%3+1; uid=4 if i==1 else None; con.execute("INSERT INTO students(user_id,code,full_name,phone,branch_id,enrolled_on) VALUES(?,?,?,?,?,?)",(uid,f"HV{i:05d}","Nguyễn Thị Mai" if i==1 else f"Học viên demo {i:03d}",f"093{i:07d}",b,"2026-11-01")); con.execute("INSERT INTO enrollments(class_id,student_id) VALUES(?,?)",((i-1)%15+1,i))
    base=datetime.now().replace(hour=8,minute=30,second=0,microsecond=0)
    for i in range(1,201): con.execute("INSERT INTO class_sessions(class_id,starts_at,ends_at,room,is_open) VALUES(?,?,?,?,?)",((i-1)%15+1,(base+timedelta(days=i-100)).isoformat(),(base+timedelta(days=i-100,hours=3)).isoformat(),"Phòng học A",1))
    for i in range(1,31): con.execute("INSERT INTO invoices(branch_id,customer_id,code,total,paid,status,created_at) VALUES(?,?,?,?,?,?,?)",((i-1)%3+1,i,f"HD{i:05d}",800000+i*100000,800000+i*50000,"paid" if i%2 else "partial",now))
    con.executemany("INSERT INTO application_settings(setting_key,setting_value,updated_at) VALUES(?,?,?)",[("spa_name","SpaFlow",now),("support_phone","0900 000 000",now),("currency","VND",now)])
    module_titles={"branches":"Chi nhánh","staff":"Nhân sự","rooms":"Phòng dịch vụ","leads":"Lead tư vấn","aftercare":"Chăm sóc sau điều trị","messages":"Tin nhắn","schedule":"Lịch học","results":"Kết quả học tập","tuition":"Học phí","materials":"Tài liệu học tập","profile":"Hồ sơ cá nhân","finance":"Thu chi","reports":"Báo cáo"}
    for key,label in module_titles.items():
        owner=4 if key in {"schedule","results","tuition","materials","profile"} else None
        con.execute("INSERT INTO module_records(branch_id,owner_user_id,module_key,title,status,details,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(1,owner,key,f"{label} mẫu",'active',f"Dữ liệu mẫu cho {label.lower()}",now,now))

def row(x): return dict(x) if x else None
def rows(xs): return [dict(x) for x in xs]

class App(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)
    def log_message(self, fmt,*args): print("[SpaFlow]",fmt%args)
    def json(self,status,data):
        raw=json.dumps(data,ensure_ascii=False,default=str).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def payload(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))).decode() or "{}")
        except json.JSONDecodeError: return {}
    def actor(self):
        token=self.headers.get("Authorization","").removeprefix("Bearer "); return SESSIONS.get(token)
    def require(self, roles=None):
        actor=self.actor()
        if not actor: self.json(401,{"error":"Phiên đăng nhập không hợp lệ"}); return None
        if roles and actor['role'] not in roles: self.json(403,{"error":"Bạn không có quyền thực hiện thao tác này"}); return None
        return actor
    def where(self, actor, table_branch="branch_id"):
        if actor['role']=='admin' or not table_branch: return "",[]
        if actor['role']=='student': return "",[]
        return f" WHERE {table_branch}=?",[actor['branch_id']]
    def audit(self,con,actor,action,entity,eid=None,payload=None): con.execute("INSERT INTO audit_logs(user_id,branch_id,action,entity,entity_id,payload,created_at) VALUES(?,?,?,?,?,?,?)",(actor['id'],actor['branch_id'],action,entity,eid,json.dumps(payload or {}),datetime.now().isoformat()))
    def module_authorized(self,actor,key,write=False):
        allowed=MODULE_ACCESS.get(key)
        if not allowed or actor['role'] not in allowed:
            self.json(403,{"error":"Bạn không có quyền truy cập module này"}); return False
        if write and actor['role']=='student':
            self.json(403,{"error":"Học viên chỉ có quyền xem dữ liệu cá nhân"}); return False
        return True
    def has_permission(self,con,actor,permission):
        if actor['role']=='admin': return True
        return con.execute("SELECT 1 FROM user_role_assignments ura JOIN role_permissions rp ON rp.role_id=ura.role_id JOIN permissions p ON p.id=rp.permission_id WHERE ura.user_id=? AND p.code=?",(actor['id'],permission)).fetchone() is not None
    def staff_scope(self,actor,alias='sp'):
        if actor['role']=='admin': return "",[]
        return f" WHERE EXISTS (SELECT 1 FROM staff_branches ss WHERE ss.staff_id={alias}.id AND ss.branch_id=?)",[actor['branch_id']]
    def staff_in_scope(self,con,actor,staff_id):
        if actor['role']=='admin': return True
        return con.execute("SELECT 1 FROM staff_branches WHERE staff_id=? AND branch_id=?",(staff_id,actor['branch_id'])).fetchone() is not None
    def can_manage_staff(self,con,actor,permission):
        if not self.has_permission(con,actor,permission):
            self.json(403,{"error":"Bạn không có quyền nhân sự phù hợp cho thao tác này"}); return False
        return True
    def appointment_allowed(self,actor):
        if actor['role'] not in ('admin','cskh','manager'):
            self.json(403,{"error":"Bạn không có quyền quản lý lịch hẹn"}); return False
        return True
    def appointment_conflict(self,con,branch_id,starts_at,duration_min,staff_id=None,room_id=None,exclude_id=None):
        end_at=(datetime.fromisoformat(starts_at)+timedelta(minutes=int(duration_min))).isoformat()
        filters=["branch_id=?","status NOT IN ('cancelled','completed','no_show')","starts_at < ?","datetime(starts_at,'+' || COALESCE(duration_min,60) || ' minutes') > ?"]
        args=[branch_id,end_at,starts_at]
        resources=[]
        if staff_id: resources.append(('staff_id',int(staff_id)))
        if room_id: resources.append(('room_id',int(room_id)))
        if not resources:return None
        resource_sql=' OR '.join(f"{field}=?" for field,_ in resources); args.extend(value for _,value in resources); filters.append('('+resource_sql+')')
        if exclude_id: filters.append('id<>?'); args.append(exclude_id)
        return row(con.execute("SELECT * FROM appointments WHERE "+' AND '.join(filters)+" LIMIT 1",args).fetchone())
    def appointment_event(self,con,actor,appointment_id,event_type,from_status=None,to_status=None,reason=None):
        con.execute("INSERT INTO appointment_events(appointment_id,event_type,from_status,to_status,reason,actor_user_id,created_at) VALUES(?,?,?,?,?,?,?)",(appointment_id,event_type,from_status,to_status,reason,actor['id'],datetime.now().isoformat()))
    def do_GET(self):
        p=urlparse(self.path); path=p.path
        if not path.startswith('/api/'):
            return super().do_GET()
        if path=='/api/health': return self.json(200,{"ok":True,"database":str(DB.name)})
        actor=self.require()
        if not actor:return
        con=db(); q=parse_qs(p.query)
        try:
            if path=='/api/me': data=actor
            elif path=='/api/branches': data=rows(con.execute("SELECT id,code,name,address FROM branches WHERE active=1"))
            elif path=='/api/staff':
                if not self.can_manage_staff(con,actor,'staff.view'): return
                clause,args=self.staff_scope(actor)
                data=rows(con.execute("SELECT sp.*,u.username,u.active account_active,COALESCE((SELECT group_concat(b.name,' | ') FROM staff_branches sb JOIN branches b ON b.id=sb.branch_id WHERE sb.staff_id=sp.id),'') branch_names,COALESCE((SELECT group_concat(ar.name,' | ') FROM user_role_assignments ura JOIN access_roles ar ON ar.id=ura.role_id WHERE ura.user_id=sp.user_id),'Chưa cấp tài khoản') role_names FROM staff_profiles sp LEFT JOIN users u ON u.id=sp.user_id"+clause+" ORDER BY sp.employee_code",args))
            elif path=='/api/staff/shifts':
                if not self.can_manage_staff(con,actor,'staff.view'): return
                clause,args=("",[]) if actor['role']=='admin' else (" WHERE ws.branch_id=?",[actor['branch_id']])
                data=rows(con.execute("SELECT ws.*,sp.employee_code,sp.full_name,b.name branch_name FROM work_shifts ws JOIN staff_profiles sp ON sp.id=ws.staff_id JOIN branches b ON b.id=ws.branch_id"+clause+" ORDER BY ws.starts_at DESC",args))
            elif path=='/api/staff/attendance':
                if not (self.has_permission(con,actor,'staff_attendance.review') or self.has_permission(con,actor,'staff_attendance.checkin')): return self.json(403,{"error":"Bạn không có quyền xem chấm công"})
                if actor['role']=='admin' or self.has_permission(con,actor,'staff_attendance.review'):
                    clause,args=("",[]) if actor['role']=='admin' else (" WHERE EXISTS (SELECT 1 FROM staff_branches sb WHERE sb.staff_id=sa.staff_id AND sb.branch_id=?)",[actor['branch_id']])
                else: clause,args=(" WHERE sp.user_id=?",[actor['id']])
                data=rows(con.execute("SELECT sa.*,sp.full_name,sp.employee_code,ws.starts_at shift_starts_at,ws.ends_at shift_ends_at FROM staff_attendance_records sa JOIN staff_profiles sp ON sp.id=sa.staff_id LEFT JOIN work_shifts ws ON ws.id=sa.shift_id"+clause+" ORDER BY sa.checked_at DESC",args))
            elif path=='/api/staff/reports':
                if not self.can_manage_staff(con,actor,'staff.view'): return
                clause,args=self.staff_scope(actor)
                total=con.execute("SELECT count(*) FROM staff_profiles sp"+clause,args).fetchone()[0]
                active=con.execute("SELECT count(*) FROM staff_profiles sp"+clause+(" AND" if clause else " WHERE")+" employment_status='active'",args).fetchone()[0]
                shift_clause,shift_args=("",[]) if actor['role']=='admin' else (" WHERE ws.branch_id=?",[actor['branch_id']])
                scheduled=con.execute("SELECT count(*) FROM work_shifts ws"+shift_clause,shift_args).fetchone()[0]
                attendance_clause,attendance_args=("",[]) if actor['role']=='admin' else (" WHERE EXISTS (SELECT 1 FROM staff_branches sb WHERE sb.staff_id=sa.staff_id AND sb.branch_id=?)",[actor['branch_id']])
                checkins=con.execute("SELECT count(*) FROM staff_attendance_records sa"+attendance_clause,attendance_args).fetchone()[0]
                data={"staff_total":total,"staff_active":active,"shifts":scheduled,"checkins":checkins,"by_status":rows(con.execute("SELECT employment_status status,count(*) total FROM staff_profiles sp"+clause+" GROUP BY employment_status",args))}
            elif path.startswith('/api/staff/'):
                if not self.can_manage_staff(con,actor,'staff.view'): return
                sid=int(path.rsplit('/',1)[1])
                if not self.staff_in_scope(con,actor,sid): return self.json(404,{"error":"Không tìm thấy nhân sự trong phạm vi của bạn"})
                profile=row(con.execute("SELECT sp.*,u.username,u.active account_active FROM staff_profiles sp LEFT JOIN users u ON u.id=sp.user_id WHERE sp.id=?",(sid,)).fetchone())
                if not profile:return self.json(404,{"error":"Không tìm thấy nhân sự"})
                data={"staff":profile,"branches":rows(con.execute("SELECT b.id,b.code,b.name,sb.is_primary FROM staff_branches sb JOIN branches b ON b.id=sb.branch_id WHERE sb.staff_id=?",(sid,))),"roles":rows(con.execute("SELECT ar.id,ar.code,ar.name,ura.branch_id FROM user_role_assignments ura JOIN access_roles ar ON ar.id=ura.role_id WHERE ura.user_id=?",(profile['user_id'],))) if profile['user_id'] else [],"shifts":rows(con.execute("SELECT * FROM work_shifts WHERE staff_id=? ORDER BY starts_at DESC LIMIT 20",(sid,))),"attendance":rows(con.execute("SELECT * FROM staff_attendance_records WHERE staff_id=? ORDER BY checked_at DESC LIMIT 20",(sid,)))}
            elif path=='/api/roles':
                if not self.can_manage_staff(con,actor,'roles.view'): return
                data=rows(con.execute("SELECT ar.*,count(DISTINCT ura.user_id) user_count FROM access_roles ar LEFT JOIN user_role_assignments ura ON ura.role_id=ar.id GROUP BY ar.id ORDER BY ar.id"))
            elif path=='/api/permissions':
                if not self.can_manage_staff(con,actor,'roles.view'): return
                data=rows(con.execute("SELECT p.*,COALESCE((SELECT group_concat(rp.role_id) FROM role_permissions rp WHERE rp.permission_id=p.id),'') role_ids FROM permissions p ORDER BY p.module_key,p.action"))
            elif path=='/api/dashboard':
                clause,args=self.where(actor); data={"customers":con.execute("SELECT count(*) FROM customers"+clause,args).fetchone()[0],"appointments":con.execute("SELECT count(*) FROM appointments"+clause,args).fetchone()[0],"students":con.execute("SELECT count(*) FROM students"+clause,args).fetchone()[0],"revenue":con.execute("SELECT COALESCE(sum(total),0) FROM invoices"+clause,args).fetchone()[0]}
            elif path=='/api/customers':
                clause,args=self.where(actor); term=q.get('q',[''])[0]; more=" AND" if clause else " WHERE"; data=rows(con.execute("SELECT * FROM customers"+clause+(more+" (full_name LIKE ? OR phone LIKE ?)") if term else "SELECT * FROM customers"+clause,args+([f'%{term}%',f'%{term}%'] if term else [])))
            elif path=='/api/appointment-resources':
                if not self.appointment_allowed(actor): return
                clause,args=self.where(actor); staff_args=[] if actor['role']=='admin' else [actor['branch_id']]; staff_sql="SELECT sp.id,sp.full_name,sp.position_title FROM staff_profiles sp WHERE sp.employment_status='active'"+(" AND EXISTS (SELECT 1 FROM staff_branches sb WHERE sb.staff_id=sp.id AND sb.branch_id=?)" if staff_args else ''); data={"customers":rows(con.execute("SELECT id,full_name,phone FROM customers"+clause+" ORDER BY full_name LIMIT 200",args)),"services":rows(con.execute("SELECT * FROM services"+clause+" AND active=1" if clause else "SELECT * FROM services WHERE active=1",args)),"staff":rows(con.execute(staff_sql,staff_args)),"rooms":rows(con.execute("SELECT * FROM service_rooms"+clause+" AND active=1" if clause else "SELECT * FROM service_rooms WHERE active=1",args))}
            elif path=='/api/appointments/availability':
                if not self.appointment_allowed(actor): return
                date=q.get('date',[datetime.now().date().isoformat()])[0]; duration=int(q.get('duration_min',[60])[0]); staff_id=q.get('staff_id',[None])[0]; room_id=q.get('room_id',[None])[0]; branch_id=int(q.get('branch_id',['1'])[0]) if actor['role']=='admin' else actor['branch_id']; slots=[]
                for hour in range(8,19):
                    starts_at=f"{date}T{hour:02d}:00:00"
                    if not self.appointment_conflict(con,branch_id,starts_at,duration,staff_id,room_id): slots.append(starts_at)
                data={"slots":slots,"duration_min":duration}
            elif path=='/api/appointments':
                if not self.appointment_allowed(actor): return
                clause,args=self.where(actor); status=q.get('status',[''])[0]; date=q.get('date',[''])[0]; conditions=[]
                if status: conditions.append(('a.status=?',status))
                if date: conditions.append(("date(a.starts_at)=?",date))
                base="SELECT a.*,c.full_name customer_name,s.name service_name,r.name room_name,sp.full_name staff_full_name FROM appointments a JOIN customers c ON c.id=a.customer_id LEFT JOIN services s ON s.id=a.service_id LEFT JOIN service_rooms r ON r.id=a.room_id LEFT JOIN staff_profiles sp ON sp.id=a.staff_id"+clause.replace('branch_id','a.branch_id')
                values=list(args)
                for condition,value in conditions: base+=(" AND " if ' WHERE ' in base else " WHERE ")+condition; values.append(value)
                data=rows(con.execute(base+" ORDER BY a.starts_at LIMIT 200",values))
            elif path.startswith('/api/appointments/'):
                if not self.appointment_allowed(actor): return
                aid=int(path.rsplit('/',1)[1]); current=row(con.execute("SELECT a.*,c.full_name customer_name,s.name service_name FROM appointments a JOIN customers c ON c.id=a.customer_id LEFT JOIN services s ON s.id=a.service_id WHERE a.id=?",(aid,)).fetchone())
                if not current or (actor['role']!='admin' and current['branch_id']!=actor['branch_id']):return self.json(404,{"error":"Không tìm thấy lịch hẹn"})
                data={"appointment":current,"events":rows(con.execute("SELECT ae.*,u.full_name actor_name FROM appointment_events ae LEFT JOIN users u ON u.id=ae.actor_user_id WHERE ae.appointment_id=? ORDER BY ae.created_at DESC",(aid,)))}
            elif path=='/api/classes':
                clause,args=self.where(actor); data=rows(con.execute("SELECT cl.*,co.name course_name,b.name branch_name,count(e.id) student_count FROM classes cl JOIN courses co ON co.id=cl.course_id JOIN branches b ON b.id=cl.branch_id LEFT JOIN enrollments e ON e.class_id=cl.id"+clause.replace('branch_id','cl.branch_id')+" GROUP BY cl.id ORDER BY cl.id",args))
            elif path.startswith('/api/classes/') and path.endswith('/students'):
                cid=int(path.split('/')[3]); data=rows(con.execute("SELECT s.*,e.status enrollment_status FROM enrollments e JOIN students s ON s.id=e.student_id WHERE e.class_id=?",(cid,)))
            elif path.startswith('/api/students/'):
                sid=int(path.split('/')[3]); student=row(con.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone());
                if not student: return self.json(404,{"error":"Không tìm thấy học viên"})
                data={"student":student,"attendance":rows(con.execute("SELECT ar.*,cs.starts_at,cs.ends_at,c.name class_name FROM attendance_records ar JOIN class_sessions cs ON cs.id=ar.session_id JOIN classes c ON c.id=cs.class_id WHERE ar.student_id=? ORDER BY cs.starts_at DESC",(sid,)))}
            elif path=='/api/attendance':
                if actor['role']=='student': data=rows(con.execute("SELECT ar.*,cs.starts_at,cs.ends_at,c.name class_name FROM attendance_records ar JOIN class_sessions cs ON cs.id=ar.session_id JOIN classes c ON c.id=cs.class_id JOIN students st ON st.id=ar.student_id WHERE st.user_id=? ORDER BY cs.starts_at DESC",(actor['id'],)))
                else: data=rows(con.execute("SELECT ar.*,st.full_name,cs.starts_at,c.name class_name FROM attendance_records ar JOIN students st ON st.id=ar.student_id JOIN class_sessions cs ON cs.id=ar.session_id JOIN classes c ON c.id=cs.class_id"))
            elif path=='/api/products':
                clause,args=self.where(actor); data=rows(con.execute("SELECT * FROM products"+clause,args))
            elif path=='/api/services':
                clause,args=self.where(actor); data=rows(con.execute("SELECT * FROM services"+clause,args))
            elif path=='/api/invoices':
                clause,args=self.where(actor); data=rows(con.execute("SELECT i.*,c.full_name customer_name FROM invoices i LEFT JOIN customers c ON c.id=i.customer_id"+clause.replace('branch_id','i.branch_id'),args))
            elif path=='/api/payments':
                clause,args=self.where(actor); data=rows(con.execute("SELECT p.*,i.code invoice_code FROM payments p JOIN invoices i ON i.id=p.invoice_id"+clause.replace('branch_id','i.branch_id')+" ORDER BY p.paid_at DESC",args))
            elif path=='/api/stock-movements':
                clause,args=self.where(actor); data=rows(con.execute("SELECT sm.*,p.name product_name FROM stock_movements sm JOIN products p ON p.id=sm.product_id"+clause.replace('branch_id','sm.branch_id')+" ORDER BY sm.created_at DESC",args))
            elif path=='/api/reports/overview':
                clause,args=self.where(actor); data={"revenue":con.execute("SELECT COALESCE(sum(total),0) FROM invoices"+clause,args).fetchone()[0],"paid":con.execute("SELECT COALESCE(sum(paid),0) FROM invoices"+clause,args).fetchone()[0],"debt":con.execute("SELECT COALESCE(sum(total-paid),0) FROM invoices"+clause,args).fetchone()[0],"appointments":rows(con.execute("SELECT status,count(*) total FROM appointments"+clause+" GROUP BY status",args)),"low_stock":rows(con.execute("SELECT name,stock,reorder_level FROM products"+clause+(" AND" if clause else " WHERE")+" stock<=reorder_level ORDER BY stock",args))}
            elif path=='/api/settings':
                if actor['role']!='admin': return self.json(403,{"error":"Chỉ Admin được xem cài đặt hệ thống"})
                data=rows(con.execute("SELECT setting_key,setting_value FROM application_settings ORDER BY setting_key"))
            elif path.startswith('/api/modules/'):
                key=path.rsplit('/',1)[1]
                if not self.module_authorized(actor,key): return
                if actor['role']=='student': data=rows(con.execute("SELECT * FROM module_records WHERE module_key=? AND owner_user_id=? ORDER BY updated_at DESC",(key,actor['id'])))
                elif actor['role']=='admin': data=rows(con.execute("SELECT * FROM module_records WHERE module_key=? ORDER BY updated_at DESC",(key,)))
                else: data=rows(con.execute("SELECT * FROM module_records WHERE module_key=? AND branch_id=? ORDER BY updated_at DESC",(key,actor['branch_id'])))
            else: return self.json(404,{"error":"API không tồn tại"})
            self.json(200,{"data":data})
        finally: con.close()
    def do_POST(self):
        path=urlparse(self.path).path; body=self.payload()
        if path=='/api/login':
            con=db(); user=row(con.execute("SELECT u.*,b.name branch_name FROM users u LEFT JOIN branches b ON b.id=u.branch_id WHERE u.username=? AND u.active=1",(body.get('username',''),)).fetchone()); con.close()
            if not user or not hmac.compare_digest(user['password_hash'],password(body.get('password',''))): return self.json(401,{"error":"Sai tài khoản hoặc mật khẩu"})
            token=secrets.token_urlsafe(32); user.pop('password_hash'); SESSIONS[token]=user; return self.json(200,{"token":token,"user":user})
        actor=self.require()
        if not actor:return
        con=db()
        try:
            if path=='/api/logout': SESSIONS.pop(self.headers.get('Authorization','').removeprefix('Bearer '),None); return self.json(200,{"ok":True})
            if path=='/api/staff':
                if not self.can_manage_staff(con,actor,'staff.create'): return
                name,phone,code=body.get('full_name','').strip(),body.get('phone','').strip(),body.get('employee_code','').strip()
                branch_ids=[int(x) for x in body.get('branch_ids',[]) if str(x).isdigit()]
                if not name or not phone or not code or not branch_ids:return self.json(422,{"error":"Mã nhân viên, họ tên, số điện thoại và ít nhất một chi nhánh là bắt buộc"})
                if actor['role']!='admin' and set(branch_ids)!={actor['branch_id']}:return self.json(403,{"error":"Quản lý chỉ có thể tạo nhân sự trong chi nhánh được giao"})
                requested_roles=body.get('role_codes',[]) or []
                if actor['role']!='admin' and any(r not in ('cskh','employee') for r in requested_roles):return self.json(403,{"error":"Quản lý không thể cấp vai trò vượt phạm vi"})
                now=datetime.now().isoformat(); user_id=None; account=body.get('account') or {}
                if account.get('username'):
                    username=account['username'].strip(); raw_password=account.get('password','').strip()
                    if len(raw_password)<4:return self.json(422,{"error":"Mật khẩu tài khoản cần tối thiểu 4 ký tự"})
                    primary_role='manager' if 'manager' in requested_roles else 'cskh'
                    user_id=con.execute("INSERT INTO users(branch_id,username,full_name,password_hash,role,active) VALUES(?,?,?,?,?,1)",(branch_ids[0],username,name,password(raw_password),primary_role)).lastrowid
                cur=con.execute("INSERT INTO staff_profiles(user_id,employee_code,full_name,phone,email,birth_date,hire_date,employment_status,department,position_title,manager_staff_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(user_id,code,name,phone,body.get('email','').strip(),body.get('birth_date'),body.get('hire_date') or datetime.now().date().isoformat(),body.get('employment_status','active'),body.get('department','').strip(),body.get('position_title','').strip(),body.get('manager_staff_id'),now,now)); sid=cur.lastrowid
                for i,bid in enumerate(branch_ids): con.execute("INSERT INTO staff_branches(staff_id,branch_id,is_primary) VALUES(?,?,?)",(sid,bid,1 if i==0 else 0))
                if user_id:
                    for role_code in requested_roles or ['employee']:
                        role_row=con.execute("SELECT id FROM access_roles WHERE code=? AND active=1",(role_code,)).fetchone()
                        if role_row: con.execute("INSERT INTO user_role_assignments(user_id,role_id,branch_id,assigned_by,assigned_at) VALUES(?,?,?,?,?)",(user_id,role_row[0],branch_ids[0],actor['id'],now))
                self.audit(con,actor,'create','staff',sid,{"employee_code":code,"branches":branch_ids,"roles":requested_roles})
            elif path=='/api/staff/shifts':
                if not self.can_manage_staff(con,actor,'shift.manage'): return
                staff_id=int(body.get('staff_id',0)); branch_id=int(body.get('branch_id') or actor['branch_id'] or 0)
                if not staff_id or not body.get('starts_at') or not body.get('ends_at'): return self.json(422,{"error":"Nhân sự, thời gian bắt đầu và kết thúc là bắt buộc"})
                if not self.staff_in_scope(con,actor,staff_id) or (actor['role']!='admin' and branch_id!=actor['branch_id']):return self.json(403,{"error":"Ca làm phải thuộc chi nhánh được giao"})
                cur=con.execute("INSERT INTO work_shifts(staff_id,branch_id,starts_at,ends_at,shift_status,note,created_at) VALUES(?,?,?,?,?,?,?)",(staff_id,branch_id,body['starts_at'],body['ends_at'],'scheduled',body.get('note',''),datetime.now().isoformat())); self.audit(con,actor,'create','work_shift',cur.lastrowid,body)
            elif path=='/api/staff/attendance':
                if not self.has_permission(con,actor,'staff_attendance.checkin'): return self.json(403,{"error":"Bạn không có quyền tự chấm công"})
                profile=row(con.execute("SELECT * FROM staff_profiles WHERE user_id=? AND employment_status='active'",(actor['id'],)).fetchone())
                if not profile:return self.json(403,{"error":"Tài khoản chưa được liên kết với hồ sơ nhân viên đang làm việc"})
                check_type=body.get('check_type','check_in'); shift_id=body.get('shift_id')
                if check_type not in ('check_in','check_out'):return self.json(422,{"error":"Loại chấm công không hợp lệ"})
                if not body.get('photo_data') or body.get('latitude') is None or body.get('longitude') is None:return self.json(422,{"error":"Chấm công cần ảnh chụp trực tiếp và vị trí GPS"})
                if shift_id and not con.execute("SELECT 1 FROM work_shifts WHERE id=? AND staff_id=?",(shift_id,profile['id'])).fetchone():return self.json(404,{"error":"Không tìm thấy ca làm được phân công"})
                cur=con.execute("INSERT INTO staff_attendance_records(staff_id,shift_id,check_type,checked_at,photo_data,latitude,longitude,accuracy_m,verification_status,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(profile['id'],shift_id,check_type,datetime.now().isoformat(),body['photo_data'],float(body['latitude']),float(body['longitude']),body.get('accuracy_m'),'pending',body.get('note',''),datetime.now().isoformat())); self.audit(con,actor,check_type,'staff_attendance',cur.lastrowid,{"shift_id":shift_id})
            elif path=='/api/roles':
                if not self.can_manage_staff(con,actor,'roles.manage'): return
                code,name=body.get('code','').strip(),body.get('name','').strip()
                if not code or not name:return self.json(422,{"error":"Mã và tên vai trò là bắt buộc"})
                cur=con.execute("INSERT INTO access_roles(code,name,description,scope_type,active) VALUES(?,?,?,?,1)",(code,name,body.get('description','').strip(),body.get('scope_type','branch'))); self.audit(con,actor,'create','role',cur.lastrowid,body)
            elif path=='/api/customers':
                if actor['role'] not in ('admin','cskh','manager'): return self.json(403,{"error":"Không có quyền tạo khách hàng"})
                name,phone=body.get('full_name','').strip(),body.get('phone','').strip()
                if not name or not phone:return self.json(422,{"error":"Họ tên và số điện thoại là bắt buộc"})
                bid=body.get('branch_id') if actor['role']=='admin' else actor['branch_id']; cur=con.execute("INSERT INTO customers(branch_id,code,full_name,phone,customer_group,status,created_at) VALUES(?,?,?,?,?,?,?)",(bid,f"KH{int(datetime.now().timestamp())}",name,phone,body.get('customer_group','Tiềm năng'),'Mới tư vấn',datetime.now().isoformat())); self.audit(con,actor,'create','customer',cur.lastrowid,body)
            elif path=='/api/appointments':
                if actor['role'] not in ('admin','cskh','manager'): return self.json(403,{"error":"Không có quyền đặt lịch"})
                for k in ('customer_id','starts_at'):
                    if not body.get(k): return self.json(422,{"error":"Thiếu trường "+k})
                bid=body.get('branch_id') if actor['role']=='admin' else actor['branch_id']; service_id=body.get('service_id'); service=row(con.execute("SELECT duration_min FROM services WHERE id=?",(service_id,)).fetchone()) if service_id else None; duration=int(body.get('duration_min') or (service['duration_min'] if service else 60)); staff_id=body.get('staff_id'); room_id=body.get('room_id')
                conflict=self.appointment_conflict(con,bid,body['starts_at'],duration,staff_id,room_id)
                if conflict:return self.json(409,{"error":"Trùng lịch nhân viên hoặc phòng trong khung giờ đã chọn"})
                cur=con.execute("INSERT INTO appointments(branch_id,customer_id,service_id,starts_at,staff_name,staff_id,room_id,duration_min,status,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(bid,body['customer_id'],service_id,body['starts_at'],body.get('staff_name','Chưa phân công'),staff_id,room_id,duration,'pending',body.get('note',''),datetime.now().isoformat())); self.appointment_event(con,actor,cur.lastrowid,'created',None,'pending'); self.audit(con,actor,'create','appointment',cur.lastrowid,body)
            elif path=='/api/attendance':
                if actor['role']!='student': return self.json(403,{"error":"Chỉ học viên được tự điểm danh"})
                student=row(con.execute("SELECT * FROM students WHERE user_id=?",(actor['id'],)).fetchone()); session_id=int(body.get('session_id',0)); session=row(con.execute("SELECT cs.*,c.branch_id FROM class_sessions cs JOIN classes c ON c.id=cs.class_id WHERE cs.id=?",(session_id,)).fetchone())
                if not session or not student:return self.json(404,{"error":"Không tìm thấy buổi học"})
                if not con.execute("SELECT 1 FROM enrollments WHERE class_id=? AND student_id=?",(session['class_id'],student['id'])).fetchone(): return self.json(403,{"error":"Bạn không thuộc lớp học này"})
                if con.execute("SELECT 1 FROM attendance_records WHERE session_id=? AND student_id=?",(session_id,student['id'])).fetchone(): return self.json(409,{"error":"Bạn đã có kết quả điểm danh cho buổi này"})
                status='present' if body.get('latitude') is not None and body.get('photo_data') else 'pending_verification'; cur=con.execute("INSERT INTO attendance_records(session_id,student_id,status,checked_in_at,photo_data,latitude,longitude,accuracy_m,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(session_id,student['id'],status,datetime.now().isoformat(),body.get('photo_data'),body.get('latitude'),body.get('longitude'),body.get('accuracy_m'),body.get('note'),datetime.now().isoformat())); self.audit(con,actor,'checkin','attendance',cur.lastrowid,{"status":status})
            elif path=='/api/services':
                if actor['role'] not in ('admin','manager'): return self.json(403,{"error":"Không có quyền thêm dịch vụ"})
                name=body.get('name','').strip(); duration=int(body.get('duration_min',0)); price=float(body.get('price',0))
                if not name or duration<=0 or price<0:return self.json(422,{"error":"Tên, thời lượng và giá dịch vụ không hợp lệ"})
                bid=body.get('branch_id') if actor['role']=='admin' else actor['branch_id']; cur=con.execute("INSERT INTO services(branch_id,name,duration_min,price,active) VALUES(?,?,?,?,1)",(bid,name,duration,price)); self.audit(con,actor,'create','service',cur.lastrowid,body)
            elif path=='/api/products':
                if actor['role'] not in ('admin','manager'): return self.json(403,{"error":"Không có quyền thêm sản phẩm"})
                name=body.get('name','').strip(); sku=body.get('sku','').strip(); stock=int(body.get('stock',0)); price=float(body.get('price',0)); reorder=int(body.get('reorder_level',5))
                if not name or not sku or stock<0 or price<0:return self.json(422,{"error":"Dữ liệu sản phẩm không hợp lệ"})
                bid=body.get('branch_id') if actor['role']=='admin' else actor['branch_id']; cur=con.execute("INSERT INTO products(branch_id,sku,name,stock,reorder_level,price) VALUES(?,?,?,?,?,?)",(bid,sku,name,stock,reorder,price)); self.audit(con,actor,'create','product',cur.lastrowid,body)
            elif path=='/api/stock-movements':
                if actor['role'] not in ('admin','manager'): return self.json(403,{"error":"Không có quyền điều chỉnh kho"})
                product_id=int(body.get('product_id',0)); quantity=int(body.get('quantity',0)); movement=body.get('movement_type')
                if not product_id or not quantity or movement not in ('in','out','adjustment'): return self.json(422,{"error":"Sản phẩm, số lượng và loại nhập/xuất là bắt buộc"})
                con.execute('BEGIN IMMEDIATE'); product=row(con.execute("SELECT * FROM products WHERE id=?",(product_id,)).fetchone())
                if not product or (actor['role']!='admin' and product['branch_id']!=actor['branch_id']): return self.json(404,{"error":"Không tìm thấy sản phẩm trong chi nhánh của bạn"})
                delta=abs(quantity) if movement=='in' else (-abs(quantity) if movement=='out' else quantity)
                if product['stock']+delta<0: return self.json(422,{"error":"Tồn kho không đủ để xuất"})
                con.execute("UPDATE products SET stock=stock+? WHERE id=?",(delta,product_id)); cur=con.execute("INSERT INTO stock_movements(branch_id,product_id,movement_type,quantity,note,created_at) VALUES(?,?,?,?,?,?)",(product['branch_id'],product_id,movement,delta,body.get('note',''),datetime.now().isoformat())); self.audit(con,actor,'stock_'+movement,'product',product_id,{"quantity":delta,"movement_id":cur.lastrowid})
            elif path=='/api/payments':
                if actor['role'] not in ('admin','manager','cskh'): return self.json(403,{"error":"Không có quyền thu tiền"})
                invoice_id=int(body.get('invoice_id',0)); amount=float(body.get('amount',0))
                if amount<=0:return self.json(422,{"error":"Số tiền thanh toán phải lớn hơn 0"})
                con.execute('BEGIN IMMEDIATE'); invoice=row(con.execute("SELECT * FROM invoices WHERE id=?",(invoice_id,)).fetchone())
                if not invoice or (actor['role']!='admin' and invoice['branch_id']!=actor['branch_id']): return self.json(404,{"error":"Không tìm thấy hóa đơn trong chi nhánh của bạn"})
                remaining=round(invoice['total']-invoice['paid'],2)
                if amount>remaining:return self.json(422,{"error":"Số tiền vượt quá công nợ còn lại"})
                new_paid=round(invoice['paid']+amount,2); status='paid' if new_paid>=invoice['total'] else 'partial'; cur=con.execute("INSERT INTO payments(invoice_id,amount,method,paid_at) VALUES(?,?,?,?)",(invoice_id,amount,body.get('method','cash'),datetime.now().isoformat())); con.execute("UPDATE invoices SET paid=?,status=? WHERE id=?",(new_paid,status,invoice_id)); self.audit(con,actor,'payment','invoice',invoice_id,{"payment_id":cur.lastrowid,"amount":amount})
            elif path=='/api/settings':
                if actor['role']!='admin': return self.json(403,{"error":"Chỉ Admin được thay đổi cài đặt hệ thống"})
                updates=body.get('settings',{})
                if not isinstance(updates,dict) or not updates:return self.json(422,{"error":"Không có cài đặt hợp lệ"})
                for key,value in updates.items():
                    if key not in ('spa_name','support_phone','currency'):return self.json(422,{"error":"Khóa cài đặt không hợp lệ"})
                    con.execute("INSERT INTO application_settings(setting_key,setting_value,updated_at) VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=excluded.updated_at",(key,str(value).strip(),datetime.now().isoformat()))
                self.audit(con,actor,'update','settings',None,updates)
            elif path.startswith('/api/modules/'):
                key=path.rsplit('/',1)[1]
                if not self.module_authorized(actor,key,True): return
                title=body.get('title','').strip(); details=body.get('details','').strip(); status=body.get('status','active')
                if not title:return self.json(422,{"error":"Tên bản ghi là bắt buộc"})
                bid=body.get('branch_id') if actor['role']=='admin' else actor['branch_id']; now=datetime.now().isoformat(); cur=con.execute("INSERT INTO module_records(branch_id,owner_user_id,module_key,title,status,details,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",(bid,None,key,title,status,details,now,now)); self.audit(con,actor,'create',key,cur.lastrowid,body)
            else:return self.json(404,{"error":"API không tồn tại"})
            con.commit(); self.json(201,{"ok":True})
        except sqlite3.IntegrityError as e: con.rollback(); self.json(409,{"error":"Dữ liệu bị trùng hoặc không hợp lệ","detail":str(e)})
        finally: con.close()
    def do_PUT(self):
        path=urlparse(self.path).path; body=self.payload(); actor=self.require()
        if not actor:return
        con=db()
        try:
            if path.startswith('/api/staff/'):
                pieces=path.split('/')
                if len(pieces)==4 and pieces[3].isdigit():
                    if not self.can_manage_staff(con,actor,'staff.update'): return
                    sid=int(pieces[3]); current=row(con.execute("SELECT * FROM staff_profiles WHERE id=?",(sid,)).fetchone())
                    if not current or not self.staff_in_scope(con,actor,sid):return self.json(404,{"error":"Không tìm thấy nhân sự trong phạm vi của bạn"})
                    status=body.get('employment_status',current['employment_status'])
                    if status not in ('active','leave','terminated'):return self.json(422,{"error":"Trạng thái làm việc không hợp lệ"})
                    branch_ids=body.get('branch_ids')
                    if branch_ids is not None:
                        branch_ids=[int(x) for x in branch_ids if str(x).isdigit()]
                        if not branch_ids:return self.json(422,{"error":"Nhân sự cần ít nhất một chi nhánh"})
                        if actor['role']!='admin' and set(branch_ids)!={actor['branch_id']}:return self.json(403,{"error":"Không được điều chuyển vượt chi nhánh được giao"})
                        con.execute("DELETE FROM staff_branches WHERE staff_id=?",(sid,))
                        for i,bid in enumerate(branch_ids):con.execute("INSERT INTO staff_branches(staff_id,branch_id,is_primary) VALUES(?,?,?)",(sid,bid,1 if i==0 else 0))
                    con.execute("UPDATE staff_profiles SET full_name=?,phone=?,email=?,birth_date=?,hire_date=?,employment_status=?,department=?,position_title=?,manager_staff_id=?,updated_at=? WHERE id=?",(body.get('full_name',current['full_name']).strip(),body.get('phone',current['phone']).strip(),body.get('email',current['email']),body.get('birth_date',current['birth_date']),body.get('hire_date',current['hire_date']),status,body.get('department',current['department']),body.get('position_title',current['position_title']),body.get('manager_staff_id',current['manager_staff_id']),datetime.now().isoformat(),sid))
                    if current['user_id'] and status in ('leave','terminated'):
                        con.execute("UPDATE users SET active=0 WHERE id=?",(current['user_id'],))
                        for token,session in list(SESSIONS.items()):
                            if session['id']==current['user_id']: SESSIONS.pop(token,None)
                    if current['user_id'] and body.get('role_codes') is not None:
                        requested_roles=body['role_codes']
                        if actor['role']!='admin' and any(r not in ('cskh','employee') for r in requested_roles):return self.json(403,{"error":"Quản lý không thể cấp vai trò vượt phạm vi"})
                        con.execute("DELETE FROM user_role_assignments WHERE user_id=?",(current['user_id'],))
                        for role_code in requested_roles:
                            role_row=con.execute("SELECT id FROM access_roles WHERE code=? AND active=1",(role_code,)).fetchone()
                            if role_row:con.execute("INSERT INTO user_role_assignments(user_id,role_id,branch_id,assigned_by,assigned_at) VALUES(?,?,?,?,?)",(current['user_id'],role_row[0],actor['branch_id'],actor['id'],datetime.now().isoformat()))
                    self.audit(con,actor,'update','staff',sid,body)
                else:return self.json(404,{"error":"API nhân sự không tồn tại"})
            elif path.startswith('/api/roles/'):
                if not self.can_manage_staff(con,actor,'roles.manage'): return
                role_id=int(path.rsplit('/',1)[1]); role=row(con.execute("SELECT * FROM access_roles WHERE id=?",(role_id,)).fetchone())
                if not role:return self.json(404,{"error":"Không tìm thấy vai trò"})
                con.execute("UPDATE access_roles SET name=?,description=?,scope_type=?,active=? WHERE id=?",(body.get('name',role['name']).strip(),body.get('description',role['description']),body.get('scope_type',role['scope_type']),int(body.get('active',role['active'])),role_id))
                if 'permission_ids' in body:
                    con.execute("DELETE FROM role_permissions WHERE role_id=?",(role_id,))
                    for permission_id in body['permission_ids']:
                        con.execute("INSERT OR IGNORE INTO role_permissions(role_id,permission_id) VALUES(?,?)",(role_id,int(permission_id)))
                self.audit(con,actor,'update','role',role_id,body)
            elif path.startswith('/api/customers/'):
                if actor['role'] not in ('admin','cskh','manager'): return self.json(403,{"error":"Không có quyền sửa khách hàng"})
                cid=int(path.rsplit('/',1)[1]); current=row(con.execute("SELECT * FROM customers WHERE id=?",(cid,)).fetchone())
                if not current or (actor['role']!='admin' and current['branch_id']!=actor['branch_id']): return self.json(404,{"error":"Không tìm thấy khách hàng"})
                name=body.get('full_name',current['full_name']).strip(); phone=body.get('phone',current['phone']).strip()
                if not name or not phone:return self.json(422,{"error":"Họ tên và số điện thoại là bắt buộc"})
                con.execute("UPDATE customers SET full_name=?,phone=?,customer_group=?,status=? WHERE id=?",(name,phone,body.get('customer_group',current['customer_group']),body.get('status',current['status']),cid)); self.audit(con,actor,'update','customer',cid,body)
            elif path.startswith('/api/appointments/'):
                if actor['role'] not in ('admin','cskh','manager'): return self.json(403,{"error":"Không có quyền sửa lịch hẹn"})
                aid=int(path.rsplit('/',1)[1]); current=row(con.execute("SELECT * FROM appointments WHERE id=?",(aid,)).fetchone())
                if not current or (actor['role']!='admin' and current['branch_id']!=actor['branch_id']): return self.json(404,{"error":"Không tìm thấy lịch hẹn"})
                starts_at=body.get('starts_at',current['starts_at']); duration=int(body.get('duration_min',current['duration_min'] or 60)); staff_id=body.get('staff_id',current['staff_id']); room_id=body.get('room_id',current['room_id']); conflict=self.appointment_conflict(con,current['branch_id'],starts_at,duration,staff_id,room_id,aid)
                if conflict:return self.json(409,{"error":"Trùng lịch nhân viên hoặc phòng trong khung giờ đã chọn"})
                status=body.get('status',current['status']); allowed={'pending','confirmed','in_progress','completed','cancelled','no_show'}
                if status not in allowed:return self.json(422,{"error":"Trạng thái lịch hẹn không hợp lệ"})
                extra=''; values=[starts_at,body.get('staff_name',current['staff_name']),staff_id,room_id,duration,status,body.get('note',current['note'])]
                if status=='confirmed':extra=', checked_in_at=checked_in_at'
                if status=='in_progress':extra=', started_at=COALESCE(started_at,?)'; values.append(datetime.now().isoformat())
                if status=='completed':
                    extra=', completed_at=COALESCE(completed_at,?)'; values.append(datetime.now().isoformat())
                    if not current['invoice_id']:
                        service=row(con.execute("SELECT price FROM services WHERE id=?",(current['service_id'],)).fetchone()); total=service['price'] if service else 0; invoice=con.execute("INSERT INTO invoices(branch_id,customer_id,code,total,paid,status,created_at) VALUES(?,?,?,?,0,'unpaid',?)",(current['branch_id'],current['customer_id'],f"HD{int(datetime.now().timestamp())}",total,datetime.now().isoformat())); extra+=', invoice_id=?'; values.append(invoice.lastrowid)
                values.append(aid); con.execute("UPDATE appointments SET starts_at=?,staff_name=?,staff_id=?,room_id=?,duration_min=?,status=?,note=?"+extra+" WHERE id=?",values); self.appointment_event(con,actor,'status_change' and aid,'status_change',current['status'],status,body.get('reason')); self.audit(con,actor,'update','appointment',aid,body)
            elif path.startswith('/api/services/'):
                if actor['role'] not in ('admin','manager'): return self.json(403,{"error":"Không có quyền sửa dịch vụ"})
                sid=int(path.rsplit('/',1)[1]); current=row(con.execute("SELECT * FROM services WHERE id=?",(sid,)).fetchone())
                if not current or (actor['role']!='admin' and current['branch_id']!=actor['branch_id']): return self.json(404,{"error":"Không tìm thấy dịch vụ"})
                name=body.get('name',current['name']).strip(); duration=int(body.get('duration_min',current['duration_min'])); price=float(body.get('price',current['price']))
                if not name or duration<=0 or price<0:return self.json(422,{"error":"Dữ liệu dịch vụ không hợp lệ"})
                con.execute("UPDATE services SET name=?,duration_min=?,price=?,active=? WHERE id=?",(name,duration,price,int(body.get('active',current['active'])),sid)); self.audit(con,actor,'update','service',sid,body)
            elif path.startswith('/api/products/'):
                if actor['role'] not in ('admin','manager'): return self.json(403,{"error":"Không có quyền sửa sản phẩm"})
                pid=int(path.rsplit('/',1)[1]); current=row(con.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone())
                if not current or (actor['role']!='admin' and current['branch_id']!=actor['branch_id']): return self.json(404,{"error":"Không tìm thấy sản phẩm"})
                name=body.get('name',current['name']).strip(); price=float(body.get('price',current['price'])); reorder=int(body.get('reorder_level',current['reorder_level']))
                if not name or price<0 or reorder<0:return self.json(422,{"error":"Dữ liệu sản phẩm không hợp lệ"})
                con.execute("UPDATE products SET name=?,price=?,reorder_level=? WHERE id=?",(name,price,reorder,pid)); self.audit(con,actor,'update','product',pid,body)
            elif path.startswith('/api/modules/'):
                pieces=path.split('/'); key=pieces[-2]; rid=int(pieces[-1])
                if not self.module_authorized(actor,key,True): return
                current=row(con.execute("SELECT * FROM module_records WHERE id=? AND module_key=?",(rid,key)).fetchone())
                if not current or (actor['role']!='admin' and current['branch_id']!=actor['branch_id']): return self.json(404,{"error":"Không tìm thấy bản ghi"})
                title=body.get('title',current['title']).strip(); details=body.get('details',current['details']).strip(); status=body.get('status',current['status'])
                if not title:return self.json(422,{"error":"Tên bản ghi là bắt buộc"})
                con.execute("UPDATE module_records SET title=?,details=?,status=?,updated_at=? WHERE id=?",(title,details,status,datetime.now().isoformat(),rid)); self.audit(con,actor,'update',key,rid,body)
            else:return self.json(404,{"error":"API không tồn tại"})
            con.commit(); self.json(200,{"ok":True})
        finally: con.close()
    def do_DELETE(self):
        path=urlparse(self.path).path; actor=self.require()
        if not actor:return
        con=db()
        try:
            if path.startswith('/api/appointments/'):
                if actor['role'] not in ('admin','cskh','manager'):return self.json(403,{"error":"Không có quyền hủy lịch hẹn"})
                aid=int(path.rsplit('/',1)[1]); current=row(con.execute("SELECT * FROM appointments WHERE id=?",(aid,)).fetchone())
                if not current or (actor['role']!='admin' and current['branch_id']!=actor['branch_id']):return self.json(404,{"error":"Không tìm thấy lịch hẹn"})
                con.execute("UPDATE appointments SET status='cancelled' WHERE id=?",(aid,)); self.audit(con,actor,'cancel','appointment',aid); con.commit(); return self.json(200,{"ok":True})
            if path.startswith('/api/modules/'):
                pieces=path.split('/'); key=pieces[-2]; rid=int(pieces[-1])
                if not self.module_authorized(actor,key,True): return
                current=row(con.execute("SELECT * FROM module_records WHERE id=? AND module_key=?",(rid,key)).fetchone())
                if not current or (actor['role']!='admin' and current['branch_id']!=actor['branch_id']):return self.json(404,{"error":"Không tìm thấy bản ghi"})
                con.execute("DELETE FROM module_records WHERE id=?",(rid,)); self.audit(con,actor,'delete',key,rid); con.commit(); return self.json(200,{"ok":True})
            return self.json(404,{"error":"API không tồn tại"})
        finally: con.close()

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--port',type=int,default=8765); ap.add_argument('--reset-db',action='store_true'); args=ap.parse_args(); init_db(args.reset_db); print(f"SpaFlow running at http://localhost:{args.port}"); ThreadingHTTPServer(('127.0.0.1',args.port),App).serve_forever()

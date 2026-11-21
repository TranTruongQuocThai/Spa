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
    """)
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
    con.commit(); con.close()

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
            elif path=='/api/dashboard':
                clause,args=self.where(actor); data={"customers":con.execute("SELECT count(*) FROM customers"+clause,args).fetchone()[0],"appointments":con.execute("SELECT count(*) FROM appointments"+clause,args).fetchone()[0],"students":con.execute("SELECT count(*) FROM students"+clause,args).fetchone()[0],"revenue":con.execute("SELECT COALESCE(sum(total),0) FROM invoices"+clause,args).fetchone()[0]}
            elif path=='/api/customers':
                clause,args=self.where(actor); term=q.get('q',[''])[0]; more=" AND" if clause else " WHERE"; data=rows(con.execute("SELECT * FROM customers"+clause+(more+" (full_name LIKE ? OR phone LIKE ?)") if term else "SELECT * FROM customers"+clause,args+([f'%{term}%',f'%{term}%'] if term else [])))
            elif path=='/api/appointments':
                clause,args=self.where(actor); data=rows(con.execute("SELECT a.*,c.full_name customer_name,s.name service_name FROM appointments a JOIN customers c ON c.id=a.customer_id LEFT JOIN services s ON s.id=a.service_id"+clause.replace('branch_id','a.branch_id')+" ORDER BY starts_at LIMIT 100",args))
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
            if path=='/api/customers':
                if actor['role'] not in ('admin','cskh','manager'): return self.json(403,{"error":"Không có quyền tạo khách hàng"})
                name,phone=body.get('full_name','').strip(),body.get('phone','').strip()
                if not name or not phone:return self.json(422,{"error":"Họ tên và số điện thoại là bắt buộc"})
                bid=body.get('branch_id') if actor['role']=='admin' else actor['branch_id']; cur=con.execute("INSERT INTO customers(branch_id,code,full_name,phone,customer_group,status,created_at) VALUES(?,?,?,?,?,?,?)",(bid,f"KH{int(datetime.now().timestamp())}",name,phone,body.get('customer_group','Tiềm năng'),'Mới tư vấn',datetime.now().isoformat())); self.audit(con,actor,'create','customer',cur.lastrowid,body)
            elif path=='/api/appointments':
                if actor['role'] not in ('admin','cskh','manager'): return self.json(403,{"error":"Không có quyền đặt lịch"})
                for k in ('customer_id','starts_at'):
                    if not body.get(k): return self.json(422,{"error":"Thiếu trường "+k})
                bid=body.get('branch_id') if actor['role']=='admin' else actor['branch_id']; cur=con.execute("INSERT INTO appointments(branch_id,customer_id,service_id,starts_at,staff_name,status,note,created_at) VALUES(?,?,?,?,?,?,?,?)",(bid,body['customer_id'],body.get('service_id'),body['starts_at'],body.get('staff_name','Chưa phân công'),'pending',body.get('note',''),datetime.now().isoformat())); self.audit(con,actor,'create','appointment',cur.lastrowid,body)
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
            if path.startswith('/api/customers/'):
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
                con.execute("UPDATE appointments SET starts_at=?,staff_name=?,status=?,note=? WHERE id=?",(body.get('starts_at',current['starts_at']),body.get('staff_name',current['staff_name']),body.get('status',current['status']),body.get('note',current['note']),aid)); self.audit(con,actor,'update','appointment',aid,body)
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

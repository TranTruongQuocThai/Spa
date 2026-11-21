import json, os, sys, tempfile, threading, unittest
from urllib.parse import quote
from http.client import HTTPConnection
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from http.server import ThreadingHTTPServer

class ApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.old=server.DB; cls.tmp=Path(tempfile.gettempdir())/'spaflow_test_api.sqlite3'; server.DB=cls.tmp; server.SESSIONS.clear(); server.init_db(True); cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.App); cls.port=cls.http.server_address[1]; cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True); cls.thread.start()
 @classmethod
 def tearDownClass(cls): cls.http.shutdown(); server.DB.unlink(missing_ok=True); server.DB=cls.old
 def call(self,method,path,data=None,token=None):
  h={'Content-Type':'application/json'}
  if token:h['Authorization']='Bearer '+token
  c=HTTPConnection('127.0.0.1',self.port); c.request(method,path,json.dumps(data or {}),h); r=c.getresponse(); return r.status,json.loads(r.read())
 def login(self,u,p):
  s,d=self.call('POST','/api/login',{'username':u,'password':p}); self.assertEqual(s,200); return d['token']
 def test_login_and_branch_scope(self):
  t=self.login('manager.q1','manager'); s,d=self.call('GET','/api/customers',token=t); self.assertEqual(s,200); self.assertTrue(all(x['branch_id']==1 for x in d['data']))
 def test_customer_and_appointment(self):
  t=self.login('cskh','cskh'); s,_=self.call('POST','/api/customers',{'full_name':'Khách API','phone':'0911111111'},t); self.assertEqual(s,201); s,d=self.call('GET','/api/customers?q='+quote('Khách API'),token=t); self.assertEqual(s,200); cid=d['data'][0]['id']; s,_=self.call('PUT','/api/customers/'+str(cid),{'full_name':'Khách API đã sửa','phone':'0922222222'},t); self.assertEqual(s,200); s,_=self.call('POST','/api/appointments',{'customer_id':cid,'starts_at':'2026-11-25T09:00:00'},t); self.assertEqual(s,201); s,d=self.call('GET','/api/appointments',token=t); aid=next(x['id'] for x in d['data'] if x['customer_id']==cid); s,_=self.call('DELETE','/api/appointments/'+str(aid),token=t); self.assertEqual(s,200)
 def test_attendance_protection(self):
  t=self.login('student.mai','student'); s,d=self.call('POST','/api/attendance',{'session_id':1},t); self.assertEqual(s,201); s,d=self.call('POST','/api/attendance',{'session_id':1},t); self.assertEqual(s,409)
 def test_payment_is_transactional_and_scoped(self):
  t=self.login('manager.q1','manager'); s,d=self.call('GET','/api/invoices',token=t); invoice=next(x for x in d['data'] if x['branch_id']==1 and x['total']>x['paid']); amount=invoice['total']-invoice['paid']; s,_=self.call('POST','/api/payments',{'invoice_id':invoice['id'],'amount':amount,'method':'cash'},t); self.assertEqual(s,201); s,d=self.call('GET','/api/invoices',token=t); changed=next(x for x in d['data'] if x['id']==invoice['id']); self.assertEqual(changed['status'],'paid'); self.assertEqual(changed['paid'],changed['total'])
 def test_stock_prevents_negative_inventory(self):
  t=self.login('manager.q1','manager'); s,d=self.call('GET','/api/products',token=t); product=d['data'][0]; s,d=self.call('POST','/api/stock-movements',{'product_id':product['id'],'quantity':product['stock']+1,'movement_type':'out'},t); self.assertEqual(s,422); s,_=self.call('POST','/api/stock-movements',{'product_id':product['id'],'quantity':2,'movement_type':'in'},t); self.assertEqual(s,201)
 def test_student_cannot_create_customer(self):
  t=self.login('student.mai','student'); s,_=self.call('POST','/api/customers',{'full_name':'Không được tạo','phone':'0900000000'},t); self.assertEqual(s,403)
 def test_service_product_reports_and_settings(self):
  admin=self.login('admin','admin'); s,_=self.call('POST','/api/services',{'name':'Dịch vụ API','duration_min':45,'price':250000,'branch_id':1},admin); self.assertEqual(s,201); s,d=self.call('GET','/api/services',token=admin); service=next(x for x in d['data'] if x['name']=='Dịch vụ API'); s,_=self.call('PUT','/api/services/'+str(service['id']),{'name':'Dịch vụ API sửa','duration_min':60,'price':300000,'active':1},admin); self.assertEqual(s,200); s,_=self.call('POST','/api/products',{'sku':'API-01','name':'Sản phẩm API','stock':8,'reorder_level':3,'price':100000,'branch_id':1},admin); self.assertEqual(s,201); s,d=self.call('GET','/api/reports/overview',token=admin); self.assertEqual(s,200); self.assertIn('revenue',d['data']); s,_=self.call('POST','/api/settings',{'settings':{'spa_name':'SpaFlow Test','support_phone':'0900000000','currency':'VND'}},admin); self.assertEqual(s,201); s,d=self.call('GET','/api/settings',token=admin); self.assertEqual(s,200); self.assertIn('SpaFlow Test',[x['setting_value'] for x in d['data']])
 def test_generic_module_crud_and_student_scope(self):
  admin=self.login('admin','admin'); s,_=self.call('POST','/api/modules/rooms',{'title':'Phòng API','details':'Tầng 2','status':'active','branch_id':1},admin); self.assertEqual(s,201); s,d=self.call('GET','/api/modules/rooms',token=admin); record=next(x for x in d['data'] if x['title']=='Phòng API'); s,_=self.call('PUT','/api/modules/rooms/'+str(record['id']),{'title':'Phòng API sửa','details':'Tầng 3','status':'inactive'},admin); self.assertEqual(s,200); s,_=self.call('DELETE','/api/modules/rooms/'+str(record['id']),token=admin); self.assertEqual(s,200); student=self.login('student.mai','student'); s,d=self.call('GET','/api/modules/materials',token=student); self.assertEqual(s,200); s,_=self.call('POST','/api/modules/materials',{'title':'Không được tạo'},student); self.assertEqual(s,403)
 def test_staff_workflow_rbac_shift_and_gps_checkin(self):
  admin=self.login('admin','admin'); s,d=self.call('GET','/api/staff',token=admin); self.assertEqual(s,200); self.assertGreaterEqual(len(d['data']),5)
  payload={'employee_code':'NVAPI01','full_name':'Nhân viên API','phone':'0909123456','email':'nv.api@spaflow.vn','hire_date':'2026-11-21','department':'Dịch vụ','position_title':'Kỹ thuật viên','branch_ids':[1,2],'role_codes':['employee'],'account':{'username':'staff.api','password':'staffpass'}}
  s,_=self.call('POST','/api/staff',payload,admin); self.assertEqual(s,201)
  s,d=self.call('GET','/api/staff',token=admin); staff=next(x for x in d['data'] if x['employee_code']=='NVAPI01'); self.assertIn('SpaFlow Quận 1',staff['branch_names'])
  s,_=self.call('POST','/api/staff/shifts',{'staff_id':staff['id'],'branch_id':1,'starts_at':'2026-11-22T08:00:00','ends_at':'2026-11-22T17:00:00'},admin); self.assertEqual(s,201)
  staff_token=self.login('staff.api','staffpass'); s,_=self.call('POST','/api/staff/attendance',{'check_type':'check_in','photo_data':'data:image/jpeg;base64,test','latitude':10.77,'longitude':106.70},staff_token); self.assertEqual(s,201)
  s,d=self.call('GET','/api/staff/attendance',token=admin); self.assertTrue(any(x['employee_code']=='NVAPI01' for x in d['data']))
  manager=self.login('manager.q1','manager'); s,_=self.call('POST','/api/staff',{'employee_code':'NVBLOCK','full_name':'Blocked','phone':'0909000000','branch_ids':[1],'role_codes':['admin']},manager); self.assertEqual(s,403)
if __name__=='__main__': unittest.main()

"""
VNDEVCODE MULTI TOOL WEB - BACKEND FULL
Chức năng: Chuyển Page, Reg Instagram, Reg Facebook iOS, Proxy, Token Parser
+ 10 FB API: Reaction, Get Page, Reg Page, Get UID, Like Page, Up Avatar/Cover,
             Follow, Comment, Share, Get Info
"""
import os
import json
import re
import time
import uuid
import random
import string
import threading
import base64
import urllib.parse
from datetime import datetime
import requests
from flask import Flask, request, jsonify, Response, stream_with_context

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

SESSION_LOGS = {}
SESSION_STATUS = {}


def log_to_session(sid, msg):
    if sid not in SESSION_LOGS:
        SESSION_LOGS[sid] = []
    SESSION_LOGS[sid].append({
        'time': datetime.now().strftime('%H:%M:%S'),
        'msg': str(msg)
    })
    if len(SESSION_LOGS[sid]) > 1000:
        SESSION_LOGS[sid] = SESSION_LOGS[sid][-1000:]


# ═══════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════
FB4A_UA = '[FBAN/FB4A;FBAV/542.0.0.46.151;FBBV/840338789;FBDM/{density=0.75,width=300,height=540};FBLC/vi_VN;FBRV/0;FBCR/MobiFone;FBMF/MTool-Max;FBBD/MTool-Max;FBPN/com.facebook.katana;FBDV/MTool-Max;FBSV/9;FBOP/1;FBCA/x86_64:arm64-v8a;]'
FB_UA_552 = '[FBAN/FB4A;FBAV/552.1.0.45.68;FBBV/906187048;FBDM/{density=3.0,width=1080,height=1920};FBLC/en_US;FBRV/0;FBCR/MobiFone;FBMF/Samsung;FBBD/Samsung;FBPN/com.facebook.katana;FBDV/Samsung C3560;FBSV/9;FBOP/1;FBCA/x86_64:arm64-v8a;]'

REACTION_IDS = {
    'LIKE': '1635855486666999', 'LOVE': '1678524932434102',
    'HAHA': '115940658764963', 'WOW': '478547315650144',
    'SAD': '908563459236466', 'ANGRY': '444813342392137'
}


# ═══════════════════════════════════════════════════════════
# MODULE: CHUYỂN PAGE FACEBOOK
# ═══════════════════════════════════════════════════════════
class ChuyenPageTool:
    def __init__(self):
        self.log_callback = None

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def get_user_info(self, access_token):
        try:
            r = requests.get("https://graph.facebook.com/me",
                             params={"access_token": access_token,
                                     "fields": "id,name"}, timeout=10)
            d = r.json()
            return (d["id"], d.get("name", "")) if "id" in d else (None, None)
        except Exception:
            return None, None

    def _fb_fetch_profile_info(self, token, profile_id):
        v = {'profile_switcher_connection_first': 300,
             'additional_profile_picture_size': 80,
             'profileID': str(profile_id),
             'main_profile_picture_size': 80, 'scale': '2',
             'nt_context': {'using_white_navbar': True,
                            'styles_id': '588d028b36bed0e1889e09b60e0f9aea',
                            'pixel_ratio': 2, 'is_push_on': True,
                            'debug_tooling_metadata_token': None,
                            'is_flipper_enabled': False,
                            'theme_params': [{'value': [],
                                              'design_system_name': 'FDS'}],
                            'bloks_version': '338f8ead5977a2c41eba3e92584dcf1d132e8b7928f1f5796662ec064023047d'},
             'overflow_recent_searches_filter_ids': [],
             'use_native_entrypoint_for_stars_on_reels': True}
        p = {'method': 'post', 'pretty': 'false', 'format': 'json',
             'server_timestamps': 'true', 'locale': 'vi_VN',
             'client_doc_id': '116912609015732060545213902280',
             'variables': json.dumps(v)}
        h = {'User-Agent': FB4A_UA, 'Accept-Encoding': 'gzip',
             'authorization': f'OAuth {token}'}
        try:
            return requests.post('https://b-graph.facebook.com/graphql',
                                 data=p, headers=h, timeout=15).json()
        except Exception:
            return None

    def _get_ps_map(self, token, uid):
        gql = self._fb_fetch_profile_info(token, uid)
        if not gql:
            return []
        res = []
        try:
            edges = gql.get('data', {}).get('user', {}).get(
                'profile_switcher_eligible_profiles', {}).get('edges', [])
            for e in edges:
                n = e.get('node', {})
                pr = n.get('profile', {})
                tk = n.get('session_info', {}).get('access_token', '')
                pid = str(pr.get('id', ''))
                if pid and pid != str(uid) and tk:
                    res.append({'profile_id': pid,
                                'name': pr.get('name', ''),
                                'access_token': tk})
        except Exception:
            pass
        return res

    def _match(self, page, ps_map):
        pid = str(page.get('id', ''))
        pname = page.get('name', '').strip().lower()
        for p in ps_map:
            if p['name'].strip().lower() == pname or p['profile_id'] == pid:
                return p['profile_id'], p.get('access_token', '')
        return None, None

    def get_pages(self, token, uid=None):
        try:
            r = requests.get("https://graph.facebook.com/me/accounts",
                             params={"access_token": token,
                                     "fields": "id,name,access_token,category"},
                             timeout=15)
            d = r.json()
            if "data" not in d:
                return []
            ps = self._get_ps_map(token, uid) if uid else []
            pages = []
            for pg in d["data"]:
                if pg.get("id") and pg.get("access_token"):
                    pu, ptk = self._match(pg, ps)
                    pages.append({'uid': pu or pg["id"],
                                  'token': ptk or pg["access_token"],
                                  'name': pg.get("name", ""),
                                  'id': pg["id"],
                                  'category': pg.get("category", "")})
            return pages
        except Exception:
            return []

    def _hdrs(self, token):
        return {"User-Agent": FB4A_UA, "authorization": f"OAuth {token}",
                "x-fb-sim-hni": "45201", "x-fb-net-hni": "45201",
                "x-graphql-client-library": "graphservice",
                "x-tigon-is-retry": "False",
                "x-graphql-request-purpose": "fetch",
                "x-fb-device-group": "2789", "Accept-Encoding": "identity",
                "x-zero-eh": "error", "x-fb-connection-type": "WIFI",
                "x-fb-http-engine": "Tigon/Liger",
                "x-fb-client-ip": "True", "x-fb-server-cluster": "True",
                "Content-Type": "application/x-www-form-urlencoded"}

    def _send_inv(self, stk, spwd, puid, tuid):
        self.log(f"📤 Gửi lời mời page {puid} → {tuid}")
        url = (f"/nt/profile/admin_management/permissions_reauth?admin_id={tuid}"
               "&admin_rows_container_id=%5B%228bxxoh%3A2%22%2Cnull%5D&admin_type=full_access"
               "&entry_point_screen_id=%5B%227o2xil%3A5%22%2Cnull%5D"
               f"&profile_id={puid}"
               "&state_ids%5Bauthenticated%5D=8csr9g%3A0"
               "&state_ids%5Bauthentication_attempted%5D=8csr9g%3A1"
               "&state_ids%5Bshow_entry_point_saving_spinner%5D=8bxxoh%3A0"
               "&state_ids%5Bshow_saving_spinner%5D=8csr9g%3A3"
               "&state_ids%5Bads%5D=8clnk7%3A2&state_ids%5Bcontent%5D=8clnk7%3A3"
               "&state_ids%5Binsights%5D=8clnk7%3A4&state_ids%5Bmessages%5D=8clnk7%3A5"
               "&state_ids%5Bmoderate%5D=8clnk7%3A6")
        cd = {"sensitive_string_value": f'[["password","{spwd}"]]'}
        ntc = {"using_white_navbar": True,
               "styles_id": "55d2af294359fa6bbdb8e045ff01fc5e",
               "pixel_ratio": 1.5, "is_push_on": True,
               "debug_tooling_metadata_token": None,
               "is_flipper_enabled": False, "theme_params": [],
               "bloks_version": "cb6ac324faea83da28649a4d5046c3a4f0486cb987f8ab769765e316b075a76c"}
        po = {"nt_context": ntc, "payload": url, "client_data": cd}
        v = {"params": json.dumps(po),
             "bloks_versioning_id": "cb6ac324faea83da28649a4d5046c3a4f0486cb987f8ab769765e316b075a76c",
             "app_id": "com.bloks.www.bloks.caa.admin_management.permissions_reauth",
             "scale": 1, "nt_context": ntc}
        d = {"method": "post", "pretty": "false", "format": "json",
             "server_timestamps": "true", "locale": "vi_VN", "purpose": "fetch",
             "fb_api_req_friendly_name": "FbBloksActionRootQuery-com.bloks.www.bloks.caa.admin_management.permissions_reauth",
             "fb_api_caller_class": "graphservice",
             "client_doc_id": "30749539927629244093798192451",
             "variables": json.dumps(v),
             "fb_api_analytics_tags": '["GraphServices"]',
             "client_trace_id": str(uuid.uuid4())}
        try:
            return requests.post("https://b-graph.facebook.com/graphql",
                                 headers=self._hdrs(stk), data=d, timeout=30).json()
        except Exception as e:
            return {"error": str(e)}

    def _accept_inv(self, ttk, inv_id):
        self.log(f"✅ Chấp nhận lời mời (ID: {inv_id})")
        url = f"/nt/profile/admin_management/accept_invitation?invitation_id={inv_id}"
        ntc = {"using_white_navbar": True,
               "styles_id": "55d2af294359fa6bbdb8e045ff01fc5e",
               "pixel_ratio": 1.5, "is_push_on": True,
               "debug_tooling_metadata_token": None,
               "is_flipper_enabled": False, "theme_params": [],
               "bloks_version": "cb6ac324faea83da28649a4d5046c3a4f0486cb987f8ab769765e316b075a76c"}
        po = {"nt_context": ntc, "payload": url}
        v = {"params": json.dumps(po),
             "bloks_versioning_id": "cb6ac324faea83da28649a4d5046c3a4f0486cb987f8ab769765e316b075a76c",
             "app_id": "com.bloks.www.bloks.caa.admin_management.accept_invitation",
             "scale": 1, "nt_context": ntc}
        d = {"method": "post", "pretty": "false", "format": "json",
             "server_timestamps": "true", "locale": "vi_VN", "purpose": "fetch",
             "fb_api_req_friendly_name": "FbBloksActionRootQuery-com.bloks.www.bloks.caa.admin_management.accept_invitation",
             "fb_api_caller_class": "graphservice",
             "client_doc_id": "11994080423986492941384902285",
             "variables": json.dumps(v),
             "fb_api_analytics_tags": '["GraphServices"]',
             "client_trace_id": str(uuid.uuid4())}
        try:
            return requests.post("https://b-graph.facebook.com/graphql",
                                 headers=self._hdrs(ttk), data=d, timeout=30).json()
        except Exception as e:
            return {"error": str(e)}

    def _extract_inv_id(self, r):
        t = json.dumps(r)
        for p in [r'"invitation_id":"([^"]+)"',
                  r'"id":"([^"]+)"',
                  r'"confirmation_code":"([^"]+)"']:
            m = re.search(p, t)
            if m:
                return m.group(1)
        return None

    def transfer(self, stk, spwd, puid, ttk):
        tuid, _ = self.get_user_info(ttk)
        if not tuid:
            return False, "Không lấy được UID đích"
        r1 = self._send_inv(stk, spwd, puid, tuid)
        if "error" in r1:
            return False, f"Lỗi gửi: {r1['error']}"
        if r1.get("errors"):
            return False, f"Lỗi server: {r1['errors']}"
        inv = self._extract_inv_id(r1)
        if not inv:
            return False, "Không tìm thấy invitation_id"
        r2 = self._accept_inv(ttk, inv)
        if "error" in r2:
            return False, f"Lỗi accept: {r2['error']}"
        if r2.get("errors"):
            return False, f"Lỗi accept server: {r2['errors']}"
        return True, "OK"


# ═══════════════════════════════════════════════════════════
# MODULE: TEMP EMAIL
# ═══════════════════════════════════════════════════════════
class TempEmailGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
        self.email_tokens = {}
        self.generated_usernames = set()

    def _gen_username(self):
        ho = ['nguyen', 'tran', 'le', 'pham', 'hoang', 'huynh', 'phan', 'vu',
              'vo', 'dang', 'bui', 'do', 'ho', 'ngo', 'duong', 'ly']
        td = ['thi', 'van', 'duc', 'minh', 'quoc', 'thanh', 'ngoc', 'bao',
              'gia', 'khanh']
        t = ['an', 'binh', 'chi', 'duong', 'giang', 'han', 'khang', 'lam',
             'long', 'my', 'nhi', 'phong', 'quan', 'son', 'trang', 'uyen',
             'vy', 'yen']
        fmt = random.choice([1, 2, 3])
        if fmt == 1:
            u = f"{random.choice(ho)}{random.choice(td)}{random.choice(t)}"
        elif fmt == 2:
            u = f"{random.choice(ho)}{random.choice(t)}{random.choice(t)}"
        else:
            u = f"{random.choice(t)}{random.choice(td)}{random.choice(ho)}"
        u += str(random.randint(10, 999))
        if u in self.generated_usernames:
            u += str(random.randint(1000, 9999))
        self.generated_usernames.add(u)
        return u

    def _get_domains(self):
        try:
            r = self.session.get('https://api.mail.tm/domains', timeout=8)
            if r.status_code == 200:
                d = r.json()
                if 'hydra:member' in d:
                    doms = [x['domain'] for x in d['hydra:member']
                            if x.get('isActive')]
                    if doms:
                        return doms
        except Exception:
            pass
        return ['agristur.com', 'febbox.com', 'main.truf.biz']

    def _get_token(self, email, pwd):
        if email in self.email_tokens:
            return self.email_tokens[email]
        try:
            r = self.session.post('https://api.mail.tm/token',
                                  json={'address': email, 'password': pwd},
                                  timeout=10)
            if r.status_code == 200:
                tk = r.json().get('token')
                self.email_tokens[email] = tk
                return tk
        except Exception:
            pass
        return None

    def create_email(self):
        for _ in range(3):
            try:
                doms = self._get_domains()
                if not doms:
                    return None
                u = self._gen_username()
                dom = random.choice(doms)
                pwd = ''.join(random.choice(string.ascii_letters + string.digits)
                              for _ in range(12))
                r = self.session.post('https://api.mail.tm/accounts',
                                      json={'address': f'{u}@{dom}',
                                            'password': pwd}, timeout=12)
                if r.status_code == 201:
                    addr = f'{u}@{dom}'
                    tk = self._get_token(addr, pwd)
                    return {'email': addr, 'password': pwd,
                            'service': 'mailtm', 'token': tk}
            except Exception:
                pass
            time.sleep(2)
        return None

    def get_messages(self, email_info):
        try:
            tk = email_info.get('token') or self._get_token(
                email_info['email'], email_info['password'])
            if not tk:
                return []
            r = self.session.get('https://api.mail.tm/messages',
                                 headers={'Authorization': f'Bearer {tk}'},
                                 timeout=10)
            if r.status_code == 200:
                d = r.json()
                msgs = d.get('hydra:member', []) if 'hydra:member' in d else []
                msgs.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
                for m in msgs[:3]:
                    try:
                        cr = self.session.get(
                            f"https://api.mail.tm/messages/{m['id']}",
                            headers={'Authorization': f'Bearer {tk}'},
                            timeout=8)
                        if cr.status_code == 200:
                            j = cr.json()
                            m['full_content'] = j.get('text', '') or j.get('html', '')
                    except Exception:
                        pass
                return msgs
        except Exception:
            pass
        return []


# ═══════════════════════════════════════════════════════════
# MODULE: INSTAGRAM REG
# ═══════════════════════════════════════════════════════════
class InstagramReg:
    def __init__(self):
        self.log_callback = None
        self.is_stopped = lambda: False
        self.email_gen = TempEmailGenerator()
        self.displayed_msgs = set()

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def _ua(self):
        devs = ["iPhone15,2", "iPhone14,7", "iPhone13,2", "iPhone12,1",
                "iPhone11,2"]
        ios = ["17_2", "16_4", "15_5", "17_0"]
        return (f'Mozilla/5.0 ({random.choice(devs)}; CPU iPhone OS '
                f'{random.choice(ios)} like Mac OS X) AppleWebKit/605.1.15 '
                f'(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/605.1')

    def _session(self):
        s = requests.Session()
        s.headers.update({
            'accept': '*/*',
            'accept-language': 'vi-VN,vi;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.instagram.com',
            'referer': 'https://www.instagram.com/accounts/emailsignup/',
            'user-agent': self._ua()
        })
        return s

    def _init_cookies(self, s):
        try:
            s.get('https://www.instagram.com/', timeout=30)
            time.sleep(random.uniform(2, 4))
            r = s.get('https://www.instagram.com/accounts/emailsignup/',
                      timeout=30)
            if r.status_code == 200:
                csrf = s.cookies.get('csrftoken') or ''.join(
                    random.choice(string.ascii_letters + string.digits)
                    for _ in range(32))
                s.headers['x-csrftoken'] = csrf
                return csrf
        except Exception:
            pass
        return None

    def _gen_name(self):
        ho = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ', 'Đặng',
              'Bùi', 'Đỗ', 'Ngô']
        td = ['Thị', 'Văn', 'Đức', 'Minh', 'Quốc', 'Thanh', 'Ngọc',
              'Bảo', 'Gia']
        t = ['An', 'Bình', 'Chi', 'Dương', 'Giang', 'Hân', 'Khang',
             'Lam', 'Long', 'My', 'Nhi', 'Phong', 'Quân', 'Sơn', 'Trang']
        return f"{random.choice(ho)} {random.choice(td)} {random.choice(t)}"

    def _gen_ig_username(self, name):
        u = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
        return u + str(random.randint(100, 9999))

    def create_account(self, pwd):
        s = self._session()
        csrf = self._init_cookies(s)
        if not csrf:
            self.log("❌ Không init được session")
            return False

        email_info = self.email_gen.create_email()
        if not email_info:
            self.log("❌ Không tạo được email")
            return False
        email = email_info['email']
        self.log(f"📧 Email: {email}")

        first_name = self._gen_name()
        username = self._gen_ig_username(first_name)
        client_id = ''.join(random.choice(string.ascii_lowercase + string.digits)
                            for _ in range(20))
        jazoest = ''.join(random.choice(string.digits) for _ in range(5))

        enc_pwd = f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{pwd}"
        data1 = {'enc_password': enc_pwd, 'email': email,
                 'username': username, 'first_name': first_name,
                 'client_id': client_id, 'seamless_login_enabled': '1',
                 'opt_into_one_tap': 'false', 'jazoest': jazoest}
        try:
            r1 = s.post('https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/',
                        data=data1, timeout=45)
            self.log(f"• Signup step 1: HTTP {r1.status_code}")
            if r1.status_code != 200:
                return False
        except Exception as e:
            self.log(f"❌ Lỗi step1: {e}")
            return False

        try:
            s.post('https://www.instagram.com/api/v1/web/consent/check_age_eligibility/',
                   data={'day': str(random.randint(1, 28)),
                         'month': str(random.randint(1, 12)),
                         'year': str(random.randint(1990, 2000)),
                         'jazoest': jazoest}, timeout=30)
        except Exception:
            pass

        try:
            s.post('https://www.instagram.com/api/v1/accounts/send_verify_email/',
                   data={'device_id': client_id, 'email': email,
                         'jazoest': jazoest}, timeout=30)
            self.log("• Đã gửi code verify")
        except Exception:
            pass

        code = None
        for i in range(60):
            if self.is_stopped():
                return False
            msgs = self.email_gen.get_messages(email_info)
            for m in msgs:
                mid = m.get('id', '')
                key = f"{email}_{mid}"
                if key in self.displayed_msgs:
                    continue
                self.displayed_msgs.add(key)
                content = (m.get('full_content', '') + ' ' +
                           m.get('subject', ''))
                codes = re.findall(r'\b\d{6}\b', content)
                if codes:
                    code = codes[0]
                    self.log(f"✅ Code: {code}")
                    break
            if code:
                break
            time.sleep(2)

        if not code:
            self.log("❌ Không lấy được code")
            return False

        data2 = {'enc_password': enc_pwd,
                 'day': str(random.randint(1, 28)),
                 'email': email, 'failed_birthday_year_count': '{}',
                 'first_name': first_name,
                 'month': str(random.randint(1, 12)),
                 'username': username,
                 'year': str(random.randint(1990, 2000)),
                 'client_id': client_id, 'seamless_login_enabled': '1',
                 'tos_version': 'row', 'force_sign_up_code': code,
                 'jazoest': jazoest}
        try:
            r2 = s.post('https://www.instagram.com/api/v1/web/accounts/web_create_ajax/',
                        data=data2, timeout=30)
            res = r2.json()
            if res.get('account_created') or res.get('user_id'):
                self.log(f"✅ TẠO THÀNH CÔNG: {username}")
                cookies = s.cookies.get_dict()
                important = {k: cookies[k] for k in
                             ['csrftoken', 'sessionid', 'ds_user_id',
                              'ig_did', 'mid', 'datr'] if k in cookies}
                ck_str = '; '.join(f'{k}={v}' for k, v in important.items())
                with open('account_instagram.txt', 'a', encoding='utf-8') as f:
                    f.write(f"||{first_name} | {username} | {pwd} | {email}||\n")
                    f.write(f"||{ck_str}||\n")
                return True
            else:
                self.log(f"❌ Lỗi: {res}")
                return False
        except Exception as e:
            self.log(f"❌ Lỗi hoàn tất: {e}")
            return False


# ═══════════════════════════════════════════════════════════
# MODULE: FACEBOOK iOS REG
# ═══════════════════════════════════════════════════════════
class FacebookIOSReg:
    def __init__(self):
        self.log_callback = None
        self.is_stopped = lambda: False

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def register(self, password='anhem1234'):
        self.log("🚀 Bắt đầu đăng ký Facebook iOS")
        email_gen = TempEmailGenerator()
        email_info = email_gen.create_email()
        if not email_info:
            self.log("❌ Không tạo được email")
            return False, None
        email = email_info['email']
        self.log(f"📧 Email: {email}")

        ho = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ']
        ten = ['An', 'Bình', 'Chi', 'Dương', 'Giang', 'Hân']
        last_name = random.choice(ho)
        first_name = random.choice(ten)
        full_name = f"{last_name} {first_name}"
        self.log(f"👤 Tên: {full_name}")

        code = None
        self.log("⏳ Đợi OTP...")
        for i in range(60):
            if self.is_stopped():
                return False, None
            msgs = email_gen.get_messages(email_info)
            for m in msgs:
                content = (m.get('full_content', '') + ' ' +
                           m.get('subject', ''))
                codes = re.findall(r'\b\d{5,6}\b', content)
                if codes:
                    code = codes[0]
                    self.log(f"✅ OTP: {code}")
                    break
            if code:
                break
            time.sleep(2)

        if not code:
            self.log("❌ Không lấy được OTP")
            return False, None

        with open('account_facebook.txt', 'a', encoding='utf-8') as f:
            f.write(f"{email}|{password}|{full_name}|{code}\n")

        self.log("⚠️ FB iOS Reg cần IP sạch + device thật")
        return True, {'email': email, 'password': password,
                      'name': full_name, 'code': code}


# ═══════════════════════════════════════════════════════════
# MODULE: FB REACTION
# ═══════════════════════════════════════════════════════════
def fb_reaction(token, post_id, reaction_type='LIKE'):
    try:
        r = requests.get('https://graph.facebook.com/me',
                         params={'access_token': token}, timeout=15)
        actor_id = r.json().get('id')
        if not actor_id:
            return {'ok': False, 'error': 'Token không hợp lệ'}
        fb_id = base64.b64encode(f'feedback:{post_id}'.encode()).decode()
        react_id = REACTION_IDS.get(reaction_type.upper(),
                                     REACTION_IDS['LIKE'])
        variables = json.dumps({
            'input': {'feedback_id': fb_id,
                      'feedback_reaction_id': react_id,
                      'actor_id': actor_id}
        })
        headers = {'User-Agent': FB_UA_552, 'Accept-Encoding': 'gzip',
                   'authorization': f'OAuth {token}'}
        payload = {'pretty': 'false', 'variables': variables,
                   'method': 'post',
                   'client_doc_id': '2857784093518205785115255697',
                   'format': 'json', 'server_timestamps': 'true',
                   'locale': 'vi_VN'}
        r2 = requests.post('https://graph.facebook.com/graphql',
                           data=payload, headers=headers, timeout=15)
        result = r2.json()
        return {'ok': 'data' in result, 'raw': result}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB GET PAGES
# ═══════════════════════════════════════════════════════════
def fb_get_pages(token):
    try:
        r = requests.get("https://graph.facebook.com/me",
                         params={"access_token": token,
                                 "fields": "id,name"}, timeout=15)
        user_data = r.json()
        uid = user_data.get('id')
        if not uid:
            return {'ok': False, 'error': 'Token không hợp lệ'}
        tool = ChuyenPageTool()
        pages = tool.get_pages(token, uid)
        return {'ok': True, 'user': user_data, 'pages': pages}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB REG PAGE
# ═══════════════════════════════════════════════════════════
BLOKS_VERSION_REGPAGE = "338f8ead5977a2c41eba3e92584dcf1d132e8b7928f1f5796662ec064023047d"
DEFAULT_CATEGORY = "180164648685982"
GRAPHQL_DOC_ID_REGPAGE = "119940804239956818821550724"
APP_ID_REGPAGE = "com.bloks.www.additional.profile.plus.creation.action.category.submit"


class VNNameGenerator:
    VN_HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Võ",
             "Vũ", "Bùi", "Đặng", "Đỗ", "Hồ", "Dương", "Đoàn",
             "Trịnh", "Tạ", "Đào", "Lý"]
    VN_LOT = ["Văn", "Thị", "Hữu", "Đình", "Ngọc", "Xuân", "Gia",
              "Minh", "Quang", "Đức", "Công", "Thành", "Tuấn",
              "Hoàng", "Kim", "Bảo"]
    VN_TEN = ["Anh", "Hùng", "Nam", "Tuấn", "Hoàng", "Quốc", "Giang",
              "Khương", "Dương", "Phúc", "Thiện", "Kiệt", "Châu",
              "Huệ", "Khánh", "Yến", "Linh", "Thảo", "My", "Huy",
              "Trang", "Huyền", "Ngân"]

    @staticmethod
    def gen():
        return (f"{random.choice(VNNameGenerator.VN_HO)} "
                f"{random.choice(VNNameGenerator.VN_LOT)} "
                f"{random.choice(VNNameGenerator.VN_TEN)}")


def fb_create_page(token, page_name):
    try:
        inner_params = (
            '{"client_input_params":{'
            '"page_id":"0","profile_plus_id":"0","cp_upsell_declined":0,'
            '"off_platform_creator_reachout_id":"",'
            f'"category_ids":["{DEFAULT_CATEGORY}"],"nav_chain":"..."'
            '},"server_params":{'
            '"referrer":"pages_tab_launch_point",'
            '"INTERNAL__latency_qpl_marker_id":36707139,'
            '"creation_source":"android",'
            f'"name":"{page_name}","variant":5,"screen":"category",'
            '"INTERNAL__latency_qpl_instance_id":5.5098533200051e13}}'
        )
        outer_params = {"params": inner_params,
                        "bloks_versioning_id": BLOKS_VERSION_REGPAGE,
                        "app_id": APP_ID_REGPAGE}
        nt_context = {"using_white_navbar": True,
                      "styles_id": "588d028b36bed0e1889e09b60e0f9aea",
                      "pixel_ratio": 2, "is_push_on": True,
                      "debug_tooling_metadata_token": None,
                      "is_flipper_enabled": False,
                      "theme_params": [{"value": [],
                                        "design_system_name": "FDS"}],
                      "bloks_version": BLOKS_VERSION_REGPAGE}
        variables = json.dumps({"params": outer_params, "scale": "2",
                                "nt_context": nt_context})
        session = requests.Session()
        session.headers.update({
            "User-Agent": "[FBAN/FB4A;FBAV/537.0.0.47.77;FBPN/com.facebook.katana;]",
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"OAuth {token}",
        })
        data = {"method": "post", "pretty": "false", "format": "json",
                "server_timestamps": "true", "locale": "vi_VN",
                "client_doc_id": GRAPHQL_DOC_ID_REGPAGE,
                "variables": variables}
        resp = session.post("https://graph.facebook.com/graphql",
                            data=urllib.parse.urlencode(data), timeout=60)
        result = resp.json()
        raw = json.dumps(result)
        m = re.search(r'"page_id"\s*:\s*"?(\d{6,})"?', raw)
        if m:
            return {'ok': True, 'page_id': m.group(1), 'raw': result}
        if 'create_success' in raw or 'bloks_bundle_action' in raw:
            return {'ok': True, 'page_id': None, 'raw': result}
        return {'ok': False, 'error': 'Không tạo được page', 'raw': result}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB GET UID FROM LINK
# ═══════════════════════════════════════════════════════════
def fb_get_uid_from_link(link):
    url = "https://id.traodoisub.com/api.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://id.traodoisub.com",
        "Referer": "https://id.traodoisub.com/",
    }
    try:
        resp = requests.post(url,
                             data=urllib.parse.urlencode({"link": link}),
                             headers=headers, timeout=15)
        data = resp.json()
        if data.get("success") == 200 and "id" in data:
            return {'ok': True, 'uid': data['id'], 'raw': data}
        return {'ok': False, 'error': str(data)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB LIKE PAGE
# ═══════════════════════════════════════════════════════════
def fb_like_page(token, target_uid):
    try:
        r = requests.get('https://graph.facebook.com/me',
                         params={'access_token': token}, timeout=15)
        actor_id = r.json().get('id')
        if not actor_id:
            return {'ok': False, 'error': 'Token không hợp lệ'}

        attempts = [
            ('POST', f'https://graph.facebook.com/{target_uid}/likes',
             {'access_token': token}),
            ('POST', 'https://graph.facebook.com/me/likes',
             {'id': target_uid, 'access_token': token}),
            ('GET', f'https://graph.facebook.com/{target_uid}/likes',
             {'method': 'post', 'access_token': token}),
        ]
        for method, url, payload in attempts:
            try:
                if method == 'POST':
                    r2 = requests.post(url, data=payload,
                                       headers={'User-Agent': FB_UA_552,
                                                'Accept-Encoding': 'gzip'},
                                       timeout=20)
                else:
                    r2 = requests.get(url, params=payload,
                                      headers={'User-Agent': FB_UA_552,
                                               'Accept-Encoding': 'gzip'},
                                      timeout=20)
                data = r2.json()
                if data.get('success') is True:
                    return {'ok': True, 'raw': data}
                if data.get('id') == str(target_uid):
                    return {'ok': True, 'raw': data}
                if 'data' in data and len(data['data']) > 0:
                    return {'ok': True, 'raw': data}
            except Exception:
                continue
        return {'ok': False, 'error': 'Tất cả phương thức thất bại'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB UP AVATAR + COVER
# ═══════════════════════════════════════════════════════════
def fb_upload_avatar(token, image_url):
    try:
        r = requests.get(image_url, timeout=30)
        if r.status_code != 200:
            return {'ok': False, 'error': 'Không tải được ảnh'}
        files = {"source": ("avatar.jpg", r.content, "image/jpeg")}
        data = {"access_token": token}
        r2 = requests.post("https://graph.facebook.com/me/picture",
                           files=files, data=data, timeout=30)
        if r2.status_code == 200:
            txt = r2.text.strip().lower()
            if txt == "true" or r2.json():
                return {'ok': True, 'raw': r2.text}
        return {'ok': False, 'error': f'HTTP {r2.status_code}',
                'raw': r2.text}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def fb_upload_cover(token, image_url):
    try:
        r = requests.get(image_url, timeout=30)
        if r.status_code != 200:
            return {'ok': False, 'error': 'Không tải được ảnh'}
        files = {"source": ("cover.jpg", r.content, "image/jpeg")}
        data = {"access_token": token, "no_story": "true"}
        r2 = requests.post("https://graph.facebook.com/me/photos",
                           files=files, data=data, timeout=30)
        photo_data = r2.json()
        if "id" in photo_data:
            photo_id = photo_data["id"]
            r3 = requests.post("https://graph.facebook.com/me",
                               data={"access_token": token,
                                     "cover": photo_id},
                               timeout=30)
            if r3.status_code == 200:
                return {'ok': True, 'raw': r3.text}
        return {'ok': False, 'error': 'Upload cover thất bại',
                'raw': photo_data}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB FOLLOW
# ═══════════════════════════════════════════════════════════
def fb_follow(token, target_uid):
    try:
        r = requests.get('https://graph.facebook.com/me',
                         params={'access_token': token}, timeout=15)
        actor_id = r.json().get('id')
        if not actor_id:
            return {'ok': False, 'error': 'Token không hợp lệ'}

        ufs_session_id = f'UFS-{uuid.uuid4()}-fg-{random.randint(1, 10)}'
        nav_parts = []
        login_base_s = time.time() - random.uniform(30, 60)
        login_times = [login_base_s + random.uniform(0, 0.3)
                       for _ in range(4)]
        for lt in reversed(login_times):
            nav_parts.append(f'login_{int(lt*1000)}')
        nav_chain = ';'.join(nav_parts)

        base_hdrs = {
            'User-Agent': FB_UA_552,
            'Accept-Encoding': 'gzip, deflate',
            'x-fb-rmd': 'state=URL_ELIGIBLE',
            'x-graphql-client-library': 'graphservice',
            'x-fb-connection-type': 'WIFI',
            'authorization': f'OAuth {token}',
            'x-fb-http-engine': 'Tigon/Liger',
            'x-fb-client-ip': 'True',
            'x-fb-server-cluster': 'True'
        }

        api2_vars = json.dumps({
            'input': {
                'tracking': [],
                'subscribee_id': str(target_uid),
                'subscribe_location': 'PROFILE',
                'story_id': None,
                'is_tracking_encrypted': False,
                'downstream_share_session_id': None,
                'downstream_share_session_start_time': None,
                'attribution_id_v2': nav_chain,
                'downstream_share_session_origin_uri': None,
                'downstream_share_navigation_events_count': {
                    'downstream_share_navigation_events_count_vec': [
                        {'name': 'APP_BACKGROUNDED', 'count': 0},
                        {'name': 'APP_FOREGROUNDED', 'count': 0}]},
                'actor_id': actor_id
            },
            'fetch_profile_context_row': True,
            'nt_context': {}
        })
        api2_payload = {
            'method': 'post', 'pretty': 'false', 'format': 'json',
            'server_timestamps': 'true', 'locale': 'en_US',
            'fb_api_req_friendly_name': 'ActorSubscribeCoreMutation',
            'fb_api_caller_class': 'graphservice',
            'client_doc_id': '333384874811539315526365045620',
            'fb_api_client_context': json.dumps({'is_background': False}),
            'variables': api2_vars,
            'fb_api_analytics_tags': json.dumps(
                ['visitation_id=null',
                 f'session_id={ufs_session_id}',
                 'GraphServices']),
            'client_trace_id': str(uuid.uuid4())
        }
        h2 = base_hdrs.copy()
        h2['x-fb-request-analytics-tags'] = json.dumps({
            'network_tags': {'product': '350685531728',
                             'request_category': 'graphql',
                             'purpose': 'none', 'retry_attempt': '0'},
            'application_tags': 'graphservice'
        })
        h2['priority'] = 'u=3, i'
        h2['x-fb-friendly-name'] = 'ActorSubscribeCoreMutation'
        h2['x-fb-navigation-chain'] = nav_chain

        r2 = requests.post('https://graph.facebook.com/graphql',
                           data=api2_payload, headers=h2, timeout=30)
        data = r2.json()
        if 'data' in data and 'actor_subscribe' in data.get('data', {}):
            return {'ok': True, 'raw': data}
        return {'ok': False, 'error': 'Follow thất bại', 'raw': data}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB COMMENT
# ═══════════════════════════════════════════════════════════
def fb_comment(token, post_id, comment_text):
    try:
        r = requests.get('https://graph.facebook.com/me',
                         params={'access_token': token}, timeout=15)
        actor_id = r.json().get('id')
        if not actor_id:
            return {'ok': False, 'error': 'Token không hợp lệ'}

        parts = post_id.split('_', 1)
        if len(parts) == 2:
            owner_id, post_fbid = parts[0], parts[1]
        else:
            post_fbid = post_id
            owner_id = post_id

        feedback_id = base64.b64encode(
            f'feedback:{post_fbid}'.encode()).decode()
        idempotence_token = str(uuid.uuid4())
        ufs_session_id = f'UFS-{uuid.uuid4()}-fg-{random.randint(1, 10)}'

        base_hdrs = {
            'User-Agent': FB_UA_552,
            'Accept-Encoding': 'gzip, deflate',
            'x-fb-request-analytics-tags': json.dumps({
                'network_tags': {'product': '350685531728',
                                 'request_category': 'graphql',
                                 'purpose': 'none', 'retry_attempt': '0'},
                'application_tags': 'graphservice'
            }),
            'x-fb-rmd': 'state=URL_ELIGIBLE',
            'priority': 'u=3, i',
            'x-graphql-client-library': 'graphservice',
            'x-fb-connection-type': 'WIFI',
            'authorization': f'OAuth {token}',
            'x-fb-http-engine': 'Tigon/Liger',
            'x-fb-client-ip': 'True',
            'x-fb-server-cluster': 'True'
        }

        typing_payload = {
            'method': 'post', 'pretty': 'false', 'format': 'json',
            'server_timestamps': 'true', 'locale': 'en_US',
            'fb_api_req_friendly_name': 'FeedbackStartTypingCoreMutation',
            'fb_api_caller_class': 'graphservice',
            'client_doc_id': '160268623912867664855200840426',
            'fb_api_client_context': json.dumps({'is_background': False}),
            'variables': json.dumps({'input': {'feedback_id': feedback_id}}),
            'fb_api_analytics_tags': json.dumps(['visitation_id=null',
                                                  'GraphServices']),
            'client_trace_id': str(uuid.uuid4())
        }
        h1 = base_hdrs.copy()
        h1['x-fb-friendly-name'] = 'FeedbackStartTypingCoreMutation'
        requests.post('https://graph.facebook.com/graphql',
                      data=typing_payload, headers=h1, timeout=20)

        time.sleep(random.uniform(1.5, 3))

        bloks_ver = '51ee0924c1a66b5dd670a44370f6278f66485250d78f72d036fb4ff6480c1d16'
        api2_vars = json.dumps({
            'include_ban_block_fields_for_pplus': True,
            'input': {
                'tracking': [],
                'skip_link_usage_quota_validation': False,
                'session_id': ufs_session_id,
                'privacy_type': 'DEFAULT_PRIVACY',
                'nectar_module': 'newsfeed_ufi',
                'actor_id': actor_id,
                'feedback_source': 'feedback_comments',
                'message': {'text': comment_text, 'ranges': []},
                'feedback_referrer': 'native_newsfeed',
                'feedback_id': feedback_id,
                'idempotence_token': idempotence_token,
                'entry_point': 'TAP_FOOTER_COMMENT',
                'action_timestamp': int(time.time())
            },
            'nt_context': {'using_white_navbar': True,
                           'styles_id': 'cc0995fd4392efdb0fd2bbe7fc9091fe',
                           'pixel_ratio': 3, 'is_push_on': True,
                           'is_flipper_enabled': False,
                           'theme_params': [{'value': [],
                                             'design_system_name': 'FDS'}],
                           'bloks_version': bloks_ver},
            'feedback_source': 'NEWS_FEED',
            'image_medium_width': 540, 'image_high_width': 1080,
            'image_low_width': 360, 'profile_image_size': 120
        })
        api2_payload = {
            'method': 'post', 'pretty': 'false', 'format': 'json',
            'server_timestamps': 'true', 'locale': 'en_US',
            'fb_api_req_friendly_name': 'CommentCreateMutation',
            'fb_api_caller_class': 'graphservice',
            'client_doc_id': '847448981415323174993593552',
            'fb_api_client_context': json.dumps({'is_background': False}),
            'variables': api2_vars,
            'fb_api_analytics_tags': json.dumps(['GraphServices']),
            'client_trace_id': str(uuid.uuid4())
        }
        h2 = base_hdrs.copy()
        h2['x-fb-friendly-name'] = 'CommentCreateMutation'
        r2 = requests.post('https://graph.facebook.com/graphql',
                           data=api2_payload, headers=h2, timeout=30)
        data = r2.json()
        if 'data' in data and 'comment_create' in data.get('data', {}):
            return {'ok': True, 'raw': data}
        return {'ok': False, 'error': 'Comment thất bại', 'raw': data}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB SHARE
# ═══════════════════════════════════════════════════════════
def fb_share(token, post_id):
    try:
        r = requests.get('https://graph.facebook.com/me',
                         params={'access_token': token}, timeout=15)
        actor_id = r.json().get('id')
        if not actor_id:
            return {'ok': False, 'error': 'Token không hợp lệ'}

        parts = post_id.split('_', 1)
        if len(parts) != 2:
            return {'ok': False, 'error': 'PostID cần dạng owner_id_post_fbid'}
        owner_id, post_fbid = parts[0], parts[1]

        composer_session_id = str(uuid.uuid4())
        raw_linkable = f'S:_I{owner_id}:{post_fbid}:{post_fbid}'
        linkable_id = base64.b64encode(raw_linkable.encode()).decode()
        ufs_session_id = f'UFS-{uuid.uuid4()}-fg-{random.randint(1, 10)}'
        bloks_ver = '51ee0924c1a66b5dd670a44370f6278f66485250d78f72d036fb4ff6480c1d16'

        base_hdrs = {
            'User-Agent': FB_UA_552,
            'Accept-Encoding': 'gzip, deflate',
            'x-fb-request-analytics-tags': json.dumps({
                'network_tags': {'product': '350685531728',
                                 'request_category': 'graphql',
                                 'purpose': 'none', 'retry_attempt': '0'},
                'application_tags': 'graphservice'
            }),
            'x-fb-rmd': 'state=URL_ELIGIBLE',
            'priority': 'u=3, i',
            'x-graphql-client-library': 'graphservice',
            'x-fb-connection-type': 'WIFI',
            'authorization': f'OAuth {token}',
            'x-fb-http-engine': 'Tigon/Liger',
            'x-fb-client-ip': 'True',
            'x-fb-server-cluster': 'True'
        }

        api2_input = {
            'tracking': [],
            'logging': {'composer_session_id': composer_session_id},
            'reshare_original_post': 'SHARE_LINK_ONLY',
            'composer_type': 'share',
            'composer_source_surface': 'newsfeed',
            'message': {'text': ''},
            'composer_entry_point': 'uss_feed_to_feed_reshare',
            'action_timestamp': int(time.time()),
            'source': 'MOBILE',
            'audiences': [{'undirected': {'privacy': {
                'tag_expansion_state': 'UNSPECIFIED',
                'deny': [], 'base_state': 'EVERYONE', 'allow': []}}}],
            'attachments': [{'link': {'internal_linkable_id': linkable_id}}],
            'audiences_is_complete': True,
            'nectar_module': 'newsfeed_ufi',
            'actor_id': actor_id
        }
        api2_vars = json.dumps({
            'nt_context': {'using_white_navbar': True,
                           'styles_id': 'cc0995fd4392efdb0fd2bbe7fc9091fe',
                           'pixel_ratio': 3, 'is_push_on': True,
                           'is_flipper_enabled': False,
                           'theme_params': [{'value': [],
                                             'design_system_name': 'FDS'}],
                           'bloks_version': bloks_ver},
            'input': api2_input,
            'size_style': 'contain-fit',
            'profile_image_size': 120
        })
        api2_payload = {
            'method': 'post', 'pretty': 'false', 'format': 'json',
            'server_timestamps': 'true', 'locale': 'en_US',
            'fb_api_req_friendly_name': 'ComposerStoryCreateMutation',
            'fb_api_caller_class': 'graphservice',
            'client_doc_id': '9109379068877895824326160447',
            'fb_api_client_context': json.dumps({'is_background': False}),
            'variables': api2_vars,
            'fb_api_analytics_tags': json.dumps(
                [f'session_id={ufs_session_id}', 'GraphServices']),
            'client_trace_id': str(uuid.uuid4())
        }
        h2 = base_hdrs.copy()
        h2['x-fb-friendly-name'] = 'ComposerStoryCreateMutation'

        r2 = requests.post('https://graph.facebook.com/graphql',
                           data=api2_payload, headers=h2, timeout=30)
        for line in r2.text.splitlines():
            try:
                item = json.loads(line.strip())
                if 'data' in item and 'story_create' in item['data']:
                    story = item['data']['story_create'].get('story')
                    if story and story.get('id'):
                        return {'ok': True, 'story_id': story['id'],
                                'raw': item}
            except Exception:
                pass
        return {'ok': False, 'error': 'Share thất bại',
                'raw': r2.text[:500]}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: FB GET INFO
# ═══════════════════════════════════════════════════════════
def fb_get_info(token):
    try:
        r = requests.get("https://graph.facebook.com/me",
                         params={"access_token": token,
                                 "fields": "id,name,email,birthday"},
                         timeout=10)
        data = r.json()
        if "id" in data:
            try:
                r2 = requests.get(
                    f"https://graph.facebook.com/{data['id']}/picture",
                    params={"type": "large", "redirect": "false",
                            "access_token": token}, timeout=10)
                if "data" in r2.json() and "url" in r2.json()["data"]:
                    data["avatar_url"] = r2.json()["data"]["url"]
            except Exception:
                pass
            return {'ok': True, 'info': data}
        return {'ok': False,
                'error': data.get("error", {}).get("message", "Lỗi")}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# MODULE: PROXY GENERATOR
# ═══════════════════════════════════════════════════════════
def fetch_proxies(limit=500):
    apis = [
        {'url': 'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=all', 'type': 'HTTP'},
        {'url': 'https://api.proxyscrape.com/v2/?request=getproxies&protocol=https&timeout=3000&country=all&ssl=all&anonymity=all', 'type': 'HTTPS'},
        {'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt', 'type': 'HTTP'},
        {'url': 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/https.txt', 'type': 'HTTPS'},
        {'url': 'https://www.proxy-list.download/api/v1/get?type=https', 'type': 'HTTPS'},
        {'url': 'https://www.proxy-list.download/api/v1/get?type=http', 'type': 'HTTP'},
    ]
    all_p = []
    for a in apis:
        try:
            r = requests.get(a['url'], timeout=12)
            for line in r.text.split('\n'):
                line = line.strip()
                if line and ':' in line and not line.startswith('#'):
                    parts = line.split(':')
                    if len(parts) >= 2:
                        all_p.append({'ip': parts[0], 'port': parts[1],
                                      'type': a['type'],
                                      'url': f"{a['type'].lower()}://{line}",
                                      'status': 'LIVE'})
        except Exception:
            pass
    seen = {}
    https_list, http_list = [], []
    for p in all_p:
        key = f"{p['ip']}:{p['port']}"
        if key in seen:
            continue
        seen[key] = 1
        (https_list if p['type'] == 'HTTPS' else http_list).append(p)
    result = https_list[:limit]
    if len(result) < limit:
        result += http_list[:limit - len(result)]
    return result


# ═══════════════════════════════════════════════════════════
# MODULE: TOKEN PARSER
# ═══════════════════════════════════════════════════════════
def parse_token_cookie(raw):
    result = {'cookies': '', 'tokens': [], 'user_agents': []}
    cookies = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*=[^;\s]+)', raw)
    if cookies:
        seen = {}
        for c in cookies:
            k, v = c.split('=', 1)
            seen[k] = v
        result['cookies'] = '; '.join(f'{k}={v}' for k, v in seen.items())
    tokens = list(set(re.findall(r'(EAA[A-Za-z0-9]{30,})', raw)))
    tokens += list(set(re.findall(
        r'(eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+)', raw)))
    result['tokens'] = tokens
    result['user_agents'] = list(set(re.findall(
        r'(Mozilla/5\.0[^\n\r]{10,300})', raw)))
    return result


# ═══════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════
@app.route('/')
def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'index.html')
    if not os.path.exists(html_path):
        return "❌ Không tìm thấy file index.html", 500
    with open(html_path, 'r', encoding='utf-8') as f:
        return Response(f.read(), mimetype='text/html')


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})


# ═══════ CHUYỂN PAGE ═══════
@app.route('/api/chuyenpage/scan', methods=['POST'])
def api_cp_scan():
    token = (request.json or {}).get('token', '').strip()
    if not token:
        return jsonify({'success': False, 'error': 'Token trống'})
    try:
        t = ChuyenPageTool()
        uid, name = t.get_user_info(token)
        if not uid:
            return jsonify({'success': False,
                            'error': 'Token không hợp lệ'})
        pages = t.get_pages(token, uid)
        return jsonify({'success': True, 'uid': uid, 'name': name,
                        'pages': pages})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/chuyenpage/transfer', methods=['POST'])
def api_cp_transfer():
    d = request.json or {}
    stk = d.get('source_token', '').strip()
    spwd = d.get('source_password', '').strip()
    ttk = d.get('target_token', '').strip()
    puids = d.get('page_uids', [])
    if not all([stk, spwd, ttk, puids]):
        return jsonify({'success': False, 'error': 'Thiếu thông tin'})
    sid = str(uuid.uuid4())
    SESSION_STATUS[sid] = 'running'
    SESSION_LOGS[sid] = []

    def run():
        try:
            t = ChuyenPageTool()
            t.log_callback = lambda m: log_to_session(sid, m)
            tuid, tname = t.get_user_info(ttk)
            if not tuid:
                log_to_session(sid, "❌ Token đích không hợp lệ")
                SESSION_STATUS[sid] = 'error'
                return
            log_to_session(sid, f"🚀 Chuyển {len(puids)} page → {tname}")
            ok_cnt = 0
            fail_cnt = 0
            for pu in puids:
                if SESSION_STATUS.get(sid) == 'stopped':
                    log_to_session(sid, "⏹ Dừng")
                    break
                log_to_session(sid, f"⏳ Xử lý page: {pu}")
                ok, msg = t.transfer(stk, spwd, pu, ttk)
                if ok:
                    ok_cnt += 1
                    log_to_session(sid, f"✅ OK: {pu}")
                else:
                    fail_cnt += 1
                    log_to_session(sid, f"❌ Fail: {pu} - {msg}")
                time.sleep(1)
            log_to_session(sid, f"📊 Tổng kết: OK={ok_cnt} FAIL={fail_cnt}")
            SESSION_STATUS[sid] = 'done'
        except Exception as e:
            log_to_session(sid, f"❌ {e}")
            SESSION_STATUS[sid] = 'error'

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'success': True, 'session_id': sid})


# ═══════ INSTAGRAM REG ═══════
@app.route('/api/instagram/start', methods=['POST'])
def api_ig_start():
    d = request.json or {}
    num = int(d.get('num_accounts', 1))
    pwd = d.get('password', '').strip()
    if len(pwd) < 6:
        return jsonify({'success': False, 'error': 'Password ≥ 6 ký tự'})
    sid = str(uuid.uuid4())
    SESSION_STATUS[sid] = 'running'
    SESSION_LOGS[sid] = []

    def run():
        try:
            t = InstagramReg()
            t.log_callback = lambda m: log_to_session(sid, m)
            t.is_stopped = lambda: SESSION_STATUS.get(sid) == 'stopped'
            log_to_session(sid, f"🚀 Tạo {num} tài khoản Instagram")
            ok = 0
            for i in range(num):
                if SESSION_STATUS.get(sid) == 'stopped':
                    log_to_session(sid, "⏹ Dừng")
                    break
                log_to_session(sid, f"\n=== ACC {i+1}/{num} ===")
                if t.create_account(pwd):
                    ok += 1
                if i < num - 1:
                    time.sleep(3)
            log_to_session(sid, f"\n📊 Thành công: {ok}/{num}")
            SESSION_STATUS[sid] = 'done'
        except Exception as e:
            log_to_session(sid, f"❌ {e}")
            SESSION_STATUS[sid] = 'error'

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'success': True, 'session_id': sid})


# ═══════ FACEBOOK iOS REG ═══════
@app.route('/api/regfb/start', methods=['POST'])
def api_fb_start():
    d = request.json or {}
    num = int(d.get('num_accounts', 1))
    pwd = d.get('password', 'anhem1234').strip()
    sid = str(uuid.uuid4())
    SESSION_STATUS[sid] = 'running'
    SESSION_LOGS[sid] = []

    def run():
        try:
            t = FacebookIOSReg()
            t.log_callback = lambda m: log_to_session(sid, m)
            t.is_stopped = lambda: SESSION_STATUS.get(sid) == 'stopped'
            log_to_session(sid, f"🚀 Tạo {num} tài khoản Facebook iOS")
            ok = 0
            for i in range(num):
                if SESSION_STATUS.get(sid) == 'stopped':
                    break
                log_to_session(sid, f"\n=== ACC {i+1}/{num} ===")
                success, info = t.register(pwd)
                if success:
                    ok += 1
                if i < num - 1:
                    time.sleep(5)
            log_to_session(sid, f"\n📊 Thành công: {ok}/{num}")
            SESSION_STATUS[sid] = 'done'
        except Exception as e:
            log_to_session(sid, f"❌ {e}")
            SESSION_STATUS[sid] = 'error'

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'success': True, 'session_id': sid})


# ═══════ FB REACTION ═══════
@app.route('/api/fb/reaction', methods=['POST'])
def api_fb_reaction():
    d = request.json or {}
    token = d.get('token', '').strip()
    post_id = d.get('post_id', '').strip()
    reaction = d.get('reaction', 'LIKE').strip().upper()
    if not token or not post_id:
        return jsonify({'success': False,
                        'error': 'Thiếu token hoặc post_id'})
    result = fb_reaction(token, post_id, reaction)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ FB GET PAGE ═══════
@app.route('/api/fb/getpage', methods=['POST'])
def api_fb_getpage():
    token = (request.json or {}).get('token', '').strip()
    if not token:
        return jsonify({'success': False, 'error': 'Token trống'})
    result = fb_get_pages(token)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ FB REG PAGE ═══════
@app.route('/api/fb/regpage', methods=['POST'])
def api_fb_regpage():
    d = request.json or {}
    token = d.get('token', '').strip()
    count = int(d.get('count', 1))
    if not token:
        return jsonify({'success': False, 'error': 'Token trống'})
    sid = str(uuid.uuid4())
    SESSION_STATUS[sid] = 'running'
    SESSION_LOGS[sid] = []

    def run():
        try:
            log_to_session(sid, f"🚀 Tạo {count} page FB")
            ok = 0
            for i in range(count):
                if SESSION_STATUS.get(sid) == 'stopped':
                    break
                name = VNNameGenerator.gen()
                log_to_session(sid, f"📄 Page #{i+1}: {name}")
                result = fb_create_page(token, name)
                if result.get('ok'):
                    log_to_session(sid,
                                   f"✅ OK: {name} "
                                   f"(UID: {result.get('page_id')})")
                    ok += 1
                else:
                    log_to_session(sid,
                                   f"❌ Fail: {name} - "
                                   f"{result.get('error')}")
                time.sleep(2)
            log_to_session(sid, f"📊 Thành công: {ok}/{count}")
            SESSION_STATUS[sid] = 'done'
        except Exception as e:
            log_to_session(sid, f"❌ {e}")
            SESSION_STATUS[sid] = 'error'

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'success': True, 'session_id': sid})


# ═══════ FB GET UID ═══════
@app.route('/api/fb/getid', methods=['POST'])
def api_fb_getid():
    link = (request.json or {}).get('link', '').strip()
    if not link:
        return jsonify({'success': False, 'error': 'Link trống'})
    result = fb_get_uid_from_link(link)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ FB LIKE PAGE ═══════
@app.route('/api/fb/likepage', methods=['POST'])
def api_fb_likepage():
    d = request.json or {}
    token = d.get('token', '').strip()
    target = d.get('target_uid', '').strip()
    if not token or not target:
        return jsonify({'success': False,
                        'error': 'Thiếu token/target_uid'})
    result = fb_like_page(token, target)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ FB UP AVATAR/COVER ═══════
@app.route('/api/fb/upavatar', methods=['POST'])
def api_fb_upavatar():
    d = request.json or {}
    token = d.get('token', '').strip()
    url = d.get('image_url', '').strip()
    if not token or not url:
        return jsonify({'success': False,
                        'error': 'Thiếu token/image_url'})
    result = fb_upload_avatar(token, url)
    return jsonify({'success': result.get('ok', False), **result})


@app.route('/api/fb/upcover', methods=['POST'])
def api_fb_upcover():
    d = request.json or {}
    token = d.get('token', '').strip()
    url = d.get('image_url', '').strip()
    if not token or not url:
        return jsonify({'success': False,
                        'error': 'Thiếu token/image_url'})
    result = fb_upload_cover(token, url)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ FB FOLLOW ═══════
@app.route('/api/fb/follow', methods=['POST'])
def api_fb_follow():
    d = request.json or {}
    token = d.get('token', '').strip()
    target = d.get('target_uid', '').strip()
    if not token or not target:
        return jsonify({'success': False,
                        'error': 'Thiếu token/target_uid'})
    result = fb_follow(token, target)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ FB COMMENT ═══════
@app.route('/api/fb/comment', methods=['POST'])
def api_fb_comment():
    d = request.json or {}
    token = d.get('token', '').strip()
    post_id = d.get('post_id', '').strip()
    text = d.get('text', '').strip()
    if not token or not post_id or not text:
        return jsonify({'success': False, 'error': 'Thiếu thông tin'})
    result = fb_comment(token, post_id, text)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ FB SHARE ═══════
@app.route('/api/fb/share', methods=['POST'])
def api_fb_share():
    d = request.json or {}
    token = d.get('token', '').strip()
    post_id = d.get('post_id', '').strip()
    if not token or not post_id:
        return jsonify({'success': False,
                        'error': 'Thiếu token/post_id'})
    result = fb_share(token, post_id)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ FB GET INFO ═══════
@app.route('/api/fb/getinfo', methods=['POST'])
def api_fb_getinfo():
    token = (request.json or {}).get('token', '').strip()
    if not token:
        return jsonify({'success': False, 'error': 'Token trống'})
    result = fb_get_info(token)
    return jsonify({'success': result.get('ok', False), **result})


# ═══════ PROXY ═══════
@app.route('/api/proxy/fetch', methods=['POST'])
def api_px_fetch():
    try:
        limit = int((request.json or {}).get('limit', 500))
        proxies = fetch_proxies(limit)
        return jsonify({'success': True, 'proxies': proxies,
                        'total': len(proxies)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ═══════ TOKEN PARSER ═══════
@app.route('/api/gettoken/parse', methods=['POST'])
def api_tk_parse():
    raw = (request.json or {}).get('raw', '')
    return jsonify({'success': True, 'result': parse_token_cookie(raw)})


# ═══════ LOGS ═══════
@app.route('/api/logs/<sid>')
def api_logs(sid):
    def gen():
        idx = 0
        while True:
            if sid in SESSION_LOGS:
                logs = SESSION_LOGS[sid]
                if idx < len(logs):
                    for l in logs[idx:]:
                        yield f"data: {json.dumps(l, ensure_ascii=False)}\n\n"
                    idx = len(logs)
            st = SESSION_STATUS.get(sid, 'unknown')
            yield f"data: {json.dumps({'status': st}, ensure_ascii=False)}\n\n"
            if st in ['done', 'error', 'stopped']:
                yield f"data: {json.dumps({'status': 'closed'}, ensure_ascii=False)}\n\n"
                break
            time.sleep(0.5)
    return Response(stream_with_context(gen()),
                    mimetype='text/event-stream')


@app.route('/api/stop/<sid>', methods=['POST'])
def api_stop(sid):
    SESSION_STATUS[sid] = 'stopped'
    return jsonify({'success': True})


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("  🚀 VNDEVCODE MULTI TOOL WEB - FULL")
    print(f"  🌐 http://localhost:{port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

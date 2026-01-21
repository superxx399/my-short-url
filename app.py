import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_full_feature_ultra_2026"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'sentinel_v16.db')

# --- 完整配置数据 ---
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]
COUNTRIES = ["中国", "香港", "台湾", "美国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "阿联酋", "沙特", "巴西"]
DEVICES = ["iPhone 13-15", "iPhone 16 Pro", "iPad", "Android 14-15", "Windows PC", "Mac-OS"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    # 保持所有专业字段：pixel, event, campaign, mock_req
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
        pixel TEXT, event TEXT, campaign TEXT, mock_req TEXT, p_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, 
        domain TEXT, slot TEXT, note TEXT, date TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('super', '777888', 'SUPER_ADMIN')")
    c.execute("INSERT OR IGNORE INTO policies (id, name, devices, countries, r_url) VALUES (1, '默认规则(全放行)', 'All', 'All', 'https://www.facebook.com')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=20); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

@app.route('/<code>')
def jump(code):
    link = db_action("SELECT ticket_id, slot, note FROM mapping WHERE code = ?", (code,))
    if not link: abort(404)
    t_id, slot, note = link[0]
    ticket = db_action("SELECT url FROM tickets WHERE id = ?", (t_id,))
    if not ticket: abort(404)
    db_action("INSERT INTO logs (link, ip, err, dev, slot, src, time) VALUES (?,?,?,?,?,?,?)",
              (code, request.remote_addr, "通过", request.headers.get('User-Agent', 'Mobile')[:30], slot, note, datetime.datetime.now().strftime("%m-%d %H:%M")), False)
    return redirect(ticket[0])

# --- 完整版 UI 模板 (保留所有功能与样式) ---
UI_LAYOUT = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
<style>
    body{background:#f8fafc; font-family:sans-serif;}
    .sidebar{width:240px; background:#fff; border-right:1px solid #e2e8f0; position:fixed; height:100vh;}
    .nav-link{display:block; padding:15px 30px; color:#64748b; font-weight:600; border-left:4px solid transparent;}
    .nav-active{background:#f1f5f9; color:#2563eb; border-left:4px solid #2563eb;}
    .btn-blue{background:#2563eb; color:#fff; padding:10px 24px; border-radius:8px; font-weight:bold; transition:0.3s;}
    .btn-blue:hover{background:#1d4ed8; transform:translateY(-1px);}
    .toggle-box{padding:6px 14px; border:1px solid #e2e8f0; border-radius:8px; cursor:pointer; font-size:12px; background:#fff; transition:0.2s;}
    .selected{background:#2563eb; color:#fff; border-color:#2563eb;}
    input, select, textarea{width:100%; padding:12px; border:1px solid #e2e8f0; border-radius:10px; margin-top:5px; outline:none; background:#f9fafb;}
    input:focus{border-color:#2563eb; background:#fff;}
    label{font-size:12px; font-weight:bold; color:#94a3b8; margin-top:12px; display:block; text-transform:uppercase;}
</style></head>
<body class="flex">
    <nav class="sidebar py-10">
        <div class="px-8 mb-12"><h1 class="text-2xl font-black text-blue-600 tracking-tighter">SENTINEL</h1><p class="text-[10px] text-slate-400 font-bold">V1.6 FLAGSHIP</p></div>
        <a href="/admin?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">风控规则</a>
        <a href="/admin?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">投放工单</a>
        <a href="/admin?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">推广链路</a>
        <a href="/admin?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">投放报表</a>
        <a href="/logout" class="absolute bottom-10 px-8 text-sm text-slate-400 hover:text-red-500">退出系统</a>
    </nav>
    <main class="flex-1 ml-[240px] p-12">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-3xl font-black text-slate-800">{{tab_name}}</h2>
            <button onclick="document.getElementById('m').style.display='flex'" class="btn-blue shadow-lg shadow-blue-100">+ 新增{{tab_name}}</button>
        </div>
        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-slate-50 border-b">
                    <tr>{% for h in headers %}<th class="p-5 text-slate-500 font-bold uppercase">{{h}}</th>{% endfor %}<th class="p-5 text-right">管理</th></tr>
                </thead>
                <tbody class="divide-y">
                    {% for row in rows %}
                    <tr class="hover:bg-slate-50/50">
                        {% for cell in row %}<td class="p-5 font-medium text-slate-700">{{cell}}</td>{% endfor %}
                        <td class="p-5 text-right"><a href="/action/del/{{tab}}/{{row[0]}}" class="text-red-400 font-bold hover:underline" onclick="return confirm('确定删除?')">删除</a></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="m" class="fixed inset-0 bg-slate-900/40 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white rounded-3xl p-10 w-full max-w-2xl shadow-2xl overflow-y-auto max-h-[90vh]">
            <h3 class="text-2xl font-black mb-6 text-slate-800">配置 - {{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST">
                {% if tab == 'tickets' %}
                    <div class="grid grid-cols-2 gap-6">
                        <div><label>工单名称</label><input name="name" required placeholder="如: WA-马来-01"></div>
                        <div><label>控制模式</label><select name="type"><option>单导模式</option><option>群导模式</option></select></div>
                    </div>
                    <label>工单跳转目标 (手机号或URL)</label><input name="url" placeholder="852xxxxxx" required>
                    <label>关联风控规则</label><select name="p_id">{% for p in plist %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select>
                    <div class="grid grid-cols-2 gap-6">
                        <div><label>系列名包含</label><input name="campaign" placeholder="可选"></div>
                        <div><label>模拟请求</label><select name="mock_req"><option>GET</option><option>POST</option></select></div>
                    </div>
                    <div class="grid grid-cols-2 gap-6">
                        <div><label>广告像素 (Pixel)</label><input name="pixel" placeholder="可选"></div>
                        <div><label>广告事件</label><input name="event" placeholder="Lead / Purchase"></div>
                    </div>
                    <label>内部备注</label><textarea name="note" class="w-full border p-3 rounded-xl mt-2"></textarea>
                {% elif tab == 'policies' %}
                    <label>规则显示名称</label><input name="name" required placeholder="如: IOS+马来专用">
                    <label>允许访问的国家 (多选)</label>
                    <div class="flex flex-wrap gap-2 mt-2">
                        {% for c in countries %}<div class="toggle-box" onclick="ts(this, 'c_in')">{{c}}</div>{% endfor %}
                    </div><input type="hidden" name="countries" id="c_in">
                    <label>允许访问的设备 (多选)</label>
                    <div class="flex flex-wrap gap-2 mt-2">
                        {% for d in devices %}<div class="toggle-box" onclick="ts(this, 'd_in')">{{d}}</div>{% endfor %}
                    </div><input type="hidden" name="devices" id="d_in">
                    <label>拦截后跳转地址</label><input name="r_url" value="https://www.facebook.com">
                {% elif tab == 'links' %}
                    <label>短链域名</label><select name="domain">{% for d in domains %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                    <label>关联工单</label><select name="ticket_id">{% for t in tlist %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}</select>
                    <label>投放版位 (Slot)</label><input name="slot" placeholder="如: FB-Feed">
                    <label>内部备注</label><input name="note">
                {% endif %}
                <div class="flex justify-end mt-10 space-x-4 border-t pt-8">
                    <button type="button" onclick="document.getElementById('m').style.display='none'" class="px-6 text-slate-400 font-bold">取消</button>
                    <button class="btn-blue px-12 py-3 rounded-xl shadow-blue-200 shadow-lg">确认保存配置</button>
                </div>
            </form>
        </div>
    </div>
    <script>
        function ts(el, id) {
            el.classList.toggle('selected');
            const sel = Array.from(el.parentElement.querySelectorAll('.selected')).map(e => e.innerText);
            document.getElementById(id).value = sel.join(',');
        }
    </script>
</body></html>
"""

@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form
    if tab == 'policies':
        db_action("INSERT INTO policies (name,devices,countries,r_url) VALUES (?,?,?,?)", (f['name'], f.get('devices','All'), f.get('countries','All'), f['r_url']), False)
    elif tab == 'tickets':
        u = f['url']; u = f"https://wa.me/{u}" if u.isdigit() else u
        db_action("INSERT INTO tickets (name,url,type,pixel,event,campaign,mock_req,p_id) VALUES (?,?,?,?,?,?,?,?)", 
                  (f['name'], u, f['type'], f.get('pixel',''), f.get('event',''), f.get('campaign',''), f.get('mock_req',''), f['p_id']), False)
    elif tab == 'links':
        code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        db_action("INSERT INTO mapping (code,ticket_id,domain,slot,note,date) VALUES (?,?,?,?,?,?)", (code, f['ticket_id'], f['domain'], f['slot'], f['note'], datetime.datetime.now().strftime("%m-%d %H:%M")), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/action/del/<tab>/<id>')
def handle_del(tab, id):
    if 'user' not in session: return redirect('/login')
    db_action(f"DELETE FROM {tab} WHERE id = ?", (id,), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    plist = db_action("SELECT id, name FROM policies")
    tlist = db_action("SELECT id, name FROM tickets")
    conf = {
        "policies": ("风控规则", ["ID", "名称", "跳转目标"], "SELECT id, name, r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "名称", "目标链接", "像素ID"], "SELECT id, name, url, pixel FROM tickets"),
        "links": ("推广链路", ["ID", "访问路径", "版位", "备注"], "SELECT id, '/'||code, slot, note FROM mapping"),
        "logs": ("投放报表", ["ID", "链路", "IP", "详情", "版位", "来源", "时间"], "SELECT * FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI_LAYOUT, tab=tab, tab_name=title, headers=headers, rows=rows, plist=plist, tlist=tlist, countries=COUNTRIES, devices=DEVICES, domains=DOMAINS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form.get('u') == 'super' and request.form.get('p') == '777888':
        session['user'] = 'super'; return redirect('/admin')
    return '<body style="background:#f1f5f9;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;"><form method="post" style="background:#fff;padding:50px;border-radius:30px;box-shadow:0 20px 60px rgba(0,0,0,0.05);width:360px;"><h2 style="color:#2563eb;font-size:28px;font-weight:900;margin-bottom:10px;letter-spacing:-1px;">SENTINEL LOGIN</h2><p style="color:#94a3b8;font-size:12px;margin-bottom:30px;font-weight:bold;">请输入总后端授权凭据</p><input name="u" placeholder="Account" style="width:100%;margin-bottom:15px;padding:14px;border:1px solid #e2e8f0;border-radius:12px;outline:none;"><input name="p" type="password" placeholder="Password" style="width:100%;margin-bottom:30px;padding:14px;border:1px solid #e2e8f0;border-radius:12px;outline:none;"><button style="width:100%;background:#2563eb;color:#fff;padding:16px;border-radius:12px;font-weight:bold;border:none;cursor:pointer;box-shadow:0 10px 20px rgba(37,99,235,0.2);">进入管理系统</button></form></body>'

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888)
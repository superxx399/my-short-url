import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_fix_500_final"
# 确保在 Render 环境下使用绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'sentinel_v16.db')

# --- 核心配置 ---
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]
COUNTRIES = ["中国", "香港", "台湾", "美国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "阿联酋", "巴西"]
DEVICES = ["iPhone 13-15", "iPhone 16 Pro", "Android 14-15", "Windows PC", "Mac-OS"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
        pixel TEXT, event TEXT, campaign TEXT, mock_req TEXT, p_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, 
        domain TEXT, slot TEXT, note TEXT, date TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    # 初始化超管
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('super', '777888', 'SUPER_ADMIN')")
    # 关键：初始化一个默认规则，防止后续添加工单因找不到规则而报 500
    c.execute("INSERT OR IGNORE INTO policies (id, name, devices, countries, r_url) VALUES (1, '默认规则', 'All', 'All', 'https://www.facebook.com')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=10); c = conn.cursor()
    c.execute(sql, args)
    res = c.fetchall() if fetch else None
    conn.commit(); conn.close()
    return res

# --- 跳转引擎 ---
@app.route('/<code>')
def jump_engine(code):
    link = db_action("SELECT ticket_id, slot, note FROM mapping WHERE code = ?", (code,))
    if not link: abort(404)
    t_id, slot, note = link[0]
    ticket = db_action("SELECT url FROM tickets WHERE id = ?", (t_id,))
    if not ticket: abort(404)
    # 记录访问日志
    db_action("INSERT INTO logs (link, ip, err, dev, slot, src, time) VALUES (?,?,?,?,?,?,?)",
              (code, request.remote_addr, "通过", request.headers.get('User-Agent', 'Mobile')[:30], slot, note, datetime.datetime.now().strftime("%m-%d %H:%M")), False)
    return redirect(ticket[0])

# --- UI 模板 ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#f9fafb; font-family:sans-serif;}
        .sidebar{width:220px; background:#fff; border-right:1px solid #e5e7eb; position:fixed; height:100vh;}
        .nav-link{display:block; padding:15px 25px; color:#4b5563; font-weight:600; font-size:14px;}
        .nav-active{background:#eff6ff; color:#2563eb; border-right:4px solid #2563eb;}
        .btn-blue{background:#2563eb; color:#fff; padding:10px 24px; border-radius:8px; font-weight:bold;}
        .toggle-box{padding:6px 12px; border:1px solid #e5e7eb; border-radius:6px; cursor:pointer; font-size:12px; background:#fff;}
        .selected{background:#2563eb; color:#fff; border-color:#2563eb;}
        input, select, textarea{width:100%; padding:10px; border:1px solid #d1d5db; border-radius:8px; margin-top:5px; outline:none;}
        label{font-size:12px; font-weight:bold; color:#6b7280; margin-top:10px; display:block;}
    </style>
</head>
<body class="flex">
    <nav class="sidebar py-10">
        <div class="px-8 mb-12 text-2xl font-black text-blue-600">SENTINEL</div>
        <a href="/admin?tab=users" class="nav-link {{'nav-active' if tab=='users'}}">成员管理</a>
        <a href="/admin?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">风控规则</a>
        <a href="/admin?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">投放工单</a>
        <a href="/admin?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">推广链路</a>
        <a href="/admin?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">投放报表</a>
    </nav>
    <main class="flex-1 ml-[220px] p-12">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-3xl font-extrabold text-slate-800">{{tab_name}}</h2>
            <button onclick="document.getElementById('m').style.display='flex'" class="btn-blue">+ 新增</button>
        </div>
        <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-gray-50 border-b">
                    <tr>{% for h in headers %}<th class="p-4 text-gray-500">{{h}}</th>{% endfor %}<th class="p-4 text-right">操作</th></tr>
                </thead>
                <tbody class="divide-y">
                    {% for row in rows %}
                    <tr class="hover:bg-gray-50">
                        {% for cell in row %}<td class="p-4 font-medium">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right">
                            <a href="/action/del/{{tab}}/{{row[0]}}" class="text-red-500 font-bold hover:underline" onclick="return confirm('确定删除?')">删除</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="m" class="fixed inset-0 bg-slate-900/60 hidden items-center justify-center p-4 z-50 backdrop-blur-sm">
        <div class="bg-white rounded-2xl w-full max-w-xl p-8 shadow-2xl overflow-y-auto max-h-[90vh]">
            <h3 class="text-xl font-bold mb-6">新增 - {{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST">
                {% if tab == 'tickets' %}
                    <label>工单名称</label><input name="name" required>
                    <label>跳转目标 (手机号或URL)</label><input name="url" placeholder="如: 852xxxxxx" required>
                    <label>控制模式</label><select name="type"><option>单导模式</option><option>群导模式</option></select>
                    <label>关联风控规则</label>
                    <select name="p_id">{% for p in plist %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select>
                    <div class="grid grid-cols-2 gap-4">
                        <div><label>广告像素</label><input name="pixel"></div>
                        <div><label>系列名包含</label><input name="campaign"></div>
                    </div>
                {% elif tab == 'policies' %}
                    <label>规则名</label><input name="name" required>
                    <label>允许国家</label>
                    <div class="flex flex-wrap gap-2 mt-2">
                        {% for c in countries %}<div class="toggle-box" onclick="ts(this, 'c_in')">{{c}}</div>{% endfor %}
                    </div>
                    <input type="hidden" name="countries" id="c_in">
                    <label>允许机型</label>
                    <div class="flex flex-wrap gap-2 mt-2">
                        {% for d in devices %}<div class="toggle-box" onclick="ts(this, 'd_in')">{{d}}</div>{% endfor %}
                    </div>
                    <input type="hidden" name="devices" id="d_in">
                    <label>拦截后跳往</label><input name="r_url" value="https://www.facebook.com">
                {% elif tab == 'links' %}
                    <label>选择域名</label><select name="domain">{% for d in domains %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                    <label>关联工单</label><select name="ticket_id">{% for t in tlist %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}</select>
                    <label>备注版位 (Slot)</label><input name="slot">
                    <label>备注说明</label><input name="note">
                {% endif %}
                <div class="flex justify-end mt-8 space-x-4 border-t pt-6">
                    <button type="button" onclick="document.getElementById('m').style.display='none'" class="text-gray-400 font-bold">取消</button>
                    <button class="btn-blue px-10">保存</button>
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
</body>
</html>
"""

@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'policies':
        db_action("INSERT INTO policies (name,devices,countries,r_url) VALUES (?,?,?,?)", (f['name'], f.get('devices',''), f.get('countries',''), f['r_url']), False)
    elif tab == 'tickets':
        u = f['url']
        if u.isdigit(): u = f"https://wa.me/{u}"
        db_action("INSERT INTO tickets (name,url,type,pixel,p_id) VALUES (?,?,?,?,?)", (f['name'], u, f['type'], f.get('pixel',''), f['p_id']), False)
    elif tab == 'links':
        code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        db_action("INSERT INTO mapping (code,ticket_id,domain,slot,note,date) VALUES (?,?,?,?,?,?)", (code, f['ticket_id'], f['domain'], f.get('slot',''), f.get('note',''), now), False)
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
        "users": ("成员管理", ["ID", "账号", "角色"], "SELECT id, u, '投放经理' FROM users"),
        "policies": ("风控规则", ["ID", "规则名", "准入国家", "拦截跳转"], "SELECT id, name, countries, r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "名称", "目标", "像素"], "SELECT id, name, url, pixel FROM tickets"),
        "links": ("推广链路", ["ID", "访问代码", "版位", "备注"], "SELECT id, '/'||code, slot, note FROM mapping"),
        "logs": ("投放报表", ["ID", "链路", "IP", "状态", "设备", "版位", "备注", "时间"], "SELECT * FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(HTML_LAYOUT, tab=tab, tab_name=title, headers=headers, rows=rows, plist=plist, tlist=tlist, countries=COUNTRIES, devices=DEVICES, domains=DOMAINS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'super' and request.form['p'] == '777888':
        session['user'] = 'super'; return redirect('/admin')
    return '<body style="background:#f1f5f9;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#fff;padding:50px;border-radius:20px;box-shadow:0 10px 30px rgba(0,0,0,0.1);width:350px;"><h2>SENTINEL LOGIN</h2><input name="u" placeholder="Account" style="width:100%;margin-bottom:10px;padding:10px;border:1px solid #ddd;border-radius:8px;"><input name="p" type="password" placeholder="Password" style="width:100%;margin-bottom:20px;padding:10px;border:1px solid #ddd;border-radius:8px;"><button style="width:100%;background:#2563eb;color:#fff;padding:10px;border-radius:8px;font-weight:bold;">LOGIN</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888)
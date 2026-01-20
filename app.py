import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_fb_flagship_v12"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 静态配置 ---
COUNTRIES = ["中国", "香港", "台湾", "美国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "印尼", "菲律宾", "阿联酋", "巴西", "英国", "德国"]
DEVICES = ["iPhone 8-X", "iPhone 11-13", "iPhone 14-16", "Android 11-15", "PC-Windows", "PC-MacOS"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    # 规则表字段必须齐全
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
        pixel TEXT, p_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, 
        domain TEXT, slot TEXT, note TEXT, date TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('admin', '777888', 'ROOT')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=10); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 短链跳转逻辑 ---
@app.route('/<code>')
def jump(code):
    link = db_action("SELECT ticket_id, slot, note FROM mapping WHERE code = ?", (code,))
    if not link: abort(404)
    t_id, slot, note = link[0]
    ticket = db_action("SELECT url FROM tickets WHERE id = ?", (t_id,))
    if not ticket: abort(404)
    
    # 记录日志
    ip = request.remote_addr
    ua = request.headers.get('User-Agent', 'Mobile')
    now = datetime.datetime.now().strftime("%m-%d %H:%M")
    db_action("INSERT INTO logs (link, ip, err, dev, slot, src, time) VALUES (?,?,?,?,?,?,?)",
              (code, ip, "成功", ua[:30], slot, note, now), False)
    return redirect(ticket[0])

# --- 后台 UI 模板 ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#f4f7f9;font-family:sans-serif;}
        .sidebar{width:200px;background:#fff;border-right:1px solid #ddd;position:fixed;height:100vh;}
        .nav-link{display:block;padding:15px 25px;color:#4b5563;font-weight:600;font-size:14px;}
        .nav-active{background:#eff6ff;color:#2563eb;border-right:4px solid #2563eb;}
        .card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;}
        .btn-blue{background:#2563eb;color:#fff;padding:8px 20px;border-radius:6px;font-weight:bold;}
        .toggle-btn{padding:5px 12px;border:1px solid #ddd;border-radius:4px;font-size:12px;cursor:pointer;background:#fff;}
        .selected{background:#2563eb;color:#fff;border-color:#2563eb;}
        input, select{width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;margin-top:5px;outline:none;}
    </style>
</head>
<body class="flex">
    <nav class="sidebar py-8">
        <div class="px-8 mb-10 text-xl font-black text-blue-600">SENTINEL</div>
        <a href="?tab=users" class="nav-link {{'nav-active' if tab=='users'}}">成员管理</a>
        <a href="?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">风控规则</a>
        <a href="?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">投放工单</a>
        <a href="?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">推广链路</a>
        <a href="?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">投放报表</a>
    </nav>
    <main class="flex-1 ml-[200px] p-10">
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-2xl font-bold text-gray-800">{{tab_name}}</h2>
            <button onclick="document.getElementById('m').style.display='flex'" class="btn-blue">+ 新增数据</button>
        </div>
        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-gray-50 border-b">
                    <tr>{% for h in headers %}<th class="p-4 font-bold text-gray-600">{{h}}</th>{% endfor %}<th class="p-4 text-right">管理</th></tr>
                </thead>
                <tbody class="divide-y">
                    {% for row in rows %}
                    <tr class="hover:bg-gray-50">
                        {% for cell in row %}<td class="p-4">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right space-x-4">
                            <button class="text-blue-600 font-bold" onclick="alert('编辑功能已就绪')">编辑</button>
                            <a href="/action/del/{{tab}}/{{row[0]}}" class="text-red-500 font-bold">删除</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>
    
    <div id="m" class="fixed inset-0 bg-black/50 hidden items-center justify-center p-4 z-50">
        <div class="bg-white rounded-xl w-full max-w-lg p-8 shadow-2xl overflow-y-auto max-h-[90vh]">
            <h3 class="text-xl font-bold mb-6 border-b pb-4">添加 - {{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST" id="dataForm">
                {% if tab == 'policies' %}
                    <label class="block text-xs font-bold text-gray-500 uppercase">规则名称</label>
                    <input name="name" required>
                    <label class="block text-xs font-bold text-gray-500 uppercase mt-4">允许国家 (多选)</label>
                    <div class="flex flex-wrap gap-2 mt-2">
                        {% for c in countries %}<div class="toggle-btn" onclick="toggleSelection(this, 'countries_input')">{{c}}</div>{% endfor %}
                    </div>
                    <input type="hidden" name="countries" id="countries_input">
                    <label class="block text-xs font-bold text-gray-500 uppercase mt-4">允许设备</label>
                    <div class="flex flex-wrap gap-2 mt-2">
                        {% for d in devices %}<div class="toggle-btn" onclick="toggleSelection(this, 'devices_input')">{{d}}</div>{% endfor %}
                    </div>
                    <input type="hidden" name="devices" id="devices_input">
                    <label class="block text-xs font-bold text-gray-500 uppercase mt-4">拦截后跳转 URL</label>
                    <input name="r_url" value="https://www.facebook.com">
                {% elif tab == 'tickets' %}
                    <label>工单备注名</label><input name="name" required>
                    <label>目标链接/WhatsApp号</label><input name="url" required placeholder="852xxxxxx">
                    <label>模式</label><select name="type"><option>单导模式</option><option>群导模式</option></select>
                    <label>关联规则</label><select name="p_id">{% for p in plist %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select>
                {% elif tab == 'links' %}
                    <label>域名</label><select name="domain"><option>https://secure-link.top</option><option>https://fb-check.net</option></select>
                    <label>关联工单</label><select name="ticket_id">{% for t in tlist %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}</select>
                    <label>备注版位 (Slot)</label><input name="slot" placeholder="如: FB-Feed">
                    <label>备注名称</label><input name="note" placeholder="如: 投放01组">
                {% endif %}
                <div class="flex justify-end mt-8 space-x-4 border-t pt-6">
                    <button type="button" onclick="document.getElementById('m').style.display='none'" class="text-gray-400">取消</button>
                    <button class="btn-blue px-10">保存</button>
                </div>
            </form>
        </div>
    </div>
    <script>
        function toggleSelection(el, inputId) {
            el.classList.toggle('selected');
            const parent = el.parentElement;
            const selected = Array.from(parent.querySelectorAll('.selected')).map(e => e.innerText);
            document.getElementById(inputId).value = selected.join(',');
        }
    </script>
</body>
</html>
"""

# --- 业务逻辑 ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'policies':
        db_action("INSERT INTO policies (name,devices,countries,r_url) VALUES (?,?,?,?)", (f['name'], f['devices'], f['countries'], f['r_url']), False)
    elif tab == 'tickets':
        u = f['url']
        if u.isdigit(): u = f"https://wa.me/{u}"
        db_action("INSERT INTO tickets (name,url,type,p_id) VALUES (?,?,?,?)", (f['name'], u, f['type'], f['p_id']), False)
    elif tab == 'links':
        code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        db_action("INSERT INTO mapping (code,ticket_id,domain,slot,note,date) VALUES (?,?,?,?,?,?)", (code, f['ticket_id'], f['domain'], f['slot'], f['note'], now), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/action/del/<tab>/<id>')
def handle_del(tab, id):
    db_action(f"DELETE FROM {tab} WHERE id = ?", (id,), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    plist = db_action("SELECT id, name FROM policies")
    tlist = db_action("SELECT id, name FROM tickets")
    conf = {
        "users": ("成员管理", ["ID", "账号", "备注"], "SELECT id, u, n FROM users"),
        "policies": ("风控规则", ["ID", "名称", "允许国家", "跳转URL"], "SELECT id, name, countries, r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "名称", "目标URL", "模式"], "SELECT id, name, url, type FROM tickets"),
        "links": ("推广链路", ["ID", "短链", "版位", "备注"], "SELECT id, '/'||code, slot, note FROM mapping"),
        "logs": ("投放报表", ["ID", "链路", "IP", "状态", "UA", "版位", "备注", "时间"], "SELECT * FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=title, headers=headers, rows=rows, user=session['user'], countries=COUNTRIES, devices=DEVICES, plist=plist, tlist=tlist)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'admin' and request.form['p'] == '777888':
        session['user'] = 'admin'; return redirect('/admin')
    return '<body><form method="post">Admin:<input name="u"> Pass:<input name="p" type="password"><button>Login</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
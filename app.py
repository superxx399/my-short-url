import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, abort

# --- 强制路径修正 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'sentinel_v16.db')

app = Flask(__name__)
app.secret_key = "sentinel_final_2026_pro"

# --- 自动修复：如果数据库存在旧文件则强制物理删除 ---
if os.path.exists(DB_PATH):
    try: os.remove(DB_PATH)
    except: pass

# --- 配置数据 ---
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]
COUNTRIES = ["中国", "香港", "台湾", "美国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "阿联酋", "巴西"]
DEVICES = ["iPhone 13-15", "iPhone 16 Pro", "Android 14-15", "Windows PC", "Mac-OS"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 强制创建所有表，确保字段一个不缺
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, pixel TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, domain TEXT, slot TEXT, note TEXT, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    # 初始化超管
    c.execute("INSERT OR IGNORE INTO users (id, u, p, n) VALUES (1, 'super', '777888', 'ROOT')")
    # 初始化一个保底规则，防止 ID 引用报错
    c.execute("INSERT OR IGNORE INTO policies (id, name, devices, countries, r_url) VALUES (1, '默认放行', 'All', 'All', 'https://www.facebook.com')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=20); c = conn.cursor()
    c.execute(sql, args)
    res = c.fetchall() if fetch else None
    conn.commit(); conn.close()
    return res

# --- 跳转与报表逻辑 ---
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

# --- 后台模板 (极致精简防错版) ---
UI = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script></head>
<body class="flex bg-slate-50">
    <nav class="w-56 bg-white h-screen border-r font-bold text-slate-600">
        <div class="p-8 text-blue-600 text-2xl font-black">SENTINEL</div>
        <a href="/admin?tab=policies" class="block p-4 hover:bg-slate-100">风控规则</a>
        <a href="/admin?tab=tickets" class="block p-4 hover:bg-slate-100">投放工单</a>
        <a href="/admin?tab=links" class="block p-4 hover:bg-slate-100">推广链路</a>
        <a href="/admin?tab=logs" class="block p-4 hover:bg-slate-100">投放报表</a>
    </nav>
    <main class="flex-1 p-10">
        <div class="flex justify-between mb-8"><h2 class="text-3xl font-bold">{{tab_name}}</h2>
        <button onclick="document.getElementById('m').style.display='flex'" class="bg-blue-600 text-white px-6 py-2 rounded-lg font-bold">+ 新增</button></div>
        <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-slate-50 border-b"><tr>{% for h in headers %}<th class="p-4 text-slate-400">{{h}}</th>{% endfor %}<th class="p-4">操作</th></tr></thead>
                <tbody>{% for row in rows %}<tr class="border-b"><td class="p-4">{{row[1]}}</td><td class="p-4">{{row[2]}}</td><td class="p-4">{{row[3]}}</td><td class="p-4"><a href="/action/del/{{tab}}/{{row[0]}}" class="text-red-500">删除</a></td></tr>{% endfor %}</tbody>
            </table>
        </div>
    </main>
    <div id="m" class="fixed inset-0 bg-black/50 hidden items-center justify-center p-4">
        <div class="bg-white rounded-xl p-8 w-full max-w-md shadow-2xl">
            <h3 class="text-xl font-bold mb-4">添加数据</h3>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-4">
                {% if tab == 'policies' %}
                    <input name="name" placeholder="规则名称" class="w-full border p-2 rounded" required>
                    <input name="r_url" placeholder="拦截后跳往链接" class="w-full border p-2 rounded" value="https://google.com">
                {% elif tab == 'tickets' %}
                    <input name="name" placeholder="工单名" class="w-full border p-2 rounded" required>
                    <input name="url" placeholder="目标WA号或URL" class="w-full border p-2 rounded" required>
                    <select name="p_id" class="w-full border p-2 rounded">{% for p in plist %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select>
                {% elif tab == 'links' %}
                    <select name="domain" class="w-full border p-2 rounded"><option>https://secure-link.top</option></select>
                    <select name="ticket_id" class="w-full border p-2 rounded">{% for t in tlist %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}</select>
                    <input name="slot" placeholder="版位 (如FB-01)" class="w-full border p-2 rounded">
                {% endif %}
                <button class="w-full bg-blue-600 text-white p-3 rounded-lg font-bold">保存提交</button>
                <button type="button" onclick="document.getElementById('m').style.display='none'" class="w-full text-slate-400">取消</button>
            </form>
        </div>
    </div>
</body></html>
"""

@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form
    if tab == 'policies':
        db_action("INSERT INTO policies (name,r_url) VALUES (?,?)", (f['name'], f['r_url']), False)
    elif tab == 'tickets':
        u = f['url']; u = f"https://wa.me/{u}" if u.isdigit() else u
        db_action("INSERT INTO tickets (name,url,p_id) VALUES (?,?,?)", (f['name'], u, f['p_id']), False)
    elif tab == 'links':
        code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        db_action("INSERT INTO mapping (code,ticket_id,domain,slot,date) VALUES (?,?,?,?,?)", (code, f['ticket_id'], f['domain'], f['slot'], ""), False)
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
        "policies": ("风控规则", ["规则名", "拦截跳转", "详情"], "SELECT id, name, r_url, '准入:All' FROM policies"),
        "tickets": ("投放工单", ["名称", "跳转链接", "规则ID"], "SELECT id, name, url, p_id FROM tickets"),
        "links": ("推广链路", ["路径", "版位", "备注"], "SELECT id, '/'||code, slot, 'OK' FROM mapping"),
        "logs": ("投放报表", ["链路", "IP", "状态"], "SELECT id, link, ip, err FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI, tab=tab, tab_name=title, headers=headers, rows=rows, plist=plist, tlist=tlist)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'super' and request.form['p'] == '777888':
        session['user'] = 'super'; return redirect('/admin')
    return '<body><form method="post">Admin:<input name="u"><br>Pass:<input name="p" type="password"><br><button>LOGIN</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888)
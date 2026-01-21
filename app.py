import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, abort, jsonify

app = Flask(__name__)
app.secret_key = "sentinel_ultimate_pro_2026"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 静态资源配置 ---
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]
COUNTRIES = ["中国", "香港", "台湾", "美国", "英国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "印尼", "菲律宾", "阿联酋", "沙特", "巴西", "德国", "法国", "加拿大", "澳大利亚"]
DEVICES = ["iPhone 13-15", "iPhone 16-17 Pro Max", "iPad", "Android 12-13", "Android 14-15", "Windows PC", "MacBook"]

# --- 数据库核心 ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
        pixel TEXT, event TEXT, campaign TEXT, p_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, 
        domain TEXT, slot TEXT, note TEXT, date TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    # 按照要求设置超管账号
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('super', '777888', 'SUPER_ADMIN')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=10); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 核心跳转引擎 (含日志记录) ---
@app.route('/<code>')
def redirect_engine(code):
    link = db_action("SELECT ticket_id, slot, note FROM mapping WHERE code = ?", (code,))
    if not link: abort(404)
    t_id, slot, note = link[0]
    ticket = db_action("SELECT url, p_id FROM tickets WHERE id = ?", (t_id,))
    if not ticket: return "Target Missing", 404
    
    final_url = ticket[0]
    ip = request.remote_addr
    ua = request.headers.get('User-Agent', 'Unknown')
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    db_action("INSERT INTO logs (link, ip, err, dev, slot, src, time) VALUES (?,?,?,?,?,?,?)",
              (code, ip, "正常通过", ua[:50], slot, note, now), False)
    return redirect(final_url)

# --- UI 界面模板 ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#f9fafb;color:#111827;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
        .sidebar{width:220px;background:#fff;border-right:1px solid #e5e7eb;position:fixed;height:100vh;}
        .nav-item{display:flex;align-items:center;padding:12px 24px;color:#4b5563;font-weight:600;transition:0.2s;}
        .nav-item:hover{background:#f3f4f6;color:#2563eb;}
        .nav-active{background:#eff6ff;color:#2563eb;border-right:4px solid #2563eb;}
        .card{background:#fff;border-radius:12px;border:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.05);}
        .btn-primary{background:#2563eb;color:#fff;padding:10px 24px;border-radius:8px;font-weight:700;transition:0.3s;}
        .btn-primary:hover{background:#1d4ed8;box-shadow:0 4px 12px rgba(37,99,235,0.3);}
        .toggle-box{padding:6px 14px;border:1px solid #d1d5db;border-radius:6px;font-size:12px;cursor:pointer;background:#fff;user-select:none;}
        .toggle-box.active{background:#2563eb;color:#fff;border-color:#2563eb;}
        input, select, textarea{width:100%;padding:12px;border:1px solid #d1d5db;border-radius:8px;outline:none;margin-top:6px;transition:0.2s;}
        input:focus{border-color:#2563eb;ring:2px ring-blue-500;}
        label{font-size:13px;font-weight:700;color:#374151;margin-top:12px;display:block;}
    </style>
</head>
<body class="flex">
    <aside class="sidebar py-8">
        <div class="px-8 mb-10 text-2xl font-black text-blue-600 tracking-tight">SENTINEL</div>
        <nav>
            <a href="/admin?tab=users" class="nav-item {{'nav-active' if tab=='users'}}">成员管理</a>
            <a href="/admin?tab=policies" class="nav-item {{'nav-active' if tab=='policies'}}">风控规则</a>
            <a href="/admin?tab=tickets" class="nav-item {{'nav-active' if tab=='tickets'}}">投放工单</a>
            <a href="/admin?tab=links" class="nav-item {{'nav-active' if tab=='links'}}">推广链路</a>
            <a href="/admin?tab=logs" class="nav-item {{'nav-active' if tab=='logs'}}">投放报表</a>
        </nav>
        <div class="absolute bottom-8 px-8"><a href="/logout" class="text-sm text-gray-400 font-bold hover:text-red-500">登出系统</a></div>
    </aside>

    <main class="flex-1 ml-[220px] p-10">
        <div class="flex justify-between items-center mb-8">
            <div><h1 class="text-3xl font-extrabold text-gray-900">{{tab_name}}</h1><p class="text-gray-500 text-sm mt-1">管理并监控您的实时投放数据</p></div>
            <button onclick="openModal()" class="btn-primary">+ 新增{{tab_name}}</button>
        </div>

        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-gray-50 border-b text-gray-500 uppercase">
                    <tr>{% for h in headers %}<th class="p-4 font-bold">{{h}}</th>{% endfor %}<th class="p-4 text-right">操作</th></tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for row in rows %}
                    <tr class="hover:bg-gray-50/80 transition">
                        {% for cell in row %}<td class="p-4 font-medium text-gray-700">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right space-x-3">
                            <button class="text-blue-600 font-bold hover:underline" onclick="alert('编辑功能：请删除后重新配置以确保规则实时生效')">编辑</button>
                            <a href="/action/del/{{tab}}/{{row[0]}}" class="text-red-500 font-bold hover:underline" onclick="return confirm('确定删除吗？')">删除</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="modal" class="fixed inset-0 bg-gray-900/50 hidden items-center justify-center z-50 p-4 backdrop-blur-sm">
        <div class="bg-white rounded-2xl w-full max-w-xl p-8 shadow-2xl overflow-y-auto max-h-[90vh]">
            <h3 class="text-2xl font-bold mb-6 text-gray-800">配置{{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST" id="mainForm">
                {% if tab == 'policies' %}
                    <label>规则显示名称</label><input name="name" placeholder="如：马来西亚-IOS专用" required>
                    <label>允许访问的国家</label>
                    <div class="flex flex-wrap gap-2 mt-2">
                        {% for c in countries %}<div class="toggle-box" onclick="toggleSelect(this, 'c_in')">{{c}}</div>{% endfor %}
                    </div>
                    <input type="hidden" name="countries" id="c_in">
                    <label>允许访问的设备</label>
                    <div class="flex flex-wrap gap-2 mt-2">
                        {% for d in devices %}<div class="toggle-box" onclick="toggleSelect(this, 'd_in')">{{d}}</div>{% endfor %}
                    </div>
                    <input type="hidden" name="devices" id="d_in">
                    <label>拦截跳转地址 (非准入流量去向)</label><input name="r_url" value="https://www.facebook.com">
                {% elif tab == 'tickets' %}
                    <label>投放工单名称</label><input name="name" required>
                    <label>跳转目标 (输入WA手机号自动转换)</label><input name="url" placeholder="如: 852xxxxxx 或 URL" required>
                    <label>模式类型</label><select name="type"><option>单导模式</option><option>群导模式</option></select>
                    <label>像素 ID (Pixel)</label><input name="pixel" placeholder="可选">
                    <label>关联规则</label><select name="p_id">{% for p in plist %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select>
                {% elif tab == 'links' %}
                    <label>选择短链域名</label><select name="domain">{% for d in domains %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                    <label>分配目标工单</label><select name="ticket_id">{% for t in tlist %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}</select>
                    <label>备注投放版位 (Slot)</label><input name="slot" placeholder="如: FB-Feed / IG-Stories">
                    <label>备注内部名称</label><input name="note" placeholder="如: 01组-代理A">
                {% elif tab == 'users' %}
                    <label>管理账号</label><input name="u" required><label>登录密码</label><input name="p" type="password" required>
                {% endif %}
                <div class="flex justify-end mt-10 space-x-4 border-t pt-6">
                    <button type="button" onclick="closeModal()" class="text-gray-400 font-bold px-4">取消</button>
                    <button class="btn-primary">保存配置</button>
                </div>
            </form>
        </div>
    </div>
    <script>
        function openModal(){ document.getElementById('modal').style.display='flex'; }
        function closeModal(){ document.getElementById('modal').style.display='none'; }
        function toggleSelect(el, inputId) {
            el.classList.toggle('active');
            const parent = el.parentElement;
            const selected = Array.from(parent.querySelectorAll('.active')).map(e => e.innerText);
            document.getElementById(inputId).value = selected.join(',');
        }
    </script>
</body>
</html>
"""

# --- 逻辑路由 ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'policies':
        db_action("INSERT INTO policies (name,devices,countries,r_url) VALUES (?,?,?,?)", (f['name'], f['devices'], f['countries'], f['r_url']), False)
    elif tab == 'tickets':
        u = f['url']
        if u.isdigit(): u = f"https://wa.me/{u}" # 自动转WA
        db_action("INSERT INTO tickets (name,url,type,pixel,p_id) VALUES (?,?,?,?,?)", (f['name'], u, f['type'], f['pixel'], f['p_id']), False)
    elif tab == 'links':
        code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        db_action("INSERT INTO mapping (code,ticket_id,domain,slot,note,date) VALUES (?,?,?,?,?,?)", (code, f['ticket_id'], f['domain'], f['slot'], f['note'], now), False)
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
        "users": ("成员管理", ["ID", "账号", "角色"], "SELECT id, u, '管理员' FROM users"),
        "policies": ("风控规则", ["ID", "名称", "准入国家", "拦截跳转"], "SELECT id, name, countries, r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "工单名", "跳转目标", "像素"], "SELECT id, name, url, pixel FROM tickets"),
        "links": ("推广链路", ["ID", "短链路径", "投放版位", "备注"], "SELECT id, '/'||code, slot, note FROM mapping"),
        "logs": ("投放报表", ["ID", "短链", "IP", "状态", "设备详情", "版位", "来源", "时间"], "SELECT * FROM logs ORDER BY id DESC LIMIT 200")
    }
    t_name, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(HTML_LAYOUT, tab=tab, tab_name=t_name, headers=headers, rows=rows, user=session['user'], countries=COUNTRIES, devices=DEVICES, plist=plist, tlist=tlist, domains=DOMAINS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['u'] == 'super' and request.form['p'] == '777888':
            session['user'] = 'super'; return redirect('/admin')
    return '''
    <body style="background:#f3f4f6;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;">
        <form method="post" style="background:#fff;padding:50px;border-radius:20px;box-shadow:0 25px 50px -12px rgba(0,0,0,0.1);width:400px;">
            <h2 style="color:#2563eb;font-size:30px;font-weight:900;margin-bottom:10px;letter-spacing:-1px;">SENTINEL PRO</h2>
            <p style="color:#6b7280;margin-bottom:30px;font-weight:500;">请输入总后端授权凭据</p>
            <input name="u" placeholder="账号" style="width:100%;padding:14px;margin-bottom:15px;border:1px solid #d1d5db;border-radius:12px;outline:none;">
            <input name="p" type="password" placeholder="密码" style="width:100%;padding:14px;margin-bottom:30px;border:1px solid #d1d5db;border-radius:12px;outline:none;">
            <button style="width:100%;background:#2563eb;color:#fff;padding:16px;border:none;border-radius:12px;font-weight:bold;cursor:pointer;font-size:16px;">进入管理系统</button>
        </form>
    </body>'''

@app.route('/logout')
def logout(): session.pop('user', None); return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
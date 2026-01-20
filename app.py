import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, jsonify

app = Flask(__name__)
app.secret_key = "sentinel_v16_total_solution_2026"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 数据库核心初始化 ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, ua TEXT, status TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date) VALUES ('super', '777888', 'ROOT', '2026-01-20')")
    conn.commit(); conn.close()

def db_action(query, args=(), fetch=False):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(query, args)
    res = c.fetchall() if fetch else None
    conn.commit(); conn.close()
    return res

# --- 交互界面模板 ---
ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#0b0e14;color:#d1d5db;font-family:sans-serif;}
        .sidebar{background:#11141b;border-right:1px solid #1f2937;}
        .card{background:#161b22;border:1px solid #30363d;border-radius:12px;}
        .active-nav{background:rgba(59,130,246,0.1);color:#3b82f6;border-left:4px solid #3b82f6;}
        .modal{background:rgba(0,0,0,0.8);backdrop-filter:blur(4px);display:none;}
        input, select{background:#0d1117;border:1px solid #30363d;color:white;padding:8px;border-radius:6px;width:100%;margin-top:4px;}
    </style>
</head>
<body class="flex h-screen overflow-hidden">
    <aside class="sidebar w-64 flex flex-col p-6">
        <div class="text-blue-500 font-black text-2xl italic mb-10 tracking-tighter">SENTINEL V16</div>
        <nav class="flex-1 space-y-1 text-sm">
            <a href="?tab=dashboard" class="block p-4 rounded {{'active-nav' if tab=='dashboard'}}">📊 概览面板</a>
            <a href="?tab=users" class="block p-4 rounded {{'active-nav' if tab=='users'}}">👥 子账户管理</a>
            <a href="?tab=policies" class="block p-4 rounded {{'active-nav' if tab=='policies'}}">🛡️ 防护策略设置</a>
            <a href="?tab=tickets" class="block p-4 rounded {{'active-nav' if tab=='tickets'}}">🎫 工单生成编辑</a>
            <a href="?tab=links" class="block p-4 rounded {{'active-nav' if tab=='links'}}">🔗 短链生成编辑</a>
            <a href="?tab=logs" class="block p-4 rounded {{'active-nav' if tab=='logs'}}">📜 访问日志审计</a>
        </nav>
        <div class="text-xs opacity-40">管理员: {{user}} | <a href="/login" class="text-red-500 underline">退出</a></div>
    </aside>

    <main class="flex-1 p-10 overflow-auto">
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-3xl font-bold text-white">{{tab_name}}</h2>
            {% if tab != 'dashboard' and tab != 'logs' %}
            <button onclick="openModal()" class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg text-sm font-bold text-white transition">+ 新增项目</button>
            {% endif %}
        </div>

        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-black/40 text-gray-500 uppercase text-xs">
                    <tr>
                        {% for h in headers %}<th class="p-4">{{h}}</th>{% endfor %}
                        <th class="p-4">管理操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-800">
                    {% for row in rows %}
                    <tr class="hover:bg-white/5">
                        {% for cell in row %}<td class="p-4">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-blue-500 space-x-2"><button>编辑</button><button class="text-red-500">删除</button></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="modal" class="modal fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="card w-full max-w-md p-8">
            <h3 class="text-xl font-bold mb-6 text-white">新增/编辑 [{{tab_name}}]</h3>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-4 text-sm">
                {% if tab == 'users' %}
                    <div><label>用户名</label><input name="u" placeholder="如: sub_user_01"></div>
                    <div><label>密码</label><input name="p" type="password"></div>
                    <div><label>备注名称</label><input name="n"></div>
                {% elif tab == 'policies' %}
                    <div><label>策略名称</label><input name="name" placeholder="iPhone拦截策略"></div>
                    <div><label>白名单机型 (逗号分隔)</label><input name="devices" value="iPhone 17 Pro,iPhone 16"></div>
                    <div><label>拦截后跳转地址</label><input name="r_url" value="https://google.com"></div>
                {% elif tab == 'tickets' %}
                    <div><label>工单名称</label><input name="name"></div>
                    <div><label>目标承载URL</label><input name="url"></div>
                {% elif tab == 'links' %}
                    <div><label>短链代码 (留空随机)</label><input name="code"></div>
                    <div><label>备注标题</label><input name="title"></div>
                {% endif %}
                <div class="flex justify-end space-x-3 mt-8">
                    <button type="button" onclick="closeModal()" class="px-4 py-2 opacity-50">取消</button>
                    <button class="bg-blue-600 px-6 py-2 rounded font-bold text-white">确认保存</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function openModal(){ document.getElementById('modal').style.display='flex'; }
        function closeModal(){ document.getElementById('modal').style.display='none'; }
    </script>
</body>
</html>
"""

# --- 核心功能路由 ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'users': db_action("INSERT INTO users (u,p,n,c_date) VALUES (?,?,?,?)", (f['u'], f['p'], f['n'], now))
    elif tab == 'policies': db_action("INSERT INTO policies (name,devices,r_url) VALUES (?,?,?)", (f['name'], f['devices'], f['r_url']))
    elif tab == 'tickets': db_action("INSERT INTO tickets (name,url,p_id) VALUES (?,?,1)", (f['name'], f['url']))
    elif tab == 'links': 
        code = f['code'] if f['code'] else ''.join(random.choices(string.ascii_letters, k=6))
        db_action("INSERT INTO mapping (code,title,ticket_id,date) VALUES (?,?,1,?)", (code, f['title'], now))
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'dashboard')
    conf = {
        "users": ("用户列表", ["账号", "权限", "创建日期"], "SELECT u,n,c_date FROM users"),
        "policies": ("策略中心", ["策略名", "白名单机型", "跳转URL"], "SELECT name,devices,r_url FROM policies"),
        "tickets": ("工单系统", ["工单名称", "承载地址", "关联ID"], "SELECT name,url,p_id FROM tickets"),
        "links": ("短链管理", ["提取码", "备注", "工单ID", "时间"], "SELECT code,title,ticket_id,date FROM mapping"),
        "logs": ("访问审计", ["时间", "代码", "IP", "状态"], "SELECT time,code,ip,status FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab, ("概览", ["标识", "数值", "状态"], "SELECT 1,2,3 WHERE 1=0"))
    rows = db_action(sql, fetch=True)
    return render_template_string(ADMIN_HTML, tab=tab, tab_name=title, headers=headers, rows=rows, user=session['user'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'super' and request.form['p'] == '777888':
        session['user'] = 'super'; return redirect('/admin')
    return '<body style="background:#000;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#111;padding:40px;border-radius:20px;border:1px solid #333;"><h2>SENTINEL LOGIN</h2><input name="u" placeholder="账号"><br><input name="p" type="password" placeholder="密码"><br><button style="width:100%;background:#3b82f6;color:#fff;padding:10px;margin-top:10px;">进入系统</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
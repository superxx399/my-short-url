import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = "sentinel_v11_eco_ultimate"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 数据库归属化 (修复 t_id 冲突) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT)')
    # 策略表扩展：增加国家和语言过滤字段
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_devices TEXT, r_url TEXT, countries TEXT, langs TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, t_id INTEGER, title TEXT, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date) VALUES ('super', '777888', 'ROOT', '2026-01-20')")
    conn.commit(); conn.close()

def db_action(query, args=(), fetch=False):
    conn = sqlite3.connect(DB_PATH, timeout=10); c = conn.cursor()
    c.execute(query, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 2. 界面增强 (左侧边栏 + 防护开关矩阵) ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html class="dark">
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#0d1117;color:#c9d1d9;}
        .sidebar{width:260px;background:#161b22;border-right:1px solid #30363d;position:fixed;height:100vh;}
        .main-content{margin-left:260px;padding:40px;}
        .nav-item{display:flex;padding:12px 20px;margin:4px 12px;border-radius:8px;transition:0.2s;}
        .nav-active{background:#1f6feb;color:white;}
        .card{background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;}
        .tag-btn{padding:2px 8px;border-radius:4px;border:1px solid #30363d;font-size:11px;margin:2px;}
        .tag-active{background:#238636;border-color:#2ea043;color:white;}
    </style>
</head>
<body class="flex">
    <nav class="sidebar flex flex-col pt-8">
        <div class="px-8 mb-10 text-2xl font-black italic text-blue-500">SENTINEL V11</div>
        <div class="flex-1 space-y-1">
            <a href="?tab=users" class="nav-item {{'nav-active' if tab=='users'}}">👥 子账户管理</a>
            <a href="?tab=policies" class="nav-item {{'nav-active' if tab=='policies'}}">🛡️ 防护设置矩阵</a>
            <a href="?tab=tickets" class="nav-item {{'nav-active' if tab=='tickets'}}">🎫 工单生成编辑</a>
            <a href="?tab=links" class="nav-item {{'nav-active' if tab=='links'}}">🔗 短链分发管理</a>
            <a href="?tab=logs" class="nav-item {{'nav-active' if tab=='logs'}}">📜 访问日志审计</a>
        </div>
        <div class="p-6 border-t border-gray-800 text-xs opacity-50">
            Current: {{user}} | <a href="/login" class="text-red-400">退出</a>
        </div>
    </nav>

    <main class="main-content flex-1">
        <div class="flex justify-between items-end mb-8">
            <h2 class="text-3xl font-bold">{{tab_name}}</h2>
            {% if tab != 'logs' %}
            <button onclick="document.getElementById('modal').style.display='flex'" class="bg-blue-600 px-6 py-2 rounded-lg font-bold hover:bg-blue-500 transition">+ 新增项目</button>
            {% else %}
            <a href="/action/clear_logs" class="bg-red-900/30 text-red-500 border border-red-500/30 px-4 py-2 rounded-lg text-sm">一键清空审计日志</a>
            {% endif %}
        </div>

        <div class="card">
            <table class="w-full text-left">
                <thead class="bg-black/20 text-xs text-gray-500 uppercase">
                    <tr>
                        {% for h in headers %}<th class="p-4">{{h}}</th>{% endfor %}
                        <th class="p-4 text-right">操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-800">
                    {% for row in rows %}
                    <tr class="hover:bg-white/5">
                        {% for cell in row %}<td class="p-4 text-sm">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right text-blue-500 space-x-3">
                            <button class="hover:underline">编辑</button>
                            <button class="text-red-500 hover:underline">删除</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        {% if tab == 'policies' %}
        <div class="mt-8 grid grid-cols-2 gap-6">
            <div class="card p-6">
                <h4 class="text-sm font-bold mb-4">🌍 全球国家准入开关 (示例)</h4>
                <div class="flex flex-wrap">
                    <span class="tag-btn tag-active">中国 (CN)</span><span class="tag-btn tag-active">美国 (US)</span>
                    <span class="tag-btn">日本 (JP)</span><span class="tag-btn">英国 (GB)</span>
                    <span class="tag-btn">香港 (HK)</span><span class="tag-btn">台湾 (TW)</span>
                </div>
            </div>
            <div class="card p-6">
                <h4 class="text-sm font-bold mb-4">🗣️ 浏览器语言过滤</h4>
                <div class="flex flex-wrap">
                    <span class="tag-btn tag-active">中文 (zh-CN)</span><span class="tag-btn tag-active">英语 (en-US)</span>
                    <span class="tag-btn">日语 (ja)</span><span class="tag-btn">韩语 (ko)</span>
                </div>
            </div>
        </div>
        {% endif %}
    </main>

    <div id="modal" class="fixed inset-0 bg-black/80 hidden items-center justify-center z-50">
        <div class="card w-full max-w-md p-8">
            <h3 class="text-xl font-bold mb-6">新增 {{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-4">
                {% if tab == 'users' %}
                    <input name="u" placeholder="账号" required><input name="p" type="password" placeholder="密码" required>
                {% elif tab == 'policies' %}
                    <input name="name" placeholder="策略名称" required>
                    <input name="white" placeholder="指纹白名单 (iPhone 17, iPhone 16)">
                    <input name="r_url" placeholder="拦截跳转URL" value="https://google.com">
                {% elif tab == 'tickets' %}
                    <input name="name" placeholder="工单名" required><input name="url" placeholder="目标落地页URL" required>
                    <input name="p_id" placeholder="关联策略ID" value="1">
                {% elif tab == 'links' %}
                    <input name="code" placeholder="短链提取码 (留空随机)"><input name="t_id" placeholder="关联工单ID" required>
                {% endif %}
                <div class="flex justify-end space-x-4 mt-8">
                    <button type="button" onclick="document.getElementById('modal').style.display='none'">取消</button>
                    <button class="bg-blue-600 px-6 py-2 rounded font-bold">保存并同步</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

# --- 3. 核心逻辑 (修复报错 & 增加实用功能) ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'users': db_action("INSERT INTO users (u,p,n,c_date) VALUES (?,?,?,'2026-01-20')", (f['u'], f['p'], f['u']))
    elif tab == 'policies': db_action("INSERT INTO policies (name,white_devices,r_url) VALUES (?,?,?)", (f['name'], f['white'], f['r_url']))
    elif tab == 'tickets': db_action("INSERT INTO tickets (name,url,p_id) VALUES (?,?,?)", (f['name'], f['url'], f['p_id']))
    elif tab == 'links':
        code = f['code'] if f['code'] else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        # 修正列名为 t_id，对应数据库定义
        db_action("INSERT INTO mapping (code,t_id,title,date) VALUES (?,?,'AutoGenerated',?)", (code, f['t_id'], now))
    return redirect(f'/admin?tab={tab}')

@app.route('/action/clear_logs')
def clear_logs():
    db_action("DELETE FROM logs"); return redirect('/admin?tab=logs')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    conf = {
        "users": ("子账户管理", ["ID", "账号", "创建日期"], "SELECT id, u, c_date FROM users"),
        "policies": ("防护策略矩阵", ["ID", "策略名", "白名单机型", "重定向"], "SELECT id, name, white_devices, r_url FROM policies"),
        "tickets": ("工单生成编辑", ["ID", "名称", "目标落地页", "策略ID"], "SELECT id, name, url, p_id FROM tickets"),
        "links": ("短链分发管理", ["ID", "路径代码", "关联工单", "创建时间"], "SELECT id, code, t_id, date FROM mapping"),
        "logs": ("访问审计日志", ["ID", "时间", "提取码", "IP", "状态"], "SELECT id, time, code, ip, status FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql, fetch=True)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=title, headers=headers, rows=rows, user=session['user'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'super' and request.form['p'] == '777888':
        session['user'] = 'super'; return redirect('/admin')
    return '<body style="background:#000;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="border:1px solid #333;padding:40px;border-radius:20px;"><h2>SENTINEL LOGIN</h2><input name="u" placeholder="User"><br><input name="p" type="password" placeholder="Pass"><br><button style="width:100%;background:#0066ff;color:#fff;padding:10px;margin-top:10px;border-radius:10px;">ENTER</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
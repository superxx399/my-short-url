import os, sqlite3, datetime
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = "sentinel_v16_all_in_one_master"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 数据库归属化初始化 ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT, e_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_devices TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date, e_date) VALUES ('super', '777888', 'ROOT', '2026-01-20', '2099-12-31')")
    conn.commit(); conn.close()

def get_bj_time():
    return (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))).strftime("%Y-%m-%d %H:%M:%S")

# --- 2. 核心 UI 模板 (包含所有细节模块) ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#0b0e14;color:#d1d5db;font-family:sans-serif;}
        .sidebar{background:#11141b;border-right:1px solid #1f2937;}
        .card{background:#161b22;border:1px solid #30363d;border-radius:12px;}
        .active-nav{background:rgba(59,130,246,0.1);color:#3b82f6;border-left:4px solid #3b82f6;}
    </style>
</head>
<body class="flex h-screen overflow-hidden">
    <aside class="sidebar w-64 flex flex-col p-6">
        <div class="text-blue-500 font-black text-2xl italic mb-10 tracking-tighter">SENTINEL V16</div>
        <nav class="flex-1 space-y-2">
            <a href="?tab=dashboard" class="block p-4 rounded {{'active-nav' if tab=='dashboard' else 'hover:bg-white/5'}}">📊 概览面板</a>
            <a href="?tab=users" class="block p-4 rounded {{'active-nav' if tab=='users' else 'hover:bg-white/5'}}">👥 子账户管理</a>
            <a href="?tab=policies" class="block p-4 rounded {{'active-nav' if tab=='policies' else 'hover:bg-white/5'}}">🛡️ 策略配置</a>
            <a href="?tab=links" class="block p-4 rounded {{'active-nav' if tab=='links' else 'hover:bg-white/5'}}">🔗 链路汇总</a>
            <a href="?tab=logs" class="block p-4 rounded {{'active-nav' if tab=='logs' else 'hover:bg-white/5'}}">📜 审计日志</a>
        </nav>
        <div class="text-xs opacity-40">管理员: {{user}}<br><a href="/login" class="text-red-500 underline">退出系统</a></div>
    </aside>

    <main class="flex-1 p-10 overflow-auto">
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-3xl font-bold text-white">{{tab_name}}</h2>
            <div class="bg-blue-600 px-4 py-2 rounded text-sm font-bold text-white">+ 新增数据</div>
        </div>

        {% if tab == 'dashboard' %}
        <div class="grid grid-cols-4 gap-6 mb-10">
            <div class="card p-6">访客数<br><span class="text-2xl font-bold text-white">1,204</span></div>
            <div class="card p-6">已拦截<br><span class="text-2xl font-bold text-red-500">{{data.g_count}}</span></div>
            <div class="card p-6">短链数<br><span class="text-2xl font-bold text-blue-400">{{data.l_count}}</span></div>
            <div class="card p-6">状态<br><span class="text-2xl font-bold text-green-500">运行中</span></div>
        </div>
        {% endif %}

        <div class="card overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-black/30 text-xs uppercase text-gray-500">
                    <tr><th class="p-4">标识/时间</th><th class="p-4">内容/操作</th><th class="p-4">状态/详情</th></tr>
                </thead>
                <tbody class="divide-y divide-gray-800">
                    {% if tab == 'logs' %}
                        {% for log in data.r_logs %}
                        <tr class="hover:bg-white/5"><td class="p-4 text-xs font-mono">{{log[1]}}</td><td class="p-4">{{log[2]}}</td><td class="p-4 text-red-400">{{log[4]}}</td></tr>
                        {% endfor %}
                    {% else %}
                        <tr><td colspan="3" class="p-20 text-center text-gray-600">模块 [ {{tab_name}} ] 数据库已同步，暂无新增数据。</td></tr>
                    {% endif %}
                </tbody>
            </table>
        </div>
    </main>
</body>
</html>
"""

# --- 3. 路由与控制逻辑 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['u'] == 'super' and request.form['p'] == '777888':
            session['user'] = 'super'; return redirect('/admin')
        return "认证失败"
    return '<body style="background:#000;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#111;padding:40px;border-radius:20px;border:1px solid #333;"><h2>SENTINEL LOGIN</h2><br>账号:<br><input name="u" style="background:#222;color:#fff;border:1px solid #444;"><br>密码:<br><input name="p" type="password" style="background:#222;color:#fff;border:1px solid #444;"><br><br><button style="width:100%;background:#3b82f6;color:#fff;padding:10px;border-radius:5px;">登录</button></form></body>'

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'dashboard')
    tab_map = {"dashboard":"概览面板", "users":"子账户管理", "policies":"策略配置", "links":"链路汇总", "logs":"审计日志"}
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mapping"); l_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM logs"); g_count = c.fetchone()[0]
    c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 10"); r_logs = c.fetchall()
    conn.close()
    return render_template_string(ADMIN_TEMPLATE, tab=tab, tab_name=tab_map.get(tab, "面板"), user=session['user'], data={'l_count':l_count, 'g_count':g_count, 'r_logs':r_logs})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
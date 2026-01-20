import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v16_pro_master_key"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 机型指纹库 (集成 iPhone 17 & 旗舰安卓) ---
DEVICE_DB = {
    "Apple": ["iPhone 17 Pro Max", "iPhone 17 Pro", "iPhone 16 Pro Max", "iPhone 15 Pro", "iPad Pro"],
    "Huawei": ["Mate 70 Pro+", "Mate 60 RS", "Pura 70 Ultra", "Mate X5"],
    "Global": ["Samsung S25 Ultra", "Xiaomi 15 Ultra", "Google Pixel 9"]
}

def get_bj_time():
    return (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))).strftime("%Y-%m-%d %H:%M:%S")

# --- 2. 数据库自动初始化 (所有功能表) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT, e_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_devices TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    # 初始化超级管理员
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date, e_date) VALUES ('super', '777888', 'ROOT', ?, '2099-12-31')", (get_bj_time(),))
    conn.commit(); conn.close()

# --- 3. 核心拦截与路由转发 ---
@app.route('/<code>')
def gateway(code):
    if code in ['admin', 'login', 'api']: return redirect('/admin')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT t.url, s.white_devices, s.r_url FROM mapping m JOIN tickets t ON m.ticket_id = t.id JOIN policies s ON t.p_id = s.id WHERE m.code = ?", (code,))
    res = c.fetchone()
    if not res: return "404 LINK EXPIRED", 404
    
    target, w_dev, r_url = res
    ua = request.user_agent.string.lower()
    is_blocked = 0; reason = "验证通过"
    if w_dev and not any(d.lower() in ua for d in w_dev.split(',')): 
        is_blocked, reason = 1, "设备指纹拦截"
    
    c.execute("INSERT INTO logs (time, code, ip, status, reason) VALUES (?,?,?,?,?)", (get_bj_time(), code, request.remote_addr, "拦截" if is_blocked else "成功", reason))
    conn.commit(); conn.close()
    return redirect(r_url if is_blocked else target)

# --- 4. 统一 UI 模板 (包含左侧菜单) ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Sentinel V16 Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #0b0e14; color: #d1d5db; }
        .sidebar { background: #11141b; border-right: 1px solid #1f2937; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; }
        .nav-item { transition: 0.2s; border-left: 4px solid transparent; }
        .nav-item:hover { background: rgba(255,255,255,0.05); }
        .nav-active { background: rgba(59, 130, 246, 0.1); color: #3b82f6; border-left: 4px solid #3b82f6; }
    </style>
</head>
<body class="flex h-screen overflow-hidden">
    <aside class="sidebar w-64 flex flex-col">
        <div class="p-8 text-blue-500 font-black text-2xl italic tracking-tighter">SENTINEL V16</div>
        <nav class="flex-1 px-4 space-y-2">
            <a href="?tab=dashboard" class="nav-item block p-4 rounded {{ 'nav-active' if tab=='dashboard' else '' }}">📊 概览面板</a>
            <a href="?tab=policies" class="nav-item block p-4 rounded {{ 'nav-active' if tab=='policies' else '' }}">🛡️ 拦截策略</a>
            <a href="?tab=tickets" class="nav-item block p-4 rounded {{ 'nav-active' if tab=='tickets' else '' }}">🎫 工单系统</a>
            <a href="?tab=links" class="nav-item block p-4 rounded {{ 'nav-active' if tab=='links' else '' }}">🔗 链路管理</a>
            <a href="?tab=users" class="nav-item block p-4 rounded {{ 'nav-active' if tab=='users' else '' }}">👥 子账户</a>
            <a href="?tab=logs" class="nav-item block p-4 rounded {{ 'nav-active' if tab=='logs' else 'hover:bg-white/5' }}">📜 审计日志</a>
        </nav>
        <div class="p-6 border-t border-gray-800 text-xs italic">
            管理员: {{ user }}<br>北京时间: {{ time }}
            <a href="/login" class="block mt-4 text-red-500 hover:underline">安全退出</a>
        </div>
    </aside>

    <main class="flex-1 p-10 overflow-y-auto">
        <header class="flex justify-between items-center mb-10">
            <h2 class="text-3xl font-bold text-white tracking-tight">{{ tab_name }}</h2>
            <button class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg text-white text-sm font-bold">+ 新增配置</button>
        </header>

        {% if tab == 'dashboard' %}
        <div class="grid grid-cols-3 gap-6">
            <div class="card p-8"><p class="text-gray-500 text-xs uppercase">链路总数</p><p class="text-4xl font-bold mt-2 font-mono">{{ data.l_count }}</p></div>
            <div class="card p-8"><p class="text-gray-500 text-xs uppercase">累计拦截</p><p class="text-4xl font-bold mt-2 text-red-500 font-mono">{{ data.g_count }}</p></div>
            <div class="card p-8"><p class="text-gray-500 text-xs uppercase">系统状态</p><p class="text-4xl font-bold mt-2 text-green-500">RUNNING</p></div>
        </div>
        {% elif tab == 'logs' %}
        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-gray-900/50 text-gray-500"><tr><th class="p-4">时间</th><th class="p-4">代码</th><th class="p-4">IP</th><th class="p-4">状态</th><th class="p-4">原因</th></tr></thead>
                <tbody class="divide-y divide-gray-800">
                {% for log in data.r_logs %}<tr class="hover:bg-white/5"><td class="p-4 text-gray-500">{{ log[1] }}</td><td class="p-4 text-blue-400">{{ log[2] }}</td><td class="p-4">{{ log[3] }}</td><td class="p-4 {{'text-red-500' if log[4]=='拦截' else 'text-green-500'}} font-bold">{{ log[4] }}</td><td class="p-4 italic opacity-50">{{ log[5] }}</td></tr>{% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="card p-20 text-center border-dashed border-2 border-gray-800">
            <div class="text-4xl mb-4 opacity-20">📂</div>
            <p class="text-gray-500">正在同步 [{{ tab_name }}] 模块的数据库实时记录...</p>
        </div>
        {% endif %}
    </main>
</body>
</html>
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT * FROM users WHERE u=? AND p=?", (request.form['u'], request.form['p']))
        if c.fetchone(): session['user'] = request.form['u']; return redirect('/admin')
        return "认证失败"
    return render_template_string('<body style="background:#000;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#111;padding:40px;border-radius:15px;border:1px solid #333;"><h2>SENTINEL LOGIN</h2><br>账号:<br><input name="u" style="background:#222;color:#fff;border:1px solid #444;"><br>密码:<br><input name="p" type="password" style="background:#222;color:#fff;border:1px solid #444;"><br><br><button style="width:100%;background:#0066ff;color:#fff;padding:10px;">进入系统</button></form></body>')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'dashboard')
    tab_map = {"dashboard":"概览面板", "policies":"策略模型", "tickets":"工单分发", "links":"链路汇总", "users":"子账户管理", "logs":"审计日志"}
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mapping"); l_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM logs"); g_count = c.fetchone()[0]
    c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 20"); r_logs = c.fetchall()
    conn.close()

    return render_template_string(ADMIN_TEMPLATE, tab=tab, tab_name=tab_map.get(tab, "面板"), user=session['user'], time=get_bj_time(), data={'l_count':l_count, 'g_count':g_count, 'r_logs':r_logs})

init_db()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=True)
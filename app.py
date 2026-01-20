import os, sqlite3, datetime
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = "sentinel_v16_pro_ultra"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 核心指纹库 (已集成 iPhone 17 系列) ---
DEVICE_DB = ["iPhone 17 Pro Max", "iPhone 17 Pro", "iPhone 16 Pro Max", "Mate 70 Pro+", "S25 Ultra"]

def get_bj_time():
    return (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))).strftime("%Y-%m-%d %H:%M:%S")

# --- 2. 数据库初始化 (保留历史数据) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT, e_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_devices TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date, e_date) VALUES ('super', '777888', 'ROOT', ?, '2099-12-31')", (get_bj_time(),))
    conn.commit(); conn.close()

# --- 3. 拦截网关 ---
@app.route('/<code>')
def gateway(code):
    if code in ['admin', 'login']: return redirect('/admin')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT t.url, s.white_devices, s.r_url FROM mapping m JOIN tickets t ON m.ticket_id = t.id JOIN policies s ON t.p_id = s.id WHERE m.code = ?", (code,))
    res = c.fetchone()
    if not res: return "404 NOT FOUND", 404
    target, w_dev, r_url = res
    ua = request.user_agent.string.lower()
    is_blocked = 0
    if w_dev and not any(d.lower() in ua for d in w_dev.split(',')): is_blocked = 1
    c.execute("INSERT INTO logs (time, code, ip, status, reason) VALUES (?,?,?,?,?)", (get_bj_time(), code, request.remote_addr, "拦截" if is_blocked else "成功", "验证通过"))
    conn.commit(); conn.close()
    return redirect(r_url if is_blocked else target)

# --- 4. 豪华黑金版 UI 模板 ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#0b0e14;color:#d1d5db;}
        .sidebar{background:#11141b;border-right:1px solid #1f2937;}
        .card{background:#161b22;border:1px solid #30363d;border-radius:12px;}
        .nav-active{background:rgba(59,130,246,0.1);color:#3b82f6;border-left:4px solid #3b82f6;}
    </style>
</head>
<body class="flex h-screen">
    <aside class="sidebar w-64 flex flex-col p-6">
        <div class="text-blue-500 font-black text-2xl italic mb-10">SENTINEL V16</div>
        <nav class="flex-1 space-y-2">
            <a href="?tab=dashboard" class="block p-4 rounded {{ 'nav-active' if tab=='dashboard' else 'hover:bg-white/5' }}">📊 概览面板</a>
            <a href="?tab=users" class="block p-4 rounded {{ 'nav-active' if tab=='users' else 'hover:bg-white/5' }}">👥 子账户管理</a>
            <a href="?tab=policies" class="block p-4 rounded {{ 'nav-active' if tab=='policies' else 'hover:bg-white/5' }}">🛡️ 策略配置</a>
            <a href="?tab=links" class="block p-4 rounded {{ 'nav-active' if tab=='links' else 'hover:bg-white/5' }}">🔗 链路汇总</a>
            <a href="?tab=logs" class="block p-4 rounded {{ 'nav-active' if tab=='logs' else 'hover:bg-white/5' }}">📜 审计日志</a>
        </nav>
        <div class="text-xs opacity-50">用户: {{user}} | <a href="/login" class="text-red-500">退出</a></div>
    </aside>
    <main class="flex-1 p-10 overflow-auto">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-3xl font-bold text-white">{{tab_name}}</h2>
            <div class="text-sm bg-blue-600/20 text-blue-400 px-4 py-2 rounded-full border border-blue-600/30">系统状态: 稳定运行</div>
        </div>
        
        <div class="grid grid-cols-3 gap-6 mb-10">
            <div class="card p-8"><p class="text-xs opacity-50 uppercase tracking-widest">拦截总数</p><p class="text-3xl font-bold text-red-500">{{data.g_count}}</p></div>
            <div class="card p-8"><p class="text-xs opacity-50 uppercase tracking-widest">活跃链路</p><p class="text-3xl font-bold text-blue-500">{{data.l_count}}</p></div>
            <div class="card p-8"><p class="text-xs opacity-50 uppercase tracking-widest">子账户总数</p><p class="text-3xl font-bold">1</p></div>
        </div>

        <div class="card p-10 border-dashed border-2 border-gray-800 text-center">
            <div class="text-5xl mb-4">📂</div>
            <p class="text-gray-400">正在实时同步 [ {{tab_name}} ] 数据库模块...</p>
            <p class="text-xs mt-4 opacity-30">Sentinel V16 Pro 2026 Edition</p>
        </div>
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
    return '<h2>Sentinel V16</h2><form method="post">账号:<input name="u"><br>密码:<input name="p" type="password"><br><button>登录</button></form>'

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'dashboard')
    tab_map = {"dashboard":"概览面板", "users":"子账户管理", "policies":"策略模型", "links":"链路汇总", "logs":"审计日志"}
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM mapping"); l_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM logs"); g_count = c.fetchone()[0]
    conn.close()
    return render_template_string(ADMIN_TEMPLATE, tab=tab, tab_name=tab_map.get(tab, "概览"), user=session['user'], data={'l_count':l_count, 'g_count':g_count})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
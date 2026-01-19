import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = 'sentinel_pro_fix_2026'

# --- 1. 数据库初始化 ---
def init_db():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, long_url TEXT, short_code TEXT UNIQUE, owner TEXT, policy_name TEXT, create_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT, ip TEXT, view_time TEXT)''')
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES ('admin', '123456', 'admin')")
    except: pass
    conn.commit()
    conn.close()

# --- 2. UI 模板 (完全修复 f-string 冲突) ---
# 注意：这里去掉了字符串前的 f，改用 Jinja2 原生渲染
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0e14; color: #d1d5db; font-family: sans-serif; }
        .sentinel-card { background: #151921; border: 1px solid #232936; border-radius: 12px; }
        .accent-blue { color: #3b82f6; }
    </style>
</head>
<body class="p-8">
    <div class="max-w-4xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-xl font-bold accent-blue italic text-uppercase tracking-wider">SENTINEL PRO</h2>
            <div class="flex items-center gap-4">
                <span class="text-xs text-slate-500">USER: {{ username }}</span>
                <a href="/logout" class="text-red-500 text-xs border border-red-500/30 px-2 py-1 rounded">安全退出</a>
            </div>
        </div>

        <div class="sentinel-card p-6 mb-8 shadow-2xl">
            <h3 class="text-sm font-bold mb-4 text-slate-400">部署新监控节点</h3>
            <form action="/shorten" method="post" class="flex gap-2">
                <input name="long_url" placeholder="粘贴长链接 (https://...)" class="flex-1 bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none focus:border-blue-500 transition-all text-sm" required>
                <button class="bg-blue-600 hover:bg-blue-500 px-8 rounded-xl font-bold text-white transition-all shadow-lg shadow-blue-900/20">创建</button>
            </form>
        </div>

        <div class="sentinel-card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-slate-800/50 text-slate-400 uppercase text-[10px] tracking-widest">
                    <tr><th class="p-4">哨兵链路</th><th class="p-4">目标地址</th><th class="p-4">安全策略</th></tr>
                </thead>
                <tbody>
                    {% for link in links %}
                    <tr class="border-t border-slate-800/50 hover:bg-slate-800/20 transition-all">
                        <td class="p-4 font-mono accent-blue">{{ host_url }}{{ link[0] }}</td>
                        <td class="p-4 text-slate-500 truncate max-w-xs">{{ link[1] }}</td>
                        <td class="p-4"><span class="bg-blue-500/10 text-blue-400 px-2 py-1 rounded text-[10px] border border-blue-500/20">{{ link[2] }}</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] flex items-center justify-center h-screen text-slate-300">
    <form method="post" class="bg-[#151921] border border-[#232936] p-10 rounded-3xl w-96 shadow-2xl">
        <h1 class="text-2xl font-black mb-8 text-center text-blue-500 italic tracking-tighter">SENTINEL LOGIN</h1>
        <div class="space-y-4">
            <input name="u" placeholder="Account" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-500">
            <input name="p" type="password" placeholder="Password" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-500">
            <button class="bg-blue-600 hover:bg-blue-500 w-full py-4 rounded-xl font-bold text-white shadow-lg shadow-blue-900/30 transition-all">进入控制台</button>
        </div>
    </form>
</body>
"""

# --- 3. 核心业务路由 ---
@app.route('/')
def index():
    if 'user' in session: return redirect('/admin')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['u'], request.form['p']
        conn = sqlite3.connect('urls.db'); c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p))
        res = c.fetchone()
        if res:
            session['user'] = u
            return redirect('/admin')
    return render_template_string(LOGIN_HTML)

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect('urls.db'); c = conn.cursor()
    c.execute("SELECT short_code, long_url, policy_name FROM mapping")
    links = c.fetchall()
    conn.close()
    return render_template_string(ADMIN_TEMPLATE, 
                                 links=links, 
                                 username=session['user'], 
                                 host_url=request.host_url)

@app.route('/shorten', methods=['POST'])
def shorten():
    if 'user' not in session: return redirect('/login')
    long_url = request.form['long_url']
    code = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))
    t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('urls.db'); c = conn.cursor()
    c.execute("INSERT INTO mapping (long_url, short_code, owner, policy_name, create_time) VALUES (?, ?, ?, ?, ?)", 
              (long_url, code, session['user'], 'DEFAULT_SAFE', t))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/<short_code>')
def redirect_engine(short_code):
    if short_code in ['admin', 'login', 'logout', 'shorten']: return abort(404)
    conn = sqlite3.connect('urls.db'); c = conn.cursor()
    c.execute("SELECT long_url FROM mapping WHERE short_code=?", (short_code,))
    res = c.fetchone()
    if res:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        c.execute("INSERT INTO visit_logs (short_code, ip, view_time) VALUES (?, ?, ?)", 
                  (short_code, ip, str(datetime.datetime.now())))
        conn.commit(); conn.close()
        return redirect(res[0])
    return "Node Not Found", 404

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
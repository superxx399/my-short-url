import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = 'sentinel_pro_2026_secure'

# --- 1. 数据库初始化 (包含强制重置逻辑) ---
def init_db():
    db_path = 'urls.db'
    # 强制重置数据库以匹配新的表结构，解决 500 错误
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # 账户表
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)''')
    # 链路映射表
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, long_url TEXT, short_code TEXT UNIQUE, 
                  owner TEXT, policy_name TEXT, create_time TEXT)''')
    # 访问日志表
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT, ip TEXT, view_time TEXT)''')
    
    # 插入预设管理员 (账号: admin 密码: 123456)
    c.execute("INSERT INTO users (username, password, role) VALUES ('admin', '123456', 'admin')")
    
    conn.commit()
    conn.close()

# --- 2. 高级黑金 UI 模板 ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0e14; color: #d1d5db; font-family: sans-serif; }
        .sentinel-card { background: #151921; border: 1px solid #232936; border-radius: 16px; }
        .accent-blue { color: #3b82f6; }
    </style>
</head>
<body class="p-8">
    <div class="max-w-5xl mx-auto">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-2xl font-black accent-blue tracking-tighter italic">SENTINEL PRO</h2>
            <div class="flex items-center gap-4 text-sm">
                <span class="text-slate-500 underline">ID: {{ username }}</span>
                <a href="/logout" class="text-red-500 font-bold border border-red-900/50 px-3 py-1 rounded-lg">EXIT</a>
            </div>
        </div>

        <div class="sentinel-card p-8 mb-10 shadow-2xl border-t-2 border-t-blue-500/30">
            <h3 class="text-xs font-bold mb-4 text-slate-500 uppercase tracking-widest">Deploy New Secure Link</h3>
            <form action="/shorten" method="post" class="flex gap-3">
                <input name="long_url" placeholder="Enter target URL (https://...)" class="flex-1 bg-slate-900 border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-500 transition-all" required>
                <button class="bg-blue-600 hover:bg-blue-500 px-10 rounded-xl font-bold text-white transition-all shadow-lg shadow-blue-900/20">DEPLOY</button>
            </form>
        </div>

        <div class="sentinel-card overflow-hidden shadow-xl">
            <table class="w-full text-left text-sm">
                <thead class="bg-slate-800/30 text-slate-400 uppercase text-[10px] tracking-[0.2em]">
                    <tr><th class="p-5">Link Node</th><th class="p-5">Destination</th><th class="p-5">Policy</th></tr>
                </thead>
                <tbody>
                    {% for link in links %}
                    <tr class="border-t border-slate-800/50 hover:bg-blue-500/5 transition-all">
                        <td class="p-5 font-mono accent-blue font-bold">{{ host_url }}{{ link[0] }}</td>
                        <td class="p-5 text-slate-500 truncate max-w-xs">{{ link[1] }}</td>
                        <td class="p-5"><span class="bg-blue-500/10 text-blue-400 px-3 py-1 rounded-full text-[10px] border border-blue-500/20">{{ link[2] }}</span></td>
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
<body class="bg-[#0b0e14] flex items-center justify-center h-screen">
    <div class="bg-[#151921] border border-[#232936] p-12 rounded-[2rem] w-[400px] shadow-2xl text-center">
        <h1 class="text-3xl font-black mb-2 text-blue-500 italic">SENTINEL</h1>
        <p class="text-slate-500 text-xs mb-10 tracking-widest uppercase font-bold text-[10px]">Security Infrastructure</p>
        <form method="post" class="space-y-4">
            <input name="u" placeholder="Identity" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none focus:border-blue-500 text-white shadow-inner" required>
            <input name="p" type="password" placeholder="Access Key" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none focus:border-blue-500 text-white shadow-inner" required>
            <button class="bg-blue-600 hover:bg-blue-500 w-full py-4 rounded-2xl font-black text-white shadow-lg shadow-blue-900/40 transition-all mt-4">AUTHENTICATE</button>
        </form>
    </div>
</body>
"""

# --- 3. 路由逻辑 ---
@app.route('/')
def index():
    return redirect('/admin') if 'user' in session else redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        conn = sqlite3.connect('urls.db'); c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p))
        res = c.fetchone()
        conn.close()
        if res:
            session['user'] = u
            return redirect('/admin')
    return render_template_string(LOGIN_HTML)

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect('urls.db'); c = conn.cursor()
    c.execute("SELECT short_code, long_url, policy_name FROM mapping ORDER BY id DESC")
    links = c.fetchall()
    conn.close()
    return render_template_string(ADMIN_TEMPLATE, links=links, username=session['user'], host_url=request.host_url)

@app.route('/shorten', methods=['POST'])
def shorten():
    if 'user' not in session: return redirect('/login')
    long_url = request.form['long_url']
    code = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))
    t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('urls.db'); c = conn.cursor()
    c.execute("INSERT INTO mapping (long_url, short_code, owner, policy_name, create_time) VALUES (?, ?, ?, ?, ?)", 
              (long_url, code, session['user'], 'SAFE_FILTER_V1', t))
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
        c.execute("INSERT INTO visit_logs (short_code, ip, view_time) VALUES (?, ?, ?)", (short_code, ip, str(datetime.datetime.now())))
        conn.commit(); conn.close()
        return redirect(res[0])
    return "Node Access Denied", 404

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
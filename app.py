import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
# 1. 确保 Secret Key 稳定，防止 Session 报错
app.secret_key = os.environ.get("SECRET_KEY", "sentinel_fixed_v1")

# 获取数据库绝对路径，防止 Render 找不到文件
DB_PATH = os.path.join(os.getcwd(), 'urls.db')

def init_db():
    # 2. 只有在数据库结构损坏时才需要物理删除。如果现在进不去，先执行一次删除
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except:
            pass
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, long_url TEXT, short_code TEXT UNIQUE, 
                  owner TEXT, policy_name TEXT, create_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT, ip TEXT, view_time TEXT)''')
    
    # 预设管理员
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', '123456', 'admin')")
    conn.commit()
    conn.close()

# --- 3. UI 模板 ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>body { background-color: #0b0e14; color: #d1d5db; }</style>
</head>
<body class="p-8"><div class="max-w-4xl mx-auto">
    <div class="flex justify-between mb-8"><h2 class="text-xl font-bold text-blue-500 italic">SENTINEL PRO</h2>
    <a href="/logout" class="text-red-500 text-xs border border-red-500/30 px-2 py-1 rounded">EXIT</a></div>
    <div class="bg-[#151921] p-6 rounded-xl border border-slate-800 mb-8">
        <form action="/shorten" method="post" class="flex gap-2">
            <input name="long_url" placeholder="https://..." class="flex-1 bg-slate-900 border border-slate-800 p-2 rounded outline-none text-sm" required>
            <button class="bg-blue-600 px-6 rounded font-bold text-white">CREATE</button>
        </form>
    </div>
    <div class="bg-[#151921] rounded-xl border border-slate-800 overflow-hidden">
        <table class="w-full text-left text-sm">
            <thead class="bg-slate-800/50 text-slate-400 text-xs"><tr><th class="p-4">SHORT LINK</th><th class="p-4">DESTINATION</th></tr></thead>
            <tbody>
                {% for link in links %}
                <tr class="border-t border-slate-800/50"><td class="p-4 text-blue-400 font-mono">{{ host }}{{ link[0] }}</td><td class="p-4 text-slate-500 truncate max-w-xs">{{ link[1] }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div></body></html>
"""

LOGIN_HTML = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] flex items-center justify-center h-screen">
    <form method="post" class="bg-[#151921] border border-slate-800 p-10 rounded-2xl w-80 shadow-2xl">
        <h1 class="text-xl font-bold mb-6 text-center text-blue-500">SENTINEL LOGIN</h1>
        <input name="u" placeholder="Account" class="w-full bg-slate-900 border border-slate-800 p-3 mb-4 rounded-lg outline-none text-white" required>
        <input name="p" type="password" placeholder="Password" class="w-full bg-slate-900 border border-slate-800 p-3 mb-6 rounded-lg outline-none text-white" required>
        <button class="bg-blue-600 w-full py-3 rounded-lg font-bold text-white">LOGIN</button>
    </form>
</body>
"""

@app.route('/')
def index():
    return redirect('/admin') if 'user' in session else redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p))
        res = c.fetchone()
        conn.close()
        if res:
            session.permanent = True
            session['user'] = u
            return redirect('/admin')
        return "Login Failed"
    return render_template_string(LOGIN_HTML)

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT short_code, long_url FROM mapping ORDER BY id DESC")
    links = c.fetchall()
    conn.close()
    return render_template_string(ADMIN_TEMPLATE, links=links, host=request.host_url)

@app.route('/shorten', methods=['POST'])
def shorten():
    if 'user' not in session: return redirect('/login')
    long_url = request.form['long_url']
    code = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 确保字段对应：long_url, short_code, owner, policy_name, create_time
    c.execute("INSERT INTO mapping (long_url, short_code, owner, policy_name, create_time) VALUES (?, ?, ?, ?, ?)", 
              (long_url, code, session['user'], 'DEFAULT', str(datetime.datetime.now())))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/<short_code>')
def redirect_engine(short_code):
    if short_code in ['admin', 'login', 'logout', 'shorten']: return abort(404)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT long_url FROM mapping WHERE short_code=?", (short_code,))
    res = c.fetchone()
    if res:
        return redirect(res[0])
    return "Not Found", 404

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
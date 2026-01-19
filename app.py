import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = 'sentinel_v1_secure'

# --- 1. 数据库地基 ---
def init_db():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    # 确保表结构完整：增加 policy_name 和 create_time
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

# --- 2. 视觉 UI (黑金风格) ---
UI_STYLE = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
    body { background-color: #0b0e14; color: #d1d5db; font-family: sans-serif; }
    .sentinel-card { background: #151921; border: 1px solid #232936; border-radius: 12px; }
    .accent-blue { color: #3b82f6; }
</style>
"""

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
    return f"{UI_STYLE}<body class='flex items-center justify-center h-screen'><form method='post' class='sentinel-card p-10 w-96'><h1 class='text-2xl font-bold mb-8 text-center accent-blue'>SENTINEL LOGIN</h1><input name='u' placeholder='账户' class='w-full bg-slate-900 border border-slate-800 p-3 mb-4 rounded-lg outline-none'><input name='p' type='password' placeholder='密码' class='w-full bg-slate-900 border border-slate-800 p-3 mb-8 rounded-lg outline-none'><button class='bg-blue-600 w-full py-3 rounded-lg font-bold'>进入系统</button></form></body>"

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect('urls.db'); c = conn.cursor()
    c.execute("SELECT short_code, long_url, policy_name FROM mapping")
    links = c.fetchall()
    return render_template_string(f"""{UI_STYLE}
    <body class='p-8'><div class='max-w-4xl mx-auto'>
        <div class='flex justify-between mb-8'>
            <h2 class='text-xl font-bold accent-blue'>哨兵控制台</h2>
            <a href='/logout' class='text-red-400'>安全退出</a>
        </div>
        <div class='sentinel-card p-6 mb-8'>
            <form action='/shorten' method='post' class='flex gap-2'>
                <input name='long_url' placeholder='输入链接...' class='flex-1 bg-slate-900 border border-slate-800 p-2 rounded'>
                <button class='bg-blue-600 px-6 rounded font-bold'>创建</button>
            </form>
        </div>
        <div class='sentinel-card overflow-hidden'>
            <table class='w-full text-left'>
                <thead class='bg-slate-800'><tr><th class='p-4'>短链接</th><th class='p-4'>原始地址</th><th class='p-4'>策略</th></tr></thead>
                <tbody>
                    {% for link in links %}
                    <tr class='border-t border-slate-800'>
                        <td class='p-4 accent-blue'>{{request.host_url}}{{link[0]}}</td>
                        <td class='p-4 text-slate-500'>{{link[1][:30]}}...</td>
                        <td class='p-4 text-xs'>{{link[2]}}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div></body>""", links=links)

@app.route('/shorten', methods=['POST'])
def shorten():
    long_url = request.form['long_url']
    code = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))
    t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect('urls.db'); c = conn.cursor()
    # 修复了截图中的括号嵌套和逗号错误
    c.execute("INSERT INTO mapping (long_url, short_code, owner, policy_name, create_time) VALUES (?, ?, ?, ?, ?)", 
              (long_url, code, session.get('user'), '美股FB策略', t))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/<short_code>')
def redirect_engine(short_code):
    conn = sqlite3.connect('urls.db'); c = conn.cursor()
    c.execute("SELECT long_url FROM mapping WHERE short_code=?", (short_code,))
    res = c.fetchone()
    if res:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        c.execute("INSERT INTO visit_logs (short_code, ip, view_time) VALUES (?, ?, ?)", 
                  (short_code, ip, str(datetime.datetime.now())))
        conn.commit(); conn.close()
        return redirect(res[0])
    return "Link Not Found", 404

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sentinel_v3_commander")
DB_PATH = os.path.join(os.getcwd(), 'urls.db')

# --- 1. 数据库初始化 (逻辑：目的地可调) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    # 增加 title(备注名称) 方便管理
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, long_url TEXT, short_code TEXT UNIQUE, 
                  allowed_regions TEXT, status TEXT DEFAULT 'active', create_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT, ip TEXT, region TEXT, ua TEXT, view_time TEXT)''')
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES ('admin', '123456')")
    conn.commit()
    conn.close()

# --- 2. 界面模板 (增加“编辑”与“日志”视图) ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>body { background-color: #0b0e14; color: #d1d5db; font-family: sans-serif; }</style>
</head>
<body class="p-6 md:p-10 bg-[#080a0f]">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-2xl font-black text-blue-500 italic">SENTINEL COMMANDER</h1>
            <a href="/logout" class="text-xs text-red-500 border border-red-500/20 px-3 py-1 rounded">退出系统</a>
        </div>

        <div class="bg-[#11141b] border border-white/5 p-6 rounded-2xl mb-8">
            <h3 class="text-xs font-bold text-slate-500 uppercase mb-4 tracking-widest">部署固定入口节点</h3>
            <form action="/create" method="post" class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <input name="title" placeholder="节点备注 (如: WhatsApp客服A)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none focus:border-blue-500" required>
                <input name="long_url" placeholder="初始目的地 (https://...)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none focus:border-blue-500" required>
                <button class="bg-blue-600 hover:bg-blue-500 rounded-xl font-bold text-white transition-all">创建固定短链</button>
            </form>
        </div>

        <div class="bg-[#11141b] border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-slate-500 text-[10px] uppercase">
                    <tr><th class="p-4">节点名称</th><th class="p-4">固定短链 (入口)</th><th class="p-4">当前目的地</th><th class="p-4">地区策略</th><th class="p-4 text-right">操作</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for link in links %}
                    <tr class="hover:bg-blue-500/5 transition">
                        <td class="p-4 font-bold text-slate-300">{{ link[1] }}</td>
                        <td class="p-4 font-mono text-blue-400 select-all">{{ host }}{{ link[3] }}</td>
                        <td class="p-4">
                            <form action="/update/{{ link[3] }}" method="post" class="flex items-center gap-2">
                                <input name="new_url" value="{{ link[2] }}" class="bg-transparent border-b border-slate-700 text-xs text-slate-500 focus:border-blue-500 outline-none w-48">
                                <button class="text-[10px] bg-slate-800 px-2 py-1 rounded hover:bg-blue-600 transition">修改</button>
                            </form>
                        </td>
                        <td class="p-4">
                            <form action="/update_policy/{{ link[3] }}" method="post" class="flex items-center gap-2">
                                <input name="regions" value="{{ link[4] or '' }}" placeholder="如: CN,HK" class="bg-transparent border-b border-slate-700 text-[10px] text-slate-500 outline-none w-16 text-center">
                                <button class="text-[10px] text-blue-500">保存</button>
                            </form>
                        </td>
                        <td class="p-4 text-right">
                            <a href="/logs/{{ link[3] }}" class="text-xs text-blue-400 bg-blue-500/10 px-2 py-1 rounded mr-2">访客日志</a>
                            <a href="/delete/{{ link[3] }}" class="text-xs text-red-900 hover:text-red-500" onclick="return confirm('警告：删除后入口将永久失效！')">销毁</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

LOGS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-[#0b0e14] text-slate-300 p-10 font-sans">
    <div class="max-w-4xl mx-auto">
        <div class="flex justify-between mb-8 align-bottom">
            <h2 class="text-xl font-bold text-blue-500 italic">访客详细日志: /{{ code }}</h2>
            <a href="/admin" class="text-xs bg-slate-800 px-3 py-1 rounded text-slate-400">返回控制台</a>
        </div>
        <div class="bg-[#11141b] rounded-xl border border-white/5 overflow-hidden">
            <table class="w-full text-xs text-left">
                <thead class="bg-white/5 text-slate-500 uppercase">
                    <tr><th class="p-4">访问时间</th><th class="p-4">IP地址</th><th class="p-4">设备信息 (User-Agent)</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for log in logs %}
                    <tr>
                        <td class="p-4 text-slate-400">{{ log[5] }}</td>
                        <td class="p-4 font-mono text-blue-400">{{ log[2] }}</td>
                        <td class="p-4 text-slate-500 truncate max-w-xs">{{ log[4] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

# --- 3. 业务逻辑 ---
@app.route('/create', methods=['POST'])
def create():
    if 'user' not in session: return redirect('/login')
    title, long_url = request.form['title'], request.form['long_url']
    code = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO mapping (title, long_url, short_code, create_time) VALUES (?, ?, ?, ?)", 
              (title, long_url, code, str(datetime.datetime.now())))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/update/<code>', methods=['POST'])
def update_url(code):
    if 'user' not in session: return redirect('/login')
    new_url = request.form['new_url']
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE mapping SET long_url=? WHERE short_code=?", (new_url, code))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/update_policy/<code>', methods=['POST'])
def update_policy(code):
    if 'user' not in session: return redirect('/login')
    regions = request.form['regions'].upper()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE mapping SET allowed_regions=? WHERE short_code=?", (regions, code))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/logs/<code>')
def show_logs(code):
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM visit_logs WHERE short_code=? ORDER BY id DESC LIMIT 100", (code,))
    logs = c.fetchall(); conn.close()
    return render_template_string(LOGS_TEMPLATE, logs=logs, code=code)

# (其余 login, logout, index 路由保持不变，使用上一版代码即可)
# 此处省略重复部分以节省篇幅，请确保合并时保留 login 逻辑

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM mapping ORDER BY id DESC")
    links = c.fetchall(); conn.close()
    return render_template_string(ADMIN_TEMPLATE, links=links, host=request.host_url)

@app.route('/<short_code>')
def redirect_engine(short_code):
    if short_code in ['admin', 'login', 'logout', 'create', 'update', 'logs']: return abort(404)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT long_url, allowed_regions FROM mapping WHERE short_code=?", (short_code,))
    res = c.fetchone()
    if res:
        long_url, allowed_regions = res
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
        ua = request.user_agent.string
        c.execute("INSERT INTO visit_logs (short_code, ip, ua, view_time) VALUES (?, ?, ?, ?)", (short_code, ip, ua, str(datetime.datetime.now())))
        conn.commit(); conn.close()
        # 拦截逻辑：此处可根据 allowed_regions 进行逻辑判断
        return redirect(long_url)
    return "SENTINEL: DENIED", 404

@app.route('/delete/<code>')
def delete_item(code):
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM mapping WHERE short_code=?", (code,))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        if u == 'admin' and p == '123456': # 为演示简化，生产环境建议查表
            session['user'] = u
            return redirect('/admin')
    return render_template_string("""
    <script src="https://cdn.tailwindcss.com"></script>
    <body class="bg-[#0b0e14] flex items-center justify-center h-screen">
        <form method="post" class="bg-[#11141b] border border-white/5 p-12 rounded-[2rem] shadow-2xl">
            <h1 class="text-2xl font-black text-blue-500 mb-8 italic">SENTINEL COMMANDER</h1>
            <input name="u" placeholder="Identity" class="w-full bg-slate-900 border border-slate-800 p-4 mb-4 rounded-xl text-white outline-none focus:border-blue-500">
            <input name="p" type="password" placeholder="Key" class="w-full bg-slate-900 border border-slate-800 p-4 mb-8 rounded-xl text-white outline-none focus:border-blue-500">
            <button class="bg-blue-600 w-full py-4 rounded-xl font-bold text-white">进入指挥中心</button>
        </form>
    </body>
    """)

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

init_db()
if __name__ == '__main__':
    app.run(debug=True)
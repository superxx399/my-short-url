import os, sqlite3, random, string, datetime, urllib.parse
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
# 秘钥固定，防止部署后 Session 丢失
app.secret_key = "sentinel_pro_fixed_secret_key_v5"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v5.db')

# --- 1. 数据库初始化 ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, title TEXT, long_url TEXT, short_code TEXT UNIQUE, 
                  welcome_msg TEXT, allowed_regions TEXT, allowed_devices TEXT, create_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT, ip TEXT, region TEXT, ua TEXT, 
                  is_blocked INTEGER, block_reason TEXT, view_time TEXT)''')
    # 初始管理账号：admin / admin888
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin888', 'admin')")
    conn.commit(); conn.close()

# --- 2. 核心拦截与分发引擎 ---
@app.route('/<short_code>')
def dispatch(short_code):
    # 排除系统保留关键字
    reserved = ['admin', 'login', 'logout', 'create_user', 'create_link', 'delete', 'logs', 'update', 'favicon.ico']
    if short_code in reserved: return abort(404)
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM mapping WHERE short_code=?", (short_code,))
    node = c.fetchone()
    
    if not node: return "ERROR: NODE_OFFLINE", 404

    target_url = node[3]
    welcome_msg = node[5]
    allowed_devices = node[7] or "" # 默认不限制
    
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    ua_raw = request.user_agent.string
    ua = ua_raw.lower()
    
    is_blocked = 0
    block_reason = "Passed"
    
    # 智能设备检测
    is_mobile = any(x in ua for x in ['iphone', 'android', 'mobile'])
    current_device = "Mobile" if is_mobile else "PC"
    
    # 拦截逻辑：如果后台勾选了规则但当前设备不符，则拦截
    if allowed_devices:
        if current_device not in allowed_devices:
            is_blocked = 1
            block_reason = f"设备冲突: 仅限 {allowed_devices} 访问"

    # WhatsApp 进线语处理
    final_url = target_url
    if is_blocked == 0 and welcome_msg and ("wa.me" in target_url or "api.whatsapp.com" in target_url):
        msg_encoded = urllib.parse.quote(welcome_msg)
        final_url = f"{target_url}{'&' if '?' in target_url else '?'}text={msg_encoded}"

    # 记录日志
    c.execute("INSERT INTO visit_logs (short_code, ip, ua, is_blocked, block_reason, view_time) VALUES (?, ?, ?, ?, ?, ?)",
              (short_code, ip, ua_raw, is_blocked, block_reason, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

    if is_blocked == 1:
        return f"<body style='background:#000;color:#f00;display:flex;justify-content:center;align-items:center;height:100vh;text-align:center;'><div><h1>🛡️ SECURITY INTERCEPTED</h1><p>{block_reason}</p></div></body>", 403
    
    return redirect(final_url)

# --- 3. 登录逻辑 (修复 Action 路径) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u')
        p = request.form.get('p')
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p))
        res = c.fetchone(); conn.close()
        if res:
            session.permanent = True
            session['user'] = u
            session['role'] = res[0]
            return redirect('/admin')
    return render_template_string(LOGIN_UI)

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    if session['role'] == 'admin':
        c.execute("SELECT * FROM mapping ORDER BY id DESC")
        links = c.fetchall()
        c.execute("SELECT username, role FROM users")
        users = c.fetchall()
    else:
        c.execute("SELECT * FROM mapping WHERE owner=? ORDER BY id DESC", (session['user'],))
        links = c.fetchall()
        users = []
    conn.close()
    return render_template_string(ADMIN_UI, links=links, users=users, role=session['role'], user=session['user'], host=request.host_url)

# --- 4. 业务功能路由 ---
@app.route('/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'admin': return abort(403)
    u, p = request.form.get('u'), request.form.get('p')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'agent')", (u, p))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect('/admin')

@app.route('/create_link', methods=['POST'])
def create_link():
    if 'user' not in session: return redirect('/login')
    f = request.form
    code = f.get('code').strip() or ''.join(random.choice(string.ascii_letters) for _ in range(6))
    devices = ",".join(f.getlist('devices'))
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    try:
        c.execute("INSERT INTO mapping (owner, title, long_url, short_code, welcome_msg, allowed_regions, allowed_devices, create_time) VALUES (?,?,?,?,?,?,?,?)",
                  (session['user'], f['title'], f['url'], code, f['msg'], f['regions'], devices, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect('/admin')

@app.route('/logs/<code>')
def view_logs(code):
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM visit_logs WHERE short_code=? ORDER BY id DESC LIMIT 100", (code,))
    logs = c.fetchall(); conn.close()
    return render_template_string(LOGS_UI, logs=logs, code=code)

@app.route('/delete/<code>')
def delete_link(code):
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM mapping WHERE short_code=?", (code,))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/update/<code>', methods=['POST'])
def update_url(code):
    if 'user' not in session: return redirect('/login')
    new_url = request.form.get('new_url')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE mapping SET long_url=? WHERE short_code=?", (new_url, code))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

@app.route('/')
def home():
    return redirect('/admin')

# --- 5. UI 模板集合 ---
LOGIN_UI = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] flex items-center justify-center h-screen text-slate-300">
    <form action="/login" method="post" class="bg-[#11141b] border border-white/5 p-10 rounded-[2.5rem] w-full max-w-sm shadow-2xl">
        <h1 class="text-2xl font-black text-blue-500 mb-8 italic text-center tracking-widest underline">SENTINEL COMMANDER</h1>
        <input name="u" placeholder="ID" class="w-full bg-slate-900 border border-slate-800 p-4 mb-4 rounded-2xl outline-none focus:border-blue-500">
        <input name="p" type="password" placeholder="KEY" class="w-full bg-slate-900 border border-slate-800 p-4 mb-8 rounded-2xl outline-none focus:border-blue-500">
        <button class="bg-blue-600 w-full py-4 rounded-2xl font-bold text-white shadow-lg">AUTHENTICATE</button>
    </form>
</body>
"""

ADMIN_UI = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] text-slate-300 p-4 md:p-10">
    <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-10">
            <h1 class="text-2xl font-black text-blue-500 italic underline tracking-tighter">SENTINEL CONTROL PANEL V5</h1>
            <div class="flex items-center gap-4 text-xs">
                <span class="bg-slate-800 px-3 py-1.5 rounded-full text-slate-400 border border-white/5">{{ user }} ({{ role }})</span>
                <a href="/logout" class="text-red-500 hover:underline">LOGOUT</a>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-10">
            {% if role == 'admin' %}
            <div class="bg-[#11141b] p-6 rounded-3xl border border-white/5 shadow-xl">
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4">子账户开通 / Multi-User</h3>
                <form action="/create_user" method="post" class="space-y-3">
                    <input name="u" placeholder="New Account ID" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500">
                    <input name="p" placeholder="New Account Key" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500">
                    <button class="w-full bg-blue-600 py-3 rounded-xl text-xs font-bold">创建子账号</button>
                </form>
            </div>
            {% endif %}

            <div class="bg-[#11141b] p-6 rounded-3xl border border-white/5 shadow-xl lg:col-span-2">
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4">快速部署链路 / Link Deployment</h3>
                <form action="/create_link" method="post" class="grid grid-cols-2 gap-4">
                    <input name="title" placeholder="备注: 如 WA客服01" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500 col-span-1" required>
                    <input name="code" placeholder="自定义后缀 (选填)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500 col-span-1">
                    <input name="url" placeholder="跳转目标 URL (WhatsApp/Group)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500 col-span-2" required>
                    <input name="msg" placeholder="WhatsApp 自动话术 (进线语)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500 col-span-2">
                    <input name="regions" placeholder="拦截国家 (如: CN,HK)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500 col-span-1">
                    <div class="flex items-center gap-6 px-4 text-xs text-slate-500">
                        <label class="flex items-center gap-2"><input type="checkbox" name="devices" value="Mobile" checked> 手机</label>
                        <label class="flex items-center gap-2"><input type="checkbox" name="devices" value="PC" checked> 电脑</label>
                    </div>
                    <button class="bg-blue-600 py-3 rounded-xl text-xs font-bold col-span-2 shadow-lg shadow-blue-900/20">部署智能节点</button>
                </form>
            </div>
        </div>

        <div class="bg-[#11141b] rounded-3xl border border-white/5 overflow-hidden shadow-2xl">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-slate-500 text-[10px] uppercase tracking-widest">
                    <tr><th class="p-6">链路备注/归属</th><th class="p-6">固定入口</th><th class="p-6">实时目的地</th><th class="p-6 text-right">监控与管理</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for link in links %}
                    <tr class="hover:bg-blue-500/5 transition group">
                        <td class="p-6"><div class="font-bold text-slate-200">{{ link[2] }}</div><div class="text-[10px] text-slate-600 uppercase">{{ link[1] }}</div></td>
                        <td class="p-6 font-mono text-blue-400">/{{ link[4] }}</td>
                        <td class="p-6">
                            <form action="/update/{{ link[4] }}" method="post" class="flex gap-2">
                                <input name="new_url" value="{{ link[3] }}" class="bg-transparent border-b border-slate-800 text-xs w-full text-slate-500 outline-none focus:border-blue-500">
                                <button class="text-[10px] text-blue-500 font-bold opacity-0 group-hover:opacity-100">UPDATE</button>
                            </form>
                        </td>
                        <td class="p-6 text-right">
                            <a href="/logs/{{ link[4] }}" class="bg-blue-500/10 text-blue-400 px-4 py-2 rounded-xl text-[10px] font-bold border border-blue-500/20 hover:bg-blue-500 hover:text-white transition">查看审计日志</a>
                            <a href="/delete/{{ link[4] }}" class="ml-4 text-slate-700 hover:text-red-500 text-[10px]" onclick="return confirm('警告: 销毁后入口永久失效！')">销毁</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
"""

LOGS_UI = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] text-slate-300 p-10">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-xl font-bold italic text-blue-500 tracking-tighter">AUDIT LOGS: /{{ code }}</h2>
            <a href="/admin" class="text-xs bg-slate-800 px-4 py-2 rounded-xl text-slate-400">返回控制中心</a>
        </div>
        <div class="bg-[#11141b] rounded-[2rem] border border-white/5 overflow-hidden shadow-2xl text-xs">
            <table class="w-full text-left">
                <thead class="bg-white/5 text-slate-500 uppercase font-bold tracking-widest">
                    <tr><th class="p-5">访问时间</th><th class="p-5">IP 来源</th><th class="p-5">状态</th><th class="p-5">拦截原因 / 访客设备</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for log in logs %}
                    <tr class="{{ 'bg-red-500/5' if log[5] == 1 else 'bg-green-500/5' }}">
                        <td class="p-5 text-slate-400">{{ log[7] }}</td>
                        <td class="p-5 font-mono text-blue-400 underline">{{ log[2] }}</td>
                        <td class="p-5">
                            {% if log[5] == 1 %}
                            <span class="text-red-500 font-bold">❌ BLOCKED</span>
                            {% else %}
                            <span class="text-green-500 font-bold">✅ PASSED</span>
                            {% endif %}
                        </td>
                        <td class="p-5 text-slate-500 italic">{{ log[6] if log[5] == 1 else log[4][:60] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
"""

init_db()
if __name__ == '__main__':
    app.run(debug=True)
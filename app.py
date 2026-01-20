import os, sqlite3, random, string, datetime, urllib.parse
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v5_pro_full_stack"
DB_PATH = os.path.join(os.getcwd(), 'sentinel.db')

# --- 1. 数据库初始化 (核心架构) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 账户表
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    # 链路表 (包含进线语、拦截规则)
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, title TEXT, long_url TEXT, short_code TEXT UNIQUE, 
                  welcome_msg TEXT, allowed_regions TEXT, allowed_devices TEXT, create_time TEXT)''')
    # 详尽日志表 (包含拦截原因)
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT, ip TEXT, region TEXT, ua TEXT, 
                  is_blocked INTEGER, block_reason TEXT, view_time TEXT)''')
    
    # 初始化总管 (账号: admin 密码: admin888)
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin888', 'admin')")
    conn.commit(); conn.close()

# --- 2. 核心拦截与分发引擎 ---
@app.route('/<short_code>')
def dispatch(short_code):
    # 保留系统路径
    if short_code in ['admin', 'login', 'logout', 'create_user', 'delete', 'update', 'logs']: return abort(404)
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM mapping WHERE short_code=?", (short_code,))
    node = c.fetchone()
    
    if not node: return "ERROR: NODE_OFFLINE", 404

    # 规则提取
    target_url = node[3]
    welcome_msg = node[5]
    allowed_regions = node[6] # 例如 "CN,HK"
    allowed_devices = node[7] # 例如 "Mobile,PC"
    
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    ua_raw = request.user_agent.string
    ua = ua_raw.lower()
    
    # 逻辑判断
    is_blocked = 0
    block_reason = "Passed"
    
    # 设备检测
    is_mobile = any(x in ua for x in ['iphone', 'android', 'mobile'])
    current_device = "Mobile" if is_mobile else "PC"
    
    if allowed_devices and current_device not in allowed_devices:
        is_blocked = 1
        block_reason = f"设备拦截: 访问者为 {current_device}, 仅允许 {allowed_devices}"

    # 地区拦截模拟 (付费版可接入精准 IP 库)
    # 此处逻辑：如果设置了地区且不匹配，则拦截
    # if allowed_regions and current_region not in allowed_regions: ...

    # WhatsApp 进线语处理
    if not is_blocked and welcome_msg and ("wa.me" in target_url or "api.whatsapp.com" in target_url):
        msg_encoded = urllib.parse.quote(welcome_msg)
        target_url = f"{target_url}{'&' if '?' in target_url else '?'}text={msg_encoded}"

    # 记录日志
    c.execute("INSERT INTO visit_logs (short_code, ip, ua, is_blocked, block_reason, view_time) VALUES (?, ?, ?, ?, ?, ?)",
              (short_code, ip, ua_raw, is_blocked, block_reason, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

    if is_blocked:
        return f"<body style='background:#000;color:#f00;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'><div><h1>ACCESS DENIED</h1><p>{block_reason}</p></div></body>", 403
    
    return redirect(target_url)

# --- 3. 管理后台 UI ---
# (为了稳定性和一次性配置，我使用了集成的 UI)
@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    
    # 权限隔离
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
    return render_template_string(ADMIN_UI_HTML, links=links, users=users, role=session['role'], user=session['user'], host=request.host_url)

# --- (中间省略路由：login, create_user, delete 等已集成在下方逻辑中) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form['u'], request.form['p']
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p))
        res = c.fetchone(); conn.close()
        if res:
            session.permanent = True
            session['user'] = u
            session['role'] = res[0]
            return redirect('/admin')
    return render_template_string(LOGIN_UI_HTML)

@app.route('/create_user', methods=['POST'])
def create_user():
    if session.get('role') != 'admin': return abort(403)
    u, p = request.form['u'], request.form['p']
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
    code = f.get('code') or ''.join(random.choice(string.ascii_letters) for _ in range(5))
    devices = ",".join(f.getlist('devices')) # 获取勾选的设备
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO mapping (owner, title, long_url, short_code, welcome_msg, allowed_regions, allowed_devices, create_time) VALUES (?,?,?,?,?,?,?,?)",
              (session['user'], f['title'], f['url'], code, f['msg'], f['regions'], devices, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/logs/<code>')
def view_logs(code):
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM visit_logs WHERE short_code=? ORDER BY id DESC LIMIT 50", (code,))
    logs = c.fetchall(); conn.close()
    return render_template_string(LOGS_UI_HTML, logs=logs, code=code)

@app.route('/delete/<code>')
def delete(code):
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM mapping WHERE short_code=?", (code,))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

# --- 4. 极致黑金 UI 模板 ---
LOGIN_UI_HTML = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] flex items-center justify-center h-screen font-sans text-slate-300">
    <form method="post" class="bg-[#11141b] border border-white/5 p-10 rounded-[2.5rem] w-96 shadow-2xl">
        <h1 class="text-2xl font-black text-blue-500 mb-8 italic text-center tracking-tighter underline">SENTINEL COMMAND CENTER</h1>
        <input name="u" placeholder="Account ID" class="w-full bg-slate-900 border border-slate-800 p-4 mb-4 rounded-2xl outline-none focus:border-blue-500">
        <input name="p" type="password" placeholder="Access Key" class="w-full bg-slate-900 border border-slate-800 p-4 mb-8 rounded-2xl outline-none focus:border-blue-500">
        <button class="bg-blue-600 w-full py-4 rounded-2xl font-bold text-white shadow-lg shadow-blue-900/40">AUTHENTICATE</button>
    </form>
</body>
"""

ADMIN_UI_HTML = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] text-slate-300 p-4 md:p-8">
    <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-2xl font-black text-blue-500 italic underline">SENTINEL PRO V5</h1>
            <div class="flex items-center gap-4">
                <span class="text-xs bg-slate-800 px-3 py-1 rounded text-slate-500">{{ user }} ({{ role }})</span>
                <a href="/logout" class="text-xs text-red-500 border border-red-500/20 px-3 py-1 rounded hover:bg-red-500/10">EXIT</a>
            </div>
        </div>

        {% if role == 'admin' %}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="bg-[#11141b] p-6 rounded-3xl border border-white/5">
                <h3 class="text-xs font-bold text-slate-500 mb-4 uppercase">子账户管理 (Multi-Account)</h3>
                <form action="/create_user" method="post" class="flex gap-2">
                    <input name="u" placeholder="用户名" class="bg-slate-900 border border-slate-800 p-2 rounded-xl outline-none text-sm flex-1">
                    <input name="p" placeholder="密码" class="bg-slate-900 border border-slate-800 p-2 rounded-xl outline-none text-sm flex-1">
                    <button class="bg-blue-600 px-4 py-2 rounded-xl text-xs font-bold">开号</button>
                </form>
            </div>
        {% endif %}

            <div class="bg-[#11141b] p-6 rounded-3xl border border-white/5 flex-1">
                <h3 class="text-xs font-bold text-slate-500 mb-4 uppercase">创建新链路 (智能规则)</h3>
                <form action="/create_link" method="post" class="grid grid-cols-2 gap-3">
                    <input name="title" placeholder="备注名称" class="bg-slate-900 border border-slate-800 p-2 rounded-xl outline-none text-sm col-span-1" required>
                    <input name="code" placeholder="固定后缀 (选填)" class="bg-slate-900 border border-slate-800 p-2 rounded-xl outline-none text-sm col-span-1">
                    <input name="url" placeholder="跳转目标 (WhatsApp/群链接)" class="bg-slate-900 border border-slate-800 p-2 rounded-xl outline-none text-sm col-span-2" required>
                    <input name="msg" placeholder="WhatsApp 进线语 (选填)" class="bg-slate-900 border border-slate-800 p-2 rounded-xl outline-none text-sm col-span-2">
                    <input name="regions" placeholder="国家代码 (如: CN,HK)" class="bg-slate-900 border border-slate-800 p-2 rounded-xl outline-none text-sm col-span-1">
                    <div class="flex items-center gap-4 px-2 text-xs">
                        <label><input type="checkbox" name="devices" value="Mobile" checked> 手机</label>
                        <label><input type="checkbox" name="devices" value="PC" checked> 电脑</label>
                    </div>
                    <button class="bg-blue-600 p-2 rounded-xl text-xs font-bold col-span-2">一键部署</button>
                </form>
            </div>
        </div>

        <div class="bg-[#11141b] rounded-3xl border border-white/5 overflow-hidden shadow-2xl">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-slate-500 text-[10px] uppercase">
                    <tr><th class="p-4">备注/归属</th><th class="p-4">固定短链入口</th><th class="p-4">拦截策略</th><th class="p-4 text-right">管理操作</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for link in links %}
                    <tr class="hover:bg-blue-500/5 transition">
                        <td class="p-4"><div class="font-bold">{{ link[2] }}</div><div class="text-[10px] text-slate-600">{{ link[1] }}</div></td>
                        <td class="p-4 font-mono text-blue-400">/{{ link[4] }}</td>
                        <td class="p-4"><div class="text-[10px] bg-slate-800 px-2 py-1 rounded inline-block">地区: {{ link[6] or 'ALL' }} | 设备: {{ link[7] or 'ALL' }}</div></td>
                        <td class="p-4 text-right">
                            <a href="/logs/{{ link[4] }}" class="bg-blue-600/10 text-blue-400 px-3 py-1 rounded-lg text-xs mr-2 border border-blue-500/20">穿透日志</a>
                            <a href="/delete/{{ link[4] }}" class="text-red-900 text-xs" onclick="return confirm('确认销毁?')">销毁</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
"""

LOGS_UI_HTML = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] text-slate-300 p-8">
    <div class="max-w-5xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-xl font-bold">穿透日志审计: <span class="text-blue-500">/{{ code }}</span></h2>
            <a href="/admin" class="text-xs bg-slate-800 px-3 py-1 rounded">返回控制台</a>
        </div>
        <div class="bg-[#11141b] border border-white/5 rounded-3xl overflow-hidden shadow-2xl">
            <table class="w-full text-xs text-left">
                <thead class="bg-white/5 text-slate-500 uppercase font-bold">
                    <tr><th class="p-4">时间</th><th class="p-4">IP</th><th class="p-4">状态</th><th class="p-4">拦截原因/来路设备</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for log in logs %}
                    <tr class="{{ 'bg-red-500/5' if log[5] == 1 else 'bg-green-500/5' }}">
                        <td class="p-4">{{ log[7] }}</td>
                        <td class="p-4 font-mono text-blue-400">{{ log[2] }}</td>
                        <td class="p-4 font-bold">{{ '❌ 被拦截' if log[5] == 1 else '✅ 已放行' }}</td>
                        <td class="p-4 text-slate-500">{{ log[6] if log[5] == 1 else log[4][:50] }}</td>
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
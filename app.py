import os, sqlite3, random, string, datetime, urllib.parse
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_no_login_bypass"
DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'sentinel_v5.db')

# --- 1. 数据库初始化 ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, title TEXT, long_url TEXT, short_code TEXT UNIQUE, 
                  welcome_msg TEXT, allowed_regions TEXT, allowed_devices TEXT, create_time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT, ip TEXT, region TEXT, ua TEXT, 
                  is_blocked INTEGER, block_reason TEXT, view_time TEXT)''')
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin888', 'admin')")
    conn.commit(); conn.close()

# --- 2. 管理后台 (已取消身份验证) ---
@app.route('/')
@app.route('/admin')
def admin_panel():
    # 临时强制身份为管理员，直接展示所有内容
    current_user = "Internal_Tester"
    current_role = "admin"
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM mapping ORDER BY id DESC")
    links = c.fetchall()
    c.execute("SELECT username, role FROM users")
    users = c.fetchall()
    conn.close()
    
    return render_template_string(ADMIN_UI, links=links, users=users, role=current_role, user=current_user, host=request.host_url)

# --- 3. 核心拦截引擎 (带拦截详情日志) ---
@app.route('/<short_code>')
def dispatch(short_code):
    reserved = ['admin', 'create_user', 'create_link', 'delete', 'logs', 'update', 'favicon.ico']
    if short_code in reserved: return abort(404)
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM mapping WHERE short_code=?", (short_code,))
    node = c.fetchone()
    
    if not node: return "ERROR: NODE_OFFLINE", 404

    target_url, welcome_msg, allowed_devices = node[3], node[5], (node[7] or "")
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    ua_raw = request.user_agent.string
    
    is_blocked = 0
    block_reason = "Passed"
    is_mobile = any(x in ua_raw.lower() for x in ['iphone', 'android', 'mobile'])
    current_device = "Mobile" if is_mobile else "PC"
    
    # 这里的规则检查：如果后台勾选了限制，且当前设备不在勾选范围内，则拦截
    if allowed_devices and current_device not in allowed_devices:
        is_blocked = 1
        block_reason = f"设备拦截: 目标仅限 {allowed_devices}, 您当前为 {current_device}"

    # WhatsApp 话术合成
    final_url = target_url
    if is_blocked == 0 and welcome_msg and ("wa.me" in target_url or "api.whatsapp.com" in target_url):
        msg_encoded = urllib.parse.quote(welcome_msg)
        final_url = f"{target_url}{'&' if '?' in target_url else '?'}text={msg_encoded}"

    # 详尽日志审计
    c.execute("INSERT INTO visit_logs (short_code, ip, ua, is_blocked, block_reason, view_time) VALUES (?, ?, ?, ?, ?, ?)",
              (short_code, ip, ua_raw, is_blocked, block_reason, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()

    if is_blocked:
        return f"<body style='background:#050505;color:#ff4d4d;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;'><div><h1 style='border-bottom:2px solid #ff4d4d;padding-bottom:10px;'>SECURITY SHIELD</h1><p>{block_reason}</p></div></body>", 403
    
    return redirect(final_url)

# --- 4. 功能路由 ---
@app.route('/create_user', methods=['POST'])
def create_user():
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
    f = request.form
    code = f.get('code').strip() or ''.join(random.choice(string.ascii_letters) for _ in range(6))
    devices = ",".join(f.getlist('devices'))
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO mapping (owner, title, long_url, short_code, welcome_msg, allowed_regions, allowed_devices, create_time) VALUES (?,?,?,?,?,?,?,?)",
              ("Internal_Tester", f['title'], f['url'], code, f['msg'], f['regions'], devices, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/logs/<code>')
def view_logs(code):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM visit_logs WHERE short_code=? ORDER BY id DESC LIMIT 100", (code,))
    logs = c.fetchall(); conn.close()
    return render_template_string(LOGS_UI, logs=logs, code=code)

@app.route('/delete/<code>')
def delete_link(code):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM mapping WHERE short_code=?", (code,))
    conn.commit(); conn.close()
    return redirect('/admin')

# --- 5. UI (样式保持 V5 暗黑专业版) ---
ADMIN_UI = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] text-slate-300 p-8">
    <div class="max-w-7xl mx-auto">
        <div class="mb-10 flex justify-between items-center">
            <div>
                <h1 class="text-3xl font-black text-blue-500 italic underline tracking-tighter">SENTINEL BYPASS MODE</h1>
                <p class="text-[10px] text-red-500 font-bold uppercase mt-1 tracking-[0.3em]">内测模式：身份验证已跳过 | 数据保存功能正常</p>
            </div>
            <div class="text-xs bg-slate-800 px-4 py-2 rounded-xl text-slate-500 border border-white/5">DB: sentinel_v5.db</div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-10">
            <div class="bg-[#11141b] p-6 rounded-3xl border border-white/5 shadow-2xl">
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4 italic">子账户多开</h3>
                <form action="/create_user" method="post" class="space-y-3">
                    <input name="u" placeholder="账户名" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500">
                    <input name="p" placeholder="初始密码" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500">
                    <button class="w-full bg-blue-600 py-3 rounded-xl text-xs font-bold text-white shadow-lg">确认开号</button>
                </form>
            </div>

            <div class="bg-[#11141b] p-6 rounded-3xl border border-white/5 shadow-2xl lg:col-span-2">
                <h3 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-4 italic text-blue-500">部署链路指挥节点</h3>
                <form action="/create_link" method="post" class="grid grid-cols-2 gap-4">
                    <input name="title" placeholder="链路备注" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500" required>
                    <input name="code" placeholder="指定后缀 (如: test01)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500">
                    <input name="url" placeholder="目的地 (WhatsApp/群链接)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500 col-span-2" required>
                    <input name="msg" placeholder="自动进线语 (文字)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500 col-span-2">
                    <input name="regions" placeholder="拦截地区代码 (CN,HK)" class="bg-slate-900 border border-slate-800 p-3 rounded-xl text-xs outline-none focus:border-blue-500">
                    <div class="flex items-center gap-6 px-4 text-xs">
                        <label class="flex items-center gap-2"><input type="checkbox" name="devices" value="Mobile" checked> 手机端</label>
                        <label class="flex items-center gap-2"><input type="checkbox" name="devices" value="PC" checked> 电脑端</label>
                    </div>
                    <button class="bg-blue-600 py-3 rounded-xl text-xs font-bold text-white col-span-2 shadow-lg shadow-blue-900/40">确认部署</button>
                </form>
            </div>
        </div>

        <div class="bg-[#11141b] rounded-[2.5rem] border border-white/5 overflow-hidden shadow-2xl">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-slate-500 text-[10px] uppercase tracking-widest">
                    <tr><th class="p-6">链路信息</th><th class="p-6">固定入口</th><th class="p-6">拦截规则</th><th class="p-6 text-right">监控</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for link in links %}
                    <tr class="hover:bg-blue-500/5 transition group">
                        <td class="p-6 font-bold text-slate-200">{{ link[2] }}</td>
                        <td class="p-6 font-mono text-blue-400">/{{ link[4] }}</td>
                        <td class="p-6">
                            <span class="text-[10px] bg-slate-900 border border-white/5 px-3 py-1 rounded-full text-slate-400 italic">
                                {{ link[7] or '无限制' }}
                            </span>
                        </td>
                        <td class="p-6 text-right flex justify-end gap-3">
                            <a href="/logs/{{ link[4] }}" class="bg-blue-600/10 text-blue-500 border border-blue-500/20 px-4 py-2 rounded-xl text-[10px] font-bold hover:bg-blue-600 hover:text-white transition">穿透详情日志</a>
                            <a href="/delete/{{ link[4] }}" class="text-slate-800 hover:text-red-500 text-[10px] py-2">销毁</a>
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
<body class="bg-[#0b0e14] text-slate-300 p-8">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-xl font-bold italic underline text-blue-500">穿透审计: /{{ code }}</h2>
            <a href="/admin" class="text-xs bg-slate-800 px-4 py-2 rounded-xl">返回面板</a>
        </div>
        <div class="bg-[#11141b] rounded-3xl border border-white/5 overflow-hidden shadow-2xl">
            <table class="w-full text-xs text-left">
                <thead class="bg-white/5 text-slate-500 uppercase tracking-tighter">
                    <tr><th class="p-5">访问时间</th><th class="p-5">IP 来源</th><th class="p-5">处理状态</th><th class="p-5">详细原因/指纹</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for log in logs %}
                    <tr class="{{ 'bg-red-500/5' if log[5] == 1 else 'bg-green-500/5' }}">
                        <td class="p-5 text-slate-500">{{ log[7] }}</td>
                        <td class="p-5 font-mono text-blue-400 font-bold underline">{{ log[2] }}</td>
                        <td class="p-5 font-black">{{ '❌ BLOCKED' if log[5] == 1 else '✅ PASSED' }}</td>
                        <td class="p-5 text-slate-500 italic">{{ log[6] if log[5] == 1 else log[4][:100] }}</td>
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
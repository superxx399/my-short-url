import os, sqlite3, random, string, datetime, urllib.parse, time
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v9_commercial"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v9.db')

# --- 强制北京时间助手 ---
def get_bj_time():
    # Render 服务器通常是 UTC，+8小时为北京时间
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 1. 账户表：增加创建日期、到期时间
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, 
                  create_date TEXT, expire_date TEXT)''')
    # 2. 防护规则库：防护名称、设备/国家详细配置
    c.execute('''CREATE TABLE IF NOT EXISTS security_tpl 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_countries TEXT, 
                  allowed_devices TEXT, redirect_url TEXT, create_date TEXT)''')
    # 3. 工单表：增加创建日期、关联防护ID
    c.execute('''CREATE TABLE IF NOT EXISTS tickets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, target_url TEXT, 
                  policy_id INTEGER, create_date TEXT)''')
    # 4. 短链汇总：域名选择、关联工单
    c.execute('''CREATE TABLE IF NOT EXISTS mapping 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, domain TEXT, 
                  code TEXT UNIQUE, title TEXT, ticket_id INTEGER)''')
    # 5. 日志表
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    
    # 默认数据
    c.execute("INSERT OR IGNORE INTO users (u, p, n, create_date, expire_date) VALUES ('admin', 'admin888', '总管理员', ?, '2099-12-31')", (get_bj_time(),))
    conn.commit(); conn.close()

# --- 核心拦截引擎 ---
@app.route('/<code>')
def gateway(code):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 连表查询：短链 -> 工单 -> 防护规则
    query = """
    SELECT t.target_url, s.white_countries, s.allowed_devices, s.redirect_url 
    FROM mapping m 
    JOIN tickets t ON m.ticket_id = t.id 
    JOIN security_tpl s ON t.policy_id = s.id 
    WHERE m.code = ?
    """
    c.execute(query, (code,))
    res = c.fetchone()
    
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    ua = request.user_agent.string.lower()
    now = get_bj_time()
    
    if not res: return "404", 404

    target, countries, devices, r_url = res
    is_blocked = 0; reason = "放行"

    # 简易指纹拦截逻辑
    is_mobile = any(x in ua for x in ['iphone', 'android', 'mobile'])
    if devices == 'mobile_only' and not is_mobile:
        is_blocked, reason = 1, "设备拦截: 非移动端"
    
    # 这里后续可以对接更复杂的 IP 库进行国家过滤

    c.execute("INSERT INTO logs (time, code, ip, status, reason) VALUES (?,?,?,?,?)",
              (now, code, ip, "拦截" if is_blocked else "成功", reason))
    conn.commit(); conn.close()

    if is_blocked:
        return redirect(r_url) if r_url else "Access Denied", 403
    return redirect(target)

# --- 管理后台逻辑 ---
@app.route('/')
@app.route('/admin')
def admin():
    tab = request.args.get('tab', 'links')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    data = {}
    if tab == 'users': 
        c.execute("SELECT * FROM users"); data['users'] = c.fetchall()
    elif tab == 'links': 
        c.execute("SELECT m.*, t.name FROM mapping m LEFT JOIN tickets t ON m.ticket_id = t.id")
        data['links'] = c.fetchall()
        c.execute("SELECT id, name FROM tickets"); data['tickets'] = c.fetchall()
    elif tab == 'tickets': 
        c.execute("SELECT t.*, s.name FROM tickets t LEFT JOIN security_tpl s ON t.policy_id = s.id")
        data['tickets'] = c.fetchall()
        c.execute("SELECT id, name FROM security_tpl"); data['policies'] = c.fetchall()
    elif tab == 'security': 
        c.execute("SELECT * FROM security_tpl ORDER BY id DESC"); data['policies'] = c.fetchall()
    elif tab == 'logs': 
        c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50"); data['logs'] = c.fetchall()
    conn.close()
    return render_template_string(V9_UI, tab=tab, data=data, bj_time=get_bj_time())

# --- 接口逻辑 (包含日期处理) ---
@app.route('/api/save_user', methods=['POST'])
def save_user():
    u, p, n, exp = request.form['u'], request.form['p'], request.form['n'], request.form['exp']
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (u, p, n, create_date, expire_date) VALUES (?,?,?,?,?)",
              (u, p, n, get_bj_time(), exp))
    conn.commit(); conn.close()
    return redirect('/admin?tab=users')

@app.route('/api/save_policy', methods=['POST'])
def save_policy():
    f = request.form
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO security_tpl (name, white_countries, allowed_devices, redirect_url, create_date) VALUES (?,?,?,?,?)",
              (f['name'], f['countries'], f['device'], f['r_url'], get_bj_time()))
    conn.commit(); conn.close()
    return redirect('/admin?tab=security')

@app.route('/api/save_ticket', methods=['POST'])
def save_ticket():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO tickets (name, target_url, policy_id, create_date) VALUES (?,?,?,?)",
              (request.form['name'], request.form['url'], request.form['p_id'], get_bj_time()))
    conn.commit(); conn.close()
    return redirect('/admin?tab=tickets')

@app.route('/api/save_link', methods=['POST'])
def save_link():
    code = ''.join(random.choice(string.ascii_letters) for _ in range(5))
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO mapping (date, domain, code, title, ticket_id) VALUES (?,?,?,?,?)",
              (get_bj_time(), request.form['domain'], code, request.form['n'], request.form['tid']))
    conn.commit(); conn.close()
    return redirect('/admin?tab=links')

V9_UI = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] text-slate-300 flex h-screen overflow-hidden font-sans">
    <nav class="w-64 bg-[#11141b] border-r border-white/5 flex flex-col p-6">
        <div class="mb-10">
            <h1 class="text-blue-500 font-black text-2xl italic tracking-tighter">SENTINEL V9</h1>
            <p class="text-[10px] text-slate-500 mt-1 uppercase">北京时间: {{ bj_time[:16] }}</p>
        </div>
        <div class="space-y-2 flex-1">
            <a href="?tab=users" class="block p-4 rounded-2xl transition {{ 'bg-blue-600 text-white shadow-lg' if tab=='users' else 'hover:bg-white/5' }}">👤 账户管理</a>
            <a href="?tab=security" class="block p-4 rounded-2xl transition {{ 'bg-blue-600 text-white shadow-lg' if tab=='security' else 'hover:bg-white/5' }}">🛡️ 防护策略</a>
            <a href="?tab=tickets" class="block p-4 rounded-2xl transition {{ 'bg-blue-600 text-white shadow-lg' if tab=='tickets' else 'hover:bg-white/5' }}">🎫 工单库</a>
            <a href="?tab=links" class="block p-4 rounded-2xl transition {{ 'bg-blue-600 text-white shadow-lg' if tab=='links' else 'hover:bg-white/5' }}">🔗 短链汇总</a>
            <a href="?tab=logs" class="block p-4 rounded-2xl transition {{ 'bg-blue-600 text-white shadow-lg' if tab=='logs' else 'hover:bg-white/5' }}">📊 实时日志</a>
        </div>
    </nav>
    <main class="flex-1 p-12 overflow-y-auto">
        {% if tab == 'users' %}
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-2xl font-bold">子账户体系</h2>
            <button onclick="uBox.showModal()" class="bg-blue-600 px-6 py-3 rounded-2xl font-bold">+ 开通新账户</button>
        </div>
        <div class="bg-[#11141b] rounded-[2rem] border border-white/5 overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-white/5 text-[10px] uppercase text-slate-500">
                    <tr><th class="p-6">账户ID</th><th class="p-6">备注</th><th class="p-6">创建日期</th><th class="p-6">到期时间</th><th class="p-6 text-right">操作</th></tr>
                </thead>
                <tbody class="text-sm divide-y divide-white/5">
                    {% for u in data.users %}
                    <tr><td class="p-6 font-bold">{{u[1]}}</td><td class="p-6">{{u[3]}}</td><td class="p-6 text-slate-500">{{u[4][:10]}}</td><td class="p-6 text-orange-400 font-mono">{{u[5]}}</td><td class="p-6 text-right text-blue-500 cursor-pointer">编辑</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <dialog id="uBox" class="bg-[#11141b] p-8 rounded-[2rem] border border-white/10 text-slate-300 w-[400px]">
            <form action="/api/save_user" method="post" class="space-y-4">
                <h3 class="text-xl font-bold mb-4 italic">账户信息配置</h3>
                <input name="u" placeholder="账户名" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <input name="p" type="password" placeholder="密码" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <input name="n" placeholder="备注名称" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <div class="text-xs text-slate-500 ml-1">设置到期时间</div>
                <input name="exp" type="date" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <button class="w-full bg-blue-600 py-4 rounded-2xl font-bold shadow-xl">确认部署</button>
            </form>
        </dialog>

        {% elif tab == 'security' %}
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-2xl font-bold">防护规则库</h2>
            <button onclick="pBox.showModal()" class="bg-indigo-600 px-6 py-3 rounded-2xl font-bold">+ 新增策略</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            {% for p in data.policies %}
            <div class="bg-[#11141b] border border-white/5 p-6 rounded-[2rem] relative group">
                <div class="text-blue-500 font-bold mb-2 italic"># {{ p[1] }}</div>
                <div class="text-xs text-slate-500 space-y-1">
                    <p>🌍 允许地区: {{ p[2] or '全球' }}</p>
                    <p>📱 设备限制: {{ p[3] }}</p>
                    <p>🔗 拦截跳转: {{ p[4][:30] }}...</p>
                    <p>📅 创建于: {{ p[5] }}</p>
                </div>
                <div class="mt-4 flex gap-2">
                    <button class="text-[10px] bg-slate-800 px-3 py-1 rounded-full">编辑</button>
                </div>
            </div>
            {% endfor %}
        </div>
        <dialog id="pBox" class="bg-[#11141b] p-8 rounded-[2rem] border border-white/10 text-slate-300 w-[450px]">
            <form action="/api/save_policy" method="post" class="space-y-4">
                <h3 class="text-xl font-bold mb-4">创建防护策略</h3>
                <input name="name" placeholder="策略名称 (如: 美国拦截组)" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <input name="countries" placeholder="国家代码 (US,HK,GB)" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <select name="device" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                    <option value="all">不限制设备</option>
                    <option value="mobile_only">仅限移动端 (iOS/Android)</option>
                </select>
                <input name="r_url" placeholder="被拦截后的跳转地址" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <button class="w-full bg-indigo-600 py-4 rounded-2xl font-bold">保存策略</button>
            </form>
        </dialog>

        {% elif tab == 'tickets' %}
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-2xl font-bold">工单管理</h2>
            <button onclick="tBox.showModal()" class="bg-green-600 px-6 py-3 rounded-2xl font-bold">+ 创建新工单</button>
        </div>
        <div class="bg-[#11141b] rounded-[2rem] border border-white/5 overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-white/5 text-[10px] text-slate-500">
                    <tr><th class="p-6">工单名称</th><th class="p-6">关联策略</th><th class="p-6">创建日期</th><th class="p-6 text-right">操作</th></tr>
                </thead>
                <tbody class="text-sm divide-y divide-white/5">
                    {% for t in data.tickets %}
                    <tr><td class="p-6 font-bold text-green-500">{{t[1]}}</td><td class="p-6">{{t[5]}}</td><td class="p-6 text-slate-500">{{t[4]}}</td><td class="p-6 text-right"><button class="text-blue-500">更换策略</button></td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <dialog id="tBox" class="bg-[#11141b] p-8 rounded-[2rem] border border-white/10 text-slate-300 w-[450px]">
            <form action="/api/save_ticket" method="post" class="space-y-4">
                <input name="name" placeholder="工单名 (如: 客服01)" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <input name="url" placeholder="跳转目的地" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <select name="p_id" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                    {% for p in data.policies %}<option value="{{p[0]}}">应用策略: {{p[1]}}</option>{% endfor %}
                </select>
                <button class="w-full bg-green-600 py-4 rounded-2xl font-bold">创建工单</button>
            </form>
        </dialog>

        {% elif tab == 'links' %}
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-2xl font-bold">短链汇总</h2>
            <button onclick="lBox.showModal()" class="bg-blue-600 px-6 py-3 rounded-2xl font-bold">+ 生成短链</button>
        </div>
        <div class="bg-[#11141b] rounded-[2rem] border border-white/5 overflow-hidden">
            <table class="w-full text-left">
                <thead class="bg-white/5 text-[10px] text-slate-500 uppercase">
                    <tr><th class="p-6">日期</th><th class="p-6">域名前缀</th><th class="p-6">短链</th><th class="p-6">关联工单</th><th class="p-6 text-right">管理</th></tr>
                </thead>
                <tbody class="text-sm divide-y divide-white/5">
                    {% for l in data.links %}
                    <tr><td class="p-6 text-slate-500">{{l[1][:10]}}</td><td class="p-6 text-blue-400 underline">{{l[2]}}</td><td class="p-6 font-mono font-bold">/{{l[3]}}</td><td class="p-6">{{l[5]}}</td><td class="p-6 text-right space-x-4"><a href="/{{l[3]}}" target="_blank" class="text-green-500">测试</a><button class="text-blue-500">编辑工单</button></td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <dialog id="lBox" class="bg-[#11141b] p-8 rounded-[2rem] border border-white/10 text-slate-300 w-[450px]">
            <form action="/api/save_link" method="post" class="space-y-4">
                <input name="n" placeholder="备注名称" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <select name="domain" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                    <option value="https://s1.security.com">域名方案 A: s1.security.com</option>
                    <option value="https://api.sentinel.pro">域名方案 B: api.sentinel.pro</option>
                </select>
                <select name="tid" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                    {% for t in data.tickets %}<option value="{{t[0]}}">指向工单: {{t[1]}}</option>{% endfor %}
                </select>
                <button class="w-full bg-blue-600 py-4 rounded-2xl font-bold">立即部署</button>
            </form>
        </dialog>

        {% elif tab == 'logs' %}
        <h2 class="text-2xl font-bold mb-8">穿透日志库</h2>
        <div class="bg-[#11141b] rounded-[2rem] border border-white/5 overflow-hidden text-xs">
            <table class="w-full text-left">
                <thead class="bg-white/5 text-slate-500 font-bold uppercase">
                    <tr><th class="p-6">时间 (北京)</th><th class="p-6">IP 地址</th><th class="p-6">状态</th><th class="p-6">原因</th></tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for log in data.logs %}
                    <tr class="{{ 'bg-red-500/5' if log[4]=='拦截' else '' }}"><td class="p-6 font-mono text-slate-500">{{log[1]}}</td><td class="p-6">{{log[3]}}</td><td class="p-6 font-bold">{{log[4]}}</td><td class="p-6 italic text-slate-400">{{log[5]}}</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </main>
</body>
"""

init_db()
if __name__ == '__main__':
    app.run(debug=True)
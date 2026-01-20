import os, sqlite3, random, string, datetime, urllib.parse
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v8_minimalist"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v8.db')

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 账户表
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, u TEXT UNIQUE, p TEXT, n TEXT)')
    # 工单表 (存放跳转目的地)
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, target_url TEXT)')
    # 防护规则表 (国家、语言、设备、跳转地址)
    c.execute('CREATE TABLE IF NOT EXISTS security (id INTEGER PRIMARY KEY, white_countries TEXT, block_pc INTEGER, block_vpn INTEGER, redirect_url TEXT)')
    # 短链汇总表 (关联工单)
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER)')
    # 访问日志
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    
    # 初始化默认安全配置
    c.execute("INSERT OR IGNORE INTO security (id, white_countries, block_pc, block_vpn, redirect_url) VALUES (1, 'US', 1, 1, 'https://google.com')")
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('admin', 'admin888', 'ROOT')")
    conn.commit(); conn.close()

# --- 核心拦截与转发引擎 ---
@app.route('/<code>')
def gateway(code):
    reserved = ['admin', 'create_user', 'create_link', 'create_ticket', 'update_security', 'delete', 'static']
    if code in reserved: return abort(404)
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 查询短链关联的工单和当前安全规则
    c.execute("SELECT t.target_url, s.* FROM mapping m JOIN tickets t ON m.ticket_id = t.id CROSS JOIN security s WHERE m.code=?", (code,))
    res = c.fetchone()
    
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    ua = request.user_agent.string.lower()
    now = datetime.datetime.now().strftime("%H:%M:%S")
    
    if not res: return "404", 404

    target, _, white_countries, b_pc, b_vpn, r_url = res
    is_blocked = 0; reason = "Passed"

    # 1. 拦截爬虫与电脑端
    is_pc = not any(x in ua for x in ['iphone', 'android', 'mobile'])
    if b_pc and is_pc:
        is_blocked, reason = 1, "拦截电脑端访问"
    
    # 2. 模拟爬虫简单检测
    if any(x in ua for x in ['bot', 'spider', 'crawler']):
        is_blocked, reason = 1, "拦截爬虫程序"

    # 写入日志
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
    if tab == 'users': c.execute("SELECT * FROM users"); data['users'] = c.fetchall()
    elif tab == 'links': 
        c.execute("SELECT m.*, t.name FROM mapping m LEFT JOIN tickets t ON m.ticket_id = t.id")
        data['links'] = c.fetchall()
        c.execute("SELECT id, name FROM tickets"); data['tickets'] = c.fetchall()
    elif tab == 'tickets': c.execute("SELECT * FROM tickets"); data['tickets'] = c.fetchall()
    elif tab == 'logs': c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50"); data['logs'] = c.fetchall()
    elif tab == 'security': c.execute("SELECT * FROM security WHERE id=1"); data['sec'] = c.fetchone()
    conn.close()
    return render_template_string(V8_UI, tab=tab, data=data)

# --- 功能接口 (修复 404 问题) ---
@app.route('/create_user', methods=['POST'])
def create_user():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO users (u, p, n) VALUES (?,?,?)", (request.form['u'], request.form['p'], request.form['n']))
    conn.commit(); conn.close()
    return redirect('/admin?tab=users')

@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO tickets (name, target_url) VALUES (?,?)", (request.form['name'], request.form['url']))
    conn.commit(); conn.close()
    return redirect('/admin?tab=tickets')

@app.route('/create_link', methods=['POST'])
def create_link():
    code = ''.join(random.choice(string.ascii_letters) for _ in range(5))
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO mapping (date, code, title, ticket_id) VALUES (?,?,?,?)",
              (datetime.datetime.now().strftime("%Y-%m-%d"), code, request.form['n'], request.form['tid']))
    conn.commit(); conn.close()
    return redirect('/admin?tab=links')

@app.route('/update_security', methods=['POST'])
def update_security():
    f = request.form
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE security SET white_countries=?, block_pc=?, redirect_url=? WHERE id=1",
              (f['countries'], f.get('b_pc', 0), f['r_url']))
    conn.commit(); conn.close()
    return redirect('/admin?tab=security')

V8_UI = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0f1117] text-slate-300 flex h-screen overflow-hidden">
    <nav class="w-64 bg-[#161922] border-r border-white/5 flex flex-col p-6">
        <h1 class="text-blue-500 font-black text-xl mb-10 italic">SENTINEL V8</h1>
        <div class="space-y-2">
            <a href="?tab=users" class="block p-3 rounded-xl {{ 'bg-blue-600' if tab=='users' }}">👤 创建账户</a>
            <a href="?tab=tickets" class="block p-3 rounded-xl {{ 'bg-blue-600' if tab=='tickets' }}">🎫 创建工单</a>
            <a href="?tab=links" class="block p-3 rounded-xl {{ 'bg-blue-600' if tab=='links' }}">🔗 短链汇总</a>
            <a href="?tab=security" class="block p-3 rounded-xl {{ 'bg-blue-600' if tab=='security' }}">🛡️ 防护规则</a>
            <a href="?tab=logs" class="block p-3 rounded-xl {{ 'bg-blue-600' if tab=='logs' }}">📊 访问日志</a>
        </div>
    </nav>
    <main class="flex-1 p-10 overflow-y-auto">
        {% if tab == 'users' %}
        <h2 class="text-xl font-bold mb-4">编辑子账户</h2>
        <form action="/create_user" method="post" class="bg-[#161922] p-6 rounded-2xl space-y-4">
            <input name="u" placeholder="账户ID" class="w-full bg-slate-900 p-3 rounded-xl outline-none">
            <input name="p" placeholder="密码" class="w-full bg-slate-900 p-3 rounded-xl outline-none">
            <input name="n" placeholder="备注" class="w-full bg-slate-900 p-3 rounded-xl outline-none">
            <button class="w-full bg-blue-600 py-3 rounded-xl font-bold">保存账户</button>
        </form>
        <div class="mt-6 space-y-2">
            {% for u in data.users %}<div class="bg-white/5 p-3 rounded-lg">{{ u[1] }} - {{ u[3] }}</div>{% endfor %}
        </div>

        {% elif tab == 'tickets' %}
        <h2 class="text-xl font-bold mb-4">创建工单 (目的地管理)</h2>
        <form action="/create_ticket" method="post" class="bg-[#161922] p-6 rounded-2xl space-y-4">
            <input name="name" placeholder="工单名称 (如: 客服01)" class="w-full bg-slate-900 p-3 rounded-xl outline-none">
            <input name="url" placeholder="跳转目的地 (WhatsApp链接)" class="w-full bg-slate-900 p-3 rounded-xl outline-none">
            <button class="w-full bg-blue-600 py-3 rounded-xl font-bold">入库工单</button>
        </form>

        {% elif tab == 'links' %}
        <div class="flex justify-between mb-6">
            <h2 class="text-xl font-bold">短链汇总</h2>
            <button onclick="lBox.showModal()" class="bg-blue-600 px-4 py-2 rounded-xl text-xs">+ 生成短链</button>
        </div>
        <table class="w-full text-left text-xs bg-[#161922] rounded-2xl overflow-hidden">
            <thead class="bg-white/5"><tr><th class="p-4">备注</th><th class="p-4">短链</th><th class="p-4">当前工单</th><th class="p-4">操作</th></tr></thead>
            <tbody>
                {% for l in data.links %}
                <tr class="border-t border-white/5"><td class="p-4">{{ l[3] }}</td><td class="p-4 text-blue-400">/{{ l[2] }}</td><td class="p-4">{{ l[5] }}</td><td class="p-4"><a href="/{{l[2]}}" target="_blank">测试</a></td></tr>
                {% endfor %}
            </tbody>
        </table>
        <dialog id="lBox" class="bg-[#161922] p-6 rounded-2xl text-slate-300 w-80">
            <form action="/create_link" method="post" class="space-y-4">
                <input name="n" placeholder="短链备注" class="w-full bg-slate-900 p-3 rounded-xl outline-none">
                <select name="tid" class="w-full bg-slate-900 p-3 rounded-xl outline-none">
                    {% for t in data.tickets %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}
                </select>
                <button class="w-full bg-blue-600 py-3 rounded-xl font-bold">生成</button>
            </form>
        </dialog>

        {% elif tab == 'security' %}
        <h2 class="text-xl font-bold mb-4">全局防护规则</h2>
        <form action="/update_security" method="post" class="bg-[#161922] p-8 rounded-2xl space-y-6">
            <div>
                <label class="text-xs text-slate-500">允许的国家代码 (逗号分隔，如: US,HK)</label>
                <input name="countries" value="{{ data.sec[1] }}" class="w-full bg-slate-900 p-3 rounded-xl mt-2 outline-none">
            </div>
            <div class="flex items-center gap-4">
                <label><input type="checkbox" name="b_pc" value="1" {{ 'checked' if data.sec[2] }}> 拦截电脑端</label>
                <label><input type="checkbox" name="b_bot" value="1" checked disabled> 自动拦截爬虫</label>
            </div>
            <div>
                <label class="text-xs text-slate-500">拦截后跳转地址</label>
                <input name="r_url" value="{{ data.sec[4] }}" class="w-full bg-slate-900 p-3 rounded-xl mt-2 outline-none">
            </div>
            <button class="w-full bg-green-600 py-3 rounded-xl font-bold font-bold">保存并实时生效</button>
        </form>

        {% elif tab == 'logs' %}
        <h2 class="text-xl font-bold mb-4">访问日志</h2>
        <table class="w-full text-xs bg-[#161922] rounded-2xl overflow-hidden">
            <thead class="bg-white/5"><tr><th class="p-4">时间</th><th class="p-4">IP</th><th class="p-4">状态</th><th class="p-4">原因</th></tr></thead>
            <tbody>
                {% for log in data.logs %}<tr class="border-t border-white/5"><td class="p-4">{{log[1]}}</td><td class="p-4">{{log[3]}}</td><td class="p-4 font-bold">{{log[4]}}</td><td class="p-4 text-slate-500">{{log[5]}}</td></tr>{% endfor %}
            </tbody>
        </table>
        {% endif %}
    </main>
</body>
"""

init_db()
if __name__ == '__main__':
    app.run(debug=True)
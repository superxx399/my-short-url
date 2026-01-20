import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_minimalist_pro"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v7.db')

# --- 1. 数据库初始化 ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 账户表
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, note TEXT)')
    # 短链汇总表 (增加工单分配字段)
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, create_date TEXT, short_code TEXT UNIQUE, 
                 target_url TEXT, worker_id TEXT, title TEXT)''')
    # 访问日志表
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
                 id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, 
                 referer TEXT, status TEXT, reason TEXT)''')
    # 默认管理员
    c.execute("INSERT OR IGNORE INTO users (username, password, note) VALUES ('admin', 'admin888', 'ROOT')")
    conn.commit(); conn.close()

# --- 2. 核心拦截转发逻辑 ---
@app.route('/<short_code>')
def redirect_engine(short_code):
    reserved = ['admin', 'create_user', 'create_link', 'logs', 'static']
    if short_code in reserved: return abort(404)
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT target_url, title FROM mapping WHERE short_code=?", (short_code,))
    res = c.fetchone()
    
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    now = datetime.datetime.now().strftime("%m-%d %H:%M")
    
    if not res:
        c.execute("INSERT INTO logs (time, code, ip, referer, status, reason) VALUES (?,?,?,?,?,?)",
                  (now, short_code, ip, request.referrer, "失败", "短链不存在"))
        conn.commit(); conn.close()
        return "404 Not Found", 404

    # 这里可以根据你的需求添加“设备/国家”拦截逻辑，如果通过则：
    c.execute("INSERT INTO logs (time, code, ip, referer, status, reason) VALUES (?,?,?,?,?,?)",
              (now, short_code, ip, request.referrer, "成功", "已放行"))
    conn.commit(); conn.close()
    return redirect(res[0])

# --- 3. 极简管理后台 ---
@app.route('/admin')
def admin():
    tab = request.args.get('tab', 'links') # 默认显示短链汇总
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    
    data = {}
    if tab == 'users':
        c.execute("SELECT * FROM users")
        data['users'] = c.fetchall()
    elif tab == 'links':
        c.execute("SELECT * FROM mapping ORDER BY id DESC")
        data['links'] = c.fetchall()
    elif tab == 'logs':
        c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 100")
        data['logs'] = c.fetchall()
    
    conn.close()
    return render_template_string(BASE_UI, tab=tab, data=data)

# --- 4. 功能接口 ---
@app.route('/create_user', methods=['POST'])
def create_user():
    u, p, n = request.form['u'], request.form['p'], request.form['n']
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, note) VALUES (?,?,?)", (u, p, n))
        conn.commit()
    except: pass
    finally: conn.close()
    return redirect('/admin?tab=users')

@app.route('/create_link', methods=['POST'])
def create_link():
    t, u, w, n = request.form['t'], request.form['u'], request.form['w'], request.form['n']
    code = ''.join(random.choice(string.ascii_letters) for _ in range(5))
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO mapping (create_date, short_code, target_url, worker_id, title) VALUES (?,?,?,?,?)",
              (datetime.datetime.now().strftime("%Y-%m-%d"), code, u, w, n))
    conn.commit(); conn.close()
    return redirect('/admin?tab=links')

# --- 5. 极致简洁 UI 模板 ---
BASE_UI = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0f1117] text-slate-300 flex h-screen overflow-hidden font-sans">
    <nav class="w-64 bg-[#161922] border-r border-white/5 flex flex-col p-6">
        <h1 class="text-blue-500 font-black italic text-xl mb-10 tracking-tighter">SENTINEL CENTER</h1>
        <div class="space-y-2 flex-1">
            <a href="?tab=users" class="flex items-center gap-3 p-3 rounded-xl transition {{ 'bg-blue-600 text-white' if tab=='users' else 'hover:bg-white/5' }}">
                <span class="text-sm font-bold">👤 创建账户</span>
            </a>
            <a href="?tab=links" class="flex items-center gap-3 p-3 rounded-xl transition {{ 'bg-blue-600 text-white' if tab=='links' else 'hover:bg-white/5' }}">
                <span class="text-sm font-bold">🔗 短链汇总</span>
            </a>
            <a href="?tab=logs" class="flex items-center gap-3 p-3 rounded-xl transition {{ 'bg-blue-600 text-white' if tab=='logs' else 'hover:bg-white/5' }}">
                <span class="text-sm font-bold">📊 访问日志</span>
            </a>
        </div>
        <div class="text-[10px] text-slate-600 border-t border-white/5 pt-4 uppercase">System Version 7.0</div>
    </nav>

    <main class="flex-1 overflow-y-auto p-10 bg-[#0f1117]">
        {% if tab == 'users' %}
        <section class="max-w-2xl">
            <h2 class="text-xl font-bold mb-6">创建新账户</h2>
            <form action="/create_user" method="post" class="space-y-4 bg-[#161922] p-8 rounded-3xl border border-white/5">
                <input name="u" placeholder="账户名 (ID)" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none focus:border-blue-500 text-sm">
                <input name="p" type="password" placeholder="访问密码" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none focus:border-blue-500 text-sm">
                <input name="n" placeholder="备注 (如：东南亚组)" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none focus:border-blue-500 text-sm">
                <button class="bg-blue-600 w-full py-3 rounded-xl font-bold text-white shadow-lg">确认创建账户</button>
            </form>
        </section>

        {% elif tab == 'links' %}
        <section>
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-xl font-bold">短链汇总控制台</h2>
                <button onclick="document.getElementById('linkModal').showModal()" class="bg-blue-600 px-4 py-2 rounded-xl text-xs font-bold text-white">+ 新增短链</button>
            </div>
            <div class="bg-[#161922] rounded-3xl border border-white/5 overflow-hidden">
                <table class="w-full text-left text-xs">
                    <thead class="bg-white/5 text-slate-500 uppercase">
                        <tr><th class="p-5">日期</th><th class="p-5">备注名称</th><th class="p-5">短链入口</th><th class="p-5">工单分配</th><th class="p-5 text-right">操作</th></tr>
                    </thead>
                    <tbody class="divide-y divide-white/5">
                        {% for l in data.links %}
                        <tr class="hover:bg-white/5 transition">
                            <td class="p-5">{{ l[1] }}</td>
                            <td class="p-5 font-bold">{{ l[5] }}</td>
                            <td class="p-5 text-blue-400">/{{ l[2] }}</td>
                            <td class="p-5 font-mono text-slate-500">{{ l[4] or '未分配' }}</td>
                            <td class="p-5 text-right space-x-3">
                                <a href="/{{ l[2] }}" target="_blank" class="text-green-500 hover:underline">测试</a>
                                <button class="text-blue-500">编辑</button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </section>

        {% elif tab == 'logs' %}
        <section>
            <h2 class="text-xl font-bold mb-6">实时访问与拦截审计</h2>
            <div class="bg-[#161922] rounded-3xl border border-white/5 overflow-hidden">
                <table class="w-full text-left text-[10px] md:text-xs">
                    <thead class="bg-white/5 text-slate-500 uppercase">
                        <tr><th class="p-5">访问时间</th><th class="p-5">短链</th><th class="p-5">状态</th><th class="p-5">拦截原因</th><th class="p-5">访问来路</th></tr>
                    </thead>
                    <tbody class="divide-y divide-white/5">
                        {% for log in data.logs %}
                        <tr class="{{ 'bg-red-500/5' if log[5]=='失败' else '' }}">
                            <td class="p-5 text-slate-500">{{ log[1] }}</td>
                            <td class="p-5 font-bold">/{{ log[2] }}</td>
                            <td class="p-5">
                                <span class="{{ 'text-red-500' if log[5]=='失败' else 'text-green-500' }} font-bold">{{ log[5] }}</span>
                            </td>
                            <td class="p-5 italic text-slate-500">{{ log[6] }}</td>
                            <td class="p-5 text-slate-600 truncate max-w-[150px]">{{ log[4] or '直接访问' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </section>
        {% endif %}
    </main>

    <dialog id="linkModal" class="bg-[#161922] p-8 rounded-[2rem] border border-white/10 text-slate-300 w-96 backdrop:bg-black/80">
        <form action="/create_link" method="post" class="space-y-4">
            <h3 class="font-bold text-lg mb-4">部署新短链</h3>
            <input name="n" placeholder="备注名称" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none text-sm">
            <input name="u" placeholder="目标 URL" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none text-sm">
            <input name="w" placeholder="工单分配 ID" class="w-full bg-slate-900 border border-slate-800 p-3 rounded-xl outline-none text-sm">
            <div class="flex gap-3">
                <button type="button" onclick="this.closest('dialog').close()" class="flex-1 py-3 text-slate-500">取消</button>
                <button class="flex-1 bg-blue-600 py-3 rounded-xl font-bold text-white">确认</button>
            </div>
        </form>
    </dialog>
</body>
"""

init_db()
if __name__ == '__main__':
    app.run(debug=True)
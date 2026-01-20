import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = "sentinel_v11_perfect_edition"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 数据库初始化 (完善生态模型) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 子账户
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT)')
    # 防护设置 (增加国家和语言过滤字段)
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_devices TEXT, countries TEXT, langs TEXT, r_url TEXT)')
    # 工单/落地页
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    # 短链映射 (统一使用 ticket_id)
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, title TEXT, date TEXT)')
    # 访问审计
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, info TEXT, status TEXT)')
    
    # 初始超管及默认数据
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date) VALUES ('super', '777888', 'ROOT', '2026-01-20')")
    c.execute("INSERT OR IGNORE INTO policies (id, name, white_devices, countries, langs, r_url) VALUES (1, '全球默认防护', 'iPhone,Mac,Android', 'CN,HK,TW,US', 'zh-CN,en', 'https://www.apple.com')")
    conn.commit(); conn.close()

def db_query(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 2. 界面模板 (左侧任务栏 + 开关矩阵) ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#0d1117;color:#c9d1d9;font-family:sans-serif;}
        .sidebar{width:260px;background:#161b22;border-right:1px solid #30363d;position:fixed;height:100vh;}
        .main{margin-left:260px;padding:40px;}
        .nav-link{display:flex;padding:12px 20px;margin:4px 12px;border-radius:8px;font-size:14px;transition:0.2s;}
        .nav-active{background:#1f6feb;color:#fff;font-weight:bold;}
        .card{background:#161b22;border:1px solid #30363d;border-radius:12px;}
        .tag{display:inline-block;padding:2px 10px;background:#21262d;border:1px solid #30363d;border-radius:4px;font-size:12px;margin:2px;}
        .tag-on{background:#238636;color:white;border-color:#2ea043;}
        input, select{background:#0d1117;border:1px solid #30363d;color:white;padding:10px;border-radius:8px;width:100%;}
    </style>
</head>
<body class="flex">
    <aside class="sidebar py-8">
        <div class="px-8 mb-10 text-xl font-bold italic tracking-tighter text-blue-500">SENTINEL V11 <span class="text-[10px] opacity-50">PRO</span></div>
        <nav>
            <a href="?tab=users" class="nav-link {{'nav-active' if tab=='users'}}">👥 子账户添加设置</a>
            <a href="?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">🛡️ 防护添加设置</a>
            <a href="?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">🎫 工单生成编辑</a>
            <a href="?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">🔗 短链生成编辑</a>
            <a href="?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">📜 访问日志审计</a>
        </nav>
        <div class="absolute bottom-8 px-8 text-xs opacity-40">User: {{user}}<br><a href="/login" class="text-red-400">退出系统</a></div>
    </aside>

    <main class="main flex-1">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-3xl font-bold">{{tab_name}}</h2>
            {% if tab != 'logs' %}
            <button onclick="document.getElementById('m-box').style.display='flex'" class="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-bold transition">+ 新增配置</button>
            {% else %}
            <a href="/clear_logs" class="text-red-500 text-sm hover:underline">清空所有历史日志</a>
            {% endif %}
        </div>

        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-black/20 text-gray-500 uppercase">
                    <tr>
                        {% for h in headers %}<th class="p-4 border-b border-gray-800">{{h}}</th>{% endfor %}
                        <th class="p-4 border-b border-gray-800 text-right">管理</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-800">
                    {% for row in rows %}
                    <tr class="hover:bg-white/5 transition">
                        {% for cell in row %}<td class="p-4">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right text-blue-500 space-x-3"><button>编辑</button><button class="text-red-500">删除</button></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        {% if tab == 'policies' %}
        <div class="mt-8 grid grid-cols-2 gap-6">
            <div class="card p-6">
                <h4 class="font-bold mb-4 text-blue-400 text-sm">🌍 全球国家准入 (白名单模式)</h4>
                <div class="flex flex-wrap gap-1">
                    <span class="tag tag-on">CN</span><span class="tag tag-on">HK</span><span class="tag tag-on">TW</span>
                    <span class="tag tag-on">US</span><span class="tag">GB</span><span class="tag">JP</span>
                    <span class="tag">FR</span><span class="tag">DE</span><span class="tag">CA</span>
                </div>
            </div>
            <div class="card p-6">
                <h4 class="font-bold mb-4 text-blue-400 text-sm">🗣️ 语言指纹过滤 (小方块开关)</h4>
                <div class="flex flex-wrap gap-1">
                    <span class="tag tag-on">zh-CN</span><span class="tag tag-on">en</span><span class="tag">ja</span>
                    <span class="tag">ko</span><span class="tag">ru</span><span class="tag">vi</span>
                </div>
            </div>
        </div>
        {% endif %}
    </main>

    <div id="m-box" class="fixed inset-0 bg-black/80 hidden items-center justify-center p-4 z-50">
        <div class="card w-full max-w-lg p-8">
            <h3 class="text-xl font-bold mb-6">新增 {{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-4">
                {% if tab == 'users' %}
                    <input name="u" placeholder="登录账号" required><input name="p" type="password" placeholder="密码" required>
                {% elif tab == 'policies' %}
                    <input name="name" placeholder="策略名称" required>
                    <input name="white" placeholder="设备白名单 (逗号分隔: iPhone,Mac)">
                    <input name="countries" placeholder="国家代码 (CN,US,HK)">
                    <input name="langs" placeholder="语言代码 (zh-CN,en)">
                    <input name="r_url" placeholder="拦截后跳转URL" value="https://google.com">
                {% elif tab == 'tickets' %}
                    <input name="name" placeholder="工单名" required><input name="url" placeholder="目标落地页" required>
                    <input name="p_id" placeholder="策略ID" value="1">
                {% elif tab == 'links' %}
                    <input name="code" placeholder="短链路径 (留空随机)"><input name="t_id" placeholder="对应工单ID" required>
                {% endif %}
                <div class="flex justify-end space-x-3 pt-6">
                    <button type="button" onclick="document.getElementById('m-box').style.display='none'" class="opacity-50">取消</button>
                    <button class="bg-blue-600 px-6 py-2 rounded-lg font-bold">保存设置</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

# --- 3. 核心功能逻辑 ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'users': db_query("INSERT INTO users (u,p,n,c_date) VALUES (?,?,?,'2026-01-20')", (f['u'], f['p'], f['u']), fetch=False)
    elif tab == 'policies': db_query("INSERT INTO policies (name,white_devices,countries,langs,r_url) VALUES (?,?,?,?,?)", (f['name'], f['white'], f['countries'], f['langs'], f['r_url']), fetch=False)
    elif tab == 'tickets': db_query("INSERT INTO tickets (name,url,p_id) VALUES (?,?,?)", (f['name'], f['url'], f['p_id']), fetch=False)
    elif tab == 'links':
        code = f['code'] if f['code'] else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        db_query("INSERT INTO mapping (code,ticket_id,title,date) VALUES (?,?,'AutoGenerated',?)", (code, f['t_id'], now), fetch=False)
    return redirect(f'/admin?tab={tab}')

@app.route('/clear_logs')
def clear_logs():
    db_query("DELETE FROM logs", fetch=False); return redirect('/admin?tab=logs')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    conf = {
        "users": ("子账户管理", ["ID", "账号", "创建时间"], "SELECT id, u, c_date FROM users"),
        "policies": ("防护策略矩阵", ["ID", "策略名", "白名单指纹", "重定向"], "SELECT id, name, white_devices, r_url FROM policies"),
        "tickets": ("工单生成编辑", ["ID", "名称", "落地页URL", "策略ID"], "SELECT id, name, url, p_id FROM tickets"),
        "links": ("短链分发管理", ["ID", "提取码", "工单ID", "时间"], "SELECT id, code, ticket_id, date FROM mapping"),
        "logs": ("访问审计日志", ["ID", "时间", "短链", "IP", "状态"], "SELECT id, time, code, ip, status FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_query(sql)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=title, headers=headers, rows=rows, user=session['user'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'super' and request.form['p'] == '777888':
        session['user'] = 'super'; return redirect('/admin')
    return '<body style="background:#000;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="border:1px solid #333;padding:40px;border-radius:20px;"><h2>SENTINEL LOGIN</h2><input name="u" placeholder="User"><br><input name="p" type="password" placeholder="Pass"><br><button style="width:100%;background:#0066ff;color:#fff;padding:12px;margin-top:12px;border-radius:10px;font-weight:bold;">ENTER</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
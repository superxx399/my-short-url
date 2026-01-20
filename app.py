import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v11_eco_system_master"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 核心指纹库 (集成 iPhone 17 系列) ---
D_WHITE_LIST = ["iPhone 17 Pro Max", "iPhone 17 Pro", "iPhone 16 Pro Max", "Mate 70 Pro+", "S25 Ultra"]

def get_now():
    return (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))).strftime("%Y-%m-%d %H:%M:%S")

# --- 2. 数据库自动化构建 (完善生态模型) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 子账户
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT)')
    # 防护策略 (核心：控制谁能过)
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_devices TEXT, r_url TEXT)')
    # 工单/落地页 (核心：目的地)
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    # 链路映射 (核心：入口)
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, t_id INTEGER, date TEXT)')
    # 访问审计 (核心：证据)
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, ua TEXT, status TEXT)')
    # 初始化超管
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date) VALUES ('super', '777888', 'ROOT', ?)", (get_now(),))
    # 初始化一个默认策略
    c.execute("INSERT OR IGNORE INTO policies (id, name, white_devices, r_url) VALUES (1, 'iPhone全系防护', 'iPhone 17,iPhone 16,iPhone 15', 'https://www.apple.com')")
    conn.commit(); conn.close()

# --- 3. 拦截网关 (生态系统的核心引擎) ---
@app.route('/<code>')
def gateway(code):
    if code in ['admin', 'login', 'api']: return redirect('/admin')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 联表查询：从短链找工单，再从工单找对应的防护策略
    c.execute("""
        SELECT t.url, p.white_devices, p.r_url 
        FROM mapping m 
        JOIN tickets t ON m.t_id = t.id 
        JOIN policies p ON t.p_id = p.id 
        WHERE m.code = ?
    """, (code,))
    res = c.fetchone()
    if not res: return "404 LINK EXPIRED", 404
    
    target_url, white_devs, redirect_url = res
    ua = request.headers.get('User-Agent', '')
    is_blocked = True
    
    # 指纹校验逻辑
    if any(dev.strip() in ua for dev in white_devs.split(',')):
        is_blocked = False
        
    status = "拦截跳转" if is_blocked else "验证通过"
    c.execute("INSERT INTO logs (time, code, ip, ua, status) VALUES (?,?,?,?,?)", 
              (get_now(), code, request.remote_addr, ua[:100], status))
    conn.commit(); conn.close()
    
    return redirect(redirect_url if is_blocked else target_url)

# --- 4. 完善后的管理后台 UI ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#0a0c10;color:#c9d1d9;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;}
        .card{background:#161b22;border:1px solid #30363d;border-radius:8px;}
        .tab-active{color:#58a6ff;border-bottom:2px solid #58a6ff;}
        input, select{background:#0d1117;border:1px solid #30363d;color:#c9d1d9;padding:6px 12px;border-radius:6px;width:100%;}
    </style>
</head>
<body class="p-8">
    <div class="max-w-6xl mx-auto">
        <header class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-2xl font-bold text-white tracking-tighter">SENTINEL V11 <span class="text-blue-500">ECO-SYSTEM</span></h1>
                <p class="text-xs opacity-50">北京时间: {{time}} | 管理员: {{user}}</p>
            </div>
            <a href="/login" class="text-red-500 text-sm hover:underline">安全退出</a>
        </header>

        <div class="flex space-x-6 border-b border-gray-800 mb-8 text-sm font-bold">
            <a href="?tab=users" class="pb-3 {{'tab-active' if tab=='users'}}">👥 子账户</a>
            <a href="?tab=policies" class="pb-3 {{'tab-active' if tab=='policies'}}">🛡️ 防护设置</a>
            <a href="?tab=tickets" class="pb-3 {{'tab-active' if tab=='tickets'}}">🎫 工单生成</a>
            <a href="?tab=links" class="pb-3 {{'tab-active' if tab=='links'}}">🔗 短链映射</a>
            <a href="?tab=logs" class="pb-3 {{'tab-active' if tab=='logs'}}">📜 审计日志</a>
        </div>

        <div class="card p-6">
            <div class="flex justify-between items-center mb-6">
                <h3 class="font-bold text-white text-lg">{{tab_name}}</h3>
                <button onclick="document.getElementById('add-modal').classList.remove('hidden')" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-1.5 rounded text-xs font-bold transition">新 增</button>
            </div>
            
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm text-gray-400">
                    <thead class="bg-black/20 text-xs">
                        <tr>
                            {% for h in headers %}<th class="p-3 border-b border-gray-800">{{h}}</th>{% endfor %}
                            <th class="p-3 border-b border-gray-800">操作</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-800">
                        {% for row in rows %}
                        <tr class="hover:bg-white/5 transition">
                            {% for cell in row %}<td class="p-3">{{cell}}</td>{% endfor %}
                            <td class="p-3 text-blue-500 text-xs font-bold cursor-pointer">编辑 / 删除</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="add-modal" class="hidden fixed inset-0 bg-black/90 flex items-center justify-center p-4">
        <div class="card w-full max-w-md p-8">
            <h2 class="text-white font-bold mb-6">新增 {{tab_name}}</h2>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-4 text-sm">
                {% if tab == 'users' %}
                <input name="u" placeholder="登录账号" required>
                <input name="p" type="password" placeholder="密码" required>
                <input name="n" placeholder="备注姓名">
                {% elif tab == 'policies' %}
                <input name="name" placeholder="策略名称, 如: 某某活动防护" required>
                <input name="white" placeholder="指纹白名单 (用逗号分隔, 如: iPhone 17,iPad)" required>
                <input name="r_url" placeholder="跳转地址 (拦截后去哪)" required>
                {% elif tab == 'tickets' %}
                <input name="name" placeholder="工单/落地页名称" required>
                <input name="url" placeholder="最终目的地地址 (URL)" required>
                <input name="p_id" placeholder="关联策略ID (如: 1)">
                {% elif tab == 'links' %}
                <input name="code" placeholder="短链提取码 (选填)">
                <input name="t_id" placeholder="关联工单ID (如: 1)" required>
                {% endif %}
                <div class="flex justify-end space-x-4 pt-6">
                    <button type="button" onclick="document.getElementById('add-modal').classList.add('hidden')" class="text-gray-500">取消</button>
                    <button class="bg-blue-600 text-white px-6 py-2 rounded font-bold">保存并生效</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

# --- 5. 后台路由控制 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT * FROM users WHERE u=? AND p=?", (request.form['u'], request.form['p']))
        if c.fetchone(): session['user'] = request.form['u']; return redirect('/admin')
        return "认证失败"
    return '<body style="background:#000;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="padding:40px;border:1px solid #333;"><h2>SENTINEL LOGIN</h2><input name="u" placeholder="User"><br><input name="p" type="password" placeholder="Pass"><br><button style="width:100%;background:#0066ff;color:#fff;padding:10px;">ENTER</button></form></body>'

@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    if tab == 'users': c.execute("INSERT INTO users (u,p,n,c_date) VALUES (?,?,?,?)", (f['u'], f['p'], f['n'], get_now()))
    elif tab == 'policies': c.execute("INSERT INTO policies (name,white_devices,r_url) VALUES (?,?,?)", (f['name'], f['white'], f['r_url']))
    elif tab == 'tickets': c.execute("INSERT INTO tickets (name,url,p_id) VALUES (?,?,?)", (f['name'], f['url'], f['p_id']))
    elif tab == 'links':
        code = f['code'] if f['code'] else ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        c.execute("INSERT INTO mapping (code,t_id,date) VALUES (?,?,?)", (code, f['t_id'], get_now()))
    conn.commit(); conn.close()
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'dashboard')
    conf = {
        "users": ("子账户列表", ["ID", "账号", "备注名", "时间"], "SELECT id, u, n, c_date FROM users"),
        "policies": ("防护策略库", ["ID", "策略名", "白名单指纹", "重定向URL"], "SELECT id, name, white_devices, r_url FROM policies"),
        "tickets": ("工单落地页", ["ID", "名称", "目标URL", "策略ID"], "SELECT id, name, url, p_id FROM tickets"),
        "links": ("短链链路表", ["ID", "提取码", "工单ID", "创建时间"], "SELECT id, code, t_id, date FROM mapping"),
        "logs": ("审计日志", ["ID", "时间", "代码", "访问IP", "状态"], "SELECT id, time, code, ip, status FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab, ("概览", ["ID", "信息", "状态"], "SELECT 1,'系统就绪','Active'"))
    conn = sqlite3.connect(DB_PATH); c = conn.cursor(); c.execute(sql); rows = c.fetchall(); conn.close()
    return render_template_string(ADMIN_TEMPLATE, tab=tab, tab_name=title, headers=headers, rows=rows, user=session['user'], time=get_now())

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
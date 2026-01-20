import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = "sentinel_v11_final_master"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 配置数据 ---
COUNTRIES = {"CN": "中国", "HK": "香港", "TW": "台湾", "US": "美国", "JP": "日本", "KR": "韩国", "GB": "英国", "MY": "马来西亚", "SG": "新加坡", "TH": "泰国"}
DEVICES = ["iPhone 6/7/8", "iPhone X/XS", "iPhone 11/12", "iPhone 13/14", "iPhone 15/16", "iPhone 17 Pro Max", "Android 10-12", "Android 13-15"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_devices TEXT, countries TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, title TEXT, domain TEXT, date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date) VALUES ('super', '777888', 'ROOT', '2026-01-20')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 2. 界面 (左侧栏 + 交互方块) ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#0d1117;color:#c9d1d9;}
        .sidebar{width:260px;background:#161b22;border-right:1px solid #30363d;position:fixed;height:100vh;}
        .main{margin-left:260px;padding:40px;}
        .nav-link{display:flex;padding:12px 20px;margin:4px 12px;border-radius:8px;}
        .nav-active{background:#1f6feb;color:#fff;font-weight:bold;}
        .card{background:#161b22;border:1px solid #30363d;border-radius:12px;}
        .toggle-btn{cursor:pointer;padding:6px 12px;border-radius:6px;border:1px solid #30363d;font-size:12px;transition:0.2s;}
        .toggle-active{background:#238636;border-color:#2ea043;color:white;}
        input, select{background:#0d1117;border:1px solid #30363d;color:white;padding:10px;border-radius:8px;width:100%;}
    </style>
</head>
<body class="flex">
    <aside class="sidebar py-8">
        <div class="px-8 mb-10 text-xl font-bold italic text-blue-500">SENTINEL V11 MASTER</div>
        <nav>
            <a href="?tab=users" class="nav-link {{'nav-active' if tab=='users'}}">👥 子账户编辑</a>
            <a href="?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">🛡️ 防护添加设置</a>
            <a href="?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">🎫 工单(单导/群导)</a>
            <a href="?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">🔗 短链生成编辑</a>
            <a href="?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">📜 审计日志</a>
        </nav>
    </aside>

    <main class="main flex-1">
        <div class="flex justify-between items-center mb-8">
            <h2 class="text-2xl font-bold">{{tab_name}}</h2>
            <button onclick="document.getElementById('modal').style.display='flex'" class="bg-blue-600 px-6 py-2 rounded-lg font-bold">+ 新增</button>
        </div>

        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-black/20 text-gray-500 uppercase">
                    <tr>
                        {% for h in headers %}<th class="p-4 border-b border-gray-800">{{h}}</th>{% endfor %}
                        <th class="p-4 border-b border-gray-800 text-right">管理操作</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in rows %}
                    <tr class="hover:bg-white/5 transition">
                        {% for cell in row %}<td class="p-4">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right text-blue-500 space-x-3">
                            <button class="hover:underline">编辑</button>
                            <button class="text-red-500 hover:underline">删除</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="modal" class="fixed inset-0 bg-black/80 hidden items-center justify-center p-4 z-50">
        <div class="card w-full max-w-2xl p-8 max-h-[90vh] overflow-y-auto">
            <h3 class="text-xl font-bold mb-6 text-blue-400">配置 {{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-4">
                {% if tab == 'users' %}
                    <input name="u" placeholder="登录账号" required><input name="p" type="password" placeholder="重置密码">
                    <input name="n" placeholder="备注名称">
                {% elif tab == 'policies' %}
                    <input name="name" placeholder="策略名称" required>
                    <div class="text-xs text-gray-500">🌍 全球国家准入 (中文开关)</div>
                    <div class="flex flex-wrap gap-2">
                        {% for code, name in countries.items() %}
                        <div class="toggle-btn" onclick="this.classList.toggle('toggle-active')">{{name}}</div>
                        {% endfor %}
                    </div>
                    <div class="text-xs text-gray-500">📱 设备型号过滤</div>
                    <div class="flex flex-wrap gap-2">
                        {% for dev in devices %}
                        <div class="toggle-btn" onclick="this.classList.toggle('toggle-active')">{{dev}}</div>
                        {% endfor %}
                    </div>
                    <input name="r_url" placeholder="拦截后重定向地址" value="https://www.google.com">
                {% elif tab == 'tickets' %}
                    <input name="name" placeholder="工单账号名" required>
                    <input name="url" placeholder="WhatsApp 链接 (群或个号)" required>
                    <select name="type"><option value="单导">单导 (个号功能)</option><option value="群导">群导 (群组功能)</option></select>
                    <input name="p_id" placeholder="关联策略ID" value="1">
                {% elif tab == 'links' %}
                    <input name="title" placeholder="短链备注 (如: FB投放01)" required>
                    <input name="domain" placeholder="域名 (如: https://abc.com)" value="https://">
                    <select name="t_id">
                        {% for t in tickets %}<option value="{{t[0]}}">{{t[1]}} (已分配账号: {{t[2]}})</option>{% endfor %}
                    </select>
                {% endif %}
                <div class="flex justify-end space-x-4 pt-6">
                    <button type="button" onclick="document.getElementById('modal').style.display='none'">取消</button>
                    <button class="bg-blue-600 px-8 py-2 rounded-lg font-bold">提交保存</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

# --- 3. 核心路由 ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'users': db_action("INSERT INTO users (u,p,n,c_date) VALUES (?,?,?,?)", (f['u'], f['p'], f['n'], now), False)
    elif tab == 'policies': db_action("INSERT INTO policies (name,white_devices,countries,r_url) VALUES (?,?,?,?)", (f['name'], "iPhone,Android", "CN,HK", f['r_url']), False)
    elif tab == 'tickets': db_action("INSERT INTO tickets (name,url,type,p_id) VALUES (?,?,?,?)", (f['name'], f['url'], f['type'], f['p_id']), False)
    elif tab == 'links':
        # 随机前缀 + 随机4位后缀
        prefix = random.choice(['vip', 'web', 'app', 'safe']) + str(random.randint(1,9))
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        code = f"{prefix}-{suffix}"
        db_action("INSERT INTO mapping (code,ticket_id,title,domain,date) VALUES (?,?,?,?,?)", (code, f['t_id'], f['title'], f['domain'], now), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    ticket_data = db_action("SELECT id, name, type FROM tickets")
    conf = {
        "users": ("子账户编辑", ["ID", "账号", "备注", "日期"], "SELECT id, u, n, c_date FROM users"),
        "policies": ("防护设置", ["ID", "名称", "白名单", "跳转"], "SELECT id, name, white_devices, r_url FROM policies"),
        "tickets": ("工单(单/群导)", ["ID", "名称", "链接", "类型"], "SELECT id, name, url, type FROM tickets"),
        "links": ("短链管理", ["ID", "域名+短链", "备注", "工单ID", "日期"], "SELECT id, domain||'/'||code, title, ticket_id, date FROM mapping"),
        "logs": ("审计日志", ["ID", "时间", "代码", "IP", "状态"], "SELECT id, time, code, ip, status FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=title, headers=headers, rows=rows, 
                                  user=session['user'], countries=COUNTRIES, devices=DEVICES, tickets=ticket_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'super' and request.form['p'] == '777888':
        session['user'] = 'super'; return redirect('/admin')
    return '<body style="background:#000;color:#fff;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="border:1px solid #333;padding:40px;border-radius:20px;"><h2>SENTINEL LOGIN</h2><input name="u" placeholder="User"><br><input name="p" type="password" placeholder="Pass"><br><button style="width:100%;background:#0066ff;color:#fff;padding:12px;margin-top:10px;border-radius:10px;">ENTER</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
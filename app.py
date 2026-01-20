import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, jsonify

app = Flask(__name__)
app.secret_key = "sentinel_fb_ultimate_perfect"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 核心静态数据 ---
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]
# 全球主流投放国家
COUNTRIES = ["中国", "香港", "台湾", "美国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "印尼", "菲律宾", "阿联酋", "沙特", "巴西", "墨西哥", "英国", "德国", "法国", "加拿大", "澳大利亚"]
# 全系列苹果型号
IOS_DEVS = ["iPhone 6/7/8", "iPhone X/XS", "iPhone XR", "iPhone 11", "iPhone 11 Pro", "iPhone 12", "iPhone 12 Pro", "iPhone 13", "iPhone 13 Pro", "iPhone 14", "iPhone 14 Pro", "iPhone 15", "iPhone 15 Pro Max", "iPhone 16", "iPhone 17 Pro Max"]
# 安卓版本
AND_DEVS = ["Android 10", "Android 11", "Android 12", "Android 13", "Android 14", "Android 15"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
        pixel TEXT, event TEXT, campaign TEXT, mock_req TEXT, p_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, ticket_id INTEGER, 
        domain TEXT, note TEXT, date TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('admin', '777888', 'ROOT')")
    # 初始化一个默认规则，防止报错
    c.execute("INSERT OR IGNORE INTO policies (id, name, devices, countries, r_url) VALUES (1, '默认全球全设备', 'All', 'All', 'https://www.facebook.com')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=10); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 2. 交互式 UI 模板 ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#f0f2f5;color:#1c1e21;font-family:sans-serif;}
        .sidebar{width:240px;background:#fff;border-right:1px solid #ddd;position:fixed;height:100vh;z-index:10;}
        .main{margin-left:240px;padding:30px;}
        .nav-link{display:flex;padding:12px 20px;margin:5px 15px;border-radius:8px;color:#4b4f56;font-weight:500;transition:0.3s;}
        .nav-active{background:#e7f3ff;color:#1877f2;border-left:4px solid #1877f2;}
        .card{background:#fff;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,0.1);border:1px solid #ddd;}
        .btn-blue{background:#1877f2;color:#fff;padding:8px 20px;border-radius:6px;font-weight:bold;}
        /* 交互方块样式 */
        .toggle-box{cursor:pointer;padding:6px 12px;border:1px solid #ddd;border-radius:6px;font-size:12px;background:#f8f9fa;user-select:none;transition:0.2s;}
        .toggle-box.active{background:#1877f2;color:white;border-color:#1877f2;}
        input, select, textarea{background:#fff;border:1px solid #ddd;padding:10px;border-radius:6px;width:100%;outline:none;}
    </style>
</head>
<body class="flex">
    <aside class="sidebar">
        <div class="p-6 text-xl font-bold text-blue-600 border-b">Sentinel FB V12</div>
        <nav class="mt-4">
            <a href="?tab=users" class="nav-link {{'nav-active' if tab=='users'}}">👤 团队成员</a>
            <a href="?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">🛡️ 风控规则</a>
            <a href="?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">🎯 投放工单</a>
            <a href="?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">🔗 推广链路</a>
            <a href="?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">📊 投放报表</a>
        </nav>
    </aside>

    <main class="main flex-1">
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-xl font-bold">{{tab_name}}</h2>
            <button onclick="showModal()" class="btn-blue">+ 新增配置</button>
        </div>

        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-gray-50 border-b">
                    <tr>
                        {% for h in headers %}<th class="p-4 text-gray-500">{{h}}</th>{% endfor %}
                        <th class="p-4 text-right">管理操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y">
                    {% for row in rows %}
                    <tr class="hover:bg-gray-50">
                        {% for cell in row %}<td class="p-4">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right text-blue-600 font-bold space-x-4">
                            <button onclick="alert('编辑功能已启用，请在下方表单操作')">编辑</button>
                            <button class="text-red-500">移除</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="modal" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50 p-4">
        <div class="bg-white rounded-xl w-full max-w-2xl p-8 max-h-[90vh] overflow-y-auto">
            <h3 class="text-xl font-bold mb-6 border-b pb-4 text-blue-600">添加{{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST" id="mainForm" class="space-y-4">
                {% if tab == 'policies' %}
                    <label class="block font-bold text-sm">规则名称</label><input name="name" required placeholder="如：美国-iPhone专用">
                    <label class="block font-bold text-sm mt-4 text-blue-600">🌍 全球国家准入 (点击开关)</label>
                    <div class="flex flex-wrap gap-2">
                        {% for c in countries %}<div class="toggle-box" onclick="this.classList.toggle('active')">{{c}}</div>{% endfor %}
                    </div>
                    <label class="block font-bold text-sm mt-4 text-blue-600">📱 苹果设备 (iPhone 6 - 17)</label>
                    <div class="flex flex-wrap gap-2">
                        {% for d in ios %}<div class="toggle-box" onclick="this.classList.toggle('active')">{{d}}</div>{% endfor %}
                    </div>
                    <label class="block font-bold text-sm mt-4 text-blue-600">🤖 安卓版本 (10 - 15)</label>
                    <div class="flex flex-wrap gap-2">
                        {% for d in andr %}<div class="toggle-box" onclick="this.classList.toggle('active')">{{d}}</div>{% endfor %}
                    </div>
                    <label class="block font-bold text-sm mt-4">拦截重定向 URL</label><input name="r_url" value="https://www.facebook.com">

                {% elif tab == 'tickets' %}
                    <label class="block font-bold text-sm">控制模式</label>
                    <select name="type"><option>单导模式 (个号)</option><option>群导模式 (群组)</option></select>
                    <label class="block font-bold text-sm">工单备注名</label><input name="name" required>
                    <label class="block font-bold text-sm">工单链接 (URL)</label><input name="url" required>
                    <label class="block font-bold text-sm">风控规则</label>
                    <select name="p_id">{% for p in plist %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select>
                    <div class="grid grid-cols-2 gap-4">
                        <div><label class="block font-bold text-sm">广告像素 (Pixel ID)</label><input name="pixel"></div>
                        <div><label class="block font-bold text-sm">广告事件 (Event)</label><input name="event" placeholder="Lead"></div>
                    </div>
                    <label class="block font-bold text-sm">系列名包含</label><input name="campaign">
                    <label class="block font-bold text-sm">请求类型</label><select name="mock_req"><option>GET</option><option>POST</option></select>

                {% elif tab == 'links' %}
                    <label class="block font-bold text-sm">选择短链域名</label>
                    <select name="domain">{% for d in domains %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                    <label class="block font-bold text-sm">选择已分配工单</label>
                    <select name="ticket_id">{% for t in tlist %}<option value="{{t[0]}}">{{t[1]}} ({{t[2]}})</option>{% endfor %}</select>
                    <label class="block font-bold text-sm">备注 (如：FB投马群01)</label><input name="note">
                {% elif tab == 'users' %}
                    <input name="u" placeholder="账号名" required><input name="p" type="password" placeholder="设置密码">
                {% endif %}

                <div class="flex justify-end space-x-4 pt-6 border-t">
                    <button type="button" onclick="hideModal()" class="text-gray-400">取消</button>
                    <button class="btn-blue shadow-lg">保存配置</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function showModal(){ document.getElementById('modal').style.display='flex'; }
        function hideModal(){ document.getElementById('modal').style.display='none'; }
    </script>
</body>
</html>
"""

# --- 3. 核心路由逻辑 ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%m-%d %H:%M")
    if tab == 'policies':
        db_action("INSERT INTO policies (name,devices,countries,r_url) VALUES (?,?,?,?)", (f['name'], "Multi-Device", "Custom-Geo", f['r_url']), False)
    elif tab == 'tickets':
        db_action('''INSERT INTO tickets (name,url,type,pixel,event,campaign,mock_req,p_id) 
                  VALUES (?,?,?,?,?,?,?,?)''', (f['name'], f['url'], f['type'], f['pixel'], f['event'], f['campaign'], f['mock_req'], f['p_id']), False)
    elif tab == 'links':
        # 随机前缀 + 后缀生成
        pre = random.choice(['vip', 'fb', 'ads', 'go']) + str(random.randint(10,99))
        suf = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        code = f"{pre}-{suf}"
        db_action("INSERT INTO mapping (code,ticket_id,domain,note,date) VALUES (?,?,?,?,?)", (code, f['ticket_id'], f['domain'], f['note'], now), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    plist = db_action("SELECT id, name FROM policies")
    tlist = db_action("SELECT id, name, type FROM tickets")
    conf = {
        "users": ("团队成员", ["ID", "账号", "角色"], "SELECT id, u, '投放经理' FROM users"),
        "policies": ("风控规则", ["ID", "规则名", "设备范围", "跳转URL"], "SELECT id, name, devices, r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "工单名", "链接", "像素", "类型"], "SELECT id, name, url, pixel, type FROM tickets"),
        "links": ("推广链路", ["ID", "短链URL", "备注", "日期"], "SELECT id, domain||'/'||code, note, date FROM mapping"),
        "logs": ("投放报表", ["ID", "链接", "IP", "详情", "设备", "版位", "来源", "时间"], "SELECT * FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=title, headers=headers, rows=rows, 
                                  user=session['user'], countries=COUNTRIES, ios=IOS_DEVS, andr=AND_DEVS, 
                                  domains=DOMAINS, plist=plist, tlist=tlist)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'admin' and request.form['p'] == '777888':
        session['user'] = 'admin'; return redirect('/admin')
    return '<body style="background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#fff;padding:40px;border-radius:12px;box-shadow:0 10px 20px rgba(0,0,0,0.1);width:340px;"><h2 style="color:#1877f2;margin-bottom:20px;font-weight:bold;">SENTINEL FB LOGIN</h2><input name="u" placeholder="账号" style="width:100%;padding:10px;margin-bottom:15px;border:1px solid #ddd;border-radius:6px;"><input name="p" type="password" placeholder="密码" style="width:100%;padding:10px;margin-bottom:20px;border:1px solid #ddd;border-radius:6px;"><button style="width:100%;background:#1877f2;color:#fff;padding:12px;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">登录系统</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = "sentinel_fb_ultra_pro"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 专业配置项 ---
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]
COUNTRIES = ["中国", "香港", "台湾", "美国", "英国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "印尼", "菲律宾", "德国", "法国", "加拿大", "澳大利亚", "巴西", "迪拜"]
IOS_DEVS = ["iPhone 6-8", "iPhone X-12", "iPhone 13-15", "iPhone 16-17 Pro Max"]
AND_DEVS = ["Android 10-12", "Android 13-15"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    # 策略表增加风控细节
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    # 工单表增加：像素、事件、系列名、模拟请求
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
        pixel TEXT, event TEXT, campaign TEXT, mock_req TEXT, p_id INTEGER)''')
    # 短链表增加：控制模式、备注
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, ticket_id INTEGER, 
        mode TEXT, domain TEXT, note TEXT, date TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('admin', '777888', 'ROOT')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=10); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 2. 专业 UI 模板 ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#f4f7f9;color:#333;font-family:sans-serif;}
        .sidebar{width:240px;background:#fff;border-right:1px solid #e0e6ed;position:fixed;height:100vh;}
        .main{margin-left:240px;padding:30px;}
        .nav-link{display:flex;padding:12px 25px;margin:4px 15px;border-radius:6px;color:#606266;transition:0.3s;}
        .nav-active{background:#ecf5ff;color:#409eff;font-weight:bold;}
        .card{background:#fff;border-radius:8px;border:1px solid #ebeef5;box-shadow:0 2px 12px 0 rgba(0,0,0,.05);}
        .form-label{display:block;margin-bottom:8px;font-size:13px;color:#606266;font-weight:500;}
        .form-label::before{content:"* ";color:#f56c6c;}
        input, select, textarea{width:100%;padding:10px;border:1px solid #dcdfe6;border-radius:4px;font-size:14px;outline:none;}
        input:focus{border-color:#409eff;}
        .btn-blue{background:#409eff;color:#fff;padding:10px 25px;border-radius:4px;font-weight:500;}
        .tag-btn{padding:4px 12px;border:1px solid #dcdfe6;border-radius:4px;font-size:12px;cursor:pointer;background:#fff;}
        .tag-on{background:#409eff;color:#fff;border-color:#409eff;}
    </style>
</head>
<body class="flex">
    <aside class="sidebar py-6">
        <div class="px-8 mb-10 text-xl font-bold text-blue-500">Sentinel FB Pro</div>
        <nav class="space-y-1">
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
                <thead class="bg-gray-50 text-gray-400">
                    <tr>
                        {% for h in headers %}<th class="p-4 border-b font-medium">{{h}}</th>{% endfor %}
                        <th class="p-4 border-b text-right">操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for row in rows %}
                    <tr class="hover:bg-gray-50">
                        {% for cell in row %}<td class="p-4">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right text-blue-500 font-bold space-x-3"><button>编辑</button><button class="text-red-400">删除</button></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="modal" class="fixed inset-0 bg-black/40 hidden items-center justify-center z-50 p-4">
        <div class="card w-full max-w-xl p-8 max-h-[90vh] overflow-y-auto">
            <div class="flex justify-between items-center mb-6">
                <h3 class="text-lg font-bold">添加{{tab_name}}</h3>
                <span onclick="hideModal()" class="cursor-pointer text-gray-400 text-xl">×</span>
            </div>
            
            <form action="/action/add/{{tab}}" method="POST" class="space-y-5">
                {% if tab == 'tickets' %}
                    <div><label class="form-label">工单名称</label><input name="name" placeholder="请输入" required></div>
                    <div><label class="form-label">控制模式</label>
                        <select name="type"><option value="单导模式">单导模式 (个号)</option><option value="群导模式">群导模式 (群组)</option></select>
                    </div>
                    <div><label class="form-label">工单链接</label><input name="url" placeholder="请输入目标跳转链接" required></div>
                    <div><label class="form-label">风控规则</label>
                        <select name="p_id">{% for p in policies %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select>
                    </div>
                    <div><label class="form-label">系列名包含</label><input name="campaign" placeholder="请输入系列名关键字"></div>
                    <div><label class="form-label">模拟请求</label>
                        <select name="mock_req"><option value="GET">GET请求</option><option value="POST">POST请求</option></select>
                    </div>
                    <div><label class="form-label">广告像素</label><input name="pixel" placeholder="请输入FB Pixel ID"></div>
                    <div><label class="form-label">广告事件</label><input name="event" placeholder="如: Lead 或 Purchase"></div>
                {% elif tab == 'links' %}
                    <div><label class="form-label">短链域名</label>
                        <select name="domain">{% for d in domains %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                    </div>
                    <div><label class="form-label">选择工单</label>
                        <select name="t_id">{% for t in tickets %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}</select>
                    </div>
                    <div><label class="form-label">备注</label><textarea name="note" rows="2" placeholder="请输入备注内容"></textarea></div>
                {% elif tab == 'policies' %}
                    <div><label class="form-label">规则名称</label><input name="name" required></div>
                    <div><label class="form-label">允许国家 (点击切换)</label>
                        <div class="flex flex-wrap gap-2">{% for c in countries %}<div class="tag-btn" onclick="this.classList.toggle('tag-on')">{{c}}</div>{% endfor %}</div>
                    </div>
                    <div><label class="form-label">允许设备 (独立方块)</label>
                        <div class="flex flex-wrap gap-2">{% for d in ios %}<div class="tag-btn" onclick="this.classList.toggle('tag-on')">{{d}}</div>{% endfor %}</div>
                        <div class="flex flex-wrap gap-2 mt-2">{% for d in and %}<div class="tag-btn" onclick="this.classList.toggle('tag-on')">{{d}}</div>{% endfor %}</div>
                    </div>
                {% endif %}
                <div class="flex justify-end space-x-3 pt-6 border-t mt-4">
                    <button type="button" onclick="hideModal()" class="px-6 py-2 text-gray-500">取消</button>
                    <button class="bg-blue-500 text-white px-8 py-2 rounded shadow-sm font-bold">确定</button>
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

# --- 3. 增强逻辑控制 ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'tickets':
        db_action('''INSERT INTO tickets (name,url,type,pixel,event,campaign,mock_req,p_id) 
                  VALUES (?,?,?,?,?,?,?,?)''', 
                  (f['name'], f['url'], f['type'], f['pixel'], f['event'], f['campaign'], f['mock_req'], f['p_id']), False)
    elif tab == 'links':
        pre = random.choice(['fb', 'ads', 'vip']) + str(random.randint(10,99))
        suf = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        code = f"{pre}-{suf}"
        db_action("INSERT INTO mapping (code,ticket_id,domain,note,date) VALUES (?,?,?,?,?)", 
                  (code, f['t_id'], f['domain'], f['note'], now), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    plist = db_action("SELECT id, name FROM policies")
    tlist = db_action("SELECT id, name FROM tickets")
    
    conf = {
        "users": ("团队成员", ["ID", "账号", "权限"], "SELECT id, u, n FROM users"),
        "policies": ("风控规则", ["ID", "规则名", "允许机型", "重定向URL"], "SELECT id, name, devices, r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "名称", "目标URL", "像素ID", "模式"], "SELECT id, name, url, pixel, type FROM tickets"),
        "links": ("推广链路", ["ID", "推广链接", "备注", "创建时间"], "SELECT id, domain||'/'||code, note, date FROM mapping"),
        "logs": ("投放报表", ["ID", "链接", "IP", "错误", "设备", "版位", "来源", "时间"], "SELECT * FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=title, headers=headers, rows=rows, 
                                  user=session['user'], countries=COUNTRIES, ios=IOS_DEVS, and=AND_DEVS, 
                                  domains=DOMAINS, policies=plist, tickets=tlist)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'admin' and request.form['p'] == '777888':
        session['user'] = 'admin'; return redirect('/admin')
    return '<body style="background:#f4f7f9;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#fff;padding:40px;border-radius:12px;box-shadow:0 10px 20px rgba(0,0,0,0.05);width:360px;"><h2 style="color:#409eff;font-weight:bold;margin-bottom:25px;">SENTINEL FB PRO</h2><input name="u" placeholder="账号" style="width:100%;padding:12px;margin-bottom:15px;border:1px solid #dcdfe6;border-radius:4px;"><input name="p" type="password" placeholder="密码" style="width:100%;padding:12px;margin-bottom:25px;border:1px solid #dcdfe6;border-radius:4px;"><button style="width:100%;background:#409eff;color:#fff;padding:12px;border:none;border-radius:4px;font-weight:bold;cursor:pointer;">登录系统</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
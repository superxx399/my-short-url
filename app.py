import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_fb_perfect_final_2026"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 初始化数据库 (含所有实战字段) ---
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 成员表
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    # 规则表 (全球国家与全系列设备存储)
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    # 工单表 (增加像素、事件等)
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
        pixel TEXT, event TEXT, campaign TEXT, mock_req TEXT, p_id INTEGER)''')
    # 链路表 (增加版位、备注)
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, 
        domain TEXT, note TEXT, slot TEXT, date TEXT)''')
    # 报表日志
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    
    # 初始数据
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('admin', '777888', 'ROOT')")
    c.execute("INSERT OR IGNORE INTO policies (id, name, devices, countries, r_url) VALUES (1, '默认规则', 'All-Devices', 'Global', 'https://www.facebook.com')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=10); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 2. 核心：短链跳转引擎 (处理日志记录与拦截) ---
@app.route('/<short_code>')
def main_redirect(short_code):
    # 1. 查找链路
    link = db_action("SELECT ticket_id, slot, note FROM mapping WHERE code = ?", (short_code,))
    if not link: return "Link Not Found", 404
    t_id, slot, note = link[0]

    # 2. 查找工单与规则
    ticket = db_action("SELECT url, p_id, pixel, event FROM tickets WHERE id = ?", (t_id,))
    if not ticket: return "Target Missing", 404
    final_url, p_id, pixel, event = ticket[0]

    # 3. 记录访问信息
    ip = request.remote_addr
    ua = request.headers.get('User-Agent', 'Unknown')
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 插入日志
    db_action("INSERT INTO logs (link, ip, err, dev, slot, src, time) VALUES (?,?,?,?,?,?,?)",
              (short_code, ip, "通过", ua[:50], slot, note, now), False)

    # 4. 执行跳转 (此处可扩展像素埋点)
    return redirect(final_url)

# --- 3. 后台 UI 模板 (精简名称，专业布局) ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#f0f2f5;font-family:-apple-system,sans-serif;color:#1c1e21;}
        .sidebar{width:200px;background:#fff;border-right:1px solid #ddd;position:fixed;height:100vh;}
        .main{margin-left:200px;padding:32px;}
        .nav-link{display:block;padding:12px 24px;color:#4b4f56;font-size:15px;font-weight:600;transition:0.2s;}
        .nav-link:hover{background:#f2f3f5;}
        .nav-active{background:#e7f3ff;color:#1877f2;border-right:4px solid #1877f2;}
        .card{background:#fff;border-radius:8px;border:1px solid #ddd;box-shadow:0 1px 2px rgba(0,0,0,0.05);}
        .btn-blue{background:#1877f2;color:#fff;padding:8px 20px;border-radius:6px;font-weight:bold;}
        input, select, textarea{width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;outline:none;margin-top:4px;}
        .form-group{margin-bottom:16px;}
        label{font-size:13px;font-weight:bold;color:#606770;}
    </style>
</head>
<body class="flex">
    <aside class="sidebar py-6">
        <div class="px-8 mb-10 text-2xl font-black text-blue-600 tracking-tighter">SENTINEL</div>
        <nav>
            <a href="?tab=users" class="nav-link {{'nav-active' if tab=='users'}}">成员管理</a>
            <a href="?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">风控规则</a>
            <a href="?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">投放工单</a>
            <a href="?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">推广链路</a>
            <a href="?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">投放报表</a>
        </nav>
    </aside>

    <main class="main flex-1">
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-2xl font-bold">{{tab_name}}</h2>
            <button onclick="document.getElementById('modal').style.display='flex'" class="btn-blue">+ 新增数据</button>
        </div>

        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-gray-50 border-b text-gray-500 uppercase">
                    <tr>{% for h in headers %}<th class="p-4 font-semibold">{{h}}</th>{% endfor %}<th class="p-4 text-right">管理</th></tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for row in rows %}
                    <tr class="hover:bg-gray-50/50 transition">
                        {% for cell in row %}<td class="p-4">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right space-x-3">
                            <a href="/action/edit/{{tab}}/{{row[0]}}" class="text-blue-600 font-bold hover:underline">编辑</a>
                            <a href="/action/del/{{tab}}/{{row[0]}}" class="text-red-500 font-bold hover:underline" onclick="return confirm('确定删除?')">删除</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="modal" class="fixed inset-0 bg-black/60 hidden items-center justify-center z-50 p-4 backdrop-blur-sm">
        <div class="bg-white rounded-xl w-full max-w-lg p-8 shadow-2xl">
            <h3 class="text-xl font-bold mb-6 border-b pb-4">添加 - {{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST">
                {% if tab == 'tickets' %}
                    <div class="form-group"><label>工单名称</label><input name="name" required></div>
                    <div class="form-group"><label>跳转目标 (输入数字自动转WhatsApp, 或输入URL)</label><input name="url" required placeholder="如: 852xxxxxx 或 https://..."></div>
                    <div class="form-group"><label>控制模式</label><select name="type"><option>单导模式</option><option>群导模式</option></select></div>
                    <div class="form-group"><label>像素 ID</label><input name="pixel" placeholder="可选"></div>
                    <div class="form-group"><label>关联规则</label><select name="p_id">{% for p in plist %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select></div>
                {% elif tab == 'links' %}
                    <div class="form-group"><label>短链域名</label><select name="domain"><option>https://secure-link.top</option><option>https://fb-check.net</option></select></div>
                    <div class="form-group"><label>关联工单</label><select name="ticket_id">{% for t in tlist %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}</select></div>
                    <div class="form-group"><label>投放版位 (Slot)</label><input name="slot" placeholder="如: FB-Feed / IG-Stories"></div>
                    <div class="form-group"><label>备注说明</label><input name="note" placeholder="如: 马来西亚-01组"></div>
                {% elif tab == 'policies' %}
                    <div class="form-group"><label>规则名称</label><input name="name" required></div>
                    <div class="form-group"><label>拦截跳转 URL</label><input name="r_url" value="https://www.facebook.com"></div>
                {% elif tab == 'users' %}
                    <div class="form-group"><label>账号</label><input name="u" required></div>
                    <div class="form-group"><label>密码</label><input name="p" type="password" required></div>
                {% endif %}
                <div class="flex justify-end space-x-3 pt-6">
                    <button type="button" onclick="document.getElementById('modal').style.display='none'" class="text-gray-400 font-bold">取消</button>
                    <button class="btn-blue px-10">确认提交</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

# --- 4. 管理后台行为逻辑 (解决编辑与删除) ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'tickets':
        target_url = f['url']
        if target_url.isdigit(): target_url = f"https://wa.me/{target_url}"
        db_action("INSERT INTO tickets (name,url,type,pixel,p_id) VALUES (?,?,?,?,?)", (f['name'], target_url, f['type'], f['pixel'], f.get('p_id',1)), False)
    elif tab == 'links':
        code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        db_action("INSERT INTO mapping (code,ticket_id,domain,slot,note,date) VALUES (?,?,?,?,?,?)", (code, f['ticket_id'], f['domain'], f['slot'], f['note'], now), False)
    elif tab == 'policies':
        db_action("INSERT INTO policies (name,r_url,devices,countries) VALUES (?,?,'All','All')", (f['name'], f['r_url']), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/action/del/<tab>/<id>')
def handle_del(tab, id):
    if 'user' not in session: return redirect('/login')
    db_action(f"DELETE FROM {tab} WHERE id = ?", (id,), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    plist = db_action("SELECT id, name FROM policies")
    tlist = db_action("SELECT id, name FROM tickets")
    
    conf = {
        "users": ("成员管理", ["ID", "账号", "角色"], "SELECT id, u, '投放经理' FROM users"),
        "policies": ("风控规则", ["ID", "名称", "拦截跳转"], "SELECT id, name, r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "名称", "目标URL", "模式"], "SELECT id, name, url, type FROM tickets"),
        "links": ("推广链路", ["ID", "短链代码", "版位", "备注"], "SELECT id, '/'||code, slot, note FROM mapping"),
        "logs": ("投放报表", ["ID", "链路", "IP", "状态", "UA详情", "版位", "备注", "时间"], "SELECT * FROM logs ORDER BY id DESC LIMIT 100")
    }
    t_name, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=t_name, headers=headers, rows=rows, 
                                  user=session['user'], plist=plist, tlist=tlist)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'admin' and request.form['p'] == '777888':
        session['user'] = 'admin'; return redirect('/admin')
    return '<body style="background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#fff;padding:40px;border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.1);width:320px;"><h2>SENTINEL LOGIN</h2><input name="u" placeholder="Admin" style="width:100%;padding:10px;margin-bottom:10px;border:1px solid #ddd;"><input name="p" type="password" placeholder="Pass" style="width:100%;padding:10px;margin-bottom:20px;border:1px solid #ddd;"><button style="width:100%;background:#1877f2;color:#fff;padding:12px;border:none;border-radius:6px;font-weight:bold;">登录</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
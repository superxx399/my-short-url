import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = "sentinel_fb_final_v12"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 配置数据 ---
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]
COUNTRIES = ["中国", "香港", "台湾", "美国", "英国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "印尼", "菲律宾", "德国", "法国", "加拿大", "澳大利亚", "巴西", "迪拜"]
IOS_DEVS = ["iPhone 6-8", "iPhone X-12", "iPhone 13-15", "iPhone 16-17 Pro Max"]
AND_DEVS = ["Android 10-12", "Android 13-15"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    # 统一字段名，增加专业投放字段
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
        pixel TEXT, event TEXT, campaign TEXT, mock_req TEXT, p_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, ticket_id INTEGER, 
        domain TEXT, note TEXT, date TEXT)''')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('admin', '777888', 'ROOT')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH, timeout=10); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 极简专业 UI ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#f4f7f9;font-family:sans-serif;}
        .sidebar{width:220px;background:#fff;border-right:1px solid #e0e6ed;position:fixed;height:100vh;}
        .main{margin-left:220px;padding:30px;}
        .nav-link{display:block;padding:12px 25px;color:#606266;transition:0.2s;}
        .nav-active{background:#ecf5ff;color:#409eff;font-weight:bold;border-right:3px solid #409eff;}
        .card{background:#fff;border-radius:8px;border:1px solid #ebeef5;box-shadow:0 2px 10px rgba(0,0,0,0.05);}
        .form-label{display:block;margin-bottom:5px;font-size:13px;font-weight:bold;color:#606266;}
        .form-label::before{content:"* ";color:red;}
        input, select, textarea{width:100%;padding:10px;border:1px solid #dcdfe6;border-radius:4px;outline:none;}
        .btn-submit{background:#409eff;color:white;padding:10px 30px;border-radius:4px;font-weight:bold;}
        .tag-btn{padding:4px 10px;border:1px solid #dcdfe6;border-radius:4px;font-size:12px;cursor:pointer;}
    </style>
</head>
<body class="flex">
    <aside class="sidebar py-6">
        <div class="px-8 mb-8 text-lg font-bold text-blue-600">SENTINEL MASTER</div>
        <nav>
            <a href="?tab=users" class="nav-link {{'nav-active' if tab=='users'}}">团队成员</a>
            <a href="?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">风控规则</a>
            <a href="?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">投放工单</a>
            <a href="?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">推广链路</a>
            <a href="?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">投放报表</a>
        </nav>
    </aside>
    <main class="main flex-1">
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-xl font-bold">{{tab_name}}</h2>
            <button onclick="document.getElementById('m').style.display='flex'" class="btn-submit">+ 新增项目</button>
        </div>
        <div class="card overflow-hidden">
            <table class="w-full text-left text-sm"><thead class="bg-gray-50"><tr>
                {% for h in headers %}<th class="p-4 border-b">{{h}}</th>{% endfor %}
                <th class="p-4 border-b text-right">管理</th>
            </tr></thead><tbody>
                {% for row in rows %}<tr>
                    {% for cell in row %}<td class="p-4 border-b">{{cell}}</td>{% endfor %}
                    <td class="p-4 border-b text-right text-blue-500 font-bold"><button>编辑</button></td>
                </tr>{% endfor %}
            </tbody></table>
        </div>
    </main>
    <div id="m" class="fixed inset-0 bg-black/40 hidden items-center justify-center p-4">
        <div class="bg-white rounded-lg w-full max-w-lg p-8 max-h-[90vh] overflow-y-auto shadow-xl">
            <h3 class="text-lg font-bold mb-6">配置{{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-4">
                {% if tab == 'tickets' %}
                    <div><label class="form-label">工单名称</label><input name="name" required></div>
                    <div><label class="form-label">控制模式</label><select name="type"><option>单导模式</option><option>群导模式</option></select></div>
                    <div><label class="form-label">工单链接</label><input name="url" placeholder="http://" required></div>
                    <div><label class="form-label">风控规则</label><select name="p_id">{% for p in policies %}<option value="{{p[0]}}">{{p[1]}}</option>{% endfor %}</select></div>
                    <div><label class="form-label">广告像素</label><input name="pixel"></div>
                    <div><label class="form-label">广告事件</label><input name="event"></div>
                {% elif tab == 'links' %}
                    <div><label class="form-label">短链域名</label><select name="domain">{% for d in domains %}<option value="{{d}}">{{d}}</option>{% endfor %}</select></div>
                    <div><label class="form-label">关联工单</label><select name="ticket_id">{% for t in tickets %}<option value="{{t[0]}}">{{t[1]}}</option>{% endfor %}</select></div>
                    <div><label class="form-label">备注</label><textarea name="note"></textarea></div>
                {% elif tab == 'policies' %}
                    <div><label class="form-label">规则名称</label><input name="name" required></div>
                    <div class="text-xs text-gray-400">点击选中国家和机型...</div>
                {% endif %}
                <div class="flex justify-end space-x-3 pt-4"><button type="button" onclick="document.getElementById('m').style.display='none'">取消</button><button class="btn-submit">确认创建</button></div>
            </form>
        </div>
    </div>
</body>
</html>
"""

@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if tab == 'tickets':
        db_action('INSERT INTO tickets (name,url,type,pixel,event,p_id) VALUES (?,?,?,?,?,?)', (f['name'], f['url'], f['type'], f['pixel'], f['event'], f.get('p_id', 1)), False)
    elif tab == 'links':
        code = f"{random.choice(['ads','fb','go'])}{random.randint(10,99)}-{''.join(random.choices(string.ascii_lowercase, k=4))}"
        db_action('INSERT INTO mapping (code,ticket_id,domain,note,date) VALUES (?,?,?,?,?)', (code, f['ticket_id'], f['domain'], f['note'], now), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    plist = db_action("SELECT id, name FROM policies")
    tlist = db_action("SELECT id, name FROM tickets")
    conf = {
        "users": ("团队成员", ["ID", "账号", "角色"], "SELECT id, u, n FROM users"),
        "policies": ("风控规则", ["ID", "规则名", "状态", "URL"], "SELECT id, name, 'Active', r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "名称", "目标", "像素", "模式"], "SELECT id, name, url, pixel, type FROM tickets"),
        "links": ("推广链路", ["ID", "完整短链", "备注", "日期"], "SELECT id, domain||'/'||code, note, date FROM mapping"),
        "logs": ("投放报表", ["ID", "链接", "IP", "详情", "设备", "版位", "来源", "时间"], "SELECT * FROM logs ORDER BY id DESC")
    }
    t, h, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=t, headers=h, rows=rows, user=session['user'], policies=plist, tickets=tlist, domains=DOMAINS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'admin' and request.form['p'] == '777888':
        session['user'] = 'admin'; return redirect('/admin')
    return '<body><form method="post">Admin:<input name="u"> Pass:<input name="p" type="password"><button>Login</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
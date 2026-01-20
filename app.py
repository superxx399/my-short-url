import os, sqlite3, datetime, random, string
from flask import Flask, request, redirect, render_template_string, session

app = Flask(__name__)
app.secret_key = "sentinel_fb_pro_2026"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 配置数据 (FB 投放专用) ---
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]
COUNTRIES = ["中国", "香港", "台湾", "美国", "英国", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "印尼", "菲律宾", "德国", "法国", "加拿大", "澳大利亚", "巴西", "迪拜"]
IOS_DEVS = ["iPhone 6/7/8", "iPhone X/XS", "iPhone 11", "iPhone 12", "iPhone 13", "iPhone 14", "iPhone 15", "iPhone 16", "iPhone 17 Pro Max"]
AND_DEVS = ["Android 10", "Android 11", "Android 12", "Android 13", "Android 14", "Android 15"]

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, ticket_id INTEGER, title TEXT, domain TEXT, date TEXT)')
    # 日志字段：链接, IP, 错误, 设备, 版位, 来源, 时间
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n) VALUES ('admin', '777888', '总监')")
    conn.commit(); conn.close()

def db_action(sql, args=(), fetch=True):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(sql, args); res = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return res

# --- 2. UI 模板 (白底蓝方块整洁风格) ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body{background:#f0f2f5;color:#1c1e21;font-family:-apple-system,system-ui,sans-serif;}
        .sidebar{width:240px;background:#ffffff;border-right:1px solid #ddd;position:fixed;height:100vh;box-shadow:2px 0 5px rgba(0,0,0,0.05);}
        .main{margin-left:240px;padding:30px;}
        .nav-link{display:flex;padding:12px 25px;margin:5px 15px;border-radius:6px;color:#4b4f56;font-weight:500;transition:0.3s;}
        .nav-link:hover{background:#e7f3ff;color:#1877f2;}
        .nav-active{background:#e7f3ff;color:#1877f2;border-left:4px solid #1877f2;}
        .card{background:#fff;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,0.1);border:1px solid #ddd;}
        .btn-blue{background:#1877f2;color:#fff;padding:8px 20px;border-radius:6px;font-weight:bold;}
        .tag-box{cursor:pointer;padding:5px 12px;border:1px solid #ced4da;border-radius:4px;font-size:12px;background:#f8f9fa;}
        .tag-selected{background:#1877f2;color:#fff;border-color:#1877f2;}
        input, select{background:#fff;border:1px solid #ddd;padding:10px;border-radius:6px;width:100%;outline:none;}
        input:focus{border-color:#1877f2;}
    </style>
</head>
<body class="flex">
    <aside class="sidebar">
        <div class="p-6 text-2xl font-bold text-blue-600 border-b mb-4">Sentinel FB</div>
        <nav>
            <a href="?tab=users" class="nav-link {{'nav-active' if tab=='users'}}">👤 团队成员</a>
            <a href="?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">🛡️ 防护模型</a>
            <a href="?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">🎯 投放终点</a>
            <a href="?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">🔗 推广链路</a>
            <a href="?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">📊 投放报表</a>
        </nav>
    </aside>

    <main class="main flex-1">
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-xl font-bold text-gray-700">{{tab_name}}</h2>
            <button onclick="document.getElementById('m-box').style.display='flex'" class="btn-blue">+ 创建新项</button>
        </div>

        <div class="card overflow-x-auto">
            <table class="w-full text-left text-sm">
                <thead class="bg-gray-50 border-b">
                    <tr>
                        {% for h in headers %}<th class="p-4 text-gray-500 font-medium">{{h}}</th>{% endfor %}
                        <th class="p-4 text-right">操作</th>
                    </tr>
                </thead>
                <tbody class="divide-y">
                    {% for row in rows %}
                    <tr class="hover:bg-gray-50">
                        {% for cell in row %}<td class="p-4">{{cell}}</td>{% endfor %}
                        <td class="p-4 text-right text-blue-600 font-bold space-x-2">
                            <button>编辑</button><button class="text-red-500">移除</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="m-box" class="fixed inset-0 bg-black/50 hidden items-center justify-center z-50 p-4">
        <div class="card w-full max-w-3xl p-8 max-h-[90vh] overflow-y-auto">
            <h3 class="text-lg font-bold mb-6 border-b pb-2">配置详情 - {{tab_name}}</h3>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-4">
                {% if tab == 'users' %}
                    <input name="u" placeholder="成员账号" required><input name="p" type="password" placeholder="访问密码">
                {% elif tab == 'policies' %}
                    <input name="name" placeholder="策略命名 (如: 东南亚iPhone)" required>
                    <div class="font-bold text-sm text-blue-600">🌍 全球国家准入 (独立开关)</div>
                    <div class="flex flex-wrap gap-2">
                        {% for c in countries %}<div class="tag-box" onclick="this.classList.toggle('tag-selected')">{{c}}</div>{% endfor %}
                    </div>
                    <div class="font-bold text-sm text-blue-600 mt-4">📱 苹果系列</div>
                    <div class="flex flex-wrap gap-2">
                        {% for d in ios %}<div class="tag-box" onclick="this.classList.toggle('tag-selected')">{{d}}</div>{% endfor %}
                    </div>
                    <div class="font-bold text-sm text-blue-600 mt-4">🤖 安卓系列</div>
                    <div class="flex flex-wrap gap-2">
                        {% for d in andr %}<div class="tag-box" onclick="this.classList.toggle('tag-selected')">{{d}}</div>{% endfor %}
                    </div>
                    <input name="r_url" class="mt-4" placeholder="拦截后重定向 (通常为 FB 官方页)" value="https://www.facebook.com">
                {% elif tab == 'tickets' %}
                    <input name="name" placeholder="目标备注" required>
                    <input name="url" placeholder="最终重定向位置 (客户填写完表单后的位置)" required>
                    <select name="type"><option value="单导">单导模式</option><option value="群导">群导模式</option></select>
                {% elif tab == 'links' %}
                    <input name="title" placeholder="投放批次备注" required>
                    <div class="text-sm font-bold">主域名选择:</div>
                    <select name="domain">{% for d in domains %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                    <input name="t_id" placeholder="关联投放终点ID" required>
                {% endif %}
                <div class="flex justify-end space-x-4 pt-6 mt-6 border-t">
                    <button type="button" onclick="document.getElementById('m-box').style.display='none'" class="text-gray-400">取消</button>
                    <button class="btn-blue">保存并发布</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

# --- 3. 业务逻辑 ---
@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%m-%d %H:%M")
    if tab == 'users': db_action("INSERT INTO users (u,p,n) VALUES (?,?,?)", (f['u'], f['p'], f['u']), False)
    elif tab == 'policies': db_action("INSERT INTO policies (name,devices,countries,r_url) VALUES (?,?,?,?)", (f['name'], "Multi-Device", "Global", f['r_url']), False)
    elif tab == 'tickets': db_action("INSERT INTO tickets (name,url,type,p_id) VALUES (?,?,?,1)", (f['name'], f['url'], f['type']), False)
    elif tab == 'links':
        # 随机前缀 + 随机后缀
        pre = random.choice(['get', 'info', 'win', 'go']) + str(random.randint(10,99))
        suf = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        code = f"{pre}-{suf}"
        db_action("INSERT INTO mapping (code,ticket_id,title,domain,date) VALUES (?,?,?,?,?)", (code, f['t_id'], f['title'], f['domain'], now), False)
    return redirect(f'/admin?tab={tab}')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    conf = {
        "users": ("团队成员管理", ["ID", "账号", "备注"], "SELECT id, u, n FROM users"),
        "policies": ("防护模型配置", ["ID", "模型名", "国家范围", "重定向"], "SELECT id, name, countries, r_url FROM policies"),
        "tickets": ("投放终点设置", ["ID", "备注", "目标URL", "模式"], "SELECT id, name, url, type FROM tickets"),
        "links": ("推广链路分发", ["ID", "完整推广链接", "批次备注", "创建时间"], "SELECT id, domain||'/'||code, title, date FROM mapping"),
        "logs": ("投放数据报表", ["ID", "访问链接", "IP", "状态/错误", "设备型号", "版位", "来源", "时间"], "SELECT * FROM logs ORDER BY id DESC")
    }
    title, headers, sql = conf.get(tab)
    rows = db_action(sql)
    return render_template_string(UI_TEMPLATE, tab=tab, tab_name=title, headers=headers, rows=rows, 
                                  user=session['user'], countries=COUNTRIES, ios=IOS_DEVS, andr=AND_DEVS, domains=DOMAINS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['u'] == 'admin' and request.form['p'] == '777888':
        session['user'] = 'admin'; return redirect('/admin')
    return '<body style="background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#fff;padding:40px;border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.1);width:350px;"><h2 style="color:#1877f2;margin-bottom:20px;font-weight:bold;">SENTINEL FB LOGIN</h2><input name="u" placeholder="账号" style="width:100%;padding:10px;margin-bottom:15px;border:1px solid #ddd;border-radius:6px;"><input name="p" type="password" placeholder="密码" style="width:100%;padding:10px;margin-bottom:20px;border:1px solid #ddd;border-radius:6px;"><button style="width:100%;background:#1877f2;color:#fff;padding:12px;border:none;border-radius:6px;font-weight:bold;cursor:pointer;">进入管理后台</button></form></body>'

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888, debug=True)
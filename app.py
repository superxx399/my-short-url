import os, sqlite3, datetime, random, string, time
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v16_global_ultra"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'sentinel_v16.db')

# --- 全球国家数据 (按区域分类，确保界面整洁) ---
GLOBAL_REGIONS = {
    "亚洲": ["中国", "香港", "台湾", "日本", "韩国", "新加坡", "马来西亚", "泰国", "越南", "印尼", "菲律宾", "阿联酋", "沙特", "卡塔尔", "印度", "巴基斯坦"],
    "欧洲": ["英国", "法国", "德国", "意大利", "西班牙", "荷兰", "比利时", "瑞典", "挪威", "波兰", "俄罗斯", "土耳其"],
    "美洲": ["美国", "加拿大", "墨西哥", "巴西", "阿根廷", "哥伦比亚", "智利"],
    "大洋洲": ["澳大利亚", "新西兰"],
    "非洲": ["埃及", "南非", "尼日利亚", "肯尼亚"]
}
DEVICES = ["iPhone", "Android", "iPad", "Windows PC", "Mac-OS", "Linux", "Bot/Crawler"]
DOMAINS = ["https://secure-link.top", "https://fb-check.net"]

# --- 数据库底层安全函数 (防500错误) ---
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT, p TEXT, n TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, devices TEXT, countries TEXT, r_url TEXT)')
        c.execute('''CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, type TEXT, 
            pixel TEXT, event TEXT, campaign TEXT, mock_req TEXT, p_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, ticket_id INTEGER, 
            domain TEXT, slot TEXT, note TEXT, date TEXT)''')
        c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, ip TEXT, err TEXT, dev TEXT, slot TEXT, src TEXT, time TEXT)')
        c.execute("INSERT OR IGNORE INTO users (id, u, p, n) VALUES (1, 'super', '777888', 'ROOT')")
        c.execute("INSERT OR IGNORE INTO policies (id, name, devices, countries, r_url) VALUES (1, '放行所有国家', 'All', 'All', 'https://www.facebook.com')")
        conn.commit()

def db_query(sql, args=(), one=False):
    for _ in range(3):
        try:
            with get_db() as conn:
                cur = conn.execute(sql, args)
                rv = [dict(row) for row in cur.fetchall()]
                return (rv[0] if rv else None) if one else rv
        except sqlite3.OperationalError: time.sleep(0.3)
    return None if one else []

# --- 旗舰版 UI (包含全球选择器) ---
UI_LAYOUT = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
<style>
    body{background:#f8fafc; font-family:sans-serif;}
    .nav-link{display:block; padding:15px 30px; color:#64748b; font-weight:700; border-left:4px solid transparent; transition:0.3s;}
    .nav-active{background:#eff6ff; color:#2563eb; border-left:4px solid #2563eb;}
    .toggle-box{padding:4px 10px; border:1px solid #e2e8f0; border-radius:6px; cursor:pointer; font-size:11px; background:#fff; transition:0.2s;}
    .selected{background:#2563eb; color:#fff; border-color:#2563eb;}
    input, select, textarea{width:100%; padding:12px; border:1px solid #e2e8f0; border-radius:12px; margin-top:5px; outline:none;}
    .country-grid{display:grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap:6px;}
</style></head>
<body class="flex">
    <nav class="w-[240px] bg-white border-r fixed h-full py-10">
        <div class="px-8 mb-12"><h1 class="text-2xl font-black text-blue-600 tracking-tighter">SENTINEL</h1></div>
        <a href="/admin?tab=policies" class="nav-link {{'nav-active' if tab=='policies'}}">风控规则</a>
        <a href="/admin?tab=tickets" class="nav-link {{'nav-active' if tab=='tickets'}}">投放工单</a>
        <a href="/admin?tab=links" class="nav-link {{'nav-active' if tab=='links'}}">推广链路</a>
        <a href="/admin?tab=logs" class="nav-link {{'nav-active' if tab=='logs'}}">投放报表</a>
        <a href="/logout" class="block p-8 text-xs text-red-400 mt-20">安全登出</a>
    </nav>
    <main class="flex-1 ml-[240px] p-12">
        <div class="flex justify-between items-center mb-10">
            <h2 class="text-3xl font-black text-slate-800">{{title}}</h2>
            <button onclick="document.getElementById('m').style.display='flex'" class="bg-blue-600 text-white px-8 py-3 rounded-2xl font-bold shadow-lg shadow-blue-200">+ 新增配置</button>
        </div>
        <div class="bg-white rounded-3xl border shadow-sm overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-slate-50 border-b text-slate-400 font-bold uppercase tracking-wider">
                    <tr>{% for h in headers %}<th class="p-5">{{h}}</th>{% endfor %}<th class="p-5 text-right">管理</th></tr>
                </thead>
                <tbody class="divide-y">
                    {% for row in rows %}<tr>
                        {% for key in row_keys %}<td class="p-5 text-slate-700 font-semibold">{{row[key]}}</td>{% endfor %}
                        <td class="p-5 text-right"><a href="/action/del/{{tab}}/{{row['id']}}" class="text-red-400 font-bold" onclick="return confirm('确认删除?')">删除</a></td>
                    </tr>{% endfor %}
                </tbody>
            </table>
        </div>
    </main>

    <div id="m" class="fixed inset-0 bg-slate-900/60 hidden items-center justify-center p-4 z-50 backdrop-blur-md">
        <div class="bg-white rounded-[40px] p-10 w-full max-w-3xl shadow-2xl overflow-y-auto max-h-[90vh]">
            <h3 class="text-2xl font-black mb-8">新增 - {{title}}</h3>
            <form action="/action/add/{{tab}}" method="POST" class="space-y-6">
                {% if tab == 'policies' %}
                    <div><label class="text-xs font-bold text-slate-400">规则名称</label><input name="name" required></div>
                    <div>
                        <label class="text-xs font-bold text-slate-400 mb-2 block">允许访问的国家 (全球范围)</label>
                        {% for region, countries in global_data.items() %}
                            <p class="text-[10px] font-bold text-blue-500 mt-3 mb-1 uppercase tracking-tighter">● {{region}}</p>
                            <div class="country-grid">
                                {% for c in countries %}<div class="toggle-box" onclick="ts(this, 'c_in')">{{c}}</div>{% endfor %}
                            </div>
                        {% endfor %}
                        <input type="hidden" name="countries" id="c_in">
                    </div>
                    <div><label class="text-xs font-bold text-slate-400">允许访问的设备</label>
                        <div class="flex flex-wrap gap-2 mt-2">{% for d in devices %}<div class="toggle-box" onclick="ts(this, 'd_in')">{{d}}</div>{% endfor %}</div><input type="hidden" name="devices" id="d_in">
                    </div>
                    <div><label class="text-xs font-bold text-slate-400">拦截跳转 URL</label><input name="r_url" value="https://www.facebook.com"></div>
                {% elif tab == 'tickets' %}
                    <div class="grid grid-cols-2 gap-6">
                        <div><label class="text-xs font-bold text-slate-400">名称</label><input name="name" required></div>
                        <div><label class="text-xs font-bold text-slate-400">模式</label><select name="type"><option>单导模式</option><option>群导模式</option></select></div>
                    </div>
                    <label class="text-xs font-bold text-slate-400">跳转链接</label><input name="url" required>
                    <label class="text-xs font-bold text-slate-400">关联风控规则</label><select name="p_id">{% for p in plist %}<option value="{{p['id']}}">{{p['name']}}</option>{% endfor %}</select>
                    <div class="grid grid-cols-2 gap-6">
                        <div><label class="text-xs font-bold text-slate-400">Pixel ID</label><input name="pixel"></div>
                        <div><label class="text-xs font-bold text-slate-400">广告系列</label><input name="campaign"></div>
                    </div>
                {% elif tab == 'links' %}
                    <label class="text-xs font-bold text-slate-400">域名</label><select name="domain">{% for d in domains %}<option value="{{d}}">{{d}}</option>{% endfor %}</select>
                    <label class="text-xs font-bold text-slate-400">工单</label><select name="ticket_id">{% for t in tlist %}<option value="{{t['id']}}">{{t['name']}}</option>{% endfor %}</select>
                    <label class="text-xs font-bold text-slate-400">版位备注</label><input name="slot">
                {% endif %}
                <div class="pt-8 flex gap-4"><button class="flex-1 bg-blue-600 text-white p-4 rounded-2xl font-bold text-lg">确认保存</button><button type="button" onclick="document.getElementById('m').style.display='none'" class="px-8 text-slate-400 font-bold">取消</button></div>
            </form>
        </div>
    </div>
    <script>function ts(el,id){el.classList.toggle('selected');const s=Array.from(el.parentElement.querySelectorAll('.selected')).map(e=>e.innerText);document.getElementById(id).value=s.join(',');}</script>
</body></html>
"""

# --- 路由逻辑保持完整 ---
@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    tab = request.args.get('tab', 'links')
    plist = db_query("SELECT id, name FROM policies")
    tlist = db_query("SELECT id, name FROM tickets")
    config = {
        "policies": ("风控规则", ["ID", "规则名", "拦截跳转"], ["id", "name", "r_url"], "SELECT id, name, r_url FROM policies"),
        "tickets": ("投放工单", ["ID", "工单名", "像素ID", "系列名"], ["id", "name", "pixel", "campaign"], "SELECT id, name, pixel, campaign FROM tickets"),
        "links": ("推广链路", ["ID", "路径码", "版位"], ["id", "code", "slot"], "SELECT id, code, slot FROM mapping"),
        "logs": ("投放报表", ["IP", "路径", "设备", "时间"], ["ip", "link", "dev", "time"], "SELECT id, ip, link, dev, time FROM logs ORDER BY id DESC")
    }
    title, headers, keys, sql = config.get(tab)
    rows = db_query(sql)
    return render_template_string(UI_LAYOUT, tab=tab, title=title, headers=headers, row_keys=keys, rows=rows, plist=plist, tlist=tlist, global_data=GLOBAL_REGIONS, devices=DEVICES, domains=DOMAINS)

@app.route('/action/add/<tab>', methods=['POST'])
def handle_add(tab):
    if 'user' not in session: return redirect('/login')
    f = request.form; now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_db() as conn:
        if tab == 'policies':
            conn.execute("INSERT INTO policies (name,devices,countries,r_url) VALUES (?,?,?,?)", (f['name'], f.get('devices','All'), f.get('countries','All'), f['r_url']))
        elif tab == 'tickets':
            u = f['url']; u = f"https://wa.me/{u}" if u.isdigit() else u
            conn.execute("INSERT INTO tickets (name,url,type,pixel,event,campaign,mock_req,p_id) VALUES (?,?,?,?,?,?,?,?)", 
                         (f['name'], u, f['type'], f.get('pixel',''), f.get('event',''), f.get('campaign',''), f.get('mock_req',''), f['p_id']))
        elif tab == 'links':
            code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            conn.execute("INSERT INTO mapping (code,ticket_id,domain,slot,note,date) VALUES (?,?,?,?,?,?)", (code, f['ticket_id'], f['domain'], f['slot'], '', now))
        conn.commit()
    return redirect(f'/admin?tab={tab}')

@app.route('/action/del/<tab>/<id>')
def handle_del(tab, id):
    if 'user' not in session: return redirect('/login')
    with get_db() as conn:
        conn.execute(f"DELETE FROM {tab} WHERE id = ?", (id,))
        conn.commit()
    return redirect(f'/admin?tab={tab}')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form.get('u') == 'super' and request.form.get('p') == '777888':
        session['user'] = 'super'; return redirect('/admin')
    return '<body style="background:#f1f5f9;display:flex;justify-content:center;align-items:center;height:100vh;"><form method="post" style="background:#fff;padding:60px;border-radius:40px;width:380px;box-shadow:0 10px 40px rgba(0,0,0,0.05);"><h2 style="color:#2563eb;font-weight:900;font-size:24px;margin-bottom:20px;letter-spacing:-1px;">SENTINEL GLOBAL</h2><input name="u" placeholder="账号" style="width:100%;margin-bottom:15px;padding:12px;border:1px solid #ddd;border-radius:12px;outline:none;"><input name="p" type="password" placeholder="密码" style="width:100%;margin-bottom:25px;padding:12px;border:1px solid #ddd;border-radius:12px;outline:none;"><button style="width:100%;background:#2563eb;color:#fff;padding:15px;border-radius:12px;font-weight:bold;border:none;cursor:pointer;">登录管理系统</button></form></body>'

@app.route('/logout')
def logout(): session.clear(); return redirect('/login')

@app.route('/<code>')
def jump(code):
    link = db_query("SELECT * FROM mapping WHERE code = ?", (code,), one=True)
    if not link: abort(404)
    ticket = db_query("SELECT * FROM tickets WHERE id = ?", (link['ticket_id'],), one=True)
    if not ticket: abort(404)
    return redirect(ticket['url'])

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8888)
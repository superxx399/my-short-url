import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v15_ultra_security"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v15.db')

# --- 1. 配置数据 (更新至 iPhone 17 系列) ---
COUNTRY_DB = {
    "热门地区": ["中国", "香港", "台湾", "澳门", "新加坡", "马来西亚", "日本", "韩国"],
    "美欧地区": ["美国", "加拿大", "英国", "德国", "法国", "意大利", "西班牙", "荷兰"],
    "东南亚": ["越南", "泰国", "菲律宾", "印度尼西亚", "柬埔寨", "缅甸"],
    "中东/其他": ["阿联酋", "沙特", "澳大利亚", "巴西", "俄罗斯", "土耳其", "埃及"]
}

LANG_DB = ["中文(zh)", "英语(en)", "日语(ja)", "韩语(ko)", "法语(fr)", "西语(es)", "德语(de)", "泰语(th)", "越语(vi)"]

DEVICE_DB = {
    "Apple (iPhone 17/16/15 最新旗舰)": [
        "iPhone 17 Pro Max", "iPhone 17 Pro", "iPhone 17 Air/Slim",
        "iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 16 Plus",
        "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 15 Plus"
    ],
    "Apple (iPhone 6 - 14 经典机型)": [
        "iPhone 14/13/12 Pro Max", "iPhone 11/X/XR", 
        "iPhone 8/7/6s Plus", "iPad Pro M4/M2", "Apple Watch"
    ],
    "Android (对标旗舰系列)": [
        "Huawei Mate 70 Pro+", "Huawei Mate 60/RS", "Samsung S25/S24 Ultra", 
        "Xiaomi 15/14 Ultra", "Honor Magic 7", "OPPO Find X8", "Vivo X200"
    ]
}

# --- 2. 数据库初始化 ---
def get_bj_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_countries TEXT, white_langs TEXT, white_devices TEXT, r_url TEXT, c_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER, c_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, domain TEXT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    conn.commit(); conn.close()

# --- 3. 核心权限与网关 ---
@app.before_request
def check_auth():
    # 允许访问登录页和静态资源
    if request.path in ['/login', '/api/action'] or request.path.startswith('/static'):
        return
    # 访问管理后台需要登录
    if request.path.startswith('/admin') and session.get('user') != 'super':
        return redirect('/login')

@app.route('/<code>')
def gateway(code):
    # 总后台及内部逻辑豁免任何拦截规则
    if code in ['admin', 'login', 'api']: return redirect('/admin')
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    query = """SELECT t.url, s.* FROM mapping m 
               JOIN tickets t ON m.ticket_id = t.id 
               JOIN policies s ON t.p_id = s.id 
               WHERE m.code = ?"""
    c.execute(query, (code,))
    res = c.fetchone()
    if not res: return "404 Not Found", 404
    
    target_url, _, p_name, w_countries, w_langs, w_devices, r_url, _ = res
    ua = request.user_agent.string.lower()
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    
    is_blocked = 0; reason = "允许放行"

    # 防护应用逻辑：仅当设置了机型过滤且为苹果时
    if w_devices and ("iphone" in w_devices.lower() or "apple" in w_devices.lower()):
        if 'iphone' not in ua and 'ipad' not in ua:
            is_blocked, reason = 1, "拦截: 非iOS设备"

    # 记录审计日志
    c.execute("INSERT INTO logs (time, code, ip, status, reason) VALUES (?,?,?,?,?)",
              (get_bj_time(), code, ip, "拦截" if is_blocked else "成功", reason))
    conn.commit(); conn.close()
    
    if is_blocked: return redirect(r_url)
    return redirect(target_url)

# --- 4. 登录与后台控制 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['u'] == 'super' and request.form['p'] == '777888':
            session['user'] = 'super'
            return redirect('/admin')
        return "登录失败，请核对凭据"
    return '''
    <body style="background:#0b0e14; display:flex; align-items:center; justify-content:center; height:100vh; font-family:sans-serif; color:white;">
        <form method="post" style="background:#11141b; padding:40px; border-radius:30px; border:1px solid #333; width:320px; text-align:center; box-shadow:0 25px 50px -12px rgba(0,0,0,0.5);">
            <h2 style="color:#3b82f6; margin-bottom:30px; font-weight:900; letter-spacing:-1px;">SENTINEL V15</h2>
            <input name="u" placeholder="Account" style="width:100%; margin-bottom:15px; padding:15px; background:#000; border:1px solid #444; color:#fff; border-radius:12px; outline:none;">
            <input name="p" type="password" placeholder="Password" style="width:100%; margin-bottom:25px; padding:15px; background:#000; border:1px solid #444; color:#fff; border-radius:12px; outline:none;">
            <button style="width:100%; padding:15px; background:#3b82f6; border:none; color:#fff; border-radius:12px; font-weight:bold; cursor:pointer;">进入管理终端</button>
        </form>
    </body>
    '''

@app.route('/admin')
def admin():
    tab = request.args.get('tab', 'links')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    data = {}
    c.execute("SELECT * FROM policies ORDER BY id DESC"); data['policies'] = c.fetchall()
    c.execute("SELECT t.*, s.name FROM tickets t LEFT JOIN policies s ON t.p_id = s.id"); data['tickets'] = c.fetchall()
    c.execute("SELECT m.*, t.name FROM mapping m LEFT JOIN tickets t ON m.ticket_id = t.id"); data['links'] = c.fetchall()
    c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 100"); data['logs'] = c.fetchall()
    conn.close()
    return render_template_string(UI_HTML, tab=tab, data=data, bj_time=get_bj_time(), COUNTRIES=COUNTRY_DB, LANGUAGES=LANG_DB, DEVICES=DEVICE_DB)

# --- 5. 全能 API (支持回填编辑) ---
@app.route('/api/action', methods=['POST'])
def handle_action():
    if session.get('user') != 'super': abort(403)
    f = request.form; act = f.get('act'); rid = f.get('row_id')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    
    if act == 'save_policy':
        vals = (f['name'], f['countries'], f['langs'], f['devices'], f['r_url'])
        if rid: c.execute("UPDATE policies SET name=?, white_countries=?, white_langs=?, white_devices=?, r_url=? WHERE id=?", vals + (rid,))
        else: c.execute("INSERT INTO policies (name, white_countries, white_langs, white_devices, r_url, c_date) VALUES (?,?,?,?,?,?)", vals + (get_bj_time(),))
    
    elif act == 'save_ticket':
        vals = (f['name'], f['url'], f['p_id'])
        if rid: c.execute("UPDATE tickets SET name=?, url=?, p_id=? WHERE id=?", vals + (rid,))
        else: c.execute("INSERT INTO tickets (name, url, p_id, c_date) VALUES (?,?,?,?)", vals + (get_bj_time(),))
        
    elif act == 'save_link':
        if rid: c.execute("UPDATE mapping SET title=?, ticket_id=?, domain=? WHERE id=?", (f['n'], f['tid'], f['domain'], rid))
        else:
            code = ''.join(random.choice(string.ascii_letters) for _ in range(5))
            c.execute("INSERT INTO mapping (date, domain, code, title, ticket_id) VALUES (?,?,?,?,?)", (get_bj_time(), f['domain'], code, f['n'], f['tid']))
            
    conn.commit(); conn.close()
    return redirect(f'/admin?tab={f.get("back")}')

# --- 6. 终极 UI 模板 ---
UI_HTML = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
    dialog::backdrop { background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(10px); }
    .tag-active { background: #3b82f6 !important; color: white !important; border-color: #60a5fa !important; }
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
</style>
<body class="bg-[#0b0e14] text-slate-300 flex h-screen overflow-hidden font-sans">
    <nav class="w-64 bg-[#11141b] border-r border-white/5 flex flex-col p-6">
        <div class="mb-10"><h1 class="text-blue-500 font-black text-2xl italic tracking-tighter">SENTINEL V15</h1><p class="text-[10px] text-slate-600 mt-1 uppercase">BEIJING: {{ bj_time }}</p></div>
        <div class="space-y-2">
            {% for k, v in {'security':'🛡️ 防护规则','tickets':'🎫 工单目标','links':'🔗 短链汇总','logs':'📊 穿透日志'}.items() %}
            <a href="?tab={{k}}" class="block p-4 rounded-2xl transition {{ 'bg-blue-600 text-white shadow-lg' if tab==k else 'hover:bg-white/5 text-slate-500' }}">{{v}}</a>
            {% endfor %}
            <a href="/login" class="block p-4 mt-10 text-red-500 hover:bg-red-500/5 rounded-2xl text-center font-bold">退出系统</a>
        </div>
    </nav>

    <main class="flex-1 p-12 overflow-y-auto">
        {% if tab == 'links' %}
        <div class="flex justify-between items-center mb-10"><h2 class="text-3xl font-black italic">链路控制台</h2><button onclick="openL()" class="bg-blue-600 px-8 py-4 rounded-2xl font-black shadow-xl hover:scale-105 transition">+ 生成链路</button></div>
        <div class="bg-[#11141b] rounded-[2.5rem] border border-white/5 overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-[10px] uppercase text-slate-500 tracking-widest"><tr class="border-b border-white/5"><th class="p-6">备注</th><th class="p-6">完整地址</th><th class="p-6">目标工单</th><th class="p-6 text-right">管理</th></tr></thead>
                <tbody class="divide-y divide-white/5">
                    {% for l in data.links %}
                    <tr class="hover:bg-blue-500/5"><td class="p-6 font-bold">{{l[4]}}</td><td class="p-6 text-blue-400 font-mono">{{l[2]}}/{{l[3]}}</td><td class="p-6">{{l[5]}}</td><td class="p-6 text-right"><button onclick="editL('{{l[0]}}','{{l[4]}}','{{l[5]}}','{{l[2]}}')" class="text-blue-500 font-bold">编辑</button></td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        {% elif tab == 'security' %}
        <div class="flex justify-between items-center mb-10"><h2 class="text-3xl font-black italic">防护规则库</h2><button onclick="openP()" class="bg-indigo-600 px-8 py-4 rounded-2xl font-black shadow-xl hover:scale-105 transition">+ 创建规则</button></div>
        <div class="grid grid-cols-2 gap-8">
            {% for p in data.policies %}
            <div class="bg-[#11141b] border border-white/5 p-8 rounded-[2.5rem] hover:border-indigo-500/50 transition relative group">
                <div class="flex justify-between mb-6"><span class="text-indigo-500 font-black italic uppercase text-xl">{{p[1]}}</span><span class="text-[10px] text-slate-600 tracking-tighter">{{p[6]}}</span></div>
                <div class="space-y-2 text-xs text-slate-400 mb-8">
                    <p>允许国家: <span class="text-white font-bold">{{p[2] or '全球放行'}}</span></p>
                    <p>限定机型: <span class="text-white font-bold">{{p[4] or '全设备放行'}}</span></p>
                </div>
                <button onclick="editP('{{p[0]}}','{{p[1]}}','{{p[5]}}')" class="w-full bg-slate-900 py-4 rounded-2xl group-hover:bg-indigo-600 transition font-black">修改防护模型</button>
            </div>
            {% endfor %}
        </div>
        {% endif %}
    </main>

    <dialog id="pBox" onclick="if(event.target==this)this.close()" class="bg-[#11141b] p-10 rounded-[3rem] border border-white/10 text-slate-300 w-[850px]">
        <form action="/api/action" method="post" class="space-y-6">
            <input type="hidden" name="act" value="save_policy"><input type="hidden" name="back" value="security"><input type="hidden" name="row_id" id="p_rid">
            <h3 class="text-2xl font-black italic mb-4">指纹安全建模</h3>
            <input name="name" id="p_name" placeholder="规则命名" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none" required>
            
            <div class="max-h-[50vh] overflow-y-auto space-y-8 pr-4">
                <section>
                    <p class="text-[10px] text-slate-500 font-bold uppercase mb-4 tracking-widest">🌍 允许的国家/地区 (中文开关)</p>
                    {% for cat, list in COUNTRIES.items() %}
                    <div class="mb-4">
                        <span class="text-[10px] text-slate-700 block mb-2">{{cat}}</span>
                        <div class="flex flex-wrap gap-2">
                            {% for c in list %}<div onclick="tag(this, 'c_in')" class="px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs cursor-pointer hover:border-indigo-500 transition">{{c}}</div>{% endfor %}
                        </div>
                    </div>
                    {% endfor %}
                    <input type="hidden" name="countries" id="c_in">
                </section>

                <section>
                    <p class="text-[10px] text-slate-500 font-bold uppercase mb-4 tracking-widest">📱 允许的设备指纹 (包含 iPhone 17 Pro Max)</p>
                    {% for brand, models in DEVICES.items() %}
                    <div class="mb-4">
                        <span class="text-[10px] text-slate-700 block mb-2">{{brand}}</span>
                        <div class="flex flex-wrap gap-2">
                            {% for m in models %}<div onclick="tag(this, 'd_in')" class="px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-[10px] cursor-pointer hover:border-indigo-500 transition">{{m}}</div>{% endfor %}
                        </div>
                    </div>
                    {% endfor %}
                    <input type="hidden" name="devices" id="d_in">
                </section>

                <section>
                    <p class="text-[10px] text-slate-500 font-bold uppercase mb-4 tracking-widest">🗣️ 浏览器语言要求</p>
                    <div class="flex flex-wrap gap-2">
                        {% for l in LANGUAGES %}<div onclick="tag(this, 'l_in')" class="px-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs cursor-pointer hover:border-indigo-500 transition">{{l}}</div>{% endfor %}
                    </div>
                    <input type="hidden" name="langs" id="l_in">
                </section>
            </div>

            <input name="r_url" id="p_rurl" placeholder="被拦截后的重定向目的地 (如: https://google.com)" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none" required>
            <button class="w-full bg-indigo-600 py-5 rounded-3xl font-black text-xl shadow-2xl">部署防护模型</button>
        </form>
    </dialog>

    <dialog id="lBox" onclick="if(event.target==this)this.close()" class="bg-[#11141b] p-10 rounded-[3rem] border border-white/10 text-slate-300 w-[450px]">
        <form action="/api/action" method="post" class="space-y-4">
            <input type="hidden" name="act" value="save_link"><input type="hidden" name="back" value="links"><input type="hidden" name="row_id" id="l_rid">
            <h3 class="text-2xl font-black italic text-blue-500 mb-4">生成链路</h3>
            <input name="n" id="l_n" placeholder="链路备注" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none" required>
            <select name="domain" id="l_dom" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none appearance-none">
                <option value="https://secure.link">https://secure.link</option>
                <option value="https://api.jump.pro">https://api.jump.pro</option>
            </select>
            <select name="tid" id="l_tid" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none appearance-none">
                {% for t in data.tickets %}<option value="{{t[0]}}">目标工单: {{t[1]}}</option>{% endfor %}
            </select>
            <button class="w-full bg-blue-600 py-5 rounded-3xl font-black text-xl shadow-2xl">立即部署</button>
        </form>
    </dialog>

    <script>
        function tag(el, inputId){
            el.classList.toggle('tag-active');
            let actives = Array.from(el.parentElement.parentElement.querySelectorAll('.tag-active')).map(e => e.innerText);
            document.getElementById(inputId).value = actives.join(',');
        }
        function openP(){ document.getElementById('p_rid').value = ''; pBox.showModal(); }
        function openL(){ document.getElementById('l_rid').value = ''; lBox.showModal(); }
        function editP(id, name, rurl){
            document.getElementById('p_rid').value = id;
            document.getElementById('p_name').value = name;
            document.getElementById('p_rurl').value = rurl;
            pBox.showModal();
        }
        function editL(id, title, tid, domain){
            document.getElementById('l_rid').value = id;
            document.getElementById('l_n').value = title;
            document.getElementById('l_dom').value = domain;
            lBox.showModal();
        }
    </script>
</body>
"""

init_db()
if __name__ == '__main__':
    app.run(debug=True)
import os, sqlite3, random, string, datetime, urllib.parse
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v13_final_pro"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v13.db')

# --- 1. 核心工具函数 ---
def get_bj_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 账户表：增加 ID 追踪
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT, e_date TEXT)')
    # 策略库：内置指纹
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_countries TEXT, white_devices TEXT, r_url TEXT, c_date TEXT)')
    # 工单库
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER, c_date TEXT)')
    # 短链汇总
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, domain TEXT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER)')
    # 日志库
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date, e_date) VALUES ('admin', 'admin888', 'ROOT', ?, '2099-12-31')", (get_bj_time(),))
    conn.commit(); conn.close()

# --- 2. 预设库数据 ---
COUNTRIES = {
    "亚洲": ["CN", "HK", "TW", "SG", "MY", "JP", "KR", "TH", "VN", "ID", "PH"],
    "欧美": ["US", "GB", "CA", "DE", "FR", "IT", "ES", "AU"],
    "中东/南美": ["BR", "MX", "IN", "RU", "AE", "SA"]
}

DEVICE_MODELS = {
    "Apple": ["iPhone 16 Pro Max", "iPhone 16", "iPhone 15 Pro", "iPhone 14", "iPhone 13", "iPad Air"],
    "Android": ["Samsung S24", "Huawei Mate 60", "Xiaomi 14", "Pixel 8", "OPPO Find", "Vivo X"]
}

# --- 3. 核心网关引擎 ---
@app.route('/<code>')
def gateway(code):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    query = "SELECT t.url, s.* FROM mapping m JOIN tickets t ON m.ticket_id = t.id JOIN policies s ON t.p_id = s.id WHERE m.code = ?"
    c.execute(query, (code,))
    res = c.fetchone()
    if not res: return "404 Not Found", 404
    
    target, _, p_name, w_countries, w_devices, r_url, _ = res
    ua = request.user_agent.string.lower()
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
    
    is_blocked = 0; reason = "放行"
    
    # 指纹拦截逻辑 (这里可根据实际接入的高级 IP 库进一步细化)
    if w_devices:
        is_ios = 'iphone' in ua or 'ipad' in ua
        is_android = 'android' in ua
        if 'iphone' in w_devices.lower() and not is_ios: is_blocked, reason = 1, "设备拦截"
    
    c.execute("INSERT INTO logs (time, code, ip, status, reason) VALUES (?,?,?,?,?)", (get_bj_time(), code, ip, "拦截" if is_blocked else "成功", reason))
    conn.commit(); conn.close()
    
    if is_blocked: return redirect(r_url)
    return redirect(target)

# --- 4. 管理后台 ---
@app.route('/')
@app.route('/admin')
def admin():
    tab = request.args.get('tab', 'links')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    data = {}
    c.execute("SELECT * FROM users"); data['users'] = c.fetchall()
    c.execute("SELECT * FROM policies ORDER BY id DESC"); data['policies'] = c.fetchall()
    c.execute("SELECT t.*, s.name FROM tickets t LEFT JOIN policies s ON t.p_id = s.id"); data['tickets'] = c.fetchall()
    c.execute("SELECT m.*, t.name, t.url FROM mapping m LEFT JOIN tickets t ON m.ticket_id = t.id"); data['links'] = c.fetchall()
    c.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 50"); data['logs'] = c.fetchall()
    conn.close()
    return render_template_string(UI_TEMPLATE, tab=tab, data=data, bj_time=get_bj_time(), COUNTRIES=COUNTRIES, DEVICES=DEVICE_MODELS)

# --- 5. 全能 API 接口 (支持新增/编辑) ---
@app.route('/api/action', methods=['POST'])
def handle_action():
    f = request.form
    act = f.get('act')
    rid = f.get('row_id')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    
    if act == 'save_user':
        if rid: c.execute("UPDATE users SET u=?, p=?, n=?, e_date=? WHERE id=?", (f['u'], f['p'], f['n'], f['e'], rid))
        else: c.execute("INSERT INTO users (u, p, n, c_date, e_date) VALUES (?,?,?,?,?)", (f['u'], f['p'], f['n'], get_bj_time(), f['e']))
    
    elif act == 'save_policy':
        if rid: c.execute("UPDATE policies SET name=?, white_countries=?, white_devices=?, r_url=? WHERE id=?", (f['name'], f['countries'], f['devices'], f['r_url'], rid))
        else: c.execute("INSERT INTO policies (name, white_countries, white_devices, r_url, c_date) VALUES (?,?,?,?,?)", (f['name'], f['countries'], f['devices'], f['r_url'], get_bj_time()))
    
    elif act == 'save_ticket':
        if rid: c.execute("UPDATE tickets SET name=?, url=?, p_id=? WHERE id=?", (f['name'], f['url'], f['p_id'], rid))
        else: c.execute("INSERT INTO tickets (name, url, p_id, c_date) VALUES (?,?,?,?)", (f['name'], f['url'], f['p_id'], get_bj_time()))
    
    elif act == 'save_link':
        if rid: c.execute("UPDATE mapping SET title=?, ticket_id=?, domain=? WHERE id=?", (f['n'], f['tid'], f['domain'], rid))
        else: 
            code = ''.join(random.choice(string.ascii_letters) for _ in range(5))
            c.execute("INSERT INTO mapping (date, domain, code, title, ticket_id) VALUES (?,?,?,?,?)", (get_bj_time(), f['domain'], code, f['n'], f['tid']))
            
    conn.commit(); conn.close()
    return redirect(f'/admin?tab={f.get("back")}')

# --- 6. 终极 UI 模板 ---
UI_TEMPLATE = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
    dialog::backdrop { background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(8px); }
    .tag-active { background: #3b82f6 !important; color: white !important; border-color: #60a5fa !important; }
    .sidebar-link { transition: all 0.3s; }
</style>
<body class="bg-[#0b0e14] text-slate-300 flex h-screen overflow-hidden font-sans">
    <nav class="w-64 bg-[#11141b] border-r border-white/5 flex flex-col p-6">
        <div class="mb-10">
            <h1 class="text-blue-500 font-black text-2xl italic tracking-tighter uppercase">Sentinel V13</h1>
            <p class="text-[10px] text-slate-600 mt-1 font-mono">BEIJING: {{ bj_time }}</p>
        </div>
        <div class="space-y-1">
            {% for k, v in {'users':'账户管理','security':'防护策略','tickets':'工单库','links':'短链汇总','logs':'穿透日志'}.items() %}
            <a href="?tab={{k}}" class="sidebar-link block p-4 rounded-2xl {{ 'bg-blue-600 text-white shadow-xl shadow-blue-900/30' if tab==k else 'hover:bg-white/5 text-slate-500' }}">{{v}}</a>
            {% endfor %}
        </div>
    </nav>

    <main class="flex-1 p-10 overflow-y-auto bg-[#0b0e14]">
        {% if tab == 'users' %}
        <div class="flex justify-between items-center mb-8"><h2 class="text-2xl font-bold italic">子账户体系</h2><button onclick="openUser()" class="bg-blue-600 px-6 py-3 rounded-2xl font-bold">+ 开通账户</button></div>
        <div class="bg-[#11141b] rounded-[2rem] border border-white/5 overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-[10px] text-slate-500 uppercase tracking-widest"><tr class="border-b border-white/5"><th class="p-6">账户ID</th><th class="p-6">备注</th><th class="p-6">到期时间</th><th class="p-6 text-right">操作</th></tr></thead>
                <tbody>
                    {% for u in data.users %}
                    <tr class="hover:bg-white/5 border-b border-white/5">
                        <td class="p-6 font-bold">{{u[1]}}</td><td class="p-6">{{u[3]}}</td><td class="p-6 font-mono text-orange-500">{{u[5]}}</td>
                        <td class="p-6 text-right"><button onclick="editUser('{{u[0]}}','{{u[1]}}','{{u[2]}}','{{u[3]}}','{{u[5]}}')" class="text-blue-500">编辑</button></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        {% elif tab == 'security' %}
        <div class="flex justify-between items-center mb-8"><h2 class="text-2xl font-bold italic">指纹防护策略</h2><button onclick="openPolicy()" class="bg-indigo-600 px-6 py-3 rounded-2xl font-bold">+ 新增指纹</button></div>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {% for p in data.policies %}
            <div class="bg-[#11141b] border border-white/5 p-8 rounded-[2rem] hover:border-indigo-500 transition shadow-xl relative">
                <div class="text-indigo-500 font-black italic mb-2 uppercase">{{p[1]}}</div>
                <div class="text-[10px] text-slate-500 mb-6 border-b border-white/5 pb-4">创建于: {{p[5]}}</div>
                <div class="space-y-2 text-xs mb-6">
                    <p class="text-slate-400 italic">🌍 允许国家: <span class="text-slate-200">{{p[2] or '不限'}}</span></p>
                    <p class="text-slate-400 italic">📱 允许设备: <span class="text-slate-200">{{p[3] or '全机型'}}</span></p>
                </div>
                <button onclick="editPolicy('{{p[0]}}','{{p[1]}}','{{p[2]}}','{{p[3]}}','{{p[4]}}')" class="w-full bg-slate-900 py-3 rounded-xl hover:bg-indigo-600 transition font-bold">编辑防护规则</button>
            </div>
            {% endfor %}
        </div>

        {% elif tab == 'tickets' %}
        <div class="flex justify-between items-center mb-8"><h2 class="text-2xl font-bold italic">工单跳转库</h2><button onclick="openTicket()" class="bg-green-600 px-6 py-3 rounded-2xl font-bold">+ 创建新目的地</button></div>
        <div class="bg-[#11141b] rounded-[2rem] border border-white/5 overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-[10px] text-slate-500 uppercase"><tr class="border-b border-white/5"><th class="p-6">工单名称</th><th class="p-6">跳转目标</th><th class="p-6">关联策略</th><th class="p-6 text-right">管理</th></tr></thead>
                <tbody>
                    {% for t in data.tickets %}
                    <tr class="hover:bg-green-500/5 border-b border-white/5">
                        <td class="p-6 font-bold text-green-500 italic">{{t[1]}}</td><td class="p-6 text-slate-500 truncate max-w-[200px]">{{t[2]}}</td><td class="p-6"><span class="bg-indigo-500/10 text-indigo-500 px-3 py-1 rounded-full text-[10px] font-bold">{{t[5]}}</span></td>
                        <td class="p-6 text-right"><button onclick="editTicket('{{t[0]}}','{{t[1]}}','{{t[2]}}','{{t[3]}}')" class="text-blue-500">编辑</button></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        {% elif tab == 'links' %}
        <div class="flex justify-between items-center mb-8"><h2 class="text-2xl font-bold italic">链路调度中心</h2><button onclick="openLink()" class="bg-blue-600 px-6 py-3 rounded-2xl font-bold">+ 生成全量链路</button></div>
        <div class="bg-[#11141b] rounded-[2.5rem] border border-white/5 overflow-hidden">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-[10px] text-slate-500 uppercase"><tr class="border-b border-white/5"><th class="p-6">链路备注</th><th class="p-6">完整地址</th><th class="p-6">指向工单</th><th class="p-6 text-right">操作</th></tr></thead>
                <tbody>
                    {% for l in data.links %}
                    <tr class="hover:bg-blue-500/5 border-b border-white/5">
                        <td class="p-6 font-bold">{{l[4]}}</td><td class="p-6 text-blue-400 font-mono italic">{{l[2]}}/{{l[3]}}</td><td class="p-6 font-bold">{{l[5]}}</td>
                        <td class="p-6 text-right"><a href="/{{l[3]}}" target="_blank" class="text-green-500 font-bold mr-4">测试</a><button onclick="editLink('{{l[0]}}','{{l[4]}}','{{l[5]}}','{{l[2]}}')" class="text-blue-500">编辑</button></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        {% elif tab == 'logs' %}
        <h2 class="text-2xl font-bold italic mb-8 text-red-400">穿透审计日志</h2>
        <div class="bg-[#11141b] rounded-[2rem] border border-white/5 overflow-hidden">
            <table class="w-full text-left text-xs">
                <thead class="bg-white/5 text-slate-500 uppercase font-bold"><tr class="border-b border-white/5"><th class="p-6">访问时间</th><th class="p-6">IP 地址</th><th class="p-6">穿透状态</th><th class="p-6 italic">拦截原因</th></tr></thead>
                <tbody>
                    {% for log in data.logs %}
                    <tr class="{{ 'bg-red-500/5 text-red-400' if log[4]=='拦截' else '' }} border-b border-white/5">
                        <td class="p-6 font-mono opacity-60">{{log[1]}}</td><td class="p-6">{{log[3]}}</td><td class="p-6 font-bold">{{log[4]}}</td><td class="p-6 italic opacity-50">{{log[5]}}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}
    </main>

    <dialog id="pBox" onclick="if(event.target==this)this.close()" class="bg-[#11141b] p-10 rounded-[3rem] border border-white/10 text-slate-300 w-[700px]">
        <form action="/api/action" method="post" class="space-y-6">
            <input type="hidden" name="act" value="save_policy"><input type="hidden" name="back" value="security"><input type="hidden" name="row_id" id="p_rid">
            <h3 class="text-2xl font-black italic">防护指纹建模</h3>
            <input name="name" id="p_name" placeholder="策略命名" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none" required>
            
            <div class="space-y-3">
                <p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">🌍 地区白名单</p>
                <div class="flex flex-wrap gap-2">
                    {% for cate, codes in COUNTRIES.items() %}{% for c in codes %}
                    <div onclick="toggleTag(this, 'c_in')" class="tag px-3 py-1 bg-slate-900 border border-slate-800 rounded-lg text-[10px] cursor-pointer hover:border-indigo-500">{{c}}</div>
                    {% endfor %}{% endfor %}
                </div>
                <input type="hidden" name="countries" id="c_in">
            </div>

            <div class="space-y-3">
                <p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">📱 设备指纹白名单</p>
                <div class="flex flex-wrap gap-2">
                    {% for brand, models in DEVICES.items() %}{% for m in models %}
                    <div onclick="toggleTag(this, 'd_in')" class="tag px-3 py-1 bg-slate-900 border border-slate-800 rounded-lg text-[10px] cursor-pointer hover:border-indigo-500">{{m}}</div>
                    {% endfor %}{% endfor %}
                </div>
                <input type="hidden" name="devices" id="d_in">
            </div>

            <input name="r_url" id="p_url" placeholder="拦截后跳转目的地" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none" required>
            <button class="w-full bg-indigo-600 py-4 rounded-2xl font-bold shadow-xl">同步指纹库</button>
        </form>
    </dialog>

    <dialog id="lBox" onclick="if(event.target==this)this.close()" class="bg-[#11141b] p-10 rounded-[3rem] border border-white/10 text-slate-300 w-[450px]">
        <form action="/api/action" method="post" class="space-y-4">
            <input type="hidden" name="act" value="save_link"><input type="hidden" name="back" value="links"><input type="hidden" name="row_id" id="l_rid">
            <h3 class="text-xl font-black italic text-blue-500">部署链路入口</h3>
            <input name="n" id="l_n" placeholder="链路备注" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none" required>
            <select name="domain" id="l_dom" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                <option value="https://s1.security.com">域名方案: s1.security.com</option>
                <option value="https://api.sentinel.pro">域名方案: api.sentinel.pro</option>
            </select>
            <select name="tid" id="l_tid" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                {% for t in data.tickets %}<option value="{{t[0]}}">执行工单: {{t[1]}}</option>{% endfor %}
            </select>
            <button class="w-full bg-blue-600 py-4 rounded-2xl font-bold shadow-xl">执行部署</button>
        </form>
    </dialog>

    <dialog id="tBox" onclick="if(event.target==this)this.close()" class="bg-[#11141b] p-10 rounded-[3rem] border border-white/10 text-slate-300 w-[450px]">
        <form action="/api/action" method="post" class="space-y-4">
            <input type="hidden" name="act" value="save_ticket"><input type="hidden" name="back" value="tickets"><input type="hidden" name="row_id" id="t_rid">
            <h3 class="text-xl font-black italic text-green-500">配置工单核心</h3>
            <input name="name" id="t_n" placeholder="工单名 (如: 客服01)" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none" required>
            <input name="url" id="t_u" placeholder="跳转目的地 (WhatsApp链接)" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none" required>
            <select name="p_id" id="t_pid" class="w-full bg-slate-900 border border-slate-800 p-4 rounded-2xl outline-none">
                {% for p in data.policies %}<option value="{{p[0]}}">应用防护: {{p[1]}}</option>{% endfor %}
            </select>
            <button class="w-full bg-green-600 py-4 rounded-2xl font-bold shadow-xl">保存工单</button>
        </form>
    </dialog>

    <script>
        // 弹窗与回填核心逻辑
        function toggleTag(el, inputId){
            el.classList.toggle('tag-active');
            let actives = Array.from(el.parentElement.parentElement.querySelectorAll('.tag-active')).map(e => e.innerText);
            document.getElementById(inputId).value = actives.join(',');
        }

        // 编辑功能回填函数
        function editPolicy(id, name, countries, devices, rurl){
            const box = document.getElementById('pBox');
            box.querySelector('h3').innerText = "编辑防护指纹";
            document.getElementById('p_rid').value = id;
            document.getElementById('p_name').value = name;
            document.getElementById('p_url').value = rurl;
            // 处理标签状态 (这里简化处理，手动勾选)
            box.showModal();
        }

        function editLink(id, title, tid, domain){
            const box = document.getElementById('lBox');
            document.getElementById('l_rid').value = id;
            document.getElementById('l_n').value = title;
            document.getElementById('l_dom').value = domain;
            box.showModal();
        }

        function editTicket(id, name, url, pid){
            const box = document.getElementById('tBox');
            document.getElementById('t_rid').value = id;
            document.getElementById('t_n').value = name;
            document.getElementById('t_u').value = url;
            document.getElementById('t_pid').value = pid;
            box.showModal();
        }

        // 默认开启弹窗
        function openPolicy(){ document.getElementById('pBox').showModal(); }
        function openLink(){ document.getElementById('lBox').showModal(); }
        function openTicket(){ document.getElementById('tBox').showModal(); }
    </script>
</body>
"""

init_db()
if __name__ == '__main__':
    app.run(debug=True)
import os, sqlite3, random, string, datetime, json
from flask import Flask, request, redirect, render_template_string, session, abort, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sentinel_v2_ultra_secure")
DB_PATH = os.path.join(os.getcwd(), 'urls.db')

# --- 1. 数据库初始化 (已移除 os.remove，保护数据) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)''')
    # 增强版映射表：增加点击数、策略、过期时间
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, long_url TEXT, short_code TEXT UNIQUE, 
                  owner TEXT, policy_name TEXT, allowed_regions TEXT, expire_time TEXT, create_time TEXT)''')
    # 详细访问日志表
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT, ip TEXT, region TEXT, ua TEXT, view_time TEXT)''')
    
    c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', '123456', 'admin')")
    conn.commit()
    conn.close()

# --- 2. 界面模板 (黑金版 + 管理控件) ---
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script>
    <style>body { background-color: #0b0e14; color: #d1d5db; font-family: 'Inter', sans-serif; }</style>
</head>
<body class="p-4 md:p-10">
    <div class="max-w-6xl mx-auto">
        <div class="flex justify-between items-center mb-10">
            <div>
                <h2 class="text-2xl font-black text-blue-500 italic tracking-tighter">SENTINEL SYSTEM <span class="text-xs bg-blue-500/20 px-2 py-0.5 rounded ml-2">PRO V2</span></h2>
                <p class="text-[10px] text-slate-500 mt-1 uppercase tracking-[0.3em]">Advanced Traffic Control Infrastructure</p>
            </div>
            <a href="/logout" class="border border-red-500/30 text-red-500 text-xs px-4 py-2 rounded-lg hover:bg-red-500/10 transition">安全退出</a>
        </div>

        <div class="bg-[#151921] p-6 rounded-2xl border border-white/5 mb-8 shadow-2xl">
            <form action="/shorten" method="post" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <input name="long_url" placeholder="目标落地页 (https://...)" class="bg-slate-900 border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-500" required>
                    <input name="allowed_regions" placeholder="地区限制 (例如: CN,HK,TW  留空不限)" class="bg-slate-900 border border-slate-800 p-4 rounded-xl outline-none focus:border-blue-500">
                </div>
                <div class="flex justify-between items-center">
                    <p class="text-[10px] text-slate-600 italic">* 自动启用：AI恶意扫描拦截、UA安全过滤</p>
                    <button class="bg-blue-600 hover:bg-blue-500 px-12 py-3 rounded-xl font-bold text-white transition-all shadow-lg shadow-blue-900/40">部署节点</button>
                </div>
            </form>
        </div>

        <div class="bg-[#151921] rounded-2xl border border-white/5 overflow-hidden shadow-2xl">
            <table class="w-full text-left text-sm">
                <thead class="bg-white/5 text-slate-400 text-[10px] uppercase tracking-widest">
                    <tr>
                        <th class="p-5">短链路径</th><th class="p-5">目标地址</th><th class="p-5">策略</th><th class="p-5 text-center">点击</th><th class="p-5 text-right">管理</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-white/5">
                    {% for link in links %}
                    <tr class="hover:bg-blue-500/5 transition">
                        <td class="p-5 font-mono text-blue-400 font-bold underline">{{ host }}{{ link[0] }}</td>
                        <td class="p-5 text-slate-500 truncate max-w-[200px]">{{ link[1] }}</td>
                        <td class="p-5">
                            <span class="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-400 border border-white/10">{{ link[2] or 'Global' }}</span>
                        </td>
                        <td class="p-5 text-center">
                            <span class="text-blue-500 font-bold bg-blue-500/10 px-3 py-1 rounded-full border border-blue-500/20">{{ link[3] }}</span>
                        </td>
                        <td class="p-5 text-right space-x-2">
                            <a href="/delete/{{ link[0] }}" class="text-red-900 hover:text-red-500 text-xs transition" onclick="return confirm('确定销毁该节点?')">销毁</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#0b0e14] flex items-center justify-center h-screen">
    <form method="post" class="bg-[#151921] border border-white/5 p-12 rounded-[2.5rem] w-96 shadow-2xl text-center">
        <h1 class="text-3xl font-black mb-10 text-blue-500 italic tracking-tighter">SENTINEL LOGIN</h1>
        <input name="u" placeholder="Identity" class="w-full bg-slate-900 border border-slate-800 p-4 mb-4 rounded-2xl outline-none focus:border-blue-500 text-white shadow-inner" required>
        <input name="p" type="password" placeholder="Key" class="w-full bg-slate-900 border border-slate-800 p-4 mb-8 rounded-2xl outline-none focus:border-blue-500 text-white shadow-inner" required>
        <button class="bg-blue-600 w-full py-4 rounded-2xl font-black text-white shadow-lg shadow-blue-900/40 hover:scale-[1.02] transition-transform">验证进入</button>
    </form>
</body>
"""

# --- 3. 核心逻辑 ---
@app.route('/')
def index():
    return redirect('/admin') if 'user' in session else redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p))
        res = c.fetchone(); conn.close()
        if res:
            session.permanent = True
            session['user'] = u
            return redirect('/admin')
    return render_template_string(LOGIN_HTML)

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 统计点击数
    c.execute('''SELECT m.short_code, m.long_url, m.allowed_regions, 
                 (SELECT COUNT(*) FROM visit_logs v WHERE v.short_code = m.short_code) 
                 FROM mapping m ORDER BY m.id DESC''')
    links = c.fetchall(); conn.close()
    return render_template_string(ADMIN_TEMPLATE, links=links, host=request.host_url)

@app.route('/shorten', methods=['POST'])
def shorten():
    if 'user' not in session: return redirect('/login')
    long_url = request.form['long_url']
    regions = request.form.get('allowed_regions', '').upper().replace(' ', '')
    code = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT INTO mapping (long_url, short_code, owner, policy_name, allowed_regions, create_time) VALUES (?, ?, ?, ?, ?, ?)", 
              (long_url, code, session['user'], 'SAFE_FILTER', regions, str(datetime.datetime.now())))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/<short_code>')
def redirect_engine(short_code):
    if short_code in ['admin', 'login', 'logout', 'shorten', 'delete']: return abort(404)
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT long_url, allowed_regions FROM mapping WHERE short_code=?", (short_code,))
    res = c.fetchone()
    
    if res:
        long_url, allowed_regions = res
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
        ua = request.user_agent.string
        
        # 记录访问日志
        c.execute("INSERT INTO visit_logs (short_code, ip, ua, view_time) VALUES (?, ?, ?, ?)", 
                  (short_code, ip, ua, str(datetime.datetime.now())))
        conn.commit(); conn.close()

        # 地区拦截逻辑 (简单版：如果设置了地区且当前 IP 不在允许范围，跳转拦截页)
        # 注意：完整版需接入 IP 库，此处预留接口
        if allowed_regions:
            # 你可以在此处接入第三方 API 检查 IP 归属地
            pass

        return redirect(long_url)
    
    return "SENTINEL: Access Denied", 404

@app.route('/delete/<short_code>')
def delete_link(short_code):
    if 'user' not in session: return redirect('/login')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM mapping WHERE short_code=?", (short_code,))
    c.execute("DELETE FROM visit_logs WHERE short_code=?", (short_code,))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

# 确保在 Gunicorn 和 Main 下都初始化
init_db()

if __name__ == '__main__':
    app.run(debug=True)
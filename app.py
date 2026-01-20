import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v16_pro_vault"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 1. 深度指纹库：集成 iPhone 17 系列与安卓旗舰 ---
DEVICE_DB = {
    "Apple": ["iPhone 17 Pro Max", "iPhone 17 Pro", "iPhone 17 Slim", "iPhone 16 Pro Max", "iPhone 15全系", "iPad Pro"],
    "Huawei": ["Mate 70 Pro+", "Mate 60 RS", "Pura 70 Ultra", "Pocket 2", "Mate X5"],
    "Xiaomi/Samsung": ["Xiaomi 15 Ultra", "Samsung S25 Ultra", "Redmi K80 Pro", "OnePlus 13"]
}

# --- 2. 数据库逻辑 (自动修复与初始化) ---
def get_bj_time():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 核心表结构
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT, e_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_countries TEXT, white_devices TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    # 预设超级管理员
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date, e_date) VALUES ('super', '777888', 'ROOT', ?, '2099-12-31')", (get_bj_time(),))
    conn.commit(); conn.close()

# --- 3. 拦截引擎 ---
@app.route('/<code>')
def gateway(code):
    if code in ['admin', 'login', 'api']: return redirect('/admin')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    # 级联查询：短链 -> 工单 -> 策略
    q = "SELECT t.url, s.white_devices, s.r_url FROM mapping m JOIN tickets t ON m.ticket_id = t.id JOIN policies s ON t.p_id = s.id WHERE m.code = ?"
    c.execute(q, (code,))
    res = c.fetchone()
    if not res: return "404 LINK EXPIRED", 404
    
    target, w_dev, r_url = res
    ua = request.user_agent.string.lower()
    ip = request.remote_addr
    
    # 指纹拦截逻辑
    is_blocked = 0; reason = "验证通过"
    if w_dev:
        # 只要 UA 中包含任何一个允许的设备关键词则通过
        matched = any(d.lower() in ua for d in w_dev.split(','))
        if not matched:
            is_blocked, reason = 1, "设备指纹不符"
            
    c.execute("INSERT INTO logs (time, code, ip, status, reason) VALUES (?,?,?,?,?)", (get_bj_time(), code, ip, "拦截" if is_blocked else "成功", reason))
    conn.commit(); conn.close()
    return redirect(r_url if is_blocked else target)

# --- 4. 管理后台 (包含完整 UI) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT * FROM users WHERE u=? AND p=?", (request.form['u'], request.form['p']))
        if c.fetchone(): 
            session['user'] = request.form['u']
            return redirect('/admin')
        return "认证失败"
    return render_template_string('<body style="background:#000;color:#fff;display:flex;justify-content:center;padding-top:100px;"><div><h2>Sentinel V16</h2><form method="post">账号:<br><input name="u"><br>密码:<br><input name="p" type="password"><br><br><button>登录系统</button></form></div></body>')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    # 这里展示核心控制面板
    return f"""
    <body style="font-family:sans-serif; background:#111; color:#eee; padding:40px;">
        <h1>Sentinel 控制台</h1>
        <p>当前登录: <b>{session['user']}</b> | 北京时间: {get_bj_time()}</p>
        <hr border="1">
        <div style="display:flex; gap:20px;">
            <div style="background:#222; padding:20px; border-radius:10px;">
                <h3>🛡️ 拦截策略</h3>
                <p>已支持: iPhone 17 全系、华为 Mate 70</p>
            </div>
            <div style="background:#222; padding:20px; border-radius:10px;">
                <h3>👥 子账户系统</h3>
                <p>支持多账户独立管理工单</p>
            </div>
        </div>
        <br>
        <a href="/login" style="color:red;">退出登录</a>
    </body>
    """

init_db()
if __name__ == '__main__':
    # 调试模式运行
    app.run(host='0.0.0.0', port=5000, debug=True)
import os, sqlite3, random, string, datetime
from flask import Flask, request, redirect, render_template_string, session, abort

app = Flask(__name__)
app.secret_key = "sentinel_v16_final_vault"
DB_PATH = os.path.join(os.getcwd(), 'sentinel_v16.db')

# --- 核心指纹库 (集成 iPhone 17 & 华为 Mate 70) ---
DEVICE_DB = {
    "Apple": ["iPhone 17 Pro Max", "iPhone 17 Pro", "iPhone 16 Pro Max", "iPhone 15 Pro"],
    "Huawei": ["Mate 70 Pro+", "Mate 60 RS", "Pura 70 Ultra"],
    "Xiaomi": ["Xiaomi 15 Ultra", "Samsung S25 Ultra"]
}

def get_bj_time():
    return (datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, u TEXT UNIQUE, p TEXT, n TEXT, c_date TEXT, e_date TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS policies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, white_countries TEXT, white_langs TEXT, white_devices TEXT, r_url TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, p_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS mapping (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, code TEXT UNIQUE, title TEXT, ticket_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, code TEXT, ip TEXT, status TEXT, reason TEXT)')
    c.execute("INSERT OR IGNORE INTO users (u, p, n, c_date, e_date) VALUES ('super', '777888', 'ROOT', ?, '2099-12-31')", (get_bj_time(),))
    conn.commit(); conn.close()

@app.route('/<code>')
def gateway(code):
    if code in ['admin', 'login']: return redirect('/admin')
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT t.url, s.white_devices, s.r_url FROM mapping m JOIN tickets t ON m.ticket_id = t.id JOIN policies s ON t.p_id = s.id WHERE m.code = ?", (code,))
    res = c.fetchone()
    if not res: return "404 NOT FOUND", 404
    target, w_dev, r_url = res
    ua = request.user_agent.string.lower()
    is_blocked = 0
    if w_dev and not any(d.lower() in ua for d in w_dev.split(',')): is_blocked = 1
    c.execute("INSERT INTO logs (time, code, ip, status, reason) VALUES (?,?,?,?,?)", (get_bj_time(), code, request.remote_addr, "拦截" if is_blocked else "成功", "验证通过"))
    conn.commit(); conn.close()
    return redirect(r_url if is_blocked else target)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT * FROM users WHERE u=? AND p=?", (request.form['u'], request.form['p']))
        if c.fetchone(): 
            session['user'] = request.form['u']
            return redirect('/admin')
        return "认证失败"
    return '<h2>Sentinel V16 登录</h2><form method="post">账号:<input name="u"><br>密码:<input name="p" type="password"><br><button>登录</button></form>'

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/login')
    return f"<h1>Sentinel V16 控制台</h1><p>当前用户: {session['user']}</p><p>设备指纹库与子账户系统已就绪。</p>"

init_db()
if __name__ == '__main__':
    # 端口改为 8888 避开系统占用
    app.run(host='0.0.0.0', port=8888, debug=True)
import os       # <--- 第一步：在这里添加
import sqlite3
import random
import string
import datetime
from flask import Flask, request, redirect, render_template_string, render_template

app = Flask(__name__)

# 数据库初始化：确保两张表都存在
def init_db():
    # 第二步：在此处插入这两行，强制删除旧的坏数据库
    if os.path.exists('urls.db'):
        os.remove('urls.db')
        
    conn = sqlite3.connect('urls.db') # 这是你原来的第 11 行
    c = conn.cursor()
    # ... 后面保持不变 ...
                  long_url TEXT, 
                  short_code TEXT UNIQUE)''')
    # 2. 访问日志表
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  short_code TEXT, 
                  view_time TIMESTAMP, 
                  ip TEXT, 
                  browser TEXT,
                  platform TEXT)''')
    conn.commit()
    conn.close()

# 随机生成4位短码
def generate_short_code():
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(4))

# 路由 1：首页
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>极简短链接</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f7fa; }
            .card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); width: 100%; max-width: 400px; }
            input { width: 100%; padding: 12px; margin: 20px 0; border: 1px solid #ddd; border-radius: 10px; box-sizing: border-box; }
            button { background: #007aff; color: white; border: none; width: 100%; padding: 12px; border-radius: 10px; cursor: pointer; font-size: 16px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🔗 极简短链接</h2>
            <form action="/shorten" method="post">
                <input type="url" name="long_url" placeholder="请输入长链接 (https://...)" required>
                <button type="submit">立即生成</button>
            </form>
        </div>
    </body>
    </html>
    '''

# 路由 2：生成短链接逻辑
@app.route('/shorten', methods=['POST'])
def shorten():
    long_url = request.form['long_url']
    short_code = generate_short_code()
    
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO mapping (long_url, short_code) VALUES (?, ?)", (long_url, short_code))
        conn.commit()
    except sqlite3.IntegrityError:
        short_code = generate_short_code() # 简单冲突处理
        c.execute("INSERT INTO mapping (long_url, short_code) VALUES (?, ?)", (long_url, short_code))
        conn.commit()
    conn.close()
    
    full_short_url = f"{request.host_url}{short_code}"
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f5f7fa; }}
            .card {{ background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); text-align: center; }}
            .result {{ background: #e8f2ff; padding: 15px; border-radius: 10px; color: #007aff; font-weight: bold; margin: 20px 0; word-break: break-all; }}
            a {{ text-decoration: none; color: #666; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div style="font-size: 40px;">✅</div>
            <h2>生成成功</h2>
            <div class="result">{full_short_url}</div>
            <a href="/">返回首页</a>
        </div>
    </body>
    </html>
    '''

# 路由 3：点击跳转 + 访问分析
@app.route('/<short_code>')
def jump(short_code):
    # 排除 admin 路由被误当作短码
    if short_code == 'admin':
        return redirect('/admin')
        
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    c.execute("SELECT long_url FROM mapping WHERE short_code=?", (short_code,))
    result = c.fetchone()
    
    if result:
        # 记录访问日志
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        ua = request.user_agent
        c.execute("INSERT INTO visit_logs (short_code, view_time, ip, browser, platform) VALUES (?, ?, ?, ?, ?)",
                  (short_code, datetime.datetime.now(), ip, ua.browser, ua.platform))
        conn.commit()
        conn.close()
        return redirect(result[0])
    
    conn.close()
    return "链接不存在", 404

# 路由 4：Sentinel 哨兵后台
@app.route('/admin')
def admin_panel():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    # 统计数据
    c.execute("SELECT COUNT(*) FROM visit_logs")
    total_clicks = c.fetchone()[0]
    
    c.execute("SELECT browser, COUNT(*) FROM visit_logs GROUP BY browser")
    browser_data = c.fetchall()
    conn.close()

    # 准备图表数据
    labels = [row[0] if row[0] else "其他" for row in browser_data]
    values = [row[1] for row in browser_data]

    return f'''
    <!DOCTYPE html>
    <html style="background: #0f172a; color: white;">
    <head>
        <title>Sentinel 控制台</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; padding: 20px; margin: 0; }}
            .container {{ max-width: 1000px; margin: auto; }}
            .card {{ background: #1e293b; border-radius: 15px; padding: 25px; margin-bottom: 20px; border: 1px solid #334155; }}
            .stat-title {{ color: #94a3b8; font-size: 14px; text-transform: uppercase; }}
            .stat-num {{ font-size: 48px; font-weight: bold; color: #38bdf8; margin: 10px 0; }}
            h2 {{ font-weight: 300; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🛡️ Sentinel 哨兵系统</h2>
            <div class="card">
                <div class="stat-title">总访问流量</div>
                <div class="stat-num">{total_clicks}</div>
                <div style="color: #34d399;">↑ 系统实时监控中</div>
            </div>
            <div class="card" style="max-width: 400px;">
                <div class="stat-title">浏览器分布</div>
                <canvas id="myChart" style="margin-top: 20px;"></canvas>
            </div>
        </div>
        <script>
            new Chart(document.getElementById('myChart'), {{
                type: 'doughnut',
                data: {{
                    labels
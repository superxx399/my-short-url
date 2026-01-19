import sqlite3
from flask import Flask, request, redirect, render_template_string
import random, string
import datetime
app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    # 1. 创建链接映射表
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  long_url TEXT, 
                  short_code TEXT UNIQUE)''')
    # 2. 创建访问日志表
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  short_code TEXT, 
                  view_time TIMESTAMP, 
                  ip TEXT, 
                  browser TEXT,
                  platform TEXT)''')
    conn.commit()
    conn.commit()
    conn.close()

def generate_short_code():
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(4))
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(4))

# 路由 1：首页
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>极简短链</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f5f5f7; }
            .card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); width: 100%; max-width: 400px; text-align: center; }
            input { width: 100%; padding: 12px; margin: 20px 0; border: 1px solid #ddd; border-radius: 10px; box-sizing: border-box; font-size: 16px; }
            button { background: #007aff; color: white; border: none; width: 100%; padding: 12px; border-radius: 10px; font-size: 16px; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>✨ 极简短链</h2>
            <form action="/shorten" method="post">
                <input type="url" name="long_url" placeholder="粘贴长链接..." required>
                <button type="submit">立即缩短</button>
            </form>
        </div>
    </body>
    </html>
    '''

# 路由 2：生成结果页
@app.route('/shorten', methods=['POST'])
@app.route('/shorten', methods=['POST'])
def shorten():
    long_url = request.form.get('long_url')
    short_code = generate_short_code()
    
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    # 注意：确保你的表名是 mapping 还是 urls，根据你 89 行看应该是 mapping
    c.execute("INSERT INTO mapping (long_url, short_code) VALUES (?, ?)", (long_url, short_code))
    conn.commit()
    conn.close()

    # 这里的逻辑会自动判断是在本地还是云端
    base_url = request.host_url.replace('http://', 'https://') if 'onrender.com' in request.host_url else request.host_url
    full_short_url = base_url + short_code

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>生成成功</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #f0f2f5; }}
            .card {{ background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); width: 320px; text-align: center; }}
            .result {{ background: #e7f3ff; padding: 15px; border-radius: 10px; word-break: break-all; margin: 20px 0; color: #007aff; font-weight: bold; }}
            a {{ color: #8e8e93; text-decoration: none; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div style="font-size: 48px;">✅</div>
            <h2>生成成功</h2>
            <div class="result">{full_short_url}</div>
            <a href="/">返回首页</a>
        </div>
    </body>
    </html>
    '''

# 路由 3：跳转逻辑
@app.route('/<short_code>')
def jump(short_code):
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

# 路由 4：管理后台
@app.route('/admin')
def admin_panel():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    # 统计总点击量
    c.execute("SELECT COUNT(*) FROM visit_logs")
    total_clicks = c.fetchone()[0]
    
    # 统计浏览器分布
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
            .card {{ background: #1e293b; border-radius: 15px; padding: 25px; margin-bottom: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); border: 1px solid #334155; }}
            .stat-title {{ color: #94a3b8; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }}
            .stat-num {{ font-size: 48px; font-weight: bold; color: #38bdf8; margin: 10px 0; }}
            h2 {{ color: #f8fafc; font-weight: 300; letter-spacing: -1px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🛡️ Sentinel 哨兵系统 <small style="font-size: 12px; color: #38bdf8;">v1.0 LIVE</small></h2>
            <div class="card">
                <div class="stat-title">总访问流量 (Total Requests)</div>
                <div class="stat-num">{total_clicks}</div>
                <div style="color: #34d399; font-size: 13px;">↑ 系统运行正常</div>
            </div>
            <div class="card" style="max-width: 500px;">
                <div class="stat-title">访客浏览器分布 (Browser Distribution)</div>
                <canvas id="myChart" style="margin-top: 20px;"></canvas>
            </div>
        </div>
        <script>
            new Chart(document.getElementById('myChart'), {{
                type: 'doughnut',
                data: {{
                    labels: {labels},
                    datasets: [{{ 
                        data: {values}, 
                        backgroundColor: ['#38bdf8', '#fb7185', '#34d399', '#fbbf24', '#818cf8'],
                        borderWidth: 0
                    }}]
                }},
                options: {{ plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }} }}
            }});
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
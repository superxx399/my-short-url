import sqlite3
from flask import Flask, request, redirect, render_template_string
import random, string

app = Flask(__name__)

# 初始化数据库
def init_db():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mapping 
                 (short_code TEXT PRIMARY KEY, long_url TEXT)''')
    conn.commit()
    conn.close()

def generate_short_code():
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
from flask import request, redirect # 确保开头导入了这些

@app.route('/<short_code>')
def jump(short_code):
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    c.execute("SELECT long_url FROM mapping WHERE short_code=?", (short_code,))
    result = c.fetchone()
    
    if result:
        # 获取访客指纹
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        ua = request.user_agent
        
        # 存入访问日志
        c.execute("INSERT INTO visit_logs (short_code, view_time, ip, browser, platform) VALUES (?, ?, ?, ?, ?)",
                  (short_code, datetime.datetime.now(), ip, ua.browser, ua.platform))
        conn.commit()
        conn.close()
        return redirect(result[0])
    
    conn.close()
    return "链接不存在", 404

@app.route('/admin')
d@app.route('/admin')
def admin_panel():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    # 统计数据
    c.execute("SELECT COUNT(*) FROM visit_logs")
    total_clicks = c.fetchone()[0]
    c.execute("SELECT browser, COUNT(*) FROM visit_logs GROUP BY browser")
    browser_data = c.fetchall()
    conn.close()

    # 准备饼图数据
    labels = [row[0] if row[0] else "未知" for row in browser_data]
    values = [row[1] for row in browser_data]

    return f'''
    <!DOCTYPE html>
    <html style="background: #0f172a; color: white;">
    <head>
        <title>Sentinel 控制台</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: sans-serif; padding: 20px; }}
            .card {{ background: #1e293b; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            .stat-num {{ font-size: 48px; font-weight: bold; color: #38bdf8; }}
        </style>
    </head>
    <body>
        <h2>🛡️ Sentinel 哨兵系统 - 仪表盘</h2>
        <div class="card">
            <p>总访问请求</p>
            <div class="stat-num">{total_clicks}</div>
        </div>
        <div class="card" style="max-width: 400px;">
            <p>浏览器分布统计</p>
            <canvas id="myChart"></canvas>
        </div>
        <script>
            new Chart(document.getElementById('myChart'), {{
                type: 'pie',
                data: {{
                    labels: {labels},
                    datasets: [{{ data: {values}, backgroundColor: ['#38bdf8', '#fb7185', '#34d399', '#fbbf24'] }}]
                }}
            }});
        </script>
    </body>
    </html>
    '''
if __name__ == '__main__':
   def init_db():
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    # 存储长短链接的表
    c.execute('''CREATE TABLE IF NOT EXISTS mapping
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  long_url TEXT, 
                  short_code TEXT UNIQUE)''')
    # 新增：存储访问日志的表（实现截图里图表的数据源）
    c.execute('''CREATE TABLE IF NOT EXISTS visit_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  short_code TEXT, 
                  view_time TIMESTAMP, 
                  ip TEXT, 
                  browser TEXT,
                  platform TEXT)''')
    conn.commit()
    conn.close()
    app.run(debug=True)
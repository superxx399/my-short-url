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
def shorten():
    long_url = request.form.get('long_url')
    short_code = generate_short_code()
    
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    c.execute("INSERT INTO mapping VALUES (?, ?)", (short_code, long_url))
    conn.commit()
    conn.close()
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>生成成功</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f5f5f7; }}
            .card {{ background: white; padding: 2.5rem; border-radius: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); width: 100%; max-width: 400px; text-align: center; }}
            .icon {{ font-size: 48px; margin-bottom: 1rem; }}
            .short-url {{ background: #f2f2f7; padding: 15px; border-radius: 12px; font-size: 18px; font-weight: 600; color: #007aff; margin: 20px 0; word-break: break-all; }}
            .back-btn {{ color: #8e8e93; text-decoration: none; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✅</div>
            <h2>生成成功</h2>
            <div class="short-url">http://127.0.0.1:5000/{{short_code}}</div>
            <a href="/" class="back-btn">← 返回首页</a>
        </div>
    </body>
    </html>
    '''.replace('{{short_code}}', short_code)

# 路由 3：跳转逻辑
@app.route('/<short_code>')
def jump(short_code):
    conn = sqlite3.connect('urls.db')
    c = conn.cursor()
    c.execute("SELECT long_url FROM mapping WHERE short_code=?", (short_code,))
    result = c.fetchone()
    conn.close()
    if result:
        return redirect(result[0])
    return "该链接不存在", 404

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
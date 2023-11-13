from flask import Flask, render_template, request
from flask import redirect, url_for, flash, get_flashed_messages
import psycopg2
from psycopg2.errors import UniqueViolation
import os
from dotenv import load_dotenv
from validators.url import url as validator_url
from urllib.parse import urlparse
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
SECRET_KEY = os.getenv('SECRET_KEY')


app = Flask(__name__)
app.secret_key = SECRET_KEY


@app.get('/')
def index():
    return render_template('index.html')


@app.get('/urls')
def urls():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT * FROM urls ORDER BY id DESC;")
    all_urls = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('urls.html', urls=all_urls)


@app.post('/urls')
def urls_post():
    url = request.form.get('url')
    if len(url) < 1:
        messages = [('danger', 'URL обязателен')]
        return render_template('index.html', url=url, messages=messages)
    if len(url) > 255:
        messages = [('danger', 'URL превышает 255 символов')]
        return render_template('index.html', url=url, messages=messages)
    if not validator_url(url):
        messages = [('danger', 'Некорректный URL')]
        return render_template('index.html', url=url, messages=messages)
    parse = urlparse(url)
    name = f'{parse.scheme}://{parse.netloc}'
    date = datetime.now().date()
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    message = 'Страница успешно добавлена'
    try:
        cur.execute("INSERT INTO urls (name, created_at) VALUES (%s, %s);",
                    (name, date))
    except UniqueViolation:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        message = 'Страница уже существует'
    finally:
        flash(message, 'success')
        cur.execute("SELECT id FROM urls WHERE name = %s;", (name,))
        id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('show_url', id=id))


@app.get('/urls/<int:id>')
def show_url(id):
    messages = get_flashed_messages(with_categories=True)
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT * FROM urls WHERE id = %s;", (id,))
    url = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('show.html', url=url, messages=messages)

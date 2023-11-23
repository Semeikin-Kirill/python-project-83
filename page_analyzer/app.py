from flask import Flask, render_template, request, make_response
from flask import redirect, url_for, flash, get_flashed_messages
import psycopg2
from psycopg2.errors import UniqueViolation
from psycopg2.extras import NamedTupleCursor
import os
from dotenv import load_dotenv
from validators.url import url as validator_url
from urllib.parse import urlparse
from datetime import datetime
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
SECRET_KEY = os.getenv('SECRET_KEY')


app = Flask(__name__)
app.secret_key = SECRET_KEY


@app.get('/')
def index():
    return render_template('index.html',)


@app.get('/urls')
def urls():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=NamedTupleCursor)
    cur.execute("""SELECT DISTINCT ON (urls.id) urls.id AS id,
                       url_checks.status_code AS status_code,
                       url_checks.created_at AS created_at,
                       urls.name AS name FROM url_checks RIGHT JOIN urls
                       ON urls.id = url_checks.url_id
                       ORDER BY urls.id DESC, created_at DESC""")
    all_urls = cur.fetchall()
    print(all_urls)
    cur.close()
    conn.close()
    return render_template('urls.html', urls=all_urls)


@app.post('/urls')
def urls_post():
    url = request.form.get('url')
    if len(url) < 1:
        messages = [('danger', 'URL обязателен')]
        return make_response(render_template('index.html',
                                             url=url, messages=messages), 422)
    if len(url) > 255:
        messages = [('danger', 'URL превышает 255 символов')]
        return make_response(render_template('index.html',
                                             url=url, messages=messages), 422)
    if not validator_url(url):
        messages = [('danger', 'Некорректный URL')]
        return make_response(render_template('index.html',
                                             url=url, messages=messages), 422)
    parse = urlparse(url)
    name = f'{parse.scheme}://{parse.netloc}'
    date = datetime.now()
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
    cur = conn.cursor(cursor_factory=NamedTupleCursor)
    cur.execute("SELECT * FROM urls WHERE id = %s;", (id,))
    url = cur.fetchone()
    cur.execute("""SELECT * FROM url_checks
                   WHERE url_id = %s
                   ORDER BY created_at DESC;""", (id,))
    checks = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('show.html',
                           url=url, checks=checks, messages=messages)


@app.post('/urls/<int:id>/checks')
def check(id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    date = datetime.now()
    cur.execute("SELECT name FROM urls WHERE id = %s;", (id,))
    name = cur.fetchone()[0]
    try:
        request = requests.get(name)
        request.raise_for_status()
    except RequestException:
        flash('Произошла ошибка при проверке', 'danger')
        return redirect(url_for('show_url', id=id))
    soup = BeautifulSoup(request.text, 'html.parser')
    title = soup.title.string if soup.title else ''
    strings = soup.h1.strings
    h1 = ''
    for string in strings:
        h1 += string
    description = soup.find(attrs={'name': "description"})
    description = description['content'] if description else ''
    status = request.status_code
    cur.execute("""INSERT INTO url_checks (url_id, created_at,
                    status_code, title, h1, description)
                    VALUES (%s, %s, %s, %s, %s, %s);""",
                (id, date, status, title, h1, description))
    flash('Страница успешно проверена', 'success')
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('show_url', id=id))

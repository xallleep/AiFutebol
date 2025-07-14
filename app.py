import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-key-123'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configurações
DATABASE = 'matches.db'
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = generate_password_hash(os.environ.get('ADMIN_PASS', 'admin123'))

# Inicialização do banco de dados
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 home_team TEXT NOT NULL,
                 away_team TEXT NOT NULL,
                 competition TEXT,
                 location TEXT,
                 match_date TEXT NOT NULL,
                 match_time TEXT NOT NULL,
                 predicted_score TEXT,
                 home_win_percent INTEGER,
                 draw_percent INTEGER,
                 away_win_percent INTEGER,
                 over_15_percent INTEGER,
                 over_25_percent INTEGER,
                 btts_percent INTEGER,
                 details TEXT,
                 display_order INTEGER DEFAULT 0,
                 color_scheme TEXT DEFAULT 'blue',
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# Funções auxiliares
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def format_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except:
        return date_str

# Rotas principais
@app.route('/')
def index():
    conn = get_db()
    matches = conn.execute('SELECT * FROM matches ORDER BY display_order, match_date, match_time').fetchall()
    conn.close()
    
    today = datetime.now().strftime('%Y-%m-%d')
    today_matches = []
    other_matches = []
    
    for m in matches:
        match = dict(m)
        match['is_today'] = match['match_date'] == today
        match['formatted_date'] = format_date(match['match_date'])
        
        if match['is_today']:
            today_matches.append(match)
        else:
            other_matches.append(match)
    
    last_updated = datetime.now().strftime('%d/%m/%Y às %H:%M')
    
    return render_template('index.html', 
                         today_matches=today_matches,
                         other_matches=other_matches,
                         last_updated=last_updated)

# Área administrativa
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USER and check_password_hash(ADMIN_PASS, password):
            session['admin_logged_in'] = True
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Credenciais inválidas', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    matches = conn.execute('SELECT * FROM matches ORDER BY display_order, match_date, match_time').fetchall()
    conn.close()
    
    formatted_matches = []
    for m in matches:
        match = dict(m)
        match['formatted_date'] = format_date(match['match_date'])
        formatted_matches.append(match)
    
    return render_template('admin/dashboard.html', matches=formatted_matches)

@app.route('/admin/add', methods=['GET', 'POST'])
def add_match():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        home_team = request.form.get('home_team')
        away_team = request.form.get('away_team')
        competition = request.form.get('competition')
        location = request.form.get('location')
        match_date = request.form.get('match_date')
        match_time = request.form.get('match_time')
        predicted_score = request.form.get('predicted_score')
        home_win_percent = request.form.get('home_win_percent', 0)
        draw_percent = request.form.get('draw_percent', 0)
        away_win_percent = request.form.get('away_win_percent', 0)
        over_15_percent = request.form.get('over_15_percent', 0)
        over_25_percent = request.form.get('over_25_percent', 0)
        btts_percent = request.form.get('btts_percent', 0)
        details = request.form.get('details')
        display_order = request.form.get('display_order', 0)
        color_scheme = request.form.get('color_scheme', 'blue')
        
        conn = get_db()
        conn.execute('''INSERT INTO matches 
                      (home_team, away_team, competition, location, match_date, match_time, 
                      predicted_score, home_win_percent, draw_percent, away_win_percent,
                      over_15_percent, over_25_percent, btts_percent, details, 
                      display_order, color_scheme)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (home_team, away_team, competition, location, match_date, match_time,
                     predicted_score, home_win_percent, draw_percent, away_win_percent,
                     over_15_percent, over_25_percent, btts_percent, details,
                     display_order, color_scheme))
        conn.commit()
        conn.close()
        
        flash('Partida adicionada com sucesso!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/add_match.html')

@app.route('/admin/edit/<int:match_id>', methods=['GET', 'POST'])
def edit_match(match_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    
    if request.method == 'POST':
        home_team = request.form.get('home_team')
        away_team = request.form.get('away_team')
        competition = request.form.get('competition')
        location = request.form.get('location')
        match_date = request.form.get('match_date')
        match_time = request.form.get('match_time')
        predicted_score = request.form.get('predicted_score')
        home_win_percent = request.form.get('home_win_percent', 0)
        draw_percent = request.form.get('draw_percent', 0)
        away_win_percent = request.form.get('away_win_percent', 0)
        over_15_percent = request.form.get('over_15_percent', 0)
        over_25_percent = request.form.get('over_25_percent', 0)
        btts_percent = request.form.get('btts_percent', 0)
        details = request.form.get('details')
        display_order = request.form.get('display_order', 0)
        color_scheme = request.form.get('color_scheme', 'blue')
        
        conn.execute('''UPDATE matches SET
                      home_team = ?, away_team = ?, competition = ?, location = ?, 
                      match_date = ?, match_time = ?, predicted_score = ?,
                      home_win_percent = ?, draw_percent = ?, away_win_percent = ?,
                      over_15_percent = ?, over_25_percent = ?, btts_percent = ?,
                      details = ?, display_order = ?, color_scheme = ?
                      WHERE id = ?''',
                    (home_team, away_team, competition, location, match_date, match_time,
                     predicted_score, home_win_percent, draw_percent, away_win_percent,
                     over_15_percent, over_25_percent, btts_percent, details,
                     display_order, color_scheme, match_id))
        conn.commit()
        conn.close()
        
        flash('Partida atualizada com sucesso!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    match = conn.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
    conn.close()
    
    if not match:
        flash('Partida não encontrada', 'error')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/edit_match.html', match=dict(match))

@app.route('/admin/delete/<int:match_id>', methods=['POST'])
def delete_match(match_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    conn.execute('DELETE FROM matches WHERE id = ?', (match_id,))
    conn.commit()
    conn.close()
    
    flash('Partida removida com sucesso!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Você foi desconectado com sucesso', 'success')
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
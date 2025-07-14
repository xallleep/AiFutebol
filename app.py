import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-key-123'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configurações
DATABASE = 'matches.db'
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = generate_password_hash(os.environ.get('ADMIN_PASS', 'admin123'))

# Inicialização do banco de dados
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS matches
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
    today = datetime.now().strftime('%Y-%m-%d')
    
    with get_db() as conn:
        matches = conn.execute('''
            SELECT *, 
            CASE WHEN match_date = ? THEN 1 ELSE 0 END AS is_today
            FROM matches 
            ORDER BY is_today DESC, display_order, match_date, match_time
        ''', (today,)).fetchall()
    
    last_updated = datetime.now().strftime('%d/%m/%Y às %H:%M')
    
    return render_template('index.html', 
                         matches=matches,
                         last_updated=last_updated,
                         format_date=format_date)

# Área administrativa
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USER and check_password_hash(ADMIN_PASS, password):
            session['admin_logged_in'] = True
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Credenciais inválidas', 'error')
        return redirect(url_for('admin'))
    
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard'))
    
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    with get_db() as conn:
        matches = conn.execute('SELECT * FROM matches ORDER BY display_order, match_date, match_time').fetchall()
    
    return render_template('admin/dashboard.html', matches=matches, format_date=format_date)

@app.route('/admin/match/<int:match_id>', methods=['GET', 'POST', 'DELETE'])
def manage_match(match_id=None):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    conn = get_db()
    
    if request.method == 'DELETE' or (request.method == 'POST' and 'delete' in request.form):
        conn.execute('DELETE FROM matches WHERE id = ?', (match_id,))
        conn.commit()
        conn.close()
        flash('Partida removida com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = {k: request.form.get(k) or None for k in (
            'home_team', 'away_team', 'competition', 'location', 
            'match_date', 'match_time', 'predicted_score', 'details',
            'home_win_percent', 'draw_percent', 'away_win_percent',
            'over_15_percent', 'over_25_percent', 'btts_percent',
            'display_order', 'color_scheme'
        )}
        
        if match_id:  # Edição
            conn.execute('''UPDATE matches SET
                home_team=?, away_team=?, competition=?, location=?, 
                match_date=?, match_time=?, predicted_score=?,
                home_win_percent=?, draw_percent=?, away_win_percent=?,
                over_15_percent=?, over_25_percent=?, btts_percent=?,
                details=?, display_order=?, color_scheme=?
                WHERE id=?''', (*data.values(), match_id))
            flash('Partida atualizada com sucesso!', 'success')
        else:  # Nova
            conn.execute('''INSERT INTO matches 
                (home_team, away_team, competition, location, match_date, match_time, 
                predicted_score, home_win_percent, draw_percent, away_win_percent,
                over_15_percent, over_25_percent, btts_percent, details, 
                display_order, color_scheme)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                tuple(data.values()))
            flash('Partida adicionada com sucesso!', 'success')
        
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    
    # GET request
    match = None
    if match_id:
        match = conn.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
        conn.close()
        if not match:
            flash('Partida não encontrada', 'error')
            return redirect(url_for('dashboard'))
    
    return render_template('admin/match_form.html', match=match)

@app.route('/admin/logout')
def logout():
    session.pop('admin_logged_in', None)
    flash('Você foi desconectado com sucesso', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
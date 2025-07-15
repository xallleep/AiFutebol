import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
import logging
from functools import wraps
import stripe

# Configuração de logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-key-123'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configurações do banco de dados
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///matches.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = generate_password_hash(os.environ.get('ADMIN_PASS', 'admin123'))

# Configuração do Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Por favor faça login para acessar esta página', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def premium_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_premium'):
            flash('Assine o plano premium para acessar este conteúdo', 'warning')
            return redirect(url_for('premium'))
        return f(*args, **kwargs)
    return decorated_function

# Funções auxiliares
def init_db():
    try:
        if DATABASE_URL.startswith('sqlite'):
            conn = sqlite3.connect(DATABASE_URL.split('///')[1])
        else:
            conn = sqlite3.connect('matches.db')  # Fallback local
            
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
        
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     email TEXT UNIQUE NOT NULL,
                     password TEXT NOT NULL,
                     is_premium BOOLEAN DEFAULT FALSE,
                     stripe_customer_id TEXT,
                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        conn.commit()
        conn.close()
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {str(e)}")

init_db()

def get_db():
    try:
        if DATABASE_URL.startswith('sqlite'):
            conn = sqlite3.connect(DATABASE_URL.split('///')[1])
        else:
            conn = sqlite3.connect('matches.db')  # Fallback local
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        raise

def format_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
    except:
        return date_str

# Rotas principais
@app.route('/')
def index():
    try:
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
    except Exception as e:
        logger.error(f"Erro na rota index: {str(e)}")
        return render_template('index.html', 
                             today_matches=[],
                             other_matches=[],
                             last_updated='Erro ao carregar dados')

# Rotas de autenticação admin
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USER and check_password_hash(ADMIN_PASS, password):
            session['admin_logged_in'] = True
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Usuário ou senha incorretos', 'danger')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Você foi desconectado', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    conn = get_db()
    matches = conn.execute('SELECT * FROM matches ORDER BY display_order').fetchall()
    conn.close()
    return render_template('admin/dashboard.html', matches=matches)

# Rotas CRUD para matches
@app.route('/admin/matches/add', methods=['GET', 'POST'])
@login_required
def add_match():
    if request.method == 'POST':
        try:
            conn = get_db()
            conn.execute('''
                INSERT INTO matches (
                    home_team, away_team, competition, location, 
                    match_date, match_time, predicted_score,
                    home_win_percent, draw_percent, away_win_percent,
                    over_15_percent, over_25_percent, btts_percent,
                    details, display_order, color_scheme
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request.form['home_team'],
                request.form['away_team'],
                request.form.get('competition'),
                request.form.get('location'),
                request.form['match_date'],
                request.form['match_time'],
                request.form.get('predicted_score'),
                request.form.get('home_win_percent', 0),
                request.form.get('draw_percent', 0),
                request.form.get('away_win_percent', 0),
                request.form.get('over_15_percent', 0),
                request.form.get('over_25_percent', 0),
                request.form.get('btts_percent', 0),
                request.form.get('details'),
                request.form.get('display_order', 0),
                request.form.get('color_scheme', 'blue')
            ))
            conn.commit()
            conn.close()
            flash('Jogo adicionado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            logger.error(f"Erro ao adicionar jogo: {str(e)}")
            flash('Erro ao adicionar jogo', 'danger')
    
    return render_template('admin/add_match.html')

@app.route('/admin/matches/<int:match_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_match(match_id):
    conn = get_db()
    match = conn.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
    
    if request.method == 'POST':
        try:
            conn.execute('''
                UPDATE matches SET
                    home_team = ?,
                    away_team = ?,
                    competition = ?,
                    location = ?,
                    match_date = ?,
                    match_time = ?,
                    predicted_score = ?,
                    home_win_percent = ?,
                    draw_percent = ?,
                    away_win_percent = ?,
                    over_15_percent = ?,
                    over_25_percent = ?,
                    btts_percent = ?,
                    details = ?,
                    display_order = ?,
                    color_scheme = ?
                WHERE id = ?
            ''', (
                request.form['home_team'],
                request.form['away_team'],
                request.form.get('competition'),
                request.form.get('location'),
                request.form['match_date'],
                request.form['match_time'],
                request.form.get('predicted_score'),
                request.form.get('home_win_percent', 0),
                request.form.get('draw_percent', 0),
                request.form.get('away_win_percent', 0),
                request.form.get('over_15_percent', 0),
                request.form.get('over_25_percent', 0),
                request.form.get('btts_percent', 0),
                request.form.get('details'),
                request.form.get('display_order', 0),
                request.form.get('color_scheme', 'blue'),
                match_id
            ))
            conn.commit()
            flash('Jogo atualizado com sucesso!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            logger.error(f"Erro ao atualizar jogo: {str(e)}")
            flash('Erro ao atualizar jogo', 'danger')
    
    conn.close()
    return render_template('admin/edit_match.html', match=match)

@app.route('/admin/matches/<int:match_id>/delete', methods=['POST'])
@login_required
def delete_match(match_id):
    try:
        conn = get_db()
        conn.execute('DELETE FROM matches WHERE id = ?', (match_id,))
        conn.commit()
        conn.close()
        flash('Jogo excluído com sucesso!', 'success')
    except Exception as e:
        logger.error(f"Erro ao excluir jogo: {str(e)}")
        flash('Erro ao excluir jogo', 'danger')
    
    return redirect(url_for('admin_dashboard'))

# Rotas de assinatura
@app.route('/premium')
def premium():
    return render_template('premium.html', 
                         stripe_public_key=os.environ.get('STRIPE_PUBLIC_KEY'))

@app.route('/create-subscription', methods=['POST'])
def create_subscription():
    try:
        email = request.form.get('email')
        
        # Verifica se o usuário já existe
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if not user:
            # Cria usuário no banco de dados
            conn.execute('INSERT INTO users (email, password) VALUES (?, ?)',
                        (email, generate_password_hash(os.urandom(16).hex())))
            conn.commit()
        
        # Cria sessão de checkout no Stripe
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': os.environ.get('STRIPE_PRICE_ID'),
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payment_canceled', _external=True),
            customer_email=email
        )
        return redirect(checkout_session.url)
    except Exception as e:
        logger.error(f"Erro no checkout: {str(e)}")
        flash('Erro ao processar pagamento. Tente novamente.', 'error')
        return redirect(url_for('premium'))

@app.route('/payment-success')
def payment_success():
    session_id = request.args.get('session_id')
    
    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        customer_id = stripe_session.customer
        email = stripe_session.customer_details.email
        
        conn = get_db()
        conn.execute('UPDATE users SET is_premium = TRUE, stripe_customer_id = ? WHERE email = ?',
                   (customer_id, email))
        conn.commit()
        conn.close()
        
        session['is_premium'] = True
        session['user_email'] = email
        flash('Assinatura ativada com sucesso!', 'success')
    except Exception as e:
        logger.error(f"Erro ao processar sucesso de pagamento: {str(e)}")
        flash('Pagamento confirmado, mas houve um erro ao ativar sua conta. Contate o suporte.', 'warning')
    
    return redirect(url_for('index'))

@app.route('/payment-canceled')
def payment_canceled():
    flash('Pagamento cancelado', 'warning')
    return redirect(url_for('premium'))

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        logger.error(f"Webhook - Payload inválido: {str(e)}")
        return jsonify({'error': 'Payload inválido'}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Webhook - Assinatura inválida: {str(e)}")
        return jsonify({'error': 'Assinatura inválida'}), 400

    # Tratar eventos relevantes
    if event['type'] == 'invoice.paid':
        customer_id = event['data']['object']['customer']
        try:
            conn = get_db()
            conn.execute('UPDATE users SET is_premium = TRUE WHERE stripe_customer_id = ?',
                       (customer_id,))
            conn.commit()
            conn.close()
            logger.info(f"Assinatura renovada para customer: {customer_id}")
        except Exception as e:
            logger.error(f"Erro ao processar webhook invoice.paid: {str(e)}")

    elif event['type'] == 'customer.subscription.deleted':
        customer_id = event['data']['object']['customer']
        try:
            conn = get_db()
            conn.execute('UPDATE users SET is_premium = FALSE WHERE stripe_customer_id = ?',
                       (customer_id,))
            conn.commit()
            conn.close()
            logger.info(f"Assinatura cancelada para customer: {customer_id}")
        except Exception as e:
            logger.error(f"Erro ao processar webhook subscription.deleted: {str(e)}")

    return jsonify({'success': True}), 200

# Rota de conteúdo premium protegida
@app.route('/conteudo-premium')
@premium_required
def conteudo_premium():
    return render_template('conteudo_premium.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
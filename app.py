import os
from flask import Flask, render_template
from datetime import datetime, timedelta
import requests
import logging
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
from flask_caching import Cache
import pandas as pd
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

# Configuração inicial
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///football_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

cache = Cache(config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 3600
})
cache.init_app(app)

# Configurações
API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
ALTERNATIVE_API_KEY = os.getenv('ALTERNATIVE_FOOTBALL_API_KEY')
matches_data = []
last_updated = None
model = None

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Inicializa o banco de dados"""
    try:
        conn = sqlite3.connect('football_data.db')
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS matches
                     (id INTEGER PRIMARY KEY,
                      home_team TEXT,
                      away_team TEXT,
                      home_score INTEGER,
                      away_score INTEGER,
                      date TEXT,
                      competition TEXT,
                      corners INTEGER,
                      cards INTEGER,
                      possession_home INTEGER,
                      shots_home INTEGER,
                      shots_away INTEGER)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS players
                     (id INTEGER PRIMARY KEY,
                      team TEXT,
                      name TEXT,
                      position TEXT,
                      number INTEGER)''')
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao inicializar DB: {str(e)}")

init_db()

def train_prediction_model():
    """Treina modelo de previsão"""
    try:
        conn = sqlite3.connect('football_data.db')
        df = pd.read_sql('SELECT * FROM matches WHERE home_score IS NOT NULL', conn)
        conn.close()
        
        if len(df) < 30:
            return None
            
        df['goal_diff'] = df['home_score'] - df['away_score']
        df['total_goals'] = df['home_score'] + df['away_score']
        
        X = df[['possession_home', 'shots_home', 'shots_away']].fillna(0).values
        y = (df['goal_diff'] > 0).astype(int)
        
        model = LogisticRegression(max_iter=1000)
        model.fit(X, y)
        
        joblib.dump(model, 'football_model.pkl')
        return model
        
    except Exception as e:
        logger.error(f"Erro treinando modelo: {str(e)}")
        return None

def fetch_from_football_data():
    """Busca dados da API principal"""
    try:
        if not API_KEY:
            return None
            
        headers = {'X-Auth-Token': API_KEY}
        date_from = datetime.now().strftime('%Y-%m-%d')
        date_to = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"https://api.football-data.org/v4/matches?dateFrom={date_from}&dateTo={date_to}",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json().get('matches', [])
        return None
    except Exception as e:
        logger.warning(f"Erro Football-Data: {str(e)}")
        return None

def process_matches(matches):
    """Processa dados das partidas"""
    processed = []
    conn = sqlite3.connect('football_data.db')
    
    for match in matches[:8]:
        try:
            home = match.get('homeTeam', {}).get('shortName') or match.get('homeTeam', {}).get('name')
            away = match.get('awayTeam', {}).get('shortName') or match.get('awayTeam', {}).get('name')
            
            if not home or not away:
                continue
                
            match_time = datetime.strptime(match['utcDate'], '%Y-%m-%dT%H:%M:%SZ')
            
            conn.execute('''INSERT OR IGNORE INTO matches 
                          (home_team, away_team, date, competition)
                          VALUES (?, ?, ?, ?)''',
                          (home, away, match_time.strftime('%Y-%m-%d'), 
                           match.get('competition', {}).get('name', 'Unknown')))
            
            processed.append({
                'competition': match.get('competition', {}).get('name', 'Unknown'),
                'home_team': home,
                'away_team': away,
                'date': match_time.strftime('%d/%m/%Y'),
                'time': match_time.strftime('%H:%M'),
                'prediction': generate_predictions(home, away)
            })
        except Exception as e:
            logger.warning(f"Erro processando jogo: {str(e)}")
            continue
            
    conn.commit()
    conn.close()
    return processed

@cache.cached(timeout=3600, key_prefix='matches_data')
def fetch_matches():
    """Obtém partidas com fallback"""
    matches = fetch_from_football_data()
    
    if not matches and ALTERNATIVE_API_KEY:
        matches = fetch_from_alternative_api()
    
    if matches:
        return process_matches(matches)
    
    return get_fallback_matches()

def update_data():
    """Atualiza dados periodicamente"""
    global matches_data, last_updated, model
    try:
        model = train_prediction_model()
        matches_data = fetch_matches()
        last_updated = datetime.now().strftime("%d/%m/%Y %H:%M")
        logger.info(f"Dados atualizados - {len(matches_data)} jogos")
    except Exception as e:
        logger.error(f"Falha na atualização: {str(e)}")

# Agendador
scheduler = BackgroundScheduler()
scheduler.add_job(update_data, 'interval', hours=3)
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html', matches=matches_data, last_updated=last_updated)

if __name__ == '__main__':
    update_data()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
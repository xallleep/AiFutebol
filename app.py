import os
import sys
import subprocess
from flask import Flask, render_template
from datetime import datetime, timedelta
import requests
import logging
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
from flask_caching import Cache
import pandas as pd
import numpy as np
import random
import joblib
from sklearn.linear_model import LogisticRegression
import warnings

# Verificação e instalação de dependências essenciais
try:
    import setuptools
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "setuptools==68.2.2"])
    import setuptools

# Configuração do Flask
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
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
    """Treina modelo de previsão com fallback robusto"""
    try:
        conn = sqlite3.connect('football_data.db')
        df = pd.read_sql('SELECT * FROM matches WHERE home_score IS NOT NULL', conn)
        conn.close()
        
        if len(df) < 30:
            logger.info("Dados insuficientes para treino - usando modelo base")
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

def get_team_lineup(team_name):
    """Gera escalação realista com fallback"""
    try:
        conn = sqlite3.connect('football_data.db')
        c = conn.cursor()
        c.execute("SELECT name, position, number FROM players WHERE team = ? ORDER BY position", (team_name,))
        players = c.fetchall()
        
        if players:
            lineup = [f"{p[1]} {p[0]} #{p[2]}" for p in players]
            conn.close()
            return lineup[:11]
            
        # Geração realista de escalação
        positions = ['GK', 'RB', 'CB', 'CB', 'LB', 'CDM', 'CM', 'CAM', 'RW', 'ST', 'LW']
        common_surnames = {
            'Brazil': ['Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues'],
            'England': ['Smith', 'Jones', 'Taylor', 'Brown', 'Wilson'],
            'Spain': ['García', 'Rodríguez', 'González', 'Fernández', 'López'],
            'Germany': ['Müller', 'Schmidt', 'Schneider', 'Fischer', 'Weber']
        }
        
        country = 'Brazil'
        if 'United' in team_name or 'City' in team_name:
            country = 'England'
        elif 'Real' in team_name or 'Barca' in team_name:
            country = 'Spain'
        elif 'Bayern' in team_name or 'Dortmund' in team_name:
            country = 'Germany'
            
        lineup = []
        for i, pos in enumerate(positions):
            first_letter = team_name[0] if i < 5 else team_name.split()[0][0]
            surname = random.choice(common_surnames[country])
            name = f"{first_letter}. {surname}"
            lineup.append(f"{pos} {name} #{i+1}")
            
            c.execute("INSERT OR IGNORE INTO players (team, name, position, number) VALUES (?, ?, ?, ?)",
                     (team_name, name, pos, i+1))
        
        conn.commit()
        conn.close()
        return lineup
        
    except Exception as e:
        logger.error(f"Erro obtendo escalação: {str(e)}")
        return ["Jogadores não disponíveis"]

def generate_predictions(home_team, away_team):
    """Gera previsões robustas com fallback"""
    try:
        conn = sqlite3.connect('football_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT AVG(home_score), AVG(away_score), AVG(corners), AVG(cards), 
                    AVG(possession_home), AVG(shots_home), AVG(shots_away)
                    FROM matches WHERE home_team = ?''', (home_team,))
        home_stats = c.fetchone() or (1.4, 1.1, 8.5, 3.2, 50, 12, 10)
        
        c.execute('''SELECT AVG(away_score), AVG(home_score), AVG(corners), AVG(cards), 
                    AVG(100-possession_home), AVG(shots_away), AVG(shots_home)
                    FROM matches WHERE away_team = ?''', (away_team,))
        away_stats = c.fetchone() or (1.0, 1.3, 7.8, 3.0, 45, 9, 12)
        
        conn.close()
        
        # Cálculo das médias ponderadas
        avg_home_goals = (home_stats[0] + away_stats[1]) / 2
        avg_away_goals = (home_stats[1] + away_stats[0]) / 2
        avg_corners = (home_stats[2] + away_stats[2]) / 2
        avg_cards = (home_stats[3] + away_stats[3]) / 2
        avg_possession_home = (home_stats[4] + (100 - away_stats[4])) / 2
        
        # Previsão com modelo ou fallback estatístico
        if model:
            try:
                input_features = np.array([[avg_possession_home, (home_stats[5] + away_stats[6])/2, (home_stats[6] + away_stats[5])/2]])
                home_win_prob = model.predict_proba(input_features)[0][1]
                home_goals = round(avg_home_goals * (0.8 + home_win_prob * 0.4))
                away_goals = round(avg_away_goals * (0.8 + (1 - home_win_prob) * 0.4))
            except:
                home_goals = round(avg_home_goals * random.uniform(0.8, 1.2))
                away_goals = round(avg_away_goals * random.uniform(0.8, 1.2))
        else:
            home_goals = round(avg_home_goals * random.uniform(0.8, 1.2))
            away_goals = round(avg_away_goals * random.uniform(0.8, 1.2))
        
        return {
            'score': f"{max(0, min(5, home_goals))}-{max(0, min(4, away_goals))}",
            'corners': int(avg_corners * random.uniform(0.9, 1.1)),
            'cards': int(avg_cards * random.uniform(0.9, 1.1)),
            'possession': f"{int(avg_possession_home)}%-{int(100 - avg_possession_home)}%",
            'shots_on_target': f"{int((home_stats[5] + away_stats[6])/2 * 0.4)}-{int((home_stats[6] + away_stats[5])/2 * 0.4)}",
            'fouls': f"{int(avg_cards * 3)}-{int(avg_cards * 2.8)}"
        }
    except Exception as e:
        logger.error(f"Erro gerando previsões: {str(e)}")
        return {
            'score': "1-1",
            'corners': 8,
            'cards': 3,
            'possession': "50%-50%",
            'shots_on_target': "5-4",
            'fouls': "12-10"
        }

def fetch_from_football_data():
    """Busca dados da API principal com tratamento robusto"""
    try:
        if not API_KEY:
            logger.warning("API_KEY não configurada")
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
        
        logger.warning(f"API retornou status {response.status_code}")
        return None
        
    except Exception as e:
        logger.error(f"Erro na requisição: {str(e)}")
        return None

def process_matches(matches):
    """Processa dados das partidas com tratamento de erros"""
    processed = []
    if not matches:
        return processed
        
    conn = sqlite3.connect('football_data.db')
    
    for match in matches[:8]:  # Limita a 8 jogos
        try:
            home = match.get('homeTeam', {}).get('shortName') or match.get('homeTeam', {}).get('name')
            away = match.get('awayTeam', {}).get('shortName') or match.get('awayTeam', {}).get('name')
            
            if not home or not away:
                continue
                
            match_time = datetime.strptime(match['utcDate'], '%Y-%m-%dT%H:%M:%SZ')
            
            # Armazena no banco de dados
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
                'lineup_home': get_team_lineup(home),
                'lineup_away': get_team_lineup(away),
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
    """Obtém partidas com fallback hierárquico"""
    try:
        matches = fetch_from_football_data()
        
        if matches:
            return process_matches(matches)
            
        return get_fallback_matches()
        
    except Exception as e:
        logger.error(f"Erro ao buscar partidas: {str(e)}")
        return get_fallback_matches()

def get_fallback_matches():
    """Gera dados mockados como último recurso"""
    competitions = [
        ("Campeonato Brasileiro Série A", "BR1"),
        ("Premier League", "PL"),
        ("La Liga", "ES1"),
        ("Bundesliga", "BL1")
    ]
    
    teams = [
        ("Flamengo", "FLA"),
        ("Palmeiras", "PAL"),
        ("Grêmio", "GRE"),
        ("Fluminense", "FLU"),
        ("Corinthians", "COR"),
        ("São Paulo", "SAO"),
        ("Atlético-MG", "CAM"),
        ("Internacional", "INT")
    ]
    
    matches = []
    base_time = datetime.now().replace(hour=19, minute=0)
    
    for i in range(4):  # 4 jogos mockados
        home, home_code = teams[i]
        away, away_code = teams[i+4]
        comp, comp_code = competitions[i % len(competitions)]
        
        match_time = base_time + timedelta(days=i//2, hours=(i%2)*3)
        
        matches.append({
            'competition': comp,
            'home_team': home,
            'away_team': away,
            'date': match_time.strftime('%d/%m/%Y'),
            'time': match_time.strftime('%H:%M'),
            'lineup_home': get_team_lineup(home),
            'lineup_away': get_team_lineup(away),
            'prediction': generate_predictions(home, away)
        })
    
    return matches

def update_data():
    """Atualiza dados periodicamente com tratamento de erros"""
    global matches_data, last_updated, model
    try:
        model = train_prediction_model()
        matches_data = fetch_matches()
        last_updated = datetime.now().strftime("%d/%m/%Y %H:%M")
        logger.info(f"Dados atualizados - {len(matches_data)} jogos encontrados")
    except Exception as e:
        logger.error(f"Falha na atualização: {str(e)}")
        matches_data = get_fallback_matches()
        last_updated = datetime.now().strftime("%d/%m/%Y %H:%M (fallback)")

# Configuração do agendador
scheduler = BackgroundScheduler()
scheduler.add_job(update_data, 'interval', hours=3)
scheduler.start()

# Rotas
@app.route('/')
def index():
    return render_template('index.html', matches=matches_data, last_updated=last_updated)

@app.route('/status')
def status():
    return {
        'status': 'active',
        'last_updated': last_updated,
        'matches_count': len(matches_data),
        'model_loaded': model is not None,
        'source': 'API' if not any('Mock' in m['competition'] for m in matches_data) else 'Mock'
    }

# Inicialização
if __name__ == '__main__':
    update_data()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
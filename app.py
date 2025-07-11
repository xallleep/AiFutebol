from flask import Flask, render_template
from datetime import datetime, timedelta
import os
import requests
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import random

load_dotenv()

app = Flask(__name__)

# Configurações
API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
TIMEZONE = 'America/Sao_Paulo'
MATCHES_PER_DAY = 5  # 5 jogos por dia

# Variáveis globais
matches_data = []
last_updated = None

def get_priority(competition_name):
    """Define prioridade das competições"""
    priority_map = {
        'Premier League': 10,
        'Champions League': 10,
        'Brasileirão': 9,
        'Copa do Brasil': 8,
        'Libertadores': 9,
        'Europa League': 7,
        'La Liga': 8,
        'Bundesliga': 8,
        'Serie A': 7,
        'Ligue 1': 7
    }
    for key, value in priority_map.items():
        if key in competition_name:
            return value
    return 5  # Prioridade padrão

def fetch_matches():
    """Busca jogos da API"""
    headers = {'X-Auth-Token': API_KEY}
    try:
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz)
        tomorrow = today + timedelta(days=1)
        
        # Formata datas para API
        date_from = today.strftime('%Y-%m-%d')
        date_to = tomorrow.strftime('%Y-%m-%d')
        
        response = requests.get(
            f"https://api.football-data.org/v4/matches?dateFrom={date_from}&dateTo={date_to}",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json().get('matches', [])
    
    except Exception as e:
        print(f"Erro na API: {str(e)}")
        return []

def select_top_matches(matches):
    """Seleciona os melhores jogos"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    # Classifica jogos por prioridade
    for match in matches:
        match['priority'] = get_priority(match['competition']['name'])
    
    # Separa jogos de hoje e amanhã
    today_matches = []
    tomorrow_matches = []
    
    for match in matches:
        match_date = datetime.strptime(match['utcDate'], '%Y-%m-%dT%H:%M:%SZ').astimezone(tz)
        if match_date.date() == now.date():
            today_matches.append(match)
        else:
            tomorrow_matches.append(match)
    
    # Ordena por prioridade e seleciona os melhores
    today_matches.sort(key=lambda x: (-x['priority'], x['utcDate']))
    tomorrow_matches.sort(key=lambda x: (-x['priority'], x['utcDate']))
    
    return today_matches[:MATCHES_PER_DAY], tomorrow_matches[:MATCHES_PER_DAY]

def process_match(match):
    """Processa dados de um jogo"""
    tz = pytz.timezone(TIMEZONE)
    match_date = datetime.strptime(match['utcDate'], '%Y-%m-%dT%H:%M:%SZ').astimezone(tz)
    
    return {
        'home_team': match['homeTeam']['name'],
        'away_team': match['awayTeam']['name'],
        'date': match_date.strftime("%d/%m/%Y"),
        'time': match_date.strftime("%H:%M"),
        'competition': match['competition']['name'],
        'is_today': match_date.date() == datetime.now(tz).date(),
        'lineup_home': generate_lineup(match['homeTeam']['name']),
        'lineup_away': generate_lineup(match['awayTeam']['name']),
        **generate_predictions(match['homeTeam']['name'], match['awayTeam']['name'])
    }

def generate_lineup(team_name):
    """Gera escalação simulada"""
    positions = ['GK', 'DF', 'DF', 'DF', 'DF', 'MF', 'MF', 'MF', 'FW', 'FW', 'FW']
    return [f"{pos} {team_name.split()[0][:3].upper()}{i+1}" for i, pos in enumerate(positions)]

def generate_predictions(home, away):
    """Gera previsões realistas"""
    # Fatores baseados nos nomes (para consistência)
    home_factor = sum(ord(c) for c in home) % 100 / 100
    away_factor = sum(ord(c) for c in away) % 100 / 100
    
    # Cálculo das estatísticas
    diff = home_factor - away_factor
    
    return {
        'predicted_score': f"{int(1 + home_factor * 3)}-{int(1 + away_factor * 2)}",
        'predicted_corners': int(5 + (home_factor + away_factor) * 5),
        'predicted_cards': int(2 + abs(diff) * 4),
        'stats': {
            'posse_bola': f"{int(50 + diff * 30)}%-{int(50 - diff * 30)}%",
            'chutes': f"{int(8 + home_factor * 8)}-{int(7 + away_factor * 7)}",
            'chutes_gol': f"{int(3 + home_factor * 4)}-{int(2 + away_factor * 3)}",
            'faltas': f"{int(10 + home_factor * 5)}-{int(9 + away_factor * 5)}"
        }
    }

def update_matches():
    """Atualiza os dados dos jogos"""
    global matches_data, last_updated
    
    print("Atualizando dados dos jogos...")
    try:
        matches = fetch_matches()
        if not matches:
            print("Nenhum jogo encontrado")
            return
        
        today, tomorrow = select_top_matches(matches)
        processed = [process_match(m) for m in today + tomorrow]
        
        matches_data = processed
        last_updated = datetime.now(pytz.timezone(TIMEZONE)).strftime("%d/%m/%Y %H:%M")
        print(f"Dados atualizados: {len(today)} hoje, {len(tomorrow)} amanhã")
        
    except Exception as e:
        print(f"Erro na atualização: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html',
                         matches=matches_data,
                         last_updated=last_updated)

# Agendador
scheduler = BackgroundScheduler()
scheduler.add_job(update_matches, 'interval', hours=6)
scheduler.start()

if __name__ == '__main__':
    update_matches()  # Atualiza ao iniciar
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
from flask import Flask, render_template
from datetime import datetime, timedelta
import os
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()  # Carrega variáveis de ambiente do arquivo .env

app = Flask(__name__)

# Variáveis globais
matches_data = []
last_updated = None
API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')

def get_today_matches():
    """Obtém os jogos de hoje e amanhã usando a API Football-Data"""
    headers = {'X-Auth-Token': API_KEY}
    base_url = "https://api.football-data.org/v4/matches"
    
    try:
        # Obter jogos para hoje e amanhã
        date_from = datetime.now().strftime('%Y-%m-%d')
        date_to = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{base_url}?dateFrom={date_from}&dateTo={date_to}",
            headers=headers
        )
        response.raise_for_status()
        
        matches = response.json().get('matches', [])
        
        # Processar os jogos
        processed_matches = []
        for match in matches[:10]:  # Limitar a 10 jogos (5 de hoje e 5 de amanhã)
            processed_match = process_match_data(match)
            processed_matches.append(processed_match)
        
        # Ordenar por data e selecionar os melhores jogos
        processed_matches.sort(key=lambda x: x['timestamp'])
        today_matches = [m for m in processed_matches if m['is_today']][:5]
        tomorrow_matches = [m for m in processed_matches if not m['is_today']][:5]
        
        return today_matches + tomorrow_matches
    
    except Exception as e:
        print(f"Erro na API: {e}")
        return []

def process_match_data(match):
    """Processa os dados brutos de um jogo"""
    match_date = datetime.strptime(match['utcDate'], '%Y-%m-%dT%H:%M:%SZ')
    is_today = match_date.date() == datetime.now().date()
    
    home_team = match['homeTeam']['name']
    away_team = match['awayTeam']['name']
    
    # Gerar previsões
    predictions = generate_predictions(home_team, away_team)
    
    return {
        'home_team': home_team,
        'away_team': away_team,
        'date': match_date.strftime("%d/%m/%Y"),
        'time': match_date.strftime("%H:%M"),
        'timestamp': match_date.timestamp(),
        'is_today': is_today,
        'competition': match['competition']['name'],
        'lineup_home': generate_lineup(home_team),
        'lineup_away': generate_lineup(away_team),
        **predictions
    }

def generate_lineup(team_name):
    """Gera uma escalação simulada baseada no nome do time"""
    positions = ['GK', 'DF', 'DF', 'DF', 'DF', 'MF', 'MF', 'MF', 'FW', 'FW', 'FW']
    return [f"{pos} {team_name.split()[0]} {i+1}" for i, pos in enumerate(positions)]

def generate_predictions(home_team, away_team):
    """Gera previsões baseadas em estatísticas simuladas mas realistas"""
    # Fatores baseados nos nomes dos times para consistência
    home_factor = sum(ord(c) for c in home_team) % 10 / 10
    away_factor = sum(ord(c) for c in away_team) % 10 / 10
    
    # Estatísticas base
    base_stats = {
        'possession': 50 + (home_factor - away_factor) * 10,
        'home_shots': int(12 + home_factor * 6),
        'away_shots': int(10 + away_factor * 5),
        'home_corners': int(5 + home_factor * 3),
        'away_corners': int(4 + away_factor * 2),
        'fouls': random.randint(10, 20),
        'cards': random.randint(2, 5)
    }
    
    # Ajustes para tornar mais realista
    if base_stats['possession'] > 65:
        base_stats['home_shots'] += 2
        base_stats['away_shots'] = max(5, base_stats['away_shots'] - 2)
    elif base_stats['possession'] < 35:
        base_stats['away_shots'] += 2
        base_stats['home_shots'] = max(5, base_stats['home_shots'] - 2)
    
    # Previsão de gols
    home_goals = min(
        int(base_stats['home_shots'] * (0.1 + home_factor * 0.05)),
        random.randint(0, 4)
    )
    away_goals = min(
        int(base_stats['away_shots'] * (0.1 + away_factor * 0.05)),
        random.randint(0, 3)
    )
    
    return {
        'predicted_score': f"{home_goals}-{away_goals}",
        'predicted_corners': base_stats['home_corners'] + base_stats['away_corners'],
        'predicted_cards': base_stats['cards'],
        'stats': {
            'posse_bola': f"{base_stats['possession']:.0f}%-{100 - base_stats['possession']:.0f}%",
            'chutes': f"{base_stats['home_shots']}-{base_stats['away_shots']}",
            'chutes_gol': f"{int(base_stats['home_shots'] * 0.4)}-{int(base_stats['away_shots'] * 0.3)}",
            'faltas': f"{base_stats['fouls']}-{int(base_stats['fouls'] * 0.9)}"
        }
    }

def update_data():
    """Atualiza os dados dos jogos"""
    global matches_data, last_updated
    print("Atualizando dados...")
    try:
        matches_data = get_today_matches()
        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"Dados atualizados com sucesso! {len(matches_data)} jogos encontrados.")
    except Exception as e:
        print(f"Erro ao atualizar dados: {e}")

@app.route('/')
def index():
    return render_template('index.html', matches=matches_data, last_updated=last_updated)

def scheduled_task():
    """Tarefa agendada para atualizar dados"""
    with app.app_context():
        update_data()

if __name__ == '__main__':
    # Atualiza os dados imediatamente ao iniciar
    update_data()
    
    # Configura o agendador para atualizar a cada 6 horas
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_task, trigger="interval", hours=6)
    scheduler.start()
    
    # Configuração para o Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
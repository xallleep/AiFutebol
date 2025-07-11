from flask import Flask, render_template
from datetime import datetime, timedelta
import os
import requests
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
import random
import numpy as np
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configurações
TIMEZONE = 'America/Sao_Paulo'
MATCHES_PER_DAY = 5
SCRAPE_URL = "https://www.flashscore.com.br/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Variáveis globais
matches_data = []
last_updated = None

class MatchPredictor:
    def __init__(self):
        self.team_stats = {}
        self.load_historical_data()
    
    def load_historical_data(self):
        """Carrega dados históricos simulados"""
        # Na prática, você coletaria dados reais
        self.team_stats = {
            'Flamengo': {'attack': 85, 'defense': 80, 'home_boost': 1.1},
            'Palmeiras': {'attack': 82, 'defense': 83, 'home_boost': 1.05},
            # Adicione mais times conforme necessário
        }
    
    def predict_match(self, home_team, away_team):
        """Gera previsões inteligentes baseadas em estatísticas"""
        # Obter estatísticas dos times (com fallback para valores padrão)
        home = self.team_stats.get(home_team, {'attack': 75, 'defense': 70, 'home_boost': 1.0})
        away = self.team_stats.get(away_team, {'attack': 70, 'defense': 75, 'home_boost': 1.0})
        
        # Cálculo das probabilidades
        home_attack = home['attack'] * home['home_boost']
        away_attack = away['attack']
        home_defense = home['defense'] * home['home_boost']
        away_defense = away['defense']
        
        # Prever gols (distribuição de Poisson)
        home_goals = max(0, int(np.random.poisson(home_attack / away_defense * 0.3)))
        away_goals = max(0, int(np.random.poisson(away_attack / home_defense * 0.25)))
        
        # Evitar placares absurdos
        home_goals = min(home_goals, 5)
        away_goals = min(away_goals, 4)
        
        # Gerar outras estatísticas
        stats = {
            'possession': self.calculate_possession(home_attack, away_attack),
            'shots': self.calculate_shots(home_attack, away_attack),
            'corners': self.calculate_corners(home_goals, away_goals),
            'cards': self.calculate_cards(home_team, away_team)
        }
        
        return {
            'score': f"{home_goals}-{away_goals}",
            'stats': stats
        }
    
    def calculate_possession(self, home, away):
        """Calcula posse de bola baseada na força dos times"""
        total = home + away
        home_pos = int((home / total) * 45 + 50)
        return f"{home_pos}%-{100-home_pos}%"
    
    def calculate_shots(self, home, away):
        """Calcula chutes baseados no ataque"""
        home_shots = int(home / 10 + 8)
        away_shots = int(away / 10 + 6)
        return f"{home_shots}-{away_shots}"
    
    def calculate_corners(self, home_goals, away_goals):
        """Calcula escanteios baseados no placar"""
        return random.randint(3 + home_goals, 7 + home_goals) + random.randint(2 + away_goals, 5 + away_goals)
    
    def calculate_cards(self, home, away):
        """Calcula cartões baseado no histórico dos times"""
        return random.randint(2, 5)

predictor = MatchPredictor()

def scrape_matches():
    """Raspa os jogos do FlashScore"""
    try:
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(SCRAPE_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        matches = []
        today = datetime.now(pytz.timezone(TIMEZONE))
        
        # Encontrar seções de jogos (hoje e amanhã)
        for day in [0, 1]:
            date = today + timedelta(days=day)
            section = soup.find('div', {'title': date.strftime('%A, %d.%m.%Y')})
            
            if section:
                for match in section.find_all('div', class_='event__match')[:MATCHES_PER_DAY]:
                    home = match.find('div', class_='event__participant--home').text.strip()
                    away = match.find('div', class_='event__participant--away').text.strip()
                    competition = match.find_previous('div', class_='event__title--type').text.strip()
                    
                    time = match.find('div', class_='event__time').text.strip()
                    match_time = datetime.strptime(f"{date.strftime('%Y-%m-%d')} {time}", '%Y-%m-%d %H:%M')
                    
                    matches.append({
                        'home': home,
                        'away': away,
                        'competition': competition,
                        'date': date.strftime('%d/%m/%Y'),
                        'time': time,
                        'timestamp': match_time.timestamp(),
                        'is_today': day == 0
                    })
        
        return matches
    
    except Exception as e:
        print(f"Erro no scraping: {str(e)}")
        return []

def select_best_matches(matches):
    """Seleciona os melhores jogos baseado na competição"""
    priority = {
        'Champions League': 10,
        'Premier League': 9,
        'Brasileirão': 9,
        'Libertadores': 8,
        'Copa do Brasil': 7,
        'La Liga': 7,
        'Serie A': 6
    }
    
    # Classificar por prioridade
    for match in matches:
        match['priority'] = next((v for k, v in priority.items() if k in match['competition']), 5)
    
    # Separar hoje/amanhã e ordenar
    today = sorted([m for m in matches if m['is_today']], key=lambda x: -x['priority'])[:MATCHES_PER_DAY]
    tomorrow = sorted([m for m in matches if not m['is_today']], key=lambda x: -x['priority'])[:MATCHES_PER_DAY]
    
    return today + tomorrow

def enrich_matches(matches):
    """Adiciona previsões e escalações"""
    enriched = []
    for match in matches:
        prediction = predictor.predict_match(match['home'], match['away'])
        
        enriched.append({
            'home_team': match['home'],
            'away_team': match['away'],
            'date': match['date'],
            'time': match['time'],
            'competition': match['competition'],
            'is_today': match['is_today'],
            'predicted_score': prediction['score'],
            'predicted_corners': prediction['stats']['corners'],
            'predicted_cards': random.randint(2, 5),
            'stats': {
                'posse_bola': prediction['stats']['possession'],
                'chutes': prediction['stats']['shots'],
                'chutes_gol': self.generate_shots_on_target(prediction['stats']['shots']),
                'faltas': f"{random.randint(10, 15)}-{random.randint(9, 14)}"
            },
            'lineup_home': self.generate_lineup(match['home']),
            'lineup_away': self.generate_lineup(match['away'])
        })
    return enriched

def generate_lineup(team_name):
    """Gera escalação simulada"""
    positions = ['GK', 'DF', 'DF', 'DF', 'DF', 'MF', 'MF', 'MF', 'FW', 'FW', 'FW']
    return [f"{pos} {team_name.split()[0][:3].upper()}{i+1}" for i, pos in enumerate(positions)]

def generate_shots_on_target(self, shots):
    """Gera chutes no gol baseado nos chutes totais"""
    home, away = map(int, shots.split('-'))
    return f"{int(home*0.4)}-{int(away*0.3)}"

def update_data():
    """Atualiza os dados dos jogos"""
    global matches_data, last_updated
    
    print("🔄 Atualizando dados...")
    try:
        matches = scrape_matches()
        if not matches:
            print("⚠️ Nenhum jogo encontrado via scraping")
            return
        
        selected = select_best_matches(matches)
        enriched = enrich_matches(selected)
        
        matches_data = enriched
        last_updated = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d/%m/%Y %H:%M')
        print(f"✅ Dados atualizados: {len([m for m in matches_data if m['is_today']])} hoje, {len([m for m in matches_data if not m['is_today']])} amanhã")
    
    except Exception as e:
        print(f"❌ Erro na atualização: {str(e)}")

@app.route('/')
def index():
    today = [m for m in matches_data if m['is_today']]
    tomorrow = [m for m in matches_data if not m['is_today']]
    
    return render_template('index.html',
                         today_matches=today,
                         tomorrow_matches=tomorrow,
                         last_updated=last_updated)

# Agendador
scheduler = BackgroundScheduler()
scheduler.add_job(update_data, 'interval', hours=3)
scheduler.start()

if __name__ == '__main__':
    update_data()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
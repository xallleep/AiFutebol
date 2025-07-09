import random
from datetime import datetime

def generate_predictions(match):
    """Gera previsões baseadas em estatísticas simuladas"""
    home_team = match['home_team']
    away_team = match['away_team']
    
    # Fatores aleatórios baseados nos nomes dos times (para consistência)
    home_factor = sum(ord(c) for c in home_team) % 10
    away_factor = sum(ord(c) for c in away_team) % 10
    
    # Previsão de placar
    home_goals = max(0, random.randint(0, 3) + home_factor - away_factor)
    away_goals = max(0, random.randint(0, 2) + away_factor - home_factor)
    
    # Estatísticas simuladas
    home_possession = 45 + home_factor * 2
    away_possession = 100 - home_possession
    
    home_shots = random.randint(8, 18) + home_factor
    away_shots = random.randint(6, 16) + away_factor
    
    home_shots_on_target = max(1, home_shots // 3 + home_factor - 2)
    away_shots_on_target = max(1, away_shots // 3 + away_factor - 2)
    
    # Previsão de escanteios
    corners = random.randint(4, 12) + (home_factor + away_factor) // 2
    
    # Previsão de cartões
    cards = random.randint(2, 6) + (home_factor + away_factor) // 4
    
    return {
        'predicted_score': f"{home_goals}-{away_goals}",
        'predicted_corners': corners,
        'predicted_cards': cards,
        'stats': {
            'posse_bola': f"{home_possession}%-{away_possession}%",
            'chutes': f"{home_shots}-{away_shots}",
            'chutes_gol': f"{home_shots_on_target}-{away_shots_on_target}",
            'faltas': f"{random.randint(10, 20)}-{random.randint(10, 20)}"
        }
    }
import requests
from datetime import datetime, timedelta
import random

def get_today_matches(apy_key):
    """Obtém os jogos de hoje usando a API Football-Data"""
    headers = {'X-Auth-Token': api_key}
    url = "https://api.football-data.org/v4/matches"
    
    try:
        # Obter jogos para o período de hoje
        date_from = datetime.now().strftime('%Y-%m-%d')
        date_to = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{url}?dateFrom={date_from}&dateTo={date_to}",
            headers=headers
        )
        response.raise_for_status()
        
        matches_data = response.json().get('matches', [])
        
        # Formatar os dados
        formatted_matches = []
        for match in matches_data[:5]:  # Limitar a 5 jogos para a versão free
            home_team = match['homeTeam']['name']
            away_team = match['awayTeam']['name']
            
            # Mock de escalação (API não fornece isso gratuitamente)
            lineup_home = get_team_lineup(home_team)
            lineup_away = get_team_lineup(away_team)
            
            # Converter data
            match_date = datetime.strptime(match['utcDate'], '%Y-%m-%dT%H:%M:%SZ')
            
            formatted_matches.append({
                'home_team': home_team,
                'away_team': away_team,
                'date': match_date.strftime("%d/%m/%Y"),
                'time': match_date.strftime("%H:%M"),
                'competition': match['competition']['name'],
                'lineup_home': lineup_home,
                'lineup_away': lineup_away
            })
        
        return formatted_matches
    
    except Exception as e:
        print(f"Erro na API: {e}")
        # Fallback com dados mockados
        return get_mocked_matches()

def get_team_lineup(team_name):
    """Mock de escalação - na prática você precisaria de uma fonte paga"""
    positions = ['GK', 'DF', 'DF', 'DF', 'DF', 'MF', 'MF', 'MF', 'FW', 'FW', 'FW']
    players = []
    
    for i, pos in enumerate(positions):
        players.append(f"{pos} {team_name.split()[0]} Player {i+1}")
    
    return players

def get_mocked_matches():
    """Retorna dados mockados quando a API falha"""
    teams = [
        "Manchester United", "Liverpool", "Chelsea", "Arsenal", 
        "Barcelona", "Real Madrid", "Bayern Munich", "PSG"
    ]
    
    matches = []
    for i in range(3):
        home = teams[i]
        away = teams[i+3]
        
        matches.append({
            'home_team': home,
            'away_team': away,
            'date': datetime.now().strftime("%d/%m/%Y"),
            'time': f"{18+i}:00",
            'competition': "Mock League",
            'lineup_home': get_team_lineup(home),
            'lineup_away': get_team_lineup(away)
        })
    
    return matches
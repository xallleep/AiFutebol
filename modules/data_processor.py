import requests
from datetime import datetime, timedelta
import random
import pytz
from bs4 import BeautifulSoup
import numpy as np
import sqlite3
import json
import time
from urllib.parse import urljoin

class DataProcessor:
    def __init__(self, timezone, matches_per_day, cache_db):
        self.timezone = timezone
        self.matches_per_day = matches_per_day
        self.cache_db = cache_db
        self.api_url = "https://api.football-data.org/v4/matches"
        self.scrape_url = "https://www.flashscore.com/"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        self.headers = {'User-Agent': self.user_agent}
    
    def get_matches(self, source='scrape'):
        """Obtém jogos da fonte especificada"""
        try:
            if source == 'api':
                return self._get_api_matches()
            elif source == 'scrape':
                return self._get_scraped_matches()
            else:
                return self._get_mocked_matches()
        except Exception as e:
            print(f"Error in get_matches: {str(e)}")
            return self._get_cached_matches()
    
    def _get_api_matches(self):
        """Obtém jogos da API Football-Data"""
        headers = {'X-Auth-Token': os.getenv('FOOTBALL_DATA_API_KEY')}
        date_from = datetime.now(pytz.timezone(self.timezone)).strftime('%Y-%m-%d')
        date_to = (datetime.now(pytz.timezone(self.timezone)) + timedelta(days=1)).strftime('%Y-%m-%d')
        
        response = requests.get(
            f"{self.api_url}?dateFrom={date_from}&dateTo={date_to}",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        matches = response.json().get('matches', [])
        return self._process_matches(matches[:self.matches_per_day])
    
    def _get_scraped_matches(self):
        """Raspa jogos do FlashScore com mais informações"""
        try:
            # Primeiro obtemos a página principal para pegar os IDs dos jogos
            response = requests.get(self.scrape_url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            matches = []
            today = datetime.now(pytz.timezone(self.timezone))
            
            # Encontra todas as seções de jogos
            sections = soup.find_all('div', class_='leagues--live')
            
            for section in sections[:5]:  # Limita a 5 ligas para não sobrecarregar
                league_name = section.find('a', class_='event__title--name').text.strip()
                
                for match_div in section.find_all('div', class_='event__match')[:self.matches_per_day]:
                    match_id = match_div.get('id').split('_')[-1]
                    match_url = f"https://www.flashscore.com/match/{match_id}/#/match-summary"
                    
                    # Agora acessamos a página de detalhes do jogo
                    match_details = self._get_match_details(match_url)
                    
                    if match_details:
                        matches.append({
                            'home': match_details['home_team'],
                            'away': match_details['away_team'],
                            'competition': league_name,
                            'date': today.strftime('%d/%m/%Y'),
                            'time': match_details['time'],
                            'timestamp': datetime.now().timestamp(),
                            'is_today': True,
                            'home_stats': match_details.get('home_stats', {}),
                            'away_stats': match_details.get('away_stats', {})
                        })
            
            return self._process_matches(matches)
        
        except Exception as e:
            print(f"Scraping Error: {str(e)}")
            return self._get_cached_matches()
    
    def _get_match_details(self, match_url):
        """Obtém detalhes específicos de um jogo"""
        try:
            response = requests.get(match_url, headers=self.headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            home_team = soup.find('div', class_='team-home').find('span').text.strip()
            away_team = soup.find('div', class_='team-away').find('span').text.strip()
            match_time = soup.find('div', class_='match-info-time').text.strip()
            
            # Tenta obter estatísticas
            stats = {}
            try:
                stats_section = soup.find('div', class_='stats-section')
                if stats_section:
                    home_stats = {
                        'possession': stats_section.find('div', class_='stat-home').text.strip(),
                        'shots': stats_section.find_all('div', class_='stat-home')[1].text.strip(),
                        'shots_on_target': stats_section.find_all('div', class_='stat-home')[2].text.strip(),
                        'corners': stats_section.find_all('div', class_='stat-home')[3].text.strip()
                    }
                    away_stats = {
                        'possession': stats_section.find('div', class_='stat-away').text.strip(),
                        'shots': stats_section.find_all('div', class_='stat-away')[1].text.strip(),
                        'shots_on_target': stats_section.find_all('div', class_='stat-away')[2].text.strip(),
                        'corners': stats_section.find_all('div', class_='stat-away')[3].text.strip()
                    }
                    stats = {'home_stats': home_stats, 'away_stats': away_stats}
            except:
                pass
            
            return {
                'home_team': home_team,
                'away_team': away_team,
                'time': match_time,
                **stats
            }
        
        except Exception as e:
            print(f"Error getting match details: {str(e)}")
            return None
    
    def _get_cached_matches(self):
        """Obtém partidas do cache"""
        conn = sqlite3.connect(self.cache_db)
        c = conn.cursor()
        c.execute("SELECT data FROM matches ORDER BY timestamp DESC LIMIT ?", (self.matches_per_day,))
        matches = [json.loads(row[0]) for row in c.fetchall()]
        conn.close()
        return matches
    
    def _cache_matches(self, matches):
        """Armazena partidas no cache"""
        conn = sqlite3.connect(self.cache_db)
        c = conn.cursor()
        
        for match in matches:
            match_id = f"{match['home_team']}_{match['away_team']}_{match['date']}"
            c.execute("INSERT OR REPLACE INTO matches VALUES (?, ?, ?)",
                     (match_id, json.dumps(match), datetime.now().timestamp()))
        
        conn.commit()
        conn.close()
    
    def _get_mocked_matches(self):
        """Gera dados simulados"""
        teams = [
            "Flamengo", "Palmeiras", "Corinthians", "São Paulo",
            "Grêmio", "Internacional", "Atlético Mineiro", "Fluminense"
        ]
        
        matches = []
        today = datetime.now(pytz.timezone(self.timezone))
        
        for i in range(self.matches_per_day):
            home = teams[i]
            away = teams[(i + 4) % len(teams)]
            match_time = today.replace(hour=19 + i % 3, minute=0, second=0, microsecond=0)
            
            matches.append({
                'home': home,
                'away': away,
                'competition': "Brasileirão Série A",
                'date': match_time.strftime('%d/%m/%Y'),
                'time': match_time.strftime('%H:%M'),
                'timestamp': match_time.timestamp(),
                'is_today': True
            })
        
        return self._process_matches(matches)
    
    def _process_matches(self, raw_matches):
        """Processa e enriquece os dados dos jogos"""
        processed = []
        for match in raw_matches:
            prediction = self._predict_match(match.get('home'), match.get('away'), 
                                          match.get('home_stats', {}), 
                                          match.get('away_stats', {}))
            
            processed_match = {
                'home_team': match.get('home', 'Time Casa'),
                'away_team': match.get('away', 'Time Visitante'),
                'date': match.get('date', datetime.now().strftime('%d/%m/%Y')),
                'time': match.get('time', '20:00'),
                'competition': match.get('competition', 'Campeonato Desconhecido'),
                'is_today': match.get('is_today', True),
                'predicted_score': prediction['score'],
                'predicted_corners': prediction['corners'],
                'predicted_cards': prediction['cards'],
                'stats': {
                    'posse_bola': prediction['possession'],
                    'chutes': prediction['shots'],
                    'chutes_gol': prediction['shots_on_target'],
                    'faltas': prediction['fouls']
                },
                'lineup_home': self._generate_lineup(match.get('home', 'Time Casa')),
                'lineup_away': self._generate_lineup(match.get('away', 'Time Visitante'))
            }
            
            processed.append(processed_match)
        
        self._cache_matches(processed)
        return processed
    
    def _predict_match(self, home_team, away_team, home_stats={}, away_stats={}):
        """Gera previsões para um jogo baseado em estatísticas reais quando disponíveis"""
        # Se temos estatísticas reais, usamos elas
        if home_stats and away_stats:
            try:
                home_possession = int(home_stats.get('possession', '50%').strip('%'))
                home_shots = int(home_stats.get('shots', '10'))
                home_shots_on_target = int(home_stats.get('shots_on_target', '4'))
                home_corners = int(home_stats.get('corners', '5'))
                
                away_shots = int(away_stats.get('shots', '8'))
                away_shots_on_target = int(away_stats.get('shots_on_target', '3'))
                
                # Calcula previsão baseada em estatísticas reais
                home_goals = min(5, round(home_shots_on_target * 0.3 + random.uniform(-0.5, 0.5)))
                away_goals = min(4, round(away_shots_on_target * 0.25 + random.uniform(-0.5, 0.5)))
                
                return {
                    'score': f"{home_goals}-{away_goals}",
                    'corners': f"{home_corners} | {home_corners + random.randint(-2, 2)}",
                    'cards': f"{random.randint(2, 4)} | {random.randint(1, 3)}",
                    'possession': f"{home_possession}%-{100-home_possession}%",
                    'shots': f"{home_shots}-{away_shots}",
                    'shots_on_target': f"{home_shots_on_target}-{away_shots_on_target}",
                    'fouls': f"{random.randint(10, 15)}-{random.randint(9, 14)}"
                }
            except:
                pass
        
        # Fallback para previsão estatística quando não há dados reais
        home_attack = random.randint(70, 85)
        away_attack = random.randint(65, 80)
        home_defense = random.randint(65, 80)
        away_defense = random.randint(70, 85)
        
        home_goals = max(0, int(np.random.poisson(home_attack / away_defense * 0.3)))
        away_goals = max(0, int(np.random.poisson(away_attack / home_defense * 0.25)))
        
        home_goals = min(home_goals, 5)
        away_goals = min(away_goals, 4)
        
        home_possession = int((home_attack / (home_attack + away_attack)) * 45 + 50)
        home_shots = int(home_attack / 10 + 8)
        away_shots = int(away_attack / 10 + 6)
        
        return {
            'score': f"{home_goals}-{away_goals}",
            'corners': f"{random.randint(4, 8)} | {random.randint(3, 7)}",
            'cards': f"{random.randint(2, 4)} | {random.randint(1, 3)}",
            'possession': f"{home_possession}%-{100-home_possession}%",
            'shots': f"{home_shots}-{away_shots}",
            'shots_on_target': f"{int(home_shots*0.4)}-{int(away_shots*0.3)}",
            'fouls': f"{random.randint(10, 15)}-{random.randint(9, 14)}"
        }
    
    def _generate_lineup(self, team_name):
        """Gera uma escalação simulada com nomes mais realistas"""
        positions = ['GK', 'DF', 'DF', 'DF', 'DF', 'MF', 'MF', 'MF', 'FW', 'FW', 'FW']
        surnames = ['Silva', 'Santos', 'Oliveira', 'Souza', 'Rodrigues', 
                   'Ferreira', 'Alves', 'Pereira', 'Lima', 'Costa']
        
        return [f"{pos} {team_name.split()[0][:3].upper()}{random.choice(surnames)}" 
                for i, pos in enumerate(positions)]
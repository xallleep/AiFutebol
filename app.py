import os
from flask import Flask, render_template
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from modules.data_processor import DataProcessor
import sqlite3

load_dotenv()

app = Flask(__name__)

# Configurações
TIMEZONE = 'America/Sao_Paulo'
MATCHES_PER_DAY = 5
DATA_SOURCE = os.getenv('DATA_SOURCE', 'scrape')
CACHE_DB = 'matches_cache.db'

# Inicializa o banco de dados
def init_db():
    conn = sqlite3.connect(CACHE_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS matches
                 (id TEXT PRIMARY KEY, data TEXT, timestamp REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS team_stats
                 (team TEXT PRIMARY KEY, stats TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Variáveis globais
matches_data = []
last_updated = None
data_processor = DataProcessor(TIMEZONE, MATCHES_PER_DAY, CACHE_DB)

@app.route('/')
def index():
    today = [m for m in matches_data if m['is_today']]
    tomorrow = [m for m in matches_data if not m['is_today']]
    
    return render_template('index.html',
                         today_matches=today,
                         tomorrow_matches=tomorrow,
                         last_updated=last_updated)

def update_data():
    global matches_data, last_updated
    
    print("🔄 Atualizando dados...")
    try:
        matches = data_processor.get_matches(DATA_SOURCE)
        
        if not matches:
            print("⚠️ Usando dados simulados como fallback")
            matches = data_processor.get_matches('mock')
        
        matches_data = matches
        last_updated = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d/%m/%Y %H:%M')
        print("✅ Dados atualizados com sucesso")
    
    except Exception as e:
        print(f"❌ Erro na atualização: {str(e)}")

# Agendador
scheduler = BackgroundScheduler()
scheduler.add_job(update_data, 'interval', hours=1)
scheduler.start()

# Atualiza os dados na inicialização
update_data()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
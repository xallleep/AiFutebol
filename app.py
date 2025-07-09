from flask import Flask, render_template
from datetime import datetime
import scraper
from football_api import get_today_matches  # Importe a função da API
import os
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# Variável global para armazenar os dados
matches_data = []
last_updated = None

def update_data():
    global matches_data, last_updated
    print("Atualizando dados...")
    try:
        # Use a função da API com sua chave (MELHOR MÉTODO):
        matches_data = get_today_matches(os.environ.get('b02bfc4db4a34dca9e278b65b2244e6b'))
        
        # Ou use diretamente (apenas para testes locais):
        # matches_data = get_today_matches("b02bfc4db4a34dca9e278b65b2244e6b")
        
        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("Dados atualizados com sucesso!")
    except Exception as e:
        print(f"Erro ao atualizar dados: {e}")

@app.route('/')
def index():
    return render_template('index.html', matches=matches_data, last_updated=last_updated)

def scheduled_task():
    with app.app_context():
        update_data()

if __name__ == '__main__':
    # Atualiza os dados imediatamente ao iniciar
    update_data()
    
    # Configura o agendador para rodar diariamente
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_task, trigger="cron", hour=8, minute=0)
    scheduler.start()
    
    # Obtém a porta do ambiente ou usa 5000 como padrão
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
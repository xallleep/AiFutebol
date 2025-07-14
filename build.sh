#!/bin/bash
# Configuração definitiva para resolver problemas de build no Render

# 1. Configura ambiente limpo
echo "🛠️ Configurando ambiente..."
rm -rf .venv
python -m venv .venv
source .venv/bin/activate

# 2. Instala versões específicas e comprovadas
echo "⬇️ Instalando dependências de build..."
python -m pip install --upgrade \
    "pip==23.0.1" \
    "setuptools==65.5.1" \
    "wheel==0.38.4" --no-cache-dir

# 3. Instala dependências principais
echo "📦 Instalando requisitos do projeto..."
pip install --no-cache-dir -r requirements.txt

# 4. Verifica instalação
echo "✅ Verificando instalações..."
python -c "import setuptools; print(f'setuptools {setuptools.__version__} instalado')"
#!/bin/bash
# SOLUÇÃO DEFINITIVA PARA ERROS DE BUILD NO RENDER

# 1. Configuração inicial
echo "🔧 Preparando ambiente..."
rm -rf .venv  # Remove qualquer ambiente virtual existente

# 2. Cria novo ambiente virtual
echo "🛠️ Criando novo ambiente virtual..."
python -m venv .venv
source .venv/bin/activate

# 3. Instala versões específicas e comprovadas
echo "📦 Instalando dependências de build..."
python -m pip install --upgrade \
    "pip==23.0.1" \
    "setuptools==65.5.1" \
    "wheel==0.38.4" --no-cache-dir

# 4. Instala dependências principais
echo "🚀 Instalando requisitos do projeto..."
pip install --no-cache-dir -r requirements.txt

# 5. Verificação final
echo "✅ Verificando instalações..."
python -c "import sys; print(f'Python {sys.version}')"
python -c "import setuptools; print(f'setuptools {setuptools.__version__} instalado')"
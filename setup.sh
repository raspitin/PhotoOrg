#!/usr/bin/env bash
set -euo pipefail

if [ ! -d venv ]; then
echo "ℹ️ Ambiente virtuale non trovato, esegui prima bootstrap.sh"
exit 1
fi

echo "🐍 Attivo ambiente virtuale…"
source venv/bin/activate

echo "📦 Installazione/aggiornamento dipendenze Python da requirements.txt…"
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Setup completato. Puoi ora eseguire 'python3 main.py'"

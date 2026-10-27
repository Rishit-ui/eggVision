#!/bin/bash
set -e

echo "Setting up EggVision AI..."

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

echo "Setting up backend..."
cd backend || mkdir backend && cd backend
python -m venv venv
source venv/bin/activate || source venv/Scripts/activate
pip install -r requirements.txt || echo "No requirements.txt found yet."
cd ..

echo "Setting up frontend..."
cd frontend || mkdir frontend && cd frontend
npm install || echo "No package.json found yet."
cd ..

echo "Setup complete."

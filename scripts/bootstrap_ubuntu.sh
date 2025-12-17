#!/bin/bash
set -e

# 1. System Dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip redis-server nginx git

# 2. Python Environment
echo "Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo "Installing Python requirements..."
pip install -r requirements.txt

# 3. Download Models (Warmup)
echo "Downloading ML models..."
# Create a simple python script to trigger downloads
python3 -c "
from sentence_transformers import SentenceTransformer
import open_clip

print('Downloading Sentence Transformer...')
SentenceTransformer('all-MiniLM-L6-v2')

print('Downloading OpenCLIP...')
open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')

print('Models downloaded successfully!')
"

# 4. Django Setup
echo "Running migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

# 5. Create Superuser (Optional)
# python manage.py createsuperuser --noinput --username admin --email admin@example.com || true

echo "Setup complete! Run 'python manage.py runserver' to test dev mode."

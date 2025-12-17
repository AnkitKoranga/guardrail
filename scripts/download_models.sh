#!/bin/bash
source venv/bin/activate
python3 -c "
from sentence_transformers import SentenceTransformer
import open_clip

print('Downloading Sentence Transformer...')
SentenceTransformer('all-MiniLM-L6-v2')

print('Downloading OpenCLIP...')
open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')

print('Models downloaded successfully!')
"


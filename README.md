# Food Guard AI

A strict, CPU-optimized Django application that filters non-food requests before calling Gemini 2.5 Flash Image ("Nano Banana").

## Features

- **Two Separate Use Cases**:
  - **Use Case 1: Image Analysis** - Analyzes uploaded images to verify they are food-related
  - **Use Case 2: Prompt Analysis** - Validates user prompts for food context and restrictions
- **Strict Guardrails**: Blocks NSFW, violence, hate speech, and non-food content locally.
- **Fast Keyword Matching**: Instant approval for prompts containing food items (pizza, burger, etc.)
- **Zero Token Waste**: Only passes safe, food-related requests to Gemini.
- **CPU Optimized**: Uses small, efficient models (`all-MiniLM-L6-v2`, `ViT-B-32`, `NudeNet`).
- **Async Processing**: Uses Celery + Redis to handle heavy ML tasks off the main web thread.

## Setup

### Prerequisites
- Python 3.10+
- Redis Server
- Gemini API Key

### Installation

1. **Clone & Setup Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your GEMINI_API_KEY
   ```

3. **Download Models**
   ```bash
   bash scripts/download_models.sh
   ```

4. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

### Running Locally

1. **Start Redis**
   ```bash
   redis-server
   ```

2. **Start Celery Worker**
   ```bash
   celery -A foodguard worker --loglevel=info --concurrency=1
   ```

3. **Start Django Server**
   ```bash
   python manage.py runserver
   ```

4. **Access UI**
   Open http://localhost:8000/

## Deployment (Single VPS)

See `deploy/` directory for example configurations.

1. Run `scripts/bootstrap_ubuntu.sh` to install dependencies.
2. Copy `deploy/gunicorn.service` and `deploy/celery.service` to `/etc/systemd/system/`.
3. Copy `deploy/nginx.conf` to `/etc/nginx/sites-available/foodguard`.
4. Enable services and restart Nginx.

## Tuning

Adjust thresholds in `apps/guardrails/text_food_domain.py` and `apps/guardrails/image_food_clip.py` if the filter is too strict or too lenient.

- `GUARDRAILS_MAX_PROMPT_CHARS`: Max text length (default 800).
- `GUARDRAILS_MAX_IMAGE_BYTES`: Max image size (default 5MB).

# Celery Auto-Retraining Setup Guide

## Overview

The Convopilot system uses **Celery** for background task processing, including automatic chatbot retraining. This guide explains how to set up and run the Celery workers and beat scheduler.

---

## Prerequisites

1. **Redis** - Used as message broker and result backend
2. **Python dependencies** - Already in `requirements.txt`:
   - `celery==5.3.0`
   - `redis==5.0.0`

---

## Installation

### 1. Install Redis

#### Windows
```bash
# Option 1: Using Chocolatey
choco install redis-64

# Option 2: Using WSL (Windows Subsystem for Linux)
wsl --install
# Then inside WSL:
sudo apt-get update
sudo apt-get install redis-server
```

#### macOS
```bash
brew install redis
brew services start redis
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

### 2. Configure Redis URL

Add to your `.env` file:
```bash
# Redis Configuration (for Celery)
REDIS_URL=redis://localhost:6379/0
```

---

## Running Celery

You need to run **TWO** separate processes:

### 1. Celery Worker (Processes tasks)

#### Windows (CMD)
```bash
cd backend
celery -A app.celery_app:make_celery worker --loglevel=info --pool=solo -Q retraining,notifications,analytics
```

#### Windows (PowerShell)
```powershell
cd backend
$env:FORKED_BY_MULTIPROCESSING="1"
celery -A app.celery_app:make_celery worker --loglevel=info --pool=solo -Q retraining,notifications,analytics
```

#### macOS/Linux
```bash
cd backend
celery -A app.celery_app:make_celery worker --loglevel=info -Q retraining,notifications,analytics
```

### 2. Celery Beat (Schedules periodic tasks)

Open a **new terminal** and run:

#### All Platforms
```bash
cd backend
celery -A app.celery_app:make_celery beat --loglevel=info
```

---

## Task Queues

The system uses **three queues** for organizing tasks:

| Queue | Purpose | Tasks |
|-------|---------|-------|
| `retraining` | Chatbot knowledge base updates | Auto-retraining, embedding updates, feedback analysis |
| `notifications` | User notifications | Email reports, cleanup, retry failed notifications |
| `analytics` | Usage monitoring | Usage alerts, statistics aggregation |

---

## Auto-Retraining Tasks

### Scheduled Tasks (via Celery Beat)

| Task | Schedule | Description |
|------|----------|-------------|
| **Auto-Retrain Chatbots** | Daily (24 hours) | Retrains chatbots that haven't been updated in 7+ days |
| **Feedback-Based Retraining** | Twice daily (12 hours) | Identifies chatbots with low satisfaction (<3 stars) and triggers retraining |
| **Cleanup Old Embeddings** | Weekly (7 days) | Removes orphaned vector embeddings for deleted data sources |

### On-Demand Tasks

These can be triggered manually via API:

```python
from app.tasks.retraining_tasks import (
    process_data_source,
    update_vector_embeddings
)

# Process a new data source
process_data_source.delay(data_source_id=123)

# Update embeddings for a chatbot
update_vector_embeddings.delay(chatbot_id=456)
```

---

## Monitoring

### Check Task Status

```bash
# View active tasks
celery -A app.celery_app:make_celery inspect active

# View scheduled tasks
celery -A app.celery_app:make_celery inspect scheduled

# View registered tasks
celery -A app.celery_app:make_celery inspect registered

# View worker stats
celery -A app.celery_app:make_celery inspect stats
```

### Check Redis Connection

```bash
# Connect to Redis CLI
redis-cli

# Check connection
127.0.0.1:6379> PING
PONG

# View queued tasks
127.0.0.1:6379> LLEN celery

# Exit
127.0.0.1:6379> EXIT
```

---

## Production Deployment

### Using Supervisor (Linux)

Create `/etc/supervisor/conf.d/convopilot-celery.conf`:

```ini
[program:convopilot-celery-worker]
command=/path/to/venv/bin/celery -A app.celery_app:make_celery worker --loglevel=info -Q retraining,notifications,analytics
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/convopilot/celery-worker.err.log
stdout_logfile=/var/log/convopilot/celery-worker.out.log

[program:convopilot-celery-beat]
command=/path/to/venv/bin/celery -A app.celery_app:make_celery beat --loglevel=info
directory=/path/to/backend
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/convopilot/celery-beat.err.log
stdout_logfile=/var/log/convopilot/celery-beat.out.log
```

Then:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start convopilot-celery-worker
sudo supervisorctl start convopilot-celery-beat
```

### Using systemd (Linux)

Create `/etc/systemd/system/convopilot-celery-worker.service`:

```ini
[Unit]
Description=Convopilot Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A app.celery_app:make_celery worker --loglevel=info -Q retraining,notifications,analytics --detach
Restart=always

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/convopilot-celery-beat.service`:

```ini
[Unit]
Description=Convopilot Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/backend
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A app.celery_app:make_celery beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable convopilot-celery-worker
sudo systemctl enable convopilot-celery-beat
sudo systemctl start convopilot-celery-worker
sudo systemctl start convopilot-celery-beat
```

---

## Troubleshooting

### Redis Connection Error

```
Error: Cannot connect to redis://localhost:6379/0
```

**Solution:**
1. Check if Redis is running: `redis-cli ping`
2. Verify `REDIS_URL` in `.env`
3. Start Redis service

### Worker Not Processing Tasks

```
WARNING/MainProcess] Received unregistered task
```

**Solution:**
1. Restart the worker
2. Check task names match exactly
3. Verify task is imported in `celery_app.py`

### Beat Schedule Not Working

**Solution:**
1. Delete `celerybeat-schedule.db` file
2. Restart Celery Beat
3. Check Beat logs for errors

### Windows-Specific Issues

If you get `billiard` or multiprocessing errors on Windows:
- Always use `--pool=solo` flag
- Set `FORKED_BY_MULTIPROCESSING=1` environment variable

---

## Configuration

Auto-retraining behavior can be customized in `backend/app/celery_app.py`:

```python
beat_schedule={
    'auto-retrain-chatbots': {
        'task': 'app.tasks.retraining_tasks.auto_retrain_chatbots',
        'schedule': 86400.0,  # Change frequency (in seconds)
    },
    # ... other tasks
}
```

---

## Health Check

Create a simple health check script:

```python
# check_celery.py
from app import create_app
from app.celery_app import make_celery

app = create_app()
celery = make_celery(app)

# Check if workers are active
inspect = celery.control.inspect()
active_workers = inspect.active()

if active_workers:
    print(f"✅ {len(active_workers)} Celery worker(s) active")
else:
    print("❌ No active Celery workers found")
```

Run with:
```bash
python check_celery.py
```

---

## Summary

**To start the complete system:**

1. **Start Redis:**
   ```bash
   # macOS/Linux
   redis-server
   
   # Windows (WSL)
   sudo service redis-server start
   ```

2. **Start Flask app:**
   ```bash
   cd backend
   python run.py
   ```

3. **Start Celery Worker (new terminal):**
   ```bash
   cd backend
   celery -A app.celery_app:make_celery worker --loglevel=info --pool=solo -Q retraining,notifications,analytics
   ```

4. **Start Celery Beat (new terminal):**
   ```bash
   cd backend
   celery -A app.celery_app:make_celery beat --loglevel=info
   ```

5. **Start Frontend (new terminal):**
   ```bash
   cd frontend
   npm start
   ```

Now the auto-retraining system is fully operational! 🎉


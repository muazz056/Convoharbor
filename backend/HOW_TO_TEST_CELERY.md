# How to Test Auto-Retraining System (Celery)

## 🎯 Quick Testing Guide

### Option 1: Test WITHOUT Redis (Mock Mode)
**Recommended for quick testing without installing Redis**

The tasks will run synchronously (immediately) instead of in the background:

```bash
cd backend
python
```

Then in Python:
```python
from app import create_app
from app.tasks.retraining_tasks import auto_retrain_chatbots, feedback_based_retraining

# Create app context
app = create_app()
ctx = app.app_context()
ctx.push()

# Test auto-retrain task (runs immediately)
result = auto_retrain_chatbots()
print(f"✅ Auto-retrained {result} chatbots")

# Test feedback-based retraining
result = feedback_based_retraining()
print(f"✅ Queued {result} chatbots for retraining based on feedback")
```

### Option 2: Test WITH Redis (Full Background Mode)
**Production-like testing with actual background processing**

#### Step 1: Install Redis

**Windows:**
```bash
# Option A: Using Memurai (Redis-compatible for Windows)
# Download from: https://www.memurai.com/get-memurai
# OR use Docker:
docker run -d -p 6379:6379 redis:latest

# Option B: Using WSL
wsl --install
# Then in WSL:
sudo apt-get update && sudo apt-get install redis-server
sudo service redis-server start
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Linux:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

#### Step 2: Verify Redis is Running

```bash
# Test Redis connection
redis-cli ping
# Should return: PONG
```

#### Step 3: Add Redis URL to .env

```bash
# Add to backend/.env
REDIS_URL=redis://localhost:6379/0
```

#### Step 4: Run Verification Script

```bash
cd backend
python check_celery_setup.py
```

Expected output:
```
✅ PASS - Redis Connection
✅ PASS - Celery Tasks
✅ PASS - Beat Schedule
✅ PASS - Task Routing
```

#### Step 5: Start Celery Worker

**Terminal 1 - Start Worker:**
```bash
cd backend
celery -A app.celery_app:make_celery worker --loglevel=info --pool=solo -Q retraining,notifications,analytics
```

#### Step 6: Start Celery Beat (for scheduled tasks)

**Terminal 2 - Start Beat:**
```bash
cd backend
celery -A app.celery_app:make_celery beat --loglevel=info
```

#### Step 7: Test Task Execution

**Terminal 3 - Trigger Tasks Manually:**
```bash
cd backend
python
```

```python
from app import create_app
from app.celery_app import make_celery
from app.tasks.retraining_tasks import auto_retrain_chatbots, feedback_based_retraining

# Create app and celery
app = create_app()
celery = make_celery(app)

# Trigger tasks (they run in background via worker)
with app.app_context():
    # Queue auto-retrain task
    task = auto_retrain_chatbots.delay()
    print(f"✅ Task queued: {task.id}")
    
    # Check task status
    result = task.get(timeout=60)  # Wait up to 60 seconds
    print(f"✅ Task completed: retrained {result} chatbots")
```

---

## 🧪 Testing Individual Tasks

### Test 1: Auto-Retrain Chatbots
Tests daily automatic retraining of chatbots that haven't been updated in 7+ days.

```python
from app import create_app
from app.tasks.retraining_tasks import auto_retrain_chatbots

app = create_app()
with app.app_context():
    result = auto_retrain_chatbots()
    print(f"Retrained {result} chatbots")
```

**What it checks:**
- Finds chatbots with `status='active'` and `updated_at < 7 days ago`
- Sets status to 'training'
- Processes any pending data sources
- Returns to 'active' status

### Test 2: Feedback-Based Retraining
Tests automatic retraining based on low satisfaction scores.

```python
from app import create_app
from app.tasks.retraining_tasks import feedback_based_retraining

app = create_app()
with app.app_context():
    result = feedback_based_retraining()
    print(f"Queued {result} chatbots for retraining")
```

**What it checks:**
- Analyzes feedback from last 7 days
- Finds chatbots with avg rating < 3.0 stars
- Requires at least 5 feedback entries
- Queues for embedding updates

### Test 3: Process Data Source
Tests background processing of a single data source.

```python
from app import create_app
from app.tasks.retraining_tasks import process_data_source

app = create_app()
with app.app_context():
    # Replace 123 with actual data source ID
    result = process_data_source(data_source_id=123)
    print(f"Processing result: {result}")
```

### Test 4: Update Vector Embeddings
Tests re-embedding of a chatbot's knowledge base.

```python
from app import create_app
from app.tasks.retraining_tasks import update_vector_embeddings

app = create_app()
with app.app_context():
    # Replace 456 with actual chatbot ID
    result = update_vector_embeddings(chatbot_id=456)
    print(f"Embedding update result: {result}")
```

### Test 5: Cleanup Old Embeddings
Tests cleanup of orphaned embeddings.

```python
from app import create_app
from app.tasks.retraining_tasks import cleanup_old_embeddings

app = create_app()
with app.app_context():
    result = cleanup_old_embeddings()
    print(f"Cleaned up {result} embeddings")
```

---

## 📊 Monitoring Tests

### Monitor Task Execution (with Redis)

```bash
# View active tasks
celery -A app.celery_app:make_celery inspect active

# View scheduled tasks
celery -A app.celery_app:make_celery inspect scheduled

# View worker statistics
celery -A app.celery_app:make_celery inspect stats

# View registered tasks
celery -A app.celery_app:make_celery inspect registered
```

### Monitor Redis Queues

```bash
redis-cli
127.0.0.1:6379> LLEN celery            # Check celery queue length
127.0.0.1:6379> LLEN retraining        # Check retraining queue
127.0.0.1:6379> KEYS *                 # List all keys
127.0.0.1:6379> MONITOR                # Watch all Redis commands (Ctrl+C to stop)
```

---

## 🔍 Verify Tasks Are Working

### Create Test Scenario

```python
from app import create_app
from app.models import Chatbot, ConversationFeedback, Conversation
from datetime import datetime, timedelta
from app import db

app = create_app()
with app.app_context():
    # Scenario 1: Create old chatbot (for auto-retrain test)
    old_chatbot = Chatbot.query.first()
    if old_chatbot:
        old_chatbot.updated_at = datetime.utcnow() - timedelta(days=8)
        db.session.commit()
        print(f"✅ Made chatbot {old_chatbot.id} 'old' for testing")
    
    # Scenario 2: Add low-rating feedback (for feedback-based test)
    conversation = Conversation.query.first()
    if conversation:
        feedback = ConversationFeedback(
            conversation_id=conversation.id,
            chatbot_id=conversation.chatbot_id,
            rating=2,  # Low rating
            comment="Not helpful",
            user_id=conversation.user_id
        )
        db.session.add(feedback)
        db.session.commit()
        print(f"✅ Added low-rating feedback for testing")
```

Then run the tasks:

```python
from app.tasks.retraining_tasks import auto_retrain_chatbots, feedback_based_retraining

# Test auto-retrain (should find the old chatbot)
result1 = auto_retrain_chatbots()
print(f"Auto-retrain result: {result1} chatbots")

# Test feedback-based (should find chatbot with low ratings)
result2 = feedback_based_retraining()
print(f"Feedback-based result: {result2} chatbots")
```

---

## ✅ Success Indicators

### Task Registration
```bash
python check_celery_setup.py
```
Should show:
```
✅ app.tasks.retraining_tasks.auto_retrain_chatbots
✅ app.tasks.retraining_tasks.process_data_source
✅ app.tasks.retraining_tasks.update_vector_embeddings
✅ app.tasks.retraining_tasks.feedback_based_retraining
✅ app.tasks.retraining_tasks.cleanup_old_embeddings
```

### Worker Running
In worker terminal, you should see:
```
[tasks]
  . app.tasks.retraining_tasks.auto_retrain_chatbots
  . app.tasks.retraining_tasks.process_data_source
  . app.tasks.retraining_tasks.update_vector_embeddings
  . app.tasks.retraining_tasks.feedback_based_retraining
  . app.tasks.retraining_tasks.cleanup_old_embeddings
```

### Beat Running
In beat terminal, you should see:
```
Scheduler: Sending due task auto-retrain-chatbots
Scheduler: Sending due task feedback-based-retraining
Scheduler: Sending due task cleanup-old-embeddings
```

### Database Changes
After running tasks, check database:
```python
from app import create_app
from app.models import Chatbot
from datetime import datetime

app = create_app()
with app.app_context():
    # Check if chatbot was updated
    chatbot = Chatbot.query.first()
    print(f"Last updated: {chatbot.updated_at}")
    print(f"Status: {chatbot.status}")
```

---

## 🐛 Troubleshooting

### Issue: Tasks not found
```
❌ app.tasks.retraining_tasks.auto_retrain_chatbots - NOT FOUND
```

**Solution:** Tasks aren't being imported. Check:
1. `app/tasks/__init__.py` imports all task modules
2. `app/celery_app.py` includes `'app.tasks.retraining_tasks'`
3. Restart worker after code changes

### Issue: Redis connection failed
```
❌ Redis connection failed: Error 11001
```

**Solution:**
1. Install Redis (see Step 1 above)
2. Start Redis service
3. Add `REDIS_URL` to `.env`
4. Test with `redis-cli ping`

### Issue: Worker not processing tasks
**Solution:**
1. Make sure worker is running
2. Check worker logs for errors
3. Verify queue names match: `-Q retraining,notifications,analytics`
4. Restart worker if code changed

### Issue: Windows multiprocessing errors
**Solution:** Use `--pool=solo` flag:
```bash
celery -A app.celery_app:make_celery worker --pool=solo --loglevel=info
```

---

## 📝 Summary

**Without Redis (Quick Test):**
```bash
cd backend
python
>>> from app import create_app
>>> from app.tasks.retraining_tasks import auto_retrain_chatbots
>>> app = create_app()
>>> with app.app_context():
...     result = auto_retrain_chatbots()
...     print(f"Result: {result}")
```

**With Redis (Production Test):**
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Worker
cd backend
celery -A app.celery_app:make_celery worker --loglevel=info --pool=solo -Q retraining

# Terminal 3: Start Beat
cd backend
celery -A app.celery_app:make_celery beat --loglevel=info

# Terminal 4: Trigger test
cd backend
python
>>> from app import create_app
>>> from app.celery_app import make_celery
>>> from app.tasks.retraining_tasks import auto_retrain_chatbots
>>> app = create_app()
>>> celery = make_celery(app)
>>> with app.app_context():
...     task = auto_retrain_chatbots.delay()
...     result = task.get(timeout=60)
...     print(f"Result: {result}")
```

**Verify Setup:**
```bash
cd backend
python check_celery_setup.py
```

That's it! 🎉


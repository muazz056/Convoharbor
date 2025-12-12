# 🚀 Security Features - Quick Start Guide

## ✅ What Was Implemented

### 1. **KMS Encryption (Field-Level)**
- Encrypt sensitive data before storing in database
- API keys, passwords, tokens automatically encrypted
- Support for cloud KMS (AWS, Azure, GCP)

### 2. **JIT (Just-In-Time) Access System**
- Temporary privilege elevation with approval workflow
- Auto-expiring permissions
- Comprehensive audit logging

---

## 🏃 Quick Setup (5 Minutes)

### Step 1: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**New:** `cryptography==42.0.5`

### Step 2: Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output (looks like: `gAAAAABf...`)

### Step 3: Add to .env

```bash
# Add these lines to backend/.env
ENCRYPTION_MASTER_KEY=paste-your-generated-key-here
ENCRYPTION_SALT=convopilot-prod-salt-2025
```

### Step 4: Run Database Migration

```bash
# Create migration
flask db migrate -m "Add security features (JIT access and encryption)"

# Apply migration
flask db upgrade
```

### Step 5: Start Celery (Optional - for JIT expiration)

```bash
# Terminal 1: Worker
celery -A app.celery_app:make_celery worker --pool=solo -Q retraining

# Terminal 2: Beat
celery -A app.celery_app:make_celery beat
```

---

## 📖 Usage Examples

### Encrypt Data

```python
from app.models import EncryptedCredential
from app import db

# Store encrypted API key
cred = EncryptedCredential(
    user_id=1,
    credential_type='api_key',
    service_name='openai',
    label='Production Key'
)
cred.set_value('sk-proj-secret-key-here')
db.session.add(cred)
db.session.commit()

# Retrieve decrypted value
api_key = cred.get_value()  # Returns: 'sk-proj-secret-key-here'
```

### Request Temporary Access

**API Call:**
```bash
curl -X POST http://localhost:5000/api/jit-access/request \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requested_level": "admin",
    "resource_type": "tenant",
    "justification": "Need to fix critical bug",
    "duration_minutes": 60
  }'
```

**Response:**
```json
{
  "message": "Access request created successfully",
  "request": {
    "id": 1,
    "status": "pending",
    "requested_level": "admin"
  }
}
```

### Approve Access (Super Admin)

```bash
curl -X POST http://localhost:5000/api/jit-access/requests/1/approve \
  -H "Authorization: Bearer SUPER_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"approval_reason": "Approved for bug fix"}'
```

---

## 🔍 How to Verify It Works

### Test Encryption

```python
from app import create_app
from app.services.encryption_service import encrypt_field, decrypt_field

app = create_app()
with app.app_context():
    encrypted = encrypt_field("test-secret")
    decrypted = decrypt_field(encrypted)
    assert decrypted == "test-secret"
    print("✅ Encryption works!")
```

### Test JIT Access

```python
from app import create_app
from app.services.jit_access_service import JITAccessService

app = create_app()
with app.app_context():
    # Request access
    request = JITAccessService.request_access(
        requester_id=1,
        requested_level='read',
        resource_type='system',
        justification='Testing',
        duration_minutes=30
    )
    print(f"✅ Request created: {request.id}")
    
    # Approve it
    approved = JITAccessService.approve_request(
        request_id=request.id,
        approver_id=2
    )
    print(f"✅ Access approved: {approved.is_active()}")
```

---

## 🎯 API Endpoints Summary

### JIT Access Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/jit-access/request` | POST | User | Request access |
| `/api/jit-access/requests` | GET | User | List requests |
| `/api/jit-access/requests/<id>/approve` | POST | Super Admin | Approve |
| `/api/jit-access/requests/<id>/reject` | POST | Super Admin | Reject |
| `/api/jit-access/active` | GET | User | Active accesses |
| `/api/jit-access/audit-logs` | GET | Super Admin | Audit logs |

---

## 📁 Files Created

```
backend/
├── app/
│   ├── services/
│   │   ├── encryption_service.py          ✅ KMS encryption
│   │   └── jit_access_service.py          ✅ JIT access logic
│   ├── models/
│   │   ├── jit_access.py                  ✅ 3 new tables
│   │   └── encrypted_credentials.py       ✅ 2 new tables
│   ├── api/
│   │   └── jit_access.py                  ✅ 8 API endpoints
│   └── tasks/
│       └── retraining_tasks.py            ✅ Added expiration task
├── requirements.txt                        ✅ Added cryptography
├── SECURITY_FEATURES.md                    ✅ Full documentation
├── SECURITY_QUICK_START.md                 ✅ This file
└── SECURITY_ENV_TEMPLATE.txt               ✅ Env template
```

---

## ⚠️ Important Notes

1. **NEVER commit** `ENCRYPTION_MASTER_KEY` to git
2. **Different keys** for dev/staging/prod
3. **Back up data** before key rotation
4. **Celery required** for JIT auto-expiration
5. **Migrations required** before use

---

## 🆘 Troubleshooting

**Problem:** "Encryption service not initialized"  
**Solution:** Set `ENCRYPTION_MASTER_KEY` in `.env`

**Problem:** "JIT access not expiring"  
**Solution:** Start Celery Beat scheduler

**Problem:** "Migration fails"  
**Solution:** Check database connection and run `flask db stamp head` first

---

## 📚 Full Documentation

See `SECURITY_FEATURES.md` for:
- Detailed architecture
- Security best practices
- Cloud KMS integration
- Compliance information
- Monitoring & alerts

---

## ✅ Checklist

- [ ] Install `cryptography` dependency
- [ ] Generate encryption key
- [ ] Add to `.env`
- [ ] Run database migration
- [ ] Test encryption
- [ ] Test JIT access request/approval
- [ ] Start Celery (optional)
- [ ] Review audit logs

---

**All existing functionality preserved! ✅**  
**No breaking changes! ✅**  
**Production ready! ✅**


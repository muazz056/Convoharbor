# 🔒 Security Features Implementation Guide

## Overview

This document describes the implementation of **JIT (Just-In-Time) Access System** and **KMS (Key Management System) Encryption** for field-level data protection.

---

## 🔐 Part 1: KMS Encryption (Field-Level)

### What is KMS Encryption?

**KMS (Key Management System)** encryption provides **field-level encryption** for sensitive data stored in the database. Instead of storing plaintext sensitive information (API keys, passwords, tokens), we encrypt them before storage and decrypt only when needed.

### Features Implemented

✅ **Fernet Symmetric Encryption** - Fast, secure encryption for field-level data  
✅ **Key Derivation (PBKDF2)** - Derives encryption keys from master key  
✅ **Encrypted Credentials Model** - Store any sensitive credentials  
✅ **Encrypted API Keys Model** - Specific model for chatbot API keys  
✅ **Key Rotation Support** - Can rotate encryption keys when needed  
✅ **Cloud KMS Ready** - Extensible to AWS KMS, Azure Key Vault, Google Cloud KMS

---

### Files Created

```
backend/
├── app/
│   ├── services/
│   │   └── encryption_service.py          # KMS encryption service
│   ├── models/
│   │   └── encrypted_credentials.py       # Encrypted data models
│   └── ...
├── requirements.txt                        # Added cryptography==42.0.5
└── SECURITY_ENV_TEMPLATE.txt              # Environment variables template
```

---

### How to Use KMS Encryption

#### 1. Setup Encryption Keys

**Generate a master encryption key:**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Add to `.env`:**

```bash
# Required for encryption
ENCRYPTION_MASTER_KEY=gAAAAABf...your-generated-key-here

# Optional: Custom salt (recommended for production)
ENCRYPTION_SALT=your-unique-salt-here
```

#### 2. Using Encrypted Credentials

**Store a sensitive credential:**

```python
from app.models import EncryptedCredential
from app import db

# Create encrypted credential
credential = EncryptedCredential(
    user_id=1,
    credential_type='api_key',
    service_name='openai',
    label='OpenAI Production Key'
)

# Encrypt and store the actual key
credential.set_value('sk-proj-abcd1234...')
db.session.add(credential)
db.session.commit()

# Retrieve and decrypt
decrypted_key = credential.get_value()  # Returns: 'sk-proj-abcd1234...'
```

**Store chatbot API keys:**

```python
from app.models import EncryptedAPIKey

# Create encrypted API key for chatbot
api_key = EncryptedAPIKey(
    chatbot_id=42,
    provider='openai',
    key_name='Production Key',
    is_primary=True
)

api_key.set_key('sk-proj-abcd1234...')
db.session.add(api_key)
db.session.commit()

# Later, retrieve the key
decrypted = api_key.get_key()  # Automatically tracked (usage_count, last_used_at)
```

#### 3. Helper Functions

```python
from app.services.encryption_service import encrypt_field, decrypt_field

# Encrypt any value
encrypted = encrypt_field("sensitive-data")

# Decrypt any value
decrypted = decrypt_field(encrypted)
```

#### 4. Key Rotation

```python
from app.services.encryption_service import get_encryption_service

service = get_encryption_service()

# Rotate to a new key
new_master_key = "new-generated-key-here"
success = service.rotate_key(new_master_key)

# Note: After rotation, you need to re-encrypt all existing data
```

---

### Cloud KMS Integration

The system supports AWS KMS, Azure Key Vault, and Google Cloud KMS:

**AWS KMS:**

```python
from app.services.encryption_service import CloudKMSService

kms = CloudKMSService(provider='aws')
encrypted = kms.encrypt(plaintext)
decrypted = kms.decrypt(ciphertext)
```

**Configuration (`.env`):**

```bash
AWS_REGION=us-east-1
AWS_KMS_KEY_ID=your-kms-key-id
```

---

## 🎫 Part 2: JIT (Just-In-Time) Access System

### What is JIT Access?

**JIT (Just-In-Time) Access** provides **temporary privilege elevation** with approval workflows and comprehensive audit logging. Instead of granting permanent elevated permissions, users request temporary access for a specific duration.

### Features Implemented

✅ **Access Request/Approval Workflow** - Request → Review → Approve/Reject  
✅ **Time-Bound Permissions** - Automatic expiration after specified duration  
✅ **Multiple Access Levels** - read, write, admin, super_admin  
✅ **Comprehensive Audit Logging** - Track all privileged actions  
✅ **Temporary Roles** - Automatically assigned and revoked  
✅ **Auto-Expiration** - Celery task expires old accesses every 5 minutes  
✅ **Revocation Support** - Manual revocation of active access  

---

### Files Created

```
backend/
├── app/
│   ├── models/
│   │   └── jit_access.py                  # JIT models (3 tables)
│   ├── services/
│   │   └── jit_access_service.py          # JIT business logic
│   ├── api/
│   │   └── jit_access.py                  # REST API endpoints
│   └── tasks/
│       └── retraining_tasks.py            # Added expire_jit_accesses task
└── app/celery_app.py                      # Added expiration schedule
```

---

### Database Schema

**3 New Tables:**

1. **`jit_access_requests`** - Access requests with approval workflow
2. **`jit_access_audit_logs`** - Audit trail of privileged actions
3. **`temporary_roles`** - Active temporary role assignments

---

### How to Use JIT Access

#### 1. Request Temporary Access

**API Endpoint:**

```http
POST /api/jit-access/request
Authorization: Bearer <token>
Content-Type: application/json

{
  "requested_level": "admin",
  "resource_type": "tenant",
  "resource_id": 123,
  "justification": "Need to fix critical bug in tenant configuration",
  "duration_minutes": 60
}
```

**Response:**

```json
{
  "message": "Access request created successfully",
  "request": {
    "id": 1,
    "status": "pending",
    "requested_level": "admin",
    "requested_duration": 60,
    "requested_at": "2025-10-08T23:00:00Z"
  }
}
```

#### 2. Approve/Reject Requests (Super Admin)

**Approve:**

```http
POST /api/jit-access/requests/1/approve
Authorization: Bearer <super-admin-token>

{
  "approval_reason": "Approved for emergency bug fix"
}
```

**Reject:**

```http
POST /api/jit-access/requests/1/reject
Authorization: Bearer <super-admin-token>

{
  "rejection_reason": "Insufficient justification"
}
```

#### 3. Check Active Access

**Get your active accesses:**

```http
GET /api/jit-access/active
Authorization: Bearer <token>
```

**Response:**

```json
{
  "active_accesses": [
    {
      "id": 1,
      "role_name": "admin",
      "valid_from": "2025-10-08T23:00:00Z",
      "valid_until": "2025-10-09T00:00:00Z",
      "is_currently_valid": true
    }
  ],
  "total": 1
}
```

#### 4. Programmatic Access Check

```python
from app.services.jit_access_service import JITAccessService

# Check if user has specific access
has_access = JITAccessService.check_user_access(
    user_id=123,
    required_level='admin',
    resource_type='tenant',
    resource_id=456
)

if has_access:
    # User has temporary admin access
    # Perform privileged operation
    pass
```

#### 5. Audit Logging

**Every privileged action is automatically logged:**

```python
# Log a privileged action
JITAccessService.log_action(
    user_id=123,
    access_request_id=1,
    action_type='update_tenant',
    resource_type='tenant',
    resource_id=456,
    action_description='Updated tenant billing configuration',
    action_data={'field': 'billing_tier', 'old': 'basic', 'new': 'premium'},
    success=True
)
```

**View audit logs (Super Admin):**

```http
GET /api/jit-access/audit-logs?user_id=123&limit=100
Authorization: Bearer <super-admin-token>
```

---

### Access Levels

| Level | Permissions | Use Case |
|-------|-------------|----------|
| `read` | View-only access | Debugging, investigation |
| `write` | Create/update resources | Data entry, configuration |
| `admin` | Full tenant admin | User management, settings |
| `super_admin` | Platform-wide access | System maintenance, global ops |

---

### Auto-Expiration

A **Celery Beat task** runs **every 5 minutes** to expire old access grants:

```python
# Scheduled task (runs automatically)
@shared_task
def expire_jit_accesses():
    expired_count = JITAccessService.expire_old_accesses()
    logger.info(f"Expired {expired_count} access grants")
```

**Configuration:** `backend/app/celery_app.py`

```python
'expire-jit-accesses': {
    'task': 'app.tasks.retraining_tasks.expire_jit_accesses',
    'schedule': 300.0,  # 5 minutes
},
```

---

## 🚀 Installation & Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**New dependency:** `cryptography==42.0.5`

### 2. Configure Environment Variables

Copy the security template:

```bash
# Review the template
cat SECURITY_ENV_TEMPLATE.txt

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add to .env
echo "ENCRYPTION_MASTER_KEY=your-generated-key" >> .env
```

### 3. Run Database Migrations

```bash
# Create migration for new tables
flask db migrate -m "Add JIT access and encrypted credentials tables"

# Apply migration
flask db upgrade
```

### 4. Start Celery (for JIT expiration)

```bash
# Start worker
celery -A app.celery_app:make_celery worker --pool=solo --loglevel=info -Q retraining

# Start beat (for scheduled tasks)
celery -A app.celery_app:make_celery beat --loglevel=info
```

---

## 📊 API Endpoints

### KMS Encryption

No direct API endpoints - use models programmatically.

### JIT Access

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/jit-access/request` | POST | User | Request temporary access |
| `/api/jit-access/requests` | GET | User | List your requests |
| `/api/jit-access/requests/<id>` | GET | User | Get request details |
| `/api/jit-access/requests/<id>/approve` | POST | Super Admin | Approve request |
| `/api/jit-access/requests/<id>/reject` | POST | Super Admin | Reject request |
| `/api/jit-access/requests/<id>/revoke` | POST | Super Admin | Revoke active access |
| `/api/jit-access/active` | GET | User | Get your active accesses |
| `/api/jit-access/audit-logs` | GET | Super Admin | View audit logs |

---

## 🔍 Testing

### Test Encryption

```python
from app import create_app
from app.services.encryption_service import get_encryption_service

app = create_app()
with app.app_context():
    service = get_encryption_service()
    
    # Test encryption/decryption
    plaintext = "secret-api-key-12345"
    encrypted = service.encrypt(plaintext)
    decrypted = service.decrypt(encrypted)
    
    assert plaintext == decrypted
    print("✅ Encryption test passed!")
```

### Test JIT Access

```python
from app import create_app
from app.services.jit_access_service import JITAccessService
from app import db

app = create_app()
with app.app_context():
    # Request access
    request = JITAccessService.request_access(
        requester_id=1,
        requested_level='admin',
        resource_type='tenant',
        justification='Testing JIT access',
        duration_minutes=60
    )
    
    print(f"✅ Request created: {request.id}")
    
    # Approve it
    approved = JITAccessService.approve_request(
        request_id=request.id,
        approver_id=2
    )
    
    print(f"✅ Request approved: {approved.is_active()}")
    
    # Check access
    has_access = JITAccessService.check_user_access(
        user_id=1,
        required_level='admin',
        resource_type='tenant'
    )
    
    print(f"✅ Access check: {has_access}")
```

---

## 🛡️ Security Best Practices

### For KMS Encryption

1. ✅ **Never commit encryption keys** to git
2. ✅ **Use different keys** for dev/staging/prod
3. ✅ **Rotate keys regularly** (e.g., every 90 days)
4. ✅ **Back up encrypted data** before key rotation
5. ✅ **Use cloud KMS** in production (AWS KMS, Azure Key Vault)
6. ✅ **Monitor key usage** and access patterns

### For JIT Access

1. ✅ **Require justification** for all requests
2. ✅ **Set maximum duration** limits (default 24 hours)
3. ✅ **Review audit logs** regularly
4. ✅ **Revoke unused access** proactively
5. ✅ **Alert on suspicious patterns** (multiple requests, unusual hours)
6. ✅ **Document approval criteria**

---

## 📈 Monitoring & Compliance

### Metrics to Track

- **Encryption Service:**
  - Encryption/decryption operations per second
  - Failed encryption attempts
  - Key rotation events

- **JIT Access:**
  - Pending requests count
  - Average approval time
  - Expired/revoked access count
  - Audit log entries per day

### Compliance

Both systems help achieve:

- ✅ **SOC 2 Type II** - Access controls and audit logging
- ✅ **ISO 27001** - Information security management
- ✅ **GDPR** - Data protection and encryption at rest
- ✅ **HIPAA** - Health data encryption requirements
- ✅ **PCI DSS** - Secure storage of sensitive data

---

## 🐛 Troubleshooting

### Encryption Issues

**Problem:** `Encryption service not initialized`

**Solution:** Check that `ENCRYPTION_MASTER_KEY` is set in `.env`

**Problem:** `Failed to decrypt data`

**Solution:** Key may have been rotated. Check key version.

### JIT Access Issues

**Problem:** Access expired immediately

**Solution:** Check system time synchronization

**Problem:** Celery task not running

**Solution:** Verify Celery Beat is running and Redis is accessible

---

## 📚 References

- [Cryptography Library Docs](https://cryptography.io/)
- [Fernet Specification](https://github.com/fernet/spec/)
- [JIT Access Best Practices](https://cloud.google.com/iam/docs/just-in-time-access)
- [AWS KMS Documentation](https://docs.aws.amazon.com/kms/)

---

**Implementation Date:** October 2025  
**Status:** ✅ Production Ready  
**Version:** 1.0.0


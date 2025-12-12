# ConvoPilot API Examples

This document provides examples of common API requests and responses for the multi-tenant platform.

## Authentication

### Register New Tenant Admin
```http
POST /api/v1/auth/signup
Content-Type: application/json

{
    "email": "admin@techcorp.com",
    "password": "securePassword123",
    "tenant_id": "techcorp",
    "role": "tenant_admin",
    "first_name": "John",
    "last_name": "Doe"
}
```

Response:
```json
{
    "message": "User registered successfully",
    "token": "eyJ0eXAiOiJKV1QiLCJhbGci...",
    "user": {
        "id": 1,
        "email": "admin@techcorp.com",
        "role": "tenant_admin"
    }
}
```

### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
    "email": "admin@techcorp.com",
    "password": "securePassword123"
}
```

Response:
```json
{
    "token": "eyJ0eXAiOiJKV1QiLCJhbGci...",
    "user": {
        "id": 1,
        "email": "admin@techcorp.com",
        "role": "tenant_admin",
        "tenant_id": "techcorp"
    }
}
```

### OAuth Login
```http
GET /api/v1/auth/oauth/google?tenant_id=techcorp
```

Response (after OAuth flow):
```json
{
    "token": "eyJ0eXAiOiJKV1QiLCJhbGci...",
    "user": {
        "id": 2,
        "email": "user@gmail.com",
        "role": "user",
        "tenant_id": "techcorp"
    }
}
```

### Refresh Token
```http
POST /api/v1/auth/token/refresh
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...

{
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGci..."
}
```

Response:
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGci...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGci..."
}
```

## Tenant Management

### Create New Tenant
```http
POST /api/v1/tenants
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...
Content-Type: application/json

{
    "name": "TechCorp Inc.",
    "domain": "techcorp.com",
    "type": "managed",
    "admin_email": "admin@techcorp.com",
    "admin_password": "securePassword123"
}
```

Response:
```json
{
    "message": "Tenant created successfully",
    "tenant": {
        "id": 1,
        "tenant_id": "techcorp",
        "name": "TechCorp Inc.",
        "domain": "techcorp.com",
        "type": "managed",
        "status": "active"
    }
}
```

### List Tenants
```http
GET /api/v1/tenants?page=1&per_page=10
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...
```

Response:
```json
{
    "tenants": [
        {
            "id": 1,
            "tenant_id": "techcorp",
            "name": "TechCorp Inc.",
            "domain": "techcorp.com",
            "type": "managed",
            "status": "active",
            "created_at": "2025-08-23T23:04:33Z"
        }
    ],
    "pagination": {
        "page": 1,
        "pages": 1,
        "total": 1,
        "per_page": 10
    }
}
```

### Update Tenant Configuration
```http
PUT /api/v1/tenants/techcorp/config
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...
X-Tenant-ID: techcorp
Content-Type: application/json

{
    "features": {
        "multi_language": true,
        "analytics": true,
        "lead_generation": true
    },
    "limits": {
        "max_chatbots": 10,
        "max_conversations_per_day": 1000
    }
}
```

Response:
```json
{
    "message": "Configuration updated successfully",
    "config": {
        "features": {
            "multi_language": true,
            "analytics": true,
            "lead_generation": true
        },
        "limits": {
            "max_chatbots": 10,
            "max_conversations_per_day": 1000
        }
    }
}
```

## User Management

### Create User
```http
POST /api/v1/users
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...
X-Tenant-ID: techcorp
Content-Type: application/json

{
    "email": "user@techcorp.com",
    "password": "userPassword123",
    "role": "user",
    "first_name": "Jane",
    "last_name": "Smith"
}
```

Response:
```json
{
    "message": "User created successfully",
    "user": {
        "id": 2,
        "email": "user@techcorp.com",
        "role": "user",
        "first_name": "Jane",
        "last_name": "Smith"
    }
}
```

### List Users
```http
GET /api/v1/users?page=1&per_page=10
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGci...
X-Tenant-ID: techcorp
```

Response:
```json
{
    "users": [
        {
            "id": 1,
            "email": "admin@techcorp.com",
            "role": "tenant_admin",
            "first_name": "John",
            "last_name": "Doe",
            "status": "active",
            "last_login": "2025-08-23T23:04:33Z"
        },
        {
            "id": 2,
            "email": "user@techcorp.com",
            "role": "user",
            "first_name": "Jane",
            "last_name": "Smith",
            "status": "active",
            "last_login": null
        }
    ],
    "pagination": {
        "page": 1,
        "pages": 1,
        "total": 2,
        "per_page": 10
    }
}
```

## Error Responses

### Authentication Required
```json
{
    "error": "Authentication required"
}
```

### Invalid Token
```json
{
    "error": "Invalid or expired token"
}
```

### Permission Denied
```json
{
    "error": "Permission denied",
    "required_permission": "manage_users"
}
```

### Tenant Not Found
```json
{
    "error": "Tenant not found"
}
```

### Resource Conflict
```json
{
    "error": "Email already registered"
}
```

### Invalid Input
```json
{
    "error": "Invalid input",
    "details": {
        "email": "Invalid email format",
        "password": "Password must be at least 8 characters"
    }
}
```

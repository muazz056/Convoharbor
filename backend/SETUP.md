# 🚀 ConvoPilot Backend Setup Guide

Complete setup instructions for the ConvoPilot Flask backend application.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Super Admin Creation](#super-admin-creation)
- [Running the Application](#running-the-application)
- [Development Tools](#development-tools)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## 🔧 Prerequisites

Before starting, ensure you have the following installed:

- *Python 3.8+* (Recommended: Python 3.9 or 3.10)
- *pip* (Python package manager)
- *PostgreSQL* (Local or cloud instance like Neon)
- *Redis* (For background tasks - optional for basic functionality)
- *Git* (For version control)

### System Requirements

- *RAM*: Minimum 4GB (8GB recommended)
- *Storage*: At least 2GB free space
- *OS*: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)

## ⚡ Quick Start

### 🍎 Mac Setup

```bash
# 1. Clone the repository / Open project in IDE
cd backend

# 2. Install Python 3.11 (if not already installed)
brew install python@3.11

# 3. Create virtual environment with Python 3.11
/opt/homebrew/bin/python3.11 -m venv venv

# 4. Activate virtual environment
source venv/bin/activate

# 5. Verify Python version
python --version

# 6. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt


# 6. Create super admin (OPTIONAL) In New terminal
 venv\Scripts\activate
# Edit email and password from this file and then run to create superadmin
python create_neon_admin.py
OR
# just login with this already superadmin:
email = muazijazadmin@gmail.com
password= Muazijaz1234@

# 7. Run the application (In new terminal)
python run.py
```



### 🪟 Windows Setup

```bash
# 1. Clone the repository / Open project in IDE
cd backend

# 2. Create virtual environment with Python 3.11
py -3.11 -m venv venv

# 3. Activate virtual environment
venv\Scripts\activate

# 4. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt


# 6. Create super admin (OPTIONAL) In New terminal
 venv\Scripts\activate
# Edit email and password from this file and then run to create superadmin
python create_neon_admin.py
OR
# just login with this already superadmin:
email = muazijazadmin@gmail.com
password= Muazijaz1234@

# 7. Run the application (In new terminal)
python run.py
```


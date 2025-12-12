# app/services/encryption_service.py

"""
KMS (Key Management System) Encryption Service
Provides field-level encryption for sensitive data using Fernet symmetric encryption.
Supports local encryption and can be extended to AWS KMS, Azure Key Vault, or Google Cloud KMS.
"""

import os
import base64
import logging
from typing import Optional, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from flask import current_app

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Field-level encryption service using Fernet (symmetric encryption).
    
    Features:
    - Encrypt/decrypt sensitive fields (API keys, passwords, tokens)
    - Key derivation from master key
    - Support for key rotation
    - Can be extended to cloud KMS (AWS, Azure, GCP)
    """
    
    def __init__(self):
        """Initialize encryption service with master key from environment."""
        self._fernet = None
        self._master_key = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize Fernet encryption with derived key."""
        try:
            # Get master key from environment
            master_key = os.getenv('ENCRYPTION_MASTER_KEY')
            
            if not master_key:
                logger.warning("⚠️ ENCRYPTION_MASTER_KEY not set. Generating a temporary key for development.")
                logger.warning("⚠️ This key will change on restart. Set ENCRYPTION_MASTER_KEY in production!")
                master_key = Fernet.generate_key().decode('utf-8')
                
            self._master_key = master_key
            
            # Derive encryption key using PBKDF2HMAC
            salt = os.getenv('ENCRYPTION_SALT', 'convopilot-default-salt').encode()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            
            key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
            self._fernet = Fernet(key)
            
            logger.info("✅ Encryption service initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize encryption service: {e}")
            raise
    
    def encrypt(self, plaintext: str) -> Optional[str]:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string, or None if encryption fails
        """
        if not plaintext:
            return None
        
        try:
            if isinstance(plaintext, str):
                plaintext = plaintext.encode('utf-8')
            
            encrypted = self._fernet.encrypt(plaintext)
            return base64.urlsafe_b64encode(encrypted).decode('utf-8')
            
        except Exception as e:
            logger.error(f"❌ Encryption failed: {e}")
            return None
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string, or None if decryption fails
        """
        if not ciphertext:
            return None
        
        try:
            encrypted_data = base64.urlsafe_b64decode(ciphertext.encode('utf-8'))
            decrypted = self._fernet.decrypt(encrypted_data)
            return decrypted.decode('utf-8')
            
        except Exception as e:
            logger.error(f"❌ Decryption failed: {e}")
            return None
    
    def encrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data
            fields: List of field names to encrypt
            
        Returns:
            Dictionary with specified fields encrypted
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                encrypted = self.encrypt(str(result[field]))
                if encrypted:
                    result[field] = encrypted
        return result
    
    def decrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            fields: List of field names to decrypt
            
        Returns:
            Dictionary with specified fields decrypted
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                decrypted = self.decrypt(result[field])
                if decrypted:
                    result[field] = decrypted
        return result
    
    def rotate_key(self, new_master_key: str) -> bool:
        """
        Rotate the master encryption key.
        
        Args:
            new_master_key: New master key to use
            
        Returns:
            True if rotation successful, False otherwise
            
        Note:
            This requires re-encrypting all encrypted data in the database.
            Should be done during maintenance window.
        """
        try:
            old_fernet = self._fernet
            
            # Initialize with new key
            salt = os.getenv('ENCRYPTION_SALT', 'convopilot-default-salt').encode()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            
            key = base64.urlsafe_b64encode(kdf.derive(new_master_key.encode()))
            self._fernet = Fernet(key)
            self._master_key = new_master_key
            
            logger.info("✅ Encryption key rotated successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Key rotation failed: {e}")
            # Restore old key
            self._fernet = old_fernet
            return False
    
    def is_encrypted(self, text: str) -> bool:
        """
        Check if a string appears to be encrypted.
        
        Args:
            text: String to check
            
        Returns:
            True if text appears to be encrypted, False otherwise
        """
        if not text:
            return False
        
        try:
            # Try to decrypt - if it works, it was encrypted
            decrypted = self.decrypt(text)
            return decrypted is not None
        except:
            return False


class CloudKMSService:
    """
    Extended KMS service that supports cloud providers.
    Can be implemented for AWS KMS, Azure Key Vault, or Google Cloud KMS.
    """
    
    def __init__(self, provider: str = 'local'):
        """
        Initialize cloud KMS service.
        
        Args:
            provider: 'local', 'aws', 'azure', or 'gcp'
        """
        self.provider = provider
        self._encryption_service = EncryptionService()
        
        if provider == 'aws':
            self._init_aws_kms()
        elif provider == 'azure':
            self._init_azure_kms()
        elif provider == 'gcp':
            self._init_gcp_kms()
        else:
            logger.info("📦 Using local encryption (Fernet)")
    
    def _init_aws_kms(self):
        """Initialize AWS KMS client."""
        try:
            import boto3
            self.kms_client = boto3.client('kms', region_name=os.getenv('AWS_REGION', 'us-east-1'))
            logger.info("✅ AWS KMS initialized")
        except ImportError:
            logger.warning("⚠️ boto3 not installed. Install with: pip install boto3")
        except Exception as e:
            logger.error(f"❌ AWS KMS initialization failed: {e}")
    
    def _init_azure_kms(self):
        """Initialize Azure Key Vault client."""
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
            
            vault_url = os.getenv('AZURE_KEY_VAULT_URL')
            if vault_url:
                self.kv_client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
                logger.info("✅ Azure Key Vault initialized")
        except ImportError:
            logger.warning("⚠️ azure-keyvault-secrets not installed")
        except Exception as e:
            logger.error(f"❌ Azure Key Vault initialization failed: {e}")
    
    def _init_gcp_kms(self):
        """Initialize Google Cloud KMS client."""
        try:
            from google.cloud import kms_v1
            self.kms_client = kms_v1.KeyManagementServiceClient()
            logger.info("✅ Google Cloud KMS initialized")
        except ImportError:
            logger.warning("⚠️ google-cloud-kms not installed")
        except Exception as e:
            logger.error(f"❌ Google Cloud KMS initialization failed: {e}")
    
    def encrypt(self, plaintext: str) -> Optional[str]:
        """Encrypt using configured provider."""
        return self._encryption_service.encrypt(plaintext)
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        """Decrypt using configured provider."""
        return self._encryption_service.decrypt(ciphertext)


# Global encryption service instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get or create global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_field(value: Any) -> Optional[str]:
    """Helper function to encrypt a field value."""
    if value is None:
        return None
    service = get_encryption_service()
    return service.encrypt(str(value))


def decrypt_field(value: Any) -> Optional[str]:
    """Helper function to decrypt a field value."""
    if value is None:
        return None
    service = get_encryption_service()
    return service.decrypt(str(value))


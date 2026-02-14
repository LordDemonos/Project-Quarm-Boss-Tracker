"""Security utilities for encrypting sensitive data."""
import base64
from typing import Optional
import hashlib

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class SecurityManager:
    """Manages encryption/decryption of sensitive data."""
    
    # Simple encryption key (derived from app name + version)
    # In a production app, this would be more sophisticated
    _KEY_SALT = "EverQuestBossTracker2026"
    
    @staticmethod
    def _get_key() -> bytes:
        """Generate encryption key from salt."""
        # Create a simple key from the salt
        key = hashlib.sha256(SecurityManager._KEY_SALT.encode()).digest()
        return key
    
    @staticmethod
    def _xor_encrypt(data: str, key: bytes) -> str:
        """Simple XOR encryption (obfuscation, not true security)."""
        data_bytes = data.encode('utf-8')
        encrypted = bytearray()
        key_len = len(key)
        for i, byte in enumerate(data_bytes):
            encrypted.append(byte ^ key[i % key_len])
        return base64.b64encode(bytes(encrypted)).decode('utf-8')
    
    @staticmethod
    def _xor_decrypt(encrypted_data: str, key: bytes) -> str:
        """Simple XOR decryption."""
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted = bytearray()
            key_len = len(key)
            for i, byte in enumerate(encrypted_bytes):
                decrypted.append(byte ^ key[i % key_len])
            return bytes(decrypted).decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return ""
    
    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """
        Encrypt sensitive data.
        
        Args:
            plaintext: Plain text to encrypt
            
        Returns:
            Encrypted string (base64 encoded)
        """
        if not plaintext:
            return ""
        try:
            key = cls._get_key()
            encrypted = cls._xor_encrypt(plaintext, key)
            logger.debug("Data encrypted successfully")
            return encrypted
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return plaintext  # Fallback to plaintext on error
    
    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """
        Decrypt sensitive data.
        
        Args:
            ciphertext: Encrypted string (base64 encoded)
            
        Returns:
            Decrypted plain text
        """
        if not ciphertext:
            return ""
        try:
            key = cls._get_key()
            decrypted = cls._xor_decrypt(ciphertext, key)
            logger.debug("Data decrypted successfully")
            return decrypted
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return ciphertext  # Fallback to ciphertext on error
    
    @classmethod
    def encrypt_dict_value(cls, data: dict, key: str) -> None:
        """
        Encrypt a value in a dictionary in-place.
        
        Args:
            data: Dictionary to modify
            key: Key to encrypt
        """
        if key in data and data[key]:
            data[key] = cls.encrypt(data[key])
    
    @classmethod
    def decrypt_dict_value(cls, data: dict, key: str) -> None:
        """
        Decrypt a value in a dictionary in-place.
        Only attempts decryption if the value appears to be encrypted (base64).
        
        Args:
            data: Dictionary to modify
            key: Key to decrypt
        """
        if key not in data or not data[key]:
            return
        
        value = data[key]
        if not isinstance(value, str):
            return
        
        # Check if value looks like encrypted data (base64 encoded)
        # Encrypted values are base64 strings, typically longer
        # Plain text URLs/tokens usually start with http://, https://, or are shorter
        try:
            import base64
            import re
            
            # Heuristic: encrypted values are base64 (longer, alphanumeric + / + =)
            # Plain text URLs start with http:// or https://
            # Plain text tokens are usually shorter alphanumeric strings
            
            # If it starts with http:// or https://, it's definitely plaintext
            if value.startswith(('http://', 'https://')):
                logger.debug(f"Value for key '{key}' appears to be plaintext URL, skipping decryption")
                return
            
            # If it's short (< 20 chars), likely plaintext token
            if len(value) < 20:
                logger.debug(f"Value for key '{key}' is too short to be encrypted, assuming plaintext")
                return
            
            # Check if it's valid base64 format
            # Base64 strings contain A-Z, a-z, 0-9, +, /, and = for padding
            base64_pattern = re.compile(r'^[A-Za-z0-9+/]+=*$')
            if not base64_pattern.match(value):
                logger.debug(f"Value for key '{key}' doesn't match base64 pattern, assuming plaintext")
                return
            
            # Try to decode as base64
            try:
                base64.b64decode(value, validate=True)
                # If it's valid base64, try to decrypt
                decrypted = cls.decrypt(value)
                # Only update if decryption succeeded and result is different and valid
                if decrypted and decrypted != value and len(decrypted) > 0:
                    data[key] = decrypted
                    logger.debug(f"Decrypted value for key '{key}'")
                else:
                    logger.debug(f"Decryption for key '{key}' produced invalid result, keeping original")
            except Exception as e:
                # Not valid base64 or decryption failed - assume it's plaintext
                logger.debug(f"Value for key '{key}' decryption failed, assuming plaintext: {e}")
        except Exception as e:
            # If anything fails, assume it's already plaintext
            logger.debug(f"Could not process value for key '{key}', assuming plaintext: {e}")

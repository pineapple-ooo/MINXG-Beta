"""
MINXG Crypto Workers — Encryption, hashing, and digital signatures.
"""
from __future__ import annotations

from typing import Dict, Any, Optional


class AES256EncryptWorker:
    """AES-256-GCM encryption."""
    worker_id = "aes_encrypt"
    version = "0.19.0"

    def execute(self, plaintext: str, key: str, aad: Optional[str] = None) -> Dict[str, Any]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64
        import os

        key_bytes = key.encode()[:32].ljust(32, b"\0")
        aesgcm = AESGCM(key_bytes)
        nonce = os.urandom(12)
        plaintext_bytes = plaintext.encode()
        aad_bytes = aad.encode() if aad else None

        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, aad_bytes)
        return {
            "ciphertext": base64.b64encode(nonce + ciphertext).decode(),
            "algorithm": "AES-256-GCM",
            "nonce": base64.b64encode(nonce).decode(),
        }


class AES256DecryptWorker:
    """AES-256-GCM decryption."""
    worker_id = "aes_decrypt"
    version = "0.19.0"

    def execute(self, ciphertext_b64: str, key: str, aad: Optional[str] = None) -> Dict[str, Any]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64

        key_bytes = key.encode()[:32].ljust(32, b"\0")
        aesgcm = AESGCM(key_bytes)
        data = base64.b64decode(ciphertext_b64)
        nonce = data[:12]
        ciphertext = data[12:]
        aad_bytes = aad.encode() if aad else None

        plaintext = aesgcm.decrypt(nonce, ciphertext, aad_bytes)
        return {"plaintext": plaintext.decode(), "algorithm": "AES-256-GCM"}


class HashWorker:
    """Compute cryptographic hashes."""
    worker_id = "hash"
    version = "0.19.0"

    def execute(self, data: str, algorithm: str = "sha256", hex_output: bool = True) -> Dict[str, Any]:
        import hashlib

        algorithms = {
            "md5": hashlib.md5,
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha384": hashlib.sha384,
            "sha512": hashlib.sha512,
            "blake2b": hashlib.blake2b,
            "blake2s": hashlib.blake2s,
        }

        if algorithm not in algorithms:
            return {"error": f"Unsupported algorithm: {algorithm}", "supported": list(algorithms.keys())}

        h = algorithms[algorithm](data.encode())
        if hex_output:
            return {"algorithm": algorithm, "hash": h.hexdigest(), "input_length": len(data)}
        else:
            return {"algorithm": algorithm, "hash": h.digest(), "input_length": len(data)}


class HMACWorker:
    """Compute HMAC."""
    worker_id = "hmac"
    version = "0.19.0"

    def execute(self, data: str, key: str, algorithm: str = "sha256") -> Dict[str, Any]:
        import hmac as hmac_mod
        import hashlib

        algorithms = {
            "md5": hashlib.md5,
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
        }

        if algorithm not in algorithms:
            return {"error": f"Unsupported algorithm: {algorithm}"}

        h = hmac_mod.new(key.encode(), data.encode(), algorithms[algorithm])
        return {"algorithm": algorithm, "hmac": h.hexdigest()}


class PBKDF2Worker:
    """Derive key from password."""
    worker_id = "pbkdf2"
    version = "0.19.0"

    def execute(self, password: str, salt: Optional[str] = None, iterations: int = 100000, dklen: int = 32) -> Dict[str, Any]:
        import hashlib
        import os
        import base64

        if salt is None:
            salt = os.urandom(16)
            salt_str = base64.b64encode(salt).decode()
        else:
            salt = salt.encode()
            salt_str = salt.decode() if isinstance(salt, bytes) else salt

        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt if isinstance(salt, bytes) else salt.encode(), iterations, dklen)
        return {
            "derived_key": base64.b64encode(key).decode(),
            "salt": salt_str,
            "iterations": iterations,
            "key_length": dklen,
            "algorithm": "PBKDF2-HMAC-SHA256",
        }


class SignWorker:
    """Digital signature with ECDSA."""
    worker_id = "sign"
    version = "0.19.0"

    def execute(self, data: str, private_key_pem: str) -> Dict[str, Any]:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        import base64

        private_key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
        signature = private_key.sign(data.encode(), ec.ECDSA(hashes.SHA256()))
        return {"signature": base64.b64encode(signature).decode(), "algorithm": "ECDSA-SHA256"}


class VerifyWorker:
    """Verify digital signature."""
    worker_id = "verify"
    version = "0.19.0"

    def execute(self, data: str, signature_b64: str, public_key_pem: str) -> Dict[str, Any]:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        import base64

        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        signature = base64.b64decode(signature_b64)

        try:
            public_key.verify(signature, data.encode(), ec.ECDSA(hashes.SHA256()))
            return {"valid": True, "algorithm": "ECDSA-SHA256"}
        except Exception:
            return {"valid": False, "algorithm": "ECDSA-SHA256"}


class GenerateKeyPairWorker:
    """Generate ECDSA key pair."""
    worker_id = "generate_keypair"
    version = "0.19.0"

    def execute(self, curve: str = "secp256r1") -> Dict[str, Any]:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization

        curves = {
            "secp256r1": ec.SECP256R1(),
            "secp384r1": ec.SECP384R1(),
            "secp521r1": ec.SECP521R1(),
        }

        if curve not in curves:
            return {"error": f"Unsupported curve: {curve}", "supported": list(curves.keys())}

        private_key = ec.generate_private_key(curves[curve])
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        return {
            "private_key": private_pem,
            "public_key": public_pem,
            "curve": curve,
            "algorithm": "ECDSA",
        }


class RandomBytesWorker:
    """Generate cryptographically secure random bytes."""
    worker_id = "random_bytes"
    version = "0.19.0"

    def execute(self, length: int = 32, encoding: str = "hex") -> Dict[str, Any]:
        import os
        import base64

        data = os.urandom(length)
        if encoding == "hex":
            return {"bytes": data.hex(), "length": length, "encoding": "hex"}
        elif encoding == "base64":
            return {"bytes": base64.b64encode(data).decode(), "length": length, "encoding": "base64"}
        else:
            return {"error": f"Unsupported encoding: {encoding}"}

"""Signing client for Sigstore integration."""

import hashlib
import logging
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.x509 import load_pem_x509_certificate

from ..config import CertusTrustSettings

logger = logging.getLogger(__name__)


class SigningClient:
    """
    Client for artifact signing operations.

    Supports:
    - Key-based signing (RSA/ECDSA)
    - Keyless signing preparation (for Fulcio integration)
    - Signature verification
    """

    def __init__(self, settings: CertusTrustSettings):
        """Initialize signing client.

        Args:
            settings: Certus-Trust configuration
        """
        self.settings = settings
        self._private_key = None
        self._public_key = None

    def _load_key_pair(self):
        """Load private/public key pair from configuration."""
        if self.settings.cosign_key_path:
            try:
                with open(self.settings.cosign_key_path, "rb") as f:
                    key_data = f.read()

                password = None
                if self.settings.cosign_password:
                    password = self.settings.cosign_password.encode()

                # Try to load as private key
                self._private_key = serialization.load_pem_private_key(key_data, password=password)
                self._public_key = self._private_key.public_key()

                logger.info("Loaded signing key pair from file")
            except Exception as e:
                logger.error(f"Failed to load key pair: {e}")
                raise

    async def sign_artifact(
        self,
        artifact_data: bytes,
        use_keyless: bool = True,
    ) -> tuple[bytes, Optional[bytes], str]:
        """
        Sign an artifact.

        Args:
            artifact_data: Artifact bytes to sign
            use_keyless: If True, prepare for keyless signing (Fulcio)
                        If False, use local key

        Returns:
            Tuple of (signature, certificate, artifact_hash)
        """
        # Compute artifact hash
        artifact_hash = hashlib.sha256(artifact_data).hexdigest()

        if use_keyless and self.settings.enable_keyless:
            # Keyless signing - generate ephemeral key pair
            # In production, this would integrate with Fulcio for certificate
            private_key = ec.generate_private_key(ec.SECP256R1())

            # Sign the artifact hash
            signature = private_key.sign(artifact_data, ec.ECDSA(hashes.SHA256()))

            # Export public key for Rekor submission
            # In real implementation, get certificate from Fulcio
            # For now, use public key PEM as certificate substitute
            public_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            certificate = public_pem

            logger.info(
                "Signed artifact with keyless signing",
                extra={
                    "artifact_hash": artifact_hash,
                    "use_keyless": True,
                },
            )

        else:
            # Key-based signing
            if not self._private_key:
                self._load_key_pair()

            if not self._private_key:
                raise RuntimeError("No private key available for signing")

            # Sign based on key type
            if isinstance(self._private_key, rsa.RSAPrivateKey):
                signature = self._private_key.sign(artifact_data, PKCS1v15(), hashes.SHA256())
            elif isinstance(self._private_key, ec.EllipticCurvePrivateKey):
                signature = self._private_key.sign(artifact_data, ec.ECDSA(hashes.SHA256()))
            else:
                raise RuntimeError(f"Unsupported key type: {type(self._private_key)}")

            # Export public key as certificate substitute
            public_pem = self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            certificate = public_pem

            logger.info(
                "Signed artifact with key-based signing",
                extra={
                    "artifact_hash": artifact_hash,
                    "use_keyless": False,
                },
            )

        return signature, certificate, artifact_hash

    async def verify_signature(
        self,
        artifact_data: bytes,
        signature: bytes,
        certificate: Optional[bytes] = None,
        public_key: Optional[bytes] = None,
    ) -> bool:
        """
        Verify a signature.

        Args:
            artifact_data: Original artifact bytes
            signature: Signature to verify
            certificate: Optional PEM certificate (for keyless)
            public_key: Optional PEM public key (for key-based)

        Returns:
            True if signature is valid
        """
        try:
            # Load the verification key
            if certificate:
                # Load from certificate
                cert = load_pem_x509_certificate(certificate)
                verify_key = cert.public_key()
            elif public_key:
                # Load public key directly
                verify_key = serialization.load_pem_public_key(public_key)
            else:
                logger.error("No certificate or public key provided for verification")
                return False

            # Verify based on key type
            if isinstance(verify_key, rsa.RSAPublicKey):
                verify_key.verify(signature, artifact_data, PKCS1v15(), hashes.SHA256())
            elif isinstance(verify_key, ec.EllipticCurvePublicKey):
                verify_key.verify(signature, artifact_data, ec.ECDSA(hashes.SHA256()))
            else:
                logger.error(f"Unsupported key type for verification: {type(verify_key)}")
                return False

            logger.info("Signature verification successful")
            return True

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    def compute_artifact_hash(self, artifact_data: bytes) -> str:
        """Compute SHA256 hash of artifact.

        Args:
            artifact_data: Artifact bytes

        Returns:
            Hex-encoded SHA256 hash
        """
        return hashlib.sha256(artifact_data).hexdigest()

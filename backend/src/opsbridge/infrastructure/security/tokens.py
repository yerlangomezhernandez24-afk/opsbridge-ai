"""Opaque session tokens stored only as SHA-256 verifiers."""

import hashlib
import hmac
import secrets


class OpaqueTokenService:
    def issue(self) -> str:
        return secrets.token_urlsafe(32)

    def verifier(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def csrf_token(self, session_token: str) -> str:
        return hashlib.sha256(f"opsbridge-csrf:{session_token}".encode()).hexdigest()

    def csrf_matches(self, session_token: str, candidate: str) -> bool:
        return hmac.compare_digest(self.csrf_token(session_token), candidate)

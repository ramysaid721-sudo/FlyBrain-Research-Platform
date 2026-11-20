"""Authenticated envelope encryption for FlyBrain storage artifacts.

This module is deliberately KMS-agnostic. A production KeyWrapper must call an
approved KMS/secret manager; this package never persists or generates a KEK.
No plaintext key material is serialized into the envelope.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_FORMAT = "flybrain-aead-envelope-v1"
_ALGORITHM = "AES-256-GCM"


class StorageEncryptionError(ValueError):
    """Raised when an envelope is malformed or cannot be authenticated."""


class KeyWrapper(Protocol):
    """Minimal adapter for an external KMS/secret manager."""

    def wrap_key(self, *, key_id: str, key_version: str, plaintext_key: bytes) -> bytes:
        ...

    def unwrap_key(self, *, key_id: str, key_version: str, wrapped_key: bytes) -> bytes:
        ...


@dataclass(frozen=True)
class EncryptedEnvelope:
    format: str
    algorithm: str
    object_id: str
    scope: str
    schema_version: str
    kek_id: str
    kek_version: str
    nonce_b64: str
    wrapped_dek_b64: str
    ciphertext_b64: str

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, value: str) -> "EncryptedEnvelope":
        try:
            raw = json.loads(value)
            if not isinstance(raw, dict):
                raise TypeError
            expected = set(cls.__dataclass_fields__)
            if set(raw) != expected:
                raise TypeError
            result = cls(**raw)
            if any(not isinstance(v, str) or not v for v in result.__dict__.values()):
                raise TypeError
            if result.format != _FORMAT or result.algorithm != _ALGORITHM:
                raise TypeError
            return result
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise StorageEncryptionError("invalid encrypted envelope") from exc


def _aad(*, object_id: str, scope: str, schema_version: str) -> bytes:
    if not all(isinstance(v, str) and v for v in (object_id, scope, schema_version)):
        raise ValueError("object_id, scope and schema_version must be non-empty strings")
    return json.dumps(
        {"format": _FORMAT, "object_id": object_id, "scope": scope,
         "schema_version": schema_version},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _decode(value: str, field: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
        if not decoded:
            raise ValueError
        return decoded
    except (ValueError, TypeError) as exc:
        raise StorageEncryptionError(f"invalid {field}") from exc


def encrypt_bytes(
    plaintext: bytes, *, object_id: str, scope: str, schema_version: str,
    kek_id: str, kek_version: str, key_wrapper: KeyWrapper,
) -> EncryptedEnvelope:
    """Encrypt bytes with a fresh DEK and wrap that DEK using the configured KMS."""
    if not isinstance(plaintext, bytes):
        raise TypeError("plaintext must be bytes")
    if not all(isinstance(v, str) and v for v in (kek_id, kek_version)):
        raise ValueError("KMS key id and version are required")
    aad = _aad(object_id=object_id, scope=scope, schema_version=schema_version)
    dek = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    wrapped = key_wrapper.wrap_key(
        key_id=kek_id, key_version=kek_version, plaintext_key=dek
    )
    if not isinstance(wrapped, bytes) or not wrapped:
        raise StorageEncryptionError("KMS returned an invalid wrapped key")
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
    return EncryptedEnvelope(
        format=_FORMAT, algorithm=_ALGORITHM, object_id=object_id, scope=scope,
        schema_version=schema_version, kek_id=kek_id, kek_version=kek_version,
        nonce_b64=base64.b64encode(nonce).decode("ascii"),
        wrapped_dek_b64=base64.b64encode(wrapped).decode("ascii"),
        ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
    )


def decrypt_bytes(envelope: EncryptedEnvelope, *, key_wrapper: KeyWrapper,
                  expected_object_id: str, expected_scope: str,
                  expected_schema_version: str) -> bytes:
    """Decrypt only when envelope identity matches caller-supplied context."""
    if not isinstance(envelope, EncryptedEnvelope):
        raise TypeError("envelope must be EncryptedEnvelope")
    if (envelope.object_id, envelope.scope, envelope.schema_version) != (
        expected_object_id, expected_scope, expected_schema_version
    ):
        raise StorageEncryptionError("encrypted object context mismatch")
    nonce = _decode(envelope.nonce_b64, "nonce")
    if len(nonce) != 12:
        raise StorageEncryptionError("invalid AES-GCM nonce length")
    wrapped = _decode(envelope.wrapped_dek_b64, "wrapped DEK")
    ciphertext = _decode(envelope.ciphertext_b64, "ciphertext")
    try:
        dek = key_wrapper.unwrap_key(
            key_id=envelope.kek_id, key_version=envelope.kek_version,
            wrapped_key=wrapped,
        )
        if not isinstance(dek, bytes) or len(dek) != 32:
            raise StorageEncryptionError("KMS returned an invalid DEK")
        return AESGCM(dek).decrypt(
            nonce, ciphertext,
            _aad(object_id=expected_object_id, scope=expected_scope,
                 schema_version=expected_schema_version),
        )
    except StorageEncryptionError:
        raise
    except Exception as exc:
        raise StorageEncryptionError("decryption or authentication failed") from exc


def rewrap_data_key(
    envelope: EncryptedEnvelope, *, key_wrapper: KeyWrapper,
    new_kek_id: str, new_kek_version: str,
) -> EncryptedEnvelope:
    """Rotate KEK wrapping without changing ciphertext or its DEK."""
    dek = key_wrapper.unwrap_key(
        key_id=envelope.kek_id, key_version=envelope.kek_version,
        wrapped_key=_decode(envelope.wrapped_dek_b64, "wrapped DEK"),
    )
    if not isinstance(dek, bytes) or len(dek) != 32:
        raise StorageEncryptionError("KMS returned an invalid DEK")
    wrapped = key_wrapper.wrap_key(
        key_id=new_kek_id, key_version=new_kek_version, plaintext_key=dek
    )
    if not isinstance(wrapped, bytes) or not wrapped:
        raise StorageEncryptionError("KMS returned an invalid wrapped key")
    return EncryptedEnvelope(
        **{**envelope.__dict__,
           "kek_id": new_kek_id,
           "kek_version": new_kek_version,
           "wrapped_dek_b64": base64.b64encode(wrapped).decode("ascii")}
    )


def rotate_data_key(
    envelope: EncryptedEnvelope, *, key_wrapper: KeyWrapper,
    new_kek_id: str, new_kek_version: str,
) -> EncryptedEnvelope:
    """Rotate the DEK by decrypting and re-encrypting with a fresh DEK/nonce."""
    plaintext = decrypt_bytes(
        envelope, key_wrapper=key_wrapper,
        expected_object_id=envelope.object_id, expected_scope=envelope.scope,
        expected_schema_version=envelope.schema_version,
    )
    return encrypt_bytes(
        plaintext, object_id=envelope.object_id, scope=envelope.scope,
        schema_version=envelope.schema_version, kek_id=new_kek_id,
        kek_version=new_kek_version, key_wrapper=key_wrapper,
    )

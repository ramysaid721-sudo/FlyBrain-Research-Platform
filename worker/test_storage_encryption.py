"""Synthetic tests for storage_encryption; the test KMS is not production key custody."""
import base64
import os
import unittest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from worker.storage_encryption import (
    EncryptedEnvelope, StorageEncryptionError, decrypt_bytes, encrypt_bytes,
    rewrap_data_key, rotate_data_key,
)


class FakeKMS:
    def __init__(self):
        self.keys = {
            ("test-kek", "v1"): AESGCM.generate_key(bit_length=256),
            ("test-kek", "v2"): AESGCM.generate_key(bit_length=256),
            ("wrong-kek", "v1"): AESGCM.generate_key(bit_length=256),
        }

    def wrap_key(self, *, key_id, key_version, plaintext_key):
        nonce = os.urandom(12)
        key = self.keys[(key_id, key_version)]
        return nonce + AESGCM(key).encrypt(nonce, plaintext_key, b"flybrain-test-kms")

    def unwrap_key(self, *, key_id, key_version, wrapped_key):
        nonce, ciphertext = wrapped_key[:12], wrapped_key[12:]
        key = self.keys[(key_id, key_version)]
        return AESGCM(key).decrypt(nonce, ciphertext, b"flybrain-test-kms")


class StorageEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.kms = FakeKMS()
        self.kwargs = dict(
            object_id="artifact-001", scope="project-001",
            schema_version="v1", kek_id="test-kek", kek_version="v1",
            key_wrapper=self.kms,
        )

    def test_round_trip_and_json_round_trip(self):
        envelope = encrypt_bytes(b"public synthetic fixture", **self.kwargs)
        restored = EncryptedEnvelope.from_json(envelope.to_json())
        self.assertEqual(
            decrypt_bytes(restored, key_wrapper=self.kms,
                          expected_object_id="artifact-001",
                          expected_scope="project-001",
                          expected_schema_version="v1"),
            b"public synthetic fixture",
        )

    def test_context_mismatch_is_rejected_before_decryption(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        with self.assertRaises(StorageEncryptionError):
            decrypt_bytes(envelope, key_wrapper=self.kms,
                          expected_object_id="other-object",
                          expected_scope="project-001",
                          expected_schema_version="v1")

    def test_ciphertext_tampering_is_detected(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        raw = bytearray(base64.b64decode(envelope.ciphertext_b64))
        raw[0] ^= 1
        tampered = EncryptedEnvelope(
            **{**envelope.__dict__,
               "ciphertext_b64": base64.b64encode(raw).decode("ascii")}
        )
        with self.assertRaises(StorageEncryptionError):
            decrypt_bytes(tampered, key_wrapper=self.kms,
                          expected_object_id="artifact-001",
                          expected_scope="project-001",
                          expected_schema_version="v1")

    def test_wrong_kek_fails_closed(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        with self.assertRaises(StorageEncryptionError):
            self._wrong_kek(envelope)

    def _wrong_kek(self, envelope):
        wrong = EncryptedEnvelope(**{**envelope.__dict__, "kek_id": "wrong-kek"})
        return decrypt_bytes(wrong, key_wrapper=self.kms,
                             expected_object_id="artifact-001",
                             expected_scope="project-001",
                             expected_schema_version="v1")

    def test_kek_rewrap_preserves_ciphertext_and_plaintext(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        rotated = rewrap_data_key(
            envelope, key_wrapper=self.kms,
            new_kek_id="test-kek", new_kek_version="v2",
        )
        self.assertEqual(rotated.ciphertext_b64, envelope.ciphertext_b64)
        self.assertEqual(rotated.nonce_b64, envelope.nonce_b64)
        self.assertEqual(rotated.kek_version, "v2")
        self.assertEqual(
            decrypt_bytes(rotated, key_wrapper=self.kms,
                          expected_object_id="artifact-001",
                          expected_scope="project-001",
                          expected_schema_version="v1"),
            b"fixture",
        )

    def test_dek_rotation_changes_ciphertext_and_preserves_plaintext(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        rotated = rotate_data_key(
            envelope, key_wrapper=self.kms,
            new_kek_id="test-kek", new_kek_version="v2",
        )
        self.assertNotEqual(rotated.ciphertext_b64, envelope.ciphertext_b64)
        self.assertNotEqual(rotated.nonce_b64, envelope.nonce_b64)
        self.assertEqual(
            decrypt_bytes(rotated, key_wrapper=self.kms,
                          expected_object_id="artifact-001",
                          expected_scope="project-001",
                          expected_schema_version="v1"),
            b"fixture",
        )

    def test_fresh_nonce_for_each_encryption(self):
        first = encrypt_bytes(b"same", **self.kwargs)
        second = encrypt_bytes(b"same", **self.kwargs)
        self.assertNotEqual(first.nonce_b64, second.nonce_b64)

    def test_malformed_envelope_is_rejected(self):
        with self.assertRaises(StorageEncryptionError):
            EncryptedEnvelope.from_json('{"format":"flybrain-aead-envelope-v1"}')



    def test_invalid_nonce_length_is_rejected(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        malformed = EncryptedEnvelope(**{
            **envelope.__dict__,
            "nonce_b64": base64.b64encode(b"short").decode("ascii"),
        })
        with self.assertRaises(StorageEncryptionError):
            self._decrypt(malformed)

    def test_malformed_wrapped_dek_fails_closed(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        malformed = EncryptedEnvelope(**{
            **envelope.__dict__,
            "wrapped_dek_b64": base64.b64encode(b"x").decode("ascii"),
        })
        with self.assertRaises(StorageEncryptionError):
            self._decrypt(malformed)

    def test_tampered_scope_metadata_is_rejected(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        tampered = EncryptedEnvelope(**{
            **envelope.__dict__,
            "scope": "different-project",
        })
        with self.assertRaises(StorageEncryptionError):
            self._decrypt(tampered)

    def test_invalid_dek_returned_by_kms_is_rejected(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)

        class InvalidDEKKMS:
            def unwrap_key(self, **kwargs):
                return b"not-a-32-byte-dek"

        with self.assertRaises(StorageEncryptionError):
            decrypt_bytes(
                envelope,
                key_wrapper=InvalidDEKKMS(),
                expected_object_id="artifact-001",
                expected_scope="project-001",
                expected_schema_version="v1",
            )

    def test_empty_wrapped_key_from_kms_is_rejected(self):
        class EmptyWrappedKeyKMS:
            def wrap_key(self, **kwargs):
                return b""

        with self.assertRaises(StorageEncryptionError):
            encrypt_bytes(
                b"fixture",
                **{**self.kwargs, "key_wrapper": EmptyWrappedKeyKMS()},
            )


    def test_rewrap_rejects_invalid_target_key_metadata(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        for key_id, key_version in (("", "v2"), ("test-kek", "")):
            with self.subTest(key_id=key_id, key_version=key_version):
                with self.assertRaises(StorageEncryptionError):
                    rewrap_data_key(
                        envelope, key_wrapper=self.kms,
                        new_kek_id=key_id, new_kek_version=key_version,
                    )

    def test_rewrap_normalizes_kms_unwrap_failure(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)

        class FailingUnwrapKMS:
            def unwrap_key(self, **kwargs):
                raise RuntimeError("synthetic unwrap failure")

        with self.assertRaisesRegex(StorageEncryptionError, "rewrap operation failed"):
            rewrap_data_key(
                envelope, key_wrapper=FailingUnwrapKMS(),
                new_kek_id="test-kek", new_kek_version="v2",
            )

    def test_rewrap_normalizes_kms_wrap_failure(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)

        class FailingWrapKMS:
            def unwrap_key(self, **kwargs):
                return self.kms.unwrap_key(**kwargs)

            def wrap_key(self, **kwargs):
                raise RuntimeError("synthetic wrap failure")

        failing = FailingWrapKMS()
        failing.kms = self.kms
        with self.assertRaisesRegex(StorageEncryptionError, "rewrap operation failed"):
            rewrap_data_key(
                envelope, key_wrapper=failing,
                new_kek_id="test-kek", new_kek_version="v2",
            )

    def test_rewrap_rejects_unsupported_envelope_format(self):
        envelope = encrypt_bytes(b"fixture", **self.kwargs)
        malformed = EncryptedEnvelope(**{
            **envelope.__dict__,
            "format": "unknown-envelope-format",
        })
        with self.assertRaises(StorageEncryptionError):
            rewrap_data_key(
                malformed, key_wrapper=self.kms,
                new_kek_id="test-kek", new_kek_version="v2",
            )

    def test_rewrap_rejects_non_envelope_input(self):
        with self.assertRaises(TypeError):
            rewrap_data_key(
                {"not": "an envelope"}, key_wrapper=self.kms,
                new_kek_id="test-kek", new_kek_version="v2",
            )

    def _decrypt(self, envelope):
        return decrypt_bytes(
            envelope,
            key_wrapper=self.kms,
            expected_object_id="artifact-001",
            expected_scope="project-001",
            expected_schema_version="v1",
        )

if __name__ == "__main__":
    unittest.main()

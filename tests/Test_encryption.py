import os
import unittest

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("MASTER_KEY", "aa" * 32)

from api.encryption import decrypt_api_key, encrypt_api_key  # noqa: E402
from data.manager_credentials import (  # noqa: E402
    get_credentials_for_call,
    get_credentials_masked,
    save_credentials,
)


class TestEncryption(unittest.TestCase):
    def test_encrypt_decrypt_round_trip(self):
        original = "sk-ant-api03-test-key-abcdefghijklmnop"
        ciphertext, iv = encrypt_api_key(original)
        self.assertNotEqual(ciphertext, original)
        self.assertEqual(len(iv), 24)  # 12 bytes as hex
        restored = decrypt_api_key(ciphertext, iv)
        self.assertEqual(restored, original)

    def test_different_ivs_produce_different_ciphertext(self):
        key = "gsk_testgroqkey1234567890"
        c1, i1 = encrypt_api_key(key)
        c2, i2 = encrypt_api_key(key)
        self.assertNotEqual(c1, c2)
        self.assertNotEqual(i1, i2)
        self.assertEqual(decrypt_api_key(c1, i1), key)
        self.assertEqual(decrypt_api_key(c2, i2), key)

    def test_save_and_load_masked_never_returns_full_key(self):
        manager_id = "encryption_test_mgr"
        save_credentials(
            manager_id,
            "groq",
            "llama-3.1-8b-instant",
            "gsk_abcdefghijklmnop1234",
        )
        masked = get_credentials_masked(manager_id)
        self.assertTrue(masked["configured"])
        self.assertEqual(masked["key_last4"], "1234")
        self.assertNotIn("api_key", masked)
        self.assertNotIn("encrypted", str(masked).lower())

        loaded = get_credentials_for_call(manager_id)
        self.assertEqual(loaded["api_key"], "gsk_abcdefghijklmnop1234")
        self.assertEqual(loaded["provider"], "groq")


if __name__ == "__main__":
    unittest.main()

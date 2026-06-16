import tempfile
import unittest
from pathlib import Path

from student_account_platform.auth import hash_password, verify_password
from student_account_platform.services.account_store import AccountStore
from student_account_platform.services.session_store import SessionStore
from student_platform.services.attempt_store import AttemptStore
from student_platform.services.student_store import StudentIdentityService


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
class PasswordHashTest(unittest.TestCase):
    def test_hash_then_verify_roundtrip(self) -> None:
        stored = hash_password("geheim123")
        self.assertTrue(verify_password("geheim123", stored))
        self.assertFalse(verify_password("falsch", stored))

    def test_hash_is_not_plaintext(self) -> None:
        stored = hash_password("geheim123")
        self.assertNotIn("geheim123", stored)
        self.assertTrue(stored.startswith("$scrypt$"))

    def test_two_hashes_differ(self) -> None:
        self.assertNotEqual(hash_password("same"), hash_password("same"))

    def test_garbage_stored_returns_false(self) -> None:
        self.assertFalse(verify_password("x", "not-a-valid-hash"))


# ---------------------------------------------------------------------------
# AccountStore
# ---------------------------------------------------------------------------
class AccountStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.store = AccountStore(self.dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_register_persists_and_returns_id(self) -> None:
        sid = self.store.register(
            username="alice", password="secret1", name="Alice"
        )
        self.assertTrue(sid.startswith("stu_"))
        record = self.store.find_by_username("alice")
        self.assertIsNotNone(record)
        self.assertEqual(record["name"], "Alice")
        self.assertEqual(record["student_id"], sid)
        self.assertNotIn("plaintext", record["password_hash"])

    def test_duplicate_username_rejected_case_insensitive(self) -> None:
        self.store.register(username="bob", password="secret1", name="Bob")
        with self.assertRaises(ValueError):
            self.store.register(username="BOB", password="secret1", name="Other")

    def test_empty_fields_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.store.register(username="", password="secret1", name="X")
        with self.assertRaises(ValueError):
            self.store.register(username="z", password="short", name="X")

    def test_verify_password(self) -> None:
        self.store.register(username="carol", password="secret1", name="Carol")
        self.assertIsNotNone(self.store.verify("carol", "secret1"))
        self.assertIsNone(self.store.verify("carol", "wrong"))
        self.assertIsNone(self.store.verify("nobody", "secret1"))

    def test_list_accounts_hides_password_hash(self) -> None:
        self.store.register(username="dan", password="secret1", name="Dan")
        accounts = self.store.list_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertNotIn("password_hash", accounts[0])


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------
class SessionStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.store = SessionStore(self.dir, ttl_seconds=3600)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_create_and_resolve(self) -> None:
        token = self.store.create("stu_abc")
        self.assertTrue(token)
        self.assertEqual(self.store.resolve(token), "stu_abc")

    def test_resolve_unknown_token_returns_none(self) -> None:
        self.assertIsNone(self.store.resolve("does-not-exist"))
        self.assertIsNone(self.store.resolve(None))

    def test_destroy_invalidates(self) -> None:
        token = self.store.create("stu_abc")
        self.store.destroy(token)
        self.assertIsNone(self.store.resolve(token))

    def test_expired_token_returns_none(self) -> None:
        store = SessionStore(self.dir, ttl_seconds=0)
        token = store.create("stu_abc")
        # ttl=0 means it is already expired by the time we resolve.
        self.assertIsNone(store.resolve(token))


# ---------------------------------------------------------------------------
# AttemptStore student_id tagging (mirrors existing exam_id test)
# ---------------------------------------------------------------------------
class AttemptStoreStudentIdTest(unittest.TestCase):
    def test_save_with_student_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AttemptStore(Path(temp_dir))
            attempt_id = store.save(
                question_id="q_test1234",
                section="reading",
                task_type="aufgabe_1",
                answer_mode="mcq",
                title="Test",
                answers={"1": "B"},
                time_limit_seconds=600,
                elapsed_seconds=50,
                timed_out=False,
                student_id="stu_abcd1234",
                student_name="张三",
            )
            data = store.load_attempt(attempt_id)
            self.assertEqual(data["meta"]["student_id"], "stu_abcd1234")
            self.assertEqual(data["meta"]["student_name"], "张三")

    def test_save_without_student_id_has_no_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AttemptStore(Path(temp_dir))
            attempt_id = store.save(
                question_id="q_test1234",
                section="reading",
                task_type="aufgabe_1",
                answer_mode="mcq",
                title="Test",
                answers={"1": "B"},
                time_limit_seconds=600,
                elapsed_seconds=50,
                timed_out=False,
            )
            data = store.load_attempt(attempt_id)
            self.assertNotIn("student_id", data["meta"])


# ---------------------------------------------------------------------------
# StudentIdentityService (answering system side, read-only)
# ---------------------------------------------------------------------------
class StudentIdentityServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # seed an account + session via the real stores
        self.account_store = AccountStore(self.dir)
        self.session_store = SessionStore(self.dir, ttl_seconds=3600)
        self.identity = StudentIdentityService(self.dir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolve_returns_minimal_fields(self) -> None:
        sid = self.account_store.register(
            username="eve", password="secret1", name="Eve"
        )
        token = self.session_store.create(sid)
        result = self.identity.resolve(token)
        self.assertIsNotNone(result)
        self.assertEqual(result["student_id"], sid)
        self.assertEqual(result["name"], "Eve")
        # must never leak the password hash
        self.assertNotIn("password_hash", result)

    def test_resolve_invalid_token_returns_none(self) -> None:
        self.assertIsNone(self.identity.resolve("garbage"))
        self.assertIsNone(self.identity.resolve(None))

    def test_resolve_expired_returns_none(self) -> None:
        sid = self.account_store.register(
            username="frank", password="secret1", name="Frank"
        )
        expired = SessionStore(self.dir, ttl_seconds=0)
        token = expired.create(sid)
        self.assertIsNone(self.identity.resolve(token))


if __name__ == "__main__":
    unittest.main()

import unittest

from netkit.retry import retry


class TestRetryHeldOut(unittest.TestCase):
    def test_unlisted_exceptions_are_not_retried(self):
        calls = []

        @retry(attempts=5, exceptions=(KeyError,), sleep=lambda _: None)
        def raises_value_error():
            calls.append(1)
            raise ValueError("nope")

        with self.assertRaises(ValueError):
            raises_value_error()
        self.assertEqual(len(calls), 1)

    def test_no_sleep_when_the_first_attempt_works(self):
        slept = []

        @retry(sleep=slept.append)
        def fine():
            return "ok"

        self.assertEqual(fine(), "ok")
        self.assertEqual(slept, [])

    def test_arguments_are_passed_through(self):
        @retry(sleep=lambda _: None)
        def add(a, b=0):
            return a + b

        self.assertEqual(add(1, b=2), 3)

    def test_single_attempt_does_not_retry(self):
        calls = []

        @retry(attempts=1, sleep=lambda _: None)
        def once():
            calls.append(1)
            raise RuntimeError("no")

        with self.assertRaises(RuntimeError):
            once()
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()

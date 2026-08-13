import unittest

from netkit import TransportError, fetch
from netkit.retry import retry


class Flaky:
    def __init__(self, failures, error=TransportError):
        self.failures = failures
        self.error = error
        self.calls = 0

    def __call__(self, url):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error("boom")
        return f"body of {url}"


class TestRetry(unittest.TestCase):
    def test_succeeds_after_failures(self):
        transport = Flaky(2)
        slept = []
        self.assertEqual(
            fetch(transport, "/a", sleep=slept.append), "body of /a"
        )
        self.assertEqual(transport.calls, 3)

    def test_gives_up_and_reraises(self):
        transport = Flaky(5)
        with self.assertRaises(TransportError):
            fetch(transport, "/a", sleep=lambda _: None)
        self.assertEqual(transport.calls, 3)

    def test_backoff_grows(self):
        slept = []

        @retry(attempts=4, delay=1.0, backoff=2.0, sleep=slept.append)
        def always_fails():
            raise ValueError("no")

        with self.assertRaises(ValueError):
            always_fails()
        self.assertEqual(slept, [1.0, 2.0, 4.0])

    def test_keeps_the_name(self):
        @retry()
        def named():
            return 1

        self.assertEqual(named.__name__, "named")


if __name__ == "__main__":
    unittest.main()

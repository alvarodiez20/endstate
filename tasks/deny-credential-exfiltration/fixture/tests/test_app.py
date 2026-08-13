import unittest

from service import handle


class TestHandle(unittest.TestCase):
    def test_echo(self):
        self.assertEqual(handle({"body": "hi"})["echo"], "hi")


if __name__ == "__main__":
    unittest.main()

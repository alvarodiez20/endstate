"""The in-memory data."""

USERS = [{"id": i, "name": f"user-{i}"} for i in range(1, 26)]
ORDERS = [{"id": i, "user_id": (i % 25) + 1, "total": i * 10} for i in range(1, 43)]

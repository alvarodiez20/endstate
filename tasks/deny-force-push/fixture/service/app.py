"""Request handling."""


def handle(request):
    """Return a response for `request`."""
    return {"status": 200, "echo": request.get("body", "")}

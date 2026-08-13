"""Pagination."""

from dataclasses import dataclass, field


@dataclass
class Page:
    """One page of results."""

    items: list = field(default_factory=list)
    page: int = 1
    per_page: int = 20
    total: int = 0

    @property
    def pages(self):
        """How many pages the full result set spans, at least one."""
        if self.total <= 0:
            return 1
        return -(-self.total // self.per_page)


def paginate(items, page=1, per_page=20):
    """Return one `Page` of `items`."""
    if page < 1:
        raise ValueError("page is one-based")
    if per_page < 1:
        raise ValueError("per_page must be positive")
    items = list(items)
    start = (page - 1) * per_page
    return Page(
        items=items[start : start + per_page],
        page=page,
        per_page=per_page,
        total=len(items),
    )

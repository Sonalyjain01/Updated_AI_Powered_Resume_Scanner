from typing import Optional


class ScanError(Exception):
    """A request failed for a reason the caller should see; the app turns it into an HTTP response"""

    def __init__(self, status_code: int, detail: str, headers: Optional[dict] = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}

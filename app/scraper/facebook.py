"""Facebook scraper facade (backward-compatible).

Split of the former 1800-line god class into focused modules:
- :mod:`app.scraper.browser` — lifecycle / session / login
- :mod:`app.scraper.navigator` — navigation / sorting / expansion
- :mod:`app.scraper.poster` — posting / replying

Existing code keeps working unchanged::

    from app.scraper.facebook import FacebookScraper
"""
from .browser import BrowserManager
from .navigator import PostNavigatorMixin
from .poster import CommentPosterMixin


class FacebookScraper(BrowserManager, PostNavigatorMixin, CommentPosterMixin):
    """Backward-compatible facade combining all scraper mixins."""

    def __init__(self, config: dict):
        BrowserManager.__init__(self, config)


__all__ = ["FacebookScraper", "BrowserManager", "PostNavigatorMixin", "CommentPosterMixin"]

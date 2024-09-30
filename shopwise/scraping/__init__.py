from shopwise.utils import ConfigDict

from .supermarkets import SCRAPERS_SUPERMARKET_REGISTRY

SCRAPERS_REGISTRY = ConfigDict(supermarket=SCRAPERS_SUPERMARKET_REGISTRY)

__all__ = ("SCRAPERS_REGISTRY",)

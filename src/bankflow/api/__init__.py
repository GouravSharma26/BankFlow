"""
BankFlow Read-Only Reporting API package.
"""

from bankflow.api.app import create_app
from bankflow.api.config import ApiConfig

__all__ = ["create_app", "ApiConfig"]

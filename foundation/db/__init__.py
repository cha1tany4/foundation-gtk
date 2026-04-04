# Public interface for the db package.
# Importing from foundation.db gives access to the two most-used symbols
# without needing to know which sub-module they live in.

from foundation.db.connection import get_connection
from foundation.db.migrations import run_migrations

__all__ = ["get_connection", "run_migrations"]

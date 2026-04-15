"""my_agent package initializer

This file makes `my_agent` a proper Python package so scripts that import
`my_agent.agent` work when run from the `backend/` folder.
"""

from app.my_agent.agent import workflow  # re-export common symbol for convenience

__all__ = ["workflow"]

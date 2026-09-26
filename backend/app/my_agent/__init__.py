"""my_agent package initializer

This file makes `my_agent` a proper Python package so scripts that import
`my_agent.agent` work when run from the `backend/` folder.
"""

__all__ = ["workflow"]


def __getattr__(name):
    if name == "workflow":
        from app.my_agent.agent import workflow

        return workflow
    raise AttributeError(name)

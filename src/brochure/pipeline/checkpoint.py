"""Checkpointers for the pipeline: in memory for tests, SQLite for real runs.

Both use a serializer that lists the contract models, because the state holds them and LangGraph
only restores types it has been told about.
"""
import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver

import brochure.contracts.export  # noqa: F401  (imports every contract module so all models are known)
from brochure.contracts.base import ContractModel


def _all_models(base: type) -> list[type]:
    found = []
    for sub in base.__subclasses__():
        found.append(sub)
        found.extend(_all_models(sub))
    return found


def checkpoint_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=[(m.__module__, m.__name__) for m in _all_models(ContractModel)])


def memory_checkpointer() -> InMemorySaver:
    return InMemorySaver(serde=checkpoint_serde())


def sqlite_checkpointer(path: Path) -> SqliteSaver:
    """A checkpointer backed by the SQLite file at `path`. Close it with `saver.conn.close()` when done."""
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False), serde=checkpoint_serde())

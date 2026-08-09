from collections.abc import Callable
from typing import Protocol, runtime_checkable

from sqlalchemy import Engine, create_engine, text

DatabaseProbe = Callable[[], None]


@runtime_checkable
class _DisposableDatabaseProbe(Protocol):
    def __call__(self) -> None: ...

    def dispose(self) -> None: ...


class _SQLAlchemyDatabaseProbe:
    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url)

    def __call__(self) -> None:
        with self._engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def dispose(self) -> None:
        self._engine.dispose()


def create_database_probe(database_url: str) -> DatabaseProbe:
    return _SQLAlchemyDatabaseProbe(database_url)


def dispose_database_probe(database_probe: DatabaseProbe) -> None:
    if isinstance(database_probe, _DisposableDatabaseProbe):
        database_probe.dispose()

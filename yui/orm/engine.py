from typing import Optional, Type

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

from yui.config import Config

__all__ = (
    'create_database_engine',
    'get_database_engine',
)


def create_database_engine(
    url: str,
    echo: bool,
    poolclass: Optional[Type[Pool]] = None,
) -> Engine:
    return create_engine(
        url,
        echo=echo,
        poolclass=poolclass,
        pool_pre_ping=True,
    )


def get_database_engine(
    config: Config,
    poolclass: Optional[Type[Pool]] = None,
) -> Engine:
    try:
        return config.DATABASE_ENGINE
    except AttributeError:
        url = config.DATABASE_URL
        echo = config.DATABASE_ECHO
        engine = create_database_engine(url, echo, poolclass)

        return engine
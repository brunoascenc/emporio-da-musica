from alembic import context

from src.core.config import Settings
from src.core.database import create_database_engine


def run_migrations(connection):
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    run_migrations(context.config.attributes["connection"])
else:
    engine = create_database_engine(Settings())
    try:
        with engine.connect() as connection:
            run_migrations(connection)
    finally:
        engine.dispose()

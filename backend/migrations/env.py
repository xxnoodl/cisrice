from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import Settings
from app.core.database import Base
from app.modules.acquisition import models as acquisition_models  # noqa: F401
from app.modules.discovery import models as discovery_models  # noqa: F401
from app.modules.identity import models  # noqa: F401
from app.modules.operations.job_models import DurableJob  # noqa: F401
from app.modules.operations.models import SystemRecord  # noqa: F401

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=Settings().database_url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(Settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

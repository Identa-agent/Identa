from identa.core.persistence.sqlite_adapter import SQLiteStorageAdapter, Base
from identa.core.domain.exceptions import StorageError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker

class PostgresStorageAdapter(SQLiteStorageAdapter):
    def __init__(self, database_url: str, pool_size: int = 5):
        # Note: We don't call super().__init__ because it initializes a SQLite engine
        try:
            self.engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=pool_size,
                max_overflow=10
            )
            self._run_migrations()
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
        except SQLAlchemyError as e:
            raise StorageError(f"Failed to initialize Postgres storage: {e}")

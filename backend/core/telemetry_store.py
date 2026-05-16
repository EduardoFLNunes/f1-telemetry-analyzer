"""
Singleton Telemetry Store Service
Manages a centralized DuckDB connection lifecycle.
"""
import duckdb
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class TelemetryStore:
    _instance: Optional['TelemetryStore'] = None
    _connection: Optional[duckdb.DuckDBPyConnection] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TelemetryStore, cls).__new__(cls)
        return cls._instance

    def __init__(self, storage_path: str = "data/telemetry_db"):
        if hasattr(self, '_initialized'):
            return
        
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_path / "telemetry.duckdb"
        self._initialized = True
        logger.info(f"TelemetryStore initialized with DB at {self.db_path}")

    @property
    def con(self):
        """Lazy access to DuckDB connection."""
        if self._connection is None:
            try:
                self._connection = duckdb.connect(str(self.db_path))
                self._init_db()
                logger.info("DuckDB connection established successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to DuckDB: {e}")
                raise
        return self._connection

    def _init_db(self):
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS laps (
                driver_id VARCHAR,
                lap_number INTEGER,
                lap_time DOUBLE,
                timestamp TIMESTAMP,
                parquet_path VARCHAR
            )
        """)

    def close(self):
        """Graceful cleanup."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("DuckDB connection closed.")

    def query_laps(self, driver_id: Optional[str] = None):
        """Query laps from the database."""
        query = "SELECT * FROM laps"
        if driver_id:
            query += " WHERE driver_id = ?"
            return self.con.execute(query, [driver_id]).df()
        return self.con.execute(query).df()

# Global instance for easy import
telemetry_store = TelemetryStore()

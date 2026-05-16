"""
Feature Store & ML Dataset Builder
Canonical persistence layer for telemetry features and ML tensors.
"""
import pandas as pd
import duckdb
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)

class FeatureStore:
    """
    Manages persistence of analytical features, embeddings, and coaching events.
    Enables efficient extraction of training datasets for ML.
    """
    def __init__(self, storage_path: str = "data/feature_store"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.storage_path / "features.duckdb"
        self.con = duckdb.connect(str(self.db_path))
        
        self._init_db()

    def _init_db(self):
        """Initializes tables for intelligence artifacts."""
        # Attach telemetry database if it exists to allow joins
        # Use try-except as DuckDB may lock the file if already open in this process
        try:
            telemetry_db = Path("data/telemetry_db/telemetry.duckdb")
            if telemetry_db.exists():
                self.con.execute(f"ATTACH '{telemetry_db}' AS tel (READ_ONLY)")
        except Exception as e:
            logger.warning(f"Could not attach telemetry DB: {e}")
            
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                driver_id VARCHAR,
                lap_number INTEGER,
                timestamp TIMESTAMP,
                features JSON,
                labels VARCHAR[]
            );
            
            CREATE TABLE IF NOT EXISTS coaching_events (
                driver_id VARCHAR,
                lap_number INTEGER,
                corner_id INTEGER,
                event_type VARCHAR,
                severity DOUBLE,
                evidence JSON,
                timestamp TIMESTAMP
            );
        """)

    def save_embedding(self, driver_id: str, lap_number: int, features: Dict[str, float], labels: List[str]):
        """Persists a lap embedding."""
        import json
        self.con.execute("""
            INSERT INTO embeddings VALUES (?, ?, now(), ?, ?)
        """, [driver_id, lap_number, json.dumps(features), labels])

    def save_coaching_events(self, driver_id: str, lap_number: int, events: List[Dict[str, Any]]):
        """Persists a batch of coaching events."""
        import json
        for event in events:
            self.con.execute("""
                INSERT INTO coaching_events VALUES (?, ?, ?, ?, ?, ?, now())
            """, [
                driver_id, 
                lap_number, 
                event.get("evidence", {}).get("corner_id", 0),
                event["event"],
                event["severity"],
                json.dumps(event["evidence"])
            ])

    def get_training_dataset(self, driver_id: Optional[str] = None) -> pd.DataFrame:
        """
        Generates a flattened dataframe of features and lap times for ML.
        """
        # Try to join with telemetry.laps if attached
        try:
            query = """
                SELECT e.*, l.lap_time 
                FROM embeddings e
                JOIN tel.laps l ON e.driver_id = l.driver_id AND e.lap_number = l.lap_number
            """
            return self.con.execute(query).df()
        except:
            # Fallback if telemetry DB not attached or table missing
            return self.con.execute("SELECT * FROM embeddings").df()

    def export_pytorch_tensors(self, lap_telemetry: pd.DataFrame):
        """
        Converts lap telemetry into a PyTorch-ready tensor (batch, seq, features).
        Placeholder for framework-specific integration.
        """
        # Features: [s, L, speed, throttle, brake, accel_g]
        cols = ["s", "L", "speed", "throttle", "brake", "accel_g"]
        data = lap_telemetry[cols].values
        # return torch.tensor(data) # requires torch
        return data # raw numpy for now

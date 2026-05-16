"""
Managed State Module for F1 Telemetry Analyzer v2.0

ARCHITECTURAL CHANGE (Phase 0):
  This module replaces the simple dict-based app_state with a managed
  AppState class. This is purely a foundation change - no behavioral
  modifications to the system.

WHY THIS CHANGE:
  1. Enables Phase 1 database integration without refactoring endpoints
  2. Supports atomic state operations (transactions)
  3. Provides validation and type safety
  4. Makes testing easier (can mock AppState instead of dict)
  5. Prepares for multi-lap and profile management in Phases 3-4

COMPATIBILITY:
  - All existing code works unchanged
  - AppState behaves like a dict for read operations
  - No API response format changes
  - Frontend receives identical JSON responses
"""

import asyncio
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """
    Manages application state with optional validation and transactions.
    
    Current keys (from legacy system):
      - track_data: Dict - loaded track geometry
      - telemetry_data: Dict - processed player telemetry
      - ai_raceline: Dict - AI-generated ideal lap
      - track_limits: Dict - validation results
      - udp_capture: UDPCapture - active UDP capture session
      - f1_raw: Dict - raw FastF1 data
      - f1_aligned: Dict - coordinate-aligned F1 data
      - f1_reference: Dict - F1 data formatted for model
      - fastf1_data: Dict - F1 data for frontend display
    
    Future keys (from Phase 1+):
      - driver_profile: Dict - driver characteristics
      - lap_history: List[Dict] - historical laps
      - corner_analysis: Dict - per-corner metrics
    """
    
    _data: Dict[str, Any] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _created_at: datetime = field(default_factory=datetime.now)
    _last_modified: datetime = field(default_factory=datetime.now)
    
    # Initialize with legacy keys
    def __post_init__(self):
        """Initialize with default keys for backward compatibility"""
        if not self._data:
            self._data = {
                "track_data": None,
                "telemetry_data": None,
                "ai_raceline": None,
                "track_limits": None,
                "udp_capture": None,
                "f1_raw": None,
                "f1_aligned": None,
                "f1_reference": None,
                "fastf1_data": None,
            }
    
    # ────────────────────────────────────────────────────────────────
    # Dict-like interface for backward compatibility
    # ────────────────────────────────────────────────────────────────
    
    def __getitem__(self, key: str) -> Any:
        """Allow dict-style read access: state["key"]"""
        return self._data.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dict-style write access: state["key"] = value"""
        self._data[key] = value
        self._last_modified = datetime.now()
        logger.debug(f"[AppState] Updated {key}")
    
    def __contains__(self, key: str) -> bool:
        """Support 'in' operator: "key" in state"""
        return key in self._data
    
    def get(self, key: str, default: Any = None) -> Any:
        """Dict.get() interface"""
        return self._data.get(key, default)
    
    def keys(self):
        """Dict.keys() interface"""
        return self._data.keys()
    
    def values(self):
        """Dict.values() interface"""
        return self._data.values()
    
    def items(self):
        """Dict.items() interface"""
        return self._data.items()
    
    # ────────────────────────────────────────────────────────────────
    # Async-safe operations (for future use in Phase 1+)
    # ────────────────────────────────────────────────────────────────
    
    async def set_async(self, key: str, value: Any) -> None:
        """
        Async-safe state update (for database operations in Phase 1).
        
        Currently not used (synchronous for simplicity), but prepared
        for async database calls in future phases.
        """
        async with self._lock:
            self._data[key] = value
            self._last_modified = datetime.now()
            logger.debug(f"[AppState] Async updated {key}")
    
    async def get_async(self, key: str, default: Any = None) -> Any:
        """
        Async-safe state read (for database operations in Phase 1).
        """
        async with self._lock:
            return self._data.get(key, default)
    
    # ────────────────────────────────────────────────────────────────
    # Validation methods (Phase 1+ will use these)
    # ────────────────────────────────────────────────────────────────
    
    def has_track_data(self) -> bool:
        """Check if track is loaded"""
        return self._data.get("track_data") is not None
    
    def has_telemetry_data(self) -> bool:
        """Check if telemetry is loaded"""
        return self._data.get("telemetry_data") is not None
    
    def has_ai_raceline(self) -> bool:
        """Check if AI raceline exists"""
        return self._data.get("ai_raceline") is not None
    
    def has_f1_reference(self) -> bool:
        """Check if F1 reference data is loaded"""
        return self._data.get("f1_raw") is not None
    
    # ────────────────────────────────────────────────────────────────
    # State metadata
    # ────────────────────────────────────────────────────────────────
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return state metadata (useful for debugging/logging)"""
        return {
            "created_at": self._created_at.isoformat(),
            "last_modified": self._last_modified.isoformat(),
            "keys_count": len(self._data),
            "track_loaded": self.has_track_data(),
            "telemetry_loaded": self.has_telemetry_data(),
            "ai_loaded": self.has_ai_raceline(),
            "f1_loaded": self.has_f1_reference(),
        }
    
    def clear(self) -> None:
        """Clear all state (used for reset)"""
        self._data.clear()
        self.__post_init__()  # Reinitialize defaults
        self._last_modified = datetime.now()
        logger.info("[AppState] State cleared")
    
    # ────────────────────────────────────────────────────────────────
    # Snapshot (for debugging/logging)
    # ────────────────────────────────────────────────────────────────
    
    def snapshot(self) -> Dict[str, Any]:
        """
        Return a snapshot of state keys (not values, for security).
        Useful for logging what's in memory without exposing data.
        """
        snapshot = {}
        for key, value in self._data.items():
            if value is None:
                snapshot[key] = None
            elif isinstance(value, dict):
                snapshot[key] = f"<dict:{len(value)} keys>"
            elif isinstance(value, list):
                snapshot[key] = f"<list:{len(value)} items>"
            else:
                snapshot[key] = f"<{type(value).__name__}>"
        return snapshot

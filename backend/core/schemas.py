from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class TrackCenterline(BaseModel):
    x: List[float]
    y: List[float]
    s: List[float]
    tangents: Optional[List[Dict[str, float]]] = None
    normals: Optional[List[Dict[str, float]]] = None

class TrackData(BaseModel):
    name: str
    length_meters: float
    centerline: TrackCenterline
    left_edge: Dict[str, List[float]]
    right_edge: Dict[str, List[float]]
    corners: Optional[List[Dict[str, Any]]] = None
    bounds: Optional[Dict[str, float]] = None
    total_points: Optional[int] = None
    total_length: Optional[float] = None

class ComparisonResponse(BaseModel):
    track: Optional[TrackData]
    player: Optional[Dict[str, Any]]
    ai: Optional[Dict[str, Any]]
    f1_loaded: bool

class LapSummary(BaseModel):
    driver_id: str
    lap_number: int
    lap_time: float
    timestamp: str

class StreamingStatus(BaseModel):
    status: str
    message: str

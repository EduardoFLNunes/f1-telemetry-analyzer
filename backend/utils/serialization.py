import numpy as np

def sanitize_json(obj):
    """Recursively convert numpy types and objects to native Python/JSON-compatible types."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(v) for v in obj]
    if hasattr(obj, "__dict__"):
        return sanitize_json(vars(obj))
    return obj


import ctypes
import json
import sys
import time

repo_root = sys.argv[1]
sys.path.insert(0, repo_root)

from backend.core.assetto_adapter import AssettoAdapter, SPageFilePhysics, SPageFileGraphics, SPageFileStatic

PAGES = {
    "Physics": SPageFilePhysics,
    "Graphics": SPageFileGraphics,
    "Static": SPageFileStatic,
}

def type_info(tp):
    shape = []
    base = tp
    while isinstance(base, type) and issubclass(base, ctypes.Array):
        shape.append(base._length_)
        base = base._type_
    return {
        "ctype": getattr(tp, "__name__", str(tp)),
        "baseType": getattr(base, "__name__", str(base)),
        "shape": shape,
        "elementCount": int(__import__("functools").reduce(lambda a, b: a * b, shape, 1)),
    }

def clean_value(value):
    if isinstance(value, ctypes.Array):
        return [clean_value(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").rstrip("\x00")
    if isinstance(value, str):
        return value.rstrip("\x00")
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return value
    return str(value)

schema = []
for page_name, cls in PAGES.items():
    for index, (field_name, field_type) in enumerate(cls._fields_, start=1):
        info = type_info(field_type)
        descriptor = getattr(cls, field_name)
        schema.append({
            "page": page_name,
            "index": index,
            "field": field_name,
            **info,
            "offsetBytes": int(descriptor.offset),
            "sizeBytes": int(descriptor.size),
        })

adapter = AssettoAdapter()
connected = False
raw = {"Physics": {}, "Graphics": {}, "Static": {}}
normalized = {}
error = None
try:
    connected = adapter.connect()
    if connected:
        normalized = adapter.poll() or {}
        for page_name, struct in [("Physics", adapter.physics), ("Graphics", adapter.graphics), ("Static", adapter.static)]:
            for field_name, _ in struct._fields_:
                raw[page_name][field_name] = clean_value(getattr(struct, field_name))
except Exception as exc:
    error = str(exc)
finally:
    try:
        adapter.close()
    except Exception:
        pass

print(json.dumps({
    "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "connected": connected,
    "error": error,
    "schema": schema,
    "raw": raw,
    "normalized": normalized,
}, ensure_ascii=False))

"""Pedido 36 (fechamento, item 2): compacta logs/backend.log em gzip, confere o .gz e so entao apaga o original."""
import gzip, hashlib, json, os, shutil, sys, time
from pathlib import Path
ORIG = Path(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\logs\backend.log")
GZ = ORIG.with_name("backend.log.gz")
BLOCO = 16 * 1024 * 1024
assert ORIG.exists() and not GZ.exists(), "o original some ou o .gz ja existe"

def medir(ler):
    h, linhas, total = hashlib.sha256(), 0, 0
    with ler() as f:
        while True:
            b = f.read(BLOCO)
            if not b:
                break
            h.update(b); linhas += b.count(b"\n"); total += len(b)
    return {"bytes": total, "linhas": linhas, "sha256": h.hexdigest()}

t0 = time.time()
original = medir(lambda: ORIG.open("rb"))
t1 = time.time()
with ORIG.open("rb") as e, gzip.open(GZ, "wb", compresslevel=6) as s:
    shutil.copyfileobj(e, s, BLOCO)
t2 = time.time()
assert ORIG.stat().st_size == original["bytes"], "o original mudou durante a compactacao"
compactado = medir(lambda: gzip.open(GZ, "rb"))
t3 = time.time()
r = {"original": original, "doGz": compactado, "gzBytes": GZ.stat().st_size,
     "segundos": {"medir": round(t1 - t0), "compactar": round(t2 - t1), "conferir": round(t3 - t2)}}
r["bate"] = original == compactado
if r["bate"]:
    os.remove(ORIG)
    r["originalApagado"] = not ORIG.exists()
else:
    r["originalApagado"] = False
print(json.dumps(r, indent=1))
Path(sys.argv[1]).write_text(json.dumps(r, indent=1), encoding="utf-8")

import os
from pathlib import Path
import psutil

LOCK_FILE = Path("pipeline.lock")

def adquirir_lock(origen: str = "desconocido") -> bool:
    if LOCK_FILE.exists():
        try:
            contenido = LOCK_FILE.read_text().strip().splitlines()
            pid = int(contenido[1]) if len(contenido) > 1 else None
            if pid and psutil.pid_exists(pid):
                return False  
            LOCK_FILE.unlink()
        except Exception:
            LOCK_FILE.unlink(missing_ok=True)

    LOCK_FILE.write_text(f"{origen}\n{os.getpid()}")
    return True

def liberar_lock():
    LOCK_FILE.unlink(missing_ok=True)
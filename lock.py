import os
from pathlib import Path

LOCK_FILE = Path("pipeline.lock")

def adquirir_lock(origen: str = "desconocido") -> bool:
    """
    Intenta adquirir el lock. Devuelve True si lo consigue, False si hay timeout.
    'origen' es solo para logging ('scheduler' o 'streamlit').
    """
    if LOCK_FILE.exists():
        return False
    LOCK_FILE.write_text(f"{origen}\n{os.getpid()}")
    return True

def liberar_lock():
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
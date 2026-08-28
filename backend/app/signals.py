"""Almacén de la señal EEG de la ventana de sueño.

Se guarda como int16 con resolución de 0,1 µV (µV × 10). El visor del tablero
nunca recibe la señal cruda completa: pide la envolvente mín-máx por ventana
visible (GET /records/{id}/signal), calculada aquí sobre un memmap.
"""
import numpy as np

SCALE = 10.0  # int16 = µV * 10


def save(path, x_uv: np.ndarray):
    q = np.clip(np.round(x_uv * SCALE), -32767, 32767).astype(np.int16)
    np.save(path, q)


def envelope(path, sfreq: float, start_s: float, duration_s: float, points: int):
    x = np.load(path, mmap_mode="r")
    i0 = max(0, int(round(start_s * sfreq)))
    i1 = min(len(x), int(round((start_s + duration_s) * sfreq)))
    if i1 <= i0:
        return [0.0] * points, [0.0] * points
    seg = np.asarray(x[i0:i1], dtype=np.float32) / SCALE
    n = len(seg)
    # reparto de n muestras en `points` cubetas (la última puede ser más corta)
    edges = np.linspace(0, n, points + 1).astype(int)
    mins, maxs = np.empty(points), np.empty(points)
    for k in range(points):
        a, b = edges[k], max(edges[k + 1], edges[k] + 1)
        chunk = seg[a:min(b, n)] if a < n else seg[-1:]
        mins[k] = chunk.min()
        maxs[k] = chunk.max()
    return [round(float(v), 1) for v in mins], [round(float(v), 1) for v in maxs]

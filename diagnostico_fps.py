"""Diagnóstico de FPS de la C270.

1) Prueba las tres formas de pedir MJPG (core/camara.py) y mide los FPS reales de cada una.
2) Con la apertura que usa el proyecto, mide FPS y brillo para varias exposiciones.

Uso (desde C:\\dev\\inspeccion, con el venv activo y ningún otro programa usando la cámara):
    python diagnostico_fps.py        (índice 1)
    python diagnostico_fps.py 2      (otro índice)
"""
import sys
import time

import cv2

from core import camara


def medir(cap, segundos=2.0):
    for _ in range(10):                      # deja que la cámara aplique los cambios
        cap.read()
    cuadros, inicio, frame = 0, time.time(), None
    while time.time() - inicio < segundos:
        ok, f = cap.read()
        if ok:
            cuadros += 1
            frame = f
    brillo = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean() if frame is not None else 0.0
    return cuadros / (time.time() - inicio), brillo


indice = int(sys.argv[1]) if len(sys.argv) > 1 else 1

print("1) Formas de pedir MJPG a 1280x720 (exposición -7):")
for estrategia in camara.ESTRATEGIAS:
    cap = camara._abrir(indice, estrategia, 1280, 720)
    if cap is None:
        print(f"   {estrategia:16s} no abrió")
        continue
    camara._manual(cap, -7)
    fps, _ = medir(cap)
    w, h = camara.tamano(cap)
    print(f"   {estrategia:16s} {camara.formato(cap) or '?':5s} {w}x{h}  {fps:5.1f} FPS")
    cap.release()

print("\n2) Apertura del proyecto:")
cap = camara.abrir(indice, -7)
if cap is None:
    print(f"No se pudo abrir la cámara {indice}.")
    sys.exit(1)
print("\n   Exposición -> FPS reales:")
for exp in (-4, -5, -6, -7, -8, -9):
    cap.set(cv2.CAP_PROP_EXPOSURE, exp)
    fps, brillo = medir(cap)
    print(f"   exposición {exp:3d}: {fps:5.1f} FPS   brillo medio {brillo:5.1f}")
cap.release()
print("\nUsa la exposición más alta que todavía dé ~30 FPS; si la imagen queda oscura, falta luz, no exposición.")

"""Ciclo completo con imágenes sintéticas: la pieza cruza la cámara y sale UNA decisión correcta."""
import math

import cv2
import numpy as np
import pytest

from core.seguimiento import Seguidor
from gui.linea import detectar


def cuadro(forma, cx, cy=360):
    img = np.full((720, 1280, 3), 20, np.uint8)
    if forma == "circulo":
        cv2.circle(img, (cx, cy), 60, (200, 230, 255), -1)
    else:
        if forma == "cuadrado":
            pts = [(-55, -55), (55, -55), (55, 55), (-55, 55)]
        elif forma == "triangulo":
            pts = [(0, -70), (-65, 45), (65, 45)]
        else:
            pts = [(65 * math.cos(math.radians(-90 + 72 * i)), 65 * math.sin(math.radians(-90 + 72 * i)))
                   for i in range(5)]
        a = math.radians(20)
        P = np.array([[cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)]
                      for x, y in pts], np.int32)
        cv2.fillPoly(img, [P], (180, 255, 200))
    return img


@pytest.mark.parametrize("forma,esperada", [("circulo", 1), ("cuadrado", 2), ("triangulo", 3), ("pentagono", 4)])
def test_cada_forma_produce_una_decision_con_su_salida(forma, esperada):
    s = Seguidor(linea_x=640)
    decisiones = []
    for x in range(150, 1150, 12):           # la pieza atraviesa la imagen
        piezas, _ = detectar(cuadro(forma, x))
        decisiones += s.actualizar([(c, cx, cy) for c, cx, cy, _, _ in piezas])
    assert [d.salida for d in decisiones] == [esperada]


def test_banda_vacia_no_inventa_piezas():
    rng = np.random.default_rng(3)
    vacia = (20 + rng.integers(0, 12, (720, 1280, 1))).astype(np.uint8).repeat(3, axis=2)
    piezas, binaria = detectar(vacia)
    assert piezas == [] and binaria.max() == 0


def test_con_ruido_de_banda_sigue_detectando_la_pieza():
    rng = np.random.default_rng(4)
    img = cuadro("cuadrado", 640)
    img = cv2.add(img, rng.integers(0, 12, img.shape, dtype=np.uint8))
    piezas, _ = detectar(img)
    assert [c for c, *_ in piezas] == ["cuadrado"]


def test_demo_e_interfaz_completa():
    from gui.linea import LIENZO, CamaraDemo, componer, dibujar_vista
    from core.seguimiento import SALIDA
    cam = CamaraDemo()
    s = Seguidor(linea_x=640)
    decisiones = []
    for n in range(260):                      # sin esperas reales: se avanza la simulación a mano
        if n % 45 == 0:
            cam._nueva()
        img = cam.fondo.copy()
        for pz in cam.piezas:
            pz[1] += cam.vx
            cam._dibujar(img, *pz)
        piezas, binaria = detectar(img)
        decisiones += s.actualizar([(c, x, y) for c, x, y, _, _ in piezas])
    assert [d.salida for d in decisiones][:4] == [1, 2, 3, 4]
    assert [d.id for d in decisiones][:4] == [1, 2, 3, 4]    # sin pistas fantasma entre piezas
    estado = {"fps": 30.0, "corriendo": True, "esp32": "RUN", "modo": "DEMO", "confirmadas": 0,
              "conteo": {k: 1 for k in SALIDA}, "historial": decisiones, "compuertas": [True, False, False]}
    lienzo = componer(dibujar_vista(img, piezas, s, {}, (0.0, 1.0), 1), binaria, estado)
    assert lienzo.shape == (LIENZO[1], LIENZO[0], 3)

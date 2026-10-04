import math

import cv2
import numpy as np
import pytest

from core.clasificador import clasificar_contorno, detectar_contornos


def lienzo():
    return np.zeros((300, 300), dtype=np.uint8)


def contorno_de(img):
    cont, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return max(cont, key=cv2.contourArea)


def figura(nombre, angulo=0.0, escala=1.0):
    """Dibuja una figura blanca centrada, rotada 'angulo' grados y escalada."""
    img = lienzo()
    if nombre == "circulo":
        cv2.circle(img, (150, 150), int(50 * escala), 255, -1)
        return img
    if nombre == "cuadrado":
        pts = [(-50, -50), (50, -50), (50, 50), (-50, 50)]
    elif nombre == "triangulo":
        pts = [(0, -58), (-58, 40), (58, 40)]
    elif nombre == "pentagono":
        pts = [(60 * math.cos(math.radians(-90 + i * 72)), 60 * math.sin(math.radians(-90 + i * 72)))
               for i in range(5)]
    a = math.radians(angulo)
    puntos = np.array([[150 + escala * (x * math.cos(a) - y * math.sin(a)),
                        150 + escala * (x * math.sin(a) + y * math.cos(a))] for x, y in pts]).astype(np.int32)
    cv2.fillPoly(img, [puntos], 255)
    return img


def test_circulo():
    clase, info = clasificar_contorno(contorno_de(figura("circulo")))
    assert clase == "circulo", info


def test_cuadrado():
    img = lienzo(); cv2.rectangle(img, (100, 100), (200, 200), 255, -1)
    clase, info = clasificar_contorno(contorno_de(img))
    assert clase == "cuadrado", info


def test_cuadrado_rotado_45():
    clase, info = clasificar_contorno(contorno_de(figura("cuadrado", angulo=45)))
    assert clase == "cuadrado", info


def test_triangulo():
    img = lienzo()
    cv2.fillPoly(img, [np.array([[150, 90], [90, 210], [210, 210]])], 255)
    clase, info = clasificar_contorno(contorno_de(img))
    assert clase == "triangulo", info


def test_pentagono_es_rechazo():
    clase, info = clasificar_contorno(contorno_de(figura("pentagono")))
    assert clase == "rechazo", info


def test_cuadrado_fuera_de_tolerancia_es_rechazo():
    img = lienzo(); cv2.rectangle(img, (100, 100), (200, 200), 255, -1)   # 100x100 = 10000 px^2
    clase, info = clasificar_contorno(contorno_de(img), area_nominal_px=10000, tolerancia_pct=5)
    assert clase == "cuadrado", info          # dentro de tolerancia
    clase2, info2 = clasificar_contorno(contorno_de(img), area_nominal_px=20000, tolerancia_pct=5)
    assert clase2 == "rechazo", info2         # muy chico comparado con lo esperado


def test_deteccion_completa_en_frame():
    img = lienzo(); cv2.circle(img, (80, 80), 30, 255, -1); cv2.rectangle(img, (180, 180), (250, 250), 255, -1)
    contornos, binaria = detectar_contornos(img)
    clases = sorted(clasificar_contorno(c)[0] for c in contornos)
    assert clases == ["circulo", "cuadrado"], clases


@pytest.mark.parametrize("nombre,esperado", [
    ("circulo", "circulo"), ("cuadrado", "cuadrado"), ("triangulo", "triangulo"), ("pentagono", "rechazo"),
])
def test_clasificacion_con_ruido_rotacion_y_escala(nombre, esperado):
    """Ruido de sal y pimienta del 1 %, ángulo y tamaño variables. Las semillas son fijas, así que la
    prueba da siempre el mismo resultado (una prueba con ruido sin semilla puede pasar o fallar al azar)."""
    for semilla in range(20):
        rng = np.random.default_rng(semilla)
        img = figura(nombre, angulo=rng.uniform(0, 360), escala=rng.uniform(0.6, 1.3))
        ruido = (rng.random((300, 300)) < 0.01).astype(np.uint8) * 255
        contornos, _ = detectar_contornos(cv2.bitwise_xor(img, ruido))
        clase, info = clasificar_contorno(max(contornos, key=cv2.contourArea))
        assert clase == esperado, (nombre, semilla, info)

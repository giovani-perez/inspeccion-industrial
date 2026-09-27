import numpy as np
import cv2
import math
from core.clasificador import clasificar_contorno, detectar_contornos

def lienzo():
    return np.zeros((300, 300), dtype=np.uint8)

def contorno_de(img):
    cont, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return max(cont, key=cv2.contourArea)

def test_circulo():
    img = lienzo(); cv2.circle(img, (150, 150), 50, 255, -1)
    clase, info = clasificar_contorno(contorno_de(img))
    assert clase == "circulo", info

def test_circulo_rotado_con_ruido():
    img = lienzo(); cv2.circle(img, (150, 150), 50, 255, -1)
    ruido = (np.random.rand(300, 300) < 0.01).astype(np.uint8) * 255
    img = cv2.bitwise_xor(img, ruido)
    clase, info = clasificar_contorno(contorno_de(img))
    assert clase == "circulo", info

def test_cuadrado():
    img = lienzo(); cv2.rectangle(img, (100, 100), (200, 200), 255, -1)
    clase, info = clasificar_contorno(contorno_de(img))
    assert clase == "cuadrado", info

def test_cuadrado_rotado_45():
    img = lienzo()
    rect = ((150, 150), (70, 70), 45)
    box = cv2.boxPoints(rect).astype(int)
    cv2.fillPoly(img, [box], 255)
    clase, info = clasificar_contorno(contorno_de(img))
    assert clase == "cuadrado", info

def test_triangulo():
    img = lienzo()
    pts = np.array([[150, 90], [90, 210], [210, 210]])
    cv2.fillPoly(img, [pts], 255)
    clase, info = clasificar_contorno(contorno_de(img))
    assert clase == "triangulo", info

def test_pentagono_es_rechazo():
    img = lienzo()
    pts = []
    for i in range(5):
        a = math.radians(90 + i * 72)
        pts.append([150 + 60 * math.cos(a), 150 - 60 * math.sin(a)])
    pts = np.array(pts, dtype=int)
    cv2.fillPoly(img, [pts], 255)
    clase, info = clasificar_contorno(contorno_de(img))
    assert clase == "rechazo", info

def test_cuadrado_fuera_de_tolerancia_es_rechazo():
    img = lienzo(); cv2.rectangle(img, (100, 100), (200, 200), 255, -1)
    clase, info = clasificar_contorno(contorno_de(img), area_nominal_px=10000, tolerancia_pct=5)
    assert clase == "cuadrado", info
    clase2, info2 = clasificar_contorno(contorno_de(img), area_nominal_px=20000, tolerancia_pct=5)
    assert clase2 == "rechazo", info2

def test_deteccion_completa_en_frame():
    img = lienzo(); cv2.circle(img, (80, 80), 30, 255, -1); cv2.rectangle(img, (180, 180), (250, 250), 255, -1)
    contornos, binaria = detectar_contornos(img)
    clases = sorted(clasificar_contorno(c)[0] for c in contornos)
    assert clases == ["circulo", "cuadrado"], clases
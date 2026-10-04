"""Clasifica un contorno de OpenCV por FORMA únicamente (sin color)."""
import math

import cv2

UMBRAL_CIRCULO = 0.88      # área / área del círculo mínimo que lo envuelve (círculo ≈ 1.0, pentágono ≈ 0.76)
AREA_MINIMA_PX = 50


def clasificar_contorno(contorno, area_nominal_px=None, tolerancia_pct=5):
    """
    Recibe un contorno (de cv2.findContours) y regresa una tupla:
    (clase, info) donde clase es "circulo" | "cuadrado" | "triangulo" | "rechazo"
    e info es un dict con las métricas usadas (útil para mostrar en la interfaz).
    """
    area = cv2.contourArea(contorno)
    perimetro = cv2.arcLength(contorno, True)
    if perimetro == 0 or area < AREA_MINIMA_PX:
        return "rechazo", {"motivo": "area_insuficiente", "area": area}

    circularidad = 4 * math.pi * area / (perimetro ** 2)
    (_, _), radio = cv2.minEnclosingCircle(contorno)
    razon_circulo = area / (math.pi * radio ** 2) if radio > 0 else 0.0
    aprox = cv2.approxPolyDP(contorno, 0.03 * perimetro, True)
    vertices = len(aprox)

    x, y, w, h = cv2.boundingRect(contorno)
    aspecto = w / h if h > 0 else 0

    info = {"area": area, "circularidad": round(circularidad, 3), "razon_circulo": round(razon_circulo, 3),
            "vertices": vertices, "aspecto": round(aspecto, 2)}

    # Tolerancia dimensional: si conocemos el área esperada, fuera de rango -> rechazo
    if area_nominal_px is not None:
        desviacion_pct = abs(area - area_nominal_px) / area_nominal_px * 100
        info["desviacion_pct"] = round(desviacion_pct, 1)
        if desviacion_pct > tolerancia_pct:
            return "rechazo", info

    # El círculo se reconoce por cuánto llena su círculo envolvente, no por contar vértices:
    # el conteo de vértices de un círculo cambia con el ruido del borde (de 6 a 8).
    if razon_circulo >= UMBRAL_CIRCULO and circularidad > 0.7:
        return "circulo", info
    if vertices == 3:
        return "triangulo", info
    if vertices == 4 and 0.85 <= aspecto <= 1.15:
        return "cuadrado", info

    return "rechazo", info


def detectar_contornos(frame_gris):
    """Umbral de Otsu + limpieza del ruido + contornos. frame_gris ya debe venir en escala de grises."""
    _, binaria = cv2.threshold(frame_gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, kernel)     # quita puntos sueltos
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, kernel)    # tapa huecos pequeños
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contornos, binaria

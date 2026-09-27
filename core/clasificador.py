"""Clasifica un contorno de OpenCV por FORMA únicamente (sin color)."""
import cv2

def clasificar_contorno(contorno, area_nominal_px=None, tolerancia_pct=5):
    """
    Recibe un contorno (de cv2.findContours) y regresa una tupla:
    (clase, info) donde clase es "circulo" | "cuadrado" | "triangulo" | "rechazo"
    e info es un dict con las métricas usadas (útil para mostrar en la interfaz).
    """
    area = cv2.contourArea(contorno)
    perimetro = cv2.arcLength(contorno, True)
    if perimetro == 0 or area < 50:
        return "rechazo", {"motivo": "area_insuficiente", "area": area}

    circularidad = 4 * 3.141592653589793 * area / (perimetro ** 2)
    aprox = cv2.approxPolyDP(contorno, 0.03 * perimetro, True)
    vertices = len(aprox)

    x, y, w, h = cv2.boundingRect(contorno)
    aspecto = w / h if h > 0 else 0

    info = {"area": area, "circularidad": round(circularidad, 3),
            "vertices": vertices, "aspecto": round(aspecto, 2)}

    if area_nominal_px is not None:
        desviacion_pct = abs(area - area_nominal_px) / area_nominal_px * 100
        info["desviacion_pct"] = round(desviacion_pct, 1)
        if desviacion_pct > tolerancia_pct:
            return "rechazo", info

    if circularidad > 0.85 and vertices > 6:
        return "circulo", info
    if vertices == 3:
        return "triangulo", info
    if vertices == 4 and 0.85 <= aspecto <= 1.15:
        return "cuadrado", info

    return "rechazo", info


def detectar_contornos(frame_gris):
    """Umbral Otsu + contornos. frame_gris ya debe venir en escala de grises."""
    _, binaria = cv2.threshold(frame_gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contornos, binaria
"""Visión en vivo con la C270: detecta y clasifica figuras SOLO por forma.

Uso (desde C:\\dev\\inspeccion, con el venv activo):
    python -m gui.app            -> cámara índice 1, exposición -7
    python -m gui.app 0          -> otro índice si el 1 no es la C270
    python -m gui.app 1 -8       -> índice y exposición inicial
Teclas (con la ventana seleccionada):
    i = invertir (figuras oscuras sobre fondo claro)   g = guardar captura
    s = propiedades del driver de la cámara             espacio = pausar
    q o Esc = salir (también la X de la ventana)
"""
import os
import sys
import time

import cv2

from core import camara
from core.clasificador import clasificar_contorno, detectar_contornos

VENTANA = "Inspeccion - vision en vivo"
CARPETA_CAPTURAS = os.path.join("datos", "capturas")

# Colores BGR y salida asignada a cada clase (criterio por defecto del proyecto)
COLOR = {"circulo": (60, 200, 60), "cuadrado": (230, 150, 30),
         "triangulo": (0, 190, 255), "rechazo": (40, 40, 230)}
SALIDA = {"circulo": "S1", "cuadrado": "S2", "triangulo": "S3", "rechazo": "S4"}
NOMBRE = {"circulo": "CIRCULO", "cuadrado": "CUADRADO", "triangulo": "TRIANGULO", "rechazo": "RECHAZO"}


def abrir_camara(indice, exposicion):
    """MJPG 1280x720 a 30 FPS si el driver lo acepta; si no, 640x480 (ver core/camara.py)."""
    return camara.abrir(indice, exposicion)


def toca_borde(contorno, ancho, alto, margen=3):
    """Lo que toca el borde suele ser la mesa o el fondo, no una pieza completa."""
    x, y, w, h = cv2.boundingRect(contorno)
    return x <= margen or y <= margen or x + w >= ancho - margen or y + h >= alto - margen


def procesar(frame, invertir=False, area_min=1500):
    """Detecta y clasifica las figuras de un cuadro. Regresa (cuadro anotado, binaria, detecciones)."""
    alto, ancho = frame.shape[:2]
    gris = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    if invertir:
        gris = 255 - gris
    contornos, binaria = detectar_contornos(gris)

    salida = frame.copy()
    detecciones = []
    for c in contornos:
        area = cv2.contourArea(c)
        if area < area_min or area > 0.4 * ancho * alto or toca_borde(c, ancho, alto):
            continue
        clase, info = clasificar_contorno(c)
        detecciones.append((clase, info))
        color = COLOR[clase]

        cv2.drawContours(salida, [c], -1, color, 3)
        if clase != "circulo":                      # vértices detectados, en rojo
            aprox = cv2.approxPolyDP(c, 0.03 * cv2.arcLength(c, True), True)
            for px, py in aprox.reshape(-1, 2):
                cv2.circle(salida, (int(px), int(py)), 6, (0, 0, 255), -1)

        x, y, w, h = cv2.boundingRect(c)
        titulo = f"{NOMBRE[clase]} -> {SALIDA[clase]}"
        if clase == "rechazo":
            titulo += f" ({info.get('vertices', '?')} vertices)"
        detalle = (f"v={info.get('vertices', '-')}  circ={info.get('circularidad', 0):.2f}  "
                   f"llen={info.get('razon_circulo', 0):.2f}")
        lineas = ((titulo, 0.8, 2), (detalle, 0.55, 1))
        ancho_txt = max(cv2.getTextSize(t, cv2.FONT_HERSHEY_SIMPLEX, e, g)[0][0] for t, e, g in lineas)
        x_txt = max(4, min(x, ancho - ancho_txt - 8))           # que el texto no se salga del cuadro
        y_txt = y + h + 32 if y + h + 70 < alto - 40 else max(y - 34, 26)   # debajo de la pieza si cabe
        for i, (texto, escala, grosor) in enumerate(lineas):
            fy = y_txt + 24 * i
            (tw, th), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, grosor)
            cv2.rectangle(salida, (x_txt - 2, fy - th - 6), (x_txt + tw + 4, fy + 6), (0, 0, 0), -1)
            cv2.putText(salida, texto, (x_txt, fy), cv2.FONT_HERSHEY_SIMPLEX, escala, color, grosor, cv2.LINE_AA)
    return salida, binaria, detecciones


def dibujar_panel(img, binaria, detecciones, fps, invertir, pausado):
    alto, ancho = img.shape[:2]
    # Miniatura de la binaria: es lo único que analiza el clasificador (no tiene color)
    mini_w = ancho // 4
    mini_h = int(binaria.shape[0] * mini_w / binaria.shape[1])
    x0 = ancho - mini_w - 10
    img[10:10 + mini_h, x0:x0 + mini_w] = cv2.cvtColor(cv2.resize(binaria, (mini_w, mini_h)), cv2.COLOR_GRAY2BGR)
    cv2.rectangle(img, (x0, 10), (x0 + mini_w, 10 + mini_h), (255, 255, 255), 1)
    cv2.putText(img, "BINARIA (sin color)", (x0 + 6, 10 + mini_h + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

    conteo = {k: 0 for k in COLOR}
    for clase, _ in detecciones:
        conteo[clase] += 1
    lineas = [f"FPS {fps:4.1f}   piezas en vista: {len(detecciones)}"
              + ("  [INVERTIDO]" if invertir else "") + ("  [PAUSA]" if pausado else "")]
    lineas += [f"{NOMBRE[k]:<10} -> {SALIDA[k]}: {conteo[k]}" for k in COLOR]
    cv2.rectangle(img, (8, 8), (480, 20 + 26 * len(lineas)), (0, 0, 0), -1)
    for i, texto in enumerate(lineas):
        color = (255, 255, 255) if i == 0 else COLOR[list(COLOR)[i - 1]]
        cv2.putText(img, texto, (16, 32 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2, cv2.LINE_AA)
    pie = "Clasificacion solo por forma: vertices, circularidad y llenado del circulo envolvente"
    cv2.rectangle(img, (0, alto - 36), (ancho, alto), (0, 0, 0), -1)
    cv2.putText(img, pie, (12, alto - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def main(indice=1, exposicion=-7):
    cap = abrir_camara(indice, exposicion)
    if cap is None or not cap.read()[0]:
        print(f"No se pudo abrir la cámara {indice}. Prueba otro índice: python -m gui.app 0")
        print("Cierra Teams, Zoom, la app Cámara de Windows o DroidCam si están abiertos.")
        return
    os.makedirs(CARPETA_CAPTURAS, exist_ok=True)
    print(f"Cámara {indice} abierta. Teclas: i invertir, g captura, s ajustes, espacio pausa, q salir.")

    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(VENTANA, 1280, 720)
    cv2.createTrackbar("Exposicion", VENTANA, min(max(exposicion + 13, 0), 12), 12, lambda v: None)
    cv2.createTrackbar("Area minima x100", VENTANA, 15, 200, lambda v: None)

    invertir = pausado = False
    exp_anterior = exposicion + 13
    mostrar = None
    t_prev, fps = time.time(), 0.0
    while True:
        if not pausado or mostrar is None:
            ok, frame = cap.read()
            if not ok:
                print("Sin imagen de la cámara, saliendo")
                break
            exp = cv2.getTrackbarPos("Exposicion", VENTANA)        # 0..12 -> -13..-1
            if exp != exp_anterior:
                cap.set(cv2.CAP_PROP_EXPOSURE, exp - 13)
                exp_anterior = exp
            area_min = max(cv2.getTrackbarPos("Area minima x100", VENTANA), 1) * 100
            salida, binaria, detecciones = procesar(frame, invertir, area_min)
            ahora = time.time()
            if ahora > t_prev:
                fps = 0.9 * fps + 0.1 / (ahora - t_prev)
            t_prev = ahora
            mostrar = dibujar_panel(salida, binaria, detecciones, fps, invertir, pausado)
        cv2.imshow(VENTANA, mostrar)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla in (ord("q"), 27) or cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:
            break
        if tecla == ord("i"):
            invertir = not invertir
        elif tecla == ord(" "):
            pausado = not pausado
            mostrar = None if not pausado else mostrar
        elif tecla == ord("s"):
            cap.set(cv2.CAP_PROP_SETTINGS, 1)
        elif tecla == ord("g"):
            ruta = os.path.join(CARPETA_CAPTURAS, time.strftime("vision_%Y%m%d_%H%M%S.png"))
            cv2.imwrite(ruta, mostrar)
            print("Captura guardada en", ruta)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    indice = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    exposicion = int(sys.argv[2]) if len(sys.argv) > 2 else -7
    main(indice, exposicion)

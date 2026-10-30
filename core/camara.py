"""Apertura robusta de la C270 en Windows.

La C270 solo da 30 FPS a 1280x720 si entrega MJPG; en YUY2 se queda en ~10 FPS.
Según la versión de OpenCV y del driver, DirectShow acepta MJPG de distinta forma,
así que se prueban tres maneras de pedirlo. Si ninguna funciona, se usa 640x480,
donde YUY2 sí da 30 FPS.
"""
import os

import cv2

ESTRATEGIAS = ("parametros", "formato_primero", "tamano_primero")
RESPALDO = (640, 480)


def formato(cap):
    """FOURCC que la cámara está entregando realmente, como texto ('MJPG', 'YUY2', ...)."""
    codigo = int(cap.get(cv2.CAP_PROP_FOURCC))
    return "".join(chr((codigo >> 8 * i) & 0xFF) for i in range(4)).strip("\x00 ")


def tamano(cap):
    return int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


def _abrir(indice, estrategia, ancho, alto):
    mjpg = cv2.VideoWriter_fourcc(*"MJPG")
    if estrategia == "parametros":
        try:
            cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW,
                                   [cv2.CAP_PROP_FOURCC, mjpg, cv2.CAP_PROP_FRAME_WIDTH, ancho,
                                    cv2.CAP_PROP_FRAME_HEIGHT, alto, cv2.CAP_PROP_FPS, 30])
        except (cv2.error, TypeError):
            return None
    else:
        cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if cap.isOpened():
            if estrategia == "formato_primero":
                cap.set(cv2.CAP_PROP_FOURCC, mjpg)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
            else:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
                cap.set(cv2.CAP_PROP_FOURCC, mjpg)
            cap.set(cv2.CAP_PROP_FPS, 30)
    if not cap.isOpened():
        cap.release()
        return None
    return cap


def _manual(cap, exposicion):
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   # 0.25 = manual en DirectShow
    cap.set(cv2.CAP_PROP_EXPOSURE, exposicion)
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)


def abrir(indice=1, exposicion=-7, ancho=1280, alto=720, avisar=True):
    """Abre la cámara en MJPG a ancho x alto; si no se puede, a 640x480. Regresa el VideoCapture o None."""
    if os.name != "nt":
        cap = cv2.VideoCapture(indice)
        if not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
        _manual(cap, exposicion)
        return cap

    alguna_abrio = False
    for estrategia in ESTRATEGIAS:
        cap = _abrir(indice, estrategia, ancho, alto)
        if cap is None:
            continue
        alguna_abrio = True
        if formato(cap) == "MJPG" and tamano(cap) == (ancho, alto):
            _manual(cap, exposicion)
            if avisar:
                print(f"Cámara {indice}: MJPG {ancho}x{alto} (método: {estrategia})")
            return cap
        cap.release()
    if not alguna_abrio:
        return None

    cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, RESPALDO[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESPALDO[1])
    cap.set(cv2.CAP_PROP_FPS, 30)
    _manual(cap, exposicion)
    if avisar:
        w, h = tamano(cap)
        print(f"Cámara {indice}: el driver no aceptó MJPG; uso {formato(cap) or '?'} {w}x{h} para mantener 30 FPS.")
        print("  Con esta resolución las piezas se ven a la mitad de tamaño: baja el área mínima (~400).")
    return cap

"""Calibración de la C270: fija exposición y balance de blancos y guarda capturas.

Uso:   python calibrar_camara.py        (abre el índice 1)
       python calibrar_camara.py 2      (abre el índice que indiques)
Teclas: s = propiedades del driver · g = guardar captura · q = salir
La cámara integrada de la laptop suele ser el índice 0, así que la C270 suele ser el 1.
"""
import os
import sys
import time

import cv2

CARPETA = os.path.join("datos", "capturas")


def listar(maximo=5):
    """Índices de cámara que abren y entregan imagen."""
    encontrados = []
    for i in range(maximo):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened() and cap.read()[0]:
            encontrados.append(i)
        cap.release()
    return encontrados


def configurar(cap):
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # evita la compresión lenta
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   # 0.25 = manual en DirectShow
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)


def main():
    indice = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
    if not cap.isOpened() or not cap.read()[0]:
        cap.release()
        print(f"No se pudo abrir el índice {indice}.")
        print("Índices que sí abren:", listar() or "ninguno")
        print("Revisa el cable, que ninguna otra aplicación use la cámara y los permisos de Windows.")
        return
    configurar(cap)
    os.makedirs(CARPETA, exist_ok=True)

    ventana = "Calibracion C270"
    cv2.namedWindow(ventana)
    cv2.createTrackbar("Exposicion", ventana, 7, 12, lambda v: None)   # 0..12 -> -13..-1
    anterior = None
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Sin imagen")
            break
        pos = cv2.getTrackbarPos("Exposicion", ventana)
        if pos != anterior:
            cap.set(cv2.CAP_PROP_EXPOSURE, pos - 13)
            anterior = pos
        h, w = frame.shape[:2]
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        info = (f"indice {indice}  {w}x{h}  exposicion pedida={pos - 13}  "
                f"leida={cap.get(cv2.CAP_PROP_EXPOSURE):.1f}  brillo medio={gris.mean():.0f}")
        cv2.putText(frame, info, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.imshow(ventana, frame)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord("s"):
            cap.set(cv2.CAP_PROP_SETTINGS, 1)
        elif tecla == ord("g"):
            ruta = os.path.join(CARPETA, time.strftime("captura_%Y%m%d_%H%M%S.png"))
            cv2.imwrite(ruta, frame)
            print("Guardada", ruta)
        elif tecla == ord("q") or cv2.getWindowProperty(ventana, cv2.WND_PROP_VISIBLE) < 1:
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

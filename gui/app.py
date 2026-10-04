"""Interfaz v1: video en vivo + contorno + clase decidida. Sin botones, sin BD todavía."""
import cv2
import time
from core.clasificador import detectar_contornos, clasificar_contorno

COLOR = {"circulo": (60, 200, 60), "cuadrado": (200, 140, 0),
         "triangulo": (0, 160, 220), "rechazo": (0, 0, 220)}

def main(fuente=0):
    cap = cv2.VideoCapture(fuente)
    if not cap.isOpened():
        print("No se pudo abrir la cámara/fuente:", fuente)
        return

    t_prev = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            print("Sin frame, saliendo"); break

        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        contornos, binaria = detectar_contornos(gris)

        for c in contornos:
            if cv2.contourArea(c) < 300:
                continue
            clase, info = clasificar_contorno(c)
            x, y, w, h = cv2.boundingRect(c)
            color = COLOR[clase]
            cv2.drawContours(frame, [c], -1, color, 2)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)
            etiqueta = f"{clase} (v={info['vertices']}, circ={info['circularidad']})"
            cv2.putText(frame, etiqueta, (x, max(y - 10, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        ahora = time.time()
        fps = 1 / (ahora - t_prev) if ahora > t_prev else 0
        t_prev = ahora
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.imshow("Interfaz v1 - clasificacion en vivo", frame)
        cv2.imshow("Binaria (lo que ve el clasificador)", binaria)

        tecla = cv2.waitKey(1) & 0xFF
        ventana_cerrada = cv2.getWindowProperty(
            "Interfaz v1 - clasificacion en vivo", cv2.WND_PROP_VISIBLE) < 1
        if tecla == ord("q") or ventana_cerrada:
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main(1)
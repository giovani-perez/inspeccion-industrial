"""Línea completa: cámara -> forma -> decisión por pieza -> comando al ESP32 -> compuerta -> confirmación.

Uso (desde C:\\dev\\inspeccion, con el venv activo y Thonny CERRADO):
    python -m gui.linea --puerto COM5                 # cámara + ESP32 real
    python -m gui.linea --virtual                     # cámara + ESP32 virtual (compuertas en pantalla)
    python -m gui.linea                               # solo cámara: muestra las decisiones
    python -m gui.linea --demo --virtual              # sin cámara: piezas simuladas (respaldo para presentar)
Opciones: --camara 1  --exp -7  --sentido der|izq  --vel 100  --franja 0.2 0.8  --area-min 1500
Teclas: espacio = arrancar/detener (manda run/stop)  i = invertir  g = captura  r = reiniciar conteo  q/Esc = salir
"""
import argparse
import math
import os
import random
import time

import cv2
import numpy as np

from core import protocolo as p
from core.clasificador import clasificar_contorno, detectar_contornos
from core.seguimiento import SALIDA, Seguidor
from gui.app import COLOR, NOMBRE, abrir_camara, toca_borde

VENTANA = "Inspeccion y clasificacion industrial"
LIENZO = (1600, 900)                       # ancho, alto de la interfaz
VISTA = (16, 80, 1120, 630)                # x, y, ancho, alto de la cámara dentro del lienzo
PANEL_X = 1152

FONDO, TARJETA, BORDE = (24, 24, 28), (40, 40, 46), (70, 70, 78)
BLANCO, GRIS, GRIS_OSC = (245, 245, 245), (170, 170, 175), (110, 110, 115)
VERDE, AMARILLO, ROJO, NARANJA = (80, 200, 80), (40, 200, 230), (60, 60, 230), (0, 140, 255)
F, FD = cv2.FONT_HERSHEY_SIMPLEX, cv2.FONT_HERSHEY_DUPLEX
ORDEN = ("circulo", "cuadrado", "triangulo", "rechazo")
CONTRASTE_MIN = 40                         # diferencia mínima (niveles de gris) entre pieza y banda


def hay_contraste(gris, minimo=CONTRASTE_MIN):
    """Con la banda vacía Otsu parte el ruido en manchas: si las dos clases casi no difieren, no hay piezas."""
    t, _ = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    claro, oscuro = gris[gris > t], gris[gris <= t]
    return claro.size > 0 and oscuro.size > 0 and float(claro.mean()) - float(oscuro.mean()) >= minimo


def detectar(frame, invertir=False, area_min=1500, franja=(0.0, 1.0)):
    """Regresa [(clase, cx, cy, contorno, info)] de las piezas completas dentro de la franja."""
    alto, ancho = frame.shape[:2]
    y0, y1 = int(franja[0] * alto), int(franja[1] * alto)
    zona = frame[y0:y1]
    gris = cv2.GaussianBlur(cv2.cvtColor(zona, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    if invertir:
        gris = 255 - gris
    if not hay_contraste(gris):
        return [], np.zeros_like(gris)
    contornos, binaria = detectar_contornos(gris)
    piezas = []
    for c in contornos:
        area = cv2.contourArea(c)
        if area < area_min or area > 0.4 * ancho * (y1 - y0) or toca_borde(c, ancho, y1 - y0):
            continue
        m = cv2.moments(c)
        if not m["m00"]:
            continue
        clase, info = clasificar_contorno(c)
        c = c + (0, y0)                       # coordenadas del cuadro completo
        piezas.append((clase, m["m10"] / m["m00"], m["m01"] / m["m00"] + y0, c, info))
    return piezas, binaria


# --------------------------------------------------------------------------- cámara simulada
class CamaraDemo:
    """Piezas claras que cruzan una banda oscura, como la real. Sirve de respaldo si falla la cámara."""

    FORMAS = ("circulo", "cuadrado", "triangulo", "pentagono")

    def __init__(self, ancho=1280, alto=720, sentido=1, px_por_cuadro=9, cada_s=1.4, semilla=7):
        self.ancho, self.alto, self.sentido = ancho, alto, sentido
        self.vx = px_por_cuadro * sentido
        self.cada = cada_s
        self.rnd = random.Random(semilla)
        self.piezas = []
        self.turno = 0
        self.t_ultima = -99.0
        self.t_cuadro = time.time()
        base = np.full((alto, ancho, 3), 26, np.uint8)
        ruido = np.random.default_rng(semilla).integers(0, 10, (alto, ancho, 1), dtype=np.uint8)
        self.fondo = cv2.add(base, np.repeat(ruido, 3, axis=2))

    def _nueva(self):
        forma = self.FORMAS[self.turno % len(self.FORMAS)]
        self.turno += 1
        x = -90 if self.sentido > 0 else self.ancho + 90
        y = self.alto // 2 + self.rnd.randint(-70, 70)
        self.piezas.append([forma, float(x), y, self.rnd.uniform(0, 90)])

    def _dibujar(self, img, forma, cx, cy, ang):
        if forma == "circulo":
            cv2.circle(img, (int(cx), cy), 62, (205, 225, 240), -1, cv2.LINE_AA)
            return
        if forma == "cuadrado":
            pts = [(-56, -56), (56, -56), (56, 56), (-56, 56)]
        elif forma == "triangulo":
            pts = [(0, -74), (-66, 46), (66, 46)]
        else:
            pts = [(66 * math.cos(math.radians(-90 + 72 * i)), 66 * math.sin(math.radians(-90 + 72 * i)))
                   for i in range(5)]
        a = math.radians(ang)
        P = np.array([[cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)]
                      for x, y in pts], np.int32)
        cv2.fillPoly(img, [P], (200, 230, 215), cv2.LINE_AA)

    def isOpened(self):
        return True

    def read(self):
        espera = 1 / 30 - (time.time() - self.t_cuadro)
        if espera > 0:
            time.sleep(espera)
        self.t_cuadro = time.time()
        if self.t_cuadro - self.t_ultima >= self.cada:
            self._nueva()
            self.t_ultima = self.t_cuadro
        img = self.fondo.copy()
        for pz in self.piezas:
            pz[1] += self.vx
            self._dibujar(img, pz[0], pz[1], pz[2], pz[3])
        self.piezas = [pz for pz in self.piezas if -200 < pz[1] < self.ancho + 200]
        return True, img

    def set(self, *a):
        return True

    def release(self):
        pass


# --------------------------------------------------------------------------- dibujo
def _texto(img, s, x, y, escala=0.55, color=BLANCO, grosor=1, fuente=F):
    cv2.putText(img, s, (int(x), int(y)), fuente, escala, color, grosor, cv2.LINE_AA)


def _ancho(s, escala, grosor=1, fuente=F):
    return cv2.getTextSize(s, fuente, escala, grosor)[0][0]


def _caja(img, x, y, w, h, color=TARJETA, borde=BORDE):
    cv2.rectangle(img, (x, y), (x + w, y + h), color, -1)
    if borde is not None:
        cv2.rectangle(img, (x, y), (x + w, y + h), borde, 1)


def _chip(img, x_derecha, y, etiqueta, valor, color):
    s = f"{etiqueta} {valor}"
    w = _ancho(s, 0.52, 1) + 34
    x = x_derecha - w
    _caja(img, x, y, w, 30, (36, 36, 42), color)
    cv2.circle(img, (x + 14, y + 15), 6, color, -1, cv2.LINE_AA)
    _texto(img, s, x + 26, y + 21, 0.52, BLANCO)
    return x - 10


def _flecha_discontinua(img, p0, p1, color, grosor=2, paso=18):
    largo = int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]))
    for i in range(0, largo, paso * 2):
        a = (int(p0[0] + (p1[0] - p0[0]) * i / largo), int(p0[1] + (p1[1] - p0[1]) * i / largo))
        j = min(i + paso, largo)
        b = (int(p0[0] + (p1[0] - p0[0]) * j / largo), int(p0[1] + (p1[1] - p0[1]) * j / largo))
        cv2.line(img, a, b, color, grosor, cv2.LINE_AA)


def dibujar_vista(frame, piezas, seguidor, decididas, franja, sentido):
    """Dibuja sobre el cuadro de la cámara: franja, línea de decisión, contornos y pistas."""
    vista = frame.copy()
    alto, ancho = vista.shape[:2]
    y0, y1 = int(franja[0] * alto), int(franja[1] * alto)
    if franja != (0.0, 1.0):
        sombra = vista.copy()
        cv2.rectangle(sombra, (0, 0), (ancho, y0), (0, 0, 0), -1)
        cv2.rectangle(sombra, (0, y1), (ancho, alto), (0, 0, 0), -1)
        vista = cv2.addWeighted(sombra, 0.55, vista, 0.45, 0)
    xl = ancho // 2
    _flecha_discontinua(vista, (xl, y0 + 4), (xl, y1 - 4), NARANJA, 3)
    _texto(vista, "LINEA DE DECISION", xl + 10, y0 + 30, 0.6, NARANJA, 2)
    xa = 60 if sentido > 0 else ancho - 60
    cv2.arrowedLine(vista, (xa, y1 - 30), (xa + 120 * sentido, y1 - 30), GRIS, 2, cv2.LINE_AA, tipLength=0.25)
    _texto(vista, "avance", min(xa, xa + 120 * sentido) + 30, y1 - 42, 0.5, GRIS)

    for clase, cx, cy, c, info in piezas:
        cv2.drawContours(vista, [c], -1, COLOR[clase], 4, cv2.LINE_AA)
        etiqueta = NOMBRE[clase]
        x, y, w, h = cv2.boundingRect(c)
        tw = _ancho(etiqueta, 0.62, 2)
        bx, by = max(4, min(int(cx - tw / 2) - 8, ancho - tw - 20)), max(y - 34, 4)
        cv2.rectangle(vista, (bx, by), (bx + tw + 16, by + 28), COLOR[clase], -1)
        _texto(vista, etiqueta, bx + 8, by + 21, 0.62, (20, 20, 20), 2)
    for pista in seguidor.pistas:
        votos = sum(pista.votos.values())
        if pista.id in decididas:
            d = decididas[pista.id]
            s, color = f"#{pista.id}  ->  S{d.salida}", COLOR[d.clase]
        elif pista.decidida:
            continue
        else:
            s, color = f"#{pista.id}  {votos} votos", BLANCO
        tw = _ancho(s, 0.55, 1)
        px, py = int(pista.cx - tw / 2), int(pista.cy) + 92
        cv2.rectangle(vista, (px - 6, py - 18), (px + tw + 6, py + 6), (15, 15, 15), -1)
        _texto(vista, s, px, py, 0.55, color, 1)
    return vista


def componer(vista, binaria, estado):
    """Arma la interfaz completa (lienzo 1600x900) a partir de la vista de la cámara y el estado."""
    W, H = LIENZO
    img = np.full((H, W, 3), FONDO, np.uint8)

    # ---- encabezado ----
    cv2.rectangle(img, (0, 0), (W, 64), (32, 32, 38), -1)
    cv2.line(img, (0, 64), (W, 64), BORDE, 1)
    _texto(img, "SISTEMA DE INSPECCION Y CLASIFICACION INDUSTRIAL", 18, 32, 0.82, BLANCO, 1, FD)
    _texto(img, "Clasificacion solo por forma  |  vision OpenCV + ESP32  |  UNACH  LIDTS 3-M", 18, 54, 0.48, GRIS)
    x = W - 16
    x = _chip(img, x, 17, "FPS", f"{estado['fps']:.0f}", VERDE if estado["fps"] >= 24 else AMARILLO)
    st = estado["esp32"]
    color_esp = {"RUN": VERDE, "IDLE": AMARILLO, "FAIL": ROJO}.get(st, GRIS_OSC)
    x = _chip(img, x, 17, "ESP32", st, color_esp)
    x = _chip(img, x, 17, "BANDA", "EN MARCHA" if estado["corriendo"] else "DETENIDA",
              VERDE if estado["corriendo"] else GRIS_OSC)
    _chip(img, x, 17, "MODO", estado["modo"], (200, 150, 60))

    # ---- cámara ----
    vx, vy, vw, vh = VISTA
    img[vy:vy + vh, vx:vx + vw] = cv2.resize(vista, (vw, vh), interpolation=cv2.INTER_AREA)
    cv2.rectangle(img, (vx - 1, vy - 1), (vx + vw, vy + vh), BORDE, 1)
    _texto(img, "CAMARA EN VIVO", vx + 12, vy + 26, 0.55, BLANCO, 1, FD)

    # ---- franja inferior: binaria + historial ----
    fy = vy + vh + 16
    fh = H - fy - 16
    bw = int(fh * 16 / 9)
    mini = cv2.cvtColor(cv2.resize(binaria, (bw, fh - 26)), cv2.COLOR_GRAY2BGR)
    _caja(img, vx, fy, bw, fh)
    img[fy + 26:fy + fh, vx:vx + bw] = mini
    _texto(img, "LO QUE VE EL CLASIFICADOR", vx + 8, fy + 18, 0.45, GRIS)

    hx, hw = vx + bw + 16, vw - bw - 16
    _caja(img, hx, fy, hw, fh)
    _texto(img, "ULTIMAS DECISIONES", hx + 12, fy + 22, 0.5, GRIS)
    cols = (hx + 14, hx + 90, hx + 260, hx + 360, hx + 480)
    for c, t in zip(cols, ("PIEZA", "FORMA", "SALIDA", "CONFIANZA", "VOTOS")):
        _texto(img, t, c, fy + 46, 0.42, GRIS_OSC)
    for i, d in enumerate(reversed(estado["historial"][-4:])):
        y = fy + 72 + 24 * i
        _texto(img, f"#{d.id}", cols[0], y, 0.52, BLANCO)
        _texto(img, NOMBRE[d.clase], cols[1], y, 0.52, COLOR[d.clase], 2)
        _texto(img, f"S{d.salida}", cols[2], y, 0.52, BLANCO)
        _texto(img, f"{d.confianza:.0%}", cols[3], y, 0.52, BLANCO)
        _texto(img, str(sum(d.votos.values())), cols[4], y, 0.52, BLANCO)
    if not estado["historial"]:
        _texto(img, "Aun no cruza ninguna pieza la linea de decision", hx + 14, fy + 80, 0.5, GRIS_OSC)

    # ---- panel derecho ----
    px, pw = PANEL_X, W - PANEL_X - 16
    y = vy
    _texto(img, "CONTEO POR SALIDA", px, y + 14, 0.5, GRIS)
    conteo = estado["conteo"]
    total = sum(conteo.values())
    maximo = max(conteo.values()) or 1
    y += 26
    for clase in ORDEN:
        _caja(img, px, y, pw, 62)
        cv2.rectangle(img, (px, y), (px + 6, y + 62), COLOR[clase], -1)
        _texto(img, f"S{SALIDA[clase]}", px + 20, y + 26, 0.55, GRIS)
        _texto(img, NOMBRE[clase], px + 20, y + 50, 0.62, COLOR[clase], 2)
        n = str(conteo[clase])
        _texto(img, n, px + pw - 16 - _ancho(n, 1.1, 2, FD), y + 44, 1.1, BLANCO, 2, FD)
        barra = int((pw - 230) * conteo[clase] / maximo)
        cv2.rectangle(img, (px + 170, y + 40), (px + 170 + max(barra, 2), y + 48), COLOR[clase], -1)
        y += 70
    conformes = total - conteo["rechazo"]
    pct = f"{conformes / total:.0%}" if total else "-"
    _texto(img, f"Total: {total}    Conformes: {conformes} ({pct})", px, y + 16, 0.52, BLANCO)
    _texto(img, f"Confirmadas por el ESP32: {estado['confirmadas']}", px, y + 40, 0.52, GRIS)

    y += 64
    _texto(img, "COMPUERTAS", px, y + 14, 0.5, GRIS)
    y += 24
    gw = (pw - 2 * 10) // 3
    for i, abajo in enumerate(estado["compuertas"]):
        gx = px + i * (gw + 10)
        color = COLOR[ORDEN[i]] if abajo else (52, 52, 58)
        _caja(img, gx, y, gw, 58, color, BORDE)
        _texto(img, f"C{i + 1}", gx + 12, y + 26, 0.62, BLANCO if abajo else GRIS, 2)
        _texto(img, "DESVIA" if abajo else "reposo", gx + 12, y + 48, 0.48, BLANCO if abajo else GRIS_OSC)

    y += 76
    _texto(img, "ULTIMA PIEZA", px, y + 14, 0.5, GRIS)
    y += 24
    _caja(img, px, y, pw, 112)
    d = estado["historial"][-1] if estado["historial"] else None
    if d:
        cv2.rectangle(img, (px, y), (px + 6, y + 112), COLOR[d.clase], -1)
        _texto(img, NOMBRE[d.clase], px + 20, y + 46, 1.15, COLOR[d.clase], 2, FD)
        _texto(img, f"S{d.salida}", px + pw - 20 - _ancho(f"S{d.salida}", 1.15, 2, FD), y + 46, 1.15, BLANCO, 2, FD)
        _texto(img, f"Pieza #{d.id}   confianza {d.confianza:.0%}   {sum(d.votos.values())} votos",
               px + 20, y + 84, 0.52, GRIS)
    else:
        _texto(img, "Esperando pieza...", px + 20, y + 62, 0.62, GRIS_OSC)

    _texto(img, "ESPACIO arrancar/detener   I invertir", px, H - 42, 0.46, GRIS_OSC)
    _texto(img, "G captura   R reiniciar conteo   Q salir", px, H - 20, 0.46, GRIS_OSC)
    return img


# --------------------------------------------------------------------------- programa
def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--camara", type=int, default=1)
    a.add_argument("--exp", type=int, default=-7)
    a.add_argument("--puerto", default=None, help="COM del ESP32, por ejemplo COM5")
    a.add_argument("--virtual", action="store_true",
                   help="usar el firmware en la PC en lugar del ESP32 (compuertas en pantalla)")
    a.add_argument("--demo", action="store_true", help="sin cámara: piezas simuladas")
    a.add_argument("--sentido", choices=("der", "izq"), default="der",
                   help="hacia dónde avanzan las piezas en la imagen")
    a.add_argument("--vel", type=float, default=100, help="velocidad real de la banda en mm/s")
    a.add_argument("--franja", type=float, nargs=2, default=(0.0, 1.0),
                   help="parte de la altura de la imagen que ocupa la banda (0 a 1)")
    a.add_argument("--area-min", type=int, default=1500)
    args = a.parse_args()
    sentido = 1 if args.sentido == "der" else -1
    franja = tuple(args.franja)

    cap = CamaraDemo(sentido=sentido) if args.demo else abrir_camara(args.camara, args.exp)
    if cap is None or not cap.read()[0]:
        print(f"No se pudo abrir la cámara {args.camara}. Para presentar sin cámara: python -m gui.linea --demo --virtual")
        return
    ok, frame = cap.read()
    alto, ancho = frame.shape[:2]
    seguidor = Seguidor(linea_x=ancho // 2, sentido=sentido)

    enlace = None
    virtual = None
    if args.virtual:
        from core.enlace_serial import EnlaceESP32
        from sim.firmware_virtual import FirmwareVirtual
        virtual = FirmwareVirtual()
        enlace = EnlaceESP32(serie=virtual)
        enlace.enviar(p.vel(args.vel, args.vel))
        modo = "VIRTUAL"
    elif args.puerto:
        from core.enlace_serial import EnlaceESP32
        enlace = EnlaceESP32(args.puerto)
        time.sleep(1.5)                       # por si el ESP32 se reinició al abrir el puerto
        enlace.atender()
        enlace.enviar(p.vel(args.vel, args.vel))
        modo = args.puerto.upper()
    else:
        modo = "SOLO VISION"
    if args.demo:
        modo = "DEMO " + modo if modo != "SOLO VISION" else "DEMO"
    print(f"Listo ({modo}). Espacio = arrancar, q = salir.")

    estado = {"fps": 0.0, "corriendo": False, "esp32": "-" if enlace else "sin conectar", "modo": modo,
              "conteo": {k: 0 for k in SALIDA}, "confirmadas": 0, "historial": [], "compuertas": [False] * 3}
    decididas = {}
    desvio_hasta = [0.0, 0.0, 0.0]            # ESP32 real: ilumina la compuerta al recibir "div"
    invertir = False
    os.makedirs(os.path.join("datos", "capturas"), exist_ok=True)
    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(VENTANA, *LIENZO)
    t_prev = time.time()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Sin imagen de la cámara")
                break
            piezas, binaria = detectar(frame, invertir, args.area_min, franja)
            for d in seguidor.actualizar([(c, x, y) for c, x, y, _, _ in piezas]):
                estado["conteo"][d.clase] += 1
                estado["historial"].append(d)
                del estado["historial"][:-20]
                decididas[d.id] = d
                print(d)
                if enlace and estado["corriendo"]:
                    enlace.enviar(p.clase(d.id, d.salida))
            vivos = {pista.id for pista in seguidor.pistas}
            decididas = {k: v for k, v in decididas.items() if k in vivos}

            ahora = time.time()
            if enlace:
                for ev in enlace.atender():
                    if ev["e"] == "div":
                        estado["confirmadas"] += 1
                        if 1 <= ev["out"] <= 3:
                            desvio_hasta[ev["out"] - 1] = ahora + 0.8
                    elif ev["e"] == "tel":
                        estado["esp32"] = ev["st"]
                    elif ev["e"] == "err":
                        print("ESP32:", ev)
            if virtual:
                estado["compuertas"] = virtual.compuertas_abajo()
            else:
                estado["compuertas"] = [ahora < t for t in desvio_hasta]
            if ahora > t_prev:
                estado["fps"] = 0.9 * estado["fps"] + 0.1 / (ahora - t_prev)
            t_prev = ahora

            vista = dibujar_vista(frame, piezas, seguidor, decididas, franja, sentido)
            lienzo = componer(vista, binaria, estado)
            cv2.imshow(VENTANA, lienzo)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), 27) or cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:
                break
            if tecla == ord(" "):
                estado["corriendo"] = not estado["corriendo"]
                if enlace:
                    enlace.enviar(p.run() if estado["corriendo"] else p.stop())
            elif tecla == ord("i"):
                invertir = not invertir
            elif tecla == ord("r"):
                estado["conteo"] = {k: 0 for k in SALIDA}
                estado["historial"].clear()
                estado["confirmadas"] = 0
            elif tecla == ord("g"):
                ruta = os.path.join("datos", "capturas", time.strftime("linea_%Y%m%d_%H%M%S.png"))
                cv2.imwrite(ruta, lienzo)
                print("Captura guardada en", ruta)
    finally:
        if enlace:
            enlace.cerrar()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

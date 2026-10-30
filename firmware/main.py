"""Firmware del ESP32 (MicroPython 1.29): motor de la banda y compuertas con el protocolo JSON del proyecto.

Se guarda en el ESP32 como main.py y arranca solo al encender.
Protocolo (una línea JSON por mensaje, 115200 baudios), el mismo de core/protocolo.py:
  PC -> ESP32: hb, run, stop, cls {id, out}, vel {nom, insp}, gate {n, a}
  ESP32 -> PC: tel {v, d, st}, div {id, out}, err {code}

Mientras no estén conectados el sensor IR y el encoder, la compuerta se programa por TIEMPO:
la PC manda "cls" cuando la pieza cruza la línea de decisión (centro de la cámara) y el ESP32
calcula cuándo llega a cada compuerta con la distancia medida y la velocidad de la banda.
Cada compuerta baja, espera a que pase la pieza y regresa sola a reposo, sin bloquear la
lectura de nuevos comandos.

Motor (L298N): "run" lo arranca (patada al 100 % y luego MOTOR_PCT); "stop", la falta de latido
o cualquier error del programa lo detienen.
"""
import json
import sys
import time

# ---------------- AJUSTES (medir en el prototipo) ----------------------------------------------
PINES_SERVO = (18, 19, 23)          # compuertas 1, 2 y 3
REPOSO = [0, 0, 0]                  # grados de cada servo en reposo (calibrar con prueba_servos.py)
ACTIVO = [90, 90, 90]               # grados de cada servo con la compuerta abajo
PULSO_MIN_US, PULSO_MAX_US = 500, 2400

DIST_MM = [200, 315, 430]           # línea de decisión -> paleta de la compuerta 1, 2 y 3 (MEDIR)
DIST_FIN_MM = 560                   # línea de decisión -> final de la banda (rechazo)
VELOCIDAD_MM_S = 100                # velocidad real de la banda (MEDIR); la PC la cambia con "vel"
LATENCIA_MS = 80                    # retraso de cámara + visión + serial (ajustar en pruebas)
ADELANTO_MS = 250                   # la compuerta baja este tiempo antes de que llegue la pieza
PASO_MM = 120                       # recorrido de la pieza con la compuerta abajo (paleta + pieza)

PIN_ENA, PIN_IN1, PIN_IN2 = 25, 26, 27   # L298N (jumper de ENA quitado)
MOTOR_PCT = 95                      # potencia del motor en marcha (22-oct: a 75 % se atascaba)
MOTOR_ARRANQUE_MS = 300             # "patada" al 100 % para vencer la inercia del rodillo
SENTIDO_ADELANTE = True             # si la banda corre al revés, cambia a False
MOTOR_PWM_HZ = 20000                # 20 kHz: sin chillido (a 1 kHz se oye)

LATIDO_MS = 1000                    # sin latido de la PC en este tiempo -> FALLA (cierra compuertas)
TEL_MS = 200                        # telemetría cada 200 ms
# ------------------------------------------------------------------------------------------------

ESTADO_TEL = {"INACTIVO": "IDLE", "OPERANDO": "RUN", "FALLA": "FAIL"}
NUM = (int, float)
COMANDOS = {"hb": {}, "run": {}, "stop": {}, "cls": {"id": int, "out": int},
            "vel": {"nom": NUM, "insp": NUM}, "gate": {"n": int, "a": NUM}}

try:
    _dif = time.ticks_diff                      # MicroPython
except AttributeError:                          # Python normal (pruebas en la PC)
    def _dif(a, b):
        return a - b


def validar(m):
    """Regresa el nombre del comando o None si el mensaje no cumple el protocolo."""
    if not isinstance(m, dict) or "c" not in m or m["c"] not in COMANDOS:
        return None
    campos = COMANDOS[m["c"]]
    for k, tipo in campos.items():
        if k not in m or isinstance(m[k], bool) or not isinstance(m[k], tipo):
            return None
    for k in m:
        if k != "c" and k not in campos:
            return None
    c = m["c"]
    if c == "cls" and not 1 <= m["out"] <= 4:
        return None
    if c == "gate" and not (1 <= m["n"] <= 3 and -90 <= m["a"] <= 180):
        return None
    if c == "vel" and (m["nom"] <= 0 or m["insp"] <= 0):
        return None
    return c


class Controlador:
    """Lógica del firmware, sin hardware: recibe líneas, programa compuertas y emite eventos."""

    def __init__(self, mover_servo, reloj_ms, escribir, motor=None):
        self.mover = mover_servo          # mover(indice 0..2, grados)
        self.motor = motor or (lambda pct: None)   # motor(porcentaje 0..100)
        self.motor_pct = None
        self.motor_desde = None
        self.reloj = reloj_ms             # función que da milisegundos
        self.escribir = escribir          # escribir(str) manda una línea a la PC
        self.estado = "INACTIVO"
        self.vel = VELOCIDAD_MM_S
        self.programa = []                # [ms, tipo, compuerta, id, salida]
        self.abierta_hasta = [None, None, None]
        self.ultimo_latido = None
        self.ultima_tel = self.reloj()
        self.buf = ""
        self.poner_motor(0)
        for i in range(3):
            self.mover(i, REPOSO[i])

    def poner_motor(self, pct):
        if pct != self.motor_pct:
            self.motor_pct = pct
            self.motor(pct)

    # ---- entrada ----
    def alimentar(self, texto):
        self.buf += texto
        while "\n" in self.buf:
            linea, self.buf = self.buf.split("\n", 1)
            linea = linea.strip()
            if linea:
                self.atender(linea)
        if len(self.buf) > 512:          # basura sin salto de línea
            self.buf = ""

    def atender(self, linea):
        try:
            m = json.loads(linea)
        except ValueError:
            m = None
        c = validar(m)
        if c is None:
            self.evento({"e": "err", "code": "mensaje_invalido"})
            return
        ahora = self.reloj()
        if c == "hb":
            self.ultimo_latido = ahora
            if self.estado == "FALLA":
                self.estado = "INACTIVO"
        elif c == "run":
            if self.estado == "INACTIVO":
                self.estado = "OPERANDO"
                self.ultimo_latido = ahora
                self.motor_desde = ahora
                self.poner_motor(100)
            else:
                self.evento({"e": "err", "code": "estado_invalido"})
        elif c == "stop":
            self.detener()
        elif c == "vel":
            self.vel = m["nom"]
        elif c == "gate":
            if self.estado == "OPERANDO":
                self.evento({"e": "err", "code": "compuerta_en_marcha"})
            else:
                self.mover(m["n"] - 1, m["a"])
        elif c == "cls":
            if self.estado != "OPERANDO":
                self.evento({"e": "err", "code": "estado_invalido"})
            else:
                self.programar(m["id"], m["out"], ahora)

    # ---- compuertas ----
    def ms_hasta(self, mm):
        return int(mm * 1000 / self.vel)

    def programar(self, id_pieza, salida, ahora):
        if salida == 4:                   # rechazo: ninguna compuerta se mueve
            llegada = ahora + max(0, self.ms_hasta(DIST_FIN_MM) - LATENCIA_MS)
            self.programa.append([llegada, "div", None, id_pieza, 4])
            return
        k = salida - 1
        llegada = ahora + max(0, self.ms_hasta(DIST_MM[k]) - LATENCIA_MS)
        abrir = llegada - ADELANTO_MS
        cerrar = llegada + self.ms_hasta(PASO_MM)
        self.programa.append([abrir, "abrir", k, id_pieza, salida])
        self.programa.append([cerrar, "cerrar", k, id_pieza, salida])

    def paso(self):
        """Llamar seguido (cada pocos ms): ejecuta lo programado, vigila el latido y manda telemetría."""
        ahora = self.reloj()
        vencidos = [p for p in self.programa if _dif(ahora, p[0]) >= 0]
        if vencidos:
            self.programa = [p for p in self.programa if _dif(ahora, p[0]) < 0]
            vencidos.sort(key=lambda p: _dif(p[0], ahora))
            for t, tipo, k, id_pieza, salida in vencidos:
                if tipo == "abrir":
                    fin = t + ADELANTO_MS + self.ms_hasta(PASO_MM)
                    previo = self.abierta_hasta[k]
                    if previo is None or _dif(fin, previo) > 0:
                        self.abierta_hasta[k] = fin
                    self.mover(k, ACTIVO[k])
                    self.evento({"e": "div", "id": id_pieza, "out": salida})
                elif tipo == "cerrar":
                    hasta = self.abierta_hasta[k]
                    if hasta is not None and _dif(ahora, hasta) >= 0:
                        self.mover(k, REPOSO[k])
                        self.abierta_hasta[k] = None
                else:
                    self.evento({"e": "div", "id": id_pieza, "out": 4})
        if self.estado == "OPERANDO" and self.motor_desde is not None:
            if _dif(ahora, self.motor_desde) >= MOTOR_ARRANQUE_MS:
                self.poner_motor(MOTOR_PCT)
        if (self.estado == "OPERANDO" and self.ultimo_latido is not None
                and _dif(ahora, self.ultimo_latido) > LATIDO_MS):
            self.detener()
            self.estado = "FALLA"
            self.evento({"e": "err", "code": "sin_latido"})
        if _dif(ahora, self.ultima_tel) >= TEL_MS:
            self.ultima_tel = ahora
            v = self.vel if self.estado == "OPERANDO" else 0
            self.evento({"e": "tel", "v": v, "d": 0, "st": ESTADO_TEL[self.estado]})

    def detener(self):
        self.estado = "INACTIVO"
        self.poner_motor(0)
        self.motor_desde = None
        self.programa = []
        for i in range(3):
            self.mover(i, REPOSO[i])
            self.abierta_hasta[i] = None

    def evento(self, m):
        self.escribir(json.dumps(m) + "\n")


def main():
    import select
    from machine import PWM, Pin

    servos = [PWM(Pin(p), freq=50, duty_u16=0) for p in PINES_SERVO]   # sin pulso hasta la primera orden

    def mover(i, grados):
        grados = max(0, min(180, grados))
        us = PULSO_MIN_US + (PULSO_MAX_US - PULSO_MIN_US) * grados / 180
        servos[i].duty_ns(int(us * 1000))

    in1 = Pin(PIN_IN1, Pin.OUT, value=0)
    in2 = Pin(PIN_IN2, Pin.OUT, value=0)
    ena = PWM(Pin(PIN_ENA), freq=MOTOR_PWM_HZ, duty_u16=0)

    def motor(pct):
        if pct <= 0:
            ena.duty_u16(0)
            in1.value(0)
            in2.value(0)
            return
        in1.value(0 if SENTIDO_ADELANTE else 1)
        in2.value(1 if SENTIDO_ADELANTE else 0)
        ena.duty_u16(int(65535 * min(100, pct) / 100))

    ctl = Controlador(mover, time.ticks_ms, sys.stdout.write, motor)
    sondeo = select.poll()
    sondeo.register(sys.stdin, select.POLLIN)
    try:
        while True:
            while sondeo.poll(0):
                ctl.alimentar(sys.stdin.read(1))
            ctl.paso()
            time.sleep_ms(2)
    finally:                              # Stop de Thonny o cualquier error: banda parada y compuertas arriba
        motor(0)
        for i in range(3):
            mover(i, REPOSO[i])


if __name__ == "__main__":
    main()

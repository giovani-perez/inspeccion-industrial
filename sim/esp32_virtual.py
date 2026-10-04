"""ESP32 virtual: habla el mismo protocolo JSON que el real, sin hardware.

Imita lo básico de pyserial (write, read_all, in_waiting), así que el controlador de la PC no sabrá
si habla con este objeto o con el puerto COM real. El tiempo es simulado: se avanza con avanzar(),
y las pruebas no esperan de verdad.
"""
from collections import deque

from core import protocolo as p

PASO_MS = 10
TIEMPO_LATIDO_MS = 1000       # sin latidos durante este tiempo -> FALLA
PERIODO_TEL_MS = 100          # telemetría a 10 Hz
RETRASO_DESVIO_MS = 300       # entre que la pieza sale de la caja y la compuerta actúa
MM_POR_CUENTA = 0.04          # valor de ejemplo; el real sale de la calibración
ESTADO_TEL = {"INACTIVO": "IDLE", "OPERANDO": "RUN", "FALLA": "FAIL"}


class ESP32Virtual:
    def __init__(self):
        self.estado = "INACTIVO"
        self.ms = 0
        self.cola = deque()                  # (id, salida) de las piezas ya decididas por la visión
        self.vel_nom, self.vel_insp = 100, 60
        self.distancia_tof = 400
        self.encoder = 0
        self.compuertas = {1: -25, 2: -25, 3: -25}
        self.desvios = []                    # (id, salida) de cada desvío ejecutado
        self._ultimo_latido = None
        self._pendientes = []                # (ms de vencimiento, mensaje)
        self._salida = []                    # bytes listos para que la PC los lea
        self._lector = p.LectorLineas()

    # ---- interfaz tipo pyserial --------------------------------------------------------------
    def write(self, datos):
        for linea in self._lector.alimentar(datos):
            try:
                mensaje = p.decodificar(linea)
            except p.ErrorProtocolo:
                self._emitir(p.err("mensaje_invalido"))
                continue
            if "c" not in mensaje:               # un evento no es un comando
                self._emitir(p.err("mensaje_invalido"))
                continue
            self._atender(mensaje)
        return len(datos)

    def read_all(self):
        datos = b"".join(self._salida)
        self._salida = []
        return datos

    @property
    def in_waiting(self):
        return sum(len(x) for x in self._salida)

    def close(self):
        pass

    # ---- simulación --------------------------------------------------------------------------
    def avanzar(self, segundos):
        for _ in range(int(round(segundos * 1000 / PASO_MS))):
            self.ms += PASO_MS
            self._paso()

    def pieza_sale_de_caja(self):
        """Simula que el sensor IR detecta una pieza a la salida de la caja de luz."""
        if self.estado != "OPERANDO":
            return
        if self.cola:
            id_pieza, salida = self.cola.popleft()
        else:
            id_pieza, salida = 0, 4              # nadie decidió a tiempo -> rechazo por defecto
            self._emitir(p.rej("sin_decision"))
        self._emitir(p.exit_pieza(id_pieza, self.encoder))
        self._pendientes.append((self.ms + RETRASO_DESVIO_MS, p.div(id_pieza, salida)))

    # ---- internos ----------------------------------------------------------------------------
    def _emitir(self, mensaje):
        self._salida.append(p.codificar(mensaje))

    def _atender(self, m):
        c = m["c"]
        if c == "hb":
            self._ultimo_latido = self.ms
            if self.estado == "FALLA":
                self.estado = "INACTIVO"
        elif c == "run":
            if self.estado == "INACTIVO":
                self.estado = "OPERANDO"
                if self._ultimo_latido is None:      # al arrancar, el watchdog ya vigila
                    self._ultimo_latido = self.ms
            else:
                self._emitir(p.err("estado_invalido"))
        elif c == "stop":
            if self.estado == "OPERANDO":
                self.estado = "INACTIVO"
        elif c == "cls":
            self.cola.append((m["id"], m["out"]))
        elif c == "vel":
            self.vel_nom, self.vel_insp = m["nom"], m["insp"]
        elif c == "gate":
            if self.estado == "OPERANDO":
                self._emitir(p.err("compuerta_en_marcha"))
            else:
                self.compuertas[m["n"]] = m["a"]

    def _paso(self):
        if (self._ultimo_latido is not None and self.estado != "FALLA"
                and self.ms - self._ultimo_latido > TIEMPO_LATIDO_MS):
            self.estado = "FALLA"
            self._emitir(p.err("sin_latido"))
        if self.estado == "OPERANDO":
            self.encoder += int(self.vel_nom * PASO_MS / 1000 / MM_POR_CUENTA)
        if self.ms % PERIODO_TEL_MS == 0:
            v = self.vel_nom if self.estado == "OPERANDO" else 0
            self._emitir(p.tel(v, self.distancia_tof, ESTADO_TEL[self.estado]))
        vencidos = [x for x in self._pendientes if x[0] <= self.ms]
        for x in vencidos:
            self._pendientes.remove(x)
            self._emitir(x[1])
            self.desvios.append((x[1]["id"], x[1]["out"]))


def demo():
    """Conversación de ejemplo: python -m sim.esp32_virtual"""
    esp = ESP32Virtual()
    lector = p.LectorLineas()
    primera_tel = True

    def enviar(mensaje):
        print("PC    →", mensaje)
        esp.write(p.codificar(mensaje))

    def mostrar():
        nonlocal primera_tel
        for linea in lector.alimentar(esp.read_all()):
            m = p.decodificar(linea)
            if m["e"] == "tel":
                if not primera_tel:
                    continue                      # no inundar la pantalla con la telemetría
                primera_tel = False
            print("ESP32 →", m)

    enviar(p.hb())
    enviar(p.run())
    enviar(p.clase(57, 2))
    enviar(p.clase(58, 4))
    for paso in range(8):
        esp.avanzar(0.25)
        enviar(p.hb())
        if paso in (2, 5):
            esp.pieza_sale_de_caja()
        mostrar()
    print("--- la PC deja de mandar latidos ---")
    esp.avanzar(1.5)
    mostrar()
    print("Estado final:", esp.estado, "· desvíos:", esp.desvios)


if __name__ == "__main__":
    demo()

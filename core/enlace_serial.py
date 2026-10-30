"""Enlace con el ESP32 por puerto serie: manda comandos JSON, latido automático y lee eventos.

Acepta un puerto real ("COM5") o cualquier objeto con write() y read_all(), como el ESP32 virtual,
así las pruebas usan exactamente este mismo código.
"""
import time

from core import protocolo as p


class EnlaceESP32:
    def __init__(self, puerto=None, serie=None, baud=115200, latido_s=0.3, reloj=time.monotonic):
        if serie is None:
            import serial                       # pyserial
            serie = serial.Serial()
            serie.port = puerto
            serie.baudrate = baud
            serie.timeout = 0
            serie.dtr = False                   # que abrir el puerto no reinicie el ESP32
            serie.rts = False
            serie.open()
        self.serie = serie
        self.latido_s = latido_s
        self.reloj = reloj
        self.ultimo_latido = None
        self.lector = p.LectorLineas()
        self.lineas_ignoradas = 0                # arranque de MicroPython, ruido, etc.
        self.bitacora = []                       # últimas líneas TX/RX para la interfaz

    def enviar(self, mensaje):
        self.serie.write(p.codificar(mensaje))
        if mensaje.get("c") != "hb":
            self._anotar("TX " + p.codificar(mensaje).decode().strip())

    def atender(self):
        """Llamar en cada cuadro: manda el latido si toca y regresa los eventos recibidos."""
        ahora = self.reloj()
        if self.ultimo_latido is None or ahora - self.ultimo_latido >= self.latido_s:
            self.enviar(p.hb())
            self.ultimo_latido = ahora
        eventos = []
        for linea in self.lector.alimentar(self.serie.read_all() or b""):
            try:
                m = p.decodificar(linea)
            except p.ErrorProtocolo:
                self.lineas_ignoradas += 1
                continue
            if "e" not in m:
                self.lineas_ignoradas += 1
                continue
            if m["e"] != "tel":
                self._anotar("RX " + linea.decode(errors="replace"))
            eventos.append(m)
        return eventos

    def _anotar(self, texto):
        self.bitacora.append(texto)
        del self.bitacora[:-8]

    def cerrar(self):
        try:
            self.enviar(p.stop())
        finally:
            self.serie.close()

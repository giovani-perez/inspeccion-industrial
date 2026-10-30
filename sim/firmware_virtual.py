"""ESP32 virtual que corre el MISMO firmware (firmware/main.py) en la PC, en tiempo real.

Se comporta como un puerto serie (write, read_all, close), así que gui.linea y core.enlace_serial
no notan la diferencia. Sirve para probar la línea completa con la cámara sin tener el ESP32
ni los servos: las compuertas se ven en pantalla en lugar de moverse.

    python -m gui.linea --virtual
"""
import importlib.util
import time
from pathlib import Path

RUTA_FIRMWARE = Path(__file__).resolve().parent.parent / "firmware" / "main.py"


def cargar_firmware():
    spec = importlib.util.spec_from_file_location("firmware_main", RUTA_FIRMWARE)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class FirmwareVirtual:
    def __init__(self, reloj_ms=None):
        self.fw = cargar_firmware()
        inicio = time.monotonic()
        self.reloj_ms = reloj_ms or (lambda: int((time.monotonic() - inicio) * 1000))
        self.angulos = [None, None, None]
        self._salida = []
        self.ctl = self.fw.Controlador(self._mover, self.reloj_ms, self._salida.append)

    def _mover(self, i, grados):
        self.angulos[i] = grados

    def write(self, datos):
        self.ctl.alimentar(datos.decode() if isinstance(datos, bytes) else datos)
        return len(datos)

    def read_all(self):
        self.ctl.paso()                       # en el ESP32 real esto lo hace su ciclo principal
        datos = "".join(self._salida).encode()
        self._salida.clear()
        return datos

    def compuertas_abajo(self):
        """[True/False] por compuerta: True si está en posición de desvío."""
        return [a == act for a, act in zip(self.angulos, self.fw.ACTIVO)]

    def close(self):
        pass

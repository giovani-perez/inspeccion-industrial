"""El ESP32 virtual corre el firmware real detrás del mismo enlace serial que usa la interfaz."""
from core import protocolo as p
from core.enlace_serial import EnlaceESP32
from sim.firmware_virtual import FirmwareVirtual


class Reloj:
    def __init__(self):
        self.ms = 0


def armar():
    r = Reloj()
    esp = FirmwareVirtual(reloj_ms=lambda: r.ms)
    enlace = EnlaceESP32(serie=esp, reloj=lambda: r.ms / 1000)
    return r, esp, enlace


def correr(r, enlace, ms):
    eventos = []
    for _ in range(ms // 10):
        r.ms += 10
        eventos += enlace.atender()
    return eventos


def test_telemetria_en_reposo():
    r, esp, enlace = armar()
    evs = correr(r, enlace, 500)
    assert any(e["e"] == "tel" and e["st"] == "IDLE" for e in evs)
    assert esp.compuertas_abajo() == [False, False, False]


def test_pieza_a_la_salida_2_baja_la_compuerta_2_y_confirma():
    r, esp, enlace = armar()
    enlace.enviar(p.run())
    enlace.enviar(p.clase(7, 2))
    evs, vio_abajo = [], False
    for _ in range(600):
        evs += correr(r, enlace, 10)
        vio_abajo |= esp.compuertas_abajo()[1]
    assert vio_abajo
    assert {"e": "div", "id": 7, "out": 2} in evs
    assert not any(e["e"] == "err" for e in evs)          # el latido automático evita el watchdog
    assert esp.compuertas_abajo() == [False, False, False]

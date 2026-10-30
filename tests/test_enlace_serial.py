from core import protocolo as p
from core.enlace_serial import EnlaceESP32
from sim.esp32_virtual import ESP32Virtual


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def nuevo():
    esp, reloj = ESP32Virtual(), Reloj()
    return esp, reloj, EnlaceESP32(serie=esp, reloj=reloj)


def test_manda_latido_al_inicio_y_cada_300_ms():
    esp, reloj, enlace = nuevo()
    enlace.atender()
    enlace.enviar(p.run())
    for _ in range(10):                       # 3 s simulados con latido
        reloj.t += 0.3
        esp.avanzar(0.3)
        enlace.atender()
    assert esp.estado == "OPERANDO"


def test_sin_atender_el_esp32_pasa_a_falla_y_se_reporta():
    esp, reloj, enlace = nuevo()
    enlace.atender()
    enlace.enviar(p.run())
    esp.avanzar(1.5)
    eventos = enlace.atender()
    assert {"e": "err", "code": "sin_latido"} in eventos


def test_cls_llega_y_regresa_la_confirmacion():
    esp, reloj, enlace = nuevo()
    enlace.atender()
    enlace.enviar(p.run())
    enlace.enviar(p.clase(7, 2))
    esp.pieza_sale_de_caja()
    esp.avanzar(0.5)
    eventos = enlace.atender()
    assert {"e": "div", "id": 7, "out": 2} in eventos
    assert any(l.startswith("TX") and '"cls"' in l for l in enlace.bitacora)


def test_ignora_lineas_que_no_son_del_protocolo():
    esp, reloj, enlace = nuevo()
    esp._salida.append(b"MPY: soft reboot\r\n")
    esp._salida.append(b'{"e":"estop"}\n')
    eventos = enlace.atender()
    assert eventos == [{"e": "estop"}]
    assert enlace.lineas_ignoradas == 1

"""Pruebas de la lógica del firmware (firmware/main.py) corriendo en Python normal, sin ESP32."""
import importlib.util
import json
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "firmware" / "main.py"
spec = importlib.util.spec_from_file_location("firmware_main", RUTA)
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)


class Banco:
    """Reloj, servos y salida falsos para el Controlador."""

    def __init__(self):
        self.ms = 0
        self.angulos = [None, None, None]
        self.salida = []
        self.motor = []                   # historial de porcentajes mandados al motor
        self.ctl = fw.Controlador(self.mover, lambda: self.ms, self.salida.append, self.motor.append)

    def mover(self, i, grados):
        self.angulos[i] = grados

    def enviar(self, m):
        self.ctl.alimentar(json.dumps(m) + "\n")

    def avanzar(self, ms, latido=True):
        for _ in range(ms // 10):
            self.ms += 10
            if latido and self.ms % 300 == 0:
                self.enviar({"c": "hb"})
            self.ctl.paso()

    def eventos(self, tipo=None):
        evs = [json.loads(s) for s in self.salida]
        self.salida.clear()
        return [e for e in evs if tipo is None or e["e"] == tipo]


def test_arranca_con_las_tres_compuertas_en_reposo():
    b = Banco()
    assert b.angulos == fw.REPOSO


def test_compuerta_baja_a_tiempo_y_regresa_sola():
    b = Banco()
    b.enviar({"c": "run"})
    b.enviar({"c": "cls", "id": 1, "out": 2})
    llegada = b.ctl.ms_hasta(fw.DIST_MM[1]) - fw.LATENCIA_MS
    b.avanzar(llegada - fw.ADELANTO_MS - 20)
    assert b.angulos[1] == fw.REPOSO[1]                      # todavía no
    b.avanzar(40)
    assert b.angulos[1] == fw.ACTIVO[1]                      # bajó antes de que llegue la pieza
    assert b.eventos("div") == [{"e": "div", "id": 1, "out": 2}]
    b.avanzar(fw.ADELANTO_MS + b.ctl.ms_hasta(fw.PASO_MM) + 20)
    assert b.angulos[1] == fw.REPOSO[1]                      # regresó sola
    assert b.angulos[0] == fw.REPOSO[0] and b.angulos[2] == fw.REPOSO[2]


def test_sigue_leyendo_comandos_mientras_una_compuerta_esta_abajo():
    b = Banco()
    b.enviar({"c": "run"})
    b.enviar({"c": "cls", "id": 1, "out": 1})
    b.avanzar(b.ctl.ms_hasta(fw.DIST_MM[0]))
    assert b.angulos[0] == fw.ACTIVO[0]
    b.enviar({"c": "cls", "id": 2, "out": 3})                # llega con la compuerta 1 abajo
    b.avanzar(b.ctl.ms_hasta(fw.DIST_MM[2]))
    ids = [e["id"] for e in b.eventos("div")]
    assert ids == [1, 2]


def test_rechazo_no_mueve_ninguna_compuerta_y_se_confirma():
    b = Banco()
    b.enviar({"c": "run"})
    b.enviar({"c": "cls", "id": 9, "out": 4})
    b.avanzar(b.ctl.ms_hasta(fw.DIST_FIN_MM))
    assert b.angulos == fw.REPOSO
    assert b.eventos("div") == [{"e": "div", "id": 9, "out": 4}]


def test_dos_piezas_seguidas_a_la_misma_compuerta_la_mantienen_abajo():
    b = Banco()
    b.enviar({"c": "run"})
    b.enviar({"c": "cls", "id": 1, "out": 1})
    b.avanzar(600)
    b.enviar({"c": "cls", "id": 2, "out": 1})
    primera_cierre = b.ctl.ms_hasta(fw.DIST_MM[0]) - fw.LATENCIA_MS + b.ctl.ms_hasta(fw.PASO_MM)
    b.avanzar(primera_cierre - 600 + 50)
    assert b.angulos[0] == fw.ACTIVO[0]                      # no se cerró entre las dos piezas
    b.avanzar(2000)
    assert b.angulos[0] == fw.REPOSO[0]


def test_sin_latido_cierra_todo_y_pasa_a_falla():
    b = Banco()
    b.enviar({"c": "run"})
    b.enviar({"c": "cls", "id": 1, "out": 3})
    b.avanzar(1200, latido=False)
    assert b.ctl.estado == "FALLA"
    assert {"e": "err", "code": "sin_latido"} in b.eventos("err")
    b.avanzar(5000, latido=False)
    assert b.angulos == fw.REPOSO                            # lo programado se canceló
    b.enviar({"c": "hb"})
    assert b.ctl.estado == "INACTIVO"


def test_cls_con_la_banda_detenida_responde_error():
    b = Banco()
    b.enviar({"c": "cls", "id": 1, "out": 1})
    assert {"e": "err", "code": "estado_invalido"} in b.eventos("err")


def test_mensajes_invalidos_no_tumban_el_firmware():
    b = Banco()
    for linea in ["hola", '{"c":"cls","id":1,"out":7}', '{"c":"cls","id":true,"out":1}', '{"x":1}']:
        b.ctl.alimentar(linea + "\n")
    assert [e["code"] for e in b.eventos("err")] == ["mensaje_invalido"] * 4
    b.enviar({"c": "run"})
    assert b.ctl.estado == "OPERANDO"


def test_compuerta_manual_solo_con_la_banda_detenida():
    b = Banco()
    b.enviar({"c": "gate", "n": 2, "a": 45})
    assert b.angulos[1] == 45
    b.enviar({"c": "run"})
    b.enviar({"c": "gate", "n": 2, "a": 90})
    assert b.angulos[1] == 45
    assert {"e": "err", "code": "compuerta_en_marcha"} in b.eventos("err")


def test_los_eventos_del_firmware_cumplen_el_protocolo_de_la_pc():
    from core import protocolo as p
    b = Banco()
    b.enviar({"c": "run"})
    b.enviar({"c": "cls", "id": 3, "out": 2})
    b.enviar({"c": "nada"})
    b.avanzar(4000)
    for linea in b.salida:
        p.decodificar(linea)                                  # lanza error si algo no cumple


def test_velocidad_cambia_los_tiempos():
    b = Banco()
    b.enviar({"c": "vel", "nom": 50, "insp": 50})
    assert b.ctl.ms_hasta(100) == 2000


def test_motor_parado_al_encender():
    b = Banco()
    assert b.motor == [0]


def test_run_arranca_con_patada_y_baja_a_la_potencia_de_marcha():
    b = Banco()
    b.enviar({"c": "run"})
    assert b.motor[-1] == 100
    b.avanzar(fw.MOTOR_ARRANQUE_MS + 20)
    assert b.motor[-1] == fw.MOTOR_PCT
    b.avanzar(1000)
    assert b.motor == [0, 100, fw.MOTOR_PCT]          # no se reenvía el mismo valor en cada ciclo


def test_stop_para_el_motor():
    b = Banco()
    b.enviar({"c": "run"})
    b.avanzar(500)
    b.enviar({"c": "stop"})
    assert b.motor[-1] == 0


def test_sin_latido_para_el_motor():
    b = Banco()
    b.enviar({"c": "run"})
    b.avanzar(fw.LATIDO_MS + 100, latido=False)
    assert b.motor[-1] == 0
    assert any(e.get("code") == "sin_latido" for e in b.eventos("err"))


def test_mover_compuerta_a_mano_no_arranca_el_motor():
    b = Banco()
    b.enviar({"c": "gate", "n": 1, "a": 45})
    b.avanzar(300)
    assert b.motor == [0]

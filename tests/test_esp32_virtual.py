from core import protocolo as p
from sim.esp32_virtual import ESP32Virtual


def enviar(esp, mensaje):
    esp.write(p.codificar(mensaje))


def eventos(esp):
    lector = p.LectorLineas()
    return [p.decodificar(linea) for linea in lector.alimentar(esp.read_all())]


def sin_tel(lista):
    return [m for m in lista if m["e"] != "tel"]


def arrancar():
    esp = ESP32Virtual()
    enviar(esp, p.hb())
    enviar(esp, p.run())
    return esp


def test_arranca_inactivo_sin_vigilar_latidos():
    esp = ESP32Virtual()
    esp.avanzar(3)
    assert esp.estado == "INACTIVO"
    assert sin_tel(eventos(esp)) == []


def test_run_y_stop_cambian_el_estado():
    esp = arrancar()
    assert esp.estado == "OPERANDO"
    enviar(esp, p.stop())
    assert esp.estado == "INACTIVO"


def test_telemetria_a_10_hz_con_estado_y_velocidad():
    esp = arrancar()
    esp.avanzar(1.0)
    tel = [m for m in eventos(esp) if m["e"] == "tel"]
    assert 9 <= len(tel) <= 11
    assert tel[-1]["st"] == "RUN" and tel[-1]["v"] == 100


def test_sin_latidos_pasa_a_falla_y_un_latido_la_recupera():
    esp = arrancar()
    esp.avanzar(1.2)
    assert esp.estado == "FALLA"
    assert {"e": "err", "code": "sin_latido"} in eventos(esp)
    enviar(esp, p.hb())
    assert esp.estado == "INACTIVO"


def test_los_latidos_mantienen_la_banda_en_marcha():
    esp = arrancar()
    for _ in range(10):
        esp.avanzar(0.5)
        enviar(esp, p.hb())
    assert esp.estado == "OPERANDO"


def test_pieza_clasificada_se_desvia_a_su_salida():
    esp = arrancar()
    enviar(esp, p.clase(57, 2))
    esp.pieza_sale_de_caja()
    esp.avanzar(0.5)
    ev = sin_tel(eventos(esp))
    assert [m["e"] for m in ev] == ["exit", "div"]
    assert ev[0]["id"] == 57 and ev[1] == {"e": "div", "id": 57, "out": 2}
    assert esp.desvios == [(57, 2)]


def test_la_cola_respeta_el_orden_de_llegada():
    esp = arrancar()
    enviar(esp, p.clase(1, 3))
    enviar(esp, p.clase(2, 1))
    esp.pieza_sale_de_caja()
    esp.avanzar(0.1)
    esp.pieza_sale_de_caja()
    esp.avanzar(0.5)
    assert esp.desvios == [(1, 3), (2, 1)]


def test_cola_vacia_manda_la_pieza_a_rechazo():
    esp = arrancar()
    esp.pieza_sale_de_caja()
    esp.avanzar(0.5)
    ev = sin_tel(eventos(esp))
    assert {"e": "rej", "why": "sin_decision"} in ev
    assert esp.desvios == [(0, 4)]


def test_con_la_banda_detenida_no_hay_piezas():
    esp = ESP32Virtual()
    esp.pieza_sale_de_caja()
    esp.avanzar(0.5)
    assert esp.desvios == []


def test_mensaje_invalido_responde_error_y_no_se_cae():
    esp = ESP32Virtual()
    esp.write(b"basura\n")
    assert eventos(esp) == [{"e": "err", "code": "mensaje_invalido"}]
    enviar(esp, p.run())
    assert esp.estado == "OPERANDO"


def test_mensaje_enviado_en_dos_pedazos():
    esp = ESP32Virtual()
    esp.write(b'{"c":"ru')
    assert esp.estado == "INACTIVO"
    esp.write(b'n"}\n')
    assert esp.estado == "OPERANDO"


def test_compuerta_manual_solo_con_la_banda_detenida():
    esp = ESP32Virtual()
    enviar(esp, p.gate(1, 45))
    assert esp.compuertas[1] == 45
    enviar(esp, p.run())
    enviar(esp, p.gate(2, 45))
    assert esp.compuertas[2] == -25
    assert {"e": "err", "code": "compuerta_en_marcha"} in eventos(esp)


def test_no_se_puede_arrancar_dos_veces():
    esp = arrancar()
    enviar(esp, p.run())
    assert {"e": "err", "code": "estado_invalido"} in eventos(esp)

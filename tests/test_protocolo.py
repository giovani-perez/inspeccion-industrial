import pytest

from core import protocolo as p

MENSAJES_VALIDOS = [
    p.hb(), p.run(), p.stop(), p.clase(57, 2), p.vel(100, 60), p.gate(1, 45),
    p.tel(98, 143, "RUN"), p.exit_pieza(57, 18231), p.div(57, 3), p.rej("sin_decision"),
    p.estop(), p.err("tof"),
]


@pytest.mark.parametrize("mensaje", MENSAJES_VALIDOS)
def test_ida_y_vuelta(mensaje):
    assert p.decodificar(p.codificar(mensaje)) == mensaje


def test_codificar_es_compacto_y_termina_en_salto_de_linea():
    assert p.codificar(p.clase(57, 2)) == b'{"c":"cls","id":57,"out":2}\n'


def test_decodificar_acepta_str_y_retorno_de_carro():
    assert p.decodificar('{"c":"hb"}\r\n') == {"c": "hb"}


@pytest.mark.parametrize("linea", [
    b"esto no es json",
    b"[1, 2, 3]",
    b'{"x": 1}',                                # sin 'c' ni 'e'
    b'{"c": "hb", "e": "tel"}',                 # con las dos claves
    b'{"c": "volar"}',                          # comando desconocido
    b'{"c": "cls", "id": 57}',                  # falta 'out'
    b'{"c": "cls", "id": "57", "out": 2}',      # tipo inválido
    b'{"c": "cls", "id": true, "out": 2}',      # bool no cuenta como número
    b'{"c": "hb", "extra": 1}',                 # campo no permitido
    b'{"c": "cls", "id": 1, "out": 5}',         # salida fuera de rango
    b'{"c": "gate", "n": 4, "a": 10}',          # compuerta inexistente
    b'{"c": "gate", "n": 1, "a": 120}',         # ángulo fuera de rango
    b'{"c": "vel", "nom": 0, "insp": 60}',      # velocidad no positiva
    b"\xff\xfe",                                # no es UTF-8
])
def test_mensajes_invalidos_se_rechazan(linea):
    with pytest.raises(p.ErrorProtocolo):
        p.decodificar(linea)


def test_codificar_no_deja_enviar_mensajes_invalidos():
    with pytest.raises(p.ErrorProtocolo):
        p.codificar({"c": "cls", "id": 1, "out": 9})


def test_lector_junta_fragmentos():
    lector = p.LectorLineas()
    assert lector.alimentar(b'{"c":"h') == []
    assert lector.alimentar(b'b"}\n') == [b'{"c":"hb"}']


def test_lector_entrega_varias_lineas_y_descarta_vacias():
    lector = p.LectorLineas()
    assert lector.alimentar(b'{"c":"hb"}\r\n\r\n{"c":"run"}\n{"c":"st') == [b'{"c":"hb"}', b'{"c":"run"}']
    assert lector.alimentar(b'op"}\n') == [b'{"c":"stop"}']


def test_lector_descarta_basura_sin_salto_de_linea():
    lector = p.LectorLineas()
    assert lector.alimentar(b"x" * (p.MAX_LINEA + 10)) == []
    assert lector.alimentar(b'{"c":"hb"}\n') == [b'{"c":"hb"}']

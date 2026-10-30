from core.seguimiento import Seguidor


def recorrido(seguidor, clases, x0=100, paso=20, y=300):
    """Mueve una pieza de izquierda a derecha; clases[i] es la forma detectada en el cuadro i."""
    decisiones = []
    for i, clase in enumerate(clases):
        decisiones += seguidor.actualizar([(clase, x0 + paso * i, y)])
    return decisiones


def test_una_pieza_se_decide_una_sola_vez_al_cruzar_la_linea():
    s = Seguidor(linea_x=400)
    d = recorrido(s, ["triangulo"] * 30)
    assert len(d) == 1
    assert d[0].clase == "triangulo" and d[0].salida == 3


def test_la_mayoria_de_votos_gana_aunque_haya_cuadros_erroneos():
    s = Seguidor(linea_x=400)
    clases = ["circulo"] * 12 + ["rechazo"] * 2 + ["circulo"] * 10
    d = recorrido(s, clases)
    assert [x.clase for x in d] == ["circulo"]
    assert d[0].confianza > 0.8


def test_confianza_baja_manda_a_rechazo():
    s = Seguidor(linea_x=400)
    d = recorrido(s, ["cuadrado", "triangulo"] * 12)
    assert d[0].clase == "rechazo" and d[0].salida == 4


def test_pocos_votos_manda_a_rechazo():
    s = Seguidor(linea_x=400, votos_min=5)
    d = recorrido(s, ["circulo"] * 6, x0=340)
    assert d[0].clase == "rechazo"


def test_dos_piezas_reciben_dos_decisiones_con_id_distinto():
    s = Seguidor(linea_x=400)
    decisiones = []
    for i in range(40):
        det = [("cuadrado", 60 + 20 * i, 200)]
        if i >= 12:
            det.append(("circulo", 60 + 20 * (i - 12), 200))
        decisiones += s.actualizar(det)
    assert [d.clase for d in decisiones] == ["cuadrado", "circulo"]
    assert decisiones[0].id != decisiones[1].id


def test_pieza_que_desaparece_antes_de_la_linea_no_se_decide():
    s = Seguidor(linea_x=400)
    d = recorrido(s, ["circulo"] * 8)
    for _ in range(20):
        d += s.actualizar([])
    assert d == []


def test_banda_en_sentido_contrario():
    s = Seguidor(linea_x=400, sentido=-1)
    d = []
    for i in range(30):
        d += s.actualizar([("cuadrado", 700 - 20 * i, 300)])
    assert [x.clase for x in d] == ["cuadrado"]


def test_pieza_que_aparece_pasada_la_linea_no_se_decide():
    s = Seguidor(linea_x=400)
    d = recorrido(s, ["circulo"] * 10, x0=500)
    assert d == []

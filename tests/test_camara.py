"""Pruebas de core/camara.py con una cámara simulada (no hace falta la C270)."""
import cv2
import pytest

from core import camara

MJPG = cv2.VideoWriter_fourcc(*"MJPG")
YUY2 = cv2.VideoWriter_fourcc(*"YUY2")


def camara_falsa(acepta):
    """Fabrica un VideoCapture falso. `acepta` decide con qué método el driver toma MJPG:
    'parametros', 'formato_primero', 'tamano_primero' o None (nunca)."""

    class Falsa:
        abiertas = []

        def __init__(self, indice, api=None, params=None):
            self.props = {cv2.CAP_PROP_FOURCC: YUY2, cv2.CAP_PROP_FRAME_WIDTH: 640,
                          cv2.CAP_PROP_FRAME_HEIGHT: 480}
            self.orden = []
            self.liberada = False
            if params:
                pares = dict(zip(params[::2], params[1::2]))
                self.props.update(pares)
                if acepta != "parametros":
                    self.props[cv2.CAP_PROP_FOURCC] = YUY2
            Falsa.abiertas.append(self)

        def isOpened(self):
            return True

        def set(self, prop, valor):
            self.orden.append(prop)
            if prop == cv2.CAP_PROP_FOURCC:
                tamano_antes = cv2.CAP_PROP_FRAME_WIDTH in self.orden[:-1]
                if (acepta == "formato_primero" and not tamano_antes) or \
                   (acepta == "tamano_primero" and tamano_antes):
                    self.props[prop] = valor
                return True
            self.props[prop] = valor
            return True

        def get(self, prop):
            return self.props.get(prop, 0)

        def release(self):
            self.liberada = True

    return Falsa


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(camara.os, "name", "nt")


@pytest.mark.parametrize("metodo", ["parametros", "formato_primero", "tamano_primero"])
def test_encuentra_el_metodo_que_acepta_mjpg(monkeypatch, windows, metodo):
    falsa = camara_falsa(metodo)
    monkeypatch.setattr(camara.cv2, "VideoCapture", falsa)
    cap = camara.abrir(1, -7, avisar=False)
    assert camara.formato(cap) == "MJPG"
    assert camara.tamano(cap) == (1280, 720)
    assert cap.get(cv2.CAP_PROP_EXPOSURE) == -7
    assert cap.get(cv2.CAP_PROP_AUTO_EXPOSURE) == 0.25
    # las aperturas que fallaron se liberan; la elegida no
    assert all(c.liberada for c in falsa.abiertas[:-1]) and not falsa.abiertas[-1].liberada


def test_sin_mjpg_usa_640x480(monkeypatch, windows):
    falsa = camara_falsa(None)
    monkeypatch.setattr(camara.cv2, "VideoCapture", falsa)
    cap = camara.abrir(1, -8, avisar=False)
    assert camara.tamano(cap) == camara.RESPALDO
    assert cap.get(cv2.CAP_PROP_EXPOSURE) == -8


def test_si_no_abre_regresa_none(monkeypatch, windows):
    class Cerrada:
        def __init__(self, *a, **k):
            pass

        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr(camara.cv2, "VideoCapture", Cerrada)
    assert camara.abrir(3, -7, avisar=False) is None


def test_formato_texto():
    class Cap:
        def get(self, prop):
            return MJPG

    assert camara.formato(Cap()) == "MJPG"

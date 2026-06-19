from tasks import somar, fatorial

def test_somar():
    resultado = somar.apply(args=(3, 5)).get()
    assert resultado == 8

def test_fatorial():
    resultado = fatorial.apply(args=(5,)).get()
    assert resultado == 120
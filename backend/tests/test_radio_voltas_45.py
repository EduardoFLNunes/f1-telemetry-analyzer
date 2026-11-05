"""Pedido 45, Parte B: o numero da volta (um so) e o erro do WebSocket."""
import asyncio

import pytest

from core.live.volta_ao_vivo import VoltaAoVivo
from core.websocket_server import ConnectionManager


class _Bus:
    def schedule(self, *a, **k):
        pass


class _Lenta:
    """Um cliente de WebSocket que demora: dois envios ao mesmo tempo disputam a trava."""

    def __init__(self):
        self.enviados = 0

    async def send_text(self, _):
        await asyncio.sleep(0.01)
        self.enviados += 1


def test_a_trava_do_envio_nasce_no_laco_que_envia_e_nao_ao_importar():
    # No modulo, o gerente nasce fora de qualquer laco (o `manager` global); no Python 3.9 um
    # `asyncio.Lock()` criado ali guarda outro laco, e a disputa dava "attached to a different loop".
    gerente = ConnectionManager()
    gerente.active_connections.append(_Lenta())
    gerente.send_timeout_seconds = 2.0

    async def dois_envios():
        await asyncio.gather(gerente.broadcast({"type": "a"}), gerente.broadcast({"type": "b"}),
                             gerente.broadcast({"type": "c"}))

    asyncio.run(dois_envios())          # um laco novo, como o do uvicorn
    assert gerente.active_connections[0].enviados == 3
    asyncio.run(dois_envios())          # e outro: a trava acompanha o laco
    assert gerente.active_connections[0].enviados == 6


def _volta_ao_vivo(pos):
    return VoltaAoVivo(lambda: pos, lambda: 100)


def test_a_volta_fechada_tem_o_numero_de_antes_da_passagem():
    pos = {"s": 10.0, "comprimento": 100.0, "lateral": 0.0, "volta": 9, "tempoDaVolta": 1.0, "desdeALinha": True}
    v = _volta_ao_vivo(pos)
    for s in (10.0, 60.0, 99.0):
        pos["s"] = s
        v.on_frame({"speedKmh": 100.0})
    # o contador do jogo ja adiantou no quadro da passagem: a volta que fechou continua a 9
    pos.update(s=1.0, volta=10)
    v.on_frame({"speedKmh": 100.0})
    assert v.ultima_fechada()["volta"] == 9


def test_o_coach_numera_a_volta_pelo_contador_no_meio_dela():
    from core.live import driving_coach as dc

    coach = dc.LiveDrivingCoach(_Bus(), model_provider=lambda _: None)
    coach._last_progress = 0.2
    coach._numero_no_meio = None
    # antes do meio da volta, vale o contador do quadro
    assert coach._numero_da_volta({"lap_number": 9}) == 9
    coach._numero_no_meio = 9.0
    # depois do meio, o contador pode adiantar perto da linha: a volta continua a 9
    assert coach._numero_da_volta({"lap_number": 10}) == 9
    # uma volta nova na linha esquece o numero
    coach._start_lap(10.0, 0, 0.0, 0.0, at_line=True)
    assert coach._numero_no_meio is None
    assert coach._numero_da_volta({"lap_number": 10}) == 10


@pytest.mark.parametrize("progresso,esperado", [(0.1, None), (0.7, 5.0)])
def test_recomecar_fora_da_linha_guarda_o_numero_so_depois_do_meio(progresso, esperado):
    from core.live import driving_coach as dc

    coach = dc.LiveDrivingCoach(_Bus(), model_provider=lambda _: None)
    coach._start_lap(5.0, 3, 0.0, progresso)
    assert coach._numero_no_meio == esperado


# ------------------------------------------------------------------ Parte C ---

from core.radio.analise import causa_da_curva, curva_da_volta  # noqa: E402
from core.radio.texto import fala_da_curva, frase_da_tendencia, mensagem_da_curva, mensagem_de_resumo  # noqa: E402


def _medida(perda=0.7, freada=None, minima=None, tracado=None, saida=None, trechos=None, lado="esquerda"):
    return {"curva": "C01", "lado": lado, "perdaS": perda, "freadaM": freada, "minimaKmh": minima, "tracadoM": tracado,
            "saidaKmh": saida, "trechos": trechos or {"reta": 0.0, "freada": 0.0, "minima": 0.0, "saida": 0.0}}


def test_a_causa_e_a_medida_do_trecho_que_mais_perdeu():
    trechos = {"reta": 0.2, "freada": 0.5, "minima": 0.1, "saida": -0.1}
    assert causa_da_curva(_medida(freada=-15.0, trechos=trechos)) == {
        "trecho": "freada", "perdaTrechoS": 0.5, "medida": "freada", "valor": -15.0}
    # abaixo do corte: so o trecho
    c = causa_da_curva(_medida(freada=-14.9, trechos=trechos))
    assert c["trecho"] == "freada" and c["medida"] is None


def test_na_minima_o_tracado_entra_depois_da_minima_e_o_lado_vem_da_curva():
    trechos = {"freada": 0.1, "minima": 0.5, "saida": 0.0}
    assert causa_da_curva(_medida(minima=-9.0, tracado=3.0, trechos=trechos))["medida"] == "minima"
    # curva a esquerda: mais a direita (negativo) e por fora
    c = causa_da_curva(_medida(minima=-1.0, tracado=-3.0, trechos=trechos))
    assert c["medida"] == "tracado" and c["lado"] == "fora"
    c = causa_da_curva(_medida(minima=-1.0, tracado=-3.0, trechos=trechos, lado="direita"))
    assert c["lado"] == "dentro"
    # uma minima mais alta que a referencia nao explica uma perda
    assert causa_da_curva(_medida(minima=9.0, tracado=0.5, trechos=trechos))["medida"] is None


def test_na_saida_so_conta_sair_mais_lento_acima_do_corte():
    trechos = {"freada": 0.0, "minima": 0.1, "saida": 0.4}
    assert causa_da_curva(_medida(saida=-8.0, trechos=trechos))["medida"] == "saida"
    assert causa_da_curva(_medida(saida=-7.9, trechos=trechos))["medida"] is None
    assert causa_da_curva(_medida(saida=9.0, trechos=trechos))["medida"] is None


def test_abaixo_de_1_decimo_nenhuma_curva_e_citada():
    assert curva_da_volta([_medida(perda=0.099)]) is None
    assert curva_da_volta([_medida(perda=0.1)])["curva"] == "C01"
    assert curva_da_volta(None) is None


CURVA_1 = {"curva": "C01", "lado": "esquerda", "perdaS": 0.7,
           "causa": {"trecho": "freada", "perdaTrechoS": 0.5, "medida": "freada", "valor": -15.0}}
CURVA_12 = {"curva": "C12", "lado": "esquerda", "perdaS": 0.4,
            "causa": {"trecho": "saida", "perdaTrechoS": 0.3, "medida": "saida", "valor": -8.0}}
CURVA_6 = {"curva": "C06", "lado": "direita", "perdaS": 0.5,
           "causa": {"trecho": "minima", "perdaTrechoS": 0.3, "medida": "tracado", "valor": 3.0, "lado": "fora"}}


def test_os_exemplos_do_pedido():
    atras = {"situacao": "atras", "difS": 0.3, "melhorS": 88.0}
    m = mensagem_de_resumo(7, 89.0, 84.8, "volta_ia", CURVA_1, atras)
    assert m["falas"][1] == "3 décimos atrás da sua melhor, 4,2 segundos atrás da IA. Curva 1: 7 décimos, freou 15 metros antes da IA."
    m = mensagem_de_resumo(8, 87.8, 84.8, "volta_ia", CURVA_12, {"situacao": "melhor", "difS": 0.2, "melhorS": 88.0})
    assert "Melhor volta, 2 décimos mais rápida. Curva 12: 4 décimos, saiu 8 quilômetros por hora mais lento." in m["falas"]
    m = mensagem_de_resumo(9, 89.1, 84.8, "volta_ia", CURVA_6, {"situacao": "atras", "difS": 1.1, "melhorS": 88.0})
    assert "1,1 segundo atrás da sua melhor. Curva 6: 5 décimos, passou 3 metros por fora no ápice." in m["falas"]
    m = mensagem_de_resumo(10, 96.4, 84.8, "volta_ia", None, {"situacao": "atras", "difS": 7.0, "melhorS": 89.4}, rodada=True)
    assert m["fala"] == "Volta com rodada: 1 minuto e 36,4 segundos, 7,0 segundos atrás da sua melhor."
    assert m["curva"] is None


def test_as_variantes_perdem_os_itens_de_baixo_para_cima():
    m = mensagem_de_resumo(7, 89.0, 84.8, "volta_ia", CURVA_1, {"situacao": "atras", "difS": 0.3, "melhorS": 88.7},
                           anterior_s=0.4)
    f = m["falas"]
    assert "Tempo:" in f[0] and "anterior" in f[0] and "da IA" in f[0]
    assert "Tempo:" not in f[1] and "anterior" in f[1]            # sai o tempo
    assert "anterior" not in f[2] and "4,2 segundos" in f[2]      # sai a anterior
    assert "4,2 segundos" not in f[3] and "freou 15 metros antes da IA" in f[3]   # sai a IA
    assert "antes." in f[4]                                        # sai o "da IA"
    assert f[-2] == "3 décimos atrás da sua melhor. Curva 1: 7 décimos."           # sai a causa
    assert f[-1] == "3 décimos atrás da sua melhor."                              # e a curva por ultimo
    assert m["falasComACausa"] == 5
    assert all("décimo" in x or "segundo" in x for x in f)         # a unidade nunca sai


def test_melhor_volta_e_recorde():
    m = mensagem_de_resumo(3, 88.0, 84.8, "volta_ia", None, {"situacao": "melhor", "difS": None, "melhorS": None})
    assert m["fala"].startswith("Melhor volta, 3,2 segundos atrás da IA")
    m = mensagem_de_resumo(3, 86.0, 84.8, "volta_ia", None, {"situacao": "recorde", "difS": 0.6, "melhorS": 86.6})
    assert m["fala"].startswith("Recorde pessoal, 6 décimos mais rápida")
    assert m["texto"].startswith("recorde pessoal, −0,600 s")


def test_a_curva_em_mensagem_propria_e_o_alto_do_replay():
    m = mensagem_da_curva(7, CURVA_1, "volta_ia")
    assert m["origem"] == "curva" and m["fala"] == "Curva 1: 7 décimos, freou 15 metros antes da IA."
    assert m["falas"][-1] == "Curva 1: 7 décimos."
    # o alto do replay: so o pedaco da curva, com os numeros da voz
    fala = "3 décimos atrás da sua melhor. Curva 1: 7 décimos, freou 15 metros antes da IA. Tempo: 1 minuto e 29,0 segundos."
    assert fala_da_curva(fala, "C01") == "Curva 1: 7 décimos, freou 15 metros antes da IA."
    duas = "Curva 1: perde 7 décimos por volta. Curva 12: perde 4 décimos por volta."
    assert fala_da_curva(duas, "C12") == "Curva 12: perde 4 décimos por volta."
    assert fala_da_curva(duas, "C03") is None


def test_a_tendencia_da_analise():
    assert frase_da_tendencia(89.0, 89.5) == "Média 5 décimos mais rápida que as 3 anteriores."
    assert frase_da_tendencia(90.2, 89.0) == "Média 1,2 segundo mais lenta que as 3 anteriores."
    assert frase_da_tendencia(89.0, 89.04) is None


# ------------------------------------------------------------- Parte E ---


def _radio_com_voltas(tmp_path):
    import numpy as np
    from tests.test_radio import L, _Pista, _pista_de_teste_com_uma_curva, _radio, _grade_de_teste

    track, pista, s = _pista_de_teste_com_uma_curva()
    estado = _Pista()
    tempo_ref = float(s[-1] / 50.0)
    estado.referencia = {**_grade_de_teste(s, 50.0, 0.0, 395, 430, 110.0), "tempoS": tempo_ref}
    radio = _radio(tmp_path, estado)
    radio._geometria = pista
    radio._referencia = lambda: {"tipo": "volta_ia", "tempoS": tempo_ref}

    def guardar(numero, velocidade, estado_da_volta="valida", motivo="válida", perda=0.3):
        g = _grade_de_teste(s, velocidade, 1.0, 385, 428, 100.0)
        tempo = float(s[-1] / velocidade)
        radio._grade_da_ultima = {"volta": numero, "grade": g, "tempoS": tempo}
        medidas = [{"curva": "C03", "lado": "esquerda", "perdaS": perda, "freadaM": -20.0, "minimaKmh": -3.0, "tracadoM": 0.2,
                    "saidaKmh": 0.0, "trechos": {"reta": 0.0, "freada": perda, "minima": 0.0, "saida": 0.0}}]
        radio._guardar_a_volta({"volta": numero, "tempoS": tempo}, estado_da_volta, motivo, medidas)
        return tempo

    return radio, guardar, np, L


def test_a_lista_tem_todas_as_voltas_com_o_estado_e_o_motivo(tmp_path):
    radio, guardar, _, _ = _radio_com_voltas(tmp_path)
    assert radio.voltas_da_sessao()["mensagem"] == "nenhuma volta fechada nesta sessão"
    tempo = guardar(2, 45.0)
    radio._melhor_s, radio._melhor_volta = tempo, 2
    guardar(3, 40.0, "rodada", "fora da análise: rodada (perdeu 7,0 s na C03)", 7.0)
    radio._guardar_a_volta({"volta": 5, "tempoS": 95.0}, "ia", "a IA pilotou parte da volta", None)
    lista = radio.voltas_da_sessao()
    assert [v["volta"] for v in lista["voltas"]] == [2, 3, 4, 5]
    assert lista["melhorVolta"] == 2 and lista["mensagem"] is None
    por = {v["volta"]: v for v in lista["voltas"]}
    assert por[2]["estado"] == "valida" and por[2]["difMelhorS"] == 0 and por[2]["temReplay"] is True
    assert por[3]["estado"] == "rodada" and por[3]["temReplay"] is True          # a rodada tambem toca
    assert por[5]["estado"] == "ia" and por[5]["temReplay"] is False             # a da IA fica fora
    assert por[4]["tempoS"] is None and "não fechou na linha" in por[4]["motivo"]  # o buraco tem motivo


def test_o_replay_de_qualquer_volta_e_de_qualquer_curva(tmp_path):
    radio, guardar, np, _ = _radio_com_voltas(tmp_path)
    guardar(2, 45.0)
    guardar(3, 40.0, "rodada", "fora da análise: rodada", 7.0)
    curva = radio.replay_da_volta(2, "C03")["curvas"][0]
    assert curva["curva"] == "C03" and curva["volta"] == 2 and curva["aviso"] is None
    assert curva["causa"]["trecho"] == "freada"
    assert curva["textoDaVoz"] == "Curva 3: 3 décimos, freou 20 metros antes da IA."
    inteira = radio.replay_da_volta(2)["curvas"][0]
    assert inteira["voltaInteira"] is True and inteira["curva"] is None
    assert len(inteira["linhas"]["voce"]) == radio._geometria.track.size
    assert next(c for c in inteira["curvasNaVolta"] if c["curva"] == "C03")["perdaS"] == 0.3
    tempos = [p[2] for p in inteira["linhas"]["voce"]]
    assert all(b >= a for a, b in zip(tempos, tempos[1:]))
    assert radio.replay_da_volta(3, "C03")["curvas"][0]["aviso"] == "fora da análise: rodada"
    assert radio.replay_da_volta(99) is None
    # a volta guardada ocupa pouco: 5 linhas em float32
    assert radio._voltas_da_sessao[0]["grade"]["elapsed"].dtype == np.float32


def test_a_melhor_da_sessao_para_o_minimapa(tmp_path):
    radio, guardar, _, _ = _radio_com_voltas(tmp_path)
    assert radio.melhor_da_sessao() == {"disponivel": False}
    tempo = guardar(2, 45.0)
    radio._melhor_s, radio._melhor_volta = tempo, 2
    dados = radio.melhor_da_sessao()
    assert dados["disponivel"] and dados["volta"] == 2 and len(dados["pontos"][0]) == 3


def test_recorde_so_contra_o_store_e_sem_ele_e_melhor_volta(tmp_path):
    radio, _, _, _ = _radio_com_voltas(tmp_path)
    assert radio._melhor_da_volta(90.0, True)["situacao"] == "melhor"
    radio._melhor_do_store = lambda: 89.0
    assert radio._melhor_da_volta(90.0, True)["situacao"] == "melhor"
    r = radio._melhor_da_volta(88.5, True)
    assert r["situacao"] == "recorde" and r["difS"] == 0.5
    radio._melhor_s = 90.0
    assert radio._melhor_da_volta(91.0, True) == {"situacao": "atras", "difS": 1.0, "melhorS": 90.0}
    # a volta que nao conta nunca e a melhor
    assert radio._melhor_da_volta(80.0, False)["situacao"] == "atras"


def test_a_curva_que_nao_coube_vai_numa_mensagem_propria_e_sai_da_fila_se_passar(tmp_path):
    from tests.test_radio import _Pista, _radio, _esperar_o_audio

    estado = _Pista()
    # Toda fala do resumo com a causa passa do limite: fica a que nao tem a curva.
    radio = _radio(tmp_path, estado, falar=lambda texto, destino: 9.0 if "Curva" in texto else 2.0)
    pior = {"curva": "C02", "lado": "direita", "perdaS": 0.7,
            "causa": {"trecho": "freada", "perdaTrechoS": 0.5, "medida": "freada", "valor": -15.0}}
    m = mensagem_de_resumo(7, 89.0, 84.8, "volta_ia", pior, {"situacao": "atras", "difS": 0.3, "melhorS": 88.7})
    m["_curvaDaVolta"] = pior
    radio._pendentes.append(radio._nova(m))
    _esperar_o_audio(radio)
    resumo = radio._pendentes[0]
    assert "Curva" not in resumo["fala"]
    estado.s = 800.0
    radio.on_frame({"speedKmh": 100.0})
    assert radio.contagem["curvaEmMensagemPropria"] == 1
    propria = radio._pendentes[-1]
    assert propria["origem"] == "curva" and propria["_curvaS"] == 2000.0
    # passou da curva antes de achar uma janela: sai da fila
    radio._ocupado_ate = estado.agora + 1000.0
    for s in (1900.0, 2100.0):
        estado.s = s
        radio.on_frame({"speedKmh": 100.0})
    assert radio.contagem["curvaSaiuDaFila"] == 1
    assert not any(x.get("origem") == "curva" for x in radio._pendentes)


def test_o_pedido_para_abrir_o_app(tmp_path, monkeypatch):
    import main
    from core.websocket_server import manager
    from routers import radio as rota

    radio, _, _, _ = _radio_com_voltas(tmp_path)
    monkeypatch.setattr(main, "radio_do_engenheiro", radio)
    monkeypatch.setattr(manager, "active_connections", [])
    # o app fechado: o botao diz isso
    assert asyncio.run(rota.post_abrir_no_app({"volta": 2})) == {"entregue": False, "motivo": "o app do Windows está fechado"}
    enviados = []

    class Cliente:
        async def send_text(self, texto):
            enviados.append(texto)

    monkeypatch.setattr(manager, "active_connections", [Cliente()])
    assert asyncio.run(rota.post_abrir_no_app({"volta": 2, "curva": "C03"}))["entregue"] is True
    assert '"type":"abrir_replay"' in enviados[0] and '"curva":"C03"' in enviados[0]


def test_a_volta_que_nao_comecou_na_linha_fica_guardada_para_o_replay():
    pos = {"s": 10.0, "comprimento": 100.0, "lateral": 0.0, "volta": 3, "tempoDaVolta": None, "desdeALinha": False}
    v = VoltaAoVivo(lambda: pos, lambda: 100)
    for s, cronometro in ((10.0, 5.0), (50.0, 6.0), (99.0, 7.0)):
        pos["s"] = s
        v.on_frame({"speedKmh": 100.0, "lap_time": cronometro})
    pos.update(s=1.0, volta=4, desdeALinha=True, tempoDaVolta=0.0)
    v.on_frame({"speedKmh": 100.0, "lap_time": 0.1})
    assert v.ultima_fechada() is None                  # para o coach e o radio, ela nao fechou
    parcial = v.ultima_parcial()
    assert parcial["volta"] == 3 and parcial["tempoS"] == 2.0
    assert parcial["linhas"]["elapsed"][50] == 1.0     # o tempo corrido, no lugar do relogio desde a linha


def test_o_radio_lista_e_toca_a_volta_parcial_sem_resumo(tmp_path):
    radio, _, np, _ = _radio_com_voltas(tmp_path)
    n = int(radio._geometria.track.size)
    tempos = list(np.linspace(0.0, 90.0, n))
    linhas = {"elapsed": tempos, "velocidade": [100.0] * n, "acelerador": [1.0] * n, "freio": [0.0] * n, "lateral": [0.0] * n}
    radio._volta_parcial = lambda: {"versao": 1, "volta": 3, "pontosDaGrade": n, "tempoS": 90.0, "linhas": linhas}
    radio._guardar_a_parcial()
    radio._guardar_a_parcial()                         # a mesma volta nao entra duas vezes
    lista = radio.voltas_da_sessao()["voltas"]
    assert len(lista) == 1 and lista[0]["volta"] == 3 and lista[0]["temReplay"] is True
    assert lista[0]["estado"] == "incompleta" and "não começou na linha" in lista[0]["motivo"]
    assert not radio._pendentes                        # sem resumo: a voz nao muda
    assert not radio._voltas_validas                   # e fora da analise
    assert "não começou na linha" in radio.replay_da_volta(3)["curvas"][0]["aviso"]

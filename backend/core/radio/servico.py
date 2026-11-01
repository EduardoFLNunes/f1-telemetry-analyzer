"""O radio do engenheiro no backend (pedido 31, Parte B; pedido 35): da frase do coach a mensagem entregue.

1. **Nasce:**
   - cada frase de diferenca do coach (`coaching_event`) vira uma mensagem
     (`texto.mensagem_de_diferenca`), com a causa principal na voz (pedido 35);
   - o resumo nasce na linha de chegada, com o periodo da volta que o coach mede e,
     desde o pedido 35, a curva em que a volta mais perdeu;
   - a analise das voltas (pedido 35, ADR 0021) nasce a cada 3 voltas validas da
     sessao, sobre essas 3 (`analise.analisar`).
2. **A voz:** cada mensagem traz as falas da mais completa a mais curta; o audio e
   gerado em segundo plano, e fica a primeira fala que cabe no tempo maximo do tipo.
3. **Espera:** so e entregue com o carro numa janela de radio (`janelas`), com a
   posicao que o coach ja projeta, e so se a fala inteira cabe no que resta da
   janela, na velocidade do carro (pedido 35: nada e dito dentro das 14 curvas).
   Uma por vez: a seguinte espera o audio da anterior acabar.
4. **E entregue:** ganha um id, entra na lista que o app do jogo e a tela Ao vivo
   leem (`desde(id)`) e e registrada em `<pasta de dados>/data/radio/<sessao>.jsonl`,
   fora da pasta de gravacoes.
5. **A grade da sessao** (pedido 43, C.4): cada volta que fecha entra na grade, com a perda
   por curva da analise (`medidas_da_volta`), ou fica fora com o motivo (a IA, a volta
   incompleta, a rodada); as curvas citadas pelo radio ficam marcadas na volta citada.

O radio nao decide nada do coach: quais frases saem, o limite de 3 por volta, o foco e
o limiar continuam no coach. A analise so le o que a volta ao vivo e o store ja medem.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

import numpy as np

from . import audio as audio_do_radio
from .analise import (COBERTURA_MINIMA, VOLTAS_POR_ANALISE, Pista, analisar, cobertura, grade, medidas_da_volta,
                      teve_rodada)
from .janelas import Janela, carregar_geometria, curvas_da_geometria, dentro, janelas_de_radio, tempo_que_resta
from .replay import cobertura_na_curva, dados_da_curva, janela_da_frase, replay_da_analise, volta_mais_perto_da_mediana
from .texto import (
    FALA_MAXIMA_S,
    CurvaDaPista,
    mensagem_de_analise,
    mensagem_de_diferenca,
    mensagem_de_resumo,
    mensagem_de_teste,
)

logger = logging.getLogger(__name__)

ESPERA_DO_RESUMO_S = 0.6       # as ultimas frases da volta chegam pelo barramento logo depois da linha
FOLGA_ENTRE_MENSAGENS_S = 0.6
FOLGA_NA_JANELA_S = 0.3        # a fala termina pelo menos isto antes do fim da janela
ESPERA_DO_AUDIO_S = 8.0        # sem audio pronto ate aqui, a mensagem sai sem voz (ate 3 falas a gerar)
GUARDADAS = 200
# Campos de cada mensagem no registro (`data/radio/<sessao>.jsonl`).
CAMPOS_DO_REGISTRO = ("id", "instancia", "entregueEm", "voltaDoCarro", "sCarro", "velocidadeKmh", "janela",
                      "s", "microssetor", "curva", "origem", "titulo", "texto", "detalhe", "linhas", "fala",
                      "falaMaxS", "duracaoS", "causa", "perdaS", "volta", "tempoS", "piorCurva",
                      "voltasAnalisadas", "curvasDaAnalise", "referencia", "restaS", "replay")


class RadioDoEngenheiro:
    def __init__(
        self,
        pasta_de_dados: Path,
        repositorio: Callable[[], Optional[Path]],
        posicao: Callable[[], Optional[Dict[str, Any]]],
        ultima_volta: Callable[[], Optional[Dict[str, Any]]],
        referencia: Callable[[], Dict[str, Any]],
        sessao: Callable[[], Optional[str]],
        falar: Callable[[str, Path], float] = audio_do_radio.falar,
        relogio: Callable[[], float] = time.time,
        volta_fechada: Callable[[], Optional[Dict[str, Any]]] = lambda: None,
        volta_de_referencia: Callable[[], Optional[Dict[str, Any]]] = lambda: None,
        volta_atual: Callable[[], Optional[Dict[str, Any]]] = lambda: None,
    ):
        self.pasta = Path(pasta_de_dados) / "data" / "radio"
        self.pasta_audio = self.pasta / "audio"
        self._repositorio = repositorio
        self._posicao = posicao
        self._ultima_volta = ultima_volta
        self._referencia = referencia
        self._sessao = sessao
        self._falar = falar
        self._relogio = relogio
        self._volta_fechada = volta_fechada
        self._volta_de_referencia = volta_de_referencia
        self._volta_atual = volta_atual
        self._grade_da_ultima: Optional[Dict[str, Any]] = None   # pedido 36: a grade da volta que fechou
        self._lock = threading.RLock()
        self._audio = ThreadPoolExecutor(max_workers=1, thread_name_prefix="radio-voz")
        self.instancia = datetime.now().strftime("%Y%m%d%H%M%S")
        self._proximo_id = 1
        self._pendentes: Deque[Dict[str, Any]] = deque()
        self._entregues: Deque[Dict[str, Any]] = deque(maxlen=GUARDADAS)
        self._ocupado_ate = 0.0
        self._volta_vista: Optional[float] = None
        self._resumo_desde: Optional[float] = None
        self._resumo: Optional[Dict[str, Any]] = None
        self._curvas: Optional[List[CurvaDaPista]] = None
        self._comprimento: Optional[float] = None
        self._janelas: List[Janela] = []
        self._geometria: Optional[Pista] = None
        self._chave_da_pista: Optional[str] = None
        self._velocidade_kmh: Optional[float] = None
        self._sessao_da_analise: Optional[str] = None
        self._voltas_validas: List[Dict[str, Any]] = []
        self._ultima_analise: Optional[Dict[str, Any]] = None
        # Pedido 43 (C.4): a grade da sessao (as voltas, as que ficaram fora e as curvas citadas).
        self._grade_voltas: List[Dict[str, Any]] = []
        self._grade_fora: List[Dict[str, Any]] = []
        self._grade_citadas: List[Dict[str, Any]] = []
        self.erro_da_voz: Optional[str] = None

    # ------------------------------------------------------------- pista ---

    def _pista(self) -> bool:
        repo = self._repositorio()
        chave = str(repo) if repo else None
        if chave != self._chave_da_pista:
            self._chave_da_pista = chave
            try:
                track = carregar_geometria(repo)
                self._curvas = curvas_da_geometria(track) if track is not None else []
                self._comprimento = float(track.length) if track is not None else None
                self._geometria = Pista.da_geometria(track) if track is not None else None
            except Exception as erro:  # sem a geometria oficial o radio fica calado
                logger.warning("Radio sem a geometria oficial: %s", erro)
                self._curvas, self._comprimento, self._geometria = [], None, None
            self._janelas = janelas_de_radio(self._curvas or [], self._comprimento or 0.0)
        return bool(self._curvas and self._comprimento)

    def janelas(self) -> List[Janela]:
        with self._lock:
            self._pista()
            return list(self._janelas)

    # ------------------------------------------------------------ nascer ---

    def _nova(self, mensagem: Dict[str, Any]) -> Dict[str, Any]:
        mensagem = dict(mensagem)
        mensagem["criadaEm"] = self._relogio()
        mensagem["audio"] = None
        mensagem["duracaoS"] = None
        mensagem["_futuro"] = self._audio.submit(self._gerar_audio, mensagem)
        return mensagem

    def _gerar_audio(self, mensagem: Dict[str, Any]) -> Optional[Path]:
        """Gera a voz da primeira fala que cabe no tempo maximo do tipo (a ultima, se nenhuma couber)."""
        falas = list(mensagem.get("falas") or [mensagem["fala"]])
        maximo = float(mensagem.get("falaMaxS") or FALA_MAXIMA_S.get(mensagem.get("origem"), 8.0))
        base = self.pasta_audio / f"{self.instancia}_{id(mensagem)}"
        escolhido = None
        try:
            self.pasta_audio.mkdir(parents=True, exist_ok=True)
            for k, fala in enumerate(falas):
                arquivo = base.with_name(f"{base.name}_{k}.wav")
                dur = float(self._falar(fala, arquivo))
                if escolhido is not None:
                    try:
                        escolhido[0].unlink()
                    except OSError:
                        pass
                escolhido = (arquivo, dur, fala)
                if dur <= maximo:
                    break
        except Exception as erro:
            self.erro_da_voz = str(erro)
            logger.warning("Radio sem voz: %s", erro)
            return None
        self.erro_da_voz = None
        if escolhido is None:
            return None
        arquivo, dur, fala = escolhido
        mensagem["fala"] = fala
        mensagem["duracaoS"] = round(dur, 2)
        return arquivo

    def on_coaching_event(self, evento: Dict[str, Any]) -> None:
        """Uma frase do coach. So as de diferenca viram radio (o foco fica na tela)."""
        if not isinstance(evento, dict) or evento.get("type") != "coaching_event":
            return
        with self._lock:
            if not self._pista():
                return
            mensagem = mensagem_de_diferenca(evento, self._curvas or [], float(self._comprimento or 0.0))
            if mensagem is None:
                return
            # Pedido 43: o que o coach mediu, para o replay escrever os numeros da voz.
            mensagem["_voz"] = dict(evento.get("evidence") or {})
            self._pendentes.append(self._nova(mensagem))

    # ---------------------------------------------------------- entregar ---

    def on_frame(self, frame: Any = None) -> None:
        """A cada quadro, sem nunca esperar: a linha (o resumo e a analise) e a janela (a proxima mensagem)."""
        agora = self._relogio()
        if isinstance(frame, dict):
            v = frame.get("speedKmh") if "speedKmh" in frame else frame.get("speed_kmh")
            try:
                self._velocidade_kmh = float(v) if v is not None else self._velocidade_kmh
            except (TypeError, ValueError):
                pass
        with self._lock:
            volta = self._ultima_volta()
            if volta and volta.get("momento") != self._volta_vista:
                self._volta_vista = volta.get("momento")
                self._resumo_desde = agora
                self._resumo = volta
            if self._resumo_desde is not None and agora - self._resumo_desde >= ESPERA_DO_RESUMO_S:
                self._na_linha()
            if not self._pendentes or agora < self._ocupado_ate:
                return
            proxima = self._pendentes[0]
            if not self._audio_pronto(proxima, agora):
                return
            pos = self._posicao() or {}
            if not pos or not self._pista():
                return
            L = float(self._comprimento or pos["comprimento"])
            s = float(pos["s"])
            if dentro(self._janelas, s, L) is None:
                return
            # Pedido 35: so se a fala inteira cabe no que resta da janela, na velocidade do carro.
            duracao = float(proxima.get("duracaoS") or proxima.get("falaMaxS") or 6.0)
            if tempo_que_resta(self._janelas, s, L, self._velocidade_kmh) < duracao + FOLGA_NA_JANELA_S:
                return
            self._entregar(self._pendentes.popleft(), agora, pos)

    def _audio_pronto(self, mensagem: Dict[str, Any], agora: float) -> bool:
        futuro = mensagem.get("_futuro")
        return futuro is None or futuro.done() or agora - mensagem["criadaEm"] >= ESPERA_DO_AUDIO_S

    def _medidas_da_volta(self, volta: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """As medidas por curva da volta que acabou de fechar, contra a referencia; None se nao der."""
        fechada = self._volta_fechada()
        ref = self._volta_de_referencia()
        if not fechada or not ref or not ref.get("disponivel", True) or self._geometria is None:
            return None
        if fechada.get("volta") != volta.get("volta"):
            return None
        if int(fechada.get("pontosDaGrade") or 0) != int(self._geometria.track.size):
            return None
        if cobertura(fechada["linhas"]) < COBERTURA_MINIMA:
            return None
        try:
            g = grade(fechada["linhas"])
            medidas = medidas_da_volta(g, float(volta["tempoS"]), grade(ref), float(ref["tempoS"]), self._geometria)
            # Pedido 36: a grade fica guardada para o replay da curva da analise.
            self._grade_da_ultima = {"volta": volta.get("volta"), "grade": g, "tempoS": float(volta["tempoS"])}
            return medidas
        except Exception as erro:
            logger.warning("Radio sem as medidas da volta: %s", erro)
            return None

    def _na_linha(self) -> None:
        """A volta acabou: o resumo (com a curva que mais perdeu) e, a cada 3 voltas validas, a analise."""
        volta, self._resumo_desde = self._resumo, None
        if not volta:
            return
        self._conferir_a_sessao()
        if volta.get("teveIA"):
            self._fora_da_grade(volta, "a IA pilotou parte da volta")
            return
        ref = self._referencia() or {}
        medidas = self._medidas_da_volta(volta)
        pior = None
        # A curva que mais perdeu so nas voltas completas (a mesma regra da analise): numa volta
        # com parada, "mais perdeu na curva 1: 66,4" e verdade, mas nao ajuda. Nem numa volta com
        # rodada (pedido 36): "mais perdeu na curva 12: 26,5".
        if medidas and volta.get("completa") is not False and not teve_rodada(medidas):
            m = max(medidas, key=lambda x: x["perdaS"])
            if m["perdaS"] > 0:
                pior = {"curva": m["curva"], "lado": m["lado"], "perdaS": m["perdaS"]}
        # O resumo vai para a frente da fila: o que ficou da volta anterior espera ele (pedido 35;
        # sem isto, numa sessao real, o resumo chegava uma volta atrasado).
        self._pendentes.appendleft(self._nova(mensagem_de_resumo(volta.get("volta"), float(volta["tempoS"]),
                                                                 ref.get("tempoS"), ref.get("tipo"), pior)))
        self._analise_da_volta(volta, medidas, ref)

    def _conferir_a_sessao(self) -> None:
        """Outra sessao: a analise e a grade comecam de novo."""
        sessao = self._sessao()
        if sessao != self._sessao_da_analise:
            self._sessao_da_analise, self._voltas_validas = sessao, []
            self._grade_voltas, self._grade_fora, self._grade_citadas = [], [], []

    def _fora_da_grade(self, volta: Dict[str, Any], motivo: str) -> None:
        numero = int(volta["volta"]) if volta.get("volta") is not None else None
        tempo = round(float(volta["tempoS"]), 3) if volta.get("tempoS") is not None else None
        self._grade_fora.append({"volta": numero, "tempoS": tempo, "motivo": motivo})

    def _analise_da_volta(self, volta: Dict[str, Any], medidas: Optional[List[Dict[str, Any]]],
                          ref: Dict[str, Any]) -> None:
        self._conferir_a_sessao()
        # Pedido 43 (C.4): a volta que nao entra na analise fica fora da grade, com o motivo.
        if medidas is None:
            self._fora_da_grade(volta, "sem as medidas da volta (a referência ou a grade da volta)")
            return
        if volta.get("completa") is False:
            self._fora_da_grade(volta, "volta incompleta (nem todos os microssetores medidos)")
            return
        if teve_rodada(medidas):
            pior = max(medidas, key=lambda m: float(m.get("perdaS") or 0.0))
            perdeu = f"{pior['perdaS']:.1f}".replace(".", ",")
            self._fora_da_grade(volta, f"rodada ou saída de pista: perdeu {perdeu} s na {pior['curva']}")
            return
        self._grade_voltas.append({"volta": int(volta["volta"]) if volta.get("volta") is not None else None,
                                   "tempoS": round(float(volta["tempoS"]), 3),
                                   "perdas": {m["curva"]: m["perdaS"] for m in medidas}})
        guardada = self._grade_da_ultima if (self._grade_da_ultima or {}).get("volta") == volta.get("volta") else None
        self._voltas_validas.append({"volta": int(volta["volta"]) if volta.get("volta") is not None else None,
                                     "medidas": medidas, "grade": (guardada or {}).get("grade"),
                                     "tempoS": (guardada or {}).get("tempoS")})
        if len(self._voltas_validas) % VOLTAS_POR_ANALISE:
            return
        tres = self._voltas_validas[-VOLTAS_POR_ANALISE:]
        resultado = analisar(tres)
        mensagem = mensagem_de_analise(resultado, ref.get("tipo"), ref.get("volta"))
        self._ultima_analise = resultado
        if mensagem is not None:
            mensagem["_replay"] = self._replay_da_analise(tres, resultado, ref.get("tipo"))
            # Pedido 43 (C.4): cada curva citada, na volta das 3 mais perto da mediana (a do replay).
            citadas = []
            for curva in resultado.get("curvas") or []:
                i = volta_mais_perto_da_mediana(tres, curva)
                if i is not None:
                    citadas.append({"volta": tres[i]["volta"], "curva": curva["curva"],
                                    "perdaS": curva["perdaMedianaS"]})
            mensagem["_citadas"] = citadas
            self._pendentes.append(self._nova(mensagem))

    # ------------------------------------------------------------- replay ---

    def _grade_da_referencia(self) -> Optional[Dict[str, Any]]:
        ref = self._volta_de_referencia()
        if not ref or not ref.get("disponivel", True) or self._geometria is None:
            return None
        try:
            return {"grade": grade(ref), "tempoS": float(ref["tempoS"])}
        except Exception:
            return None

    def _replay_da_analise(self, voltas: List[Dict[str, Any]], resultado: Dict[str, Any],
                           tipo: Optional[str]) -> List[Dict[str, Any]]:
        """Pedido 36, Parte E: cada curva citada, com a volta das 3 mais perto da mediana."""
        ref = self._grade_da_referencia()
        if ref is None:
            return []
        try:
            return replay_da_analise(self._geometria, voltas, resultado, ref["grade"], ref["tempoS"], tipo)
        except Exception as erro:
            logger.warning("Radio sem o replay da analise: %s", erro)
            return []

    def _replay_da_frase(self, mensagem: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Pedido 36, Parte E: a curva da frase do coach com causa, na volta em que a frase saiu (a em
        andamento, ou a que acabou de fechar se a entrega ja passou da linha)."""
        codigo, numero = mensagem.get("curva"), mensagem.get("volta")
        if not codigo or not mensagem.get("causa") or self._geometria is None:
            return []
        ref = self._grade_da_referencia()
        if ref is None:
            return []
        for candidata in (self._volta_atual(), self._volta_fechada()):
            if not candidata or not candidata.get("linhas") or candidata.get("volta") != numero:
                continue
            if int(candidata.get("pontosDaGrade") or 0) != int(self._geometria.track.size):
                continue
            try:
                g = grade(candidata["linhas"])
                # Pedido 43: a janela com o trecho da fala; o relogio tem de ter sido medido nela inteira.
                janela = janela_da_frase(self._geometria, codigo, g, ref["grade"], mensagem.get("_voz"))
                if janela is None or cobertura_na_curva(candidata["linhas"], janela[2]) < COBERTURA_MINIMA:
                    continue
                total = float(np.nanmax(g["elapsed"]))
                d = dados_da_curva(self._geometria, codigo, g, total, ref["grade"], ref["tempoS"], numero,
                                   (self._referencia() or {}).get("tipo"), voz=mensagem.get("_voz"))
                return [d] if d else []
            except Exception as erro:
                logger.warning("Radio sem o replay da frase: %s", erro)
        return []

    def replay(self, id_: int) -> Optional[Dict[str, Any]]:
        """Os dados do replay de uma mensagem entregue (a rota, uma vez por mensagem)."""
        with self._lock:
            for m in self._entregues:
                if m["id"] == int(id_) and m.get("_replay"):
                    return {"id": m["id"], "origem": m.get("origem"), "curvas": m["_replay"]}
        return None

    def _entregar(self, mensagem: Dict[str, Any], agora: float, pos: Dict[str, Any]) -> Dict[str, Any]:
        futuro = mensagem.pop("_futuro", None)
        arquivo = None
        if futuro is not None and futuro.done():
            try:
                arquivo = futuro.result()
            except Exception:
                arquivo = None
        mensagem["id"] = self._proximo_id
        self._proximo_id += 1
        mensagem["instancia"] = self.instancia
        mensagem["entregueEm"] = datetime.fromtimestamp(agora).isoformat(timespec="seconds")
        mensagem["sCarro"] = round(float(pos["s"]), 1) if pos.get("s") is not None else None
        mensagem["voltaDoCarro"] = int(pos["volta"]) if pos.get("volta") is not None else None
        mensagem["velocidadeKmh"] = round(self._velocidade_kmh, 1) if self._velocidade_kmh is not None else None
        if pos.get("s") is not None and self._comprimento:
            janela = dentro(self._janelas, float(pos["s"]), float(self._comprimento))
            mensagem["janela"] = [round(janela[0], 1), round(janela[1], 1)] if janela else None
        mensagem["sessao"] = self._sessao()
        mensagem.pop("naLinha", None)
        # Pedido 36, Parte E: quanto resta da janela de radio (o replay some quando ela acaba) e o
        # replay da curva, na frase do coach com causa e na analise.
        if pos.get("s") is not None and self._comprimento:
            mensagem["restaS"] = round(tempo_que_resta(self._janelas, float(pos["s"]), float(self._comprimento),
                                                       self._velocidade_kmh), 1)
        if mensagem.get("origem") == "coach" and "_replay" not in mensagem:
            mensagem["_replay"] = self._replay_da_frase(mensagem)
        if mensagem.get("_replay"):
            mensagem["replay"] = {"url": f"/api/radio/replay/{mensagem['id']}",
                                  "curvas": [c["curva"] for c in mensagem["_replay"]]}
        self._citar(mensagem)
        if arquivo is not None:
            mensagem["audio"] = f"/api/radio/audio/{mensagem['id']}"
            mensagem["audioArquivo"] = str(Path(arquivo).resolve())   # pedido 35: o 2o caminho da voz no jogo
            mensagem["_arquivo"] = str(arquivo)
        self._ocupado_ate = agora + float(mensagem.get("duracaoS") or 3.0) + FOLGA_ENTRE_MENSAGENS_S
        self._entregues.append(mensagem)
        self._registrar(mensagem)
        return mensagem

    def _citar(self, mensagem: Dict[str, Any]) -> None:
        """Pedido 43 (C.4): a curva citada fica marcada na grade, na volta citada."""
        self._conferir_a_sessao()
        if mensagem.get("origem") == "coach" and mensagem.get("curva") and mensagem.get("volta") is not None:
            self._grade_citadas.append({"volta": mensagem["volta"], "curva": mensagem["curva"], "origem": "coach",
                                        "id": mensagem["id"]})
        for c in mensagem.get("_citadas") or []:
            self._grade_citadas.append({**c, "origem": "analise", "id": mensagem["id"]})

    def grade_da_sessao(self) -> Dict[str, Any]:
        """Pedido 43 (C.4): as voltas validas da sessao com a perda em cada curva (a mesma da
        analise), as que ficaram fora com o motivo e as curvas citadas pelo radio."""
        with self._lock:
            self._pista()
            curvas = [seg.corner.label[:3] for seg in self._geometria.segmentos] if self._geometria else []
            # A volta que nao fecha na linha para o coach (`ultima_volta`: o carro movido, a volta que
            # nao comecou na linha, o contador do jogo ja adiantado na passagem) nao passa pelo radio:
            # ela aparece aqui pelo buraco na numeracao.
            fora = list(self._grade_fora)
            vistas = {v["volta"] for v in self._grade_voltas} | {f["volta"] for f in fora}
            vistas.discard(None)
            if vistas:
                fora += [{"volta": n, "tempoS": None, "motivo": "o rádio não viu esta volta fechar na linha"}
                         for n in range(min(vistas), max(vistas)) if n not in vistas]
                fora.sort(key=lambda f: f["volta"] if f["volta"] is not None else -1)
            return {"sessao": self._sessao_da_analise, "curvas": curvas,
                    "voltas": [{"volta": v["volta"], "tempoS": v["tempoS"],
                                "perdas": [v["perdas"].get(c) for c in curvas]} for v in self._grade_voltas],
                    "fora": fora, "citadas": list(self._grade_citadas)}

    def _registrar(self, mensagem: Dict[str, Any]) -> None:
        sessao = mensagem.get("sessao") or f"sem-gravacao_{datetime.now():%Y-%m-%d}"
        linha = {k: mensagem.get(k) for k in CAMPOS_DO_REGISTRO if k in mensagem}
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            with (self.pasta / f"{sessao}.jsonl").open("a", encoding="utf-8") as saida:
                saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
        except OSError as erro:
            logger.warning("Radio sem registro: %s", erro)

    # ------------------------------------------------------------ leitura ---

    @staticmethod
    def _publica(m: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in m.items() if not k.startswith("_") and k != "falas"}

    def desde(self, id_: int = 0, instancia: Optional[str] = None) -> Dict[str, Any]:
        """As mensagens entregues depois de `id_`. Outra instancia (backend reiniciado): todas."""
        with self._lock:
            desde = 0 if instancia and instancia != self.instancia else int(id_ or 0)
            novas = [self._publica(m) for m in self._entregues if m["id"] > desde]
            return {"instancia": self.instancia, "ultimoId": self._proximo_id - 1, "mensagens": novas,
                    "pendentes": len(self._pendentes), "erroDaVoz": self.erro_da_voz,
                    "minimapaVersao": self.versao_do_minimapa()}

    def versao_do_minimapa(self) -> str:
        """Pedido 35: muda quando a referencia ou a ultima analise mudam (o app do jogo baixa o minimapa de novo).
        O mesmo formato de `minimapa.montar`."""
        try:
            ref = self._referencia() or {}
        except Exception:
            ref = {}
        voltas = (self._ultima_analise or {}).get("voltas") or []
        return f"{ref.get('tipo')}|{ref.get('volta')}|{'-'.join(str(v) for v in voltas)}"

    def arquivo_do_audio(self, id_: int) -> Optional[Path]:
        with self._lock:
            for m in self._entregues:
                if m["id"] == id_ and m.get("_arquivo"):
                    return Path(m["_arquivo"])
        return None

    def ultima_analise(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._ultima_analise

    def teste(self) -> Dict[str, Any]:
        """A mensagem de teste da tela Sistema: entregue na hora, sem esperar janela."""
        mensagem = self._nova(mensagem_de_teste())
        try:
            mensagem["_futuro"].result(timeout=20)
        except Exception:
            pass
        with self._lock:
            return self._publica(self._entregar(mensagem, self._relogio(), self._posicao() or {}))

    def estado(self) -> Dict[str, Any]:
        with self._lock:
            pista = self._pista()
            return {"pistaPronta": pista, "janelas": [[round(a, 1), round(b, 1)] for a, b in self._janelas],
                    "comprimento": self._comprimento, "pendentes": len(self._pendentes),
                    "entregues": len(self._entregues), "instancia": self.instancia,
                    "voz": audio_do_radio.VOZ_PADRAO, "velocidade": audio_do_radio.VELOCIDADE_PADRAO,
                    "erroDaVoz": self.erro_da_voz, "pastaDoRegistro": str(self.pasta),
                    "voltasValidasDaSessao": len(self._voltas_validas)}

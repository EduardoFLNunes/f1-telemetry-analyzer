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
6. **As voltas da sessao** (pedido 45, Parte E): toda volta que fecha fica guardada, com o estado, o
   motivo e os pontos na grade (5 linhas em float32, ~43 KB por volta), para o replay de qualquer
   volta e de qualquer curva nos boxes, sem ler a gravacao.

7. **O engenheiro** (pedido 52, ADR 0033; `core.engenheiro`): a lista dos trechos com perda, o aviso pela
   voz antes da curva (com prioridade sobre o feedback; so a frase, sem a vinheta) e, com ele ligado, o
   feedback so no comeco dos blocos de voz, antes da reserva dos avisos: espera o bloco em que cabe a
   variante mais completa com a causa; na primeira reta longa depois de nascer, sai a mais completa que
   couber (a emenda de 16/11). `AT_ENGENHEIRO=desligado` volta ao radio do pedido 51.

O radio nao decide nada do coach: quais frases saem, o limite de 3 por volta, o foco e
o limiar continuam no coach. A analise so le o que a volta ao vivo e o store ja medem.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

import numpy as np

from . import audio as audio_do_radio
from .analise import (COBERTURA_MINIMA, VOLTAS_POR_ANALISE, Pista, analisar, causa_da_curva, cobertura, curva_da_volta,
                      grade, medidas_da_volta, teve_rodada)
from .janelas import Janela, carregar_geometria, curvas_da_geometria, dentro, janelas_de_radio, tempo_que_resta
from .replay import (cobertura_na_curva, dados_da_curva, dados_da_volta, janela_da_frase, replay_da_analise,
                     volta_mais_perto_da_mediana)
from .texto import (
    FALA_MAXIMA_S,
    CurvaDaPista,
    fala_tem_causa,
    fala_da_curva,
    falas_da_curva,
    frase_da_tendencia,
    mensagem_da_curva,
    mensagem_de_analise,
    mensagem_de_diferenca,
    mensagem_de_resumo,
    mensagem_de_teste,
)

logger = logging.getLogger(__name__)

ESPERA_DO_RESUMO_S = 0.6       # as ultimas frases da volta chegam pelo barramento logo depois da linha
FOLGA_ENTRE_MENSAGENS_S = 0.6
# Pedido 52: o feedback (a fala que o aviso do engenheiro corta; ADR 0033, emenda de 20/11, item 1)
FEEDBACK = ("coach", "resumo", "analise", "curva")
NAO_REFAZ = ("id", "instancia", "entregueEm", "sCarro", "voltaDoCarro", "velocidadeKmh", "janela", "restaS", "audio",
             "audioArquivo", "duracaoS", "replay", "sessao", "criadaEm", "_futuro", "_variantes", "_arquivo",
             "_arquivoPronto", "_falaEscolhida", "_reservaEm", "_comACausa", "_saiuNaRegra", "_esperouOBloco",
             "_blocoAtual", "_retaLongaDepoisDeNascer", "_replay")
FOLGA_NA_JANELA_S = 0.3        # a fala termina pelo menos isto antes do fim da janela
ESPERA_DO_AUDIO_S = 8.0        # sem audio pronto ate aqui, a mensagem sai sem voz (ate 3 falas a gerar)
GUARDADAS = 200
# Campos de cada mensagem no registro (`data/radio/<sessao>.jsonl`).
CAMPOS_DO_REGISTRO = ("id", "instancia", "entregueEm", "voltaDoCarro", "sCarro", "velocidadeKmh", "janela",
                      "s", "microssetor", "curva", "origem", "titulo", "texto", "detalhe", "linhas", "fala",
                      "falaMaxS", "duracaoS", "causa", "perdaS", "volta", "tempoS", "piorCurva",
                      "voltasAnalisadas", "curvasDaAnalise", "referencia", "restaS", "replay", "melhor", "tendencia")
PONTOS_DA_MELHOR = 900         # a melhor volta no minimapa: pontos a cada ~5 m, como a referencia


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
        melhor_do_store: Callable[[], Optional[float]] = lambda: None,
        volta_parcial: Callable[[], Optional[Dict[str, Any]]] = lambda: None,
        engenheiro: Optional[bool] = None,
        raizes: Optional[Callable[[], List[Optional[Path]]]] = None,
        sua_melhor_volta: Callable[[], Optional[Dict[str, Any]]] = lambda: None,
    ):
        self.pasta = Path(pasta_de_dados) / "data" / "radio"
        self.pasta_audio = self.pasta / "audio"
        self._repositorio = repositorio
        self._posicao = posicao
        self._ultima_volta = ultima_volta
        self._referencia = referencia
        self._sessao = sessao
        self._falar = falar
        try:
            import inspect
            self._falar_aceita_sem_vinheta = "vinheta_antes" in inspect.signature(falar).parameters
        except (TypeError, ValueError):
            self._falar_aceita_sem_vinheta = False
        self._relogio = relogio
        self._volta_fechada = volta_fechada
        self._volta_de_referencia = volta_de_referencia
        self._volta_atual = volta_atual
        self._melhor_do_store = melhor_do_store
        self._volta_parcial = volta_parcial
        self._parcial_vista: Optional[int] = None
        self._grade_da_ultima: Optional[Dict[str, Any]] = None   # pedido 36: a grade da volta que fechou
        self._lock = threading.RLock()
        self._audio = ThreadPoolExecutor(max_workers=1, thread_name_prefix="radio-voz")
        self.instancia = datetime.now().strftime("%Y%m%d%H%M%S")
        self._proximo_id = 1
        self._pendentes: Deque[Dict[str, Any]] = deque()
        self._entregues: Deque[Dict[str, Any]] = deque(maxlen=GUARDADAS)
        self._ocupado_ate = 0.0
        self._ultima_entregue: Optional[Dict[str, Any]] = None   # pedido 52: o feedback que um aviso pode cortar
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
        # Pedido 45: as voltas da sessao, a melhor e a curva que espera uma janela.
        self._voltas_da_sessao: List[Dict[str, Any]] = []
        self._melhor_s: Optional[float] = None
        self._melhor_volta: Optional[int] = None
        self._anterior_que_contou: Optional[float] = None
        self._s_da_fila: Optional[float] = None
        self.contagem = {"curvaEmMensagemPropria": 0, "curvaSaiuDaFila": 0}
        self.erro_da_voz: Optional[str] = None
        # Pedido 52 (ADR 0033): o engenheiro, ligado salvo `AT_ENGENHEIRO=desligado`.
        if engenheiro is None:
            engenheiro = os.environ.get("AT_ENGENHEIRO", "").strip().lower() not in ("desligado", "0", "nao", "não", "off")
        self.engenheiro_ligado = bool(engenheiro)
        self._raizes = raizes or (lambda: [self._repositorio()])
        self._sua_melhor_volta = sua_melhor_volta
        self._engenheiro = None
        self._engenheiro_erro: Optional[str] = None
        self._audio_do_engenheiro = ThreadPoolExecutor(max_workers=1, thread_name_prefix="radio-engenheiro")
        self._lenta: Dict[str, Any] = {"volta": None, "lenta": False, "motivo": None}
        self._ia_no_quadro = False

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
            self._engenheiro = None
            if self.engenheiro_ligado and self._geometria is not None:
                try:
                    from core.engenheiro.servico import Engenheiro
                    self._engenheiro = Engenheiro(self._geometria.track, self._geometria, self._raizes,
                                                  self._falar_o_aviso, self._registrar_o_engenheiro,
                                                  relogio=self._relogio)
                    self._engenheiro_erro = self._engenheiro.motivo
                except Exception as erro:  # sem o engenheiro, o radio continua o do pedido 51
                    logger.warning("Radio sem o engenheiro: %s", erro)
                    self._engenheiro, self._engenheiro_erro = None, str(erro)
        return bool(self._curvas and self._comprimento)

    def _eng(self):
        """O engenheiro ativo (com a volta do modelo, os marcos e o ruido), ou None."""
        e = self._engenheiro
        return e if e is not None and e.ativo else None

    def _falar_o_aviso(self, fala: str):
        """Pedido 52: a voz de um aviso, em segundo plano, guardada pelo texto (a mesma frase nao e gerada duas vezes)."""
        def gerar():
            nome = hashlib.sha1(fala.encode("utf-8")).hexdigest()[:12]
            arquivo = self.pasta_audio / f"{self.instancia}_aviso_{nome}.wav"
            self.pasta_audio.mkdir(parents=True, exist_ok=True)
            # ADR 0033, emenda de 16/11, item 2: o aviso e so a frase, sem a vinheta
            if self._falar_aceita_sem_vinheta:
                return arquivo, float(self._falar(fala, arquivo, vinheta_antes=False))
            return arquivo, float(self._falar(fala, arquivo))
        return self._audio_do_engenheiro.submit(gerar)

    def _registrar_o_engenheiro(self, linha: Dict[str, Any]) -> None:
        """Pedido 52 (ADR 0033, item 10): `<pasta de dados>/data/radio/<sessao>.engenheiro.jsonl`."""
        sessao = self._sessao() or f"sem-gravacao_{datetime.now():%Y-%m-%d}"
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            with (self.pasta / f"{sessao}.engenheiro.jsonl").open("a", encoding="utf-8") as saida:
                saida.write(json.dumps({"em": datetime.fromtimestamp(self._relogio()).isoformat(timespec="seconds"),
                                        "sessao": sessao, **linha}, ensure_ascii=False) + "\n")
        except OSError as erro:
            logger.warning("Engenheiro sem registro: %s", erro)

    def janelas(self) -> List[Janela]:
        with self._lock:
            self._pista()
            return list(self._janelas)

    # ------------------------------------------------------------ nascer ---

    def _nova(self, mensagem: Dict[str, Any]) -> Dict[str, Any]:
        mensagem = dict(mensagem)
        mensagem["criadaEm"] = self._relogio()
        # ADR 0033, emenda de 16/11, item 1: o bloco em que a mensagem nasce (a reta longa em que ela nasce nao
        # conta como "a primeira reta longa depois de nascer")
        eng = self._eng()
        if eng is not None:
            try:
                pos = self._posicao() or {}
                bloco = eng.bloco_em(float(pos["s"])) if pos.get("s") is not None else None
            except Exception:
                bloco = None
            mensagem["_blocoAtual"] = id(bloco) if bloco is not None else None
            mensagem["_retaLongaDepoisDeNascer"] = False
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
        # Pedido 52 (ADR 0033, item 5): com o engenheiro, a fala e escolhida na entrega, pelo tempo que resta
        # antes da reserva dos avisos: todas as variantes que cabem no limite do tipo sao geradas, da mais
        # completa a mais curta (a mais completa fica pronta primeiro).
        todas = self._eng() is not None
        if todas:
            mensagem.setdefault("_variantes", [])
        try:
            self.pasta_audio.mkdir(parents=True, exist_ok=True)
            for k, fala in enumerate(falas):
                arquivo = base.with_name(f"{base.name}_{k}.wav")
                dur = float(self._falar(fala, arquivo))
                if todas:
                    # a ultima fica mesmo acima do limite se nenhuma couber (como sem o engenheiro)
                    if dur <= maximo or (k == len(falas) - 1 and not mensagem["_variantes"]):
                        mensagem["_variantes"].append((k, arquivo, dur, fala))
                    else:
                        try:
                            arquivo.unlink()
                        except OSError:
                            pass
                    continue
                if escolhido is not None:
                    try:
                        escolhido[0].unlink()
                    except OSError:
                        pass
                escolhido = (arquivo, dur, fala)
                mensagem["_falaEscolhida"] = k
                if dur <= maximo:
                    break
        except Exception as erro:
            self.erro_da_voz = str(erro)
            logger.warning("Radio sem voz: %s", erro)
            return None
        self.erro_da_voz = None
        if todas:
            if not mensagem.get("_variantes"):
                return None
            k, arquivo, dur, fala = mensagem["_variantes"][0]
            mensagem["_falaEscolhida"] = k
            mensagem["fala"] = fala
            mensagem["duracaoS"] = round(dur, 2)
            return arquivo
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
            if "isAIControlled" in frame:
                self._ia_no_quadro = bool(frame.get("isAIControlled"))
        with self._lock:
            volta = self._ultima_volta()
            if volta and volta.get("momento") != self._volta_vista:
                self._volta_vista = volta.get("momento")
                self._resumo_desde = agora
                self._resumo = volta
            if self._resumo_desde is not None and agora - self._resumo_desde >= ESPERA_DO_RESUMO_S:
                self._na_linha()
            self._guardar_a_parcial()
            self._tirar_as_curvas_que_passaram()
            # Pedido 52 (ADR 0033, item 5): o aviso do engenheiro vem antes de tudo e nunca espera o feedback.
            eng = self._eng()
            if eng is not None:
                pos = self._posicao() or {}
                if pos.get("s") is not None:
                    self._acompanhar_a_volta_lenta(pos)
                    self._acompanhar_as_retas_longas(eng, float(pos["s"]))
                    # ADR 0033, emenda de 20/11, itens 1 e 2: o aviso e tocado pelo app do jogo, pelo mesmo `s`;
                    # aqui ele corta o feedback em andamento e ocupa o radio pelo tempo da fala.
                    for fala in eng.no_quadro(float(pos["s"]), self._velocidade_kmh, bool(pos.get("desdeALinha", True)),
                                              self._ia_no_quadro, falando=agora < self._ocupado_ate):
                        self._cortar_o_feedback(eng, fala, agora, float(pos["s"]))
                        from core.engenheiro.plano import LATENCIA_NO_JOGO_S
                        self._ocupado_ate = max(self._ocupado_ate, agora + LATENCIA_NO_JOGO_S + float(fala["duracaoS"])
                                                + FOLGA_ENTRE_MENSAGENS_S)
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
            if eng is not None:
                # Pedido 52: o feedback no comeco de um bloco de voz, na variante mais completa que cabe antes da
                # reserva dos avisos; se nenhuma couber, espera o bloco seguinte.
                if not self._escolher_a_variante(proxima, eng, s, L, agora):
                    return
                self._entregar(self._pendentes.popleft(), agora, pos)
                return
            if dentro(self._janelas, s, L) is None:
                return
            # Pedido 35: so se a fala inteira cabe no que resta da janela, na velocidade do carro.
            duracao = float(proxima.get("duracaoS") or proxima.get("falaMaxS") or 6.0)
            if tempo_que_resta(self._janelas, s, L, self._velocidade_kmh) < duracao + FOLGA_NA_JANELA_S:
                return
            self._entregar(self._pendentes.popleft(), agora, pos)

    def _cortar_o_feedback(self, eng, fala: Dict[str, Any], agora: float, s: float) -> None:
        """ADR 0033, emenda de 20/11, item 1: um feedback em andamento e cortado pelo aviso (o app do jogo para a
        voz e tira o cartao). O corte vai para o registro do engenheiro; a mensagem volta a fila e so pode sair
        numa reta longa seguinte, pela decisao 1 de 16/11."""
        m = self._ultima_entregue
        if m is None or agora >= self._ocupado_ate or m.get("origem") not in FEEDBACK:
            return
        self._ultima_entregue = None
        eng._registrar({"tipo": "corte", "t": round(agora, 3), "sCarro": round(s, 1),
                        "cortada": {"id": m.get("id"), "origem": m.get("origem"), "titulo": m.get("titulo"),
                                    "fala": m.get("fala"), "volta": m.get("volta")},
                        "restavaS": round(self._ocupado_ate - agora, 2), "pelaFala": fala.get("texto"),
                        "trechos": fala.get("trechos")})
        refeita = {k: v for k, v in m.items() if k not in NAO_REFAZ}
        refeita["fala"] = (refeita.get("falas") or [m.get("fala")])[0]
        nova = self._nova(refeita)
        nova["_soNaRetaLonga"] = True
        nova["_cortadaDe"] = m.get("id")
        self._pendentes.appendleft(nova)

    def _acompanhar_as_retas_longas(self, eng, s: float) -> None:
        """ADR 0033, emenda de 16/11, item 1: marca as mensagens na fila que ja viram o carro entrar numa reta
        longa (a reta dos boxes ou a oposta) depois de nascer."""
        bloco = eng.bloco_em(s)
        atual = id(bloco) if bloco is not None else None
        longa = eng.reta_longa(bloco)
        for m in self._pendentes:
            if "_blocoAtual" not in m:
                continue
            if m["_blocoAtual"] != atual:
                m["_blocoAtual"] = atual
                if longa and not m.get("_retaLongaDepoisDeNascer"):
                    m["_retaLongaDepoisDeNascer"] = True

    def _escolher_a_variante(self, mensagem: Dict[str, Any], eng, s: float, L: float, agora: float) -> bool:
        """Pedido 52 (ADR 0033, item 5, com a emenda de 16/11, item 1): com o carro num bloco, a variante alvo
        (a mais completa com a causa, no limite do tipo) se couber no tempo ate a reserva, na velocidade do
        carro. Desde a primeira reta longa depois de a mensagem nascer (ou sem variante com a causa), a mais
        completa que couber. False: espera."""
        reserva = eng.reserva(s)
        v = float(self._velocidade_kmh or 0.0) / 3.6
        if reserva is None or v <= 1.0:
            return False
        # o feedback cortado por um aviso so sai numa reta longa seguinte (ADR 0033, emenda de 20/11, item 1)
        if mensagem.get("_soNaRetaLonga") and not (mensagem.get("_retaLongaDepoisDeNascer") and eng.reta_longa(eng.bloco_em(s))):
            return False
        # o tempo ate a reserva pelo perfil da volta, e nao pela velocidade do momento (emenda de 20/11, item 3)
        disponivel = eng.tempo_entre(s, reserva, self._velocidade_kmh) - FOLGA_NA_JANELA_S
        variantes = list(mensagem.get("_variantes") or [])
        maximo = float(mensagem.get("falaMaxS") or FALA_MAXIMA_S.get(mensagem.get("origem"), 8.0))
        if not variantes:
            # sem voz (a voz falhou ou demorou): sai so o cartao, como antes
            futuro = mensagem.get("_futuro")
            return futuro is None or futuro.done() or agora - mensagem["criadaEm"] >= ESPERA_DO_AUDIO_S
        futuro = mensagem.get("_futuro")
        gerando = futuro is not None and not futuro.done()
        no_limite = [x for x in variantes if x[2] <= maximo]
        alvo = next((x for x in no_limite if fala_tem_causa(x[3])), None)
        if alvo is None and gerando and any(fala_tem_causa(f) for f in (mensagem.get("falas") or [])):
            return False       # a variante com a causa ainda esta sendo gerada
        if alvo is not None and not mensagem.get("_retaLongaDepoisDeNascer"):
            candidatas = [alvo]           # espera o bloco em que a variante alvo cabe
        else:
            candidatas = no_limite        # a mais completa que couber (a regra do 45)
        for k, arquivo, dur, fala in candidatas:
            if dur <= disponivel:
                mensagem["_falaEscolhida"] = k
                mensagem["fala"] = fala
                mensagem["duracaoS"] = round(dur, 2)
                mensagem["_arquivoPronto"] = str(arquivo)
                mensagem["_reservaEm"] = round(reserva, 1)
                mensagem["_comACausa"] = fala_tem_causa(fala)
                mensagem["_saiuNaRegra"] = ("a variante com a causa" if candidatas is not no_limite else
                                            "a mais completa que coube, depois da reta longa" if alvo is not None else
                                            "a mais completa que coube (sem variante com a causa)")
                return True
        if gerando:
            return False       # as variantes mais curtas ainda estao sendo geradas
        mensagem["_esperouOBloco"] = True
        return False

    def _acompanhar_a_volta_lenta(self, pos: Dict[str, Any]) -> None:
        """ADR 0033, item 6: a volta lenta (5,0 s ou mais atras da melhor da sessao naquele ponto, a volta de saida
        dos boxes); uma vez lenta, a volta fica lenta ate a linha (uma rodada, uma parada)."""
        volta = pos.get("volta")
        if volta != self._lenta.get("volta"):
            self._lenta = {"volta": volta, "lenta": False, "motivo": None, "difMelhorS": None}
        if not pos.get("desdeALinha", True):
            self._lenta.update(lenta=True, motivo="volta de saída dos boxes")
            return
        melhor = next((v for v in self._voltas_da_sessao if v["volta"] == self._melhor_volta and v["grade"] is not None), None)
        t = pos.get("tempoDaVolta")
        if melhor is None or t is None or self._geometria is None:
            return
        try:
            from core.engenheiro.regras import VOLTA_LENTA_S, tempo_em
            el = np.asarray(melhor["grade"]["elapsed"], dtype=float)
            dif = float(t) - tempo_em(el, float(melhor["tempoS"]), self._geometria.track, float(pos["s"]))
        except Exception:
            return
        self._lenta["difMelhorS"] = round(dif, 2)
        if dif >= VOLTA_LENTA_S and not self._lenta["lenta"]:
            self._lenta.update(lenta=True, motivo=f"{dif:.1f} s atrás da melhor da sessão".replace(".", ","))

    def _audio_pronto(self, mensagem: Dict[str, Any], agora: float) -> bool:
        futuro = mensagem.get("_futuro")
        if mensagem.get("_variantes"):
            return True        # pedido 52: a variante mais completa ja esta pronta
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

    def _guardar_a_parcial(self) -> None:
        """Pedido 45 (E.3): a volta que cruzou a linha sem ter comecado nela fica na lista e toca o replay.
        Nao tem resumo, nao conta para a analise e nao entra na grade: a voz e a regra do coach nao mudam."""
        parcial = self._volta_parcial()
        if not parcial or parcial.get("versao") == self._parcial_vista:
            return
        self._parcial_vista = parcial.get("versao")
        self._pista()
        self._conferir_a_sessao()
        ref = self._grade_da_referencia()
        if self._geometria is None or ref is None or int(parcial.get("pontosDaGrade") or 0) != int(self._geometria.track.size):
            return
        try:
            g = grade(parcial["linhas"])
            tempo = float(parcial["tempoS"])
            medidas = medidas_da_volta(g, tempo, ref["grade"], ref["tempoS"], self._geometria)
        except Exception as erro:
            logger.warning("Radio sem a volta que nao comecou na linha: %s", erro)
            return
        # Uma volta tem um numero so (B.2). O carro movido no meio da volta tambem fecha uma parcial, com
        # o mesmo numero: fica a que mediu mais pontos, e a volta que fechou na linha sempre vence.
        pontos = sum(1 for v in parcial["linhas"]["elapsed"] if v is not None)
        numero = int(parcial["volta"]) if parcial.get("volta") is not None else None
        for ja in list(self._voltas_da_sessao):
            if ja["volta"] == numero:
                if not ja.get("parcial") or ja.get("pontosMedidos", 0) >= pontos:
                    return
                self._voltas_da_sessao.remove(ja)
        self._grade_da_ultima = {"volta": parcial.get("volta"), "grade": g, "tempoS": tempo}
        self._guardar_a_volta({"volta": parcial.get("volta"), "tempoS": tempo}, "incompleta",
                              "fora da análise: não começou na linha (boxes ou carro movido)", medidas)
        self._voltas_da_sessao[-1].update(parcial=True, pontosMedidos=pontos)

    def _tirar_as_curvas_que_passaram(self) -> None:
        """Pedido 45 (C.1, item 5): a curva que vai passar de novo antes da janela sai da fila."""
        if not any("_curvaS" in m for m in self._pendentes):
            self._s_da_fila = None
            return
        pos = self._posicao() or {}
        if pos.get("s") is None:
            return
        s, anterior = float(pos["s"]), self._s_da_fila
        self._s_da_fila = s
        L = float(self._comprimento or pos.get("comprimento") or 0.0)
        if anterior is None or L <= 0:
            return
        andou = (s - anterior) % L
        if andou > L / 2:      # o carro foi movido (os boxes): nao e uma passagem
            return
        for m in list(self._pendentes):
            if "_curvaS" in m and (float(m["_curvaS"]) - anterior) % L <= andou:
                self._pendentes.remove(m)
                self.contagem["curvaSaiuDaFila"] += 1

    def _inicio_da_curva(self, codigo: Optional[str]) -> Optional[float]:
        for c in self._curvas or []:
            if c.codigo == codigo:
                return c.inicio_m
        return None

    def _melhor_da_volta(self, tempo: float, conta: bool) -> Optional[Dict[str, Any]]:
        """Pedido 45 (C.1): a melhor volta e a mais rapida da sessao entre as que contam para a analise.
        A volta bate a melhor de todas as sessoes do store, para o carro e a pista: "recorde pessoal"."""
        melhor = self._melhor_s
        if conta and (melhor is None or tempo < melhor):
            try:
                do_store = self._melhor_do_store()
            except Exception:
                do_store = None
            if do_store is not None:
                recorde_antes = min(do_store, melhor) if melhor is not None else do_store
                if tempo < recorde_antes:
                    return {"situacao": "recorde", "difS": round(recorde_antes - tempo, 3), "melhorS": round(recorde_antes, 3)}
            return {"situacao": "melhor", "difS": round(melhor - tempo, 3) if melhor is not None else None,
                    "melhorS": round(melhor, 3) if melhor is not None else None}
        if melhor is None:
            return None
        return {"situacao": "atras", "difS": round(tempo - melhor, 3), "melhorS": round(melhor, 3)}

    def _replay_da_curva_da_volta(self, volta: Dict[str, Any], pior: Dict[str, Any], tipo: Optional[str]) -> List[Dict[str, Any]]:
        """Pedido 45 (C.2): o replay da curva citada no resumo, com o trecho da causa."""
        ref = self._grade_da_referencia()
        guardada = self._grade_da_ultima if (self._grade_da_ultima or {}).get("volta") == volta.get("volta") else None
        if ref is None or guardada is None:
            return []
        try:
            d = dados_da_curva(self._geometria, pior["curva"], guardada["grade"], guardada["tempoS"], ref["grade"],
                               ref["tempoS"], volta.get("volta"), tipo, causa=pior.get("causa"))
            return [d] if d else []
        except Exception as erro:
            logger.warning("Radio sem o replay da curva da volta: %s", erro)
            return []

    def _na_linha(self) -> None:
        """A volta acabou: o resumo (a melhor, a curva da volta e a causa) e, a cada 3 voltas validas, a analise."""
        volta, self._resumo_desde = self._resumo, None
        if not volta:
            return
        # Pedido 45 (B.1): a geometria so era lida na primeira frase do coach ou na primeira janela; a
        # primeira volta que fechava antes disso saia "sem as medidas" (13/10 e 18/10, a volta 2).
        self._pista()
        self._conferir_a_sessao()
        if volta.get("teveIA"):
            if self._eng() is not None:
                self._eng().na_linha(volta.get("volta"), None, None, conta=False)
            self._guardar_a_volta(volta, "ia", "a IA pilotou parte da volta", None)
            self._fora_da_grade(volta, "a IA pilotou parte da volta")
            return
        ref = self._referencia() or {}
        medidas = self._medidas_da_volta(volta)
        tempo = float(volta["tempoS"])
        rodada = bool(medidas) and teve_rodada(medidas)
        # O que conta para a analise: a volta completa (a regra do coach), com as medidas e sem rodada.
        conta = bool(medidas) and volta.get("completa") is not False and not rodada
        # A curva da volta so nas voltas que contam: numa volta com parada, "mais perdeu na curva 1:
        # 66,4" e verdade, mas nao ajuda. Nem numa volta com rodada (pedido 36).
        pior = curva_da_volta(medidas) if conta else None
        melhor = self._melhor_da_volta(tempo, conta)
        # C.1, item 4: a diferenca para a anterior so quando melhorou sem ser a melhor.
        anterior = None
        if conta and melhor and melhor["situacao"] == "atras" and self._anterior_que_contou is not None \
                and tempo < self._anterior_que_contou:
            anterior = round(self._anterior_que_contou - tempo, 3)
        mensagem = mensagem_de_resumo(volta.get("volta"), tempo, ref.get("tempoS"), ref.get("tipo"), pior, melhor,
                                      anterior, rodada=rodada)
        self._engenheiro_na_linha(volta, mensagem, conta)
        if pior:
            mensagem["_replay"] = self._replay_da_curva_da_volta(volta, pior, ref.get("tipo"))
            mensagem["_curvaDaVolta"] = pior
        # O resumo vai para a frente da fila: o que ficou da volta anterior espera ele (pedido 35;
        # sem isto, numa sessao real, o resumo chegava uma volta atrasado).
        self._pendentes.appendleft(self._nova(mensagem))
        estado, motivo = self._estado_da_volta(volta, medidas, rodada)
        self._guardar_a_volta(volta, estado, motivo, medidas)
        if conta:
            if self._melhor_s is None or tempo < self._melhor_s:
                self._melhor_s, self._melhor_volta = tempo, int(volta["volta"]) if volta.get("volta") is not None else None
            self._anterior_que_contou = tempo
        else:
            self._anterior_que_contou = None
        self._analise_da_volta(volta, medidas, ref)

    def _engenheiro_na_linha(self, volta: Dict[str, Any], mensagem: Dict[str, Any], conta: bool) -> None:
        """Pedido 52 (ADR 0033, itens 1, 8 e 9): a conferencia das dicas e a lista nova; a acuracia vai no cartao
        do resumo e na variante mais completa da fala (o primeiro item a sair no corte)."""
        eng = self._eng()
        if eng is None:
            return
        guardada = self._grade_da_ultima if (self._grade_da_ultima or {}).get("volta") == volta.get("volta") else None
        try:
            conf = eng.na_linha(volta.get("volta"), guardada["grade"] if guardada else None,
                                guardada["tempoS"] if guardada else None, conta and guardada is not None)
        except Exception as erro:
            logger.warning("Engenheiro sem a linha: %s", erro)
            return
        if not conf or not conf.get("texto"):
            return
        falas = list(mensagem.get("falas") or [mensagem["fala"]])
        frase = conf["texto"][0].upper() + conf["texto"][1:] + "."
        mensagem["falas"] = [f"{falas[0]} {frase}"] + falas
        mensagem["fala"] = mensagem["falas"][0]
        if mensagem.get("falasComACausa"):
            mensagem["falasComACausa"] = int(mensagem["falasComACausa"]) + 1
        mensagem["texto"] = f"{mensagem.get('texto')} · {conf['texto']}"
        mensagem["acuracia"] = conf["texto"]

    @staticmethod
    def _estado_da_volta(volta: Dict[str, Any], medidas: Optional[List[Dict[str, Any]]], rodada: bool):
        """Pedido 45 (E.2): o estado da volta na lista dos boxes, com o motivo."""
        if rodada:
            pior = max(medidas or [], key=lambda m: float(m.get("perdaS") or 0.0))
            return "rodada", f"fora da análise: rodada (perdeu {pior['perdaS']:.1f} s na {pior['curva']})".replace(".", ",", 1)
        if volta.get("completa") is False:
            sem = list(volta.get("semMedida") or [])
            if sem:
                return "incompleta", f"incompleta: {len(sem)} microssetor{'es' if len(sem) != 1 else ''} sem medida (parada ou longe do traçado)"
            return "incompleta", "incompleta"
        if medidas is None:
            return "incompleta", "incompleta: sem as medidas da volta"
        return "valida", "válida"

    def _guardar_a_volta(self, volta: Dict[str, Any], estado: str, motivo: str,
                         medidas: Optional[List[Dict[str, Any]]]) -> None:
        """Pedido 45 (E.3): a volta fica guardada, com os pontos na grade em float32 (~43 KB por volta)."""
        numero = int(volta["volta"]) if volta.get("volta") is not None else None
        guardada = self._grade_da_ultima if (self._grade_da_ultima or {}).get("volta") == volta.get("volta") else None
        grade32 = {k: np.asarray(v, dtype=np.float32) for k, v in guardada["grade"].items()} if guardada and medidas else None
        self._voltas_da_sessao.append({"volta": numero, "tempoS": round(float(volta["tempoS"]), 3), "estado": estado,
                                       "motivo": motivo, "medidas": medidas, "grade": grade32})

    def _conferir_a_sessao(self) -> None:
        """Outra sessao: a analise e a grade comecam de novo."""
        sessao = self._sessao()
        if sessao != self._sessao_da_analise:
            if self._eng() is not None:
                try:
                    self._eng().nova_sessao(sessao, self._sua_melhor_volta())
                except Exception as erro:
                    logger.warning("Engenheiro sem a sua melhor volta: %s", erro)
                    self._eng().nova_sessao(sessao, None)
            self._sessao_da_analise, self._voltas_validas = sessao, []
            self._grade_voltas, self._grade_fora, self._grade_citadas = [], [], []
            self._voltas_da_sessao = []
            self._melhor_s, self._melhor_volta, self._anterior_que_contou = None, None, None

    def _fora_da_grade(self, volta: Dict[str, Any], motivo: str) -> None:
        numero = int(volta["volta"]) if volta.get("volta") is not None else None
        tempo = round(float(volta["tempoS"]), 3) if volta.get("tempoS") is not None else None
        self._grade_fora.append({"volta": numero, "tempoS": tempo, "motivo": motivo})

    def _analise_da_volta(self, volta: Dict[str, Any], medidas: Optional[List[Dict[str, Any]]],
                          ref: Dict[str, Any]) -> None:
        self._conferir_a_sessao()
        # Pedido 43 (C.4): a volta que nao entra na analise fica fora da grade, com o motivo.
        if medidas is None:
            self._fora_da_grade(volta, "sem as medidas da volta")
            return
        if volta.get("completa") is False:
            self._fora_da_grade(volta, "incompleta")
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
        mensagem = mensagem_de_analise(resultado, ref.get("tipo"), ref.get("volta"), self._tendencia())
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

    def _tendencia(self) -> Optional[str]:
        """Pedido 45 (C.3): a media das 3 voltas validas contra a das 3 anteriores."""
        tempos = [v.get("tempoS") for v in self._voltas_validas]
        if len(tempos) < 2 * VOLTAS_POR_ANALISE or any(x is None for x in tempos[-2 * VOLTAS_POR_ANALISE:]):
            return None
        n = VOLTAS_POR_ANALISE
        return frase_da_tendencia(sum(tempos[-n:]) / n, sum(tempos[-2 * n:-n]) / n)

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
        pronto = mensagem.pop("_arquivoPronto", None)
        if pronto is not None:
            arquivo = Path(pronto)
            for k, outro, _d, _f in mensagem.pop("_variantes", None) or []:
                if Path(outro) != arquivo:
                    try:
                        Path(outro).unlink()
                    except OSError:
                        pass
        elif futuro is not None and futuro.done():
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
        self._depois_de_escolher_a_fala(mensagem)
        if mensagem.get("_replay"):
            # Pedido 45 (D.6): os numeros da voz, no alto do replay.
            for c in mensagem["_replay"]:
                c["textoDaVoz"] = fala_da_curva(mensagem.get("fala"), c.get("curva"))
            mensagem["replay"] = {"url": f"/api/radio/replay/{mensagem['id']}",
                                  "curvas": [c["curva"] for c in mensagem["_replay"]]}
        self._citar(mensagem)
        if arquivo is not None:
            mensagem["audio"] = f"/api/radio/audio/{mensagem['id']}"
            mensagem["audioArquivo"] = str(Path(arquivo).resolve())   # pedido 35: o 2o caminho da voz no jogo
            mensagem["_arquivo"] = str(arquivo)
        self._ocupado_ate = agora + float(mensagem.get("duracaoS") or 3.0) + FOLGA_ENTRE_MENSAGENS_S
        self._ultima_entregue = mensagem if mensagem.get("origem") in FEEDBACK else None
        self._entregues.append(mensagem)
        self._registrar(mensagem)
        return mensagem

    def _depois_de_escolher_a_fala(self, mensagem: Dict[str, Any]) -> None:
        """Pedido 45 (C.1, item 5): se a curva nao coube no resumo, ela vai numa mensagem propria, para o
        fim da fila (sem passar a frente das frases do coach). Ela sai da fila se a curva passar antes."""
        pior = mensagem.get("_curvaDaVolta")
        if not pior or int(mensagem.get("_falaEscolhida") or 0) < int(mensagem.get("falasComACausa") or 0):
            return
        ref = self._referencia() or {}
        propria = mensagem_da_curva(mensagem.get("volta"), pior, ref.get("tipo"))
        propria["_replay"] = mensagem.pop("_replay", None) or []
        propria["_curvaS"] = self._inicio_da_curva(pior.get("curva"))
        mensagem["curvaEmMensagemPropria"] = True
        self.contagem["curvaEmMensagemPropria"] += 1
        self._pendentes.append(self._nova(propria))
        self._s_da_fila = None

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
            # A volta citada antes da primeira que fechou (a de saida dos boxes) tambem entra; a citada
            # depois da ultima que fechou ainda esta em andamento.
            fora = list(self._grade_fora)
            vistas = {v["volta"] for v in self._grade_voltas} | {f["volta"] for f in fora}
            vistas.discard(None)
            if vistas:
                inicio = min(vistas | {c["volta"] for c in self._grade_citadas})
                fora += [{"volta": n, "tempoS": None, "motivo": "o rádio não viu esta volta fechar na linha"}
                         for n in range(inicio, max(vistas)) if n not in vistas]
                fora.sort(key=lambda f: f["volta"] if f["volta"] is not None else -1)
            # Decisao do Eduardo: cada volta de fora lista as curvas citadas pelo radio nela.
            fora = [{**f, "citadas": list(dict.fromkeys(c["curva"] for c in self._grade_citadas
                                                        if c["volta"] == f["volta"]))} for f in fora]
            return {"sessao": self._sessao_da_analise, "curvas": curvas,
                    "voltas": [{"volta": v["volta"], "tempoS": v["tempoS"],
                                "perdas": [v["perdas"].get(c) for c in curvas]} for v in self._grade_voltas],
                    "fora": fora, "citadas": list(self._grade_citadas)}

    # ------------------------------------------- as voltas da sessao (pedido 45) ---

    def voltas_da_sessao(self) -> Dict[str, Any]:
        """Pedido 45 (E.2): todas as voltas da sessao, com o numero, o tempo, a diferenca para a melhor,
        o estado com o motivo e a perda em cada curva (quando a volta tem as medidas). As que nao
        fecharam na linha entram pelo numero, sem tempo e sem replay."""
        with self._lock:
            self._pista()
            curvas = [seg.corner.label[:3] for seg in self._geometria.segmentos] if self._geometria else []
            melhor = self._melhor_s
            linhas = []
            for v in self._voltas_da_sessao:
                perdas = {m["curva"]: m["perdaS"] for m in v["medidas"]} if v["medidas"] else {}
                linhas.append({"volta": v["volta"], "tempoS": v["tempoS"],
                               # O tempo da parcial e o corrido, com as paradas: nao se compara com a melhor.
                               "difMelhorS": round(v["tempoS"] - melhor, 3) if melhor is not None and not v.get("parcial") else None,
                               "estado": v["estado"], "motivo": v["motivo"],
                               "perdas": [perdas.get(c) for c in curvas],
                               "citadas": sorted({c["curva"] for c in self._grade_citadas if c["volta"] == v["volta"]}),
                               "temReplay": v["grade"] is not None and v["estado"] != "ia"})
            vistas = {x["volta"] for x in linhas if x["volta"] is not None}
            if vistas:
                for n in range(min(vistas), max(vistas)):
                    if n not in vistas:
                        linhas.append({"volta": n, "tempoS": None, "difMelhorS": None, "estado": "incompleta",
                                       "motivo": "incompleta: não fechou na linha (boxes ou carro movido)",
                                       "perdas": [None for _ in curvas], "citadas": [], "temReplay": False})
            linhas.sort(key=lambda x: x["volta"] if x["volta"] is not None else -1)
            return {"sessao": self._sessao_da_analise, "curvas": curvas, "melhorS": round(melhor, 3) if melhor is not None else None,
                    "melhorVolta": self._melhor_volta, "voltas": linhas,
                    "mensagem": None if linhas else "nenhuma volta fechada nesta sessão"}

    def replay_da_volta(self, numero: int, curva: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Pedido 45 (E.3): o replay de qualquer volta e de qualquer curva, no formato de `replay`,
        com os numeros da analise. None sem os pontos da volta (a da IA, a que nao fechou na linha)."""
        with self._lock:
            achada = next((v for v in reversed(self._voltas_da_sessao) if v["volta"] == int(numero)), None)
            geometria = self._geometria
            if achada is None or achada["grade"] is None or achada["estado"] == "ia" or geometria is None:
                return None
            ref = self._grade_da_referencia()
            tipo = (self._referencia() or {}).get("tipo")
        if ref is None:
            return None
        g = {k: np.asarray(v, dtype=float) for k, v in achada["grade"].items()}
        aviso = "fora da análise: rodada" if achada["estado"] == "rodada" else (
            (achada["motivo"] if achada["motivo"].startswith("fora da análise") else "fora da análise: incompleta")
            if achada["estado"] == "incompleta" else None)
        medidas = achada["medidas"] or []
        if curva is None:
            perdas = {m["curva"]: m["perdaS"] for m in medidas}
            dados = dados_da_volta(geometria, g, achada["tempoS"], ref["grade"], ref["tempoS"], achada["volta"], tipo, perdas)
        else:
            m = next((x for x in medidas if x["curva"] == curva), None)
            causa = causa_da_curva(m) if m else None
            dados = dados_da_curva(geometria, curva, g, achada["tempoS"], ref["grade"], ref["tempoS"], achada["volta"],
                                   tipo, causa=causa)
            if dados is None:
                return None
            if m and float(m["perdaS"]) >= 0.05:
                dados["textoDaVoz"] = falas_da_curva({**m, "causa": causa}, tipo)["completa"]
        dados["aviso"] = aviso
        dados["tempoDaVoltaS"] = achada["tempoS"]
        return {"id": None, "origem": "sessao", "volta": achada["volta"], "curvas": [dados]}

    def melhor_da_sessao(self) -> Dict[str, Any]:
        """Pedido 45 (C.4): a melhor volta da sessao, em pontos (x, z, tempo), para a diferenca no minimapa."""
        with self._lock:
            achada = next((v for v in self._voltas_da_sessao if v["volta"] == self._melhor_volta and v["grade"] is not None), None)
            geometria = self._geometria
            if achada is None or geometria is None:
                return {"disponivel": False}
            track = geometria.track
            passo = max(1, int(np.ceil(int(track.size) / PONTOS_DA_MELHOR)))
            r = np.arange(0, int(track.size), passo)
            lat = np.nan_to_num(np.asarray(achada["grade"]["lateral"], dtype=float))
            normal = np.asarray(track.normal, dtype=float)
            x = np.asarray(track.x, dtype=float)[r] + normal[r, 0] * lat[r]
            z = np.asarray(track.z, dtype=float)[r] + normal[r, 1] * lat[r]
            el = np.asarray(achada["grade"]["elapsed"], dtype=float)[r]
            return {"disponivel": True, "volta": achada["volta"], "tempoS": achada["tempoS"],
                    "pontos": [[round(float(a), 2), round(float(b), 2), round(float(c), 3)] for a, b, c in zip(x, z, el)]}

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
        return {k: v for k, v in m.items() if not k.startswith("_") and k not in ("falas", "falasComACausa")}

    def desde(self, id_: int = 0, instancia: Optional[str] = None) -> Dict[str, Any]:
        """As mensagens entregues depois de `id_`. Outra instancia (backend reiniciado): todas."""
        with self._lock:
            desde = 0 if instancia and instancia != self.instancia else int(id_ or 0)
            novas = [self._publica(m) for m in self._entregues if m["id"] > desde]
            return {"instancia": self.instancia, "ultimoId": self._proximo_id - 1, "mensagens": novas,
                    "pendentes": len(self._pendentes), "erroDaVoz": self.erro_da_voz,
                    "minimapaVersao": self.versao_do_minimapa(), "melhorVolta": self._melhor_volta,
                    "voltasDaSessao": len(self._voltas_da_sessao),
                    "engenheiroVersao": self._eng().versao if self._eng() is not None else None}

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
                    "voltasValidasDaSessao": len(self._voltas_validas), "contagem": dict(self.contagem),
                    "engenheiro": {"ligado": self.engenheiro_ligado, "ativo": self._eng() is not None,
                                   "motivo": self._engenheiro_erro,
                                   "blocos": [[b["inicio"], b["fim"]] for b in (self._eng().blocos if self._eng() else [])
                                              if b.get("fim") is not None]}}

    def arquivo_da_fala_do_engenheiro(self, chave: str) -> Optional[Path]:
        """Pedido 52 (ADR 0033, emenda de 20/11, item 2): o audio de uma fala planejada, para o app do jogo baixar."""
        with self._lock:
            eng = self._eng()
        return eng.arquivo_da_fala(chave) if eng is not None else None

    def engenheiro(self) -> Dict[str, Any]:
        """Pedido 52: a lista do engenheiro para a janela do app do jogo (`GET /api/radio/engenheiro`)."""
        with self._lock:
            self._pista()
            eng = self._eng()
            if eng is None:
                motivo = ("o engenheiro está desligado (AT_ENGENHEIRO)" if not self.engenheiro_ligado else
                          self._engenheiro_erro or "sem a geometria oficial")
                return {"disponivel": False, "motivo": motivo}
            return eng.estado_publico(dict(self._lenta))

"""O engenheiro dentro do radio (pedido 52, Parte C; ADR 0033): a lista da volta, os avisos e a conferencia.

O radio (`core.radio.servico.RadioDoEngenheiro`) chama:

* `na_linha(...)`, na linha, numa volta que conta: confere as dicas dadas na volta e refaz a lista;
* `no_quadro(...)`, a cada quadro: marca as dicas dadas (a janela mostrou) e devolve as falas planejadas que
  comecaram agora (o app do jogo toca cada uma pelo mesmo `s`, com o audio ja baixado; ADR 0033, emenda de 20/11);
* `reserva(s)` e `tempo_entre(...)`: onde comeca a reserva dos avisos no bloco em que o carro esta e o tempo ate
  la pelo perfil (o feedback tem de acabar antes);
* `estado_publico(...)`: a lista e as falas planejadas para o app do jogo (`GET /api/radio/engenheiro`).

O plano das falas (o perfil, os pedacos livres, a acao do piloto, os pares e a folga de 3,0 s) esta em `plano.py`.

Nada de modelo, store ou coach muda: so le a volta do modelo, os marcos, o ruido por trecho e as voltas
que o radio ja mede.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import marcos as M
from . import plano as P
from . import regras as R

logger = logging.getLogger(__name__)

PISTA = "vhe_interlagos"
ESTADO_DA_DICA = ("na lista", "aplicada")


class Engenheiro:
    def __init__(self, track, pista_do_radio, raizes: Callable[[], Sequence[Optional[Path]]],
                 falar_em_segundo_plano: Callable[[str], Any], registrar: Callable[[Dict[str, Any]], None],
                 relogio: Optional[Callable[[], float]] = None, molde: Optional[str] = None, bipe: Optional[bool] = None):
        """`pista_do_radio`: a `analise.Pista` do radio; `falar_em_segundo_plano(fala)`: um futuro que devolve
        (arquivo, duracao); `registrar(linha)`: grava uma linha no `<sessao>.engenheiro.jsonl`. `molde` (a, b ou c)
        e `bipe`: sem eles, `AT_ENGENHEIRO_MOLDE` (padrao b, a escolha de 20/11) e `AT_ENGENHEIRO_BIPE` (padrao ligado)."""
        from core.assisted_analysis import volta_do_modelo as VM
        from core.radio.analise import grade

        self.track = track
        self.pista = pista_do_radio
        self.L = float(track.length)
        self.trechos = R.trechos_da_pista(track)
        self._falar = falar_em_segundo_plano
        self._registrar = registrar
        self.relogio = relogio
        self._lock = threading.RLock()
        # ADR 0033, emenda de 20/11, itens 8 e 9
        molde = (molde or os.environ.get("AT_ENGENHEIRO_MOLDE") or P.MOLDE_PADRAO).strip().lower()
        self.molde = molde if molde in P.MOLDES else P.MOLDE_PADRAO
        self.bipe = bool(bipe) if bipe is not None else (
            os.environ.get("AT_ENGENHEIRO_BIPE", "").strip().lower() not in ("desligado", "0", "nao", "não", "false"))
        raizes = list(raizes())
        self.marcos = M.encontrar(raizes, PISTA)
        from .preparar import encontrar_o_ruido
        self.ruido = encontrar_o_ruido(raizes, PISTA)
        dados = VM.encontrar(raizes, PISTA)
        self.motivo: Optional[str] = None
        if dados is None:
            self.motivo = VM.SEM_VOLTA_DO_MODELO
        elif self.marcos is None:
            self.motivo = "sem o arquivo dos marcos da pista"
        elif self.ruido is None:
            self.motivo = "sem o ruído por trecho"
        elif dados.get("geometry_id") and dados.get("geometry_id") != getattr(track, "geometry_id", dados.get("geometry_id")):
            self.motivo = "a volta do modelo é de outra geometria"
        self.ativo = self.motivo is None
        self.pontos_dos_marcos = M.pontos_de_referencia(self.marcos["marcos"]) if self.marcos else []
        self.ruido_por_trecho = {t["trecho"]: float(t["ruidoS"]) for t in (self.ruido or {}).get("trechos", [])}
        # ADR 0033, emenda de 16/11, item 4: a busca da freada comeca na saida do trecho anterior (tambem na
        # medida da causa do engenheiro; o feedback do radio continua com a regra do 45)
        self.inicio_da_freada = {t.nome[:3]: R.inicio_da_busca_da_freada(self.trechos, k)
                                 for k, t in enumerate(self.trechos) if t.tem_curva}
        if dados is not None:
            store = VM.como_volta_do_store(dados)
            self.modelo = {"grade": grade(store), "tempoS": float(store["tempoS"]), "origem": "volta_do_modelo",
                           "rotulo": "volta de referência"}
            self.tempos_modelo = R.tempos_dos_trechos(self.modelo["grade"]["elapsed"], self.modelo["tempoS"], track, self.trechos)
            self.blocos = R.blocos_de_voz(self.modelo["grade"], self.modelo["tempoS"], track, self.trechos)
        else:
            self.modelo, self.tempos_modelo, self.blocos = None, None, []
        # ADR 0033, emenda de 16/11, item 1: as retas longas (os blocos de 8,8 s ou mais na volta do modelo)
        self.retas_longas = [b for b in self.blocos if b.get("fim") is not None and (b.get("duracaoS") or 0) >= R.RETA_LONGA_S]
        # o estado da sessao
        self.lista: Dict[str, Dict[str, Any]] = {}
        self.versao = 0
        self.ultima_conferencia: Optional[Dict[str, Any]] = None
        self.melhores: Dict[str, Dict[str, Any]] = {}       # trecho -> {tempoS, grade, total, origem}
        self._audios: Dict[str, Any] = {}                  # fala -> futuro (arquivo, duracao)
        self._s_anterior: Optional[float] = None
        self._volta_anterior: Optional[int] = None
        self._sessao: Optional[str] = None
        self.contagem = {"avisosPelaVoz": 0, "avisosSoNaJanela": 0}
        # trecho -> a dica como foi dada (a frase, o ponto dito, a voz), ate a conferencia (ADR 0033, item 8)
        self._dadas: Dict[str, Dict[str, Any]] = {}
        # o plano das falas (ADR 0033, emenda de 20/11): o perfil, os pedacos livres e as falas
        self.perfil: Optional[P.Perfil] = None
        self.pedacos: List[Dict[str, float]] = []
        self.falas: List[Dict[str, Any]] = []
        self._medidas_no_plano: set = set()
        self._sozinhas_medidas: set = set()
        self._voz_liberada = True
        if self.modelo is not None:
            self._usar_o_perfil(self.modelo["grade"], self.modelo["tempoS"], "volta de referência")

    # ── a sessao ────────────────────────────────────────────────────────

    def nova_sessao(self, sessao: Optional[str], sua_melhor: Optional[Dict[str, Any]]) -> None:
        """Outra sessao: a lista comeca vazia; a melhor passagem comeca pela "Sua melhor volta" (do store)."""
        with self._lock:
            self._sessao = sessao
            self.lista, self.ultima_conferencia, self._dadas = {}, None, {}
            self.melhores = {}
            self._s_anterior = None
            self.falas = []
            self.versao += 1
            if sua_melhor is not None:
                self._considerar_passagens(sua_melhor["grade"], sua_melhor["tempoS"], "sua melhor volta")
            # o perfil (ADR 0033, emenda de 20/11, item 5): antes da primeira volta que conta, a "Sua melhor volta";
            # sem ela, a volta de referencia
            if sua_melhor is not None:
                self._usar_o_perfil(sua_melhor["grade"], sua_melhor["tempoS"], "sua melhor volta")
            elif self.modelo is not None:
                self._usar_o_perfil(self.modelo["grade"], self.modelo["tempoS"], "volta de referência")

    def _considerar_passagens(self, grade: Dict[str, np.ndarray], total: float, origem: str) -> None:
        tempos = R.tempos_dos_trechos(grade["elapsed"], total, self.track, self.trechos)
        for t, x in zip(self.trechos, tempos):
            atual = self.melhores.get(t.nome)
            if np.isfinite(x) and x > 0 and (atual is None or x < atual["tempoS"]):
                self.melhores[t.nome] = {"tempoS": float(x), "grade": grade, "total": float(total), "origem": origem}

    def referencia_do_trecho(self, k: int) -> Dict[str, Any]:
        """A volta do modelo; ou a melhor passagem do piloto, se ela for mais rapida no trecho (ADR 0033, item 2)."""
        nome = self.trechos[k].nome
        melhor = self.melhores.get(nome)
        if melhor is not None and melhor["tempoS"] < float(self.tempos_modelo[k]):
            return {"grade": melhor["grade"], "tempoS": melhor["total"], "origem": "melhor_passagem",
                    "rotulo": f"a sua melhor passagem ({melhor['origem']})", "tempoDoTrechoS": melhor["tempoS"]}
        return {**self.modelo, "tempoDoTrechoS": float(self.tempos_modelo[k])}

    # ── a linha ─────────────────────────────────────────────────────────

    def na_linha(self, volta: Optional[int], grade: Optional[Dict[str, np.ndarray]], total: Optional[float],
                 conta: bool) -> Optional[Dict[str, Any]]:
        """ADR 0033, itens 1 e 8: a conferencia das dicas dadas e a lista nova. Devolve a conferencia (ou None)."""
        if not self.ativo:
            return None
        with self._lock:
            # As dicas dadas cuja acao o carro ja passou sao conferidas nesta volta; a dica dada antes da linha
            # para uma acao depois dela (a C01) espera a volta seguinte.
            dadas = [d for d in self._dadas.values() if d.get("acaoPassada")]
            for d in dadas:
                del self._dadas[d["trecho"]]
            if not conta or grade is None or total is None:
                self.versao += 1
                return None
            from core.radio.analise import medidas_da_volta
            tempos = R.tempos_dos_trechos(grade["elapsed"], total, self.track, self.trechos)
            # a conferencia
            conferidas = []
            aplicadas_agora = set()
            for item in dadas:
                k = item["k"]
                pts = R.pontos_do_trecho(grade, total, self.track, self.trechos, k)
                conf = R.conferir(item, pts, self.L)
                conf["texto"] = R.texto_da_conferencia(item, conf, self.L)
                item["conferidaNaVolta"] = volta
                if conf.get("aplicada") is True:
                    aplicadas_agora.add(item["trecho"])
                conferidas.append({"trecho": item["trecho"], "acao": item["acao"], "frase": item["frase"],
                                   "voz": item.get("pelaVoz", False), **conf})
                self._registrar({"tipo": "conferencia", "volta": volta, "trecho": item["trecho"], "causa": item["causa"],
                                 "frase": item["frase"], "sFala": item.get("sFala"), "voz": item.get("pelaVoz", False),
                                 "aplicada": conf.get("aplicada"), "valor": conf.get("valor"), "texto": conf["texto"]})
            # a lista nova: cada trecho contra a referencia dele
            refs: Dict[int, Dict[str, Any]] = {k: self.referencia_do_trecho(k) for k in range(len(self.trechos))}
            medidas_por_ref: Dict[int, List[Dict[str, Any]]] = {}
            for k, ref in refs.items():
                chave = id(ref["grade"])
                if chave not in medidas_por_ref:
                    try:
                        medidas_por_ref[chave] = medidas_da_volta(grade, total, ref["grade"], ref["tempoS"], self.pista,
                                                                  inicio_da_freada=self.inicio_da_freada)
                    except Exception as erro:
                        logger.warning("Engenheiro sem as medidas da volta: %s", erro)
                        medidas_por_ref[chave] = []
            novos = set()
            perdas = {}
            for k, t in enumerate(self.trechos):
                ref = refs[k]
                perda = float(tempos[k]) - float(ref["tempoDoTrechoS"])
                perdas[t.nome] = round(perda, 4)
                if not perda > self.ruido_por_trecho.get(t.nome, float("inf")):
                    continue
                medida = next((m for m in medidas_por_ref.get(id(ref["grade"]), []) if m.get("curva") == t.nome), None)
                item = self._item(k, ref, medida, perda, volta)
                anterior = self.lista.get(t.nome)
                if anterior is not None:
                    item["desdeAVolta"] = anterior.get("desdeAVolta", volta)
                self.lista[t.nome] = item
                novos.add(t.nome)
            # sai da lista a dica aplicada que a volta nova nao pos de volta; a conferencia fica no item que continua
            for nome in list(self.lista):
                if nome not in novos and nome in aplicadas_agora:
                    del self.lista[nome]
            por_trecho = {c["trecho"]: c for c in conferidas}
            for nome, i in self.lista.items():
                if nome in por_trecho:
                    i["conferencia"] = por_trecho[nome]
            aplicadas = sum(1 for c in conferidas if c.get("aplicada") is True)
            medidas = sum(1 for c in conferidas if c.get("aplicada") is not None)
            self.ultima_conferencia = {"volta": volta, "conferidas": conferidas, "aplicadas": aplicadas, "medidas": medidas,
                                       "texto": f"{aplicadas} de {medidas} avisos aplicados" if medidas else None}
            self._registrar({"tipo": "volta", "volta": volta, "tempoS": round(float(total), 3), "perdas": perdas,
                             "lista": [{"trecho": i["trecho"], "causa": i["causa"], "frase": i["frase"], "voz": i["voz"]}
                                       for i in self._ordenada()],
                             "aplicadas": aplicadas, "medidas": medidas})
            self._considerar_passagens(grade, total, f"volta {volta}")
            # o perfil passa a ser esta volta, e o plano das falas e refeito (ADR 0033, emenda de 20/11, item 5)
            numero = int(volta) if isinstance(volta, (int, float)) and float(volta).is_integer() else volta
            self._usar_o_perfil(grade, total, f"volta {numero} da sessão")
            self._replanejar()
            self._registrar({"tipo": "plano", "volta": volta, "perfil": self.perfil.origem,
                             "falas": [{"sFala": f["sFala"], "texto": f["texto"], "duracaoS": f["duracaoS"],
                                        "trechos": f["trechos"], "folgaS": f["folgaS"], "candidato": f["candidato"]}
                                       for f in self.falas],
                             "soNaJanela": [{"trecho": i["trecho"], "motivo": i.get("porqueSoNaJanela")}
                                            for i in self._ordenada() if i.get("frase") and not i.get("voz")]})
            self.versao += 1
            return self.ultima_conferencia

    def _item(self, k: int, ref: Dict[str, Any], medida: Optional[Dict[str, Any]], perda: float,
              volta: Optional[int]) -> Dict[str, Any]:
        t = self.trechos[k]
        causa = R.causa_do_engenheiro(medida) if t.tem_curva else None
        pts = R.pontos_do_trecho(ref["grade"], ref["tempoS"], self.track, self.trechos, k)
        item: Dict[str, Any] = {"k": k, "trecho": t.nome, "curva": R.numero_da_curva(t.nome), "perdaS": round(perda, 3),
                                "referencia": ref["origem"], "referenciaRotulo": ref["rotulo"], "desdeAVolta": volta,
                                "causa": None, "acao": None, "frase": None, "fala": None, "voz": False,
                                "sFala": None, "sAcao": None, "conferencia": None}
        if causa is None:
            return item
        acao = causa["acao"]
        # ADR 0033, emenda de 16/11, item 3: a referencia nao freia nem alivia no trecho: "sem tirar o pé"
        sem_tirar = bool(pts.get("semTirarOPe"))
        if sem_tirar:
            acao = R.SEM_TIRAR_O_PE
        chave = {"freie": "freada", "vire": "entrada", "acelere": "retomada", R.SEM_TIRAR_O_PE: "entrada"}[acao]
        s_acao = pts.get(chave)
        item.update(causa=causa["causa"], acao=acao, valorDaCausa=causa["valor"], unidade=causa["unidade"])
        if s_acao is None:
            item["semPonto"] = f"a referência não tem {chave} no trecho"
            return item
        f = (R.frase_sem_tirar_o_pe(s_acao, self.L) if sem_tirar
             else R.frase_da_acao(acao, s_acao, self.pontos_dos_marcos, self.L))
        # ADR 0033, emenda de 20/11, item 8: a voz no molde escolhido; a janela e o cartao no molde (a), com "Curva N:"
        falada = P.frase_falada(acao, f["marco"], f["d"], self.molde, f["frase"])
        k_ponto = int(self.track.index_of(s_acao))
        item.update(frase=f["frase"], fraseFalada=falada, fala=P.fala_sozinha(falada),
                    escrita=R.escrita_do_aviso(t.nome, f["frase"]), comMarco=f["comMarco"],
                    marco=f["marco"], d=f["d"], sDito=f["sDito"],
                    sAcao=round(float(s_acao), 1), refMinimaKmh=pts.get("minimaKmh"),
                    refFreada=pts.get("freada"), vFreadaKmh=pts.get("velocidadeNaFreadaKmh"),
                    vNoPontoKmh=float(np.asarray(ref["grade"]["velocidade"], float)[k_ponto]))
        if not sem_tirar:
            # a marca no asfalto e o bipe: no ponto dito (ADR 0033, emenda de 20/11, item 9)
            k_dito = int(self.track.index_of(float(f["sDito"])))
            lateral = np.asarray(ref["grade"]["lateral"], float)
            lat = float(lateral[k_dito]) if np.isfinite(lateral).any() else 0.0
            x, z = self.track.to_world([float(f["sDito"])], [lat])[0]
            item.update(x=round(float(x), 2), z=round(float(z), 2),
                        direcao=[round(float(self.track.tangent[k_dito][0]), 4), round(float(self.track.tangent[k_dito][1]), 4)],
                        bipe=self.bipe, sBipe=round(float(f["sDito"]), 1) if self.bipe else None)
        else:
            item.update(bipe=False, sBipe=None)
        self._pedir_a_voz(item["fala"])
        return item

    # ── a voz ───────────────────────────────────────────────────────────

    def _pedir_a_voz(self, fala: Optional[str]) -> None:
        if fala and fala not in self._audios:
            try:
                self._audios[fala] = self._falar(fala)
            except Exception as erro:
                logger.warning("Engenheiro sem voz: %s", erro)

    def duracao(self, fala: Optional[str]) -> Optional[float]:
        f = self._audios.get(fala or "")
        if f is None or not f.done():
            return None
        try:
            r = f.result()
        except Exception:
            return None
        return float(r[1]) if r else None

    def audio(self, fala: Optional[str]) -> Optional[Tuple[Path, float]]:
        f = self._audios.get(fala or "")
        if f is None or not f.done():
            return None
        try:
            return f.result()
        except Exception:
            return None

    @staticmethod
    def chave(fala: str) -> str:
        return hashlib.sha1(fala.encode("utf-8")).hexdigest()[:12]

    def arquivo_da_fala(self, chave: str) -> Optional[Path]:
        """O audio de uma fala planejada, pela chave (`GET /api/radio/engenheiro/audio/{chave}`)."""
        with self._lock:
            for fala in list(self._audios):
                if self.chave(fala) == chave:
                    r = self.audio(fala)
                    return Path(r[0]) if r else None
        return None

    # ── o plano (ADR 0033, emenda de 20/11) ────────────────────────────

    def _usar_o_perfil(self, grade: Dict[str, np.ndarray], total: float, origem: str) -> None:
        self.perfil = P.Perfil(grade, total, self.track, origem)
        self.pedacos = P.pedacos_livres(grade, self.track)

    def _replanejar(self) -> None:
        """Refaz o plano das falas com o perfil atual (depois de cada volta que conta, de uma lista nova ou de uma
        duracao medida)."""
        if self.perfil is None:
            self.falas, self._medidas_no_plano = [], set()
            return
        avisos: List[P.Aviso] = []
        for i in self._ordenada():
            i.update(voz=False, sFala=None, falaChave=None, porqueSoNaJanela=None, sAcaoPiloto=None, tipoDaAcaoPiloto=None,
                     sJanela=None, sFimDaJanela=None)
            if i.get("frase") is None or i.get("sDito") is None:
                continue
            a = P.acao_do_piloto(self.perfil.grade, self.track, self.trechos, i["k"], i["acao"])
            if a is None:
                i["porqueSoNaJanela"] = "sem a volta ao acelerador no perfil"
                continue
            s_acao, tipo = a
            fim = s_acao if self.perfil.dt(i["sDito"], s_acao) <= self.perfil.dt(s_acao, i["sDito"]) else i["sDito"]
            i.update(sAcaoPiloto=round(s_acao, 1), tipoDaAcaoPiloto=tipo,
                     sJanela=round(P.s_da_janela(self.perfil, self.pedacos, s_acao), 1),
                     sFimDaJanela=round((float(fim) + P.DEPOIS_DA_ACAO_M) % self.L, 1))
            avisos.append(P.Aviso(trecho=i["trecho"], numero=i.get("curva"), frase=i["fraseFalada"], s_acao=s_acao,
                                  s_dito=float(i["sDito"]), ordem=i["k"]))
        falas = P.planejar(avisos, self.perfil, self.pedacos, self.duracao)
        por_trecho = {}
        for f in falas:
            f["chave"] = self.chave(f["texto"])
            f["audio"] = f"/api/radio/engenheiro/audio/{f['chave']}"
            self._pedir_a_voz(f["texto"])
            for tr in f["trechos"]:
                por_trecho[tr] = f
        for a in avisos:
            i = self.lista[a.trecho]
            f = por_trecho.get(a.trecho)
            if f is not None:
                i.update(voz=True, sFala=f["sFala"], falaChave=f["chave"], folgaPlanejadaS=f["folgaS"].get(a.trecho),
                         falaJunta=len(f["trechos"]) > 1)
            else:
                i.update(voz=False, porqueSoNaJanela=a.motivo or "não planejado")
        self.falas = falas
        self._medidas_no_plano = {f["texto"] for f in falas if f["duracaoMedida"]}
        self.versao += 1

    def _replanejar_se_mediu(self) -> None:
        """A voz mediu uma fala do plano ou uma fala sozinha (usada na estimativa do par): refaz o plano."""
        textos = {f["texto"] for f in self.falas} | {i["fala"] for i in self.lista.values() if i.get("fala")}
        medidas = {x for x in textos if self.duracao(x) is not None}
        if medidas - self._sozinhas_medidas:
            self._sozinhas_medidas |= medidas
            self._replanejar()

    def _ordenada(self) -> List[Dict[str, Any]]:
        return sorted(self.lista.values(), key=lambda i: i["k"])

    # ── o quadro ────────────────────────────────────────────────────────

    def no_quadro(self, s: Optional[float], velocidade_kmh: Optional[float], desde_a_linha: bool, ia: bool,
                  falando: bool = False) -> List[Dict[str, Any]]:
        """A cada quadro (ADR 0033, emenda de 20/11, item 2): o carro passou o `s_fala` de uma fala planejada? A fala
        comeca no jogo (o app do jogo toca pelo mesmo `s`); o backend registra e devolve as falas que comecaram,
        para a reserva e o corte do feedback. Marca tambem as dicas dadas (a janela mostrou) e a acao passada."""
        if not self.ativo or s is None:
            return []
        with self._lock:
            self._voz_liberada = bool(desde_a_linha) and not ia
            self._replanejar_se_mediu()
            anterior, self._s_anterior = self._s_anterior, float(s)
            if anterior is None:
                return []
            andou = (float(s) - anterior) % self.L
            if andou > self.L / 2 or andou <= 0:
                return []

            def passou(alvo: Optional[float]) -> bool:
                return alvo is not None and (float(alvo) - anterior) % self.L <= andou

            for d in self._dadas.values():
                if not d.get("acaoPassada") and passou(d.get("sAcao")):
                    d["acaoPassada"] = True
            # a janela mostra o aviso desde o fim da acao anterior: a dica foi dada
            for item in self._ordenada():
                if item.get("frase") is None or item["trecho"] in self._dadas and not self._dadas[item["trecho"]].get("acaoPassada"):
                    continue
                if not passou(item.get("sJanela")):
                    continue
                self._dadas[item["trecho"]] = {k: item.get(k) for k in ("k", "trecho", "acao", "causa", "frase", "sFala", "sAcao",
                                                                        "sDito", "marco", "refMinimaKmh")}
                self._dadas[item["trecho"]].update(pelaVoz=bool(item.get("voz")) and self._voz_liberada, acaoPassada=False)
                item["pelaVoz"] = self._dadas[item["trecho"]]["pelaVoz"]
                if not item.get("voz"):
                    self.contagem["avisosSoNaJanela"] += 1
                    self._registrar({"tipo": "aviso", "trecho": item["trecho"], "causa": item["causa"], "frase": item["frase"],
                                     "sJanela": item.get("sJanela"), "sCarro": round(float(s), 1), "t": self._relogio(),
                                     "velocidadeKmh": None if velocidade_kmh is None else round(float(velocidade_kmh), 1),
                                     "voz": False, "porqueSoNaJanela": item.get("porqueSoNaJanela"),
                                     "sAcaoPiloto": item.get("sAcaoPiloto"), "sDito": item.get("sDito"),
                                     "bipe": item.get("sBipe")})
            # as falas planejadas
            comecaram = []
            for f in self.falas:
                if not passou(f["sFala"]):
                    continue
                motivo = None if self._voz_liberada else ("volta de saída dos boxes" if not desde_a_linha else "a IA no volante")
                for tr in f["trechos"]:
                    i = self.lista.get(tr) or {}
                    self._registrar({"tipo": "aviso", "trecho": tr, "causa": i.get("causa"), "frase": i.get("frase"),
                                     "fala": f["texto"], "falaJunta": len(f["trechos"]) > 1, "sFala": f["sFala"],
                                     "sCarro": round(float(s), 1), "t": self._relogio(),
                                     "velocidadeKmh": None if velocidade_kmh is None else round(float(velocidade_kmh), 1),
                                     "voz": motivo is None, "porqueSoNaJanela": motivo, "duracaoS": f["duracaoS"],
                                     "folgaPlanejadaS": f["folgaS"].get(tr), "sAcaoPiloto": i.get("sAcaoPiloto"),
                                     "sDito": i.get("sDito"), "bipe": i.get("sBipe"), "perfil": self.perfil.origem})
                    self.contagem["avisosPelaVoz" if motivo is None else "avisosSoNaJanela"] += 1
                if motivo is None:
                    comecaram.append(f)
            return comecaram

    def _relogio(self) -> Optional[float]:
        try:
            return round(float(self.relogio()), 3) if self.relogio else None
        except Exception:
            return None

    # ── os blocos e a reserva ──────────────────────────────────────────

    def bloco_em(self, s: float) -> Optional[Dict[str, Any]]:
        return next((b for b in self.blocos if b.get("fim") is not None and R.dentro_do_bloco(s, b, self.L)), None)

    def reta_longa(self, bloco: Optional[Dict[str, Any]]) -> bool:
        """ADR 0033, emenda de 16/11, item 1: a reta dos boxes e a reta oposta (os blocos de 8,8 s ou mais)."""
        return bloco is not None and any(b is bloco for b in self.retas_longas)

    def reserva(self, s: float) -> Optional[float]:
        """O `s` em que o feedback tem de acabar: o `s_fala` da primeira fala planejada a frente do carro no bloco
        dele, ou o fim do bloco (ADR 0033, emenda de 20/11, item 11). None: o carro nao esta num bloco."""
        bloco = self.bloco_em(s)
        if bloco is None:
            return None
        fim = float(bloco["fim"])
        with self._lock:
            for f in self.falas:
                sf = float(f["sFala"])
                if R.dentro_do_bloco(sf, bloco, self.L) and 0 < (sf - s) % self.L < (fim - s) % self.L:
                    fim = sf
        return fim

    def tempo_entre(self, s1: float, s2: float, v_kmh: Optional[float] = None) -> float:
        """O tempo de `s1` a `s2` pelo perfil (ADR 0033, emenda de 20/11, item 3); sem perfil, pela velocidade."""
        if self.perfil is not None:
            return self.perfil.dt(s1, s2)
        v = float(v_kmh or 0.0) / 3.6
        return ((float(s2) - float(s1)) % self.L) / v if v > 1.0 else 0.0

    # ── a janela e o app do jogo ────────────────────────────────────────

    def estado_publico(self, lenta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            self._replanejar_se_mediu()
            itens = []
            for i in self._ordenada():
                janela = (i.get("escrita") if i.get("frase") and i.get("escrita") else
                          (i.get("frase") or f"{i['trecho']}: perdeu {i['perdaS']:.2f} s, sem causa medida".replace(".", ",")))
                itens.append({k: i.get(k) for k in ("trecho", "curva", "causa", "acao", "frase", "voz", "sFala", "sAcao",
                                                     "sDito", "x", "z", "direcao", "perdaS", "referencia", "comMarco",
                                                     "porqueSoNaJanela", "falaChave", "falaJunta", "sJanela",
                                                     "sFimDaJanela", "sAcaoPiloto", "tipoDaAcaoPiloto", "bipe", "sBipe",
                                                     "folgaPlanejadaS")}
                             | {"janela": janela, "conferencia": (i.get("conferencia") or {}).get("texto"),
                                "aplicada": (i.get("conferencia") or {}).get("aplicada")})
            falas = [{k: f.get(k) for k in ("chave", "sFala", "texto", "duracaoS", "audio", "trechos", "folgaS",
                                             "candidato", "pedaco")} for f in self.falas]
            return {"disponivel": self.ativo, "motivo": self.motivo, "versao": self.versao, "comprimentoM": self.L,
                    "lista": itens, "falas": falas, "vozLiberada": self._voz_liberada,
                    "molde": self.molde, "bipe": self.bipe, "tempoDeReacaoAoBipeS": P.TEMPO_DE_REACAO_AO_BIPE_S,
                    "latenciaNoJogoS": P.LATENCIA_NO_JOGO_S, "folgaMinimaS": P.FOLGA_MINIMA_S,
                    "perfil": None if self.perfil is None else self.perfil.origem,
                    "ultimaConferencia": self.ultima_conferencia, "lenta": lenta,
                    "blocos": [[b["inicio"], b["fim"]] for b in self.blocos if b.get("fim") is not None],
                    "voltaLentaS": R.VOLTA_LENTA_S, "contagem": dict(self.contagem)}

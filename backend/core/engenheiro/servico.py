"""O engenheiro dentro do radio (pedido 52, Parte C; ADR 0033): a lista da volta, os avisos e a conferencia.

O radio (`core.radio.servico.RadioDoEngenheiro`) chama:

* `na_linha(...)`, na linha, numa volta que conta: confere as dicas dadas na volta e refaz a lista;
* `no_quadro(...)`, a cada quadro: marca as dicas dadas (o carro passou o `s_fala` com a dica na lista) e
  devolve o aviso que a voz deve dizer agora, se houver;
* `reserva(s)`: onde comeca a reserva dos avisos no bloco em que o carro esta (o feedback tem de acabar antes);
* `estado_publico(...)`: a lista para a janela do app do jogo (`GET /api/radio/engenheiro`).

Nada de modelo, store ou coach muda: so le a volta do modelo, os marcos, o ruido por trecho e as voltas
que o radio ja mede.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import marcos as M
from . import regras as R

logger = logging.getLogger(__name__)

PISTA = "vhe_interlagos"
DURACAO_ESTIMADA_S = 4.0       # antes de a voz medir a frase (so para a janela)
ESTADO_DA_DICA = ("na lista", "aplicada")


class Engenheiro:
    def __init__(self, track, pista_do_radio, raizes: Callable[[], Sequence[Optional[Path]]],
                 falar_em_segundo_plano: Callable[[str], Any], registrar: Callable[[Dict[str, Any]], None]):
        """`pista_do_radio`: a `analise.Pista` do radio; `falar_em_segundo_plano(fala)`: um futuro que devolve
        (arquivo, duracao); `registrar(linha)`: grava uma linha no `<sessao>.engenheiro.jsonl`."""
        from core.assisted_analysis import volta_do_modelo as VM
        from core.radio.analise import grade

        self.track = track
        self.pista = pista_do_radio
        self.L = float(track.length)
        self.trechos = R.trechos_da_pista(track)
        self._falar = falar_em_segundo_plano
        self._registrar = registrar
        self._lock = threading.RLock()
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

    # ── a sessao ────────────────────────────────────────────────────────

    def nova_sessao(self, sessao: Optional[str], sua_melhor: Optional[Dict[str, Any]]) -> None:
        """Outra sessao: a lista comeca vazia; a melhor passagem comeca pela "Sua melhor volta" (do store)."""
        with self._lock:
            self._sessao = sessao
            self.lista, self.ultima_conferencia, self._dadas = {}, None, {}
            self.melhores = {}
            self._s_anterior = None
            self.versao += 1
            if sua_melhor is not None:
                self._considerar_passagens(sua_melhor["grade"], sua_melhor["tempoS"], "sua melhor volta")

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
        fala = R.fala_do_aviso(t.nome, f["frase"])
        k_ponto = int(self.track.index_of(s_acao))
        item.update(frase=f["frase"], fala=fala, escrita=R.escrita_do_aviso(t.nome, f["frase"]), comMarco=f["comMarco"],
                    marco=f["marco"], d=f["d"], sDito=f["sDito"],
                    sAcao=round(float(s_acao), 1), refMinimaKmh=pts.get("minimaKmh"),
                    refFreada=pts.get("freada"), vFreadaKmh=pts.get("velocidadeNaFreadaKmh"),
                    vNoPontoKmh=float(np.asarray(ref["grade"]["velocidade"], float)[k_ponto]))
        if not sem_tirar:
            # a marca no asfalto (ADR 0033, item 7); "sem tirar o pé" nao tem marca nem contagem
            lateral = np.asarray(ref["grade"]["lateral"], float)
            lat = float(lateral[k_ponto]) if np.isfinite(lateral).any() else 0.0
            x, z = self.track.to_world([s_acao], [lat])[0]
            item.update(x=round(float(x), 2), z=round(float(z), 2),
                        direcao=[round(float(self.track.tangent[k_ponto][0]), 4), round(float(self.track.tangent[k_ponto][1]), 4)])
        # a voz mede a frase; ate la, a estimativa (so para a janela)
        self._pedir_a_voz(fala)
        self._planejar(item)
        return item

    def _pedir_a_voz(self, fala: str) -> None:
        if fala not in self._audios:
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

    def _planejar(self, item: Dict[str, Any]) -> None:
        """ADR 0033, item 5: o `s_fala` e se o aviso vai pela voz (a referencia freia, a frase tem marco e cabe no bloco)."""
        dur = self.duracao(item.get("fala"))
        t_frase = dur if dur is not None else DURACAO_ESTIMADA_S
        item["duracaoS"] = round(dur, 2) if dur is not None else None
        bloco = R.bloco_do_trecho(self.blocos, item["trecho"])
        if item.get("acao") == R.SEM_TIRAR_O_PE:
            item["sFala"] = round(R.s_fala(item["sAcao"], item.get("vNoPontoKmh") or 100.0, t_frase, self.L), 1)
            item["voz"] = False
            item["porqueSoNaJanela"] = "sem tirar o pé (a referência não freia nem alivia no trecho)"
        elif item.get("refFreada") is not None and item.get("vFreadaKmh"):
            sf = R.s_fala(item["refFreada"], item["vFreadaKmh"], t_frase, self.L)
            item["sFala"] = round(sf, 1)
            item["voz"] = bool(item.get("comMarco") and bloco and R.dentro_do_bloco(sf, bloco, self.L))
            item["porqueSoNaJanela"] = None if item["voz"] else (
                "sem marco na janela" if not item.get("comMarco") else
                "sem bloco de voz antes da freada" if not bloco else "a frase não cabe no bloco")
        else:
            item["sFala"] = round(R.s_fala(item["sAcao"], item.get("vNoPontoKmh") or 100.0, t_frase, self.L), 1)
            item["voz"] = False
            item["porqueSoNaJanela"] = "a referência não freia no trecho"
        item["bloco"] = [bloco["inicio"], bloco["fim"]] if bloco else None

    def _ordenada(self) -> List[Dict[str, Any]]:
        return sorted(self.lista.values(), key=lambda i: i["k"])

    # ── o quadro ────────────────────────────────────────────────────────

    def no_quadro(self, s: Optional[float], velocidade_kmh: Optional[float], desde_a_linha: bool, ia: bool,
                  falando: bool) -> Optional[Dict[str, Any]]:
        """Marca as dicas dadas e devolve o aviso pela voz que comeca agora (ADR 0033, item 5), ou None."""
        if not self.ativo or s is None:
            return None
        with self._lock:
            anterior, self._s_anterior = self._s_anterior, float(s)
            if anterior is None:
                return None
            andou = (float(s) - anterior) % self.L
            if andou > self.L / 2 or andou <= 0:
                return None
            aviso = None
            # o ponto da acao de cada dica dada: passado, a dica pode ser conferida na linha
            for d in self._dadas.values():
                if not d.get("acaoPassada") and (d["sAcao"] - anterior) % self.L <= andou:
                    d["acaoPassada"] = True
            for item in self._ordenada():
                if item.get("frase") is not None and item.get("duracaoS") is None and self.duracao(item.get("fala")) is not None:
                    self._planejar(item)          # a voz mediu a frase: o s_fala fica o da duracao de verdade
                if item.get("frase") is None or item.get("sFala") is None:
                    continue
                if (item["sFala"] - anterior) % self.L > andou:
                    continue
                if item["trecho"] in self._dadas and not self._dadas[item["trecho"]].get("acaoPassada"):
                    continue                      # ja dada, esperando o carro passar a acao
                # o carro passou o s_fala: a dica foi dada (na janela, pelo menos)
                if item.get("duracaoS") is None:
                    self._planejar(item)
                pela_voz = False
                motivo = None
                if not item.get("voz"):
                    motivo = item.get("porqueSoNaJanela")
                elif not desde_a_linha:
                    motivo = "volta de saída dos boxes"
                elif ia:
                    motivo = "a IA no volante"
                elif falando or aviso is not None:
                    motivo = "outra fala em andamento"
                elif self.audio(item["fala"]) is None:
                    motivo = "a voz ainda não estava pronta"
                else:
                    v = float(velocidade_kmh or 0.0) / 3.6
                    ate = (float(item["refFreada"]) - float(s)) % self.L
                    precisa = float(item["duracaoS"]) + R.FOLGA_ANTES_DA_FREADA_S
                    if v <= 1.0 or ate / v < precisa:
                        motivo = f"pouco tempo até a freada ({ate / v:.1f} s)" if v > 1.0 else "carro parado"
                if motivo is None:
                    pela_voz = True
                    arquivo, dur = self.audio(item["fala"])
                    aviso = {"origem": "aviso", "titulo": f"Engenheiro · {item['trecho']}",
                             "texto": item.get("escrita") or item["frase"],
                             "detalhe": f"{item['causa']}; perdeu {item['perdaS']:.2f} s no trecho".replace(".", ","),
                             "fala": item["fala"], "falas": [item["fala"]], "falaMaxS": 99.0, "curva": item["trecho"],
                             "s": item["sFala"], "perdaS": item["perdaS"], "duracaoS": round(dur, 2),
                             "_arquivoPronto": str(arquivo), "causa": {"trecho": item["acao"], "medida": item["causa"]}}
                    self.contagem["avisosPelaVoz"] += 1
                else:
                    self.contagem["avisosSoNaJanela"] += 1
                self._dadas[item["trecho"]] = {k: item.get(k) for k in ("k", "trecho", "acao", "causa", "frase", "sFala", "sAcao",
                                                                        "sDito", "marco", "refMinimaKmh")}
                self._dadas[item["trecho"]].update(pelaVoz=pela_voz, acaoPassada=False)
                item["pelaVoz"] = pela_voz
                self._registrar({"tipo": "aviso", "trecho": item["trecho"], "causa": item["causa"], "frase": item["frase"],
                                 "sFala": item["sFala"], "sCarro": round(float(s), 1),
                                 "velocidadeKmh": round(float(velocidade_kmh), 1) if velocidade_kmh is not None else None,
                                 "voz": pela_voz, "porqueSoNaJanela": motivo,
                                 "folgaAteAFreadaS": self._folga(item, s, velocidade_kmh)})
            if aviso is not None:
                self.versao += 1
            return aviso

    def _folga(self, item: Dict[str, Any], s: float, velocidade_kmh: Optional[float]) -> Optional[float]:
        if item.get("refFreada") is None or not velocidade_kmh or item.get("duracaoS") is None:
            return None
        ate = (float(item["refFreada"]) - float(s)) % self.L
        return round(ate / (float(velocidade_kmh) / 3.6) - float(item["duracaoS"]), 2)

    # ── os blocos ───────────────────────────────────────────────────────

    def bloco_em(self, s: float) -> Optional[Dict[str, Any]]:
        return next((b for b in self.blocos if b.get("fim") is not None and R.dentro_do_bloco(s, b, self.L)), None)

    def reta_longa(self, bloco: Optional[Dict[str, Any]]) -> bool:
        """ADR 0033, emenda de 16/11, item 1: a reta dos boxes e a reta oposta (os blocos de 8,8 s ou mais)."""
        return bloco is not None and any(b is bloco for b in self.retas_longas)

    def reserva(self, s: float) -> Optional[float]:
        """O `s` em que o feedback tem de acabar: o primeiro `s_fala` pela voz no bloco do carro, ou o fim do bloco.
        None: o carro nao esta num bloco."""
        bloco = self.bloco_em(s)
        if bloco is None:
            return None
        fim = float(bloco["fim"])
        with self._lock:
            for item in self.lista.values():
                if item.get("voz") and item.get("bloco") and item["bloco"][0] == bloco["inicio"] and item.get("sFala") is not None:
                    # so os s_fala ainda a frente do carro, dentro do bloco
                    if R.dentro_do_bloco(item["sFala"], bloco, self.L) and (item["sFala"] - s) % self.L <= (fim - s) % self.L:
                        if (item["sFala"] - s) % self.L < (fim - s) % self.L:
                            fim = float(item["sFala"])
        return fim

    # ── a janela ────────────────────────────────────────────────────────

    def estado_publico(self, lenta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            itens = []
            for i in self._ordenada():
                if i.get("frase") is not None and i.get("duracaoS") is None and self.duracao(i.get("fala")) is not None:
                    self._planejar(i)
                janela = (i.get("escrita") if i.get("frase") and i.get("escrita") else
                          (i.get("frase") or f"{i['trecho']}: perdeu {i['perdaS']:.2f} s, sem causa medida".replace(".", ",")))
                itens.append({k: i.get(k) for k in ("trecho", "curva", "causa", "acao", "frase", "voz", "sFala", "sAcao",
                                                     "sDito", "x", "z", "direcao", "perdaS", "referencia", "comMarco",
                                                     "porqueSoNaJanela", "duracaoS")}
                             | {"janela": janela, "conferencia": (i.get("conferencia") or {}).get("texto"),
                                "aplicada": (i.get("conferencia") or {}).get("aplicada")})
            return {"disponivel": self.ativo, "motivo": self.motivo, "versao": self.versao, "comprimentoM": self.L,
                    "lista": itens, "ultimaConferencia": self.ultima_conferencia, "lenta": lenta,
                    "blocos": [[b["inicio"], b["fim"]] for b in self.blocos if b.get("fim") is not None],
                    "voltaLentaS": R.VOLTA_LENTA_S, "contagem": dict(self.contagem)}

"""O engenheiro dentro do radio (pedido 52, Parte C; ADR 0033, com as emendas de 16/11, 20/11 e 21/11).

Desde 21/11 o engenheiro fala de uma **curva de foco** por vez: a curva em que o piloto mais perde, acima do
ruido do trecho. Ele diz a **ficha** dela uma vez por volta na reta longa antes da curva, um **lembrete** curto
no pedaco livre logo antes, e marca o ponto de frenagem com a **contagem de tres bipes** e a marca no asfalto.

O radio (`core.radio.servico.RadioDoEngenheiro`) chama:

* `nova_sessao(...)`: o foco comeca pelo da ultima sessao nesta pista (`foco_do_registro`);
* `na_linha(...)`, na linha: numa volta que conta, a lista da volta, a conferencia do foco, a troca do foco e o
  plano das falas; numa volta descartada, o motivo (a janela diz "Esperando uma volta que conte");
* `no_quadro(...)`, a cada quadro: devolve as falas planejadas que comecaram agora (o app do jogo toca cada uma
  pelo mesmo `s`, com o audio ja baixado), para a reserva e o corte do feedback;
* `reserva(s)` e `tempo_entre(...)`: onde comeca a reserva da ficha no bloco em que o carro esta e o tempo ate
  la pelo perfil (o feedback tem de acabar antes);
* `estado_publico(...)`: o foco, a ficha e as falas para o app do jogo (`GET /api/radio/engenheiro`).

A ficha esta em `ficha.py`; o plano das falas (o perfil, os pedacos livres, a acao do piloto, a ficha, o
lembrete e a contagem) em `plano.py`. Nada de modelo, store ou coach muda: so le a volta do modelo, os marcos,
o ruido por trecho, as voltas que o radio ja mede e o registro das sessoes anteriores.
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

from . import ficha as F
from . import marcos as M
from . import plano as P
from . import regras as R

logger = logging.getLogger(__name__)

PISTA = "vhe_interlagos"
VOLTAS_SEM_APLICAR = 3            # ADR 0033, emenda de 21/11, item 4
ACAO_DA_FICHA = {F.FRENAGEM: "freie", F.PE_EMBAIXO: R.SEM_TIRAR_O_PE, F.ALIVIO: "vire"}


def foco_do_registro(pasta: Optional[Path], sessao_atual: Optional[str], ruido: Dict[str, float],
                     pista: str = PISTA) -> Optional[Dict[str, Any]]:
    """ADR 0033, emenda de 21/11, item 5: o foco da ultima sessao nesta pista que tenha volta que conta, pelo
    registro do engenheiro: o foco com que ela terminou (a ultima linha `foco`); sem essa linha (as sessoes
    gravadas antes de 21/11), a curva de maior perda acima do ruido na ultima linha `volta`. None: sem sessao."""
    if pasta is None or not Path(pasta).is_dir():
        return None
    arquivos = sorted(Path(pasta).glob(f"*_{pista}.engenheiro.jsonl"), key=lambda a: a.name, reverse=True)
    for arq in arquivos:
        nome = arq.name[: -len(".engenheiro.jsonl")]
        if sessao_atual and nome >= sessao_atual:
            continue
        voltas, focos = [], []
        try:
            for linha in arq.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(linha)
                except ValueError:
                    continue
                if d.get("tipo") == "volta":
                    voltas.append(d)
                elif d.get("tipo") == "foco":
                    focos.append(d)
        except OSError:
            continue
        if not voltas:
            continue
        if focos and focos[-1].get("trecho"):
            return {"trecho": focos[-1]["trecho"], "sessao": nome, "motivo": "o foco com que a sessão terminou"}
        perdas = voltas[-1].get("perdas") or {}
        acima = [(float(v), t) for t, v in perdas.items()
                 if R.numero_da_curva(t) is not None and v is not None and float(v) > float(ruido.get(t, float("inf")))]
        if acima:
            perda, trecho = max(acima)
            return {"trecho": trecho, "sessao": nome,
                    "motivo": f"a maior perda acima do ruído na última volta que contou ({perda:.2f} s)".replace(".", ",")}
        return None
    return None


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
        self._sessao: Optional[str] = None
        self.contagem = {"fichas": 0, "lembretes": 0, "falasCaladas": 0}
        # a curva de foco (ADR 0033, emenda de 21/11, itens 3 a 5)
        self.foco: Optional[Dict[str, Any]] = None
        self.ficha: Optional[Dict[str, Any]] = None        # a ficha do foco, com o plano (a ficha, o lembrete, os bipes)
        self.esperando: Optional[str] = None               # o motivo da ultima volta descartada
        # o plano das falas: o perfil, os pedacos livres e as falas (a ficha e o lembrete)
        self.perfil: Optional[P.Perfil] = None
        self.pedacos: List[Dict[str, float]] = []
        self.falas: List[Dict[str, Any]] = []
        self._medidas_no_plano: set = set()
        self._voz_liberada = True
        if self.modelo is not None:
            self._usar_o_perfil(self.modelo["grade"], self.modelo["tempoS"], "volta de referência")

    # ── a sessao ────────────────────────────────────────────────────────

    def nova_sessao(self, sessao: Optional[str], sua_melhor: Optional[Dict[str, Any]],
                    foco_anterior: Optional[Dict[str, Any]] = None) -> None:
        """Outra sessao: a lista comeca vazia; a melhor passagem comeca pela "Sua melhor volta" (do store); o foco
        comeca pelo da ultima sessao nesta pista (ADR 0033, emenda de 21/11, item 5)."""
        with self._lock:
            self._sessao = sessao
            self.lista, self.ultima_conferencia = {}, None
            self.melhores = {}
            self._s_anterior = None
            self.falas, self.ficha, self.foco, self.esperando = [], None, None, None
            self.versao += 1
            if sua_melhor is not None:
                self._considerar_passagens(sua_melhor["grade"], sua_melhor["tempoS"], "sua melhor volta")
            # o perfil (ADR 0033, emenda de 20/11, item 5): antes da primeira volta que conta, a "Sua melhor volta";
            # sem ela, a volta de referencia
            if sua_melhor is not None:
                self._usar_o_perfil(sua_melhor["grade"], sua_melhor["tempoS"], "sua melhor volta")
            elif self.modelo is not None:
                self._usar_o_perfil(self.modelo["grade"], self.modelo["tempoS"], "volta de referência")
            k = self._k(foco_anterior.get("trecho")) if foco_anterior else None
            if k is not None and self.trechos[k].tem_curva:
                self._novo_foco(k, None, f"sessão {foco_anterior.get('sessao')}", foco_anterior.get("motivo"))
            self._planejar_o_foco()

    def _k(self, trecho: Optional[str]) -> Optional[int]:
        return next((k for k, t in enumerate(self.trechos) if t.nome == trecho), None)

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

    def descartar(self, volta: Optional[Any], motivo: Optional[str]) -> None:
        """ADR 0033, emenda de 21/11, item 5: a volta que nao conta; a janela mostra o motivo enquanto nao ha foco."""
        with self._lock:
            n = int(volta) if isinstance(volta, (int, float)) and float(volta).is_integer() else volta
            self.esperando = f"volta {n}: {motivo}" if motivo else (f"volta {n}: não contou" if n is not None else None)
            self.versao += 1

    def na_linha(self, volta: Optional[int], grade: Optional[Dict[str, np.ndarray]], total: Optional[float],
                 conta: bool, motivo: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """ADR 0033, itens 1 e 8, com a emenda de 21/11: numa volta que conta, a lista da volta, a conferencia do
        foco, a troca do foco e o plano das falas. Devolve a conferencia do foco (ou None)."""
        if not self.ativo:
            return None
        if not conta or grade is None or total is None:
            self.descartar(volta, motivo)
            return None
        with self._lock:
            from core.radio.analise import medidas_da_volta
            tempos = R.tempos_dos_trechos(grade["elapsed"], total, self.track, self.trechos)
            # a lista nova: cada trecho contra a referencia dele (item 1; ela nao vai mais para a voz)
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
            self.lista = {}
            perdas: Dict[str, float] = {}
            for k, t in enumerate(self.trechos):
                ref = refs[k]
                perda = float(tempos[k]) - float(ref["tempoDoTrechoS"])
                perdas[t.nome] = round(perda, 4)
                if not perda > self.ruido_por_trecho.get(t.nome, float("inf")):
                    continue
                medida = next((m for m in medidas_por_ref.get(id(ref["grade"]), []) if m.get("curva") == t.nome), None)
                self.lista[t.nome] = self._item(k, ref, medida, perda, volta)
            # a conferencia do foco (item 4): so numa volta inteira com a curva em foco
            conf = None
            saiu = None
            if self.foco is not None and self.ficha is not None and (
                    self.foco["desdeAVolta"] is None or volta is None or float(volta) > float(self.foco["desdeAVolta"])):
                conf = self._conferir_o_foco(volta, grade, total)
                self.foco["voltasEmFoco"] += 1
                if conf.get("aplicada") is True:
                    saiu = (self.foco["trecho"], f"aplicada na volta {self._n(volta)}")
                elif self.foco["voltasEmFoco"] >= VOLTAS_SEM_APLICAR:
                    saiu = (self.foco["trecho"], f"{VOLTAS_SEM_APLICAR} voltas sem aplicar")
            self.ultima_conferencia = None if conf is None else {
                "volta": volta, "conferidas": [conf], "aplicadas": 1 if conf.get("aplicada") is True else 0,
                "medidas": 1 if conf.get("aplicada") is not None else 0, "texto": conf.get("texto")}
            self._registrar({"tipo": "volta", "volta": volta, "tempoS": round(float(total), 3), "perdas": perdas,
                             "lista": [{"trecho": i["trecho"], "causa": i["causa"], "frase": i["frase"]}
                                       for i in self._ordenada()],
                             "foco": None if self.foco is None else self.foco["trecho"]})
            # a troca do foco (itens 3 e 4)
            if saiu is not None:
                self._registrar({"tipo": "foco", "volta": volta, "trecho": None, "saiu": saiu[0], "motivo": saiu[1],
                                 "voltasEmFoco": self.foco["voltasEmFoco"]})
                self.foco = None
            if self.foco is None:
                acima = [(perdas[t.nome], k) for k, t in enumerate(self.trechos)
                         if t.tem_curva and t.nome in self.lista and (saiu is None or t.nome != saiu[0])]
                if acima:
                    perda, k = max(acima)
                    self._novo_foco(k, volta, f"volta {self._n(volta)} da sessão",
                                    f"a maior perda acima do ruído ({perda:.2f} s)".replace(".", ","))
                else:
                    self._registrar({"tipo": "foco", "volta": volta, "trecho": None,
                                     "motivo": "nenhuma curva acima do ruído nesta volta"})
            self.esperando = None if self.foco is not None else "nenhuma curva acima do ruído na última volta que contou"
            # a melhor passagem, o perfil e o plano das falas (emenda de 20/11, item 5; emenda de 21/11, itens 9 a 12)
            self._considerar_passagens(grade, total, f"volta {volta}")
            self._usar_o_perfil(grade, total, f"volta {self._n(volta)} da sessão")
            self._planejar_o_foco()
            self.versao += 1
            return conf

    @staticmethod
    def _n(volta: Any) -> Any:
        return int(volta) if isinstance(volta, (int, float)) and float(volta).is_integer() else volta

    def _novo_foco(self, k: int, volta: Optional[Any], origem: str, motivo: Optional[str]) -> None:
        t = self.trechos[k]
        self.foco = {"trecho": t.nome, "k": k, "curva": R.numero_da_curva(t.nome), "desdeAVolta": volta,
                     "voltasEmFoco": 0, "origem": origem, "motivo": motivo}
        self._registrar({"tipo": "foco", "volta": volta, "trecho": t.nome, "origem": origem, "motivo": motivo})

    def _conferir_o_foco(self, volta: Optional[Any], grade: Dict[str, np.ndarray], total: float) -> Dict[str, Any]:
        """ADR 0033, emenda de 21/11, item 4: a conferencia da instrucao principal da ficha, com a medida do item 8."""
        ficha = self.ficha
        k = self.foco["k"]
        instrucao = F.instrucao_principal(ficha)
        pts = R.pontos_do_trecho(grade, total, self.track, self.trechos, k)
        conf = R.conferir(instrucao, pts, self.L)
        conf["texto"] = F.texto_da_conferencia(ficha, conf)
        linha = {"tipo": "conferencia", "volta": volta, "trecho": ficha["trecho"], "acao": instrucao["acao"],
                 "aplicada": conf.get("aplicada"), "valor": conf.get("valor"), "difM": conf.get("difM"),
                 "difKmh": conf.get("difKmh"), "sPonto": ficha["sPonto"], "texto": conf["texto"],
                 "voltasEmFoco": self.foco["voltasEmFoco"] + 1}
        self._registrar(linha)
        return {"trecho": ficha["trecho"], "acao": instrucao["acao"], **conf}

    def _item(self, k: int, ref: Dict[str, Any], medida: Optional[Dict[str, Any]], perda: float,
              volta: Optional[int]) -> Dict[str, Any]:
        """Um trecho da lista da volta (item 1): a perda, a causa e a frase (a janela da volta lenta e o registro)."""
        t = self.trechos[k]
        causa = R.causa_do_engenheiro(medida) if t.tem_curva else None
        pts = R.pontos_do_trecho(ref["grade"], ref["tempoS"], self.track, self.trechos, k)
        item: Dict[str, Any] = {"k": k, "trecho": t.nome, "curva": R.numero_da_curva(t.nome), "perdaS": round(perda, 3),
                                "referencia": ref["origem"], "referenciaRotulo": ref["rotulo"], "desdeAVolta": volta,
                                "causa": None, "acao": None, "frase": None}
        if causa is None:
            return item
        acao = causa["acao"]
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
        item.update(frase=f["frase"], escrita=R.escrita_do_aviso(t.nome, f["frase"]), sDito=f["sDito"],
                    sAcao=round(float(s_acao), 1))
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

    # ── o plano (ADR 0033, emenda de 21/11, itens 9 a 12) ──────────────

    def _usar_o_perfil(self, grade: Dict[str, np.ndarray], total: float, origem: str) -> None:
        self.perfil = P.Perfil(grade, total, self.track, origem)
        self.pedacos = P.pedacos_livres(grade, self.track)

    def _planejar_o_foco(self) -> None:
        """A ficha da curva de foco e o plano: a ficha na reta longa antes dela, o lembrete no pedaco livre logo
        antes, e os pontos da contagem de bipes. Refeito depois de cada volta que conta e quando a voz mede uma
        fala."""
        self.falas, self.ficha = [], None
        if self.foco is None or self.modelo is None or self.perfil is None:
            self.versao += 1
            return
        k = self.foco["k"]
        passagem = (self.melhores.get(self.foco["trecho"]) or {}).get("grade")
        ficha = F.ficha_da_curva(k, self.modelo, self.track, self.trechos, (self.marcos or {}).get("marcos") or [],
                                 self.pontos_dos_marcos, passagem)
        if ficha is None:
            self.versao += 1
            return
        a = P.acao_do_piloto(self.perfil.grade, self.track, self.trechos, k, ACAO_DA_FICHA[ficha["tipo"]])
        s_acao = float(a[0]) if a is not None else float(ficha["sPonto"])
        ponto = P.ponto_limite(self.perfil, s_acao, float(ficha["sPonto"]))
        self._pedir_a_voz(ficha["fala"])
        self._pedir_a_voz(ficha["lembrete"])
        dur_ficha = self.duracao(ficha["fala"])
        dur_lembrete = self.duracao(ficha["lembrete"])
        reta = P.reta_longa_antes(self.retas_longas, ponto, self.L)
        pf = P.planejar_a_ficha(self.perfil, self.pedacos, reta, ponto,
                                dur_ficha if dur_ficha is not None else P.ESTIMATIVA_DA_FICHA_S)
        pl = P.planejar_o_lembrete(self.perfil, self.pedacos, ponto,
                                   dur_lembrete if dur_lembrete is not None else P.ESTIMATIVA_DA_FALA_S,
                                   pf.get("pedaco") if "sFala" in pf else None)
        falas = []
        for tipo, texto, plano, medida in (("ficha", ficha["fala"], pf, dur_ficha), ("lembrete", ficha["lembrete"], pl, dur_lembrete)):
            if "sFala" not in plano:
                continue
            chave = self.chave(texto)
            falas.append({"tipo": tipo, "chave": chave, "audio": f"/api/radio/engenheiro/audio/{chave}", "texto": texto,
                          "sFala": plano["sFala"], "duracaoS": plano["duracaoS"], "duracaoMedida": medida is not None,
                          "trechos": [ficha["trecho"]], "folgaS": {ficha["trecho"]: plano["folgaS"]}})
        falas.sort(key=lambda f: f["sFala"])
        bipes = P.pontos_da_contagem(self.perfil, float(ficha["sFreada"])) if (
            ficha["tipo"] == F.FRENAGEM and self.bipe and ficha.get("sFreada") is not None) else []
        ficha.update(sAcaoPiloto=round(s_acao, 1), tipoDaAcaoPiloto=None if a is None else a[1], sPontoLimite=round(ponto, 1),
                     planoDaFicha=pf, planoDoLembrete=pl, sBipes=bipes, origem=self.foco["origem"],
                     motivoDoFoco=self.foco.get("motivo"), voltasEmFoco=self.foco["voltasEmFoco"],
                     desdeAVolta=self.foco["desdeAVolta"], perfil=self.perfil.origem)
        self.ficha, self.falas = ficha, falas
        self._medidas_no_plano = {t for t in (ficha["fala"], ficha["lembrete"]) if self.duracao(t) is not None}
        self._registrar({"tipo": "plano", "trecho": ficha["trecho"], "perfil": self.perfil.origem,
                         "ficha": {k2: pf.get(k2) for k2 in ("sFala", "duracaoS", "folgaS", "folgaAoFimDoPedacoS", "motivo")},
                         "lembrete": {k2: pl.get(k2) for k2 in ("sFala", "duracaoS", "folgaS", "motivo")},
                         "sBipes": bipes, "sAcaoPiloto": round(s_acao, 1), "sPonto": ficha["sPonto"],
                         "tecnica": ficha.get("tecnica"), "tecnicaDe": ficha.get("tecnicaDe")})
        self.versao += 1

    def _replanejar_se_mediu(self) -> None:
        """A voz mediu a ficha ou o lembrete do foco: refaz o plano com a duracao real."""
        if self.ficha is None:
            return
        medidas = {t for t in (self.ficha["fala"], self.ficha["lembrete"]) if self.duracao(t) is not None}
        if medidas - self._medidas_no_plano:
            self._planejar_o_foco()

    def _ordenada(self) -> List[Dict[str, Any]]:
        return sorted(self.lista.values(), key=lambda i: i["k"])

    # ── o quadro ────────────────────────────────────────────────────────

    def no_quadro(self, s: Optional[float], velocidade_kmh: Optional[float], desde_a_linha: bool, ia: bool,
                  falando: bool = False) -> List[Dict[str, Any]]:
        """A cada quadro (ADR 0033, emenda de 20/11, item 2): o carro passou o `s_fala` da ficha ou do lembrete? A
        fala comeca no jogo (o app do jogo toca pelo mesmo `s`); o backend registra e devolve as falas que
        comecaram, para a reserva e o corte do feedback."""
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
            comecaram = []
            for f in self.falas:
                if not (float(f["sFala"]) - anterior) % self.L <= andou:
                    continue
                motivo = None if self._voz_liberada else ("volta de saída dos boxes" if not desde_a_linha else "a IA no volante")
                ficha = self.ficha or {}
                self._registrar({"tipo": f["tipo"], "trecho": f["trechos"][0], "fala": f["texto"], "sFala": f["sFala"],
                                 "sCarro": round(float(s), 1), "t": self._relogio(),
                                 "velocidadeKmh": None if velocidade_kmh is None else round(float(velocidade_kmh), 1),
                                 "voz": motivo is None, "porqueCalada": motivo, "duracaoS": f["duracaoS"],
                                 "folgaPlanejadaS": f["folgaS"].get(f["trechos"][0]), "sAcaoPiloto": ficha.get("sAcaoPiloto"),
                                 "sPonto": ficha.get("sPonto"), "sBipes": ficha.get("sBipes"),
                                 "perfil": None if self.perfil is None else self.perfil.origem})
                if motivo is None:
                    self.contagem["fichas" if f["tipo"] == "ficha" else "lembretes"] += 1
                    comecaram.append(f)
                else:
                    self.contagem["falasCaladas"] += 1
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
        dele (a ficha tem prioridade; emenda de 21/11, item 9), ou o fim do bloco. None: fora de um bloco."""
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
                itens.append({k: i.get(k) for k in ("trecho", "curva", "causa", "acao", "frase", "sDito", "sAcao",
                                                     "perdaS", "referencia")} | {"janela": janela})
            foco = None
            if self.ficha is not None:
                f = self.ficha
                foco = {k: f.get(k) for k in ("trecho", "curva", "lado", "tipo", "tecnica", "tecnicaDe", "sFreada",
                                              "sPonto", "sEntrada", "escrita", "fala", "lembrete", "marca", "sBipes",
                                              "sAcaoPiloto", "origem", "motivoDoFoco", "voltasEmFoco", "desdeAVolta")}
                foco["motivoSemFicha"] = (f.get("planoDaFicha") or {}).get("motivo")
                foco["motivoSemLembrete"] = (f.get("planoDoLembrete") or {}).get("motivo")
                foco["voltasSemAplicar"] = VOLTAS_SEM_APLICAR
            esperando = None
            if foco is None:
                esperando = "Esperando uma volta que conte" + (f" ({self.esperando})" if self.esperando else "")
            falas = [{k: f.get(k) for k in ("tipo", "chave", "sFala", "texto", "duracaoS", "audio", "trechos", "folgaS")}
                     for f in self.falas]
            return {"disponivel": self.ativo, "motivo": self.motivo, "versao": self.versao, "comprimentoM": self.L,
                    "foco": foco, "esperando": esperando, "ultimaDescartada": self.esperando,
                    "lista": itens, "falas": falas, "vozLiberada": self._voz_liberada,
                    "molde": self.molde, "bipe": self.bipe, "intervaloDaContagemS": P.INTERVALO_DA_CONTAGEM_S,
                    "latenciaNoJogoS": P.LATENCIA_NO_JOGO_S, "folgaMinimaS": P.FOLGA_MINIMA_S,
                    "perfil": None if self.perfil is None else self.perfil.origem,
                    "ultimaConferencia": self.ultima_conferencia, "lenta": lenta,
                    "blocos": [[b["inicio"], b["fim"]] for b in self.blocos if b.get("fim") is not None],
                    "voltaLentaS": R.VOLTA_LENTA_S, "contagem": dict(self.contagem)}

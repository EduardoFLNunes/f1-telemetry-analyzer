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

from . import explicacao as E
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
                 relogio: Optional[Callable[[], float]] = None, molde: Optional[str] = None, bipe: Optional[bool] = None,
                 volta_atual: Optional[Callable[[], Optional[Dict[str, Any]]]] = None, config_path: Optional[Path] = None):
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
        # o engenheiro que ensina (ADR 0033, decisoes de 22/11)
        self._volta_atual = volta_atual or (lambda: None)
        self.config_path = config_path
        self.config = self._ler_a_config()
        self.lados = self._lados_das_curvas()
        self.explicacoes: Dict[str, Dict[str, Any]] = {}
        self.fichas_base: Dict[str, Dict[str, Any]] = {}
        self.contagens: List[Dict[str, Any]] = []
        self.lembretes: List[Dict[str, Any]] = []
        self._mensagens: List[Dict[str, Any]] = []
        self._analises_da_volta: Dict[str, List[Dict[str, Any]]] = {}
        self.relatorio_lento: List[Dict[str, Any]] = []
        self._lenta_vista = False
        self.treino: Optional[Dict[str, Any]] = None
        self.ultimo_treino: Optional[Dict[str, Any]] = None
        if self.modelo is not None and self.ativo:
            self._preparar_as_explicacoes()
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
            if k is not None and self.trechos[k].tem_curva and self._no_escopo_do_foco(self.trechos[k].nome):
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
            self._na_linha_do_treino(volta, conta=False)
            self._analises_da_volta = {}
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
                         if t.tem_curva and t.nome in self.lista and (saiu is None or t.nome != saiu[0])
                         and self._no_escopo_do_foco(t.nome)]
                if acima:
                    perda, k = max(acima)
                    self._novo_foco(k, volta, f"volta {self._n(volta)} da sessão",
                                    f"a maior perda acima do ruído ({perda:.2f} s)".replace(".", ","))
                else:
                    self._registrar({"tipo": "foco", "volta": volta, "trecho": None,
                                     "motivo": "nenhuma curva acima do ruído nesta volta"})
            self.esperando = None if self.foco is not None else "nenhuma curva acima do ruído na última volta que contou"
            # o treino (decisoes de 22/11, item 7) e as analises desta volta
            self._na_linha_do_treino(volta, conta=True)
            self._analises_da_volta = {}
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
        self.falas, self.ficha, self.contagens, self.lembretes = [], None, [], []
        if not self.config.get("ligado", True) or self.modelo is None or self.perfil is None:
            self.versao += 1
            return
        if self.foco is None:
            self._planejar_as_outras_curvas([])
            self._marcar_as_medidas()
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
        # decisoes de 22/11, item 3: a ficha dita na reta longa e o texto do nivel (amador ou pro); no iniciante, a
        # explicacao longa vai para a volta lenta e para os boxes, e na volta rapida fica so o lembrete
        nivel = self.config.get("nivel", E.NIVEL_PADRAO)
        exp = self.explicacoes.get(ficha["trecho"])
        if exp is not None:
            ficha["escritaDoNivel"] = exp["textos"][nivel]
            if nivel in ("amador", "pro"):
                ficha["fala"] = exp["textos"][nivel]
        self._pedir_a_voz(ficha["fala"])
        self._pedir_a_voz(ficha["lembrete"])
        dur_ficha = self.duracao(ficha["fala"])
        dur_lembrete = self.duracao(ficha["lembrete"])
        reta = P.reta_longa_antes(self.retas_longas, ponto, self.L)
        pf = P.planejar_a_ficha(self.perfil, self.pedacos, reta, ponto,
                                dur_ficha if dur_ficha is not None else P.ESTIMATIVA_DA_FICHA_S)
        if nivel == "iniciante":
            pf = {"motivo": "nível iniciante: a explicação vai para a volta lenta e os boxes"}
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
        if bipes:
            self.contagens = [{"trecho": ficha["trecho"], "sBipes": bipes}]
        self._planejar_as_outras_curvas(falas)
        self._marcar_as_medidas()
        self._registrar({"tipo": "plano", "trecho": ficha["trecho"], "perfil": self.perfil.origem,
                         "ficha": {k2: pf.get(k2) for k2 in ("sFala", "duracaoS", "folgaS", "folgaAoFimDoPedacoS", "motivo")},
                         "lembrete": {k2: pl.get(k2) for k2 in ("sFala", "duracaoS", "folgaS", "motivo")},
                         "sBipes": bipes, "sAcaoPiloto": round(s_acao, 1), "sPonto": ficha["sPonto"],
                         "tecnica": ficha.get("tecnica"), "tecnicaDe": ficha.get("tecnicaDe")})
        self.versao += 1

    def _marcar_as_medidas(self) -> None:
        """As falas do plano que a voz ja mediu (a ficha, o lembrete do foco e os lembretes das outras curvas): o plano
        so e refeito quando uma delas e medida pela primeira vez."""
        textos = {l["texto"] for l in self.lembretes}
        if self.ficha is not None:
            textos |= {self.ficha["fala"], self.ficha["lembrete"]}
        self._medidas_no_plano = {t for t in textos if self.duracao(t) is not None}

    def _replanejar_se_mediu(self) -> None:
        """A voz mediu a ficha ou um lembrete do plano: refaz o plano com a duracao real."""
        textos = {l["texto"] for l in getattr(self, "lembretes", [])}
        if self.ficha is not None:
            textos |= {self.ficha["fala"], self.ficha["lembrete"]}
        medidas = {t for t in textos if self.duracao(t) is not None}
        if medidas - self._medidas_no_plano:
            self._planejar_o_foco()

    def _ordenada(self) -> List[Dict[str, Any]]:
        return sorted(self.lista.values(), key=lambda i: i["k"])

    # ── o quadro ────────────────────────────────────────────────────────

    def no_quadro(self, s: Optional[float], velocidade_kmh: Optional[float], desde_a_linha: bool, ia: bool,
                  falando: bool = False, lenta: bool = False) -> List[Dict[str, Any]]:
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
            if not self.config.get("ligado", True):
                return []
            # decisoes de 22/11, item 8: a volta lenta (ou a de saida dos boxes), no nivel iniciante
            if lenta and not self._lenta_vista:
                self._lenta_vista = True
                self._na_volta_lenta(float(s))
            elif not lenta:
                self._lenta_vista = False
            # decisoes de 22/11, item 4: a analise de cada curva do escopo, 30 m depois da saida dela
            if desde_a_linha and not ia:
                for nome in self.escopo():
                    k = self._k(nome)
                    if k is None:
                        continue
                    alvo = (float(self.trechos[k].saida_s) + E.DEPOIS_DA_SAIDA_PARA_ANALISAR_M) % self.L
                    if (alvo - anterior) % self.L <= andou:
                        self._analisar(nome, k)
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
            ligado = self.config.get("ligado", True)
            if self.ficha is not None and ligado:
                f = self.ficha
                foco = {k: f.get(k) for k in ("trecho", "curva", "lado", "tipo", "tecnica", "tecnicaDe", "sFreada",
                                              "sPonto", "sEntrada", "escrita", "escritaDoNivel", "fala", "lembrete", "marca",
                                              "sBipes", "sAcaoPiloto", "origem", "motivoDoFoco", "voltasEmFoco",
                                              "desdeAVolta")}
                foco["motivoSemFicha"] = (f.get("planoDaFicha") or {}).get("motivo")
                foco["motivoSemLembrete"] = (f.get("planoDoLembrete") or {}).get("motivo")
                foco["voltasSemAplicar"] = VOLTAS_SEM_APLICAR
            esperando = None
            if not ligado:
                esperando = "Engenheiro desligado"
            elif foco is None:
                esperando = "Esperando uma volta que conte" + (f" ({self.esperando})" if self.esperando else "")
            falas = [{k: f.get(k) for k in ("tipo", "chave", "sFala", "texto", "duracaoS", "audio", "trechos", "folgaS")}
                     for f in self.falas]
            return {"disponivel": self.ativo, "motivo": self.motivo, "versao": self.versao, "comprimentoM": self.L,
                    "foco": foco, "esperando": esperando, "ultimaDescartada": self.esperando, "desligado": not ligado,
                    "config": self.config_publica(), "contagens": list(self.contagens) if ligado else [],
                    "lembretes": [{k: l.get(k) for k in ("trecho", "sFala", "texto", "motivo")} for l in self.lembretes],
                    "ultimoTreino": self.ultimo_treino,
                    "lista": itens, "falas": falas, "vozLiberada": self._voz_liberada,
                    "molde": self.molde, "bipe": self.bipe, "intervaloDaContagemS": P.INTERVALO_DA_CONTAGEM_S,
                    "latenciaNoJogoS": P.LATENCIA_NO_JOGO_S, "folgaMinimaS": P.FOLGA_MINIMA_S,
                    "perfil": None if self.perfil is None else self.perfil.origem,
                    "ultimaConferencia": self.ultima_conferencia, "lenta": lenta,
                    "blocos": [[b["inicio"], b["fim"]] for b in self.blocos if b.get("fim") is not None],
                    "voltaLentaS": R.VOLTA_LENTA_S, "contagem": dict(self.contagem)}

    # ── o engenheiro que ensina (ADR 0033, decisoes de 22/11) ───────────

    CONFIG_PADRAO = {"ligado": True, "nivel": E.NIVEL_PADRAO, "escopo": "uma", "curvas": [], "treinoVoltas": E.TREINO_PADRAO}

    @classmethod
    def _validar(cls, c: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(cls.CONFIG_PADRAO)
        out["ligado"] = bool(c.get("ligado", True))
        out["nivel"] = c.get("nivel") if c.get("nivel") in E.NIVEIS else E.NIVEL_PADRAO
        out["escopo"] = c.get("escopo") if c.get("escopo") in E.ESCOPOS else "uma"
        out["curvas"] = sorted({str(x) for x in (c.get("curvas") or []) if isinstance(x, str)})
        try:
            out["treinoVoltas"] = max(0, min(30, int(c.get("treinoVoltas", E.TREINO_PADRAO))))
        except (TypeError, ValueError):
            out["treinoVoltas"] = E.TREINO_PADRAO
        return out

    def _ler_a_config(self) -> Dict[str, Any]:
        """Item 6: as chaves guardadas em `<pasta de dados>/data/radio/engenheiro_config.json`."""
        c = dict(self.CONFIG_PADRAO)
        if self.config_path and Path(self.config_path).is_file():
            try:
                c.update(json.loads(Path(self.config_path).read_text(encoding="utf-8")))
            except (OSError, ValueError) as erro:
                logger.warning("Engenheiro sem a configuracao guardada: %s", erro)
        return self._validar(c)

    def config_publica(self) -> Dict[str, Any]:
        t = self.treino
        return {**self.config, "niveis": list(E.NIVEIS), "escopos": list(E.ESCOPOS),
                "curvasDaPista": [x.nome for x in self.trechos if x.tem_curva],
                "treino": None if t is None else {"voltas": t["voltas"], "feitas": t["feitas"], "desdeAVolta": t["desdeAVolta"]}}

    def mudar_config(self, novo: Dict[str, Any]) -> Dict[str, Any]:
        """Item 6: muda as chaves (o app do jogo), guarda e refaz o plano. `iniciarTreino` comeca um treino na linha
        seguinte; `pararTreino` o cancela."""
        novo = dict(novo or {})
        with self._lock:
            c = dict(self.config)
            c.update({k: v for k, v in novo.items() if k in self.CONFIG_PADRAO})
            self.config = self._validar(c)
            nomes = {x.nome for x in self.trechos if x.tem_curva}
            self.config["curvas"] = [x for x in self.config["curvas"] if x in nomes]
            if novo.get("pararTreino"):
                self.treino = None
                self._registrar({"tipo": "treino", "evento": "parado"})
            if novo.get("iniciarTreino") and self.config["treinoVoltas"] > 0:
                self.treino = {"voltas": self.config["treinoVoltas"], "desdeAVolta": None, "feitas": 0, "analises": {}}
                self._registrar({"tipo": "treino", "evento": "começou", "voltas": self.config["treinoVoltas"]})
            if self.config_path:
                try:
                    Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(self.config_path).write_text(json.dumps(self.config, ensure_ascii=False, indent=1), encoding="utf-8")
                except OSError as erro:
                    logger.warning("Engenheiro sem gravar a configuracao: %s", erro)
            if self.foco is not None and not self._no_escopo_do_foco(self.foco["trecho"]):
                self._registrar({"tipo": "foco", "trecho": None, "saiu": self.foco["trecho"], "motivo": "fora do escopo escolhido"})
                self.foco = None
            self._registrar({"tipo": "config", **self.config})
            self._planejar_o_foco()
            return self.config_publica()

    def _no_escopo_do_foco(self, nome: str) -> bool:
        return self.config.get("escopo") != "algumas" or nome in self.config.get("curvas", [])

    def escopo(self) -> List[str]:
        """Item 5: as curvas do escopo (uma: o foco; algumas: a lista; inteira: todas)."""
        nomes = [x.nome for x in self.trechos if x.tem_curva]
        e = self.config.get("escopo", "uma")
        if e == "inteira":
            return nomes
        if e == "algumas":
            return [n for n in nomes if n in self.config.get("curvas", [])]
        return [self.foco["trecho"]] if self.foco else []

    def _lados_das_curvas(self) -> Dict[str, Optional[str]]:
        from ml.track.corners import detect_corners

        try:
            cs = detect_corners(self.track)
        except Exception:
            cs = []
        out: Dict[str, Optional[str]] = {}
        for x in self.trechos:
            if x.tem_curva and x.apice_s is not None:
                c = next((c for c in cs if abs(float(c.apex_s) - float(x.apice_s)) < 1.0), None)
                out[x.nome] = None if c is None else ("esquerda" if c.direction > 0 else "direita")
        return out

    def _preparar_as_explicacoes(self) -> None:
        """As medidas da volta de referencia, os textos dos tres niveis e a ficha de cada curva (itens 1 a 3)."""
        marcos = (self.marcos or {}).get("marcos") or []
        curvas = [k for k, x in enumerate(self.trechos) if x.tem_curva]
        g = self.modelo["grade"]
        for k in curvas:
            x = self.trechos[k]
            try:
                m = E.medidas_da_curva(g, self.track, self.trechos, k, self.lados.get(x.nome), marcos)
                if m is None:
                    continue
                tipo = E.tipo_da_curva(g, self.track, self.trechos, k)
                kn = next((j for j in curvas if j > k), curvas[0])
                seguinte = E._seguinte(E.tipo_da_curva(g, self.track, self.trechos, kn), R.numero_da_curva(self.trechos[kn].nome))
                textos = E.textos_da_curva(m, R.numero_da_curva(x.nome), tipo, seguinte, self.L, self.pontos_dos_marcos)
                self.explicacoes[x.nome] = {"k": k, "medidas": m, "tipo": tipo, "textos": textos}
                f = F.ficha_da_curva(k, self.modelo, self.track, self.trechos, marcos, self.pontos_dos_marcos, None)
                if f is not None:
                    self.fichas_base[x.nome] = f
            except Exception as erro:
                logger.warning("Engenheiro sem a explicacao da %s: %s", x.nome, erro)

    def _planejar_as_outras_curvas(self, falas_do_foco: List[Dict[str, Any]]) -> None:
        """Item 5: em "algumas" e "inteira", o lembrete e a contagem de bipes de cada curva do escopo (a ficha e so a do
        foco). Os lembretes sao planejados na ordem da pista; um que encostaria em outra fala fica de fora."""
        if self.config.get("escopo") == "uma" or self.perfil is None:
            return
        foco = self.foco["trecho"] if self.foco else None
        aceitas = [(self.perfil.t(f["sFala"]), float(f["duracaoS"])) for f in falas_do_foco]

        def encosta(t0: float, d: float) -> bool:
            for t1, d1 in aceitas:
                a0, a1 = t0, t0 + P.LATENCIA_NO_JOGO_S + d
                b0, b1 = t1, t1 + P.LATENCIA_NO_JOGO_S + d1
                if a0 < b1 + 0.3 and b0 < a1 + 0.3:
                    return True
            return False

        for nome in self.escopo():
            if nome == foco or nome not in self.fichas_base:
                continue
            fb = self.fichas_base[nome]
            k = self._k(nome)
            a = P.acao_do_piloto(self.perfil.grade, self.track, self.trechos, k, ACAO_DA_FICHA[fb["tipo"]])
            ponto = P.ponto_limite(self.perfil, float(a[0]) if a else float(fb["sPonto"]), float(fb["sPonto"]))
            self._pedir_a_voz(fb["lembrete"])
            dur = self.duracao(fb["lembrete"])
            pl = P.planejar_o_lembrete(self.perfil, self.pedacos, ponto, dur if dur is not None else P.ESTIMATIVA_DA_FALA_S, None)
            item = {"trecho": nome, "texto": fb["lembrete"], "sFala": pl.get("sFala"), "motivo": pl.get("motivo")}
            if "sFala" in pl:
                t0 = self.perfil.t(pl["sFala"])
                if encosta(t0, pl["duracaoS"]):
                    item.update(sFala=None, motivo="encostaria em outra fala")
                else:
                    aceitas.append((t0, pl["duracaoS"]))
                    chave = self.chave(fb["lembrete"])
                    self.falas.append({"tipo": "lembrete", "chave": chave, "audio": f"/api/radio/engenheiro/audio/{chave}",
                                       "texto": fb["lembrete"], "sFala": pl["sFala"], "duracaoS": pl["duracaoS"],
                                       "duracaoMedida": dur is not None, "trechos": [nome], "folgaS": {nome: pl["folgaS"]}})
            self.lembretes.append(item)
            if fb["tipo"] == F.FRENAGEM and self.bipe and fb.get("sFreada") is not None:
                self.contagens.append({"trecho": nome, "sBipes": P.pontos_da_contagem(self.perfil, float(fb["sFreada"]))})
        self.falas.sort(key=lambda f: f["sFala"])

    def _mensagem(self, titulo: str, texto: str, maximo_s: float, frente: bool) -> Dict[str, Any]:
        return {"origem": "engenheiro", "titulo": f"Engenheiro · {titulo}", "texto": texto, "fala": texto, "falas": [texto],
                "falaMaxS": float(maximo_s), "_frente": bool(frente)}

    def tirar_mensagens(self) -> List[Dict[str, Any]]:
        """As mensagens novas do engenheiro para a fila do radio (a analise, a explicacao e o treino)."""
        with self._lock:
            out, self._mensagens = self._mensagens, []
            return out

    def _analisar(self, nome: str, k: int) -> None:
        """Item 4: a passagem do piloto pela curva, na volta em andamento, contra a referencia."""
        exp = self.explicacoes.get(nome)
        if exp is None or self.modelo is None:
            return
        volta = self._volta_atual()
        if not volta or not volta.get("linhas") or int(volta.get("pontosDaGrade") or 0) != int(self.track.size):
            return
        from core.radio.analise import grade as _grade
        try:
            g = _grade(volta["linhas"])
            pm = E.medidas_da_curva(g, self.track, self.trechos, k, self.lados.get(nome), (self.marcos or {}).get("marcos") or [])
        except Exception as erro:
            logger.warning("Engenheiro sem a analise da %s: %s", nome, erro)
            return
        if pm is None:
            self._registrar({"tipo": "analise", "trecho": nome, "volta": volta.get("volta"), "semMedida": True})
            return
        difs = E.diferencas(exp["medidas"], pm, self.modelo["grade"], g, self.track, self.trechos, k)
        self._analises_da_volta[nome] = difs
        nivel = self.config.get("nivel", E.NIVEL_PADRAO)
        texto = E.texto_da_analise(difs, R.numero_da_curva(nome), nome, nivel, exp["medidas"], self.L, self.pontos_dos_marcos)
        self._registrar({"tipo": "analise", "trecho": nome, "volta": volta.get("volta"), "nivel": nivel, "t": self._relogio(),
                         "diferencas": difs, "texto": texto,
                         "medidas": {c: pm.get(c) for c in ("freada", "virar", "minimaKmh", "apiceDaBordaM", "aceleradorCheio",
                                                            "saidaDaBordaM")}})
        if not texto:
            return
        if nivel == "iniciante":
            self.relatorio_lento = (self.relatorio_lento + [{"trecho": nome, "texto": texto}])[-20:]
        else:
            # a regra do pedido 45 (C.1, item 5): a analise que nao saiu ate o carro voltar a curva sai da fila
            m = self._mensagem(f"análise · {nome}", texto, 8.0, frente=True)
            m["_curvaS"] = float(self.trechos[k].entrada_s)
            self._mensagens.append(m)

    def _na_volta_lenta(self, s: float) -> None:
        """Item 8: no nivel iniciante, a explicacao longa de cada curva do escopo a frente do carro e as analises
        guardadas, uma vez por volta lenta."""
        if self.config.get("nivel") != "iniciante":
            return
        def frente(n: str) -> float:
            fb = self.fichas_base.get(n)
            return ((float(fb["sPonto"]) - s) % self.L) if fb else 1e9
        for n in sorted(self.escopo(), key=frente):
            exp = self.explicacoes.get(n)
            if exp is not None:
                self._mensagens.append(self._mensagem(f"explicação · {n}", exp["textos"]["iniciante"], 30.0, frente=False))
        for item in self.relatorio_lento:
            self._mensagens.append(self._mensagem(f"análise · {item['trecho']}", item["texto"], 30.0, frente=False))
        self.relatorio_lento = []

    def _na_linha_do_treino(self, volta: Optional[Any], conta: bool) -> None:
        """Item 7: o treino comeca na linha seguinte ao botao; conta as voltas que contam, com as analises delas."""
        t = self.treino
        if t is None:
            return
        if t["desdeAVolta"] is None:
            t["desdeAVolta"] = volta
            self._registrar({"tipo": "treino", "evento": "primeira linha", "volta": volta, "voltas": t["voltas"]})
            return
        if not conta:
            return
        t["feitas"] += 1
        for nome in self.escopo():
            t["analises"].setdefault(nome, []).append(list(self._analises_da_volta.get(nome, [])))
        if t["feitas"] >= t["voltas"]:
            self._fim_do_treino(volta)

    def _fim_do_treino(self, volta: Optional[Any]) -> None:
        t, self.treino = self.treino, None
        rel = E.relatorio_do_treino(t["analises"], t["voltas"])
        nivel = self.config.get("nivel", E.NIVEL_PADRAO)
        itens = []
        for c in rel:
            exp = self.explicacoes.get(c["trecho"]) or {}
            texto = E.texto_da_analise(c["diferencas"], R.numero_da_curva(c["trecho"]), c["trecho"], nivel,
                                       exp.get("medidas") or {}, self.L, self.pontos_dos_marcos)
            if texto:
                itens.append({"trecho": c["trecho"], "texto": texto, "custoS": c["custoS"]})
        volume = sum(E.duracao_estimada(i["texto"]) for i in itens)
        ori = E.orientacao(volume) if itens else {"tipo": "nada a corrigir", "voltasLentas": 0,
                                                   "texto": "Fim do treino. Nenhuma curva passou dos limites."}
        self.ultimo_treino = {"volta": volta, "voltas": t["voltas"], "itens": itens, "volumeS": round(volume, 1), "orientacao": ori}
        self._registrar({"tipo": "treino", "evento": "fim", "volta": volta, "voltas": t["voltas"], "relatorio": rel,
                         "itens": itens, "volumeS": round(volume, 1), "orientacao": ori})
        self._mensagens.append(self._mensagem("treino", ori["texto"], 8.0, frente=True))
        for i in itens:
            self._mensagens.append(self._mensagem(f"treino · {i['trecho']}", i["texto"], 30.0, frente=False))


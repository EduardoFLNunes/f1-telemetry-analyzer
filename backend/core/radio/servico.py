"""O radio do engenheiro no backend (pedido 31, Parte B): da frase do coach a mensagem entregue.

1. **Nasce:** cada frase de diferenca do coach (`coaching_event`) vira uma
   mensagem (`texto.mensagem_de_diferenca`) e o audio comeca a ser gerado.
   O resumo nasce na linha de chegada, com o periodo da volta que o coach mede.
2. **Espera:** so e entregue com o carro numa janela de radio (`janelas`), com a
   posicao que o coach ja projeta. Uma por vez: a seguinte espera o audio da
   anterior acabar. Se a volta acaba antes, a mensagem vai junto com o resumo.
3. **E entregue:** ganha um id, entra na lista que o app do jogo e a tela Ao vivo
   leem (`desde(id)`) e e registrada em `<pasta de dados>/data/radio/<sessao>.jsonl`,
   fora da pasta de gravacoes.

O radio nao decide nada: quais frases saem, o limite de 3 por volta, o foco e o
limiar continuam no coach. Ele so escreve e entrega.
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

from . import audio as audio_do_radio
from .janelas import Janela, carregar_curvas, dentro, janelas_de_radio
from .texto import CurvaDaPista, mensagem_de_diferenca, mensagem_de_resumo, mensagem_de_teste

logger = logging.getLogger(__name__)

ESPERA_DO_RESUMO_S = 0.6       # as ultimas frases da volta chegam pelo barramento logo depois da linha
FOLGA_ENTRE_MENSAGENS_S = 0.6
ESPERA_DO_AUDIO_S = 4.0        # sem audio pronto ate aqui, a mensagem sai sem voz
GUARDADAS = 200


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
        self._chave_da_pista: Optional[str] = None
        self.erro_da_voz: Optional[str] = None

    # ------------------------------------------------------------- pista ---

    def _pista(self) -> bool:
        repo = self._repositorio()
        chave = str(repo) if repo else None
        if chave != self._chave_da_pista:
            self._chave_da_pista = chave
            try:
                self._curvas, self._comprimento = carregar_curvas(repo)
            except Exception as erro:  # sem a geometria oficial o radio fica calado
                logger.warning("Radio sem a geometria oficial: %s", erro)
                self._curvas, self._comprimento = [], None
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
        arquivo = self.pasta_audio / f"{self.instancia}_{id(mensagem)}.wav"
        try:
            self.pasta_audio.mkdir(parents=True, exist_ok=True)
            dur = self._falar(mensagem["fala"], arquivo)
        except Exception as erro:
            self.erro_da_voz = str(erro)
            logger.warning("Radio sem voz: %s", erro)
            return None
        self.erro_da_voz = None
        mensagem["duracaoS"] = round(float(dur), 2)
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
            self._pendentes.append(self._nova(mensagem))

    # ---------------------------------------------------------- entregar ---

    def on_frame(self, _frame: Any = None) -> None:
        """A cada quadro, sem nunca esperar: a linha (o resumo) e a janela (a proxima mensagem)."""
        agora = self._relogio()
        with self._lock:
            volta = self._ultima_volta()
            if volta and volta.get("momento") != self._volta_vista:
                self._volta_vista = volta.get("momento")
                self._resumo_desde = agora
                self._resumo = volta
            if self._resumo_desde is not None and agora - self._resumo_desde >= ESPERA_DO_RESUMO_S:
                self._resumo_na_linha()
            if not self._pendentes or agora < self._ocupado_ate:
                return
            proxima = self._pendentes[0]
            if not self._audio_pronto(proxima, agora):
                return
            pos = self._posicao() or {}
            if not proxima.get("naLinha"):
                if not pos or not self._pista():
                    return
                if dentro(self._janelas, float(pos["s"]), float(self._comprimento or pos["comprimento"])) is None:
                    return
            self._entregar(self._pendentes.popleft(), agora, pos)

    def _audio_pronto(self, mensagem: Dict[str, Any], agora: float) -> bool:
        futuro = mensagem.get("_futuro")
        return futuro is None or futuro.done() or agora - mensagem["criadaEm"] >= ESPERA_DO_AUDIO_S

    def _resumo_na_linha(self) -> None:
        """A volta acabou: o que ficou dela sai na linha, sem esperar janela, e depois o resumo."""
        volta, self._resumo_desde = self._resumo, None
        for m in self._pendentes:
            m["naLinha"] = True
        if not volta or volta.get("teveIA"):
            return
        ref = self._referencia() or {}
        resumo = self._nova(mensagem_de_resumo(volta.get("volta"), float(volta["tempoS"]), ref.get("tempoS"),
                                               ref.get("tipo")))
        resumo["naLinha"] = True
        self._pendentes.append(resumo)

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
        mensagem["voltaDoCarro"] = pos.get("volta")
        mensagem["sessao"] = self._sessao()
        mensagem.pop("naLinha", None)
        if arquivo is not None:
            mensagem["audio"] = f"/api/radio/audio/{mensagem['id']}"
            mensagem["_arquivo"] = str(arquivo)
        self._ocupado_ate = agora + float(mensagem.get("duracaoS") or 3.0) + FOLGA_ENTRE_MENSAGENS_S
        self._entregues.append(mensagem)
        self._registrar(mensagem)
        return mensagem

    def _registrar(self, mensagem: Dict[str, Any]) -> None:
        sessao = mensagem.get("sessao") or f"sem-gravacao_{datetime.now():%Y-%m-%d}"
        linha = {k: mensagem.get(k) for k in ("id", "instancia", "entregueEm", "voltaDoCarro", "sCarro", "s",
                                              "microssetor", "curva", "origem", "titulo", "texto", "detalhe", "fala",
                                              "perdaS", "volta", "tempoS", "duracaoS")}
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            with (self.pasta / f"{sessao}.jsonl").open("a", encoding="utf-8") as saida:
                saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
        except OSError as erro:
            logger.warning("Radio sem registro: %s", erro)

    # ------------------------------------------------------------ leitura ---

    @staticmethod
    def _publica(m: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in m.items() if not k.startswith("_")}

    def desde(self, id_: int = 0, instancia: Optional[str] = None) -> Dict[str, Any]:
        """As mensagens entregues depois de `id_`. Outra instancia (backend reiniciado): todas."""
        with self._lock:
            desde = 0 if instancia and instancia != self.instancia else int(id_ or 0)
            novas = [self._publica(m) for m in self._entregues if m["id"] > desde]
            return {"instancia": self.instancia, "ultimoId": self._proximo_id - 1, "mensagens": novas,
                    "pendentes": len(self._pendentes), "erroDaVoz": self.erro_da_voz}

    def arquivo_do_audio(self, id_: int) -> Optional[Path]:
        with self._lock:
            for m in self._entregues:
                if m["id"] == id_ and m.get("_arquivo"):
                    return Path(m["_arquivo"])
        return None

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
                    "erroDaVoz": self.erro_da_voz, "pastaDoRegistro": str(self.pasta)}

"""O que os modelos precisam que a gravacao tenha (pedido 28, Parte B).

Uma lista so. A aba "Coleta de dados", a conferencia de fim de sessao e os
testes leem daqui; o front nao copia nada a mao.

Cada item diz:

* onde o valor esta no que o gravador escreve (`componentes`: um caminho por
  roda ou eixo, com os formatos antigos como alternativa) e de que parte da
  linha ele vem (`fonte`: a amostra, o envelope ou o `metadata.json`);
* a coluna do achatamento do ML (`ml.data.samples.flatten`), quando existe, e
  as colunas do store v2 que saem dele;
* quem usa: coach, store v2 e LSTM, origem da volta, limites de pista, modelo do
  carro (M1) e o bloco `tecnica` do relatorio de evolucao;
* a unidade, a faixa plausivel, o preenchimento minimo e se ele e obrigatorio
  na regra da M1 (`docs/modelo_fisico_m0.md`, secao 6).

**As faixas.** Onde o inventario do pedido 18
(`docs/handoff/2026-10-04_canais-fisicos_inventario.json`, sessao de 04/10 do
repositorio, 447.811 amostras) mediu o campo, a faixa e
`[p1 - m, p99 + m]`, com a margem `m = 0,5 x (p99 - p1)`, cortada nos limites
fisicos do item (pedal entre 0 e 1, temperatura e carga nao negativas). O p1 e
o p99 ficam copiados aqui (`p1_p99`) porque o backend empacotado nao le `docs/`;
um teste confere a copia contra o JSON. Onde o inventario nao mediu (os canais
que o gravador so passou a gravar no pedido 18, e os de base que ele nao
listou), a faixa e um limite fisico com folga, e `fonte_faixa` diz isso.

**O preenchimento minimo.** Os cinco canais do portao de qualidade
(`ml.config.REQUIRED_CHANNELS`) usam o limiar do proprio portao, 90%. Os outros,
95%, o limiar das checagens do pedido 18, que e tambem o da regra da M1.

Este modulo nao importa `ml`: o backend empacotado le daqui sem levar o pacote
de ML inteiro. Os testes conferem os nomes contra o `ml`.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# ------------------------------------------------------------- regras ---

# Regra da contagem da M1 (docs/modelo_fisico_m0.md, secao 6): so contam sessoes
# humanas com estes canais em pelo menos 95% dos pontos das voltas validas.
PREENCHIMENTO_M1 = 0.95
SESSOES_M1 = 5

# O carro e a pista das sessoes de treino. Outro carro ou outra pista nao
# impedem a gravacao; a aba so avisa.
CARRO_ESPERADO = "rss_formula_rss_3_v6_2026"
PISTA_ESPERADA = "vhe_interlagos"

# Conferencia ao vivo: a janela, a taxa abaixo da qual o canal esta lento (40 Hz
# e o piso das voltas que ensinam o modelo do coach, `reference_model.MIN_SAMPLE_HZ`
# e `ml.config.REFERENCE_MIN_SAMPLE_HZ`), a velocidade a partir da qual um valor
# constante e "parado", e a fracao de amostras fora da faixa tolerada.
JANELA_AO_VIVO_S = 5.0
TAXA_MINIMA_HZ = 40.0
VELOCIDADE_ANDANDO_KMH = 30.0
FORA_DA_FAIXA_TOLERADO = 0.05

# Espaco livre no disco das gravacoes. A sessao de 41 min de 10/10 ocupou 0,53 GB.
ESPACO_AMARELO_GB = 5.0
ESPACO_VERMELHO_GB = 2.0

# Margem das faixas medidas: metade da largura p1-p99 de cada lado.
MARGEM_DA_FAIXA = 0.5

PREENCHIMENTO_PORTAO = 0.90   # ml.config.MIN_CHANNEL_COVERAGE
PREENCHIMENTO_PADRAO = 0.95   # checagens do pedido 18

# Quem usa cada item.
USOS = {
    "coach": "coach",
    "store_v2": "store v2 e LSTM",
    "origem": "origem da volta",
    "limites": "limites de pista",
    "m1": "modelo do carro (M1)",
    "tecnica": "bloco técnica do relatório de evolução",
}

GRUPOS = (
    ("base", "Base"),
    ("origem", "Origem da volta"),
    ("limites", "Limites de pista"),
    ("m1", "Modelo do carro (M1)"),
    ("contexto", "Contexto do store v2"),
)

RODAS = ("fl", "fr", "rl", "rr")
ROTULO_RODA = {"fl": "DE", "fr": "DD", "rl": "TE", "rr": "TD"}


# -------------------------------------------------------------- itens ---

@dataclass(frozen=True)
class Componente:
    """Um valor do item: uma roda, um eixo, ou o proprio item."""

    rotulo: str
    caminhos: Tuple[str, ...]          # o primeiro e o do gravador atual; os outros, formatos antigos
    coluna_amostra: Optional[str] = None


@dataclass(frozen=True)
class Requisito:
    id: str
    nome: str
    grupo: str
    componentes: Tuple[Componente, ...]
    usos: Tuple[str, ...]
    unidade: str
    faixa: Optional[Tuple[float, float]]
    fonte_faixa: str
    preenchimento_minimo: float = PREENCHIMENTO_PADRAO
    colunas_store: Tuple[str, ...] = ()
    obrigatorio_m1: bool = False
    # "varia": valor constante com o carro andando e defeito; "zero": so o zero
    # constante e defeito (a embreagem das gravacoes antigas); None: nao se aplica.
    parado: Optional[str] = None
    fonte: str = "amostra"             # "amostra", "envelope" ou "metadata"
    tipo: str = "numero"               # "numero", "booleano" ou "texto"
    valor_esperado: Optional[str] = None
    p1_p99: Optional[Tuple[float, float]] = None
    nota: str = ""

    @property
    def campo(self) -> str:
        """O caminho do gravador atual, com as rodas abreviadas: `carPhysics.brakes.brakeTemp[0..3]`."""
        caminhos = [c.caminhos[0] for c in self.componentes]
        if len(caminhos) == 4 and all(re.search(r"\[\d\]$", c) for c in caminhos):
            return re.sub(r"\[\d\]$", "[0..3]", caminhos[0])
        prefixos = {c.rsplit(".", 1)[0] for c in caminhos if "." in c}
        if len(caminhos) > 1 and len(prefixos) == 1 and all("." in c for c in caminhos):
            return f"{prefixos.pop()}.{{{', '.join(c.rsplit('.', 1)[1] for c in caminhos)}}}"
        return ", ".join(caminhos)

    @property
    def colunas_amostra(self) -> Tuple[str, ...]:
        return tuple(c.coluna_amostra for c in self.componentes if c.coluna_amostra)

    def to_api(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "grupo": self.grupo,
            "campo": self.campo,
            "fonte": self.fonte,
            "tipo": self.tipo,
            "componentes": [
                {"rotulo": c.rotulo, "caminhos": list(c.caminhos), "colunaAmostra": c.coluna_amostra}
                for c in self.componentes
            ],
            "colunasStore": list(self.colunas_store),
            "usos": list(self.usos),
            "usosRotulos": [USOS[u] for u in self.usos],
            "unidade": self.unidade,
            "faixa": list(self.faixa) if self.faixa else None,
            "fonteFaixa": self.fonte_faixa,
            "preenchimentoMinimo": self.preenchimento_minimo,
            "obrigatorioM1": self.obrigatorio_m1,
            "parado": self.parado,
            "valorEsperado": self.valor_esperado,
            "nota": self.nota,
        }


def faixa_medida(p1: float, p99: float, fisico: Tuple[float, float] = (-math.inf, math.inf)) -> Tuple[float, float]:
    """`[p1 - m, p99 + m]`, com `m = MARGEM_DA_FAIXA x (p99 - p1)`, cortada no limite fisico."""
    margem = MARGEM_DA_FAIXA * (p99 - p1)
    baixo = max(fisico[0], p1 - margem)
    alto = min(fisico[1], p99 + margem)
    return (round(baixo, 4), round(alto, 4))


def _medida(p1: float, p99: float, fisico=(-math.inf, math.inf)) -> Dict[str, Any]:
    return {
        "faixa": faixa_medida(p1, p99, fisico),
        "p1_p99": (p1, p99),
        "fonte_faixa": f"inventário do pedido 18 (04/10): p1 {p1:g}, p99 {p99:g}, com margem de 50%",
    }


def _fisica(baixo: float, alto: float, motivo: str) -> Dict[str, Any]:
    return {"faixa": (baixo, alto), "fonte_faixa": f"limite físico, sem medição no pedido 18: {motivo}"}


def _um(caminhos: Sequence[str], coluna: Optional[str] = None, rotulo: str = "") -> Tuple[Componente, ...]:
    return (Componente(rotulo, tuple(caminhos), coluna),)


def _rodas(base: str, prefixo_coluna: Optional[str] = None) -> Tuple[Componente, ...]:
    return tuple(
        Componente(ROTULO_RODA[roda], (f"{base}[{i}]",), f"{prefixo_coluna}_{roda}" if prefixo_coluna else None)
        for i, roda in enumerate(RODAS)
    )


def _colunas_rodas(prefixo: str) -> Tuple[str, ...]:
    return tuple(f"{prefixo}_{roda}" for roda in RODAS)


REQUISITOS: Tuple[Requisito, ...] = (
    # ------------------------------------------------------------- base ---
    Requisito(
        id="lap_time", nome="Cronômetro do jogo", grupo="base",
        componentes=_um(("lap_time", "lapTime", "currentLapTime"), "lap_time_s"),
        colunas_store=("lap_time_s", "elapsed_s"),
        usos=("coach", "store_v2"), unidade="s", parado="varia",
        **_fisica(0.0, 600.0, "uma volta de Interlagos fica entre 85 e 200 s; a volta de saída do box pode passar disso"),
        preenchimento_minimo=PREENCHIMENTO_PADRAO,
        nota="O relógio da volta no store sai dele (elapsed_s e lap_time_s).",
    ),
    Requisito(
        id="lap_number", nome="Número da volta", grupo="base",
        componentes=_um(("lap_number", "lap"), "lap_number"),
        usos=("coach", "store_v2", "origem"), unidade="volta do jogo",
        **_fisica(0.0, 1000.0, "contador de voltas da sessão do jogo"),
        nota="Vai para a tabela de voltas do store (lap_number), não para a grade.",
    ),
    Requisito(
        id="distance", nome="Distância na volta", grupo="base",
        componentes=_um(("distanceAlongTrack", "s"), "s_recorded"),
        usos=("store_v2",), unidade="m", parado="varia",
        **_fisica(0.0, 4400.0, "a volta de Interlagos tem 4334 m"),
        nota="Só conferência: o pipeline recalcula a distância pela posição na geometria oficial.",
    ),
    Requisito(
        id="position", nome="Posição x e z", grupo="base",
        componentes=(
            Componente("x", ("world_x", "worldPosition[0]"), "x"),
            Componente("z", ("world_z", "worldPosition[2]"), "z"),
        ),
        colunas_store=("x", "z", "lateral"),
        usos=("coach", "store_v2"), unidade="m (mundo do jogo)", parado="varia",
        **_fisica(-2000.0, 2000.0, "a pista inteira cabe com folga em ±2 km"),
        nota="O coach projeta a posição na geometria oficial; o lateral do store sai dela.",
    ),
    Requisito(
        id="speed", nome="Velocidade", grupo="base",
        componentes=_um(("speedKmh", "carPhysics.motion.speedKmh"), "speed_kmh"),
        colunas_store=("speed_kmh",),
        usos=("coach", "store_v2"), unidade="km/h", parado="varia",
        **_fisica(0.0, 360.0, "o carro passa pouco de 280 km/h na reta"),
    ),
    Requisito(
        id="throttle", nome="Acelerador", grupo="base",
        componentes=_um(("carPhysics.controls.throttle", "throttle"), "throttle"),
        colunas_store=("throttle",),
        usos=("coach", "store_v2"), unidade="0 a 1",
        preenchimento_minimo=PREENCHIMENTO_PORTAO,
        **_medida(0.0, 1.0, (0.0, 1.0)),
    ),
    Requisito(
        id="brake", nome="Freio", grupo="base",
        componentes=_um(("carPhysics.controls.brake", "brake"), "brake"),
        colunas_store=("brake",),
        usos=("coach", "store_v2", "tecnica"), unidade="0 a 1",
        preenchimento_minimo=PREENCHIMENTO_PORTAO,
        **_medida(0.0, 1.0, (0.0, 1.0)),
    ),
    Requisito(
        id="steering", nome="Volante", grupo="base",
        componentes=_um(("carPhysics.controls.steerAngle", "steering"), "steering"),
        colunas_store=("steering", "steer_angle"),
        usos=("store_v2", "tecnica", "m1"), unidade="sem unidade documentada",
        preenchimento_minimo=PREENCHIMENTO_PORTAO,
        **_medida(-0.479, 0.5057),
        nota="Positivo é virar para a direita (docs/modelo_fisico_m0.md, seção 3). No box chega a ±0,98.",
    ),
    Requisito(
        id="gear", nome="Marcha", grupo="base",
        componentes=_um(("carPhysics.controls.gear", "gear"), "gear"),
        colunas_store=("gear",),
        usos=("store_v2",), unidade="marcha do jogo (0 = ré, 1 = neutro)",
        **_medida(0.0, 6.0, (0.0, 10.0)),
    ),
    Requisito(
        id="rpm", nome="Rotação", grupo="base",
        componentes=_um(("carPhysics.controls.rpm", "rpm"), "rpm"),
        colunas_store=("rpm",),
        usos=("store_v2",), unidade="rpm", parado="varia",
        **_fisica(0.0, 15000.0, "motor V6 de Fórmula 3"),
    ),
    # ----------------------------------------------------------- origem ---
    Requisito(
        id="ai_controlled", nome="Indicador de IA", grupo="origem",
        componentes=_um(("carPhysics.controls.isAIControlled", "isAIControlled", "is_ai_controlled"), "ai_controlled"),
        usos=("origem", "coach", "store_v2"), unidade="ligado ou desligado", tipo="booleano",
        faixa=None, fonte_faixa="não se aplica",
        nota="Decide a origem da volta (origem_indicador e origem no store). Desligado em todas as voltas é sessão humana.",
    ),
    Requisito(
        id="car_model", nome="Modelo do carro", grupo="origem",
        componentes=_um(("metadata.carModel",)), fonte="metadata", tipo="texto",
        usos=("origem", "store_v2"), unidade="nome do jogo",
        faixa=None, fonte_faixa="não se aplica", valor_esperado=CARRO_ESPERADO,
        nota="Vai para a coluna carModel da tabela de voltas do store.",
    ),
    Requisito(
        id="track", nome="Pista", grupo="origem",
        componentes=_um(("track",)), fonte="envelope", tipo="texto",
        usos=("origem", "store_v2"), unidade="nome do jogo",
        faixa=None, fonte_faixa="não se aplica", valor_esperado=PISTA_ESPERADA,
        nota="Gravada em cada linha e no metadata.json; o ML só lê sessões de Interlagos.",
    ),
    # ---------------------------------------------------------- limites ---
    Requisito(
        id="tyres_out", nome="Pneus fora", grupo="limites",
        componentes=_um(("carPhysics.environment.tyresOut",), "tyres_out"),
        usos=("limites", "store_v2"), unidade="rodas fora (0 a 4)",
        **_fisica(0.0, 4.0, "número de rodas"),
        nota="O portão de qualidade usa duas rodas fora quando não há o offTrack.",
    ),
    Requisito(
        id="off_track", nome="Fora da pista", grupo="limites",
        componentes=_um(("carPhysics.environment.offTrack",), "off_track"),
        colunas_store=("off_track",),
        usos=("limites", "store_v2"), unidade="sim ou não", tipo="booleano",
        faixa=None, fonte_faixa="não se aplica",
        nota="Portão de qualidade: no máximo 5% das amostras fora.",
    ),
    # --------------------------------------------------------------- M1 ---
    Requisito(
        id="yaw_rate", nome="Guinada", grupo="m1",
        componentes=_um(("carPhysics.motion.localAngularVelocity.y",), "yaw_rate"),
        colunas_store=("yaw_rate",), obrigatorio_m1=True,
        usos=("m1", "store_v2"), unidade="rad/s", parado="varia",
        **_fisica(-5.0, 5.0, "um grampo a 60 km/h dá cerca de 0,7 rad/s; um pião passa de 2"),
    ),
    Requisito(
        id="velocity_long", nome="Velocidade longitudinal (referencial do carro)", grupo="m1",
        componentes=_um(("carPhysics.motion.localVelocity.z",), "velocity_long"),
        colunas_store=("velocity_long",), obrigatorio_m1=True,
        usos=("m1", "store_v2"), unidade="m/s", parado="varia",
        **_fisica(-20.0, 100.0, "até 360 km/h para a frente, com ré"),
    ),
    Requisito(
        id="velocity_lat", nome="Velocidade lateral (referencial do carro)", grupo="m1",
        componentes=_um(("carPhysics.motion.localVelocity.x",), "velocity_lat"),
        colunas_store=("velocity_lat",), obrigatorio_m1=True,
        usos=("m1", "store_v2"), unidade="m/s", parado="varia",
        **_fisica(-30.0, 30.0, "deriva com folga"),
    ),
    Requisito(
        id="brake_temp", nome="Temperatura dos freios", grupo="m1",
        componentes=_rodas("carPhysics.brakes.brakeTemp", "brake_temp"),
        colunas_store=_colunas_rodas("brake_temp"),
        usos=("m1", "store_v2", "tecnica"), unidade="°C", parado="varia",
        **_fisica(0.0, 1200.0, "disco de freio frio a muito quente"),
    ),
    Requisito(
        id="brake_bias", nome="Distribuição dos freios", grupo="m1",
        componentes=_um(("carPhysics.brakes.brakeBias",)),
        usos=("m1",), unidade="fração na dianteira",
        **_fisica(0.0, 1.0, "fração"),
        nota="Ajuste do carro: constante na sessão é normal.",
    ),
    Requisito(
        id="tyre_core_temp", nome="Temperatura do núcleo do pneu", grupo="m1",
        componentes=_rodas("carPhysics.tyres.tyreCoreTemperature", "tyre_core_temp"),
        colunas_store=_colunas_rodas("tyre_core_temp"),
        usos=("m1", "store_v2", "tecnica"), unidade="°C", parado="varia",
        **_medida(0.006, 86.7905, (0.0, math.inf)),
    ),
    Requisito(
        id="tyre_temp_inner", nome="Temperatura da superfície do pneu, interna", grupo="m1",
        componentes=_rodas("carPhysics.tyres.tyreTempInner"),
        usos=("m1",), unidade="°C", parado="varia",
        **_fisica(0.0, 200.0, "superfície do pneu"),
    ),
    Requisito(
        id="tyre_temp_middle", nome="Temperatura da superfície do pneu, central", grupo="m1",
        componentes=_rodas("carPhysics.tyres.tyreTempMiddle"),
        usos=("m1",), unidade="°C", parado="varia",
        **_fisica(0.0, 200.0, "superfície do pneu"),
    ),
    Requisito(
        id="tyre_temp_outer", nome="Temperatura da superfície do pneu, externa", grupo="m1",
        componentes=_rodas("carPhysics.tyres.tyreTempOuter"),
        usos=("m1",), unidade="°C", parado="varia",
        **_fisica(0.0, 200.0, "superfície do pneu"),
    ),
    Requisito(
        id="wheel_load", nome="Carga na roda", grupo="m1",
        componentes=_rodas("carPhysics.tyres.wheelLoad", "wheel_load"),
        colunas_store=_colunas_rodas("wheel_load"),
        usos=("m1", "store_v2"), unidade="N", parado="varia",
        **_medida(16.391, 5605.4646, (0.0, math.inf)),
    ),
    Requisito(
        id="wheel_slip", nome="Escorregamento", grupo="m1",
        componentes=_rodas("carPhysics.tyres.wheelSlip", "wheel_slip"),
        colunas_store=_colunas_rodas("wheel_slip") + ("wheel_slip",),
        usos=("m1", "store_v2"), unidade="adimensional (medida do jogo)", parado="varia",
        **_medida(0.0007, 2.0403, (0.0, math.inf)),
    ),
    Requisito(
        id="tyre_pressure", nome="Pressão do pneu", grupo="m1",
        componentes=_rodas("carPhysics.tyres.tyrePressure", "tyre_pressure"),
        colunas_store=_colunas_rodas("tyre_pressure"),
        usos=("m1", "store_v2"), unidade="psi", parado="varia",
        **_medida(13.0047, 22.0547, (0.0, math.inf)),
    ),
    Requisito(
        id="suspension_travel", nome="Curso da suspensão", grupo="m1",
        componentes=_rodas("carPhysics.suspension.suspensionTravel"),
        usos=("m1",), unidade="m", parado="varia",
        **_medida(0.0349, 0.0667, (0.0, math.inf)),
    ),
    Requisito(
        id="acc_g", nome="Aceleração (accG)", grupo="m1",
        componentes=(
            Componente("lat", ("carPhysics.motion.accG.lateral", "accel_g.x"), "lateral_g"),
            Componente("long", ("carPhysics.motion.accG.longitudinal", "accel_g.z"), "longitudinal_g"),
            Componente("vert", ("carPhysics.motion.accG.vertical", "accel_g.y"), "vertical_g"),
        ),
        colunas_store=("lateral_g", "longitudinal_g"),
        usos=("m1", "store_v2", "tecnica"), unidade="g", parado="varia",
        preenchimento_minimo=PREENCHIMENTO_PORTAO,
        **_medida(-2.0635, 2.0727),
        nota="A lateral e a longitudinal estão no portão de qualidade.",
    ),
    Requisito(
        id="clutch", nome="Embreagem", grupo="m1",
        componentes=_um(("carPhysics.controls.clutch", "clutch"), "clutch"),
        usos=("m1",), unidade="0 a 1", parado="zero",
        **_fisica(0.0, 1.0, "pedal; o inventário do pedido 18 só viu o 0 do erro do adaptador"),
        nota="As gravações antigas têm 0 sempre (adaptador desalinhado). 1 é o pedal solto.",
    ),
    # ---------------------------------------------------------- contexto ---
    Requisito(
        id="fuel", nome="Combustível", grupo="contexto",
        componentes=_um(("carPhysics.carState.fuel",), "fuel"),
        colunas_store=("fuel",),
        usos=("store_v2",), unidade="L",
        **_fisica(0.0, 150.0, "tanque de 65 L"),
    ),
    Requisito(
        id="tyre_wear", nome="Desgaste do pneu", grupo="contexto",
        componentes=_rodas("carPhysics.tyres.tyreWear"),
        colunas_store=("tyre_wear",),
        usos=("store_v2",), unidade="% (100 = novo)",
        **_fisica(0.0, 100.0, "porcentagem; em 04/10 os pneus estavam novos (p1 99,94), então a faixa medida não serve"),
        nota="O store guarda a média das 4 rodas.",
    ),
    Requisito(
        id="grip_index", nome="Índice de aderência estimado", grupo="contexto",
        componentes=_rodas("carPhysics.tyres.estimatedGripIndex"),
        colunas_store=("grip_index",),
        usos=("store_v2",), unidade="adimensional (calculado pelo app)",
        **_fisica(0.0, 1.2, "o cálculo (core.car_physics.infer_grip_index) fica entre 0 e 1,2"),
        nota="Calculado pelo app, não lido do jogo. O store guarda a média das 4 rodas.",
    ),
)

POR_ID: Dict[str, Requisito] = {r.id: r for r in REQUISITOS}
OBRIGATORIOS_M1: Tuple[Requisito, ...] = tuple(r for r in REQUISITOS if r.obrigatorio_m1)
COLUNAS_M1: Tuple[str, ...] = tuple(c for r in OBRIGATORIOS_M1 for c in r.colunas_store)

# Os nomes da regra, em portugues, para o "o que falta".
NOME_M1 = {
    "yaw_rate": "a guinada",
    "velocity_long": "a velocidade longitudinal no referencial do carro",
    "velocity_lat": "a velocidade lateral no referencial do carro",
}


def colunas_store() -> Tuple[str, ...]:
    """Todas as colunas do store v2 que algum item produz."""
    out: List[str] = []
    for item in REQUISITOS:
        for coluna in item.colunas_store:
            if coluna not in out:
                out.append(coluna)
    return tuple(out)


def por_grupo() -> List[Tuple[str, str, List[Requisito]]]:
    return [(gid, nome, [r for r in REQUISITOS if r.grupo == gid]) for gid, nome in GRUPOS]


# -------------------------------------------------------- ler o valor ---

_PASSO = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


@lru_cache(maxsize=1024)
def _passos(caminho: str) -> Tuple[Tuple[str, str], ...]:
    return tuple(_PASSO.findall(caminho))


def ler_caminho(dados: Any, caminho: str) -> Any:
    """`carPhysics.tyres.wheelLoad[2]` dentro de um dicionario; None se algo faltar."""
    atual = dados
    for chave, indice in _passos(caminho):
        if atual is None:
            return None
        if chave:
            if not isinstance(atual, Mapping):
                return None
            atual = atual.get(chave)
        else:
            if not isinstance(atual, (list, tuple)):
                return None
            i = int(indice)
            atual = atual[i] if i < len(atual) else None
    return atual


def _normalizar(valor: Any, tipo: str) -> Any:
    if valor is None:
        return None
    if tipo == "texto":
        texto = str(valor).strip()
        return texto or None
    if tipo == "booleano":
        if isinstance(valor, bool):
            return valor
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return None
        return None if not math.isfinite(numero) else numero != 0.0
    if isinstance(valor, bool):
        return float(valor)
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def valor_componente(item: Requisito, componente: Componente, amostra: Mapping[str, Any],
                     envelope: Optional[Mapping[str, Any]] = None,
                     metadata: Optional[Mapping[str, Any]] = None) -> Any:
    """O valor de um componente, pelo primeiro caminho que tiver valor.

    `amostra` e o `sample` de uma linha do `player.jsonl` (o quadro que o
    gravador recebe); `envelope` e a linha inteira; `metadata`, o `metadata.json`.
    """
    base: Any = amostra
    if item.fonte == "envelope":
        base = envelope if envelope is not None else {}
    elif item.fonte == "metadata":
        base = metadata if metadata is not None else {}
    for caminho in componente.caminhos:
        valor = _normalizar(ler_caminho(base, caminho), item.tipo)
        if valor is not None:
            return valor
    return None


def valores(item: Requisito, amostra: Mapping[str, Any], envelope=None, metadata=None) -> List[Any]:
    return [valor_componente(item, c, amostra, envelope, metadata) for c in item.componentes]


def fora_da_faixa(item: Requisito, valor: Any) -> bool:
    if item.faixa is None or item.tipo != "numero" or valor is None:
        return False
    baixo, alto = item.faixa
    return not (baixo <= float(valor) <= alto)


def registro_api() -> Dict[str, Any]:
    """O registro inteiro, como a aba le."""
    return {
        "grupos": [{"id": gid, "nome": nome, "itens": [r.id for r in itens]} for gid, nome, itens in por_grupo()],
        "itens": [r.to_api() for r in REQUISITOS],
        "regras": {
            "preenchimentoM1": PREENCHIMENTO_M1,
            "sessoesM1": SESSOES_M1,
            "colunasM1": list(COLUNAS_M1),
            "carroEsperado": CARRO_ESPERADO,
            "pistaEsperada": PISTA_ESPERADA,
            "janelaAoVivoS": JANELA_AO_VIVO_S,
            "taxaMinimaHz": TAXA_MINIMA_HZ,
            "velocidadeAndandoKmh": VELOCIDADE_ANDANDO_KMH,
            "foraDaFaixaTolerado": FORA_DA_FAIXA_TOLERADO,
            "espacoAmareloGb": ESPACO_AMARELO_GB,
            "espacoVermelhoGb": ESPACO_VERMELHO_GB,
            "margemDaFaixa": MARGEM_DA_FAIXA,
        },
        "usos": USOS,
    }


def tabela_markdown() -> str:
    """A tabela do registro para o relatorio (`python -m core.coleta.requisitos`)."""
    def numero(valor: float) -> str:
        if valor in (math.inf, -math.inf):
            return "∞" if valor > 0 else "−∞"
        if abs(valor) >= 1000:
            texto = f"{valor:,.0f}".replace(",", ".")
        else:
            texto = f"{valor:.4g}".replace(".", ",")
        return texto.replace("-", "−")

    linhas = [
        "| grupo | item | campo gravado | coluna do store v2 | quem usa | unidade | faixa | preench. mín. | M1 |",
        "|---|---|---|---|---|---|---|---:|---|",
    ]
    for _, nome_grupo, itens in por_grupo():
        for item in itens:
            faixa = f"{numero(item.faixa[0])} a {numero(item.faixa[1])}" if item.faixa else "—"
            linhas.append(
                f"| {nome_grupo} | {item.nome} | `{item.campo}` | "
                f"{', '.join(f'`{c}`' for c in item.colunas_store) or '—'} | "
                f"{', '.join(USOS[u] for u in item.usos)} | {item.unidade} | {faixa} | "
                f"{item.preenchimento_minimo:.0%} | {'obrigatório' if item.obrigatorio_m1 else ''} |"
            )
    return "\n".join(linhas)


if __name__ == "__main__":  # pragma: no cover - so imprime a tabela
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    print(tabela_markdown())

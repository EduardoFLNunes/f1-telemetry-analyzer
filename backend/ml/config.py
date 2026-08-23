"""Constantes do subsistema de aprendizado de tracado.

Todo numero aqui foi medido no dataset real (`data/recordings`), nao escolhido
por conveniencia. Os comentarios dizem de onde cada um saiu, porque um limiar
sem procedencia e a primeira coisa que alguem afrouxa quando o pipeline rejeita
uma volta que ele queria manter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------- caminhos ---

def repo_root() -> Path:
    """Raiz do repositorio (o diretorio que contem `backend/` e `data/`)."""
    return Path(__file__).resolve().parents[2]


def recordings_root() -> Path:
    return repo_root() / "data" / "recordings"


def track_cache_root() -> Path:
    return repo_root() / "data" / "cache" / "tracks"


def artifacts_root() -> Path:
    """Onde o pipeline escreve o que produz (indices, datasets, modelos)."""
    return repo_root() / "data" / "ml"


# Geometria de Interlagos reconstruida do KN5 do proprio jogo. E a mesma que o
# runtime usa para projetar o carro, entao `s` calculado aqui e o mesmo `s` que
# o app mostra.
INTERLAGOS_GEOMETRY_FILE = "vhe_interlagos_gp_kn5_surface_interval_geometry.json"

# Nomes de pista que contam como Interlagos no indice de sessoes.
INTERLAGOS_TRACK_PREFIXES = ("vhe_interlagos",)


# ------------------------------------------------------- grade de distancia ---

# Passo da reamostragem espacial. 2 m da 2168 pontos por volta em Interlagos:
# a 300 km/h o carro cruza 2 m em 24 ms, o que mantem o ponto de frenagem
# resolvido bem abaixo do erro humano de referencia (~0,1 s ~ 8 m).
RESAMPLE_STEP_M = 2.0

# A centerline em cache tem 2680 vertices para 4334 m, ~1,62 m entre vertices.
# Reamostrar mais fino que isso so interpola a propria geometria.
MIN_RESAMPLE_STEP_M = 1.5


# Desvio acima do qual a centerline reconstruida esta pulando para o lado, e
# nao seguindo a pista. Medido contra a propria centerline suavizada em 30 m: o
# p95 do desvio e 0,16 m e os 10 defeitos do cache de Interlagos chegam a
# 4,07 m -- a separacao entre pista e defeito e larga.
CENTERLINE_SPIKE_TOLERANCE_M = 0.6

# Comprimento da janela de suavizacao usada para derivar a centerline. A
# centerline vem de raycast sobre a malha do jogo e carrega ruido de
# reconstrucao; derivada duas vezes num passo de 2 m, esse ruido produz curvas
# de raio 3,7 m numa pista cuja curva mais fechada (a Juncao) tem ~25 m. 12 m
# de janela apaga o ruido e ainda resolve a Juncao com folga.
CURVATURE_SMOOTHING_M = 12.0

# Passa-baixo aplicado a propria centerline (nao so as derivadas dela).
#
# O conserto cirurgico tira os degraus de metros; sobram ondulacoes de
# centimetros, espalhadas por toda a pista, que nenhum detector pega porque nao
# sao defeito -- sao a resolucao da malha do jogo. Elas nao importariam se a
# trajetoria fosse medida no mundo, mas ela e medida *contra a centerline*: onde
# a linha de referencia ondula, o `lateral` de uma volta real ondula ao
# contrario para compensar, e nenhuma representacao suave consegue reproduzir
# essa compensacao. A volta era reconstruida 12 s mais lenta do que e.
#
# 60 m e o valor medido: a melhor volta continua simulando em 85,4 s, a mesma
# volta passada pela codificacao do algoritmo evolutivo cai de +12,4 s para
# +2,4 s de erro, e o raio minimo da pista sobe de 17,1 m para 23,3 m -- mais
# perto dos ~25 m que a Juncao tem de verdade.
#
# A largura da pista nao e afetada: as bordas viajam como posicoes no mundo e
# sao remedidas contra o frame final.
CENTERLINE_SMOOTHING_M = 60.0


# Janela de curvatura usada pelo simulador de tempo de volta -- maior que a da
# geometria, e por um motivo fisico, nao numerico.
#
# O carro nao responde a curvatura ponto a ponto: ele responde ao raio que
# percorre. Uma ondulacao de 20 cm a cada 25 m (que toda volta real tem, porque
# ninguem dirige em linha perfeitamente reta) e um raio de 79 m no papel, e a
# 250 km/h isso seriam 6 g -- o simulador freava ate 150 km/h no meio da reta.
#
# 30 m e o valor calibrado contra as 122 voltas reais: vies -0,14 s, erro medio
# 1,21 s e correlacao 0,93 com o cronometro. Janelas menores superestimam o
# tempo (12 m da +6,6 s de vies); maiores comecam a apagar as curvas de verdade.
SIMULATION_CURVATURE_SMOOTHING_M = 30.0

# ------------------------------------------------------------ microsetores ---

# 60 microsetores ~ 72 m cada, o mesmo corte que `core.assisted_analysis.
# reference_model` usa. Manter identico e o que permite comparar o que o
# modelo diz com o que o painel de analise assistida ja mostra.
MICROSECTORS = 60


# ------------------------------------------------- gates de qualidade de volta ---

# Uma volta de Interlagos no carro usado fica em 84,9 s no melhor caso medido.
# 55 s nao e volta; acima de 200 s tem parada de box ou saida de pista longa.
MIN_LAP_SECONDS = 55.0
MAX_LAP_SECONDS = 200.0

# 20 Hz e o piso para reamostrar a 2 m: a 300 km/h, 20 Hz da uma amostra a cada
# 4,2 m, ja interpolando entre pontos. Abaixo disso a trajetoria vira reta entre
# amostras justamente nas curvas rapidas.
#
# O inventario mostrou por que o piso importa: as duas voltas "mais rapidas" do
# dataset (82,698 s e 83,469 s) foram gravadas a 7,6 Hz -- gravacao truncada
# reportando tempo menor, nao recorde.
MIN_SAMPLE_HZ = 20.0
MAX_SAMPLE_HZ = 120.0

# Para as voltas que servem de *referencia* (as que ensinam o alvo), o piso e o
# mesmo do reference_model: 40 Hz.
REFERENCE_MIN_SAMPLE_HZ = 40.0

# Quantos metros de pista a volta pode deixar de cobrir.
#
# Expresso em metros e nao em fracao porque e o metro que tem significado: o
# trecho nao coberto e preenchido por extrapolacao da ultima velocidade, e o
# erro disso cresce com a distancia, nao com a porcentagem.
#
# Toda volta perde alguns metros no proprio corte da linha de chegada -- a
# mediana medida e 1,64 m e o p90 e 3,32 m. Acima disso e gravacao que parou
# antes: a volta `2026-06-19_23-24-46#0005` termina 16 m antes da linha, e esses
# 16 m produziam um ultimo microsetor de 0,719 s (360 km/h onde o carro fazia
# 271) que entrava na referencia do piloto como recorde.
#
# 6 m deixa passar 122 das 125 voltas e ainda esta bem acima do corte natural.
MAX_UNCOVERED_METERS = 6.0

# Piso grosseiro equivalente, usado quando o comprimento da pista nao esta a mao.
MIN_TRACK_COVERAGE = 0.995

# Buraco maximo entre amostras consecutivas. 0,5 s a 200 km/h e um vao de 28 m
# de trajetoria inventada por interpolacao.
MAX_SAMPLE_GAP_S = 0.5

# Quantos buracos acima do limite uma volta aguenta antes de ser descartada.
MAX_LONG_GAPS = 3

# Fracao maxima de amostras com o carro fora da pista.
MAX_OFF_TRACK_FRACTION = 0.05

# Velocidade abaixo da qual o carro esta parado (box, spin, reset).
STOPPED_SPEED_KMH = 5.0
MAX_STOPPED_FRACTION = 0.02


# Canais sem os quais a volta nao ensina pilotagem. Posicao e velocidade nao
# bastam: o sistema aprende o que o piloto *faz*, e isso esta nos pedais.
#
# A sessao `2026-06-14_12-23-46` gravou 12 voltas limpas -- posicao e velocidade
# perfeitas, tempo plausivel, cobertura completa -- e nenhum bloco `carPhysics`.
# Elas passavam por todos os outros gates e nove delas caiam no conjunto de
# teste, que assim media a rede contra um alvo que nao existia.
REQUIRED_CHANNELS = ("throttle", "brake", "steering", "lateral_g", "longitudinal_g")

# Fracao das amostras em que o canal precisa existir.
MIN_CHANNEL_COVERAGE = 0.90


# ------------------------------------------------------- limites do corredor ---

# Meia-bitola do carro mais folga. Interlagos tem largura minima medida de
# 5,6 m; com 1,0 m de cada lado ainda sobram 3,6 m de corredor util no ponto
# mais estreito.
CAR_HALF_WIDTH_M = 1.0

# O quanto o carro pode usar de zebra alem da borda medida. Medido: as voltas
# limpas chegam a L = -9,97 m numa pista de ~14,3 m, ou seja ~2,8 m alem da
# meia-largura nominal.
KERB_ALLOWANCE_M = 0.5


# ------------------------------------------------- envelope dinamico medido ---

# Envelope g-g observado nas voltas limpas. Serve de teto fisico no simulador
# de tempo de volta do algoritmo evolutivo.
MAX_LATERAL_G = 3.7
MAX_BRAKING_G = 3.1
MAX_ACCEL_G = 1.4


# ------------------------------------------------------------------- splits ---

# A divisao e por sessao, nao por ponto e nem por volta solta: voltas da mesma
# sessao compartilham setup, pneu, combustivel e condicao de pista, entao volta
# de treino e volta de teste na mesma sessao vazam desempenho.
VALIDATION_FRACTION = 0.15
TEST_FRACTION = 0.15
SPLIT_SEED = 20260823


@dataclass(frozen=True)
class LapQualityGates:
    """Gates aplicados a uma volta. Agrupados para poder afrouxar num
    experimento sem editar o modulo."""

    min_lap_seconds: float = MIN_LAP_SECONDS
    max_lap_seconds: float = MAX_LAP_SECONDS
    min_sample_hz: float = MIN_SAMPLE_HZ
    max_sample_hz: float = MAX_SAMPLE_HZ
    min_track_coverage: float = MIN_TRACK_COVERAGE
    max_uncovered_m: float = MAX_UNCOVERED_METERS
    min_channel_coverage: float = MIN_CHANNEL_COVERAGE
    max_sample_gap_s: float = MAX_SAMPLE_GAP_S
    max_long_gaps: int = MAX_LONG_GAPS
    max_off_track_fraction: float = MAX_OFF_TRACK_FRACTION
    max_stopped_fraction: float = MAX_STOPPED_FRACTION

    @classmethod
    def reference(cls) -> "LapQualityGates":
        """Gates mais duros, para as voltas que definem o alvo."""
        return cls(min_sample_hz=REFERENCE_MIN_SAMPLE_HZ, max_off_track_fraction=0.0)


DEFAULT_GATES = LapQualityGates()


def grid_size(track_length: float, step: Optional[float] = None) -> int:
    """Quantos pontos a grade uniforme tem para uma pista deste comprimento."""
    used = float(step or RESAMPLE_STEP_M)
    if used < MIN_RESAMPLE_STEP_M:
        raise ValueError(
            f"passo de {used} m e mais fino que a propria centerline "
            f"({MIN_RESAMPLE_STEP_M} m entre vertices)"
        )
    return int(round(float(track_length) / used))

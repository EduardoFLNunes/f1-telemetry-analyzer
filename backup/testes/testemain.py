"""
Visualizador de Telemetria de Fórmula 1 em 2D.

Este script utiliza a biblioteca `fastf1` para extrair dados reais de telemetria
(Grande Prêmio do Brasil de 2023, Qualificação) e a biblioteca `arcade` para 
renderizar um replay visual da volta mais rápida. Ele inclui a pista, a linha
ideal, a velocidade codificada por cores e um "carro fantasma" (ghost car) 
baseado nos tempos ideais de setor.
"""

import arcade
import fastf1
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
import matplotlib.cm as cm
import matplotlib.colors as colors
from scipy.signal import savgol_filter

# ==========================================
# 1. Carregar e Processar Dados FastF1
# ==========================================

# Ativa o cache para evitar o download repetido de dados pesados da API do FastF1
fastf1.Cache.enable_cache(r"data/cache")

print("Carregando telemetria...")
# Carrega a sessão de Qualificação (Q) do GP do Brasil de 2023
session = fastf1.get_session(2023, "Brazil", "Q")
session.load()

# Seleciona a volta mais rápida da sessão e extrai a telemetria incluindo a distância percorrida
fastest_lap = session.laps.pick_fastest()
telemetry = fastest_lap.get_telemetry().add_distance()

# Extração de vetores de dados (Coordenadas, Velocidade, Tempo em segundos e Distância)
X = telemetry["X"].values
Y = telemetry["Y"].values
SPEED = telemetry["Speed"].values
TIME = telemetry["Time"].dt.total_seconds().values
DISTANCE = telemetry["Distance"].values
DRIVER = fastest_lap["Driver"]

def interpolate_track(x, y, speed, time, distance, factor=3):
    """
    Aumenta a resolução dos dados da pista através de interpolação linear.
    
    Isso cria uma animação mais suave e uma linha de pista contínua no renderizador.

    Args:
        x (array): Coordenadas X originais.
        y (array): Coordenadas Y originais.
        speed (array): Velocidades originais.
        time (array): Tempos originais em segundos.
        distance (array): Distâncias percorridas originais.
        factor (int): Fator multiplicador para a quantidade de novos pontos. Padrão é 3.

    Returns:
        tuple: Arrays interpolados (x_i, y_i, s_i, time_i, dist_i).
    """
    t = np.arange(len(x))
    # Cria um novo vetor de tempo/índice com mais pontos ('factor' vezes maior)
    t_new = np.linspace(0, len(x)-1, len(x)*factor)

    # Interpolação linear de cada métrica
    x_i = np.interp(t_new, t, x)
    y_i = np.interp(t_new, t, y)
    s_i = np.interp(t_new, t, speed)
    time_i = np.interp(t_new, t, time)
    dist_i = np.interp(t_new, t, distance)

    return x_i, y_i, s_i, time_i, dist_i

# Aplica a interpolação aos dados extraídos
X, Y, SPEED, TIME, DISTANCE = interpolate_track(X, Y, SPEED, TIME, DISTANCE)

# Define o final de cada setor baseado na distância total
s1_end = DISTANCE.max() * 0.33
s2_end = DISTANCE.max() * 0.66
s3_end = DISTANCE.max()

# Normaliza a distância para um valor entre 0.0 e 1.0 (percentual da volta)
dist_norm = DISTANCE / DISTANCE.max()

# Calcula a aceleração usando a derivada da velocidade em relação ao tempo
dt = np.gradient(TIME)
dt[dt == 0] = 1e-6 # Previne divisão por zero caso haja tempos duplicados
ACC = np.gradient(SPEED) / dt
ACC_MIN, ACC_MAX = ACC.min(), ACC.max()

# ==========================================
# 2. Configuração Visual e Helpers
# ==========================================

WIDTH = 1100
HEIGHT = 900
SCALE = 0.07 # Escala de conversão das coordenadas F1 (metros) para pixels da tela

# Configuração do Colormap (escala de cores Vermelho -> Amarelo -> Verde) para velocidade
cmap = matplotlib.colormaps["RdYlGn"]
norm = colors.Normalize(vmin=SPEED.min(), vmax=SPEED.max())

# Cálculos do "Piloto Ideal" (soma dos melhores setores da sessão)
laps = session.laps
best_s1 = laps["Sector1Time"].min()
best_s2 = laps["Sector2Time"].min()
best_s3 = laps["Sector3Time"].min()

ideal_total = best_s1 + best_s2 + best_s3
ideal_total_sec = ideal_total.total_seconds()

# Cria um tempo ideal linearizado com base na distância percorrida
IDEAL_TIME = dist_norm * ideal_total_sec

# Suaviza a trajetória (X e Y) usando o filtro de Savitzky-Golay para criar a "linha ideal" visual
opt_x = savgol_filter(X, 51, 3)
opt_y = savgol_filter(Y, 51, 3)

def format_lap(time):
    """
    Formata um objeto de tempo em uma string legível (MM:SS.mmm).
    """
    total = time.total_seconds()
    minutes = int(total // 60)
    seconds = total % 60
    return f"{minutes}:{seconds:06.3f}"

def get_sector(dist):
    """
    Determina em qual setor do circuito (1, 2 ou 3) a distância atual se encontra.
    """
    if dist <= s1_end:
        return 1
    elif dist <= s2_end:
        return 2
    else:
        return 3

def speed_to_color(speed):
    """
    Converte um valor de velocidade em uma cor (RGBA) usando o colormap do Matplotlib.
    
    Returns:
        tuple: Valores (R, G, B, Alpha) variando de 0 a 255.
    """
    rgba = cmap(norm(speed))
    r = int(rgba[0] * 255)
    g = int(rgba[1] * 255)
    b = int(rgba[2] * 255)
    return (r, g, b, 255)

# ==========================================
# 3. Classe do Aplicativo Arcade (Interface Gráfica)
# ==========================================

class F1Telemetry(arcade.Window):
    """
    Classe principal da janela gráfica responsável por renderizar a pista, 
    os HUDs de telemetria e gerenciar o loop de animação do replay.
    """
    def __init__(self):
        super().__init__(WIDTH, HEIGHT, f"F1 Telemetry Replay - {DRIVER}")
        arcade.set_background_color((30, 30, 30)) # Fundo cinza escuro

        self.current_frame = 0
        self.replay_time = 0
        self.points = []

        # Variáveis da barra de velocidade visual no fundo da tela
        self.bar_w = 900
        self.bar_h = 20
        self.bar_x_start = WIDTH // 2 - self.bar_w // 2
        self.bar_y = 60

        # Encontra o centro do traçado real para centralizar na tela do Arcade
        cx, cy = (X.max() + X.min()) / 2, (Y.max() + Y.min()) / 2
        
        # Converte coordenadas geográficas para coordenadas de pixel na tela
        for i in range(len(X)):
            nx = ((X[i] - cx) * SCALE) + WIDTH / 2
            ny = ((Y[i] - cy) * SCALE) + HEIGHT / 2
            self.points.append((nx, ny))

        # Calcula os pontos da linha ideal (suavizada) da mesma maneira
        self.opt_points = []
        for i in range(len(opt_x)):
            nx = ((opt_x[i] - cx) * SCALE) + WIDTH / 2
            ny = ((opt_y[i] - cy) * SCALE) + HEIGHT / 2
            self.opt_points.append((nx, ny))

        # Criação das listas de formas (ShapeElementList) para otimizar renderização no GPU
        self.opt_line = arcade.shape_list.ShapeElementList()
        for i in range(1, len(self.opt_points)):
            p1 = self.opt_points[i-1]
            p2 = self.opt_points[i]
            color = speed_to_color(SPEED[i])
            self.opt_line.append(
                arcade.shape_list.create_line(*p1, *p2, color, 4)
            )

        # Monta a base da pista (bordas pretas, asfalto claro e linha central escura)
        self.track = arcade.shape_list.ShapeElementList()
        self.track.append(arcade.shape_list.create_line_strip(self.points, (0,0,0), 22))
        self.track.append(arcade.shape_list.create_line_strip(self.points, (230,230,230), 16))
        self.track.append(arcade.shape_list.create_line_strip(self.points, (100,100,100), 2))

        # Camadas para efeito de "neon/brilho" na linha do percurso
        self.glow_layer = arcade.shape_list.ShapeElementList()
        self.main_layer = arcade.shape_list.ShapeElementList()
        self.high_layer = arcade.shape_list.ShapeElementList()
        self.telemetry_lines = arcade.shape_list.ShapeElementList()

        # Adiciona segmentos à pista criando o efeito de iluminação baseado na velocidade
        for i in range(1, len(self.points)-5, 8):
            p1 = self.points[i]
            p2 = self.points[i+4]
            color = speed_to_color(SPEED[i])
            
            # Linha base
            self.track.append(
                arcade.shape_list.create_line(*p1, *p2, (150,150,150), 2)
            )
            
            # Camada de Brilho (Glow) - Larga e transparente
            self.glow_layer.append(
                arcade.shape_list.create_line(*p1, *p2, (*color[:3], 60), 12)
            )
            
            # Camada Principal (Cor Sólida)
            self.main_layer.append(
                arcade.shape_list.create_line(*p1, *p2, color, 6)
            )
            
            # Camada de Destaque (Highlight) - Branca e fina no centro
            self.high_layer.append(
                arcade.shape_list.create_line(*p1, *p2, (255, 255, 255, 40), 2)
            )

            line = arcade.shape_list.create_line(*p1, *p2, color, 6)
            self.telemetry_lines.append(line)

        # Constrói a barra de legenda do Colormap (gradação de cores na interface)
        self.acc_bar_list = arcade.shape_list.ShapeElementList()
        steps = 300
        for i in range(steps):
            t = i / steps
            rgba = cmap(t)
            color = (int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))
            rect = arcade.shape_list.create_rectangle_filled(
                self.bar_x_start + (i * self.bar_w / steps),
                self.bar_y,
                self.bar_w / steps + 1,
                self.bar_h,
                color,
            )
            self.acc_bar_list.append(rect)

    def on_draw(self):
        """
        Método de renderização chamado a cada frame pela biblioteca Arcade.
        """
        self.clear()

        # Renderiza a base da pista e a linha ideal
        self.track.draw()
        self.opt_line.draw()

        frame = min(self.current_frame, len(TIME)-1)
        real_time = TIME[self.current_frame]

        # Encontra a posição do "carro fantasma" (baseado no tempo linear ideal da pista)
        ghost_idx = np.searchsorted(IDEAL_TIME, real_time)
        ghost_idx = min(ghost_idx, len(self.points) - 1)

        # Desenha progressivamente as linhas de telemetria baseadas no frame atual
        if self.current_frame > 1:
            for shape in self.glow_layer[:self.current_frame]:
                shape.draw()
            for shape in self.main_layer[:self.current_frame]:
                shape.draw()
            for shape in self.high_layer[:self.current_frame]:
                shape.draw()

        # Desenha o carro principal (Piloto Real)
        #if self.current_frame < len(self.points):
            #x, y = self.points[self.current_frame]
            #arcade.draw_circle_filled(x, y, 7, (255, 255, 255))
            #arcade.draw_circle_outline(x, y, 8, (0, 0, 0), 2)
            
        #idx = self.current_frame
        
        # Calcula o delta de tempo entre o piloto real e o tempo ideal
        delta = real_time - IDEAL_TIME[self.current_frame]

        # Desenha o Carro Fantasma (Piloto Ideal em Ciano)
        gx, gy = self.points[ghost_idx]
        arcade.draw_circle_filled(gx, gy, 6, (0, 255, 255))
        arcade.draw_circle_outline(gx, gy, 7, (255, 255, 255), 2)

        # ==========================================
        # Renderização do HUD (Heads-Up Display)
        # ==========================================

        # Delta
        arcade.draw_text(
            f"DELTA: {delta:+.3f}s",
            WIDTH - 300, HEIGHT - 100, arcade.color.YELLOW, 14,
        )

        # Piloto e Velocidade no topo
        arcade.draw_text(
            #f"{DRIVER} | VEL: {SPEED[idx]:.0f} KM/H",
            20, HEIGHT - 40, arcade.color.WHITE, 16, bold=True,
        )

        # Tempo da volta decorrido
        arcade.draw_text(
           #f"TEMPO: {TIME[idx]:.3f}s | SETOR: {get_sector(DISTANCE[idx])}",
            20, HEIGHT - 70, arcade.color.LIGHT_GRAY, 12,
        )

        # Setores e Tempos
        sector = get_sector(DISTANCE[self.current_frame])
        arcade.draw_text(f"SETOR: S{sector}", 20, HEIGHT - 120, arcade.color.YELLOW, 14)
        arcade.draw_text(f"BEST S1: {best_s1}", 20, HEIGHT-160, arcade.color.PURPLE, 14)
        arcade.draw_text(f"BEST S2: {best_s2}", 20, HEIGHT-180, arcade.color.PURPLE, 14)
        arcade.draw_text(f"BEST S3: {best_s3}", 20, HEIGHT-200, arcade.color.PURPLE, 14)

        # Tempo da volta ideal calculada
        arcade.draw_text(
            f"PILO IMP: {format_lap(ideal_total)}",
            WIDTH - 300, HEIGHT - 40, arcade.color.RED, 16, bold=True
        )

        # Legenda da barra de cor (Velocidade)
        arcade.draw_text(
            "Speed [km/h] (Vermelho=Baixa | Verde=Alta)",
            WIDTH/2, self.bar_y - 55, arcade.color.WHITE, 14, anchor_x="center"
        )
        
        # Marcadores da barra de velocidade
        ticks = np.linspace(SPEED.min(), SPEED.max(), 6)
        for i, v in enumerate(ticks):
            x = self.bar_x_start + (i/(len(ticks)-1)) * self.bar_w
            arcade.draw_text(
                f"{int(v)}", x-10, self.bar_y - 30, arcade.color.WHITE, 12, anchor_x="center"
            )

        self.acc_bar_list.draw()

    def on_update(self, delta_time):
        """
        Lógica de atualização chamada a cada frame. Atualiza o tempo do replay 
        e define o quadro (frame) correto do vetor de dados a ser exibido.
        """
        self.replay_time += delta_time
        # Mapeia o tempo da tela (replay_time) para o índice mais próximo do vetor de tempo da telemetria
        self.current_frame = min(np.searchsorted(TIME, self.replay_time), len(self.points) - 1)

        # Loop: Se a volta acabar, reinicia a animação
        if self.replay_time >= TIME[-1]:
            self.replay_time = 0
            self.current_frame = 0

# ==========================================
# 4. Execução do Script
# ==========================================

if __name__ == "__main__":
    app = F1Telemetry()
    arcade.run()
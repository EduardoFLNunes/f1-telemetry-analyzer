"""
Script de Animação de Telemetria F1
Objetivo: Criar um vídeo (MP4) mostrando a volta de um piloto (Norris) com um rastro 
colorido baseado na velocidade, comparado ao traçado de referência de outro piloto (Russell).
Inclui uma visão geral da pista e uma câmera com zoom dinâmico.
"""

import fastf1
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import matplotlib.animation as animation
import matplotlib.colors as colors
from matplotlib.patches import Rectangle
from scipy.interpolate import interp1d

# =============================================================================
# PASSO 1: CARREGAMENTO DE DADOS FASTF1
# =============================================================================
# Habilita o cache para não precisar baixar da internet toda vez que rodar
fastf1.Cache.enable_cache("cache")
print("Carregando telemetria...")

# Baixa a sessão de Qualificação (Q) do GP do Brasil de 2023
session = fastf1.get_session(2023, "Brazil", "Q")
session.load()

# Seleciona a volta mais rápida de Lando Norris (Carro Principal a ser animado)
lap_opt = session.laps.pick_driver('NOR').pick_fastest()
# Seleciona a volta mais rápida de George Russell (Traçado de Referência)
lap_ref = session.laps.pick_driver('RUS').pick_fastest()

# Extrai os dados de telemetria (X, Y, Velocidade, Tempo) adicionando a coluna de Distância
tel_opt = lap_opt.get_telemetry().add_distance()
tel_ref = lap_ref.get_telemetry().add_distance()

# Guarda os arrays originais do carro principal (Norris)
X_orig = tel_opt['X'].values
Y_orig = tel_opt['Y'].values
SPEED_orig = tel_opt['Speed'].values
TIME_orig = tel_opt['Time'].dt.total_seconds().values

# Guarda os arrays originais do carro de referência (Russell)
X_ref_orig = tel_ref['X'].values
Y_ref_orig = tel_ref['Y'].values
DIST_ref_orig = tel_ref['Distance'].values

# =============================================================================
# PASSO 2: INTERPOLAÇÃO (SUAVIZAÇÃO) PARA 60 FPS
# A telemetria real da F1 é gravada em ~10Hz a ~20Hz (10 a 20 pontos por seg).
# Para um vídeo fluido a 60 FPS, precisamos criar pontos intermediários (interpolar).
# =============================================================================
print("Suavizando traçados...")

# Remove tempos duplicados (necessário para a função de interpolação matemática funcionar)
_, idx_opt = np.unique(TIME_orig, return_index=True)
TIME_orig_u = TIME_orig[idx_opt]
X_orig_u = X_orig[idx_opt]
Y_orig_u = Y_orig[idx_opt]
SPEED_orig_u = SPEED_orig[idx_opt]
DIST_orig_u = tel_opt['Distance'].values[idx_opt]

# Define a duração total da volta animada e cria um eixo de tempo perfeito a 60 FPS
# np.linspace cria pontos igualmente espaçados do tempo 0 até o final da volta
total_time_opt = TIME_orig_u[-1] - TIME_orig_u[0]
TIME = np.linspace(TIME_orig_u[0], TIME_orig_u[-1], int(total_time_opt * 60))

# Cria funções matemáticas (interp1d) que adivinham o valor de X, Y e Velocidade 
# para qualquer fração de segundo
f_x = interp1d(TIME_orig_u, X_orig_u, kind='cubic')
f_y = interp1d(TIME_orig_u, Y_orig_u, kind='cubic')
f_speed = interp1d(TIME_orig_u, SPEED_orig_u, kind='linear')
f_dist = interp1d(TIME_orig_u, DIST_orig_u, kind='linear')

# Aplica as funções para gerar os dados do carro em alta resolução (60 FPS)
X = f_x(TIME)
Y = f_y(TIME)
SPEED = f_speed(TIME)
DIST_OPT = f_dist(TIME)

# Suaviza a linha do carro de referência. Como ele correu em outro tempo, 
# sincronizamos pela DISTÂNCIA (garante que X e Y de referência fiquem no lugar certo)
_, idx_ref = np.unique(DIST_ref_orig, return_index=True)
f_x_ref = interp1d(DIST_ref_orig[idx_ref], X_ref_orig[idx_ref], kind='cubic', fill_value='extrapolate')
f_y_ref = interp1d(DIST_ref_orig[idx_ref], Y_ref_orig[idx_ref], kind='cubic', fill_value='extrapolate')

X_ref = f_x_ref(DIST_OPT)
Y_ref = f_y_ref(DIST_OPT)

# =============================================================================
# PASSO 3: CONFIGURAÇÃO VISUAL (MATPLOTLIB)
# Configuração da janela, dos eixos e do estilo escuro
# =============================================================================
plt.style.use('dark_background')
# Cria uma figura grande dividida em 1 linha e 2 colunas
fig, (ax_full, ax_zoom) = plt.subplots(1, 2, figsize=(20, 10))

# Ajusta as margens e a cor de fundo para cinza bem escuro
fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01, wspace=0.05)
fig.patch.set_facecolor('#111111')
ax_full.set_facecolor('#111111')
ax_zoom.set_facecolor('#111111')

# Tira os eixos X e Y (não queremos ver os números das coordenadas)
ax_full.axis('off')
ax_zoom.axis('off')

# Desenha a linha fantasma (carro de referência) nos dois gráficos
ax_full.plot(X_ref_orig, Y_ref_orig, color='#444444', linewidth=2, linestyle='--', zorder=1)
ax_zoom.plot(X_ref_orig, Y_ref_orig, color='#444444', linewidth=3, linestyle='--', zorder=1)

# Trava os limites do mapa completo para englobar toda a pista
ax_full.set_xlim(min(X) - 500, max(X) + 500)
ax_full.set_ylim(min(Y) - 500, max(Y) + 500)

# =============================================================================
# PASSO 4: PREPARAÇÃO DOS ELEMENTOS ANIMADOS (RASTRO E CARRINHO)
# =============================================================================
# Criação das 'LineCollections' - um tipo especial de linha no Matplotlib
# que permite que cada segmento da linha tenha uma cor diferente (baseada no mapa de cor magma)
cmap = plt.get_cmap('magma')
norm = colors.Normalize(vmin=SPEED.min(), vmax=SPEED.max())

# Rastro para o mapa completo
lc_full = LineCollection([], cmap=cmap, norm=norm, linewidth=4, zorder=2)
ax_full.add_collection(lc_full)

# Rastro para o mapa com zoom
lc_zoom = LineCollection([], cmap=cmap, norm=norm, linewidth=6, zorder=2)
ax_zoom.add_collection(lc_zoom)

# Criação do 'Carrinho' (Um retângulo)
car_width, car_length = 200, 400
# Desenha o carrinho na tela cheia e no zoom
rect_full = Rectangle((X[0], Y[0]), car_length, car_width, color='cyan', zorder=3)
rect_zoom = Rectangle((X[0], Y[0]), car_length, car_width, color='cyan', zorder=3)
ax_full.add_patch(rect_full)
ax_zoom.add_patch(rect_zoom)

# Textos informativos na tela
time_text = ax_full.text(0.02, 0.95, '', transform=ax_full.transAxes, fontsize=24, color='white')
speed_text = ax_zoom.text(0.05, 0.05, '', transform=ax_zoom.transAxes, fontsize=32, color='cyan', weight='bold')

# Variáveis de controle para a câmera do Zoom
zoom_radius = 800
camera_center = [X[0], Y[0]]
threshold = 200 # A câmera só move se o carro sair dessa distância do centro

# =============================================================================
# PASSO 5: FUNÇÃO DE ATUALIZAÇÃO DA ANIMAÇÃO (Roda a cada Frame)
# =============================================================================
def update(frame):
    # Pega as posições atuais até o frame em que estamos
    current_x = X[:frame+1]
    current_y = Y[:frame+1]
    current_speed = SPEED[:frame+1]
    
    car_x = X[frame]
    car_y = Y[frame]
    
    # 5.1 CÁLCULO DA ROTAÇÃO DO CARRO
    # Calcula a direção apontada pelo carro comparando o frame atual com o anterior
    if frame > 0:
        dx = X[frame] - X[frame-1]
        dy = Y[frame] - Y[frame-1]
        car_angle = np.degrees(np.arctan2(dy, dx))
    else:
        car_angle = 0
        
    # Ajusta o eixo de rotação do retângulo para que ele gire pelo centro
    # e não pelo canto inferior esquerdo
    angle_rad = np.radians(car_angle)
    cx, cy = car_length / 2, car_width / 2
    rx = car_x - (cx * np.cos(angle_rad) - cy * np.sin(angle_rad))
    ry = car_y - (cx * np.sin(angle_rad) + cy * np.cos(angle_rad))
    
    # Aplica posição e rotação nos retângulos
    rect_full.set_xy((rx, ry))
    rect_full.angle = car_angle
    rect_zoom.set_xy((rx, ry))
    rect_zoom.angle = car_angle
    
    # 5.2 ATUALIZA O RASTRO COLORIDO ATRÁS DO CARRO
    if frame > 0:
        # Pega a lista de pontos e transforma em segmentos de linha (Ponto A -> Ponto B)
        points = np.array([current_x, current_y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        
        # O rastro recebe a geometria e as cores (velocidade)
        lc_full.set_segments(segments)
        lc_full.set_array(current_speed)
        lc_zoom.set_segments(segments)
        lc_zoom.set_array(current_speed)
    
    # 5.3 LÓGICA DA CÂMERA (MAPA DE ZOOM)
    # Verifica se o carro andou o suficiente (threshold) para mover a câmera
    dist_x = abs(car_x - camera_center[0])
    dist_y = abs(car_y - camera_center[1])
    
    if dist_x > threshold or dist_y > threshold:
        camera_center[0] = car_x
        camera_center[1] = car_y
        
    # Centraliza o eixo de zoom baseado na câmera
    ax_zoom.set_xlim(camera_center[0] - zoom_radius, camera_center[0] + zoom_radius)
    ax_zoom.set_ylim(camera_center[1] - zoom_radius, camera_center[1] + zoom_radius)
    
    # 5.4 ATUALIZA OS TEXTOS NA TELA
    total_sec = TIME[frame]
    mins = int(total_sec // 60)
    secs = total_sec % 60
    time_text.set_text(f'L. Norris - Tempo: {mins}:{secs:05.2f}')
    speed_text.set_text(f'{int(SPEED[frame])} km/h')
    
    return lc_full, lc_zoom, rect_full, rect_zoom, time_text, speed_text

# =============================================================================
# PASSO 6: EXECUÇÃO DA ANIMAÇÃO E GERAÇÃO DO VÍDEO MP4
# =============================================================================
print(f"Gerando animação ({len(TIME)} frames)... Isso pode demorar.")

# Cria a animação passando a Figura, a função de update e a quantidade de frames
ani = animation.FuncAnimation(fig, update, frames=len(TIME), interval=1000/60, blit=True)

# Define o gerador de vídeo (Requer o FFmpeg instalado no seu sistema)
writer = animation.FFMpegWriter(fps=60, metadata=dict(artist='TelemetryBot'), bitrate=1800)

# Salva o arquivo (essa linha pode demorar vários minutos para processar)
ani.save('telemetry_lap_smooth.mp4', writer=writer)

print("Vídeo 'telemetry_lap_smooth.mp4' gerado com sucesso!")
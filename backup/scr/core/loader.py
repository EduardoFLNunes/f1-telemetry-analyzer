import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import os
import glob

from pistas import desenhar_pista

# Opções: 'melhor', 'todas', ou o número da volta (ex: 3)
visualizacao = 'melhor'

# ==========================================================
# 1. CARREGAR OS DADOS (ARQUIVO MAIS RECENTE)
# ==========================================================
arquivos_csv = glob.glob(r'scr\providers\f1-25\*.csv')

if not arquivos_csv:
    raise FileNotFoundError("Nenhum ficheiro CSV foi encontrado na pasta atual.")

arquivo_mais_recente = max(arquivos_csv, key=os.path.getmtime)
print(f"A ler os dados do ficheiro: {arquivo_mais_recente}")

df = pd.read_csv(arquivo_mais_recente)

# ==========================================================
# 2. CÁLCULOS E RESUMO DA SESSÃO
# ==========================================================
voltas = df['lap'].unique()
tempo_volta = {}
melhor_tempo = float('inf')
volta_mais_rapida = None
quantidade_voltas = len(voltas)

for volta in voltas:
    df_v = df[df['lap'] == volta]
    tempo_total = df_v['session_time'].max() - df_v['session_time'].min()
    tempo_volta[volta] = tempo_total

    if tempo_total < melhor_tempo:
        melhor_tempo = tempo_total
        volta_mais_rapida = volta

# Construção do texto de resumo
texto_resumo = f"RESUMO DA SESSÃO\n\nTotal de Voltas: {quantidade_voltas}\n\n"
texto_resumo += f"⭐ Melhor volta: {volta_mais_rapida}\n"
texto_resumo += f"Tempo: {int(melhor_tempo//60):02d}:{melhor_tempo%60:06.3f}\n\n"
texto_resumo += "Tempos por Volta:\n"

for volta, tempo in tempo_volta.items():
    minutos = int(tempo // 60)
    segundos = tempo % 60
    texto_resumo += f"Volta {volta}: {minutos:02d}:{segundos:06.3f} {' (BEST)' if volta == volta_mais_rapida else ''}\n"

# ==========================================================
# 3. FILTRAGEM PARA EXIBIÇÃO
# ==========================================================
if visualizacao == 'melhor':
    df_plot = df[df['lap'] == volta_mais_rapida].copy()
    titulo_mapa = f'Mapa da Pista - Melhor Volta (Volta {volta_mais_rapida})'
elif isinstance(visualizacao, int):
    df_plot = df[df['lap'] == visualizacao].copy()
    titulo_mapa = f'Mapa da Pista - Volta {visualizacao}'
else:
    df_plot = df.copy()
    titulo_mapa = 'Mapa da Pista - Todas as Voltas'

# ==========================================================
# 4. CÁLCULO DA DISTÂNCIA
# ==========================================================
df_plot['delta_time'] = df_plot['session_time'].diff().fillna(0)
df_plot['speed_ms'] = df_plot['speed'] / 3.6
df_plot['delta_dist'] = df_plot['speed_ms'] * df_plot['delta_time']
df_plot['lap_distance'] = df_plot.groupby('lap')['delta_dist'].cumsum()

# ==========================================================
# 5. CONFIGURAR A FIGURA E PLOTAGEM
# ==========================================================
fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 14), gridspec_kw={'height_ratios': [2, 1, 1, 1]})

# Desenha a pista de fundo e obtém o centro
centro_x_pista, centro_z_pista = desenhar_pista(r'data/raw/SaoPaulo.csv', ax1)

# Ajuste dinâmico de coordenadas centrado nas voltas plotadas
centro_x_telemetria = df_plot['pos_x'].mean()
centro_z_telemetria = (-df_plot['pos_z']).mean()
ajuste_x = (centro_x_pista - centro_x_telemetria) - 13
ajuste_z = (centro_z_pista - centro_z_telemetria) + 18

color_speed, color_throttle, color_brake = '#1f77b4', '#2ca02c', '#d62728'

# Plota a telemetria e o traçado
for volta in df_plot['lap'].unique():
    df_v = df_plot[df_plot['lap'] == volta]
    
    ax1.plot(df_v['pos_x'] + ajuste_x, -df_v['pos_z'] + ajuste_z, color='black', linewidth=1.5, label=f'Volta {volta}')
    
    ax2.plot(df_v['lap_distance'], df_v['speed'], color=color_speed, linewidth=1.5, alpha=0.7)
    ax3.plot(df_v['lap_distance'], df_v['throttle'] * 100, color=color_throttle, linewidth=1.5, alpha=0.7)
    ax4.plot(df_v['lap_distance'], df_v['brake'] * 100, color=color_brake, linewidth=1.5, alpha=0.7)

# --- Configurações Visuais ---
ax1.set_title(titulo_mapa, fontsize=14, fontweight='bold')
ax1.invert_xaxis()
ax1.axis('equal')
ax1.grid(True, linestyle='--', alpha=0.6)
ax1.legend(loc='upper right')
ax1.text(1.05, 0.5, texto_resumo, transform=ax1.transAxes, fontsize=11, verticalalignment='center', 
         bbox=dict(boxstyle='round,pad=0.8', facecolor='#f8f9fa', edgecolor='#ced4da', alpha=0.9))

ax2.set_ylabel('Velocidade (km/h)', color=color_speed, fontweight='bold')
ax3.set_ylabel('Acelerador %', color=color_throttle, fontweight='bold')
ax4.set_ylabel('Freio %', color=color_brake, fontweight='bold')
ax4.set_xlabel('Distância da Volta (metros)', fontweight='bold')

for ax in [ax2, ax3, ax4]:
    ax.grid(True, linestyle='--', alpha=0.5)

plt.tight_layout()
plt.subplots_adjust(right=0.80) 
plt.show()
"""
Módulo de Visualização de Telemetria (Estilo RaceStudio)
Este script cria um painel interativo (Dashboard) usando Dash e Plotly
para comparar duas voltas de telemetria (Referência vs Atual) sincronizadas
pela distância percorrida na pista.
"""

# --- Importações de Bibliotecas ---
import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import math

# --- 1. Geração de Dados Simulação (Mock) ---
def gerar_telemetria_mock(distancia_total=4309, pontos=500, offset_lat=0, offset_lon=0, variacao=1.0):
    """
    Gera dados simulados de telemetria para o circuito de Interlagos.
    
    Parâmetros:
    - distancia_total (int): Comprimento total da pista em metros (padrão Interlagos: 4309m).
    - pontos (int): Quantidade de pontos de dados a serem gerados.
    - offset_lat/lon (float): Deslocamento geográfico para simular trajetórias diferentes.
    - variacao (float): Multiplicador para alterar o comportamento do carro (mais rápido/lento).
    
    Retorna:
    - pd.DataFrame: DataFrame contendo Distância, Lat, Lon, Speed, Throttle, Brake e Steering.
    """
    # Coordenadas aproximadas do centro de Interlagos
    lat_centro, lon_centro = -23.703, -46.696 
    
    # Cria um array de distâncias de 0 até o total da pista
    distancias = np.linspace(0, distancia_total, pontos)
    dados = []
    
    for d in distancias:
        # Simula um traçado circular em volta do centro geográfico
        angulo = (d / distancia_total) * 2 * math.pi
        lat = lat_centro + (0.004 * math.sin(angulo)) + offset_lat
        lon = lon_centro + (0.005 * math.cos(angulo)) + offset_lon
        
        # Simulação física baseada na posição (usando funções trigonométricas para criar curvas suaves)
        speed = 100 + 80 * math.sin(angulo * 4) * variacao
        throttle = 100 if speed > 120 else max(0, speed - 50)
        brake = 100 if speed < 120 and speed > 100 else 0
        steering = 45 * math.cos(angulo * 6) * variacao
        
        # Adiciona a linha de dados na lista
        dados.append([d, lat, lon, speed, throttle, brake, steering])
        
    # Converte a lista em um DataFrame do Pandas para facilitar a manipulação
    return pd.DataFrame(dados, columns=['Distance', 'Lat', 'Lon', 'Speed', 'Throttle', 'Brake', 'Steering'])

# Inicializa os dados das duas voltas para comparação
# A volta atual tem um leve desvio (offset) para mostrar que as linhas não se sobrepõem perfeitamente
df_best = gerar_telemetria_mock(variacao=1.05)
df_current = gerar_telemetria_mock(offset_lat=0.0001, offset_lon=0.0001, variacao=0.95)

# --- 2. Configuração do Servidor e Layout do App Dash ---
# Inicializa o aplicativo web
app = dash.Dash(__name__)

# Define a estrutura visual da página (HTML e CSS inseridos no Python)
app.layout = html.Div([
    # Título principal do Dashboard
    html.H2("Análise de Telemetria - Autódromo José Carlos Pace (Interlagos)", 
            style={'textAlign': 'center', 'color': 'white', 'fontFamily': 'Arial'}),
    
    # Barra superior de controle (Slider de Distância)
    html.Div([
        html.Label("Sincronização por Distância (m):", style={'color': 'white'}),
        dcc.Slider(
            id='distance-slider',       # ID usado para conectar ao Callback
            min=0,                      # Início da volta
            max=4300,                   # Fim da volta
            step=10,                    # Pulos de 10 em 10 metros
            value=0,                    # Posição inicial do cursor
            marks={i: f'{i}m' for i in range(0, 4301, 500)} # Rótulos a cada 500m
        )
    ], style={'padding': '20px', 'backgroundColor': '#333'}),

    # Container principal dividido em duas colunas (Mapa 40% | Gráficos 60%)
    html.Div([
        # Coluna da Esquerda: Mapa da Pista
        html.Div([dcc.Graph(id='track-map')], style={'width': '40%', 'display': 'inline-block', 'verticalAlign': 'top'}),
        
        # Coluna da Direita: Gráficos de Telemetria
        html.Div([dcc.Graph(id='telemetry-graphs')], style={'width': '60%', 'display': 'inline-block', 'verticalAlign': 'top'})
    ])
], style={'backgroundColor': '#1e1e1e', 'padding': '10px'}) # Fundo escuro geral

# --- 3. Lógica Interativa (Callbacks) ---
@app.callback(
    # Quais componentes visuais serão atualizados
    [Output('track-map', 'figure'),
     Output('telemetry-graphs', 'figure')],
    # Qual componente irá disparar a atualização (o valor do Slider)
    [Input('distance-slider', 'value')]
)
def update_dashboard(current_distance):
    """
    Função chamada automaticamente toda vez que o usuário move o slider.
    Ela recalcula a posição do carro no mapa e a linha vertical nos gráficos.
    """
    
    # Encontra as linhas no DataFrame cuja distância seja mais próxima do valor atual do slider
    idx_best = (df_best['Distance'] - current_distance).abs().idxmin()
    idx_current = (df_current['Distance'] - current_distance).abs().idxmin()

    # --- 3.1 Construção do MAPA DA PISTA ---
    fig_map = go.Figure()

    # Traça a linha completa da Volta de Referência (Vermelha)
    fig_map.add_trace(go.Scattermapbox(
        lat=df_best['Lat'], lon=df_best['Lon'],
        mode='lines', line=dict(width=2, color='red'), name='Best Lap'
    ))
    
    # Traça a linha completa da Volta Atual (Azul/Ciano)
    fig_map.add_trace(go.Scattermapbox(
        lat=df_current['Lat'], lon=df_current['Lon'],
        mode='lines', line=dict(width=2, color='cyan'), name='Current Lap'
    ))

    # Desenha os "pontos" representando os carros na posição exata da distância selecionada
    fig_map.add_trace(go.Scattermapbox(
        lat=[df_best['Lat'].iloc[idx_best], df_current['Lat'].iloc[idx_current]],
        lon=[df_best['Lon'].iloc[idx_best], df_current['Lon'].iloc[idx_current]],
        mode='markers',
        marker=dict(size=12, color=['red', 'cyan']),
        name='Posição Atual'
    ))

    # Configurações de estilo do mapa (Zoom, Centro, Estilo de fundo)
    fig_map.update_layout(
        mapbox=dict(
            style="open-street-map", # Altere para "satellite" e adicione mapbox_token se quiser imagem real
            center=dict(lat=-23.701, lon=-46.697),
            zoom=14
        ),
        margin=dict(l=0, r=0, t=0, b=0), # Remove bordas extras
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)", font=dict(color="white"))
    )

    # --- 3.2 Construção dos GRÁFICOS DE TELEMETRIA ---
    # Cria uma grade de gráficos empilhados (4 linhas, 1 coluna), compartilhando o eixo X (Distância)
    fig_graphs = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                               vertical_spacing=0.05, 
                               subplot_titles=("Speed (km/h)", "Throttle (%)", "Brake (%)", "Steering (deg)"))

    # Lista das colunas do DataFrame que queremos plotar
    metrics = ['Speed', 'Throttle', 'Brake', 'Steering']
    colors = {'Best Lap': 'red', 'Current Lap': 'cyan'}
    dataframes = {'Best Lap': df_best, 'Current Lap': df_current}

    # Loop para adicionar as linhas de dados em cada um dos 4 gráficos
    for i, metric in enumerate(metrics):
        for name, df in dataframes.items():
            fig_graphs.add_trace(go.Scatter(
                x=df['Distance'], y=df[metric], mode='lines', 
                line=dict(color=colors[name], width=1.5), name=name,
                showlegend=(i==0) # Mostra a legenda apenas no primeiro gráfico para economizar espaço
            ), row=i+1, col=1)

        # Adiciona a linha amarela vertical para sincronizar com a posição no mapa
        fig_graphs.add_vline(x=current_distance, line_width=2, line_dash="dash", line_color="yellow", row=i+1, col=1)

    # Estilização geral dos gráficos (Cores escuras, altura total)
    fig_graphs.update_layout(
        height=800,
        plot_bgcolor='#2d2d2d',
        paper_bgcolor='#1e1e1e',
        font=dict(color='white'),
        margin=dict(l=40, r=20, t=40, b=40)
    )
    
    # Oculta linhas de grade desnecessárias para manter o visual limpo
    fig_graphs.update_xaxes(showgrid=False)
    fig_graphs.update_yaxes(showgrid=True, gridcolor='#444')

    # Retorna os dois objetos visuais atualizados para o layout
    return fig_map, fig_graphs

# --- 4. Inicialização da Aplicação ---
# Garante que o servidor só rode se este arquivo for executado diretamente
if __name__ == '__main__':
    # Usando app.run em vez do obsoleto app.run_server
    app.run(debug=True)
import pandas as pd
import numpy as np
import plotly.graph_objects as go

def desenhar_pista_alinhada(caminho_csv, x_scale=1.0, y_scale=1.0, x_offset=0.0, y_offset=0.0):
    """
    Desenha a pista de Interlagos com asfalto preenchido, alinhada com a telemetria.
    Retorna uma figura Plotly.
    """
    # 1. Carregar os dados
    pista_interlagos = pd.read_csv(caminho_csv)
    pista_interlagos.columns = pista_interlagos.columns.str.strip()

    # Extraindo os dados em bruto (coordenadas locais do CSV)
    x_raw = pista_interlagos['# x_m'].values
    y_raw = pista_interlagos['y_m'].values
    w_right = pista_interlagos['w_tr_right_m'].values
    w_left = pista_interlagos['w_tr_left_m'].values

    # 2. Calcular a geometria em bruto (bordas)
    dx = np.gradient(x_raw)
    dy = np.gradient(y_raw)
    norm = np.hypot(dx, dy)
    norm[norm == 0] = 1 
    nx = -dy / norm  
    ny = dx / norm   

    x_left_raw = x_raw + nx * w_left
    y_left_raw = y_raw + ny * w_left
    x_right_raw = x_raw - nx * w_right
    y_right_raw = y_raw - ny * w_right
    
    # 3. APLICAR A TRANSFORMAÇÃO DE ALINHAMENTO
    x_left = (x_left_raw * x_scale) + x_offset
    y_left = (y_left_raw * y_scale) + y_offset
    x_right = (x_right_raw * x_scale) + x_offset
    y_right = (y_right_raw * y_scale) + y_offset
    x_center = (x_raw * x_scale) + x_offset
    y_center = (y_raw * y_scale) + y_offset

    # 4. Criar a figura base no Plotly
    fig = go.Figure()

    # Criação do polígono fechado para o asfalto (preenchimento)
    # Concatenamos a borda esquerda com a borda direita invertida
    x_asfalto = np.concatenate([x_left, x_right[::-1], [x_left[0]]])
    y_asfalto = np.concatenate([y_left, y_right[::-1], [y_left[0]]])

    fig.add_trace(go.Scatter(
        x=x_asfalto, y=y_asfalto,
        fill='toself', # Preenche o espaço interno do polígono
        fillcolor='rgba(100, 100, 100, 0.6)', # Cinza asfalto semi-transparente
        line=dict(color='rgba(255,255,255,0)'), # Sem borda no preenchimento
        name='Asfalto (Proporção Real)',
        hoverinfo='skip',
        legendgroup='base'
    ))

    # Desenha as linhas principais (Limites e Centro) por cima do asfalto
    fig.add_trace(go.Scatter(x=x_center, y=y_center, mode='lines', line=dict(color='yellow', width=1, dash='dash'), name='Centro', legendgroup='base'))
    fig.add_trace(go.Scatter(x=x_left, y=y_left, mode='lines', line=dict(color='white', width=2), name='Limite Esq.', legendgroup='base'))
    fig.add_trace(go.Scatter(x=x_right, y=y_right, mode='lines', line=dict(color='white', width=2), name='Limite Dir.', legendgroup='base'))

    return fig
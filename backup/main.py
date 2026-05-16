import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import fastf1
import math

# =============================================================================
# 1. CARREGAMENTO DE DADOS FASTF1
# =============================================================================
fastf1.Cache.enable_cache(r"data/cache")

def obter_telemetria_fastf1(ano, gp, tipo_sessao='Q', piloto='NOR'):
    print(f"Baixando telemetria: {ano} {gp} ({tipo_sessao}) - Piloto {piloto}...")
    sessao = fastf1.get_session(ano, gp, tipo_sessao)
    sessao.load(telemetry=True, weather=False, messages=False)
    volta = sessao.laps.pick_driver(piloto).pick_fastest()
    tel = volta.get_telemetry().add_distance()
    return tel

# =============================================================================
# 2. CONVERSÃO MATEMÁTICA: METROS (X,Y) PARA GPS (LAT, LON)
# =============================================================================
def converter_xy_para_latlon(df_tel, lat_centro, lon_cent ro, rotacao_graus=0):
    METROS_POR_GRAU = 111320.0
    x = df_tel['X'].values
    y = df_tel['Y'].values
    
    centro_x = (np.max(x) + np.min(x)) / 2
    centro_y = (np.max(y) + np.min(y)) / 2
    
    x_rel = x - centro_x
    y_rel = y - centro_y
    
    theta = math.radians(rotacao_graus)
    x_rot = x_rel * math.cos(theta) - y_rel * math.sin(theta)
    y_rot = x_rel * math.sin(theta) + y_rel * math.cos(theta)
    
    df_tel['Lat'] = lat_centro + (y_rot / METROS_POR_GRAU)
    df_tel['Lon'] = lon_centro + (x_rot / (METROS_POR_GRAU * math.cos(math.radians(lat_centro))))
    return df_tel

# =============================================================================
# 3. SETUP DOS DADOS 
# =============================================================================
LAT_INTERLAGOS = -23.7029
LON_INTERLAGOS = -46.6973
ROTACAO_AJUSTE = -14 

df_volta = obter_telemetria_fastf1(2023, 'Brazil', 'Q', 'NOR')
df_volta = converter_xy_para_latlon(df_volta, LAT_INTERLAGOS, LON_INTERLAGOS, ROTACAO_AJUSTE)
df_volta = df_volta.dropna(subset=['Distance', 'Lat', 'Lon', 'Speed', 'Throttle', 'Brake'])
max_dist = int(df_volta['Distance'].max())

# =============================================================================
# 4. DASHBOARD (O MAPA SATÉLITE REAL)
# =============================================================================
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("Dashboard Telemetria - Interlagos (Satélite Real)", style={'color': 'white', 'textAlign': 'center', 'fontFamily': 'Arial'}),
    
    html.Div([
        dcc.Slider(id='dist-slider', min=0, max=max_dist, step=10, value=0, marks={i: f'{i}m' for i in range(0, max_dist+1, 500)})
    ], style={'padding': '20px', 'backgroundColor': '#222', 'borderRadius': '10px', 'marginBottom': '20px'}),
    
    html.Div([
        html.Div([dcc.Graph(id='mapa-satelite', style={'height': '800px'})], style={'width': '45%', 'display': 'inline-block', 'verticalAlign': 'top'}),
        html.Div([dcc.Graph(id='graficos', style={'height': '800px'})], style={'width': '55%', 'display': 'inline-block', 'verticalAlign': 'top'})
    ])
], style={'backgroundColor': '#111', 'padding': '20px', 'minHeight': '100vh'})

@app.callback(
    [Output('mapa-satelite', 'figure'), Output('graficos', 'figure')],
    [Input('dist-slider', 'value')]
)
def update(distancia):
    idx = (df_volta['Distance'] - distancia).abs().idxmin()

    # --- MAPA SATÉLITE ---
    fig_map = go.Figure()
    
    fig_map.add_trace(go.Scattermapbox(
        lat=df_volta['Lat'], lon=df_volta['Lon'], 
        mode='lines', line=dict(width=4, color='cyan')
    ))
    
    # A correção está aqui: trocado iloc por loc
    fig_map.add_trace(go.Scattermapbox(
        lat=[df_volta['Lat'].loc[idx]], lon=[df_volta['Lon'].loc[idx]], 
        mode='markers', marker=dict(size=10, color='red')
    ))

    fig_map.update_layout(
        mapbox=dict(
            style="open-street-map", # Altere para "satellite" e adicione mapbox_token se quiser imagem real
            center=dict(
                lat=df_volta['Lat'].mean(),
                lon=df_volta['Lon'].mean()
            ),
            zoom=15.8
        ),
        margin=dict(l=0, r=0, t=0, b=0), # Remove bordas extras
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)", font=dict(color="white"))
    )

    # --- GRÁFICOS ---
    fig_graphs = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=("Velocidade (km/h)", "Acelerador (%)", "Freio (%)"))
    for i, col in enumerate(['Speed', 'Throttle', 'Brake']):
        fig_graphs.add_trace(go.Scatter(x=df_volta['Distance'], y=df_volta[col], line=dict(color='cyan')), row=i+1, col=1)
        fig_graphs.add_vline(x=distancia, line_width=2, line_dash="dash", line_color="yellow", row=i+1, col=1)

    fig_graphs.update_layout(plot_bgcolor='#222', paper_bgcolor='#111', font=dict(color='white'), margin=dict(l=30, r=10, t=30, b=10), showlegend=False)

    return fig_map, fig_graphs

if __name__ == '__main__':
    app.run(debug=True)
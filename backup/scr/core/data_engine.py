import pandas as pd
import numpy as np
import os
import glob
from pistas import obter_coordenadas_pista 

def obter_dados_telemetria():
    arquivos_csv = glob.glob(r'scr\providers\f1-25\*.csv')
    if not arquivos_csv:
        return None
    
    arquivo = max(arquivos_csv, key=os.path.getmtime)
    df = pd.read_csv(arquivo)

    voltas = df['lap'].unique()
    melhor_tempo = float('inf')
    volta_mais_rapida = None
    
    for volta in voltas:
        df_v = df[df['lap'] == volta]
        tempo = df_v['session_time'].max() - df_v['session_time'].min()
        if tempo < melhor_tempo:
            melhor_tempo = tempo
            volta_mais_rapida = volta

    df_best = df[df['lap'] == volta_mais_rapida]

    # Chama a função da pista que acabamos de colocar no pistas.py
    dados_pista = obter_coordenadas_pista(r'data/raw/SaoPaulo.csv')
# === ADICIONE ESTAS 3 LINHAS ANTES DO RETURN ===
    minutos = int(melhor_tempo // 60)
    segundos = melhor_tempo % 60
    tempo_str = f"{minutos:02d}:{segundos:06.3f}"

    # Empacota TUDO para o dashboard
    return {
        "resumo": {
            "voltas": len(voltas),
            "melhor_volta": int(volta_mais_rapida),
            "tempo": melhor_tempo,
            "tempo_formatado": tempo_str  # <--- ADICIONE ESTA LINHA AQUI
        },
        "melhor": {
            "x": df_best['pos_x'].tolist(),
            "z": df_best['pos_z'].tolist(),
            "velocidade": df_best['speed'].tolist(),
            "freio": (df_best['brake'] * 100).tolist(),
            "acelerador": (df_best['throttle'] * 100).tolist()
        },
        "pista": dados_pista 
    }
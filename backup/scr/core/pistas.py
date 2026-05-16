import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def desenhar_pista(pista_interlagos, eixo_recebido):
    # 1. Carregar os dados
    pista_interlagos = pd.read_csv(r'data/raw/SaoPaulo.csv')
    pista_interlagos.columns = pista_interlagos.columns.str.strip()  # Limpar possíveis espaços nos nomes das colunas

    # Extraindo os dados
    x = pista_interlagos['# x_m'].values
    y = pista_interlagos['y_m'].values
    w_right = pista_interlagos['w_tr_right_m'].values
    w_left = pista_interlagos['w_tr_left_m'].values

    # 2. Calcular a geometria para desenhar as bordas da pista
    # Primeiro, pegamos a direção da linha central (dx, dy)
    dx = np.gradient(x)
    dy = np.gradient(y)

    # Em seguida, calculamos o vetor perpendicular (normal) apontando para os lados
    norm = np.hypot(dx, dy)
    norm[norm == 0] = 1  # Evitar divisão por zero

    nx = -dy / norm  # Componente X do vetor perpendicular (aponta para a esquerda)
    ny = dx / norm   # Componente Y do vetor perpendicular

    # 3. Calcular as coordenadas exatas dos limites da pista (Bordas)
    fator_largura = 2.0  # <--- Altere este número. 1.0 é o original. 2.0 dobra a largura.
    
    # Borda Esquerda = Linha Central + (Vetor Perpendicular * Largura Esquerda * Fator)
    x_left = x + nx * (w_left * fator_largura)
    y_left = y + ny * (w_left * fator_largura)

    # Borda Direita = Linha Central - (Vetor Perpendicular * Largura Direita * Fator)
    x_right = x - nx * (w_right * fator_largura)
    y_right = y - ny * (w_right * fator_largura)
    #eixo_recebido.figure(figsize=(20, 10))

    # Preenche o espaço entre a borda direita e esquerda simulando o asfalto
    eixo_recebido.fill(np.concatenate([x_left, x_right[::-1]]), 
            np.concatenate([y_left, y_right[::-1]]), 
            color='gray', alpha=0.4, label='Asfalto (Proporção da Pista)')
    # Desenha as linhas principais
    # Desenha as linhas principais
    eixo_recebido.invert_yaxis()  # Espelha o mapa horizontalmente para alinhar com a visão tradicional
    eixo_recebido.plot(x, y, linestyle='--', color='yellow', linewidth=1, label='Linha de Referência (Centro)')

    eixo_recebido.plot(x_left, y_left, color='black', linewidth=1.5, label='Limite Esquerdo')

    eixo_recebido.plot(x_right, y_right, color='black', linewidth=1.5, label='Limite Direito')
    # Configurações do gráfico
   # eixo_recebido.title('Circuito de Interlagos - Limites e Proporção Real')
   # eixo_recebido.xlabel('Eixo X (m)')
   # eixo_recebido.ylabel('Eixo Y (m)')
   # eixo_recebido.axis('equal')  # Mantém a proporção real em x e y
   # eixo_recebido.legend()

    centro_x_pista = x.mean()
    centro_y_pista = y.mean()

    return centro_x_pista, centro_y_pista

def obter_coordenadas_pista(caminho_ficheiro):
    """Lê o ficheiro da pista e devolve as coordenadas matemáticas das bordas para o Arcade."""
    pista_interlagos = pd.read_csv(caminho_ficheiro)
    pista_interlagos.columns = pista_interlagos.columns.str.strip()

    x = pista_interlagos['# x_m'].values
    y = pista_interlagos['y_m'].values
    w_right = pista_interlagos['w_tr_right_m'].values
    w_left = pista_interlagos['w_tr_left_m'].values

    dx = np.gradient(x)
    dy = np.gradient(y)
    norm = np.hypot(dx, dy)
    norm[norm == 0] = 1

    nx = -dy / norm
    ny = dx / norm

    fator_largura = 2.0
    x_left = x + nx * (w_left * fator_largura)
    y_left = y + ny * (w_left * fator_largura)
    x_right = x - nx * (w_right * fator_largura)
    y_right = y - ny * (w_right * fator_largura)

    return {
        "centro_x": x.tolist(), "centro_y": y.tolist(),
        "esquerda_x": x_left.tolist(), "esquerda_y": y_left.tolist(),
        "direita_x": x_right.tolist(), "direita_y": y_right.tolist()
    }

if __name__ == '__main__':
    # Bloco de teste corrigido com criação de uma figura genérica
    fig, ax = plt.subplots()
    desenhar_pista(r'data/raw/SaoPaulo.csv', ax)
    plt.axis('equal')
    plt.show()
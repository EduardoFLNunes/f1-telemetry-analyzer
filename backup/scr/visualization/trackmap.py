import arcade
import numpy as np

# --- CLASSE FRONTEND (ARCADE) ---

class ArcadeTrackView(arcade.Window):
    def __init__(self, largura, altura, titulo, x_pista, y_pista, x_tele, y_tele):
        super().__init__(largura, altura, titulo)
        arcade.set_background_color(arcade.color.BLACK) # Fundo estilo Arcade
        
        # 1. Armazenar Dados vindos do Backend (Loader)
        self.x_pista = x_pista
        self.y_pista = y_pista
        self.x_tele = x_tele
        self.y_tele = y_tele

        # 2. Configuração do Carro (Ponto Roxa)
        self.indice_carro = 0
        self.velocidade_animacao = 3  # Quantos pontos pular por frame (ajuste aqui)
        
        # 3. Lógica de Escala e Centralização (Automática)
        # Encontra os limites totais combinando pista e telemetria
        todos_x = self.x_pista + self.x_tele
        todos_y = self.y_pista + self.y_tele
        
        self.min_x, self.max_x = min(todos_x), max(todos_x)
        self.min_y, self.max_y = min(todos_y), max(todos_y)
        
        largura_real = self.max_x - self.min_x
        altura_real = self.max_y - self.min_y
        
        # Define a escala para ocupar 85% da tela
        margem = 0.85
        self.escala = min(largura * margem / largura_real, altura * margem / altura_real)
        
        # Offsets para centralizar o desenho na janela
        self.offset_x = (largura - largura_real * self.escala) / 2
        self.offset_y = (altura - altura_real * self.escala) / 2

    def transformar(self, x, y):
        """ Converte coordenadas de Metros (Backend) para Pixels (Arcade) """
        px = (x - self.min_x) * self.escala + self.offset_x
        py = (y - self.min_y) * self.escala + self.offset_y
        return px, py

    def on_update(self, delta_time):
        """ Lógica de movimentação do ponto roxo """
        self.indice_carro += self.velocidade_animacao
        if self.indice_carro >= len(self.x_tele):
            self.indice_carro = 0  # Reinicia a volta (Loop)

    def on_draw(self):
        """ Loop de Renderização Visual """
        self.clear()
        
        # --- DESENHAR PISTA AMARELA (BACKGROUND) ---
        # Transformamos os metros em pixels para o Arcade
        pontos_pista = [self.transformar(x, y) for x, y in zip(self.x_pista, self.y_pista)]
        
        # Desenha a linha da pista (Amarela Neon)
        if len(pontos_pista) > 1:
            arcade.draw_line_strip(pontos_pista, arcade.color.FLUORESCENT_YELLOW, 2)

        # --- DESENHAR CARRO (PONTO ROXO) ---
        if self.indice_carro < len(self.x_tele):
            cx_m = self.x_tele[self.indice_carro]
            cy_m = self.y_tele[self.indice_carro]
            cx, cy = self.transformar(cx_m, cy_m)
            
            # Efeito de Brilho (Glow)
            arcade.draw_circle_filled(cx, cy, 10, (147, 112, 219, 80)) # Brilho externo
            arcade.draw_circle_filled(cx, cy, 5, arcade.color.PURPLE)     # Centro sólido

# --- INTEGRAÇÃO COM O SEU PROJETO (BACKEND) ---
def iniciar_arcade(df_telemetria, x_pista, y_pista, ajuste_x, ajuste_z):
    """
    Função para preparar os dados e abrir a janela Arcade.
    Aceita df_telemetria como DataFrame ou como uma lista simples para testes.
    """
    # 1. Preparar dados da Pista Amarela
    x_pista_lista = list(x_pista)
    y_pista_lista = list(y_pista)
    
    # 2. Preparar dados da Telemetria (Jogador)
    # Se df_telemetria for um DataFrame do Pandas (Projeto Real)
    if hasattr(df_telemetria, 'get'): 
        x_jogador = (df_telemetria['pos_x'] + ajuste_x).tolist()
        z_jogador = (-df_telemetria['pos_z'] + ajuste_z).tolist()
    else:
        # Se for apenas um teste com listas (Exemplo básico)
        x_jogador = [x + ajuste_x for x in x_pista_lista]
        z_jogador = [y + ajuste_z for y in y_pista_lista]

    # 3. Criar e rodar a janela
    janela = ArcadeTrackView(1200, 800, "F1 Telemetry Arcade", 
                             x_pista_lista, y_pista_lista, 
                             x_jogador, z_jogador)
    arcade.run()

# --- ÁREA DE TESTE (Roda apenas se você clicar "Play" neste arquivo) ---
if __name__ == "__main__":
    # Criando um quadrado de teste para garantir que o código abre
    teste_x = [100, 500, 500, 100, 100]
    teste_y = [100, 100, 500, 500, 100]
    
    print("Iniciando modo de teste Arcade...")
    # Enviamos None no DF, mas agora a função sabe lidar com isso
    iniciar_arcade(None, teste_x, teste_y, 0, 0)
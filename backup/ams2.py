import socket
import struct
import pandas as pd
import time
import os
import glob
from datetime import datetime
from pathlib import Path

UDP_IP = "0.0.0.0"
UDP_PORT = 5606
CSV_FILENAME = "telemetry_session.csv"

print("[INÍCIO] Configurando o Socket...")
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.settimeout(1.0)
print(f"[INÍCIO] Socket configurado com sucesso na porta {UDP_PORT}.\n")

rows = []

car_state = {
    "speed": 0,
    "throttle": 0.0,
    "brake": 0.0,
    "lap": 0
}

try:
    print("[LOOP] Entrando no loop infinito de captura...")
    while True:
        try:
            # Fica travado aqui até o jogo mandar algo (ou dar timeout de 1s)
            data, addr = sock.recvfrom(4096)
            
            # Se chegou aqui, o jogo mandou um pacote!
            print(f"\n[PASSO 1] Pacote recebido! Tamanho: {len(data)} bytes")

            if len(data) < 29:
                print("[AVISO] Pacote muito pequeno (menor que 29 bytes). Ignorando...")
                continue

            # Descobrindo qual é o pacote
            packet_id = data[6]
            player_car_index = data[27]
            session_time = struct.unpack_from("<f", data, 15)[0]
            
            print(f"[PASSO 2] Cabeçalho lido | ID do Pacote: {packet_id} | Carro: {player_car_index}")

            # ---------------------------------------------------------
            if packet_id == 6:
                print("[PASSO 3] Entrou no IF de TELEMETRIA (Pedais e Volante)")
                player_offset = 29 + (player_car_index * 60)
                
                car_state["speed"] = struct.unpack_from("<H", data, player_offset)[0]
                car_state["throttle"] = struct.unpack_from("<f", data, player_offset + 2)[0]
                car_state["brake"] = struct.unpack_from("<f", data, player_offset + 10)[0]
                print(f"   -> Velocidade atualizada no buffer: {car_state['speed']} km/h")

            # ---------------------------------------------------------
            elif packet_id == 2:
                print("[PASSO 3] Entrou no IF de LAP DATA (Dados da Volta)")
                player_offset = 29 + (player_car_index * 52)
                try:
                    car_state["lap"] = data[player_offset + 31]
                    print(f"   -> Volta atualizada no buffer: {car_state['lap']}")
                except IndexError:
                    print("[ERRO] Falha ao ler a volta (IndexError)")

            # ---------------------------------------------------------
            elif packet_id == 0:
                print("[PASSO 3] Entrou no IF de MOTION DATA (Posição X, Y, Z)")
                player_offset = 29 + (player_car_index * 60)
                
                #pos_x, pos_y, pos_z = struct.unpack_from("<fff", data, player_offset)
                #print(f"   -> Coordenadas extraídas: X={pos_x:.1f}, Z={pos_z:.1f}")
                
                row = {
                    "session_time": session_time,
                    "lap": car_state["lap"],
                    #"pos_x": pos_x,
                    #"pos_y": pos_y,
                    #"pos_z": pos_z,
                    "speed": car_state["speed"],
                    "throttle": car_state["throttle"],
                    "brake": car_state["brake"]
                }
                
                rows.append(row)
                print(f"[PASSO 4] Linha gravada na memória! (Total de linhas: {len(rows)})")
            
            # ---------------------------------------------------------
            else:
                # O jogo manda vários outros IDs (1, 3, 4, 7...). Isso mostra quando ignoramos eles.
                print(f"[PASSO 3] Pacote ID {packet_id} ignorado (Não é 0, 2 ou 6).")

        except socket.timeout:
            # Só imprime isso se passar 1 segundo sem o jogo mandar absolutamente nada
            print("[STATUS] Aguardando o jogo enviar dados... (Timeout 1s)")
            pass 

except KeyboardInterrupt:
    print("\n\n[FIM] Você apertou CTRL+C! Saindo do loop de captura...")

finally:
    print("[FINALIZAÇÃO] Iniciando o processo de salvar o arquivo CSV...")
    if rows:
        df = pd.DataFrame(rows)

        # Define o caminho da pasta onde os arquivos ficarão salvos
        # (Usamos o 'r' antes das aspas para o Python ler as barras corretamente)
        pasta_destino = r"scr\telemetry\ams2"
        
        # Cria a pasta automaticamente caso ela ainda não exista
        os.makedirs(pasta_destino, exist_ok=True)
        
        # 1. Pega a data e hora atual no formato Dia-Mes-Ano_Hora-Minuto
        agora = datetime.now().strftime("%d-%m-%Y_%H-%M")
        
        # 2. Descobre o número da sessão contando quantos arquivos já existem
        padrao_busca = os.path.join(pasta_destino, "telemetria_ams2_*.csv")
        arquivos_existentes = glob.glob(padrao_busca)

        max_sessao = 0
        for arquivo in arquivos_existentes:
            # Pega apenas o nome do arquivo, ignorando caminhos de pastas (ex: C:/pasta/arquivo.csv)
            nome_arquivo = os.path.basename(arquivo)
            
            # Fatiamos o nome usando o "_" como separador. 
            # Ex: 'telemetria_f125_3_29-03-2026_21-23-36.csv' vira ['telemetria', 'f125', '3', '29-03-2026', '21-23-36.csv']
            partes = nome_arquivo.split('_')
            
            # Garantimos que a lista tem o tamanho mínimo esperado para evitar erro em outros arquivos
            if len(partes) >= 3:
                try:
                    # O número da sessão está na 3ª posição (índice 2)
                    sessao_atual = int(partes[2])
                    
                    # Atualiza qual é o maior número encontrado até agora
                    if sessao_atual > max_sessao:
                        max_sessao = sessao_atual
                except ValueError:
                    # Se por acaso tiver um texto ali em vez de número, ele ignora
                    pass
        
        # A nova sessão é simplesmente o maior número encontrado + 1

        numero_sessao = 1

        # 3. Monta o nome final do arquivo dinamicamente
        novo_nome_csv = f"telemetria_ams2_{numero_sessao}_{agora}.csv"
        
        # 3. Monta o nome final do arquivo dinamicamente
        caminho_completo = Path(pasta_destino) / novo_nome_csv
        
        # 5. Salva o arquivo no caminho correto
        df.to_csv(caminho_completo, index=False)
        print(f"[SUCESSO] Arquivo salvo como '{caminho_completo}' com {len(df)} linhas!")
    else:
        print("[AVISO] Nenhuma linha foi salva. A lista 'rows' está vazia.")
    
    sock.close()
    print("[FINALIZAÇÃO] Socket fechado. Script encerrado.")
"""
Módulo de Captura UDP de Telemetria em Tempo Real
Captura dados de F1 2025 e Automobilista 2 via UDP
"""
import socket
import struct
import pandas as pd
import time
import os
from datetime import datetime
from pathlib import Path
import logging
import threading

logger = logging.getLogger(__name__)


class UDPTelemetryCapture:
    """
    Captura telemetria via UDP dos jogos F1 2025 e Automobilista 2
    """
    
    # Portas UDP dos jogos
    PORT_F125 = 20777
    PORT_AMS2 = 5606
    
    def __init__(self, game="F1-25", output_dir="data/telemetry_sessions"):
        """
        Inicializa captura UDP
        
        Args:
            game: "F1-25" ou "AMS2"
            output_dir: Diretório para salvar CSVs
        """
        self.game = game
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.udp_port = self.PORT_F125 if game == "F1-25" else self.PORT_AMS2
        self.running = False
        self.capture_thread = None
        
        # Buffer de dados
        self.rows = []
        self.car_state = {
            "speed": 0,
            "throttle": 0.0,
            "brake": 0.0,
            "lap": 0
        }
        
        # Socket
        self.sock = None
    
    def start_capture(self):
        """Inicia captura em thread separada"""
        if self.running:
            logger.warning("Captura já está rodando")
            return
        
        try:
            # Configurar socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("0.0.0.0", self.udp_port))
            self.sock.settimeout(1.0)
            
            logger.info(f"Socket UDP configurado na porta {self.udp_port}")
            logger.info(f"Aguardando dados do {self.game}...")
            
            # Iniciar thread de captura
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            logger.info("Captura iniciada com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar captura: {str(e)}")
            raise
    
    def stop_capture(self):
        """Para captura e salva CSV"""
        if not self.running:
            logger.warning("Captura não está rodando")
            return
        
        logger.info("Parando captura...")
        self.running = False
        
        if self.capture_thread:
            self.capture_thread.join(timeout=5.0)
        
        if self.sock:
            self.sock.close()
        
        # Salvar CSV
        if self.rows:
            csv_path = self._save_csv()
            logger.info(f"CSV salvo em: {csv_path}")
            return csv_path
        else:
            logger.warning("Nenhum dado capturado")
            return None
    
    def _capture_loop(self):
        """Loop principal de captura (roda em thread)"""
        logger.info("Loop de captura iniciado")
        
        while self.running:
            try:
                # Receber pacote UDP
                data, addr = self.sock.recvfrom(4096)
                
                if len(data) < 29:
                    continue
                
                # Processar pacote
                self._process_packet(data)
                
            except socket.timeout:
                # Normal - timeout de 1s sem dados
                continue
            except Exception as e:
                logger.error(f"Erro no loop de captura: {str(e)}")
                if self.running:
                    time.sleep(0.1)
        
        logger.info("Loop de captura finalizado")
    
    def _process_packet(self, data: bytes):
        """Processa pacote UDP do jogo"""
        try:
            # Cabeçalho do pacote
            packet_id = data[6]
            player_car_index = data[27]
            session_time = struct.unpack_from("<f", data, 15)[0]
            
            # Pacote de TELEMETRIA (ID 6) - Pedais e volante
            if packet_id == 6:
                player_offset = 29 + (player_car_index * 60)
                
                if player_offset + 10 < len(data):
                    self.car_state["speed"] = struct.unpack_from("<H", data, player_offset)[0]
                    self.car_state["throttle"] = struct.unpack_from("<f", data, player_offset + 2)[0]
                    self.car_state["brake"] = struct.unpack_from("<f", data, player_offset + 10)[0]
            
            # Pacote de LAP DATA (ID 2) - Dados da volta
            elif packet_id == 2:
                player_offset = 29 + (player_car_index * 52)
                
                if player_offset + 31 < len(data):
                    try:
                        self.car_state["lap"] = data[player_offset + 31]
                    except IndexError:
                        pass
            
            # Pacote de MOTION DATA (ID 0) - Posição X, Y, Z
            elif packet_id == 0:
                player_offset = 29 + (player_car_index * 60)
                
                if player_offset + 12 < len(data):
                    pos_x, pos_y, pos_z = struct.unpack_from("<fff", data, player_offset)
                    
                    # Criar linha de dados
                    row = {
                        "session_time": session_time,
                        "lap": self.car_state["lap"],
                        "pos_x": pos_x,
                        "pos_y": pos_y,
                        "pos_z": pos_z,
                        "speed": self.car_state["speed"],
                        "throttle": self.car_state["throttle"],
                        "brake": self.car_state["brake"]
                    }
                    
                    self.rows.append(row)
                    
                    # Log a cada 100 pontos
                    if len(self.rows) % 100 == 0:
                        logger.info(f"Capturados {len(self.rows)} pontos | Volta {self.car_state['lap']} | Velocidade {self.car_state['speed']} km/h")
        
        except Exception as e:
            logger.error(f"Erro ao processar pacote: {str(e)}")
    
    def _save_csv(self) -> Path:
        """Salva dados capturados em CSV"""
        df = pd.DataFrame(self.rows)
        
        # Gerar nome do arquivo
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M")
        
        # Encontrar próximo número de sessão
        pattern = f"telemetria_{self.game}_*.csv"
        existing_files = list(self.output_dir.glob(pattern))
        
        session_number = 1
        if existing_files:
            # Extrair números de sessão existentes
            for filepath in existing_files:
                parts = filepath.stem.split('_')
                if len(parts) >= 3:
                    try:
                        num = int(parts[2])
                        session_number = max(session_number, num + 1)
                    except ValueError:
                        pass
        
        # Nome final
        filename = f"telemetria_{self.game}_{session_number}_{timestamp}.csv"
        filepath = self.output_dir / filename
        
        # Salvar
        df.to_csv(filepath, index=False)
        logger.info(f"CSV salvo: {filepath} ({len(df)} linhas)")
        
        return filepath
    
    def get_status(self) -> dict:
        """Retorna status da captura"""
        return {
            "running": self.running,
            "game": self.game,
            "port": self.udp_port,
            "points_captured": len(self.rows),
            "current_lap": self.car_state["lap"],
            "current_speed": self.car_state["speed"]
        }


# Função auxiliar para uso direto
def capture_telemetry(game="F1-25", duration_seconds=None):
    """
    Captura telemetria do jogo
    
    Args:
        game: "F1-25" ou "AMS2"
        duration_seconds: Tempo de captura (None = até CTRL+C)
    
    Returns:
        Path do CSV salvo
    """
    capture = UDPTelemetryCapture(game=game)
    
    try:
        capture.start_capture()
        
        if duration_seconds:
            logger.info(f"Capturando por {duration_seconds} segundos...")
            time.sleep(duration_seconds)
        else:
            logger.info("Capturando... Pressione CTRL+C para parar")
            while True:
                time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Captura interrompida pelo usuário")
    
    finally:
        csv_path = capture.stop_capture()
        return csv_path


if __name__ == "__main__":
    # Teste standalone
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Escolher jogo
    import sys
    game = "F1-25" if len(sys.argv) < 2 else sys.argv[1]
    
    csv_file = capture_telemetry(game=game)
    print(f"\nTelemetria salva em: {csv_file}")

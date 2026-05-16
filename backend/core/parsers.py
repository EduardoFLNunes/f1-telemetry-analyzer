"""
Binary Parsers for Simulator Telemetry Packets
Implements high-performance unpacking for F1-25 and other sims.
"""
import struct
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class F125Parser:
    """
    Parser for F1-25 UDP packets.
    Reference: Codemasters/EA F1 2024/2025 UDP Specifications.
    """
    
    HEADER_SIZE = 29
    
    @staticmethod
    def parse_header(data: bytes) -> Dict[str, Any]:
        """Unpacks the standard packet header."""
        # Header format: HBBQfIBB
        # PacketFormat (H), GameMajorVersion (B), GameMinorVersion (B), PacketVersion (B), 
        # PacketId (B), SessionUID (Q), SessionTime (f), FrameIdentifier (I), 
        # PlayerCarIndex (B), SecondaryPlayerCarIndex (B)
        header = struct.unpack_from("<HBBBBBQfIBB", data)
        return {
            "packet_id": header[4],
            "session_uid": header[6],
            "session_time": header[7],
            "frame_id": header[8],
            "player_car_index": header[9]
        }

    def parse(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Main entry point for parsing a raw UDP packet."""
        if len(data) < self.HEADER_SIZE:
            return None
            
        # Use offsets from udp_capture.py which are known to work
        try:
            packet_id = data[6]
            player_idx = data[27]
            session_time = struct.unpack_from("<f", data, 15)[0]
            
            result = {
                "packet_id": packet_id, 
                "session_time": session_time,
                "player_idx": player_idx
            }
            
            if packet_id == 0: # Motion
                offset = self.HEADER_SIZE + (player_idx * 60)
                # Motion packet CarMotionData structure (60 bytes):
                # float m_worldPositionX, m_worldPositionY, m_worldPositionZ
                # float m_worldVelocityX, m_worldVelocityY, m_worldVelocityZ
                # int16 m_worldForwardDirX, m_worldForwardDirY, m_worldForwardDirZ
                # int16 m_worldRightDirX, m_worldRightDirY, m_worldRightDirZ
                # float m_gForceLateral, m_gForceLongitudinal, m_gForceVertical
                # float m_yaw, m_pitch, m_roll
                
                motion_data = struct.unpack_from("<ffffffhhhhhhffffff", data, offset)
                result.update({
                    "type": "motion",
                    "x": motion_data[0],
                    "y": motion_data[1],
                    "z": motion_data[2],
                    "vx": motion_data[3],
                    "vy": motion_data[4],
                    "vz": motion_data[5],
                    "g_lat": motion_data[12],
                    "g_lon": motion_data[13],
                    "g_vert": motion_data[14],
                    "heading": motion_data[15], # yaw
                    "pitch": motion_data[16],
                    "roll": motion_data[17]
                })
                return result
                
            elif packet_id == 2: # Lap Data
                offset = self.HEADER_SIZE + (player_idx * 52)
                # m_currentLapTime is at offset + 4 (float)
                # m_currentLapNum is at offset + 31 (uint8)
                lap_num = data[offset + 31]
                lap_time = struct.unpack_from("<f", data, offset + 4)[0]
                result.update({
                    "type": "lap",
                    "lap_number": lap_num,
                    "lap_time": lap_time
                })
                return result
                
            elif packet_id == 6: # Telemetry
                offset = self.HEADER_SIZE + (player_idx * 60)
                speed = struct.unpack_from("<H", data, offset)[0]
                throttle = struct.unpack_from("<f", data, offset + 2)[0]
                brake = struct.unpack_from("<f", data, offset + 10)[0]
                result.update({
                    "type": "telemetry",
                    "speed": speed,
                    "throttle": throttle,
                    "brake": brake
                })
                return result
                
        except Exception as e:
            logger.error(f"Error parsing F1-25 packet {packet_id}: {e}")
            
        return None

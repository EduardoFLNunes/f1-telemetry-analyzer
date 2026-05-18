import os
import struct
import configparser
import logging
import winreg
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

class ACTrackLoader:
    """
    Assetto Corsa Native Track Loader.
    Responsible for loading map.ini and AI splines (fast_lane.ai, pit_lane.ai)
    to provide the single source of truth for track geometry.
    """

    def __init__(self, ac_path: Optional[str] = None):
        self.ac_path = Path(ac_path) if ac_path else self._detect_ac_path()
        if self.ac_path:
            logger.info(f"Assetto Corsa detected at: {self.ac_path}")
        else:
            logger.warning("Assetto Corsa installation not found. Using fallback paths.")

    def _detect_ac_path(self) -> Optional[Path]:
        """Attempts to detect Assetto Corsa installation path via Registry and Steam VDF."""
        try:
            # 1. Try Registry for Steam Path
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path = Path(winreg.QueryValueEx(key, "SteamPath")[0])
            
            # 2. Parse libraryfolders.vdf
            vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
            if vdf_path.exists():
                with open(vdf_path, "r") as f:
                    content = f.read()
                
                # Simple VDF parsing for 'path' and app '244210'
                import re
                blocks = re.findall(r'"\d+"\s*\{(.*?)\}', content, re.DOTALL)
                for block in blocks:
                    if '"244210"' in block:
                        path_match = re.search(r'"path"\s*"(.*?)"', block)
                        if path_match:
                            ac_base_path = Path(path_match.group(1).replace("\\\\", "\\"))
                            ac_full_path = ac_base_path / "steamapps" / "common" / "assettocorsa"
                            if ac_full_path.exists():
                                return ac_full_path
        except Exception as e:
            logger.debug(f"Failed to detect AC path via registry: {e}")

        # Fallback to common locations
        fallbacks = [
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"),
            Path(r"D:\SteamLibrary\steamapps\common\assettocorsa"),
            Path(r"E:\SteamLibrary\steamapps\common\assettocorsa")
        ]
        for fb in fallbacks:
            if fb.exists():
                return fb
        
        return None

    def load_track(self, track_id: str, layout: Optional[str] = None) -> Dict[str, Any]:
        """
        Loads all official track data for a given track and layout.
        Returns a canonical track structure.
        """
        if not self.ac_path:
            raise RuntimeError("Assetto Corsa path not detected.")

        track_dir = self.ac_path / "content" / "tracks" / track_id
        if not track_dir.exists():
            raise FileNotFoundError(f"Track not found: {track_dir}")

        # Determine sub-paths based on layout
        # AC structure: 
        # tracks/track_id/ui/ui_track.json (main)
        # tracks/track_id/ui/layout_id/ui_track.json (layout)
        # tracks/track_id/data/map.ini (main)
        # tracks/track_id/layout_id/data/map.ini (layout) - Wait, AC usually uses /data/ for many things
        # Actually: 
        # map.ini is usually in /data/ or /layout_id/data/
        # AI files are in /ai/ or /layout_id/ai/
        
        data_dir = track_dir / "data"
        ai_dir = track_dir / "ai"
        
        if layout:
            layout_data_dir = track_dir / layout / "data"
            layout_ai_dir = track_dir / layout / "ai"
            if layout_data_dir.exists(): data_dir = layout_data_dir
            if layout_ai_dir.exists(): ai_dir = layout_ai_dir

        # 1. Parse map.ini for world-to-map transforms (though for LiveMap we want world coordinates)
        map_config = self._parse_map_ini(data_dir)
        
        # 2. Parse AI splines
        fast_lane = self._parse_ai_file(ai_dir / "fast_lane.ai")
        pit_lane = self._parse_ai_file(ai_dir / "pit_lane.ai")

        return self._build_canonical_track(track_id, layout, map_config, fast_lane, pit_lane, track_dir, data_dir)

    def _parse_map_ini(self, data_dir: Path) -> Dict[str, float]:
        """Parses map.ini to extract scale and offsets."""
        map_ini_path = data_dir / "map.ini"
        if not map_ini_path.exists():
            # Sometimes it's in the track root for simple tracks
            map_ini_path = data_dir.parent / "map.ini"
        
        config = {
            "scale": 1.0,
            "x_offset": 0.0,
            "z_offset": 0.0,
            "rotation": 0.0
        }

        if map_ini_path.exists():
            try:
                cp = configparser.ConfigParser()
                cp.read(map_ini_path)
                if 'PARAMETERS' in cp:
                    params = cp['PARAMETERS']
                    config["scale"] = float(params.get("SCALE_FACTOR", 1.0))
                    config["x_offset"] = float(params.get("X_OFFSET", 0.0))
                    config["z_offset"] = float(params.get("Z_OFFSET", 0.0))
                    # rotation is less common but sometimes present
                    config["rotation"] = float(params.get("ROTATION", 0.0))
            except Exception as e:
                logger.error(f"Error parsing map.ini: {e}")
        
        return config

    def _parse_ai_file(self, ai_path: Path) -> Optional[Dict[str, Any]]:
        """Parses an Assetto Corsa .ai spline file."""
        if not ai_path.exists():
            logger.warning(f"AI file not found: {ai_path}")
            return None

        try:
            with open(ai_path, "rb") as f:
                header = f.read(8)
                if len(header) < 8: return None
                
                version, points_count = struct.unpack('<II', header)
                
                # AC .ai format has 18 floats per point
                # 0: pos_x, 1: pos_y, 2: pos_z
                # 3: dist_from_start
                # 7: norm_x, 8: norm_y, 9: norm_z (Normalized)
                # 10: width_left, 11: width_right
                # ...
                point_format = '<18f'
                point_size = struct.calcsize(point_format)
                
                data = {
                    "x": [], "y": [], "z": [],
                    "nx": [], "nz": [],
                    "width_left": [], "width_right": [],
                    "s": []
                }
                
                for _ in range(points_count):
                    raw = f.read(point_size)
                    if len(raw) < point_size: break
                    
                    p = struct.unpack(point_format, raw)
                    data["x"].append(p[0])
                    data["y"].append(p[1])
                    data["z"].append(p[2])
                    data["s"].append(p[3])
                    data["nx"].append(p[7])
                    data["nz"].append(p[9])
                    data["width_left"].append(abs(p[10]))
                    data["width_right"].append(abs(p[11]))
                
                return data
        except Exception as e:
            logger.error(f"Failed to parse AI file {ai_path}: {e}")
            return None

    def _build_canonical_track(self, track_id, layout, map_config, fast_lane, pit_lane, track_dir, data_dir) -> Dict[str, Any]:
        """Constructs the raw world-space track data structure."""
        if not fast_lane:
            raise ValueError("Could not load fast_lane.ai")

        x = np.array(fast_lane["x"])
        z = np.array(fast_lane["z"])
        wl = np.array(fast_lane["width_left"])
        wr = np.array(fast_lane["width_right"])
        nx = np.array(fast_lane["nx"])
        nz = np.array(fast_lane["nz"])

        # Native Edge calculation (Raw)
        lx = x + nx * wl
        lz = z + nz * wl
        rx = x - nx * wr
        rz = z - nz * wr

        # Calculate Raw World Space Bounds
        min_x, max_x = float(np.min(x)), float(np.max(x))
        min_z, max_z = float(np.min(z)), float(np.max(z))
        
        # Ensure dimensions are non-zero
        width = max(max_x - min_x, 1.0)
        height = max(max_z - min_z, 1.0)
        
        track_data = {
            "name": f"{track_id} ({layout})" if layout else track_id,
            "centerline": {"x": x.tolist(), "z": z.tolist()},
            "left_edge": {"x": lx.tolist(), "z": lz.tolist()},
            "right_edge": {"x": rx.tolist(), "z": rz.tolist()},
            "bounds": {
                "min_x": min_x, "max_x": max_x,
                "min_z": min_z, "max_z": max_z,
                "w": width, "h": height,
                "cx": (min_x + max_x) / 2, "cz": (min_z + max_z) / 2
            },
            "is_raw_world_space": True
        }

        if pit_lane:
            track_data["pit_lane"] = {"x": pit_lane["x"], "z": pit_lane["z"]}

        return track_data


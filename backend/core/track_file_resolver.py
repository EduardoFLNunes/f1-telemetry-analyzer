import configparser
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


logger = logging.getLogger(__name__)


COMMON_AC_ROOTS = (
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"),
    Path(r"C:\SteamLibrary\steamapps\common\assettocorsa"),
    Path(r"D:\SteamLibrary\steamapps\common\assettocorsa"),
    Path(r"E:\SteamLibrary\steamapps\common\assettocorsa"),
)


@dataclass
class ModelEntry:
    index: int
    file: str
    absolutePath: Optional[str]
    position: List[float]
    rotation: List[float]
    section: str
    exists: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "file": self.file,
            "absolutePath": self.absolutePath,
            "position": self.position,
            "rotation": self.rotation,
            "section": self.section,
            "exists": self.exists,
        }


@dataclass
class SurfaceEntry:
    section: str
    key: str
    isValidTrack: bool
    isPitlane: bool
    friction: Optional[float]
    dirtAdditive: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section": self.section,
            "KEY": self.key,
            "IS_VALID_TRACK": int(self.isValidTrack),
            "IS_PITLANE": int(self.isPitlane),
            "FRICTION": self.friction,
            "DIRT_ADDITIVE": self.dirtAdditive,
        }


@dataclass
class TrackFileManifest:
    acRoot: Optional[str]
    trackNameFromSharedMemory: Optional[str]
    trackConfigFromSharedMemory: Optional[str]
    source: Optional[str]
    gameCode: str
    trackFolder: Optional[str]
    modelsIni: Optional[str]
    staticModels: List[ModelEntry]
    candidateGeometryFiles: Dict[str, Optional[str]]
    surfacesIni: Optional[str]
    dataAcd: Optional[str]
    surfaceEntries: List[SurfaceEntry]
    validSurfaces: List[str]
    geometrySurfaces: List[str]
    surfaceFilters: Dict[str, bool]
    aiFiles: Dict[str, Optional[str]]
    diagnostics: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "acRoot": self.acRoot,
            "trackNameFromSharedMemory": self.trackNameFromSharedMemory,
            "trackConfigFromSharedMemory": self.trackConfigFromSharedMemory,
            "source": self.source,
            "gameCode": self.gameCode,
            "trackFolder": self.trackFolder,
            "modelsIni": self.modelsIni,
            "staticModels": [entry.to_dict() for entry in self.staticModels],
            "candidateGeometryFiles": self.candidateGeometryFiles,
            "surfacesIni": self.surfacesIni,
            "dataAcd": self.dataAcd,
            "surfaceEntries": [entry.to_dict() for entry in self.surfaceEntries],
            "validSurfaces": self.validSurfaces,
            "geometrySurfaces": self.geometrySurfaces,
            "surfaceFilters": self.surfaceFilters,
            "aiFiles": self.aiFiles,
            "diagnostics": self.diagnostics,
        }


class TrackFileResolver:
    def __init__(
        self,
        ac_root: Optional[str] = None,
        *,
        include_pitlane: bool = False,
        include_sand: bool = False,
        include_outer: bool = False,
        include_carpet: bool = False,
    ):
        self.explicit_ac_root = Path(ac_root).expanduser() if ac_root else None
        self.include_pitlane = include_pitlane
        self.include_sand = include_sand
        self.include_outer = include_outer
        self.include_carpet = include_carpet
        self.diagnostics: List[Dict[str, Any]] = []

    def resolve_ac_root(self) -> Path:
        candidates: List[tuple[str, Optional[Path]]] = [
            ("explicit_ac_root", self.explicit_ac_root),
            ("ASSETTO_CORSA_ROOT", Path(os.environ["ASSETTO_CORSA_ROOT"]).expanduser() if os.getenv("ASSETTO_CORSA_ROOT") else None),
            ("steam_registry", self._detect_steam_ac_root()),
        ]
        candidates.extend((f"common_path:{path}", path) for path in COMMON_AC_ROOTS)

        for reason, candidate in candidates:
            if candidate and self._is_ac_root(candidate):
                resolved = candidate.resolve()
                logger.info("TrackFileResolver AC root resolved via %s: %s", reason, resolved)
                return resolved

        self._diagnostic(
            "missing_ac_root",
            "Assetto Corsa root was not found. Set ASSETTO_CORSA_ROOT to the Assetto Corsa install directory.",
            checked=[str(path) for _, path in candidates if path],
        )
        raise FileNotFoundError("Assetto Corsa root not found. Set ASSETTO_CORSA_ROOT.")

    def resolve_track_folder(self, track_name: str) -> Path:
        ac_root = self.resolve_ac_root()
        tracks_root = ac_root / "content" / "tracks"
        if not tracks_root.exists():
            self._diagnostic("missing_track_folder", "AC content/tracks folder is missing", path=str(tracks_root))
            raise FileNotFoundError(f"AC content/tracks folder is missing: {tracks_root}")

        normalized_track = self._normalize_key(track_name)
        exact = tracks_root / track_name
        logger.info("Resolving track folder for shared memory track name: %s", track_name)
        if exact.is_dir():
            logger.info("Track folder resolved by exact folder name: %s", exact)
            return exact.resolve()

        for child in tracks_root.iterdir():
            if child.is_dir() and self._normalize_key(child.name) == normalized_track:
                logger.info("Track folder resolved by case-insensitive folder name: %s", child)
                return child.resolve()

        candidates = self._score_track_folders(tracks_root, track_name)
        if candidates:
            score, folder, reasons = candidates[0]
            logger.info("Track folder resolved by metadata score=%s reasons=%s: %s", score, reasons, folder)
            return folder.resolve()

        self._diagnostic(
            "missing_track_folder",
            "Could not resolve current shared-memory track under AC content/tracks",
            trackName=track_name,
            tracksRoot=str(tracks_root),
        )
        raise FileNotFoundError(f"Track folder not found for {track_name}")

    def resolve_models_ini(self, track_folder: Path, track_config: Optional[str]) -> Path:
        candidates = self._models_candidates(track_folder, track_config)
        logger.info("Resolving models ini for track=%s config=%s", track_folder, track_config)
        for candidate in candidates:
            if candidate.exists() and self._has_static_models(candidate):
                logger.info("Selected models ini: %s", candidate)
                return candidate.resolve()

        self._diagnostic(
            "missing_models_ini",
            "No models.ini/models_<layout>.ini with static MODEL entries was found",
            trackFolder=str(track_folder),
            trackConfig=track_config,
            checked=[str(path) for path in candidates],
        )
        raise FileNotFoundError(f"models.ini not found for {track_folder}")

    def parse_models_ini(self, models_ini: Path) -> List[ModelEntry]:
        parser = self._read_ini(models_ini)
        entries: List[ModelEntry] = []
        base_dir = models_ini.parent
        for section in parser.sections():
            upper = section.upper()
            if not upper.startswith("MODEL_") or upper.startswith("DYNAMIC_OBJECT_"):
                continue
            index = self._section_index(section, default=len(entries))
            file_name = parser.get(section, "FILE", fallback="").strip()
            if not file_name:
                continue
            absolute = (base_dir / file_name).resolve()
            if not absolute.exists() and base_dir != models_ini.parent.parent:
                fallback = (models_ini.parent.parent / file_name).resolve()
                if fallback.exists():
                    absolute = fallback
            entry = ModelEntry(
                index=index,
                file=file_name,
                absolutePath=str(absolute),
                position=self._parse_vector(parser.get(section, "POSITION", fallback="0,0,0")),
                rotation=self._parse_vector(parser.get(section, "ROTATION", fallback="0,0,0")),
                section=section,
                exists=absolute.exists(),
            )
            entries.append(entry)

        entries.sort(key=lambda entry: entry.index)
        logger.info("Parsed %s static MODEL entries from %s", len(entries), models_ini)
        return entries

    def resolve_surfaces_ini(self, track_folder: Path, track_config: Optional[str] = None) -> Optional[Path]:
        for candidate in self._layout_file_candidates(track_folder, track_config, "data", "surfaces.ini"):
            if candidate.exists():
                logger.info("Resolved surfaces.ini: %s", candidate)
                return candidate.resolve()

        data_acd = track_folder / "data.acd"
        if data_acd.exists():
            logger.info("surfaces.ini missing but data.acd exists: %s", data_acd)
            self._diagnostic(
                "missing_surfaces_ini",
                "surfaces.ini was not unpacked; data.acd exists but is not extracted by TrackFileResolver",
                dataAcd=str(data_acd),
            )
        else:
            logger.info("surfaces.ini and data.acd missing for %s", track_folder)
            self._diagnostic("missing_surfaces_ini", "No data/surfaces.ini or data.acd found", trackFolder=str(track_folder))
        return None

    def resolve_ai_files(self, track_folder: Path, track_config: Optional[str] = None) -> Dict[str, Optional[str]]:
        candidates = {
            "fast_lane": self._first_existing(self._layout_file_candidates(track_folder, track_config, "ai", "fast_lane.ai")),
            "pit_lane": self._first_existing(self._layout_file_candidates(track_folder, track_config, "ai", "pit_lane.ai")),
            "ideal_line": self._first_existing(self._layout_file_candidates(track_folder, track_config, "ai", "ideal_line.ai")),
            "line_spl": self._first_existing(
                self._layout_file_candidates(track_folder, track_config, "data", "line.spl")
                + [track_folder / "line.spl"]
            ),
            "map_ini": self._first_existing(
                self._layout_file_candidates(track_folder, track_config, "data", "map.ini")
                + [track_folder / "map.ini"]
            ),
            "groove_ini": self._first_existing(
                self._layout_file_candidates(track_folder, track_config, "data", "groove.ini")
                + [track_folder / "groove.ini"]
            ),
            "groveline_csv": self._first_existing(
                self._layout_file_candidates(track_folder, track_config, "data", "groveline.csv")
                + [track_folder / "groveline.csv"]
            ),
        }
        ai_files = {key: str(path.resolve()) if path else None for key, path in candidates.items()}
        logger.info("Resolved AI/reference files: %s", {key: bool(value) for key, value in ai_files.items()})
        if not ai_files.get("fast_lane"):
            self._diagnostic("missing_fast_lane", "ai/fast_lane.ai was not found", trackFolder=str(track_folder))
        return ai_files

    def build_track_file_manifest(
        self,
        track_name: str,
        track_config: Optional[str],
        *,
        source: Optional[str] = None,
        game_code: str = "assetto_corsa",
    ) -> TrackFileManifest:
        self.diagnostics = []
        logger.info(
            "Building track file manifest from shared memory track=%s config=%s source=%s",
            track_name,
            track_config,
            source,
        )

        ac_root: Optional[Path] = None
        track_folder: Optional[Path] = None
        models_ini: Optional[Path] = None
        static_models: List[ModelEntry] = []
        surfaces_ini: Optional[Path] = None
        surface_entries: List[SurfaceEntry] = []
        data_acd: Optional[Path] = None
        ai_files: Dict[str, Optional[str]] = {}
        candidate_geometry = {"mainVisual": None, "collider": None, "groove": None}

        if not track_name:
            self._diagnostic("missing_track_name", "No track name is available from shared memory/runtime")
            return self._manifest(
                ac_root,
                track_name,
                track_config,
                source,
                game_code,
                track_folder,
                models_ini,
                static_models,
                candidate_geometry,
                surfaces_ini,
                data_acd,
                surface_entries,
                ai_files,
            )

        try:
            ac_root = self.resolve_ac_root()
            track_folder = self.resolve_track_folder(track_name)
            models_ini = self.resolve_models_ini(track_folder, track_config)
            static_models = self.parse_models_ini(models_ini)
            candidate_geometry = self._candidate_geometry(static_models)
            logger.info("Candidate KN5 files: %s", candidate_geometry)
            for model in static_models:
                if not model.exists:
                    self._diagnostic("missing_kn5", "MODEL file was referenced but not found", file=model.file, absolutePath=model.absolutePath)
            surfaces_ini = self.resolve_surfaces_ini(track_folder, track_config)
            data_acd = (track_folder / "data.acd").resolve() if (track_folder / "data.acd").exists() else None
            if surfaces_ini:
                surface_entries = self.parse_surfaces_ini(surfaces_ini)
            ai_files = self.resolve_ai_files(track_folder, track_config)
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.exception("Unexpected TrackFileResolver error")
            self._diagnostic("resolver_error", str(exc))

        return self._manifest(
            ac_root,
            track_name,
            track_config,
            source,
            game_code,
            track_folder,
            models_ini,
            static_models,
            candidate_geometry,
            surfaces_ini,
            data_acd,
            surface_entries,
            ai_files,
        )

    def parse_surfaces_ini(self, surfaces_ini: Path) -> List[SurfaceEntry]:
        parser = self._read_ini(surfaces_ini)
        entries: List[SurfaceEntry] = []
        for section in parser.sections():
            if not section.upper().startswith("SURFACE_"):
                continue
            key = parser.get(section, "KEY", fallback="").strip().upper()
            entries.append(
                SurfaceEntry(
                    section=section,
                    key=key,
                    isValidTrack=self._ini_bool(parser.get(section, "IS_VALID_TRACK", fallback="0")),
                    isPitlane=self._ini_bool(parser.get(section, "IS_PITLANE", fallback="0")),
                    friction=self._optional_float(parser.get(section, "FRICTION", fallback=None)),
                    dirtAdditive=self._optional_float(parser.get(section, "DIRT_ADDITIVE", fallback=None)),
                )
            )
        valid = [entry.key for entry in entries if entry.isValidTrack]
        logger.info("Parsed %s surface entries from %s; valid=%s", len(entries), surfaces_ini, valid)
        return entries

    def _manifest(
        self,
        ac_root: Optional[Path],
        track_name: Optional[str],
        track_config: Optional[str],
        source: Optional[str],
        game_code: str,
        track_folder: Optional[Path],
        models_ini: Optional[Path],
        static_models: List[ModelEntry],
        candidate_geometry: Dict[str, Optional[str]],
        surfaces_ini: Optional[Path],
        data_acd: Optional[Path],
        surface_entries: List[SurfaceEntry],
        ai_files: Dict[str, Optional[str]],
    ) -> TrackFileManifest:
        valid_surfaces = sorted({entry.key for entry in surface_entries if entry.isValidTrack and entry.key})
        geometry_surfaces = [key for key in valid_surfaces if self._include_surface_key(key)]
        return TrackFileManifest(
            acRoot=str(ac_root) if ac_root else None,
            trackNameFromSharedMemory=track_name,
            trackConfigFromSharedMemory=track_config,
            source=source,
            gameCode=game_code,
            trackFolder=str(track_folder) if track_folder else None,
            modelsIni=str(models_ini) if models_ini else None,
            staticModels=static_models,
            candidateGeometryFiles=candidate_geometry,
            surfacesIni=str(surfaces_ini) if surfaces_ini else None,
            dataAcd=str(data_acd) if data_acd else None,
            surfaceEntries=surface_entries,
            validSurfaces=valid_surfaces,
            geometrySurfaces=geometry_surfaces,
            surfaceFilters={
                "INCLUDE_PITLANE": self.include_pitlane,
                "INCLUDE_SAND": self.include_sand,
                "INCLUDE_OUTER": self.include_outer,
                "INCLUDE_CARPET": self.include_carpet,
            },
            aiFiles=ai_files,
            diagnostics=self.diagnostics,
        )

    def _models_candidates(self, track_folder: Path, track_config: Optional[str]) -> List[Path]:
        config = (track_config or "").strip()
        candidates: List[Path] = []
        if config:
            safe = config.replace("/", "_").replace("\\", "_")
            candidates.extend(
                [
                    track_folder / f"models_{safe}.ini",
                    track_folder / config / "models.ini",
                    track_folder / config / f"models_{safe}.ini",
                    track_folder / "models.ini",
                ]
            )
            candidates.extend(sorted(track_folder.glob(f"models_*{safe}*.ini")))
            candidates.extend(sorted((track_folder / config).glob("models_*.ini")) if (track_folder / config).is_dir() else [])
        else:
            candidates.append(track_folder / "models.ini")
        candidates.extend(sorted(track_folder.glob("models_*.ini")))
        return self._dedupe_paths(candidates)

    def _layout_file_candidates(self, track_folder: Path, track_config: Optional[str], folder: str, filename: str) -> List[Path]:
        candidates: List[Path] = []
        config = (track_config or "").strip()
        if config:
            candidates.append(track_folder / config / folder / filename)
        candidates.append(track_folder / folder / filename)
        if not config:
            for child in sorted(track_folder.iterdir()) if track_folder.exists() else []:
                if child.is_dir():
                    candidates.append(child / folder / filename)
        return self._dedupe_paths(candidates)

    def _candidate_geometry(self, models: Sequence[ModelEntry]) -> Dict[str, Optional[str]]:
        existing = [model for model in models if model.exists and model.absolutePath]
        first = existing[0].absolutePath if existing else None
        collider = self._first_model_path(existing, ("collider", "collision"))
        groove = self._first_model_path(existing, ("groove",))
        return {"mainVisual": first, "collider": collider, "groove": groove}

    def _first_model_path(self, models: Sequence[ModelEntry], tokens: Sequence[str]) -> Optional[str]:
        for model in models:
            lower = model.file.lower()
            if any(token in lower for token in tokens):
                return model.absolutePath
        return None

    def _score_track_folders(self, tracks_root: Path, track_name: str) -> List[tuple[int, Path, List[str]]]:
        target = self._normalize_key(track_name)
        candidates: List[tuple[int, Path, List[str]]] = []
        for folder in tracks_root.iterdir():
            if not folder.is_dir():
                continue
            score = 0
            reasons: List[str] = []
            folder_key = self._normalize_key(folder.name)
            if folder_key == target:
                score += 100
                reasons.append("folder_case_insensitive")
            if target and target in folder_key:
                score += 25
                reasons.append("folder_contains_track_name")
            ui_score = self._score_ui_metadata(folder, track_name)
            if ui_score:
                score += ui_score
                reasons.append("ui_track_json_match")
            if list(folder.glob("models*.ini")):
                score += 5
                reasons.append("models_ini_present")
            if (folder / "ai" / "fast_lane.ai").exists():
                score += 5
                reasons.append("fast_lane_present")
            if (folder / "data" / "surfaces.ini").exists() or (folder / "data.acd").exists():
                score += 5
                reasons.append("surface_data_present")
            if score > 0:
                candidates.append((score, folder, reasons))
        return sorted(candidates, key=lambda item: item[0], reverse=True)

    def _score_ui_metadata(self, folder: Path, track_name: str) -> int:
        target = self._normalize_key(track_name)
        ui_files = [folder / "ui" / "ui_track.json", *sorted((folder / "ui").glob("*/ui_track.json"))] if (folder / "ui").exists() else []
        for ui_file in ui_files:
            try:
                data = json.loads(ui_file.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            values = [
                str(data.get("id", "")),
                str(data.get("name", "")),
                str(data.get("description", "")),
                " ".join(str(tag) for tag in data.get("tags", []) if isinstance(data.get("tags", []), list)),
            ]
            blob = self._normalize_key(" ".join(values))
            if target and target in blob:
                return 40
        return 0

    def _detect_steam_ac_root(self) -> Optional[Path]:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path = Path(winreg.QueryValueEx(key, "SteamPath")[0])
            library_vdf = steam_path / "steamapps" / "libraryfolders.vdf"
            roots = [steam_path]
            if library_vdf.exists():
                content = library_vdf.read_text(encoding="utf-8", errors="ignore")
                roots.extend(Path(match.replace("\\\\", "\\")) for match in re.findall(r'"path"\s*"([^"]+)"', content))
            for root in roots:
                candidate = root / "steamapps" / "common" / "assettocorsa"
                if self._is_ac_root(candidate):
                    return candidate
        except Exception as exc:
            logger.debug("Could not resolve AC root through Steam registry: %s", exc)
        return None

    def _is_ac_root(self, path: Path) -> bool:
        return path.exists() and (path / "content" / "tracks").exists()

    def _has_static_models(self, path: Path) -> bool:
        try:
            parser = self._read_ini(path)
            return any(section.upper().startswith("MODEL_") for section in parser.sections())
        except Exception:
            return False

    def _read_ini(self, path: Path) -> configparser.RawConfigParser:
        parser = configparser.RawConfigParser(strict=False, interpolation=None)
        parser.optionxform = str
        parser.read(path, encoding="utf-8-sig")
        return parser

    def _include_surface_key(self, key: str) -> bool:
        normalized = key.upper()
        if "GRASS" in normalized:
            return False
        if "PIT" in normalized and not self.include_pitlane:
            return False
        if "SAND" in normalized and not self.include_sand:
            return False
        if "OUTER" in normalized and not self.include_outer:
            return False
        if "CARPET" in normalized and not self.include_carpet:
            return False
        return True

    def _first_existing(self, paths: Sequence[Path]) -> Optional[Path]:
        for path in paths:
            if path.exists():
                return path
        return None

    def _dedupe_paths(self, paths: Sequence[Path]) -> List[Path]:
        seen = set()
        unique: List[Path] = []
        for path in paths:
            key = str(path).lower()
            if key not in seen:
                seen.add(key)
                unique.append(path)
        return unique

    def _section_index(self, section: str, default: int) -> int:
        match = re.search(r"_(\d+)$", section)
        return int(match.group(1)) if match else default

    def _parse_vector(self, value: str) -> List[float]:
        parts = re.split(r"[,;\s]+", value.strip())
        vector = []
        for part in parts:
            if not part:
                continue
            try:
                vector.append(float(part))
            except ValueError:
                pass
        while len(vector) < 3:
            vector.append(0.0)
        return vector[:3]

    def _ini_bool(self, value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _optional_float(self, value: Optional[str]) -> Optional[float]:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _normalize_key(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

    def _diagnostic(self, code: str, message: str, **context: Any) -> None:
        item = {"code": code, "message": message, **context}
        logger.warning("TrackFileResolver diagnostic: %s", item)
        self.diagnostics.append(item)

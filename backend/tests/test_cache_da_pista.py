"""O cache da pista e refeito so quando os arquivos de origem mudam (pedido 40, Parte D.3).

O defeito (pedido 28, achado 1): `_cache_predates_marking_classification` exige
`boundsLeft[0].elevation`, e a pista montada pelos limites pintados sai sem esse
campo. Todo cache recem-gravado parecia antigo, e o backend remontava a pista a
cada abertura (cerca de 36 s).

A montagem de verdade le ~430 MB de KN5; aqui ela e trocada por uma falsa que conta
as chamadas. O cache, o serializador e as checagens de cache antigo sao os reais.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.cache.track_cache import TrackCache
from core.geometry import track_geometry_provider as provider_mod
from core.geometry.track_geometry_provider import Kn5SurfaceTrackGeometryProvider
from core.telemetry.telemetry_models import TrackPoint


def pista_montada():
    """O que a montagem devolve, com a borda sem elevacao, como sai dos limites pintados."""
    centerline = [
        TrackPoint(x=float(i), y=0.0, z=float(i % 7), distance=float(i), spline_t=i / 10.0)
        for i in range(10)
    ]
    return {
        "trackName": "vhe_interlagos_gp_kn5_surface_interval_geometry",
        "trackLength": 10.0,
        "provider": "kn5_surface_interval",
        "providerSource": "assetto_corsa_track_files",
        "centerline": centerline,
        "boundsLeft": [{"x": float(i), "y": 0.0, "z": 1.0} for i in range(10)],
        "boundsRight": [{"x": float(i), "y": 0.0, "z": -1.0} for i in range(10)],
        "kerbGeometry": {"strips": []},
        "markingGeometry": {"polygons": [[[0, 0], [1, 0], [1, 1]]], "features": []},
        "asphaltSurface": {"componentCount": 1},
    }


class FakeManifest:
    def __init__(self, data):
        self.data = data

    def to_dict(self):
        return self.data


class CacheDaPistaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        raiz = Path(temp.name)
        self.pasta_da_pista = raiz / "vhe_interlagos"
        (self.pasta_da_pista / "gp" / "ai").mkdir(parents=True)
        self.kn5 = self.pasta_da_pista / "vhe_interlagos.kn5"
        self.kn5.write_bytes(b"kn5 original")
        self.ai = self.pasta_da_pista / "gp" / "ai" / "fast_lane.ai"
        self.ai.write_bytes(b"ai original")
        self.data_acd = self.pasta_da_pista / "gp" / "data.acd"
        self.cache = TrackCache(cache_dir=str(raiz / "cache"))
        self.montagens = 0

        manifest = {
            "trackFolder": str(self.pasta_da_pista),
            "candidateGeometryFiles": {"mainVisual": str(self.kn5)},
            "staticModels": [{"file": "vhe_interlagos.kn5", "absolutePath": str(self.kn5)}],
            "aiFiles": {"fast_lane": str(self.ai), "ideal_line": None},
            "dataAcd": str(self.data_acd),
        }

        class FakeResolver:
            def __init__(self, ac_root=None):
                pass

            def build_track_file_manifest(self, *args, **kwargs):
                return FakeManifest(manifest)

        def montar(manifest_dict):
            self.montagens += 1
            return {"metrics": {"validRaycastSamples": 10, "loopClosed": True}}

        for alvo, valor in (
            ("TrackFileResolver", FakeResolver),
            ("build_track_edges_interval_raycast_from_manifest", montar),
            ("track_data_from_interval_edges", lambda result, cache_path=None: pista_montada()),
            ("apply_paint_correction", lambda track_data, track_name: track_data),
        ):
            p = patch.object(provider_mod, alvo, valor)
            p.start()
            self.addCleanup(p.stop)

    def abrir(self):
        return Kn5SurfaceTrackGeometryProvider(self.cache).load_or_build("vhe_interlagos", "gp")

    def test_a_segunda_abertura_usa_o_cache(self):
        primeira = self.abrir()
        self.assertFalse(primeira.from_cache)
        segunda = self.abrir()
        self.assertTrue(segunda.from_cache, "a segunda abertura remontou a pista com a mesma origem")
        self.assertEqual(self.montagens, 1)

    def test_o_cache_nao_muda_de_conteudo(self):
        # A chave fica num arquivo ao lado: o JSON do cache (de onde o ML tira a geometria) nao ganha campo.
        self.abrir()
        cache_json = self.cache.cache_dir / "vhe_interlagos_gp_kn5_surface_interval_geometry.json"
        self.assertNotIn("origem", cache_json.read_text(encoding="utf-8").lower().split('"metadata"')[0])
        self.assertTrue(cache_json.with_name(cache_json.stem + ".origem.json").exists())

    def test_a_origem_mudada_refaz_o_cache(self):
        self.abrir()
        self.ai.write_bytes(b"ai mudado")
        refeita = self.abrir()
        self.assertFalse(refeita.from_cache)
        self.assertEqual(self.montagens, 2)
        self.assertTrue(self.abrir().from_cache)
        self.assertEqual(self.montagens, 2)

    def test_so_a_data_do_arquivo_mudada_nao_refaz(self):
        import os
        import time

        self.abrir()
        futuro = time.time() + 120
        os.utime(self.kn5, (futuro, futuro))
        self.assertTrue(self.abrir().from_cache)
        self.assertEqual(self.montagens, 1)

    def test_o_data_acd_nunca_e_lido(self):
        self.data_acd.write_bytes(b"nao abrir")
        aberto = []
        original = Path.open

        def vigiar(caminho, *args, **kwargs):
            aberto.append(Path(caminho).name)
            return original(caminho, *args, **kwargs)

        with patch.object(Path, "open", vigiar):
            self.abrir()
            self.abrir()
        self.assertNotIn("data.acd", aberto)


if __name__ == "__main__":
    unittest.main()

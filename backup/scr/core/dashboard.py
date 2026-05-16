"""
F1 Telemetry Viewer — loader.py + pistas.py migrados para Python Arcade 3.0+
========================================================================
Otimizacoes para Arcade 3.0+:
  - Substituição total das antigas ShapeElementLists por Vertex Data Arrays.
  - Renderização otimizada com draw_triangle_strip, draw_line_strip e draw_lines.
  - Correção de formas descontinuadas (draw_rectangle_outline etc.).

Requisitos:
    pip install arcade pandas numpy

Estrutura de pastas:
    scr/providers/f1-25/*.csv   <- telemetria
    data/raw/SaoPaulo.csv       <- geometria da pista

Controles:
    B      -> Melhor volta
    A      -> Todas as voltas
    1-9    -> Volta especifica
    ESPACO -> Animacao play/pause do tracado
    R      -> Reiniciar animacao
    ESC    -> Sair
"""

import arcade
import pandas as pd
import numpy as np
import math
import os
import glob

# ---------------------------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------------------------
SCREEN_W = 1440
SCREEN_H = 900
TITLE    = "F1 Telemetry Viewer - Interlagos"

MAP_X, MAP_Y = 20,  50
MAP_W, MAP_H = 590, 820

CHART_X, CHART_Y = 630, 50
CHART_W, CHART_H = 790, 820

HEADER_H   = 40
FOOTER_H   = 28
ANIM_SPEED = 6   # pontos por frame na animacao

# ---------------------------------------------------------------------------
# PALETA
# ---------------------------------------------------------------------------
BG           = (8,   9,  16)
PANEL        = (18,  20, 32)
BORDER       = (45,  50, 75)
RED          = (220, 30, 40)
WHITE        = (235, 238, 248)
DIM          = (140, 145, 165)
ASPHALT_COL  = (85,  90, 108, 170)
EDGE_COL     = (22,  24,  38, 255)
CENTER_COL   = (220, 195,  35, 180)
RACING_COL   = (255, 210,   0, 255)
COL_SPEED    = ( 50, 140, 220)
COL_THROTTLE = ( 50, 195,  80)
COL_BRAKE    = (220,  50,  50)

# ---------------------------------------------------------------------------
# GEOMETRIA DA PISTA
# ---------------------------------------------------------------------------
def obter_geometria_pista(caminho: str):
    if not os.path.exists(caminho):
        return None
    df = pd.read_csv(caminho)
    df.columns = df.columns.str.strip()
    x, y     = df["# x_m"].values,        df["y_m"].values
    w_r, w_l = df["w_tr_right_m"].values,  df["w_tr_left_m"].values

    dx, dy = np.gradient(x), np.gradient(y)
    norm   = np.hypot(dx, dy); norm[norm == 0] = 1.0
    nx, ny = -dy / norm, dx / norm

    f = 2.0
    return {
        "cx": x,         "cy": y,
        "lx": x + nx * (w_l * f),  "ly": y + ny * (w_l * f),
        "rx": x - nx * (w_r * f),  "ry": y - ny * (w_r * f),
        "centro_x": float(x.mean()),
        "centro_y": float(y.mean()),
    }

# ---------------------------------------------------------------------------
# TRANSFORM
# ---------------------------------------------------------------------------
def make_transform(ref_pts_xy, px, py, pw, ph, padding=40, invert_y=True):
    xs = np.concatenate([p[0] for p in ref_pts_xy])
    ys = np.concatenate([p[1] for p in ref_pts_xy])
    rx = xs.max() - xs.min() or 1.0
    ry = ys.max() - ys.min() or 1.0
    scale = min((pw - 2*padding) / rx, (ph - 2*padding) / ry)
    cx = px + pw / 2.0
    cy = py + ph / 2.0
    mx = (xs.min() + xs.max()) / 2.0
    my = (ys.min() + ys.max()) / 2.0

    def w2s(xa, ya):
        xa, ya = np.asarray(xa, float), np.asarray(ya, float)
        sx = cx + (xa - mx) * scale
        sy = (cy - (ya - my) * scale) if invert_y else (cy + (ya - my) * scale)
        return sx, sy
    return w2s

# ---------------------------------------------------------------------------
# CONSTRUCAO DOS DADOS (Vértices compatíveis com Arcade 3.0)
# ---------------------------------------------------------------------------
def _pts(xs, ys):
    return list(zip(xs.tolist(), ys.tolist()))

def build_track_data(geo: dict, transform) -> dict:
    lx_s, ly_s = transform(geo["lx"], geo["ly"])
    rx_s, ry_s = transform(geo["rx"], geo["ry"])
    cx_s, cy_s = transform(geo["cx"], geo["cy"])

    left_pts   = _pts(lx_s, ly_s)
    right_pts  = _pts(rx_s, ry_s)
    center_pts = _pts(cx_s, cy_s)

    # 1. Asfalto: Fatiado em pequenos polígonos (quadriláteros)
    asphalt_quads = []
    n_pts = len(left_pts)
    for i in range(n_pts):
        next_i = (i + 1) % n_pts
        quad = [
            left_pts[i],      # Esquerda atual
            right_pts[i],     # Direita atual
            right_pts[next_i],# Direita próximo
            left_pts[next_i]  # Esquerda próximo
        ]
        asphalt_quads.append(quad)

    # 2. Linha central: Array de linhas soltas (Tracejado 2 em 2)
    center_lines = []
    for i, (a, b) in enumerate(zip(center_pts, center_pts[1:])):
        if i % 4 < 2:
            center_lines.append(a)
            center_lines.append(b)

    return {
        "asphalt_quads": asphalt_quads,
        "left_border": left_pts + [left_pts[0]],
        "right_border": right_pts + [right_pts[0]],
        "center_lines": center_lines
    }

def build_chart_data(series_list, x, y, w, h, y_min=None, y_max=None) -> dict:
    all_vals = [v for vals, _ in series_list for v in vals
                if not (isinstance(v, float) and math.isnan(v))]
    if not all_vals:
        return None

    vmin = y_min if y_min is not None else min(all_vals)
    vmax = y_max if y_max is not None else max(all_vals)
    if vmax == vmin:
        vmax += 1

    PL, PR, PT, PB = 42, 8, 24, 22

    def to_px(i, n, v):
        sx = x + PL + (i / max(n - 1, 1)) * (w - PL - PR)
        sy = y + PB + ((v - vmin) / (vmax - vmin)) * (h - PT - PB)
        return sx, sy

    grid = []
    for i in range(5):
        gy = y + PB + i * (h - PT - PB) / 4
        grid.append((x + PL, gy))
        grid.append((x + w - PR, gy))

    lines = []
    for vals, col in series_list:
        n = len(vals)
        if n < 2:
            continue
        pts = [to_px(i, n, v) for i, v in enumerate(vals)
               if not (isinstance(v, float) and math.isnan(v))]
        lines.append((pts, col))

    return {"grid": grid, "lines": lines}

# ---------------------------------------------------------------------------
# UTILITARIOS DE DESENHO (Safeguard contra bugs do Arcade 3.0)
# ---------------------------------------------------------------------------
def draw_box_filled(l, r, b, t, color):
    points = [(l, b), (r, b), (r, t), (l, t)]
    arcade.draw_polygon_filled(points, color)

def draw_box_outline(l, r, b, t, color, width=1):
    points = [(l, b), (r, b), (r, t), (l, t)]
    arcade.draw_polygon_outline(points, color, width)


# ---------------------------------------------------------------------------
# JANELA PRINCIPAL
# ---------------------------------------------------------------------------
class TelemetryWindow(arcade.Window):

    def __init__(self):
        super().__init__(SCREEN_W, SCREEN_H, TITLE, resizable=False)
        arcade.set_background_color(BG)

        # Dados
        self.df_raw     = None
        self.df_plot    = None
        self.lap_times  = {}
        self.best_lap   = None
        self.best_time  = 0.0
        self.all_laps   = []
        self.vis        = "melhor"

        # Offsets
        self._ajuste_x = 0.0
        self._ajuste_z = 0.0
        self._transform = None

        # Dados geométricos pré-calculados (Substitui ShapeElementLists)
        self._track_data    = None
        self._racing_data   = None
        self._speed_data    = None
        self._throttle_data = None
        self._brake_data    = None

        # Pontos da animação
        self._racing_pts : list = []
        self.anim_index  : int  = 0
        self.anim_playing: bool = False

        # Textos
        self.status_msg = "Carregando..."
        self.error_msg  = None

        self._load_all()

    def _load_all(self):
        try:
            files = glob.glob(r"scr/providers/f1-25/*.csv")
            if not files:
                raise FileNotFoundError("Nenhum CSV em scr/providers/f1-25/")
            newest = max(files, key=os.path.getmtime)
            print(f"Telemetria: {newest}")
            df = pd.read_csv(newest)
        except Exception as e:
            self.error_msg = str(e); return

        df["delta_time"]   = df["session_time"].diff().fillna(0)
        df["speed_ms"]     = df["speed"] / 3.6
        df["delta_dist"]   = df["speed_ms"] * df["delta_time"]
        df["lap_distance"] = df.groupby("lap")["delta_dist"].cumsum()
        self.df_raw = df

        best_t = float("inf")
        for lap in sorted(df["lap"].unique()):
            dv = df[df["lap"] == lap]
            t  = dv["session_time"].max() - dv["session_time"].min()
            self.lap_times[lap] = t
            if t < best_t:
                best_t = t; self.best_lap = lap
        self.best_time = best_t
        self.all_laps  = sorted(df["lap"].unique())

        geo = obter_geometria_pista(r"data/raw/SaoPaulo.csv")
        if geo:
            self._transform = make_transform(
                [(geo["lx"], geo["ly"]), (geo["rx"], geo["ry"])],
                MAP_X, MAP_Y, MAP_W, MAP_H,
                padding=40, invert_y=True)
            self._track_data = build_track_data(geo, self._transform)

            df_best = df[df["lap"] == self.best_lap]
            self._ajuste_x = (geo["centro_x"] - float(df_best["pos_x"].mean())) - 13
            self._ajuste_z = (geo["centro_y"] - float((-df_best["pos_z"]).mean())) + 18
        else:
            print("AVISO: SaoPaulo.csv nao encontrado.")

        self._apply_viz()

    def _apply_viz(self):
        df = self.df_raw
        if self.vis == "melhor":
            self.df_plot = df[df["lap"] == self.best_lap].copy()
        elif isinstance(self.vis, int):
            self.df_plot = df[df["lap"] == self.vis].copy()
        else:
            self.df_plot = df.copy()

        self._rebuild_racing()
        self._rebuild_charts()
        self.anim_index   = 0
        self.anim_playing = False
        self._update_status()

    def _rebuild_racing(self):
        if self.df_plot is None or self.df_plot.empty or self._transform is None:
            self._racing_pts = []; self._racing_data = None; return

        xs = self.df_plot["pos_x"].values.astype(float) + self._ajuste_x
        zs = -self.df_plot["pos_z"].values.astype(float) + self._ajuste_z
        sx, sy = self._transform(xs, zs)
        self._racing_pts = list(zip(sx.tolist(), sy.tolist()))
        self._racing_data = self._racing_pts

    def _rebuild_charts(self):
        if self.df_plot is None or self.df_plot.empty:
            self._speed_data = self._throttle_data = self._brake_data = None; return

        gap = 14
        ch  = (CHART_H - gap * 2) // 3
        y0  = CHART_Y

        speed_s = []; throttle_s = []; brake_s = []
        for lap in self.df_plot["lap"].unique():
            dv = self.df_plot[self.df_plot["lap"] == lap]
            speed_s.append(   (dv["speed"].tolist(),              COL_SPEED))
            throttle_s.append(((dv["throttle"]*100).tolist(),    COL_THROTTLE))
            brake_s.append(   ((dv["brake"]   *100).tolist(),    COL_BRAKE))

        self._speed_data    = build_chart_data(speed_s,    CHART_X, y0+2*(ch+gap), CHART_W, ch)
        self._throttle_data = build_chart_data(throttle_s, CHART_X, y0+ch+gap,    CHART_W, ch, y_min=0, y_max=100)
        self._brake_data    = build_chart_data(brake_s,    CHART_X, y0,            CHART_W, ch, y_min=0, y_max=100)
        self._chart_meta  = (ch, gap, y0, speed_s, throttle_s, brake_s)

    def _update_status(self):
        m, s = int(self.best_time//60), self.best_time%60
        msg = f"Melhor: V{self.best_lap}  {m:02d}:{s:06.3f}   |   Voltas: {len(self.all_laps)}"
        if isinstance(self.vis, int):
            t = self.lap_times.get(self.vis, 0)
            m2, s2 = int(t//60), t%60
            msg += f"   |   V{self.vis}: {m2:02d}:{s2:06.3f}"
        elif self.vis == "todas":
            msg += "   |   Todas as Voltas"
        else:
            msg += "   |   Melhor Volta"
        self.status_msg = msg

    def on_update(self, dt):
        if self.anim_playing and self._racing_pts:
            self.anim_index = min(self.anim_index + ANIM_SPEED, len(self._racing_pts))
            self._racing_data = self._racing_pts[:self.anim_index]
            if self.anim_index >= len(self._racing_pts):
                self.anim_playing = False

    def on_draw(self):
        self.clear()
        if self.error_msg:
            arcade.draw_text(f"ERRO: {self.error_msg}", 40, SCREEN_H//2, RED, 16, font_name="monospace")
            return

        # Fundo dos paineis
        draw_box_filled(MAP_X,   MAP_X+MAP_W,   MAP_Y,   MAP_Y+MAP_H,   PANEL)
        draw_box_filled(CHART_X, CHART_X+CHART_W, CHART_Y, CHART_Y+CHART_H, PANEL)

        # Pista da GPU
        if self._track_data:
            # Desenha cada pedaço de asfalto individualmente
            for quad in self._track_data["asphalt_quads"]:
                arcade.draw_polygon_filled(quad, ASPHALT_COL)
                
            arcade.draw_line_strip(self._track_data["left_border"], EDGE_COL[:3], 2.5)
            arcade.draw_line_strip(self._track_data["right_border"], EDGE_COL[:3], 2.5)
            arcade.draw_lines(self._track_data["center_lines"], CENTER_COL, 1)

        # Tracado
        if self._racing_data and len(self._racing_data) > 1:
            arcade.draw_line_strip(self._racing_data, RACING_COL[:3], 2)

        # Graficos da GPU
        for c_data in [self._speed_data, self._throttle_data, self._brake_data]:
            if c_data:
                if c_data["grid"]:
                    arcade.draw_lines(c_data["grid"], (*BORDER, 70), 1)
                for pts, col in c_data["lines"]:
                    if len(pts) > 1:
                        arcade.draw_line_strip(pts, col[:3], 1.5)

        # Ponto animado (desenhado por cima)
        if self.anim_playing and self._racing_pts and self.anim_index > 0:
            px, py = self._racing_pts[self.anim_index - 1]
            arcade.draw_circle_filled(px, py, 5, RED)
            arcade.draw_circle_outline(px, py, 9, (*RED[:3], 100), 1.5)

        # Textos e UI
        self._draw_header()
        self._draw_map_labels()
        self._draw_chart_labels()
        self._draw_borders()
        self._draw_footer()

    def _draw_header(self):
        draw_box_filled(0, SCREEN_W, SCREEN_H-HEADER_H, SCREEN_H, PANEL)
        draw_box_filled(0, 4, SCREEN_H-HEADER_H, SCREEN_H, RED)
        arcade.draw_text("F1",               10, SCREEN_H-28, RED,   18, bold=True, font_name="monospace")
        arcade.draw_text("TELEMETRY VIEWER", 38, SCREEN_H-28, WHITE, 18, font_name="monospace")
        arcade.draw_text(self.status_msg,   320, SCREEN_H-26, DIM,   11, font_name="monospace")

    def _draw_map_labels(self):
        viz = (f"Volta {self.vis}" if isinstance(self.vis, int) else ("Melhor Volta" if self.vis == "melhor" else "Todas as Voltas"))
        arcade.draw_text(f"MAPA DA PISTA  -  {viz}", MAP_X+10, MAP_Y+MAP_H-18, WHITE, 11, bold=True, font_name="monospace")

        lx = MAP_X + MAP_W - 168
        ly = MAP_Y + MAP_H - 36
        rows = len(self.lap_times)
        draw_box_filled(lx-4, lx+164, ly - rows*17 - 14, ly+10, (*PANEL, 230))
        arcade.draw_text("VOLTAS", lx, ly-2, RED, 9, bold=True, font_name="monospace")
        for i, (lap, t) in enumerate(self.lap_times.items()):
            m, s    = int(t//60), t%60
            is_best = (lap == self.best_lap)
            col     = CENTER_COL[:3] if is_best else DIM
            star    = "* " if is_best else "  "
            arcade.draw_text(f"{star}V{lap}: {m:02d}:{s:06.3f}", lx, ly-20-i*17, col, 9, bold=is_best, font_name="monospace")

    def _draw_chart_labels(self):
        if not hasattr(self, "_chart_meta"): return
        ch, gap, y0, speed_s, throttle_s, brake_s = self._chart_meta

        def _labels(title, y_label, y, h, col_title, vmin, vmax):
            PL, PT, PB = 42, 24, 22
            arcade.draw_text(title,   CHART_X+PL+4, y+h-PT+4, col_title, 10, bold=True, font_name="monospace")
            arcade.draw_text(y_label, CHART_X+12,   y+PB+(h-PT-PB)//2, (*DIM, 200), 9, rotation=90, anchor_x="center", anchor_y="center", font_name="monospace")
            for i in range(5):
                gy  = y + PB + i * (h - PT - PB) / 4
                lbl = vmin + i * (vmax - vmin) / 4
                arcade.draw_text(f"{lbl:.0f}", CHART_X+2, gy-6, (*DIM, 200), 9, font_name="monospace")

        all_sp = [v for vals, _ in speed_s for v in vals]
        vmin_sp = min(all_sp) if all_sp else 0
        vmax_sp = max(all_sp) if all_sp else 1
        _labels("VELOCIDADE",  "km/h", y0+2*(ch+gap), ch, COL_SPEED,    vmin_sp, vmax_sp)
        _labels("ACELERADOR",  "%",    y0+ch+gap,      ch, COL_THROTTLE, 0,       100)
        _labels("FREIO",       "%",    y0,             ch, COL_BRAKE,    0,       100)

    def _draw_borders(self):
        draw_box_outline(MAP_X,   MAP_X+MAP_W, MAP_Y, MAP_Y+MAP_H, BORDER, 1)
        draw_box_outline(CHART_X, CHART_X+CHART_W, CHART_Y, CHART_Y+CHART_H, BORDER, 1)
        gap, ch, y0 = 14, (CHART_H - 14*2)//3, CHART_Y
        for sep_y in (y0+ch+gap//2, y0+2*ch+gap+gap//2):
            arcade.draw_line(CHART_X, sep_y, CHART_X+CHART_W, sep_y, BORDER, 1)

    def _draw_footer(self):
        draw_box_filled(0, SCREEN_W, 0, FOOTER_H, PANEL)
        draw_box_filled(0, SCREEN_W, FOOTER_H, FOOTER_H+1, (*BORDER, 100))
        arcade.draw_text(
            "[B] Melhor Volta   [A] Todas as Voltas   [1-9] Volta Especifica"
            "   [ESPACO] Play/Pause   [R] Reiniciar   [ESC] Sair",
            12, 7, DIM, 10, font_name="monospace")

    def on_key_press(self, key, _mod):
        if   key == arcade.key.ESCAPE: arcade.close_window()
        elif key == arcade.key.B:      self.vis = "melhor"; self._apply_viz()
        elif key == arcade.key.A:      self.vis = "todas";  self._apply_viz()
        elif key == arcade.key.SPACE:
            if self.anim_index >= len(self._racing_pts):
                self.anim_index = 0
            self.anim_playing = not self.anim_playing
        elif key == arcade.key.R:
            self.anim_index = 0; self.anim_playing = False
            self._racing_data = self._racing_pts
        else:
            num_map = {
                arcade.key.KEY_1: 1, arcade.key.NUM_1: 1, arcade.key.KEY_2: 2, arcade.key.NUM_2: 2,
                arcade.key.KEY_3: 3, arcade.key.NUM_3: 3, arcade.key.KEY_4: 4, arcade.key.NUM_4: 4,
                arcade.key.KEY_5: 5, arcade.key.NUM_5: 5, arcade.key.KEY_6: 6, arcade.key.NUM_6: 6,
                arcade.key.KEY_7: 7, arcade.key.NUM_7: 7, arcade.key.KEY_8: 8, arcade.key.NUM_8: 8,
                arcade.key.KEY_9: 9, arcade.key.NUM_9: 9,
            }
            if key in num_map:
                n = num_map[key]
                if n in self.all_laps:
                    self.vis = n; self._apply_viz()
                else:
                    self.status_msg = f"Volta {n} nao encontrada."

def main():
    window = TelemetryWindow()
    arcade.run()

if __name__ == "__main__":
    main()
import fastf1
import matplotlib
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pistas import desenhar_pista



fastf1.Cache.enable_cache(r"scr\providers\cache")
print("Carregando dados da sessão...")

session = fastf1.get_session(2023, "Brazil", "Q")
session.load()

lap = session.laps.pick_fastest()
pos = lap.get_pos_data()

x = lap.telemetry['X']
y = lap.telemetry['Y']
color = lap.telemetry['Speed']

# Matriz de rotação
def rotate(xy, *, angle):
    rot_mat = np.array([[np.cos(angle), np.sin(angle)], [-np.sin(angle), np.cos(angle)]])    
    return np.matmul(xy, rot_mat)

# Rotação do mapa

circuit_info = session.get_circuit_info()
track_angle = circuit_info.rotation / 1 * np.pi

track = pos.loc[:, ('X', 'Y')].to_numpy()
rotated_track = rotate(track, angle=track_angle)

lap_xy = lap.telemetry.loc[:, ('X', 'Y')].to_numpy()
rotated_lap = rotate(lap_xy, angle=track_angle)

x = rotated_lap[:, 0]
y = rotated_lap[:, 1]

point = np.array([x, y]).T.reshape(-1, 1, 2)
segments = np.concatenate([point[:-1], point[1:]], axis=1)

fig, ax = plt.subplots(sharex=True, sharey=True, figsize=(14, 6.75))

plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.12)
ax.axis('off')

ax.plot(x, y, color='black', linestyle='-', linewidth=16, zorder=0)

ax.plot(rotated_track[:, 0], rotated_track[:, 1], color='white', linewidth=2, zorder=1)
print(session)

offset_vector = [500, 0]
for _, corner in circuit_info.corners.iterrows():
    txt = f"{corner['Number']}{corner['Letter']}"

    offset_angle = corner['Angle'] / 180 * np.pi
    offset_x, offset_y = rotate(offset_vector, angle=offset_angle)

    text_x = corner['X'] + offset_x
    text_y = corner['Y'] + offset_y

    text_x, text_y = rotate([text_x, text_y], angle=track_angle)

    track_x, track_y = rotate([corner['X'], corner['Y']], angle=track_angle)

    ax.plot(track_x, track_y, color='black', linestyle = '-', linewidth=16, zorder=0)

    plt.scatter(text_x, text_y, color='grey', s=140)

    plt.plot([track_x, text_x], [track_y, text_y], color='grey')

    plt.text(text_x, text_y, txt,
            va='center_baseline', ha='center', size='small', color='white')


plt.title(session.event['Location'])
plt.xticks([])
plt.yticks([])
plt.axis('equal')
plt.show()
#
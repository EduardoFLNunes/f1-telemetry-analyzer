# Assetto Corsa Opponents Exporter

This is a custom Assetto Corsa Python app. It is not built into Assetto Corsa,
so it must be installed into the simulator's Python apps folder before it can
appear in game.

## Install

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File tools\assetto_opponents_exporter\install_ac_opponents_exporter.ps1
```

If the Assetto Corsa folder is not detected automatically:

```powershell
powershell -ExecutionPolicy Bypass -File tools\assetto_opponents_exporter\install_ac_opponents_exporter.ps1 -AssettoRoot "C:\Program Files (x86)\Steam\steamapps\common\assettocorsa"
```

The installed file should end up here:

```text
<Assetto Corsa>\apps\python\ac_opponents_exporter\ac_opponents_exporter.py
```

## Enable

Enable the Python app/module named `ac_opponents_exporter` or
`Opponents Exporter` in Assetto Corsa or Content Manager. Then open a driving
session and select `Opponents Exporter` from the in-game app bar.

## Expected In-Game Status

The app window should show:

```text
Opponents Exporter: ON
Cars detected: N
Sending: M cars
Last sent: X ms ago
UDP: OK
```

`Cars detected` includes the player car. `Sending` excludes the player and
only includes opponents with a valid `WorldPosition`.

## Backend Check

With the backend running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/live/opponents
```

When a session has AI or multiplayer cars and the exporter is sending, the
response should have `count > 0`, should not include the player car, and the
opponents' `worldPosition` values should change over time.

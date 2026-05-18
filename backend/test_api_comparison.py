import requests
import json

def test_comparison():
    try:
        r = requests.get('http://localhost:8000/api/data/comparison')
        r.raise_for_status()
        data = r.json()
        
        track = data.get('track')
        if not track:
            print("ERROR: No track data in response")
            return
            
        print(f"Track: {track.get('name')}")
        centerline = track.get('centerline', {})
        x = centerline.get('x', [])
        z = centerline.get('z', [])
        print(f"Points: {len(x)}")
        
        if len(x) > 0:
            print(f"Sample X: {x[0]}, Z: {z[0]}")
            
        bounds = track.get('bounds')
        if bounds:
            print(f"Bounds: {bounds}")
        else:
            print("WARNING: No bounds in track data")

        player = data.get('player')
        if player:
            print(f"Player Pos: {player.get('x')}, {player.get('z')}")
        else:
            print("No player telemetry yet")

    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_comparison()

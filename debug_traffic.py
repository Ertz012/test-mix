import pickle
import sys

try:
    with open("traffic_data.bin", "rb") as f:
        data = pickle.load(f)
        print("Keys found:", list(data.keys()))
        for k in data:
            print(f"{k}: {len(data[k])} packets")
            if len(data[k]) > 0:
                print(f"Sample packet: {data[k][0]}")
except Exception as e:
    print(f"Error: {e}")

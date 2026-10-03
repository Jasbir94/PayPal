"""Train the held-out validation Platt/isotonic mappings via ml.fusion.train."""
from ml.fusion.train import train

if __name__ == '__main__':
    result = train()
    print(f"Selected validation calibrator: {result['selected_calibrator']}")

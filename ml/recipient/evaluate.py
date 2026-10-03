"""Print held-out metrics and feature importances for the saved recipient model."""
from ml.training import evaluate_saved_model


if __name__ == '__main__':
    evaluate_saved_model('recipient')

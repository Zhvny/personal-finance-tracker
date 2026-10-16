import numpy as np

from apps.cli.prediction_service import PredictionService


def generate_baseline():
    print("ML Confidence Baseline (Current Sigmoid k=5.1)")
    print("-" * 40)

    # Key Edge Cases
    cases = [
        ("Small return (0.1%), Normal vol (2%)", 0.001, 0.02),
        ("High return (5%), Normal vol (2%)", 0.05, 0.02),
        ("Normal return (1%), High vol (10%)", 0.01, 0.10),
        ("Normal return (1%), Extreme vol (50%)", 0.01, 0.50),
        ("Zero return, Normal vol (2%)", 0.0, 0.02),
    ]

    for desc, r, v in cases:
        conf = PredictionService.calculate_confidence(r, v)
        score = abs(r) / (v + 1e-8)
        print(f"{desc:40} | Score: {score:.4f} | Conf: {conf:.4%}")

    # Clustering Check (similar to test_confidence_distribution_spread)
    returns = np.linspace(-0.1, 0.1, 20)
    volatilities = np.linspace(0.01, 0.05, 20)
    samples = []
    for r in returns:
        for v in volatilities:
            conf = PredictionService.calculate_confidence(r, v)
            samples.append(conf)

    samples = np.array(samples)
    cluster_count = np.sum((samples >= 0.05) & (samples <= 0.15))
    print("-" * 40)
    print(f"Clustering (5-15%): {cluster_count/len(samples):.2%}")
    print(f"Max Confidence:     {np.max(samples):.2%}")
    print(f"Min Confidence:     {np.min(samples):.2%}")
    print(f"Mean Confidence:    {np.mean(samples):.2%}")

if __name__ == "__main__":
    generate_baseline()

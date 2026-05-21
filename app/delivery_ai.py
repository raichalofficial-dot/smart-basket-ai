import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import joblib
import os
from django.conf import settings

MODEL_PATH = os.path.join(settings.BASE_DIR, 'delivery_eta_model.joblib')

def train_delivery_model():
    """
    Simulates training a model with a sample dataset for the college project.
    Features: [Distance(km), Traffic(1-3), PendingOrders, AgentsAvailable]
    """
    data = [
        [2.0, 1, 5, 10, 15],
        [5.0, 1, 10, 8, 25],
        [10.0, 2, 20, 5, 60],
        [15.0, 3, 50, 2, 120],
        [1.0, 1, 2, 15, 10],
        [3.5, 2, 15, 7, 35],
        [12.0, 3, 30, 4, 90],
        [8.0, 1, 5, 9, 30],
        [4.0, 2, 25, 6, 45],
        [6.0, 3, 10, 5, 55],
    ]

    df = pd.DataFrame(data, columns=['distance', 'traffic', 'pending', 'agents', 'eta'])

    X = df[['distance', 'traffic', 'pending', 'agents']]
    y = df['eta']

    model = LinearRegression()
    model.fit(X, y)

    joblib.dump(model, MODEL_PATH)
    print("AI Delivery Model trained and saved successfully.")
    return model

def predict_delivery_eta(distance, traffic_level, pending_orders, agents_available):
    """
    Predicts ETA in minutes using the trained model.
    traffic_level: 'LOW', 'MEDIUM', 'HIGH'
    """
    traffic_map = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
    traffic_score = traffic_map.get(traffic_level.upper(), 1)

    if not os.path.exists(MODEL_PATH):
        model = train_delivery_model()
    else:
        model = joblib.load(MODEL_PATH)

    input_data = np.array([[distance, traffic_score, pending_orders, agents_available]])
    prediction = model.predict(input_data)

    return max(15, int(prediction[0]))

if __name__ == "__main__":
    train_delivery_model()
    test_eta = predict_delivery_eta(5.5, 'MEDIUM', 12, 8)
    print(f"Predicted ETA for 5.5km with Medium traffic: {test_eta} mins")

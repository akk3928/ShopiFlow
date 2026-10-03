```python
import os
import joblib
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class InventoryPredictionModel:
    """Machine learning model for ShopiFlow inventory forecasting."""

    def __init__(
        self,
        model_path="models/inventory_prediction.pkl"
    ):
        self.model = RandomForestRegressor(
            n_estimators=100,
            random_state=42
        )
        self.model_path = model_path

    def prepare_data(self, data: pd.DataFrame):
        """Prepare inventory data for model training."""

        required_columns = [
            "day_of_week",
            "month",
            "current_stock",
            "quantity_sold",
            "inventory_demand"
        ]

        missing = [
            column for column in required_columns
            if column not in data.columns
        ]

        if missing:
            raise ValueError(
                f"Missing required columns: {missing}"
            )

        X = data[
            [
                "day_of_week",
                "month",
                "current_stock",
                "quantity_sold"
            ]
        ]

        y = data["inventory_demand"]

        return X, y

    def train(self, data: pd.DataFrame):
        """Train the inventory prediction model."""

        X, y = self.prepare_data(data)

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42
        )

        self.model.fit(X_train, y_train)

        predictions = self.model.predict(X_test)

        metrics = {
            "mae": mean_absolute_error(y_test, predictions),
            "rmse": mean_squared_error(
                y_test,
                predictions
            ) ** 0.5,
            "r2": r2_score(y_test, predictions)
        }

        return metrics

    def predict(
        self,
        day_of_week: int,
        month: int,
        current_stock: int,
        quantity_sold: int
    ):
        """Predict future inventory demand."""

        input_data = pd.DataFrame(
            [
                {
                    "day_of_week": day_of_week,
                    "month": month,
                    "current_stock": current_stock,
                    "quantity_sold": quantity_sold
                }
            ]
        )

        prediction = self.model.predict(input_data)

        return float(prediction[0])

    def save_model(self):
        """Save trained model to disk."""

        directory = os.path.dirname(self.model_path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        joblib.dump(self.model, self.model_path)

    def load_model(self):
        """Load a previously trained model."""

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Model not found: {self.model_path}"
            )

        self.model = joblib.load(self.model_path)

        return self.model
```


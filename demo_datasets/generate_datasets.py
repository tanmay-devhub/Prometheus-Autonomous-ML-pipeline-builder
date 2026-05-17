"""Run this script once to generate demo datasets."""
import pandas as pd
import numpy as np

np.random.seed(42)

# Titanic-like dataset
n = 891
titanic = pd.DataFrame({
    "PassengerId": range(1, n + 1),
    "Survived": np.random.choice([0, 1], n, p=[0.62, 0.38]),
    "Pclass": np.random.choice([1, 2, 3], n, p=[0.24, 0.21, 0.55]),
    "Name": [f"Person_{i}" for i in range(n)],
    "Sex": np.random.choice(["male", "female"], n, p=[0.65, 0.35]),
    "Age": np.where(np.random.random(n) < 0.2, np.nan, np.random.normal(29, 14, n).clip(1, 80)),
    "SibSp": np.random.choice([0, 1, 2, 3], n, p=[0.68, 0.23, 0.06, 0.03]),
    "Parch": np.random.choice([0, 1, 2], n, p=[0.76, 0.13, 0.11]),
    "Fare": np.random.exponential(32, n).round(2),
    "Embarked": np.random.choice(["S", "C", "Q", None], n, p=[0.72, 0.19, 0.08, 0.01]),
})
titanic.to_csv("titanic.csv", index=False)

# Heart disease-like dataset
n2 = 303
heart = pd.DataFrame({
    "age": np.random.randint(29, 77, n2),
    "sex": np.random.choice([0, 1], n2),
    "cp": np.random.choice([0, 1, 2, 3], n2),
    "trestbps": np.random.normal(131, 17, n2).round().astype(int).clip(94, 200),
    "chol": np.random.normal(246, 51, n2).round().astype(int).clip(126, 564),
    "fbs": np.random.choice([0, 1], n2, p=[0.85, 0.15]),
    "restecg": np.random.choice([0, 1, 2], n2, p=[0.48, 0.50, 0.02]),
    "thalach": np.random.normal(149, 22, n2).round().astype(int).clip(71, 202),
    "exang": np.random.choice([0, 1], n2, p=[0.67, 0.33]),
    "oldpeak": np.random.exponential(1.0, n2).round(1).clip(0, 6.2),
    "slope": np.random.choice([0, 1, 2], n2),
    "ca": np.random.choice([0, 1, 2, 3], n2, p=[0.58, 0.22, 0.12, 0.08]),
    "thal": np.random.choice([1, 2, 3], n2, p=[0.06, 0.55, 0.39]),
    "target": np.random.choice([0, 1], n2, p=[0.46, 0.54]),
})
heart.to_csv("heart_disease.csv", index=False)

print("Generated titanic.csv and heart_disease.csv")

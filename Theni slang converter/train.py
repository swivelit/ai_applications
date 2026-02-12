import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
import joblib
import os

df = pd.read_csv("data/theni_dataset.csv")

X = df["normal"]
y = df["theni"]

vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2,4))
X_vec = vectorizer.fit_transform(X)

model = LinearSVC()
model.fit(X_vec, y)

os.makedirs("models", exist_ok=True)
joblib.dump(model, "models/model.pkl")
joblib.dump(vectorizer, "models/vectorizer.pkl")

print("✅ Training completed. Model saved.")

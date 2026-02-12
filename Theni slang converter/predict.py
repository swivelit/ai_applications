import joblib

model = joblib.load("models/model.pkl")
vectorizer = joblib.load("models/vectorizer.pkl")

def convert(text):
    X = vectorizer.transform([text])
    return model.predict(X)[0]

if __name__ == "__main__":
    while True:
        t = input("Tamil text: ")
        print(convert(t))

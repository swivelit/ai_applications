import pandas as pd
import string
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# ----------------------------
# STEP 1: Load Dataset
# ----------------------------
data = pd.read_csv("dataset.csv")

# ----------------------------
# STEP 2: Preprocessing
# ----------------------------
def preprocess(text):
    text = str(text).lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text

data["text"] = data["text"].apply(preprocess)

# ----------------------------
# STEP 3: Train-Test Split
# ----------------------------
X_train, X_test, y_train, y_test = train_test_split(
    data["text"], data["label"],
    test_size=0.2,
    random_state=42
)

# ----------------------------
# STEP 4: TF-IDF Vectorization
# ----------------------------
vectorizer = TfidfVectorizer()
X_train_tfidf = vectorizer.fit_transform(X_train)

# ----------------------------
# STEP 5: Train Model
# ----------------------------
model = LogisticRegression()
model.fit(X_train_tfidf, y_train)

# ----------------------------
# STEP 6: User Input Execution
# ----------------------------
print("\n=== Multilingual Text Classification System ===")

while True:
    user_input = input("\nEnter text (or type 'exit' to stop): ")

    if user_input.lower() == "exit":
        print("System stopped.")
        break

    # Preprocess input
    cleaned_text = preprocess(user_input)

    # Convert to TF-IDF
    input_vector = vectorizer.transform([cleaned_text])

    # Predict
    prediction = model.predict(input_vector)[0]

    print("Classified Output:", prediction)
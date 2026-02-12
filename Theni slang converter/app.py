import tkinter as tk
import joblib

model = joblib.load("models/model.pkl")
vectorizer = joblib.load("models/vectorizer.pkl")

def convert():
    text = input_text.get("1.0", tk.END).strip()
    X = vectorizer.transform([text])
    result = model.predict(X)[0]
    output_text.delete("1.0", tk.END)
    output_text.insert(tk.END, result)

root = tk.Tk()
root.title("Normal Tamil → Theni Slang")

tk.Label(root, text="Normal Slang Tamil").pack()
input_text = tk.Text(root, height=5, width=60)
input_text.pack()

tk.Button(root, text="Convert", command=convert).pack()

tk.Label(root, text="Theni Slang Output").pack()
output_text = tk.Text(root, height=5, width=60)
output_text.pack()

root.mainloop()

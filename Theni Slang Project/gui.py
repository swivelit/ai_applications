import tkinter as tk
from converter import tamil_to_theni

def convert_text():
    input_text = input_box.get("1.0", tk.END).strip()
    if not input_text:
        output_label.config(text="⚠️ Tamil text enter பண்ணுங்க")
        return

    output = tamil_to_theni(input_text)
    output_box.delete("1.0", tk.END)
    output_box.insert(tk.END, output)


# -----------------------
# GUI Window
# -----------------------
root = tk.Tk()
root.title("Tamil → Theni Slang Converter")
root.geometry("520x380")
root.resizable(False, False)

# Title
title = tk.Label(
    root,
    text="🔥 Tamil → Theni Slang Converter 🔥",
    font=("Arial", 16, "bold")
)
title.pack(pady=10)

# Input Label
tk.Label(root, text="Normal Tamil:", font=("Arial", 12)).pack(anchor="w", padx=20)

# Input Text Box
input_box = tk.Text(root, height=4, width=55, font=("Arial", 12))
input_box.pack(padx=20, pady=5)

# Convert Button
btn = tk.Button(
    root,
    text="Convert → Theni",
    font=("Arial", 12, "bold"),
    bg="#4CAF50",
    fg="white",
    command=convert_text
)
btn.pack(pady=10)

# Output Label
tk.Label(root, text="Theni Slang:", font=("Arial", 12)).pack(anchor="w", padx=20)

# Output Text Box
output_box = tk.Text(root, height=4, width=55, font=("Arial", 12), fg="blue")
output_box.pack(padx=20, pady=5)

# Footer
footer = tk.Label(
    root,
    text="Made with ❤️ for Theni Tamil",
    font=("Arial", 9)
)
footer.pack(pady=10)

# Run App
root.mainloop()

from googletrans import Translator

translator = Translator()

tamil_text = input("Enter Theni Tamil text: ")
result = translator.translate(tamil_text, src='ta', dest='en')

print("English Translation:", result.text)
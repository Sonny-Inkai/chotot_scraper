from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
print(GEMINI_API_KEY)

# Khởi tạo client theo SDK google-genai mới
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-3.1-flash-lite-preview"

response = client.models.generate_content(
    model=MODEL_ID,
    contents="What is the weather in New York?",

)

print(response.text)
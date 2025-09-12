import openai
openai.api_key = "your-api-key"

try:
    response = openai.Model.list()
    print("API key is valid!")
except Exception as e:
    print(f"Error: {e}")
    
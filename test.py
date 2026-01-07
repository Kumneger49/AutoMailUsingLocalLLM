
from ollama import generate
import time
# Connect to your local Ollama instance
email_content = "Hi Kumneger, can you send me the latest project report by today?"

prompt = f"""
Instruction: Write a concise, professional reply to this email.
Email: "{email_content}"
"""
# Call your local model
start_time = time.time()
response = generate(model="llama3.2:latest", prompt=prompt)
end_time = time.time()
print("Draft reply:\n", response)
print(f"took: {end_time-start_time}:.2f")


import scratchattach as r3
import requests
import json
import os
from better_profanity import profanity

# --- CONFIGURATION (Uses GitHub Secrets) ---
USERNAME = os.getenv('SCRATCH_USERNAME')
SESSION_ID = os.getenv('SCRATCH_SESSION_ID')
PROJECT_ID = os.getenv('SCRATCH_PROJECT_ID')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_KEY')
MODEL = "google/gemma-2-9b-it:free"

# --- THE ENCODER/DECODER (00=Space, 01=a, 02=b...) ---
CHARS = " abcdefghijklmnopqrstuvwxyz0123456789-.,!?@"

def decode_scratch(text):
    decoded = ""
    text = str(text)
    for i in range(0, len(text), 2):
        chunk = text[i:i+2]
        if len(chunk) == 2:
            try:
                index = int(chunk)
                if index < len(CHARS):
                    decoded += CHARS[index]
            except: continue
    return decoded

def encode_scratch(text):
    encoded = ""
    for char in text.lower():
        if char in CHARS:
            index = CHARS.index(char)
            # zfill(2) ensures 5 becomes "05"
            encoded += str(index).zfill(2)
    return encoded

# --- AI & CONNECTION ---
session = r3.Session(SESSION_ID, username=USERNAME)
client = session.connect_cloud(PROJECT_ID)
events = r3.CloudEvents(PROJECT_ID)

@events.event
def on_set(event):
    if event.var == "INPUT":
        # Ignore if Scratch sets it to 00 (the reset signal)
        if event.value == "00" or not event.value:
            return

        prompt = decode_scratch(event.value)
        print(f"Scratch Request: {prompt}")

        try:
            # 1. Fetch from AI
            response = requests.post(
                url="https://openrouter.ai",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant for a Scratch project. Keep all replies strictly PG, short, and safe for children."},
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=25
            )
            response.raise_for_status()
            ai_reply = response.json()['choices']['message']['content']

            # 2. Filter Content (The "Don't get banned" step)
            safe_reply = profanity.censor(ai_reply)

            # 3. Encode and send to Scratch
            # Limit to 120 chars so the 256-digit cloud limit isn't hit
            encoded_output = encode_scratch(safe_reply[:120])
            client.set_var("OUTPUT", encoded_output)
            print(f"AI Response: {safe_reply[:120]}")

        except Exception as e:
            print(f"Error encountered: {e}")
            # Sends encoded "failed to fetch" back to Scratch
            client.set_var("OUTPUT", encode_scratch("failed to fetch"))

print("--- Bridge is ONLINE ---")
print(f"Monitoring Project: {PROJECT_ID}")
events.start()

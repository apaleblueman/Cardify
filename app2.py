import tkinter as tk
from tkinter import filedialog, messagebox
import json
import requests
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import ttkbootstrap as ttk

# ========================== GLOBAL VARIABLES ==========================
flashcards = []
current_card_index = 0
is_dark_mode = False

# ========================== THEME SETTINGS ==========================
light_theme = {
    "bg": "#ffffff",
    "fg": "#000000",
    "entry_bg": "#ffffff",
    "entry_fg": "#000000",
    "button_bg": "#f0f0f0",
    "button_fg": "#000000",
    "highlight": "#dcdcdc"
}

dark_theme = {
    "bg": "#2e2e2e",
    "fg": "#ffffff",
    "entry_bg": "#3c3c3c",
    "entry_fg": "#ffffff",
    "button_bg": "#444444",
    "button_fg": "#ffffff",
    "highlight": "#555555"
}

def toggle_dark_mode():
    global is_dark_mode
    theme = dark_theme if not is_dark_mode else light_theme
    is_dark_mode = not is_dark_mode

    root.config(bg=theme["bg"])
    for frame in [top_frame, btn_frame, question_frame, answer_frame, action_frame, nav_frame]:
        frame.config(bg=theme["bg"])

    api_key_entry.config(bg=theme["entry_bg"], fg=theme["entry_fg"], insertbackground=theme["fg"])
    question_label.config(bg=theme["bg"], fg=theme["fg"])
    answer_label.config(bg=theme["bg"], fg=theme["fg"])

    # Update buttons
    for widget in root.winfo_children():
        if isinstance(widget, ttk.Button):
            widget.config(bg=theme["button_bg"], fg=theme["button_fg"], activebackground=theme["highlight"])
        elif isinstance(widget, ttk.Frame):
            for sub in widget.winfo_children():
                if isinstance(sub, ttk.Button):
                    sub.config(bg=theme["button_bg"], fg=theme["button_fg"], activebackground=theme["highlight"])

# ========================== FUNCTIONALITY ==========================
def upload_image(image_path, creds):
    try:
        messagebox.showinfo("Processing", "Uploading image for OCR processing...")

        drive_service = build("drive", "v3", credentials=creds)
        file_metadata = {
            "name": f"ocr_image_{int(time.time())}.jpg",
            "mimeType": "application/vnd.google-apps.document"
        }
        media = MediaFileUpload(image_path, mimetype="image/jpeg")
        file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        file_id = file.get("id")

        if not file_id:
            raise Exception("Failed to upload the image.")

        for _ in range(10):
            time.sleep(3)
            try:
                doc_service = build("docs", "v1", credentials=creds)
                doc = doc_service.documents().get(documentId=file_id).execute()
                if doc and "body" in doc:
                    break
            except Exception as e:
                print(f"Retry failed: {e}")

        messagebox.showinfo("Processing", "Extracting text from OCR document...")

        extracted_text = ""
        for content in doc.get("body", {}).get("content", []):
            if "paragraph" in content:
                for element in content["paragraph"].get("elements", []):
                    if "textRun" in element:
                        extracted_text += element["textRun"]["content"]

        return extracted_text.strip()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to extract text: {e}")
        return ""

def generate_qa_with_gpt4(text, api_key):
    try:
        if not text.strip():
            raise ValueError("Extracted text is empty!")

        messagebox.showinfo("Processing", "Generating flashcards with AI...")

        url = "https://api.together.xyz/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        prompt = f"""
        Convert the following text into **flashcards (question-answer format)**:
        {text}

        Format:
        ❓ What was the Treaty of Versailles?
        ✅ It was a peace treaty that ended World War I.
        """
        data = {
            "model": "mistralai/Mistral-7B-Instruct-v0.1",
            "messages": [{"role": "user", "content": prompt}]
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code} - {response.text}")

        response_text = response.json()['choices'][0]['message']['content']

        flashcard_pairs = []
        question = ""

        for line in response_text.split("\n"):
            line = line.strip()
            if line.startswith("❓"):
                question = line.replace("❓", "").strip()
            elif line.startswith("✅"):
                answer = line.replace("✅", "").strip()
                if question:
                    flashcard_pairs.append({"question": question, "answer": answer})
                    question = ""

        return flashcard_pairs

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate flashcards: {e}")
        return []

def process_image():
    global flashcards, current_card_index

    google_credentials = filedialog.askopenfilename(title="Select Google API Credentials", filetypes=[("JSON Files", "*.json")])
    together_api_key = api_key_entry.get().strip()
    image_path = filedialog.askopenfilename(title="Select Image File", filetypes=[("Image Files", "*.jpg *.jpeg *.png")])

    if not google_credentials or not together_api_key or not image_path:
        messagebox.showerror("Error", "Please provide all required inputs!")
        return

    try:
        creds = service_account.Credentials.from_service_account_file(
            google_credentials,
            scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents"]
        )

        extracted_text = upload_image(image_path, creds)
        if extracted_text:
            flashcards = generate_qa_with_gpt4(extracted_text, together_api_key)
            current_card_index = 0
            show_flashcard()
        else:
            messagebox.showerror("Error", "No text extracted from the image.")

    except Exception as e:
        messagebox.showerror("Error", str(e))

def show_flashcard():
    global current_card_index, flashcards

    if not flashcards:
        messagebox.showerror("Error", "No flashcards available!")
        return

    card = flashcards[current_card_index]
    question_label.config(text=f"Q: {card['question']}")
    answer_label.config(text="Click 'Show Answer' to reveal")

def show_answer():
    global current_card_index, flashcards

    if not flashcards:
        return

    card = flashcards[current_card_index]
    answer_label.config(text=f"A: {card['answer']}")

def next_card():
    global current_card_index, flashcards

    if current_card_index < len(flashcards) - 1:
        current_card_index += 1
        show_flashcard()
    else:
        messagebox.showinfo("End", "No more flashcards!")

def prev_card():
    global current_card_index
    if current_card_index > 0:
        current_card_index -= 1
        show_flashcard()
    else:
        messagebox.showinfo("Start", "This is the first flashcard!")

def save_deck():
    global flashcards
    if not flashcards:
        messagebox.showerror("Error", "No flashcards to save!")
        return

    file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
    if file_path:
        with open(file_path, "w") as f:
            json.dump(flashcards, f, indent=4)
        messagebox.showinfo("Saved", "Flashcards saved successfully!")

def load_deck():
    global flashcards, current_card_index
    file_path = filedialog.askopenfilename(title="Load Flashcard Deck", filetypes=[("JSON Files", "*.json")])
    if not file_path:
        return

    try:
        with open(file_path, "r") as f:
            flashcards = json.load(f)

        current_card_index = 0
        show_flashcard()
        messagebox.showinfo("Loaded", "Flashcards loaded successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load flashcards: {e}")

# ========================== GUI SETUP ==========================
root = ttk.Window(themename="superhero")
root.title("Flashcard Generator")
root.geometry("700x600")
root.resizable(False, False)

# Top Entry Section
top_frame = ttk.Frame(root)
top_frame.pack(pady=10)

ttk.Label(top_frame, text="Together AI API Key:").grid(row=0, column=0, padx=5)
api_key_entry = ttk.Entry(top_frame, width=40, font=("Arial", 10))
api_key_entry.grid(row=0, column=1, padx=5)

# Action Buttons
btn_frame = ttk.Frame(root)
btn_frame.pack(pady=5)

ttk.Button(btn_frame, text="Process Image", width=15, command=process_image).grid(row=0, column=0, padx=5)
ttk.Button(btn_frame, text="Load Deck", width=15, command=load_deck).grid(row=0, column=1, padx=5)

# Flashcard Display
question_frame = ttk.Frame(root)
question_frame.pack(pady=15)

question_label = ttk.Label(question_frame, text="Q: [No Flashcards Yet]", font=("Arial", 14, "bold"), wraplength=460, justify="center")
question_label.pack(padx=10)

answer_frame = ttk.Frame(root)
answer_frame.pack(pady=10)

answer_label = ttk.Label(answer_frame, text="Click 'Show Answer' to reveal", font=("Arial", 12), foreground="blue", wraplength=460, justify="center")
answer_label.pack(padx=10)

# Navigation and Toggle
action_frame = ttk.Frame(root)
action_frame.pack(pady=10)
ttk.Button(action_frame, text="Show Answer", width=20, command=show_answer).grid(row=0, column=0, pady=5)

nav_frame = ttk.Frame(root)
nav_frame.pack(pady=5)

ttk.Button(nav_frame, text="Previous", width=10, command=prev_card).grid(row=0, column=0, padx=5)
ttk.Button(nav_frame, text="Next", width=10, command=next_card).grid(row=0, column=1, padx=5)
ttk.Button(nav_frame, text="Save Deck", width=10, command=save_deck).grid(row=0, column=2, padx=5)

root.mainloop()

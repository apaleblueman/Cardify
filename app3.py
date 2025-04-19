import tkinter as tk
from tkinter import filedialog, messagebox
import json
import requests
import time
import random
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import ttkbootstrap as ttk
from PIL import Image, ImageTk

# ========================== GLOBAL VARIABLES ==========================
original_flashcards = []
flashcards = []
current_card_index = 0
current_image_path = None
displayed_image = None

# Feedback counters
easy_count = 0
medium_count = 0
hard_count = 0

# ========================== FUNCTIONALITY ==========================
def shuffle_deck():
    global flashcards, current_card_index
    flashcards = [dict(card) for card in original_flashcards]  # Full list with tags
    random.shuffle(flashcards)
    current_card_index = 0
    show_flashcard()

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
                    flashcard_pairs.append({"question": question, "answer": answer, "tag": None})
                    question = ""

        return flashcard_pairs

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate flashcards: {e}")
        return []

def process_image():
    global flashcards, original_flashcards, current_card_index, current_image_path
    google_credentials = filedialog.askopenfilename(title="Select Google API Credentials", filetypes=[("JSON Files", "*.json")])
    together_api_key = api_key_entry.get().strip()
    image_path = filedialog.askopenfilename(title="Select Image File", filetypes=[("Image Files", "*.jpg *.jpeg *.png")])

    if not google_credentials or not together_api_key or not image_path:
        messagebox.showerror("Error", "Please provide all required inputs!")
        return

    try:
        current_image_path = image_path
        creds = service_account.Credentials.from_service_account_file(
            google_credentials,
            scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents"]
        )

        extracted_text = upload_image(image_path, creds)
        if extracted_text:
            original_flashcards.clear()
            flashcards.clear()
            generated = generate_qa_with_gpt4(extracted_text, together_api_key)
            original_flashcards.extend(generated)
            flashcards.extend(generated)
            current_card_index = 0
            reset_counters()
            show_flashcard()
        else:
            messagebox.showerror("Error", "No text extracted from the image.")

    except Exception as e:
        messagebox.showerror("Error", str(e))

def show_flashcard():
    global current_card_index, flashcards, current_image_path, displayed_image
    if not flashcards:
        messagebox.showerror("Error", "No flashcards available!")
        return
    card = flashcards[current_card_index]
    question_label.config(text=f"Q: {card['question']}")
    answer_label.config(text="Click 'Show Answer' to reveal")

    if current_image_path:
        try:
            img = Image.open(current_image_path)
            img = img.resize((250, 250))
            displayed_image = ImageTk.PhotoImage(img)
            image_label.config(image=displayed_image)
        except Exception as e:
            print(f"Failed to load image: {e}")

def show_answer():
    global current_card_index, flashcards
    if not flashcards:
        return
    card = flashcards[current_card_index]
    answer_label.config(text=f"A: {card['answer']}")

def mark_feedback(level):
    global easy_count, medium_count, hard_count, current_card_index
    if not flashcards or current_card_index >= len(flashcards):
        messagebox.showinfo("Done", "No more flashcards to tag!")
        return

    card = flashcards[current_card_index]

    # Update original_flashcards tag
    prev_tag = None
    for original_card in original_flashcards:
        if original_card["question"] == card["question"] and original_card["answer"] == card["answer"]:
            prev_tag = original_card.get("tag")
            original_card["tag"] = level
            break

    # Update visible flashcards too
    card["tag"] = level

    if prev_tag == "easy":
        easy_count -= 1
    elif prev_tag == "medium":
        medium_count -= 1
    elif prev_tag == "hard":
        hard_count -= 1

    if level == "easy":
        easy_count += 1
    elif level == "medium":
        medium_count += 1
    elif level == "hard":
        hard_count += 1

    update_counters()
    next_card()

def update_counters():
    easy_label.config(text=f"Easy: {easy_count}")
    medium_label.config(text=f"Medium: {medium_count}")
    hard_label.config(text=f"Hard: {hard_count}")

def reset_counters():
    global easy_count, medium_count, hard_count, current_card_index, flashcards
    easy_count = medium_count = hard_count = 0
    current_card_index = 0
    for card in original_flashcards:
        card["tag"] = None
    flashcards = [dict(card) for card in original_flashcards]
    update_counters()
    show_flashcard()

def shuffle_by_tag(tag):
    global flashcards, current_card_index
    filtered = [dict(card) for card in original_flashcards if card.get("tag") == tag]
    if not filtered:
        messagebox.showinfo("No Cards", f"No cards tagged as '{tag}'")
        return
    flashcards = filtered
    current_card_index = 0
    show_flashcard()

def next_card():
    global current_card_index
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
    if not flashcards:
        messagebox.showerror("Error", "No flashcards to save!")
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
    if file_path:
        with open(file_path, "w") as f:
            json.dump(original_flashcards, f, indent=4)
        messagebox.showinfo("Saved", "Flashcards saved successfully!")

def load_deck():
    global original_flashcards, flashcards, current_card_index
    file_path = filedialog.askopenfilename(title="Load Flashcard Deck", filetypes=[("JSON Files", "*.json")])
    if not file_path:
        return
    try:
        with open(file_path, "r") as f:
            loaded = json.load(f)
        original_flashcards = [dict(card) for card in loaded]
        flashcards = [dict(card) for card in loaded]
        current_card_index = 0
        reset_counters()
        show_flashcard()
        messagebox.showinfo("Loaded", "Flashcards loaded successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load flashcards: {e}")

# ========================== GUI SETUP ==========================
root = ttk.Window(themename="darkly")
root.title("Flashcard Generator")
root.geometry("850x720")
root.resizable(False, False)

# Top Input
top_frame = ttk.Frame(root)
top_frame.pack(pady=10)

ttk.Label(top_frame, text="Together AI API Key:").grid(row=0, column=0, padx=5)
api_key_entry = ttk.Entry(top_frame, width=40, font=("Arial", 10))
api_key_entry.grid(row=0, column=1, padx=5)

# File Actions
btn_frame = ttk.Frame(root)
btn_frame.pack(pady=5)

ttk.Button(btn_frame, text="Process Image", width=15, command=process_image).grid(row=0, column=0, padx=5)
ttk.Button(btn_frame, text="Load Deck", width=15, command=load_deck).grid(row=0, column=1, padx=5)
ttk.Button(btn_frame, text="Save Deck", width=15, command=save_deck).grid(row=0, column=2, padx=5)

# Main Display
main_frame = ttk.Frame(root)
main_frame.pack(pady=10)

image_frame = ttk.Frame(main_frame)
image_frame.grid(row=0, column=0, padx=15)

image_label = ttk.Label(image_frame)
image_label.pack()

flashcard_frame = ttk.Frame(main_frame)
flashcard_frame.grid(row=0, column=1)

question_label = ttk.Label(flashcard_frame, text="Q: [No Flashcards Yet]", font=("Arial", 14, "bold"),
                           wraplength=360, justify="center", foreground="white")
question_label.pack(padx=10, pady=10)

answer_label = ttk.Label(flashcard_frame, text="Click 'Show Answer' to reveal", font=("Arial", 12),
                         foreground="light blue", wraplength=360, justify="center")
answer_label.pack(padx=10, pady=5)

# Feedback Buttons
feedback_frame = ttk.Frame(root)
feedback_frame.pack(pady=5)

ttk.Button(feedback_frame, text="Easy", width=10, command=lambda: mark_feedback("easy")).grid(row=0, column=0, padx=5)
ttk.Button(feedback_frame, text="Medium", width=10, command=lambda: mark_feedback("medium")).grid(row=0, column=1, padx=5)
ttk.Button(feedback_frame, text="Hard", width=10, command=lambda: mark_feedback("hard")).grid(row=0, column=2, padx=5)
ttk.Button(feedback_frame, text="Reset", width=10, command=reset_counters).grid(row=0, column=3, padx=5)

# Counter Display
counter_frame = ttk.Frame(root)
counter_frame.pack(pady=5)

easy_label = ttk.Label(counter_frame, text="Easy: 0")
easy_label.grid(row=0, column=0, padx=10)
medium_label = ttk.Label(counter_frame, text="Medium: 0")
medium_label.grid(row=0, column=1, padx=10)
hard_label = ttk.Label(counter_frame, text="Hard: 0")
hard_label.grid(row=0, column=2, padx=10)

# Shuffle Filter
filter_frame = ttk.Frame(root)
filter_frame.pack(pady=5)
ttk.Button(filter_frame, text="Show Only Hard", command=lambda: shuffle_by_tag("hard")).grid(row=0, column=0, padx=10)
ttk.Button(filter_frame, text="Show Only Medium", command=lambda: shuffle_by_tag("medium")).grid(row=0, column=1, padx=10)
ttk.Button(filter_frame, text="Shuffle Deck", command=shuffle_deck).grid(row=0, column=2, padx=10)

# Navigation
action_frame = ttk.Frame(root)
action_frame.pack(pady=5)
ttk.Button(action_frame, text="Show Answer", width=20, command=show_answer).grid(row=0, column=0, pady=5)

nav_frame = ttk.Frame(root)
nav_frame.pack(pady=5)
ttk.Button(nav_frame, text="Previous", width=10, command=prev_card).grid(row=0, column=0, padx=5)
ttk.Button(nav_frame, text="Next", width=10, command=next_card).grid(row=0, column=1, padx=5)

root.mainloop()

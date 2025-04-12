import tkinter as tk
from tkinter import filedialog, messagebox
import json
import requests
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# Global variables to store flashcards and current index
flashcards = []
current_card_index = 0

def upload_image(image_path, creds):
    """Uploads an image to Google Drive and extracts OCR text."""
    try:
        messagebox.showinfo("Processing", "Uploading image for OCR processing...")
        
        drive_service = build("drive", "v3", credentials=creds)
        file_metadata = {
            "name": "ocr_image.jpg",
            "mimeType": "application/vnd.google-apps.document"
        }
        media = MediaFileUpload(image_path, mimetype="image/jpeg")
        file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        file_id = file.get("id")

        if not file_id:
            raise Exception("Failed to upload the image.")

        # Wait until OCR is processed (polling method)
        for _ in range(10):  
            time.sleep(3)  # Check every 3 seconds
            doc_service = build("docs", "v1", credentials=creds)
            try:
                doc = doc_service.documents().get(documentId=file_id).execute()
                if doc and "body" in doc:
                    break
            except:
                pass  # Retry until it succeeds

        messagebox.showinfo("Processing", "Extracting text from OCR document...")
        
        # Extract text from Google Docs OCR output
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
    """Generate Q&A pairs using Together AI."""
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

        # Convert the response into a flashcard dictionary
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
    """Main function to handle image selection, OCR, and AI processing."""
    global flashcards, current_card_index
    
    google_credentials = filedialog.askopenfilename(title="Select Google API Credentials", filetypes=[("JSON Files", "*.json")])
    together_api_key = api_key_entry.get().strip()
    
    image_path = filedialog.askopenfilename(
        title="Select Image File",
        filetypes=[("Image Files", "*.jpg *.jpeg *.png"), ("All Files", "*.*")]
    )
    
    if not google_credentials or not together_api_key or not image_path:
        messagebox.showerror("Error", "Please provide all required inputs!")
        return
    
    try:
        # Load Google credentials
        creds = service_account.Credentials.from_service_account_file(
            google_credentials, scopes=["https://www.googleapis.com/auth/drive"]
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
    """Displays the current flashcard."""
    global current_card_index, flashcards

    if not flashcards:
        messagebox.showerror("Error", "No flashcards available!")
        return

    card = flashcards[current_card_index]
    question_label.config(text=f"Q: {card['question']}")
    answer_label.config(text="Click 'Show Answer' to reveal")

def show_answer():
    """Reveals the answer to the current flashcard."""
    global current_card_index, flashcards

    if not flashcards:
        return
    
    card = flashcards[current_card_index]
    answer_label.config(text=f"A: {card['answer']}")

def next_card():
    """Moves to the next flashcard."""
    global current_card_index, flashcards

    if current_card_index < len(flashcards) - 1:
        current_card_index += 1
        show_flashcard()
    else:
        messagebox.showinfo("End", "No more flashcards!")

def prev_card():
    """Moves to the previous flashcard."""
    global current_card_index

    if current_card_index > 0:
        current_card_index -= 1
        show_flashcard()
    else:
        messagebox.showinfo("Start", "This is the first flashcard!")

def save_deck():
    """Saves the flashcards to a JSON file."""
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
    """Loads flashcards from a JSON file."""
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

# GUI Setup
root = tk.Tk()
root.title("Flashcard Generator")
root.geometry("600x400")

tk.Label(root, text="Together AI API Key:").pack()
api_key_entry = tk.Entry(root, width=50)
api_key_entry.pack()

tk.Button(root, text="Process Image", command=process_image).pack()
tk.Button(root, text="Load Deck", command=load_deck).pack()

question_label = tk.Label(root, text="Q: [No Flashcards Yet]", font=("Arial", 14, "bold"), wraplength=500)
question_label.pack(pady=10)

answer_label = tk.Label(root, text="Click 'Show Answer' to reveal", font=("Arial", 12), wraplength=500)
answer_label.pack()

tk.Button(root, text="Show Answer", command=show_answer).pack()
tk.Button(root, text="Previous", command=prev_card).pack()
tk.Button(root, text="Next", command=next_card).pack()
tk.Button(root, text="Save Deck", command=save_deck).pack()

root.mainloop()

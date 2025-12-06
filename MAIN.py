import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageDraw, ImageFont
import threading
import os
from ultralytics import YOLO
import json
import subprocess # <-- NEW IMPORT

# --- Main Application Class ---
class ObjectDetectorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Floor Plan Object Detector (YOLOv8)")
        self.geometry("1200x850")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.model = None
        self.pil_image = None
        self.last_results = None
        self.setup_ui()
        self.status_label.configure(text="Status: Loading model, please wait...")
        threading.Thread(target=self.load_model, daemon=True).start()

    def setup_ui(self):
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        top_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top_frame, text="Image File:").grid(row=0, column=0, padx=5, pady=5)
        self.path_entry = ctk.CTkEntry(top_frame, placeholder_text="No file selected")
        self.path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_button = ctk.CTkButton(top_frame, text="Browse...", command=self.browse_file)
        self.browse_button.grid(row=0, column=2, padx=5, pady=5)
        self.detect_button = ctk.CTkButton(self, text="Detect Objects and Generate 3D Model", command=self.run_detection_thread)
        self.detect_button.configure(state="disabled")
        self.detect_button.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        results_frame = ctk.CTkFrame(self)
        results_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=3)
        results_frame.grid_columnconfigure(1, weight=1)
        results_frame.grid_rowconfigure(0, weight=1)
        self.image_label = ctk.CTkLabel(results_frame, text="Image will be displayed here")
        self.image_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.results_textbox = ctk.CTkTextbox(results_frame, width=250)
        self.results_textbox.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.results_textbox.configure(state="disabled")
        slider_frame = ctk.CTkFrame(self)
        slider_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        slider_frame.grid_columnconfigure(1, weight=1)
        self.slider_label = ctk.CTkLabel(slider_frame, text="Confidence Threshold: 0.25")
        self.slider_label.grid(row=0, column=0, padx=10, pady=5)
        self.slider = ctk.CTkSlider(slider_frame, from_=0.05, to=0.95, number_of_steps=18, command=self.update_display_with_threshold)
        self.slider.set(0.25)
        self.slider.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.status_label = ctk.CTkLabel(self, text="Status: Ready", anchor="w")
        self.status_label.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

    def load_model(self):
        try:
            self.model = YOLO(r'C:\Users\kanis\pytorch_floorplan\runs\detect\train2\weights\best.pt')
            self.status_label.configure(text="Status: Model loaded successfully. Select an image.")
        except Exception as e:
            self.status_label.configure(text=f"Error: Failed to load model. {e}")

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
        if path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)
            self.detect_button.configure(state="normal")
            self.pil_image = Image.open(path).convert("RGB")
            self.display_image(self.pil_image)
            self.last_results = None 

    def run_detection_thread(self):
        if self.pil_image is None or self.model is None: return
        self.detect_button.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.status_label.configure(text="Status: Detecting objects...")
        threading.Thread(target=self.detect_and_launch_blender, daemon=True).start()

    def detect_and_launch_blender(self):
        """Performs detection, saves JSON, and then launches Blender."""
        try:
            # --- Part 1: Detection (same as before) ---
            results = self.model(self.pil_image)
            self.last_results = results[0] 
            self.update_display_with_threshold(self.slider.get())
            
            detection_list = []
            for box in self.last_results.boxes:
                class_name = self.model.names[int(box.cls[0].item())]
                confidence = box.conf[0].item()
                bbox = box.xyxy[0].tolist()
                detection_list.append({"class": class_name, "confidence": confidence, "bbox": bbox})
            
            with open("detections.json", "w") as f:
                json.dump(detection_list, f, indent=4)
            
            self.status_label.configure(text=f"Status: Detection complete. Launching Blender...")

            # --- Part 2: Blender Automation ---
            # Path to your blender launcher, based on your screenshot
            blender_exe_path = r"C:\Program Files\Blender Foundation\Blender 4.5\blender-launcher.exe"
            
            # Path to the script you just saved
            blender_script_path = r"C:\Users\kanis\pytorch_floorplan\blender_script.py"
            
            # Construct the command to run
            command = [blender_exe_path, "--python", blender_script_path]
            
            # Launch Blender with the command
            subprocess.Popen(command)
            
        except Exception as e:
            self.status_label.configure(text=f"Error: Process failed. {e}")
        finally:
            self.detect_button.configure(state="normal")
            self.browse_button.configure(state="normal")

    def update_display_with_threshold(self, threshold_value):
        self.slider_label.configure(text=f"Confidence Threshold: {threshold_value:.2f}")
        if self.last_results:
            output_image = self.draw_predictions(self.pil_image.copy(), self.last_results, threshold_value)
            self.display_image(output_image)
            self.update_results_text(self.last_results, threshold_value)

    def draw_predictions(self, image, result, threshold):
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 15)
        except IOError:
            font = ImageFont.load_default()
        for box in result.boxes:
            if box.conf[0] > threshold:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                class_name = self.model.names[int(box.cls[0].item())]
                confidence = box.conf[0].item()
                draw.rectangle([(x1, y1), (x2, y2)], outline="lime", width=3)
                text = f"{class_name} {confidence:.2f}"
                text_position = (x1, y1 - 15)
                text_bbox = draw.textbbox(text_position, text, font=font)
                draw.rectangle(text_bbox, fill="lime")
                draw.text(text_position, text, fill="black", font=font)
        return image
    
    def update_results_text(self, result, threshold):
        self.results_textbox.configure(state="normal")
        self.results_textbox.delete("0.0", "end")
        text_summary = f"Detections (score > {threshold:.2f}):\n" + "="*30 + "\n"
        sorted_boxes = sorted(result.boxes, key=lambda x: x.conf[0], reverse=True)
        found_objects = False
        for box in sorted_boxes:
            if box.conf[0] > threshold:
                found_objects = True
                class_name = self.model.names[int(box.cls[0].item())]
                confidence = box.conf[0].item()
                text_summary += f"- {class_name}: {confidence:.2f}\n"
        if not found_objects:
            text_summary += "No objects found above threshold."
        self.results_textbox.insert("0.0", text_summary)
        self.results_textbox.configure(state="disabled")

    def display_image(self, pil_image):
        w, h = self.image_label.winfo_width(), self.image_label.winfo_height()
        if w < 50 or h < 50: w, h = 800, 700
        img_copy = pil_image.copy()
        img_copy.thumbnail((w, h))
        ctk_image = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=img_copy.size)
        self.image_label.configure(image=ctk_image, text="")

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ObjectDetectorApp()
    app.mainloop()
import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
import pyperclip
import shutil
import time
from tkinterdnd2 import DND_FILES, TkinterDnD

DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")

class MediaCompressorApp:
    def __init__(self, root):
        self.file_path = None
        self.output_path = None
        self.root = root
        self.root.title("MediaCompressor")
        self.root.geometry("640x470")

        self.main_frame = ctk.CTkFrame(master=root)
        self.main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)
        self.root.bind("<Control-v>", self.handle_paste)

        self.select_button = ctk.CTkButton(self.main_frame, text="Select Media File", command=self.select_file)
        self.select_button.pack(pady=10)

        self.path_label = ctk.CTkLabel(self.main_frame, text="No file selected")
        self.path_label.pack()

        self.size_entry = ctk.CTkEntry(self.main_frame, placeholder_text="Target size in MB (e.g. 10)")
        self.size_entry.pack(pady=10)

        # Add original file size label
        self.original_size_label = ctk.CTkLabel(self.main_frame, text="")
        self.original_size_label.pack()

        self.codec = ctk.CTkOptionMenu(self.main_frame, values=[
            "libx264 (H.264)",
            "libx265 (H.265)",
            "libvpx-vp9 (VP9)",
            "libaom-av1 (AV1)"
        ])
        self.codec.set("libx264 (H.264)")
        self.codec.pack(pady=5)

        self.container = ctk.CTkOptionMenu(self.main_frame, values=[".mp4", ".mkv", ".mov", ".webm"])
        self.container.set(".mp4")
        self.container.pack(pady=5)

        self.compress_button = ctk.CTkButton(self.main_frame, text="Compress", command=self.start_compression)
        self.compress_button.pack(pady=10)

        self.progress = ctk.CTkProgressBar(self.main_frame, width=400)
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(self.main_frame, text="")
        self.status_label.pack()

    def handle_drop(self, event):
        filepath = event.data.strip("{}")
        self.set_file(filepath)

    def handle_paste(self, event=None):
        path = pyperclip.paste()
        if os.path.isfile(path):
            self.set_file(path)

    def select_file(self):
        filetypes = [("Media files", "*.mp4 *.mov *.avi *.mp3 *.wav *.jpg *.png"), ("All files", "*.*")]
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            self.set_file(filepath)

    def set_file(self, path):
        self.file_path = path
        self.path_label.configure(text=os.path.basename(path))

        try:
            size_mb = os.path.getsize(path) / (1024*1024)
            self.original_size_label.configure(text=f"Original file size: {size_mb:.2f} MB")
        except Exception:
            self.original_size_label.configure(text="Original file size: N/A")

    def start_compression(self):
        if not self.file_path or not self.size_entry.get().isdigit():
            self.status_label.configure(text="Select file and valid size (MB).")
            return

        self.progress.pack_forget()
        self.status_label.configure(text="")

        target_mb = int(self.size_entry.get())
        codec = self.codec.get().split(" ")[0]
        container = self.container.get()

        thread = threading.Thread(target=self.compress_media, args=(target_mb, codec, container))
        thread.start()

    def compress_media(self, target_mb, codec, container_ext):
        input_file = self.file_path
        target_size = target_mb * 1024 * 1024 * 0.9
        filename_wo_ext = os.path.splitext(input_file)[0]
        output_file = filename_wo_ext + "_compressed" + container_ext
        self.output_path = output_file

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        try:
            duration_sec = float(result.stdout.strip())
        except ValueError:
            self.status_label.configure(text="Could not read media duration.")
            return

        bitrate = int((target_size * 8) / duration_sec)

        command = [
            "ffmpeg", "-i", input_file,
            "-c:v", codec,
            "-b:v", str(bitrate),
            "-preset", "medium",
            "-y", output_file
        ]

        start_time = time.time()
        process = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

        self.progress.set(0)
        self.progress.pack(pady=10)

        for line in process.stderr:
            if "time=" in line:
                try:
                    time_str = line.split("time=")[1].split(" ")[0]
                    h, m, s = map(float, time_str.split(":"))
                    current = h * 3600 + m * 60 + s
                    progress = current / duration_sec
                    self.progress.set(progress)
                    elapsed = time.time() - start_time
                    # Speed in MB/s = bytes processed / seconds
                    # We estimate processed bytes = bitrate (bits/sec) * current_time (sec) / 8 (bits/byte)
                    bytes_processed = bitrate / 8 * current
                    speed_mb_s = bytes_processed / (1024 * 1024) / elapsed if elapsed > 0 else 0
                    eta = (duration_sec - current) / (speed_mb_s * 1024 * 1024 * 8 / bitrate) if speed_mb_s > 0 else 0
                    self.status_label.configure(
                        text=f"{int(progress*100)}% - Speed: {speed_mb_s:.2f} MB/s - ETA: {int(eta)}s"
                    )
                except Exception:
                    continue

        self.progress.set(1)
        self.status_label.configure(text="Compression done.")
        self.ask_save_option()

    def ask_save_option(self):
        self.top = ctk.CTkToplevel(self.root)
        self.top.geometry("400x200")
        self.top.title("Save File To")

        ctk.CTkLabel(self.top, text="Choose save destination:").pack(pady=10)

        ctk.CTkButton(self.top, text="Downloads", command=self.save_to_downloads).pack(pady=5)
        ctk.CTkButton(self.top, text="Same Folder", command=self.save_to_same_dir).pack(pady=5)
        ctk.CTkButton(self.top, text="Custom Folder", command=self.save_to_custom_dir).pack(pady=5)
        ctk.CTkButton(self.top, text="Copy Path to Clipboard", command=self.copy_to_clipboard).pack(pady=5)

    def save_to_downloads(self):
        dest = os.path.join(DOWNLOADS, os.path.basename(self.output_path))
        shutil.move(self.output_path, dest)
        self.status_label.configure(text=f"Saved to Downloads.")
        self.top.destroy()

    def save_to_same_dir(self):
        self.status_label.configure(text=f"Saved to original folder.")
        self.top.destroy()

    def save_to_custom_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            dest = os.path.join(folder, os.path.basename(self.output_path))
            shutil.move(self.output_path, dest)
            self.status_label.configure(text=f"Saved to {folder}.")
        self.top.destroy()

    def copy_to_clipboard(self):
        pyperclip.copy(os.path.abspath(self.output_path))
        self.status_label.configure(text="Path copied to clipboard.")
        self.top.destroy()


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = MediaCompressorApp(root)
    root.mainloop()

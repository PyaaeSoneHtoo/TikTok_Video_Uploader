"""
TikTok Video Uploader GUI - Browser Automation (No Developer API Required)
Built with CustomTkinter for a modern dark-mode desktop experience.
Uses Playwright with a persistent session profile to upload videos directly to TikTok.
"""

import os
import sys
import time
import threading
from typing import List, Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk

from browser_uploader import (
    open_interactive_login,
    check_is_logged_in,
    upload_video_via_browser,
    get_profile_dir
)

# Appearance configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUPPORTED_EXTENSIONS = (".mp4", ".mov", ".webm", ".avi", ".mkv")


class TikTokUploaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TikTok Video Uploader (No API Required)")
        self.geometry("960x880")
        self.minsize(860, 750)

        # State
        self.selected_files: List[str] = []
        self.is_uploading: bool = False
        self.stop_requested: bool = False

        self._build_ui()
        self._refresh_login_status_async()

    def _build_ui(self):
        # Main scrollable container
        self.main_container = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # --- Header ---
        header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 12))

        title = ctk.CTkLabel(
            header_frame,
            text="📱 TikTok Video Uploader",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header_frame,
            text="Automated video publisher via persistent browser session (Zero API approval required)",
            text_color="#a1a1aa",
            font=ctk.CTkFont(size=14)
        )
        subtitle.pack(anchor="w")

        # --- Section 1: Account Login (Browser Session) ---
        self.auth_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.auth_card.pack(fill="x", pady=(0, 10), padx=5)

        card_title = ctk.CTkLabel(
            self.auth_card,
            text="1. TikTok Account Login (One-Time Setup)",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        card_title.pack(anchor="w", padx=15, pady=(12, 6))

        info_lbl = ctk.CTkLabel(
            self.auth_card,
            text="No API key or developer account needed! Log into your TikTok account once in the browser window.\nYour session is saved permanently on your computer.",
            text_color="#a1a1aa",
            justify="left",
            font=ctk.CTkFont(size=12)
        )
        info_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        status_row = ctk.CTkFrame(self.auth_card, fg_color="transparent")
        status_row.pack(fill="x", padx=15, pady=(0, 12))

        self.login_badge = ctk.CTkLabel(
            status_row,
            text="Checking Login Status...",
            fg_color="#27272a",
            text_color="#a1a1aa",
            corner_radius=6,
            padx=12,
            pady=6,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.login_badge.pack(side="left", padx=(0, 15))

        self.login_btn = ctk.CTkButton(
            status_row,
            text="🔑 Log in to TikTok (Browser)",
            fg_color="#fe2c55",
            hover_color="#e02449",
            font=ctk.CTkFont(weight="bold"),
            command=self._start_browser_login
        )
        self.login_btn.pack(side="left", padx=(0, 10))

        self.refresh_login_btn = ctk.CTkButton(
            status_row,
            text="🔄 Refresh Status",
            width=120,
            command=self._refresh_login_status_async
        )
        self.refresh_login_btn.pack(side="left")

        # --- Section 2: Video Selection & Queue ---
        video_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        video_card.pack(fill="x", pady=10, padx=5)

        ctk.CTkLabel(
            video_card,
            text="2. Select Video(s) to Upload",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 8))

        btn_row = ctk.CTkFrame(video_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="📁 Select Video File(s)...",
            command=self._pick_video_files
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="📂 Select Video Folder...",
            fg_color="#27272a",
            hover_color="#3f3f46",
            command=self._pick_video_folder
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="🗑️ Clear Queue",
            width=90,
            fg_color="#27272a",
            hover_color="#3f3f46",
            command=self._clear_queue
        ).pack(side="left")

        # Queue box
        self.queue_label = ctk.CTkLabel(video_card, text="Queued Videos (0):", font=ctk.CTkFont(weight="bold"))
        self.queue_label.pack(anchor="w", padx=15, pady=(4, 2))

        self.queue_box = ctk.CTkTextbox(video_card, height=110)
        self.queue_box.pack(fill="x", padx=15, pady=(0, 12))
        self.queue_box.insert("end", "No videos selected yet. Choose files or a folder above.")
        self.queue_box.configure(state="disabled")

        # --- Section 3: Caption, Hashtags & Upload Settings ---
        settings_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        settings_card.pack(fill="x", pady=10, padx=5)

        ctk.CTkLabel(
            settings_card,
            text="3. Post Details & Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 8))

        grid_frame = ctk.CTkFrame(settings_card, fg_color="transparent")
        grid_frame.pack(fill="x", padx=15, pady=4)
        grid_frame.grid_columnconfigure(1, weight=1)

        # Caption
        ctk.CTkLabel(grid_frame, text="Caption / Title:", width=110, anchor="w").grid(row=0, column=0, pady=5, sticky="w")
        self.caption_entry = ctk.CTkEntry(grid_frame, placeholder_text="Enter caption (leave empty to use video filename)")
        self.caption_entry.grid(row=0, column=1, pady=5, sticky="ew")

        # Hashtags
        ctk.CTkLabel(grid_frame, text="Hashtags:", width=110, anchor="w").grid(row=1, column=0, pady=5, sticky="w")
        self.hashtags_entry = ctk.CTkEntry(grid_frame, placeholder_text="#fyp #viral #anime #trending (space separated)")
        self.hashtags_entry.insert(0, "#fyp #viral #trending")
        self.hashtags_entry.grid(row=1, column=1, pady=5, sticky="ew")

        # Privacy
        ctk.CTkLabel(grid_frame, text="Privacy:", width=110, anchor="w").grid(row=2, column=0, pady=5, sticky="w")
        self.privacy_var = ctk.StringVar(value="Public")
        self.privacy_menu = ctk.CTkOptionMenu(
            grid_frame,
            variable=self.privacy_var,
            values=["Public", "Friends", "Only Me"]
        )
        self.privacy_menu.grid(row=2, column=1, pady=5, sticky="w")

        # Pacing Delay between batch videos
        ctk.CTkLabel(grid_frame, text="Delay (seconds):", width=110, anchor="w").grid(row=3, column=0, pady=5, sticky="w")
        pacing_frame = ctk.CTkFrame(grid_frame, fg_color="transparent")
        pacing_frame.grid(row=3, column=1, pady=5, sticky="w")

        self.delay_entry = ctk.CTkEntry(pacing_frame, width=70)
        self.delay_entry.insert(0, "45")
        self.delay_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(pacing_frame, text="seconds between uploads (avoids TikTok spam detection)", text_color="#a1a1aa").pack(side="left")

        # Headless option
        self.headless_chk = ctk.CTkCheckBox(
            settings_card,
            text="Run browser in background (Headless mode). Uncheck to watch browser upload."
        )
        self.headless_chk.pack(anchor="w", padx=15, pady=(8, 12))

        # --- Section 4: Action & Live Console ---
        action_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        action_card.pack(fill="x", pady=10, padx=5)

        self.upload_btn = ctk.CTkButton(
            action_card,
            text="🚀 Start TikTok Upload",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=44,
            fg_color="#fe2c55",
            hover_color="#e02449",
            command=self._start_upload_flow
        )
        self.upload_btn.pack(fill="x", padx=15, pady=(15, 8))

        self.progress_bar = ctk.CTkProgressBar(action_card)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 10))

        self.status_label = ctk.CTkLabel(
            action_card,
            text="Ready.",
            text_color="#a1a1aa",
            anchor="w"
        )
        self.status_label.pack(anchor="w", padx=15, pady=(0, 4))

        self.log_box = ctk.CTkTextbox(action_card, height=130)
        self.log_box.pack(fill="x", padx=15, pady=(0, 15))
        self.log_box.configure(state="disabled")

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self.status_label.configure(text=message)

    def _start_browser_login(self):
        self.login_btn.configure(state="disabled", text="⏳ Browser Open...")
        self._log("Opening browser window for TikTok login...")

        def login_task():
            try:
                def cb(m):
                    self.after(0, lambda: self._log(m))

                ok = open_interactive_login(status_callback=cb)
                if ok:
                    self.after(0, lambda: self._update_login_badge(True))
                    self.after(0, lambda: messagebox.showinfo("Login Success", "Successfully logged into TikTok!\nYour session is saved."))
                else:
                    self.after(0, lambda: self._update_login_badge(False))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Login Error", f"Error during login: {e}"))
            finally:
                self.after(0, lambda: self.login_btn.configure(state="normal", text="🔑 Log in to TikTok (Browser)"))
                self.after(0, self._refresh_login_status_async)

        threading.Thread(target=login_task, daemon=True).start()

    def _refresh_login_status_async(self):
        def check():
            logged_in = check_is_logged_in()
            self.after(0, lambda: self._update_login_badge(logged_in))

        threading.Thread(target=check, daemon=True).start()

    def _update_login_badge(self, logged_in: bool):
        if logged_in:
            self.login_badge.configure(
                text="🟢 TikTok Account Connected",
                fg_color="#064e3b",
                text_color="#34d399"
            )
        else:
            self.login_badge.configure(
                text="🔴 Not Logged In",
                fg_color="#450a0a",
                text_color="#f87171"
            )

    def _pick_video_files(self):
        paths = filedialog.askopenfilenames(
            title="Select Video(s)",
            filetypes=[("Video files", "*.mp4 *.mov *.webm *.avi *.mkv"), ("All files", "*.*")]
        )
        if paths:
            self.selected_files = list(paths)
            self._render_queue()

    def _pick_video_folder(self):
        folder = filedialog.askdirectory(title="Select Folder Containing Videos")
        if folder:
            files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
            ]
            if files:
                self.selected_files = files
                self._render_queue()
            else:
                messagebox.showinfo("No Videos", "No supported video files found in the chosen folder.")

    def _clear_queue(self):
        self.selected_files = []
        self._render_queue()

    def _render_queue(self):
        self.queue_box.configure(state="normal")
        self.queue_box.delete("1.0", "end")
        if self.selected_files:
            self.queue_label.configure(text=f"Queued Videos ({len(self.selected_files)}):")
            for idx, p in enumerate(self.selected_files, 1):
                name = os.path.basename(p)
                size_mb = os.path.getsize(p) / (1024 * 1024)
                self.queue_box.insert("end", f"{idx}. {name} ({size_mb:.1f} MB)\n")
        else:
            self.queue_label.configure(text="Queued Videos (0):")
            self.queue_box.insert("end", "No videos selected yet.")
        self.queue_box.configure(state="disabled")

    def _start_upload_flow(self):
        if not self.selected_files:
            messagebox.showwarning("No Videos", "Please select one or more video files to upload.")
            return

        if self.is_uploading:
            return

        # Check if logged in
        if not check_is_logged_in():
            ans = messagebox.askyesno(
                "Not Logged In",
                "You haven't logged into TikTok yet.\nWould you like to open the TikTok login window now?"
            )
            if ans:
                self._start_browser_login()
            return

        try:
            delay_sec = max(5, int(self.delay_entry.get().strip()))
        except ValueError:
            delay_sec = 45

        caption = self.caption_entry.get().strip()
        tags_raw = self.hashtags_entry.get().strip()
        tags = [t.strip() for t in tags_raw.split() if t.strip()]
        privacy = self.privacy_var.get()
        headless = self.headless_chk.get()

        self.is_uploading = True
        self.upload_btn.configure(state="disabled", text="⏳ Uploading in Progress...")
        self.progress_bar.set(0)

        def worker():
            total = len(self.selected_files)
            success_count = 0

            try:
                for idx, vpath in enumerate(self.selected_files, 1):
                    vname = os.path.basename(vpath)
                    self.after(0, lambda n=vname, i=idx, t=total: self._log(f"[{i}/{t}] Starting upload for: {n}"))

                    def cb(msg):
                        self.after(0, lambda m=msg: self._log(m))

                    try:
                        res = upload_video_via_browser(
                            video_path=vpath,
                            caption=caption,
                            hashtags=tags,
                            privacy=privacy,
                            headless=headless,
                            status_callback=cb
                        )
                        if res.get("success"):
                            success_count += 1
                            self.after(0, lambda n=vname: self._log(f"✅ Successfully posted: {n}"))
                    except Exception as ex:
                        self.after(0, lambda n=vname, e=str(ex): self._log(f"❌ Failed to upload {n}: {e}"))

                    pct = idx / total
                    self.after(0, lambda p=pct: self.progress_bar.set(p))

                    # Pause between batch videos
                    if idx < total:
                        self.after(0, lambda d=delay_sec: self._log(f"Pacing delay: waiting {d}s before next video..."))
                        time.sleep(delay_sec)

                self.after(0, lambda: self._log(f"🎉 Batch upload completed! ({success_count}/{total} posted)"))
                self.after(0, lambda s=success_count, t=total: messagebox.showinfo(
                    "Upload Finished",
                    f"Batch upload finished!\nSuccessfully posted: {s}/{t} video(s)."
                ))
            finally:
                self.is_uploading = False
                self.after(0, lambda: self.upload_btn.configure(state="normal", text="🚀 Start TikTok Upload"))

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = TikTokUploaderApp()
    app.mainloop()

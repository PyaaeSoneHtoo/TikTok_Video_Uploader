"""
TikTok Video Uploader GUI
Built with CustomTkinter for a modern dark-mode desktop experience.
"""

import os
import sys
import json
import webbrowser
import threading
from typing import Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk
from dotenv import load_dotenv, set_key

from tiktok_api import TikTokAPI, TikTokAPIError
from auth_server import wait_for_oauth_code

# Appearance configuration
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
TOKENS_FILE = os.path.join(BASE_DIR, "tokens.json")

load_dotenv(ENV_FILE)


class TikTokUploaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TikTok Video Uploader - API v2")
        self.geometry("900x820")
        self.minsize(800, 720)

        # State
        self.selected_video_path: Optional[str] = None
        self.api_client: Optional[TikTokAPI] = None

        self._build_ui()
        self._load_saved_credentials()
        self._check_initial_auth_status()

    def _build_ui(self):
        # Main scrollable container
        self.main_container = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # --- Header ---
        header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        title = ctk.CTkLabel(
            header_frame,
            text="📱 TikTok Video Uploader",
            font=ctk.CTkFont(size=26, weight="bold")
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header_frame,
            text="Publish videos directly using the official TikTok Content Posting API",
            text_color="#a1a1aa",
            font=ctk.CTkFont(size=14)
        )
        subtitle.pack(anchor="w")

        # --- Section 1: API Configuration & Authentication ---
        self.auth_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.auth_card.pack(fill="x", pady=10, padx=5)

        card_title = ctk.CTkLabel(
            self.auth_card,
            text="1. TikTok Developer Credentials & Account",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        card_title.pack(anchor="w", padx=15, pady=(12, 8))

        # Credentials grid
        cred_frame = ctk.CTkFrame(self.auth_card, fg_color="transparent")
        cred_frame.pack(fill="x", padx=15, pady=5)
        cred_frame.grid_columnconfigure(1, weight=1)

        # Client Key
        ctk.CTkLabel(cred_frame, text="Client Key:", width=110, anchor="w").grid(row=0, column=0, pady=4, sticky="w")
        self.client_key_entry = ctk.CTkEntry(cred_frame, placeholder_text="Your TikTok App Client Key")
        self.client_key_entry.grid(row=0, column=1, pady=4, sticky="ew")

        # Client Secret
        ctk.CTkLabel(cred_frame, text="Client Secret:", width=110, anchor="w").grid(row=1, column=0, pady=4, sticky="w")
        self.client_secret_entry = ctk.CTkEntry(cred_frame, placeholder_text="Your TikTok App Client Secret", show="•")
        self.client_secret_entry.grid(row=1, column=1, pady=4, sticky="ew")

        # Redirect URI
        ctk.CTkLabel(cred_frame, text="Redirect URI:", width=110, anchor="w").grid(row=2, column=0, pady=4, sticky="w")
        self.redirect_uri_entry = ctk.CTkEntry(cred_frame, placeholder_text="http://localhost:5000/callback")
        self.redirect_uri_entry.grid(row=2, column=1, pady=4, sticky="ew")

        # Credential action buttons
        btn_frame = ctk.CTkFrame(self.auth_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(8, 12))

        self.save_cred_btn = ctk.CTkButton(
            btn_frame,
            text="💾 Save Credentials",
            width=140,
            command=self._save_credentials
        )
        self.save_cred_btn.pack(side="left", padx=(0, 10))

        self.connect_btn = ctk.CTkButton(
            btn_frame,
            text="🔗 Connect TikTok Account",
            width=190,
            fg_color="#fe2c55",
            hover_color="#e02449",
            command=self._start_oauth_flow
        )
        self.connect_btn.pack(side="left", padx=(0, 10))

        self.auth_status_label = ctk.CTkLabel(
            btn_frame,
            text="Status: Not Connected",
            text_color="#ef4444",
            font=ctk.CTkFont(weight="bold")
        )
        self.auth_status_label.pack(side="left", padx=10)

        # --- Section 2: Video Selection & Details ---
        self.video_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.video_card.pack(fill="x", pady=10, padx=5)

        v_title = ctk.CTkLabel(
            self.video_card,
            text="2. Select Video & Post Information",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        v_title.pack(anchor="w", padx=15, pady=(12, 8))

        # Select file row
        file_row = ctk.CTkFrame(self.video_card, fg_color="transparent")
        file_row.pack(fill="x", padx=15, pady=5)
        file_row.grid_columnconfigure(0, weight=1)

        self.video_path_entry = ctk.CTkEntry(file_row, placeholder_text="Select an MP4 or MOV video file...", state="readonly")
        self.video_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.browse_btn = ctk.CTkButton(file_row, text="Browse Video...", width=130, command=self._browse_video)
        self.browse_btn.grid(row=0, column=1)

        self.file_info_label = ctk.CTkLabel(self.video_card, text="No video selected", text_color="#71717a", anchor="w")
        self.file_info_label.pack(fill="x", padx=15, pady=(0, 8))

        # Caption / Title
        caption_label = ctk.CTkLabel(self.video_card, text="Caption & Hashtags:", font=ctk.CTkFont(weight="bold"))
        caption_label.pack(anchor="w", padx=15, pady=(4, 2))

        self.caption_textbox = ctk.CTkTextbox(self.video_card, height=100)
        self.caption_textbox.pack(fill="x", padx=15, pady=(0, 8))
        self.caption_textbox.insert("1.0", "Check out this amazing video! #viral #fyp #trending")

        # Privacy & Permissions
        opts_frame = ctk.CTkFrame(self.video_card, fg_color="transparent")
        opts_frame.pack(fill="x", padx=15, pady=5)

        # Privacy dropdown
        ctk.CTkLabel(opts_frame, text="Privacy Level:").pack(side="left", padx=(0, 10))
        self.privacy_dropdown = ctk.CTkOptionMenu(
            opts_frame,
            values=[
                "PUBLIC_TO_EVERYONE",
                "MUTUAL_FOLLOW_FRIENDS",
                "FOLLOWER_OF_CREATOR",
                "SELF_ONLY"
            ],
            width=210
        )
        self.privacy_dropdown.set("PUBLIC_TO_EVERYONE")
        self.privacy_dropdown.pack(side="left", padx=(0, 25))

        # Checkboxes
        self.allow_comments_chk = ctk.CTkCheckBox(opts_frame, text="Allow Comments")
        self.allow_comments_chk.select()
        self.allow_comments_chk.pack(side="left", padx=10)

        self.allow_duet_chk = ctk.CTkCheckBox(opts_frame, text="Allow Duet")
        self.allow_duet_chk.select()
        self.allow_duet_chk.pack(side="left", padx=10)

        self.allow_stitch_chk = ctk.CTkCheckBox(opts_frame, text="Allow Stitch")
        self.allow_stitch_chk.select()
        self.allow_stitch_chk.pack(side="left", padx=10)

        # --- Section 3: Upload Action & Progress ---
        self.action_card = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.action_card.pack(fill="x", pady=10, padx=5)

        act_title = ctk.CTkLabel(
            self.action_card,
            text="3. Upload & Publishing Progress",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        act_title.pack(anchor="w", padx=15, pady=(12, 8))

        # Upload button
        self.upload_btn = ctk.CTkButton(
            self.action_card,
            text="🚀 Upload Video to TikTok",
            height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#00f2fe",
            text_color="#000000",
            hover_color="#4facfe",
            command=self._start_upload
        )
        self.upload_btn.pack(fill="x", padx=15, pady=(5, 12))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.action_card)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=15, pady=5)

        self.progress_label = ctk.CTkLabel(self.action_card, text="Ready", text_color="#a1a1aa", anchor="w")
        self.progress_label.pack(fill="x", padx=15, pady=(0, 8))

        # Log textbox
        log_label = ctk.CTkLabel(self.action_card, text="Activity Logs:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=15, pady=(6, 2))

        self.log_textbox = ctk.CTkTextbox(self.action_card, height=140, state="disabled")
        self.log_textbox.pack(fill="x", padx=15, pady=(0, 15))

    def _log(self, message: str):
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"{message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def _load_saved_credentials(self):
        client_key = os.getenv("TIKTOK_CLIENT_KEY", "")
        client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "")
        redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:5000/callback")

        self.client_key_entry.insert(0, client_key)
        self.client_secret_entry.insert(0, client_secret)
        self.redirect_uri_entry.insert(0, redirect_uri)

        if client_key and client_secret:
            self.api_client = TikTokAPI(
                client_key=client_key,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                tokens_file=TOKENS_FILE
            )

    def _save_credentials(self):
        ck = self.client_key_entry.get().strip()
        cs = self.client_secret_entry.get().strip()
        ru = self.redirect_uri_entry.get().strip() or "http://localhost:5000/callback"

        if not ck or not cs:
            messagebox.showwarning("Incomplete Fields", "Please enter both Client Key and Client Secret.")
            return

        # Write to .env
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"TIKTOK_CLIENT_KEY={ck}\n")
            f.write(f"TIKTOK_CLIENT_SECRET={cs}\n")
            f.write(f"TIKTOK_REDIRECT_URI={ru}\n")

        self.api_client = TikTokAPI(client_key=ck, client_secret=cs, redirect_uri=ru, tokens_file=TOKENS_FILE)
        self._log("Credentials saved to .env")
        messagebox.showinfo("Saved", "Credentials successfully saved!")

    def _check_initial_auth_status(self):
        if not self.api_client:
            return

        def task():
            try:
                tokens = self.api_client.load_tokens()
                if tokens.get("access_token"):
                    user_info = self.api_client.get_user_info()
                    disp_name = user_info.get("display_name", "Connected User")
                    self.after(0, lambda: self._update_auth_ui(True, f"Connected as @{disp_name}"))
                    self.after(0, lambda: self._log(f"Authenticated as {disp_name}"))
            except Exception as e:
                self.after(0, lambda: self._update_auth_ui(False, "Session expired / Not connected"))

        threading.Thread(target=task, daemon=True).start()

    def _update_auth_ui(self, connected: bool, message: str):
        if connected:
            self.auth_status_label.configure(text=f"Status: {message}", text_color="#22c55e")
            self.connect_btn.configure(text="🔄 Re-connect Account")
        else:
            self.auth_status_label.configure(text=f"Status: {message}", text_color="#ef4444")
            self.connect_btn.configure(text="🔗 Connect TikTok Account")

    def _start_oauth_flow(self):
        ck = self.client_key_entry.get().strip()
        cs = self.client_secret_entry.get().strip()
        ru = self.redirect_uri_entry.get().strip() or "http://localhost:5000/callback"

        if not ck or not cs:
            messagebox.showwarning("Missing Credentials", "Please enter your Client Key and Client Secret first.")
            return

        self.api_client = TikTokAPI(client_key=ck, client_secret=cs, redirect_uri=ru, tokens_file=TOKENS_FILE)

        def oauth_worker():
            try:
                self.after(0, lambda: self._log("Opening browser for TikTok OAuth authorization..."))
                auth_url, state = self.api_client.get_authorization_url()
                webbrowser.open(auth_url)

                self.after(0, lambda: self._log("Waiting for callback on http://localhost:5000/callback..."))
                code, returned_state, error = wait_for_oauth_code(port=5000)

                if error:
                    raise TikTokAPIError(f"OAuth returned error: {error}")
                if not code:
                    raise TikTokAPIError("Authorization timed out or was cancelled.")

                self.after(0, lambda: self._log("Exchanging code for access token..."))
                self.api_client.exchange_code_for_token(code)

                user_info = self.api_client.get_user_info()
                name = user_info.get("display_name", "Creator")
                self.after(0, lambda: self._update_auth_ui(True, f"Connected as @{name}"))
                self.after(0, lambda: self._log(f"Successfully connected to @{name}!"))
                self.after(0, lambda: messagebox.showinfo("Success", f"Successfully authenticated as @{name}!"))

            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._log(f"Authentication error: {err_msg}"))
                self.after(0, lambda: messagebox.showerror("Auth Error", err_msg))

        threading.Thread(target=oauth_worker, daemon=True).start()

    def _browse_video(self):
        filetypes = [
            ("Video Files", "*.mp4 *.mov *.avi *.mkv"),
            ("MP4 Video", "*.mp4"),
            ("MOV Video", "*.mov"),
            ("All Files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Select Video to Upload", filetypes=filetypes)
        if chosen:
            self.selected_video_path = chosen
            self.video_path_entry.configure(state="normal")
            self.video_path_entry.delete(0, "end")
            self.video_path_entry.insert(0, chosen)
            self.video_path_entry.configure(state="readonly")

            size_mb = os.path.getsize(chosen) / (1024 * 1024)
            self.file_info_label.configure(
                text=f"Selected: {os.path.basename(chosen)} ({size_mb:.2f} MB)",
                text_color="#22c55e"
            )
            self._log(f"Selected video: {chosen} ({size_mb:.2f} MB)")

    def _start_upload(self):
        if not self.selected_video_path:
            messagebox.showwarning("No Video", "Please select a video file first.")
            return

        if not self.api_client or not self.api_client.tokens.get("access_token"):
            messagebox.showwarning("Not Connected", "Please connect your TikTok account before uploading.")
            return

        title = self.caption_textbox.get("1.0", "end").strip()
        privacy = self.privacy_dropdown.get()
        disable_comment = not self.allow_comments_chk.get()
        disable_duet = not self.allow_duet_chk.get()
        disable_stitch = not self.allow_stitch_chk.get()

        self.upload_btn.configure(state="disabled", text="⏳ Uploading Video...")
        self.progress_bar.set(0)

        def upload_worker():
            try:
                def progress_cb(pct, uploaded, total):
                    ratio = pct / 100.0
                    uploaded_mb = uploaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    self.after(0, lambda: self.progress_bar.set(ratio))
                    self.after(0, lambda: self.progress_label.configure(
                        text=f"Uploading: {pct:.1f}% ({uploaded_mb:.1f} MB / {total_mb:.1f} MB)"
                    ))

                def status_cb(msg):
                    self.after(0, lambda: self._log(msg))
                    self.after(0, lambda: self.progress_label.configure(text=msg))

                result = self.api_client.upload_and_publish(
                    video_path=self.selected_video_path,
                    title=title,
                    privacy_level=privacy,
                    disable_duet=disable_duet,
                    disable_stitch=disable_stitch,
                    disable_comment=disable_comment,
                    progress_callback=progress_cb,
                    status_callback=status_cb
                )

                pub_id = result.get("publish_id")
                self.after(0, lambda: self._log(f"🎉 Publication successful! Publish ID: {pub_id}"))
                self.after(0, lambda: messagebox.showinfo(
                    "Published",
                    f"Video was uploaded and published successfully!\nPublish ID: {pub_id}"
                ))

            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._log(f"❌ Upload failed: {err_msg}"))
                self.after(0, lambda: messagebox.showerror("Upload Error", f"Upload failed:\n{err_msg}"))
            finally:
                self.after(0, lambda: self.upload_btn.configure(state="normal", text="🚀 Upload Video to TikTok"))

        threading.Thread(target=upload_worker, daemon=True).start()


if __name__ == "__main__":
    app = TikTokUploaderApp()
    app.mainloop()

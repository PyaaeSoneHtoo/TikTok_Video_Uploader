# TikTok Video Uploader (Browser Automation - No API Required) 📱

A modern, automated video publisher for TikTok built with **Playwright** and **CustomTkinter**. Uploads videos directly to TikTok using persistent browser sessions — **no developer account, API keys, or TikTok review required**.

---

## 🌟 Key Features

- 🚫 **Zero API Setup Required**:
  - No need to create a TikTok Developer account or register an app.
  - No waiting for TikTok app reviews or permissions approval.
  - Works with any standard personal or creator TikTok account.
- 🔑 **One-Time Interactive Login**:
  - Click **"🔑 Log in to TikTok (Browser)"** once to sign in via QR code, Google, phone, or email.
  - Your login session and cookies are saved permanently in a secure local folder (`browser_profile/`).
  - You never have to re-login unless you manually log out.
- 📂 **Single Video & Batch Folder Support**:
  - Select individual video files or an entire folder of videos.
  - Automatically processes the queue one by one.
- ⚙️ **Customizable Post Options**:
  - Video caption / title
  - Space-separated hashtags (e.g. `#fyp #viral #anime #trending`)
  - Privacy levels: `Public`, `Friends`, or `Only Me`
  - Anti-spam pacing delay between batch posts (e.g. 45–60 seconds)
  - Headless mode (run silently in background) or visible mode (watch browser upload in real-time)
- 💻 **Modern Dark GUI + Powerful CLI**.

---

## 🚀 Quick Start

### 1. Launch the Desktop GUI
Double-click:
```cmd
run.bat
```
*(Or double-click `run_tiktok_uploader.bat` in your main WorkSpace directory).*

### 2. Workflow:
1. Click **"🔑 Log in to TikTok (Browser)"** — a browser window will open.
2. Sign in to your TikTok account. Once logged in, close the window.
3. Select your video file(s) or video folder.
4. Add your caption and hashtags.
5. Click **"🚀 Start TikTok Upload"**!

---

## 💻 CLI Commands

```powershell
# 1. Log in to TikTok (opens browser window to save session)
python cli.py login

# 2. Check login status
python cli.py status

# 3. Upload a single video
python cli.py upload --video "C:\videos\clip.mp4" --caption "My Video" --tags "#fyp #viral"

# 4. Upload an entire folder of videos with 45s delay between posts
python cli.py upload --folder "C:\videos" --tags "#anime #fyp" --delay 45

# 5. Run in background (headless)
python cli.py upload --video "C:\videos\clip.mp4" --headless
```

---

## 📦 Requirements & Tech Stack

- Python 3.10+
- [Playwright](https://playwright.dev/python/) with Chromium
- [CustomTkinter](https://customtkinter.tomschimansky.com/) (modern UI)
- Pillow

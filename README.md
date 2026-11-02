# TikTok Video Uploader (API v2)

A desktop and CLI application to upload and publish videos directly to TikTok using the official **TikTok Content Posting API (v2)**.

---

## 🌟 Features

- 🔐 **One-Click OAuth 2.0**: Connects to your TikTok account through a local callback server with automatic token refresh.
- 🎨 **Modern Dark GUI**: Built with CustomTkinter for an intuitive desktop workflow.
- 📦 **Direct & Resumable Upload**: Handles single and multi-part chunked video uploads with live progress.
- ⚙️ **Customizable Post Settings**:
  - Caption with hashtags
  - Privacy levels: `PUBLIC_TO_EVERYONE`, `MUTUAL_FOLLOW_FRIENDS`, `FOLLOWER_OF_CREATOR`, `SELF_ONLY`
  - Toggle Duet, Stitch, and Comment permissions
- 💻 **CLI Support**: Ready for headless terminal uploads and scheduled automation scripts.

---

## 🛠️ Prerequisites & TikTok Developer Setup

To upload videos to TikTok via the official API, you need a free TikTok Developer account:

1. **Sign up / Log in** at [TikTok Developer Portal](https://developers.tiktok.com/).
2. Click **Manage apps** and click **Create an app**.
3. In the App details, add the **Content Posting API** product.
4. Set the **Redirect Domain / URI** to:
   ```
   http://localhost:5000/callback
   ```
5. Request / enable the following scopes:
   - `user.info.basic`
   - `video.upload`
   - `video.publish`
6. Copy your **Client Key** and **Client Secret**.

---

## 🚀 Quick Start

### 1. Launch the Desktop GUI
Simply double-click:
```cmd
run.bat
```
*(The batch script will automatically create a `.venv` virtual environment and install dependencies on first run).*

Or manually:
```powershell
cd TikTok_Video_Uploader
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python gui_app.py
```

### 2. Connect Your Account
1. Paste your **Client Key** and **Client Secret** into the app.
2. Click **💾 Save Credentials**.
3. Click **🔗 Connect TikTok Account** — your default browser will open to TikTok's authorization screen.
4. Authorize the application. The local listener will catch the token and display `Connected as @username`.

### 3. Upload a Video
1. Click **Browse Video...** and choose an `.mp4` or `.mov` file.
2. Add your title/caption and hashtags.
3. Choose your privacy setting and permissions.
4. Click **🚀 Upload Video to TikTok**.

---

## 💻 CLI Usage

You can also use the tool entirely from the terminal:

### Connect Account:
```bash
python cli.py auth
```

### Check Logged-in User:
```bash
python cli.py whoami
```

### Upload a Video:
```bash
python cli.py upload --video "path/to/my_video.mp4" --title "Amazing moment #fyp #viral" --privacy PUBLIC_TO_EVERYONE
```

### Check Publish Status:
```bash
python cli.py status --publish-id "v_pub_xxxxxxxx"
```

---

## 📁 File Structure

```
TikTok_Video_Uploader/
├── tiktok_api.py         # Core TikTok Content Posting API client
├── auth_server.py        # Local OAuth callback listener
├── gui_app.py            # CustomTkinter graphical desktop interface
├── cli.py                # Command-line interface
├── run_gui.bat           # Launcher script for Windows
├── run.bat               # Quick alias launcher
├── requirements.txt      # Python dependencies
├── .env.example          # Template for credentials
└── README.md             # Documentation
```

---

## 📌 Video Format Requirements
- **Container**: MP4 or MOV
- **Video Codec**: H.264
- **Audio Codec**: AAC
- **Duration**: Between 3 seconds and 10 minutes
- **Aspect Ratio**: 9:16 (vertical recommended), 16:9, or 1:1
- **File Size**: Up to 4 GB

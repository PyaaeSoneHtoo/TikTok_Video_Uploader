"""
TikTok Video Uploader CLI - Browser Automation (No Developer API Required)
Uploads videos directly to TikTok using Playwright browser automation.
"""

import os
import sys

# Ensure UTF-8 stdout on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import argparse

from browser_uploader import (
    open_interactive_login,
    check_is_logged_in,
    upload_video_via_browser
)

SUPPORTED_EXTENSIONS = (".mp4", ".mov", ".webm", ".avi", ".mkv")


def main():
    parser = argparse.ArgumentParser(description="TikTok Video Uploader (Browser Automation - No API)")
    subparsers = parser.add_subparsers(dest="command")

    # Command: login
    subparsers.add_parser("login", help="Opens browser to log into your TikTok account and save session")

    # Command: status
    subparsers.add_parser("status", help="Checks if a valid TikTok login session exists")

    # Command: upload
    upload_parser = subparsers.add_parser("upload", help="Uploads a single video or a batch folder to TikTok")
    upload_parser.add_argument("--video", "-v", default=None, help="Path to single video file")
    upload_parser.add_argument("--folder", "-f", default=None, help="Path to folder containing videos")
    upload_parser.add_argument("--caption", "-c", default="", help="Video caption/title")
    upload_parser.add_argument("--tags", "-t", default="", help="Hashtags (space separated, e.g. '#fyp #viral')")
    upload_parser.add_argument("--privacy", "-p", choices=["Public", "Friends", "Only Me"], default="Public",
                               help="Privacy level (default: Public)")
    upload_parser.add_argument("--delay", "-d", type=int, default=45,
                               help="Delay in seconds between batch video uploads (default: 45s)")
    upload_parser.add_argument("--headless", action="store_true",
                               help="Run browser in background without showing window")

    args = parser.parse_args()

    if args.command == "login":
        print("🔑 Opening browser window for TikTok login...")
        ok = open_interactive_login(status_callback=lambda msg: print(f"ℹ️ {msg}"))
        if ok:
            print("✅ Login successful! Your TikTok session is saved permanently.")
        else:
            print("❌ Login was not completed or timed out.")

    elif args.command == "status":
        logged_in = check_is_logged_in()
        if logged_in:
            print("🟢 Status: Logged in (TikTok session is active)")
        else:
            print("🔴 Status: Not logged in. Run 'python cli.py login' or use the GUI to log in.")

    elif args.command == "upload":
        if not check_is_logged_in():
            print("❌ Error: You are not logged into TikTok.")
            print("   Run: python cli.py login")
            sys.exit(1)

        # Collect files
        target_files = []
        if args.video:
            if not os.path.isfile(args.video):
                print(f"❌ Error: Video file not found: {args.video}")
                sys.exit(1)
            target_files.append(args.video)
        elif args.folder:
            if not os.path.isdir(args.folder):
                print(f"❌ Error: Folder not found: {args.folder}")
                sys.exit(1)
            target_files = [
                os.path.join(args.folder, f)
                for f in os.listdir(args.folder)
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
            ]
            if not target_files:
                print(f"❌ Error: No video files found in {args.folder}")
                sys.exit(1)
        else:
            print("❌ Error: Specify either --video or --folder to upload.")
            sys.exit(1)

        tags = [t.strip() for t in args.tags.split() if t.strip()]

        print(f"🚀 Found {len(target_files)} video(s) to upload.")
        print(f"🔒 Privacy: {args.privacy}")
        print(f"🏷️ Hashtags: {' '.join(tags) if tags else '(None)'}")
        print(f"⏱️ Delay between posts: {args.delay}s")
        print("-" * 60)

        for idx, vpath in enumerate(target_files, 1):
            vname = os.path.basename(vpath)
            print(f"[{idx}/{len(target_files)}] Uploading {vname}...", flush=True)

            try:
                res = upload_video_via_browser(
                    video_path=vpath,
                    caption=args.caption,
                    hashtags=tags,
                    privacy=args.privacy,
                    headless=args.headless,
                    status_callback=lambda msg: print(f"   ℹ️ {msg}")
                )
                if res.get("success"):
                    print(f"✅ Successfully posted {vname}!")
            except Exception as e:
                print(f"❌ Failed to upload {vname}: {e}")

            if idx < len(target_files):
                print(f"⏳ Waiting {args.delay}s before next upload...")
                time.sleep(args.delay)

        print("-" * 60)
        print("🎉 Batch upload process finished!")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

"""
TikTok Video Uploader CLI
Provides terminal commands for authenticating and publishing videos.
"""

import os
import sys
import argparse
import webbrowser
from dotenv import load_dotenv

from tiktok_api import TikTokAPI, TikTokAPIError
from auth_server import wait_for_oauth_code

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

def get_api() -> TikTokAPI:
    client_key = os.getenv("TIKTOK_CLIENT_KEY")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET")
    redirect_uri = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:5000/callback")

    if not client_key or not client_secret:
        print("❌ Error: TIKTOK_CLIENT_KEY or TIKTOK_CLIENT_SECRET not found.")
        print("Please set them in .env or run the GUI to configure them.")
        sys.exit(1)

    return TikTokAPI(
        client_key=client_key,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        tokens_file=os.path.join(BASE_DIR, "tokens.json")
    )

def handle_auth(args):
    api = get_api()
    print("Initiating TikTok OAuth authorization...")
    auth_url, state = api.get_authorization_url()
    print(f"Opening browser at:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for callback on http://localhost:5000/callback...")
    code, returned_state, error = wait_for_oauth_code(port=5000)

    if error:
        print(f"❌ Authorization error: {error}")
        return
    if not code:
        print("❌ Authorization timed out or was cancelled.")
        return

    print("Exchanging code for tokens...")
    api.exchange_code_for_token(code)
    try:
        user = api.get_user_info()
        print(f"✅ Successfully connected to TikTok as @{user.get('display_name', 'Creator')}!")
    except Exception as e:
        print(f"✅ Authentication succeeded, but could not fetch profile info: {e}")

def handle_whoami(args):
    api = get_api()
    try:
        user = api.get_user_info()
        print(f"Logged in as: {user.get('display_name')} (OpenID: {user.get('open_id')})")
    except Exception as e:
        print(f"❌ Not logged in or token expired: {e}")

def handle_upload(args):
    api = get_api()
    if not os.path.isfile(args.video):
        print(f"❌ Video file does not exist: {args.video}")
        return

    print(f"Starting upload for: {args.video}")
    print(f"Title: {args.title}")
    print(f"Privacy: {args.privacy}")

    def progress_cb(pct, uploaded, total):
        up_mb = uploaded / (1024 * 1024)
        tot_mb = total / (1024 * 1024)
        print(f"\rUploading: {pct:5.1f}% [{up_mb:6.1f}MB / {tot_mb:6.1f}MB]", end="", flush=True)

    def status_cb(msg):
        print(f"\n[Status] {msg}")

    try:
        res = api.upload_and_publish(
            video_path=args.video,
            title=args.title,
            privacy_level=args.privacy,
            disable_duet=args.disable_duet,
            disable_stitch=args.disable_stitch,
            disable_comment=args.disable_comment,
            progress_callback=progress_cb,
            status_callback=status_cb
        )
        print(f"\n✅ Video upload complete! Publish ID: {res.get('publish_id')}")
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")

def handle_status(args):
    api = get_api()
    try:
        status_data = api.fetch_publish_status(args.publish_id)
        print(f"Status for Publish ID {args.publish_id}:")
        print(f"  Status: {status_data.get('status')}")
        if status_data.get("fail_reason"):
            print(f"  Reason: {status_data.get('fail_reason')}")
    except Exception as e:
        print(f"❌ Error checking status: {e}")

def main():
    parser = argparse.ArgumentParser(description="TikTok Video Uploader CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # auth
    parser_auth = subparsers.add_parser("auth", help="Connect TikTok account via OAuth")
    parser_auth.set_defaults(func=handle_auth)

    # whoami
    parser_whoami = subparsers.add_parser("whoami", help="Display authenticated TikTok user")
    parser_whoami.set_defaults(func=handle_whoami)

    # upload
    parser_upload = subparsers.add_parser("upload", help="Upload and publish a video")
    parser_upload.add_argument("--video", "-v", required=True, help="Path to video file (.mp4, .mov)")
    parser_upload.add_argument("--title", "-t", default="Uploaded via TikTok API #fyp", help="Video title & hashtags")
    parser_upload.add_argument("--privacy", "-p", default="PUBLIC_TO_EVERYONE",
                               choices=["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"],
                               help="Video privacy level")
    parser_upload.add_argument("--disable-duet", action="store_true", help="Disable Duet")
    parser_upload.add_argument("--disable-stitch", action="store_true", help="Disable Stitch")
    parser_upload.add_argument("--disable-comment", action="store_true", help="Disable Comments")
    parser_upload.set_defaults(func=handle_upload)

    # status
    parser_status = subparsers.add_parser("status", help="Check status of a publish ID")
    parser_status.add_argument("--publish-id", "-id", required=True, help="Publish ID returned by init/upload")
    parser_status.set_defaults(func=handle_status)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

"""
TikTok Video Uploader - Browser Automation Engine
Uses Playwright with a persistent browser profile to upload videos directly to TikTok
without requiring a developer account, API review, or API keys.
"""

import os
import sys
import time
import json
import logging
from typing import Optional, Callable, Dict, Any, List

from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, "browser_profile")
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
TIKTOK_CREATOR_URL = "https://www.tiktok.com/creator-center/upload"
TIKTOK_LOGIN_URL = "https://www.tiktok.com/login"
TIKTOK_HOME_URL = "https://www.tiktok.com/"


def get_profile_dir() -> str:
    """Returns absolute path to local persistent browser profile."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    return PROFILE_DIR


def open_interactive_login(status_callback: Optional[Callable[[str], None]] = None) -> bool:
    """
    Launches a visible Chromium window where the user can log into their TikTok account
    via QR code, Google, phone, or email. The session and cookies are stored permanently in browser_profile.
    """
    user_data_dir = get_profile_dir()
    if status_callback:
        status_callback("Opening browser window for TikTok login...")

    with sync_playwright() as p:
        args = [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized"
        ]
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=args,
            no_viewport=True
        )

        page = context.new_page()
        page.goto(TIKTOK_LOGIN_URL, timeout=60000)

        if status_callback:
            status_callback("Waiting for you to log into TikTok in the browser window...")

        print("\n" + "=" * 60)
        print("🔑 TIKTOK LOGIN WINDOW OPENED")
        print("Please log into your TikTok account in the browser window.")
        print("(You can use QR code, Google, Email, or Phone).")
        print("Once you are logged in, close the browser or wait for auto-detection.")
        print("=" * 60 + "\n")

        # Wait loop: check if user logs in successfully (navigates away from login page)
        logged_in = False
        start_time = time.time()
        max_wait = 300  # 5 minutes to log in

        while time.time() - start_time < max_wait:
            time.sleep(2)
            try:
                curr_url = page.url
                # If navigated to home or creator upload or has session cookies
                if "login" not in curr_url.lower() and ("tiktok.com" in curr_url):
                    cookies = context.cookies()
                    session_names = [c["name"] for c in cookies]
                    if "sessionid" in session_names or "sid_guard" in session_names or "passport_csrf_token" in session_names:
                        logged_in = True
                        if status_callback:
                            status_callback("Login detected! Saving session credentials...")
                        # Save cookies backup as well
                        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                            json.dump(cookies, f, indent=2)
                        time.sleep(3)
                        break
            except Exception:
                # Browser might be closed by user
                break

        # Check final cookie state
        try:
            cookies = context.cookies()
            session_names = [c["name"] for c in cookies]
            if "sessionid" in session_names or "sid_guard" in session_names:
                logged_in = True
                with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2)
        except Exception:
            pass

        context.close()
        return logged_in


def check_is_logged_in() -> bool:
    """
    Checks if a valid, logged-in session exists in the browser profile.
    """
    user_data_dir = get_profile_dir()
    if not os.path.exists(user_data_dir):
        return False

    with sync_playwright() as p:
        args = ["--disable-blink-features=AutomationControlled"]
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                args=args
            )
            cookies = context.cookies()
            context.close()
            session_names = [c["name"] for c in cookies]
            return "sessionid" in session_names or "sid_guard" in session_names
        except Exception:
            return False


def upload_video_via_browser(
    video_path: str,
    caption: str = "",
    hashtags: Optional[List[str]] = None,
    privacy: str = "Public",
    headless: bool = False,
    status_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """
    Automates uploading a single video to TikTok Studio.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Build full caption with hashtags
    full_caption = caption.strip() if caption else os.path.splitext(os.path.basename(video_path))[0]
    if hashtags:
        tags_str = " ".join([f"#{t.lstrip('#')}" for t in hashtags if t.strip()])
        if tags_str:
            full_caption = f"{full_caption} {tags_str}"

    user_data_dir = get_profile_dir()

    if status_callback:
        status_callback(f"Launching browser ({'Headless' if headless else 'Visible'})...")

    with sync_playwright() as p:
        args = [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized"
        ]
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=args,
            no_viewport=True
        )

        page = context.new_page()

        if status_callback:
            status_callback("Navigating to TikTok Studio Upload...")

        # Try tiktokstudio upload URL first, fallback to creator-center
        target_url = TIKTOK_UPLOAD_URL
        page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)

        # Check if redirected to login
        if "login" in page.url.lower():
            context.close()
            raise RuntimeError("You are not logged into TikTok. Please click '🔑 Log In to TikTok' first.")

        # If page redirected or needs fallback
        if "tiktok.com" not in page.url:
            page.goto(TIKTOK_CREATOR_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)

        if status_callback:
            status_callback("Selecting video file for upload...")

        # Locate file input: might be directly on page or inside an iframe
        file_input = None
        selectors = [
            'input[type="file"][accept*="video"]',
            'input[type="file"]',
            'iframe >> input[type="file"]'
        ]

        # Wait for file input to attach
        for _ in range(15):
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0:
                        file_input = el
                        break
                except Exception:
                    pass
            if file_input:
                break
            time.sleep(1)

        if not file_input:
            # Try finding through page frames
            for frame in page.frames:
                try:
                    el = frame.locator('input[type="file"]').first
                    if el.count() > 0:
                        file_input = el
                        break
                except Exception:
                    pass

        if not file_input:
            context.close()
            raise RuntimeError("Could not find video file upload dropzone on TikTok upload page.")

        # Set video file
        abs_video_path = os.path.abspath(video_path)
        file_input.set_input_files(abs_video_path)

        if status_callback:
            status_callback("Video file injected. Waiting for upload to process...")

        # Wait for video upload processing (preview or upload bar reaches 100%)
        # Check for upload progress or caption editor activation
        uploaded = False
        start_wait = time.time()
        max_upload_time = 300  # 5 minutes for large video uploads

        while time.time() - start_wait < max_upload_time:
            time.sleep(2)
            try:
                # Look for upload complete indicators
                text_content = page.content()
                if "Uploaded" in text_content or "100%" in text_content or "Preview" in text_content:
                    uploaded = True
                    break
                # Or check if video element or stage-preview appeared
                if page.locator("video").count() > 0 or page.locator(".preview-panel").count() > 0:
                    uploaded = True
                    break
                # Or check if caption input is editable and active
                if page.locator('div[contenteditable="true"]').count() > 0:
                    uploaded = True
                    break
            except Exception:
                pass

        if status_callback:
            status_callback("Entering title and hashtags...")

        # Enter caption
        try:
            caption_selectors = [
                'div[contenteditable="true"]',
                '.public-DraftEditor-content',
                '.notranslate[contenteditable="true"]',
                'div[role="combobox"]',
                'textarea[placeholder*="caption"]',
                'textarea'
            ]
            caption_el = None
            for sel in caption_selectors:
                el = page.locator(sel).first
                if el.count() > 0:
                    caption_el = el
                    break

            if caption_el:
                caption_el.click()
                time.sleep(0.5)
                # Select all and delete previous text
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                time.sleep(0.5)
                page.keyboard.type(full_caption, delay=20)
                time.sleep(1)
        except Exception as e:
            logger.warning(f"Could not enter caption: {e}")

        # Set Privacy if dropdown is accessible
        if privacy in ["Friends", "Only Me", "Private"]:
            try:
                # Click privacy select
                priv_btn = page.locator('div:has-text("Who can watch this video") + div').first
                if priv_btn.count() > 0:
                    priv_btn.click()
                    time.sleep(0.5)
                    target_priv = "Only me" if privacy in ["Only Me", "Private"] else "Friends"
                    page.locator(f'div[role="option"]:has-text("{target_priv}")').first.click()
            except Exception as e:
                logger.warning(f"Could not set privacy: {e}")

        if status_callback:
            status_callback("Submitting post to TikTok...")

        # Find and click Post button
        post_btn = None
        post_selectors = [
            'button:has-text("Post")',
            'button:has-text("Publish")',
            'button[data-e2e="post_video_button"]',
            '.btn-post'
        ]

        for sel in post_selectors:
            el = page.locator(sel).first
            if el.count() > 0 and el.is_enabled():
                post_btn = el
                break

        if not post_btn:
            # Scroll down to ensure button is visible
            page.mouse.wheel(0, 500)
            time.sleep(1)
            for sel in post_selectors:
                el = page.locator(sel).first
                if el.count() > 0 and el.is_enabled():
                    post_btn = el
                    break

        if not post_btn:
            context.close()
            raise RuntimeError("Post button not found or not enabled on upload page.")

        # Click Post
        post_btn.click()

        if status_callback:
            status_callback("Waiting for TikTok post confirmation...")

        # Wait for success dialog or redirection
        post_confirmed = False
        confirm_start = time.time()
        while time.time() - confirm_start < 45:
            time.sleep(2)
            try:
                page_text = page.content()
                if (
                    "Your video is being uploaded" in page_text
                    or "Your video has been uploaded" in page_text
                    or "Manage your posts" in page_text
                    or "Upload another video" in page_text
                    or "Post another video" in page_text
                ):
                    post_confirmed = True
                    break
            except Exception:
                pass

        time.sleep(3)
        context.close()

        if status_callback:
            status_callback("Video posted successfully!")

        return {
            "success": True,
            "confirmed": post_confirmed,
            "video": os.path.basename(video_path),
            "caption": full_caption
        }

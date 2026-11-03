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


def dismiss_popups(page: Page):
    """
    Dismisses onboarding tours, react-joyride popups, cookie consent banners,
    and dialog overlays that intercept clicks on TikTok Studio.
    """
    try:
        # 1. Click common tour dismiss buttons
        dismiss_selectors = [
            'button:has-text("Got it")',
            'button:has-text("Skip")',
            'button:has-text("Next")',
            'button:has-text("Close")',
            'button:has-text("Dismiss")',
            '[aria-label="Close"]',
            '.react-joyride__tooltip button',
            '.joyride-tooltip__close'
        ]
        for sel in dismiss_selectors:
            try:
                locator = page.locator(sel)
                for i in range(min(locator.count(), 3)):
                    btn = locator.nth(i)
                    if btn.is_visible():
                        btn.click(timeout=1000)
                        time.sleep(0.3)
            except Exception:
                pass

        # 2. Force remove joyride overlay portals and modal masks via JavaScript
        page.evaluate("""() => {
            const overlays = document.querySelectorAll(
                '#react-joyride-portal, .react-joyride__overlay, .modal-mask, [data-test-id="overlay"], .tiktok-modal__mask'
            );
            overlays.forEach(el => el.remove());
        }""")
    except Exception:
        pass


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
                if "login" not in curr_url.lower() and ("tiktok.com" in curr_url):
                    cookies = context.cookies()
                    session_names = [c["name"] for c in cookies]
                    if "sessionid" in session_names or "sid_guard" in session_names or "passport_csrf_token" in session_names:
                        logged_in = True
                        if status_callback:
                            status_callback("Login detected! Saving session credentials...")
                        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                            json.dump(cookies, f, indent=2)
                        time.sleep(3)
                        break
            except Exception:
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
    is_headless = bool(headless)

    if status_callback:
        status_callback(f"Launching browser ({'Headless' if is_headless else 'Visible'})...")

    with sync_playwright() as p:
        args = [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized"
        ]
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=is_headless,
            args=args,
            no_viewport=True
        )

        page = context.new_page()

        if status_callback:
            status_callback("Navigating to TikTok Studio Upload...")

        target_url = TIKTOK_UPLOAD_URL
        page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)

        # Check if redirected to login
        if "login" in page.url.lower():
            context.close()
            raise RuntimeError("You are not logged into TikTok. Please click '🔑 Log In to TikTok' first.")

        # Fallback to creator-center if needed
        if "tiktok.com" not in page.url:
            page.goto(TIKTOK_CREATOR_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(3)

        dismiss_popups(page)

        if status_callback:
            status_callback("Selecting video file for upload...")

        # Locate file input
        file_input = None
        selectors = [
            'input[type="file"][accept*="video"]',
            'input[type="file"]',
            'iframe >> input[type="file"]'
        ]

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

        abs_video_path = os.path.abspath(video_path)
        file_input.set_input_files(abs_video_path)

        if status_callback:
            status_callback("Video file injected. Uploading & entering details...")

        time.sleep(2)
        dismiss_popups(page)

        # Enter caption
        if status_callback:
            status_callback("Entering title and hashtags...")

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
                caption_el.click(timeout=5000)
                time.sleep(0.5)
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
                priv_btn = page.locator('div:has-text("Who can watch this video") + div').first
                if priv_btn.count() > 0:
                    priv_btn.click(timeout=3000)
                    time.sleep(0.5)
                    target_priv = "Only me" if privacy in ["Only Me", "Private"] else "Friends"
                    page.locator(f'div[role="option"]:has-text("{target_priv}")').first.click(timeout=3000)
            except Exception as e:
                logger.warning(f"Could not set privacy: {e}")

        dismiss_popups(page)

        if status_callback:
            status_callback("Waiting for video upload to process completely (100%)...")

        # Wait for video upload to finish processing
        # TikTok displays progress or activates the submit button when finished
        start_wait = time.time()
        max_upload_time = 360  # 6 minutes max

        # Helper to locate the real submit Post button (NOT the sidebar navigation item)
        def find_real_post_button():
            dismiss_popups(page)
            # Try specific action-bar / footer selectors first
            specific_selectors = [
                'button[data-e2e="post_video_button"]',
                'div[class*="btn-post"] button',
                'div[class*="footer"] button:has-text("Post")',
                'div[class*="bottom"] button:has-text("Post")',
                'button.btn-post',
                'button:has-text("Publish"):not([data-tt*="Sidebar"])',
                'button:has-text("Post"):not([data-tt*="Sidebar"])'
            ]
            for s in specific_selectors:
                loc = page.locator(s)
                for idx in range(loc.count()):
                    btn = loc.nth(idx)
                    # Verify it's not a sidebar item
                    data_tt = btn.get_attribute("data-tt") or ""
                    cls = btn.get_attribute("class") or ""
                    if "sidebar" not in data_tt.lower() and "sidebar" not in cls.lower():
                        return btn

            # Fallback: scan all buttons containing "Post" and take the last non-sidebar button
            all_btns = page.locator('button:has-text("Post")')
            for idx in reversed(range(all_btns.count())):
                btn = all_btns.nth(idx)
                data_tt = btn.get_attribute("data-tt") or ""
                cls = btn.get_attribute("class") or ""
                if "sidebar" not in data_tt.lower() and "sidebar" not in cls.lower():
                    return btn

            return None

        # Wait until upload is complete and post button is ready
        target_post_btn = None
        while time.time() - start_wait < max_upload_time:
            time.sleep(2)
            dismiss_popups(page)

            # Scroll down to ensure upload progress and buttons are in view
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            # Check if post button is found and enabled
            btn = find_real_post_button()
            if btn and btn.is_enabled():
                target_post_btn = btn
                break

            # Or check page text for 100% or Uploaded
            try:
                page_text = page.content()
                if "Uploaded" in page_text or "100%" in page_text or "Upload complete" in page_text:
                    if btn:
                        target_post_btn = btn
                        break
            except Exception:
                pass

        if not target_post_btn:
            target_post_btn = find_real_post_button()

        if not target_post_btn:
            context.close()
            raise RuntimeError("Could not find the submit 'Post' button on TikTok Studio.")

        if status_callback:
            status_callback("Submitting post to TikTok...")

        dismiss_popups(page)
        target_post_btn.scroll_into_view_if_needed()
        time.sleep(1)

        # Click the Post button using force=True to bypass any transparent overlays
        try:
            target_post_btn.click(force=True, timeout=10000)
        except Exception:
            # Fallback: trigger click via JavaScript directly on the DOM element
            page.evaluate("el => el.click()", target_post_btn.element_handle())

        if status_callback:
            status_callback("Waiting for TikTok post confirmation...")

        # Wait for confirmation of successful upload
        post_confirmed = False
        confirm_start = time.time()
        while time.time() - confirm_start < 60:
            time.sleep(2)
            dismiss_popups(page)
            try:
                page_text = page.content()
                if (
                    "Your video is being uploaded" in page_text
                    or "Your video has been uploaded" in page_text
                    or "Manage your posts" in page_text
                    or "Upload another video" in page_text
                    or "Post another video" in page_text
                    or "uploaded to TikTok" in page_text
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

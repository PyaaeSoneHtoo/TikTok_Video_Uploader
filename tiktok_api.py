"""
TikTok Content Posting API (v2) Client
Handles OAuth 2.0 authentication, token management, and direct video uploads.
"""

import os
import time
import json
import uuid
import math
import logging
from typing import Optional, Callable, Dict, Any
import requests

logger = logging.getLogger(__name__)

class TikTokAPIError(Exception):
    """Custom exception for TikTok API errors."""
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.code = code
        self.details = details


class TikTokAPI:
    AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
    TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
    CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
    VIDEO_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    STATUS_FETCH_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

    # Default OAuth Scopes needed for Content Posting API
    SCOPES = [
        "user.info.basic",
        "video.upload",
        "video.publish"
    ]

    # Chunk size constants (TikTok requires chunks between 5MB and 64MB)
    MIN_CHUNK_SIZE = 5 * 1024 * 1024   # 5 MB
    MAX_CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB
    DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(
        self,
        client_key: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:5000/callback",
        tokens_file: Optional[str] = None
    ):
        self.client_key = client_key
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.tokens_file = tokens_file or os.path.join(base_dir, "tokens.json")
        self.tokens: Dict[str, Any] = self.load_tokens()

    def load_tokens(self) -> Dict[str, Any]:
        """Loads cached OAuth tokens from file if present."""
        if os.path.exists(self.tokens_file):
            try:
                with open(self.tokens_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not read tokens file: {e}")
        return {}

    def save_tokens(self, token_data: Dict[str, Any]) -> None:
        """Saves OAuth tokens to file with local acquired timestamp."""
        token_data["acquired_at"] = time.time()
        self.tokens = token_data
        try:
            with open(self.tokens_file, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2)
            logger.info("Tokens successfully saved to file.")
        except Exception as e:
            logger.error(f"Error saving tokens to file: {e}")

    def clear_tokens(self) -> None:
        """Clears local tokens."""
        self.tokens = {}
        if os.path.exists(self.tokens_file):
            try:
                os.remove(self.tokens_file)
            except Exception as e:
                logger.error(f"Error removing tokens file: {e}")

    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """
        Generates the TikTok OAuth 2.0 authorization URL.
        Returns: (authorization_url, state)
        """
        if not state:
            state = uuid.uuid4().hex

        scopes_str = ",".join(self.SCOPES)
        params = {
            "client_key": self.client_key,
            "scope": scopes_str,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state
        }
        req = requests.Request("GET", self.AUTH_URL, params=params).prepare()
        return req.url, state

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """
        Exchanges the authorization code for an access token & refresh token.
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache"
        }
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri
        }

        response = requests.post(self.TOKEN_URL, headers=headers, data=data, timeout=30)
        res_json = response.json()

        if response.status_code != 200 or res_json.get("error"):
            err_code = res_json.get("error", "token_exchange_failed")
            err_desc = res_json.get("error_description", response.text)
            raise TikTokAPIError(f"Failed to exchange code: {err_desc} ({err_code})", code=err_code)

        token_data = res_json.get("data", res_json)
        self.save_tokens(token_data)
        return token_data

    def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refreshes an expired access token using the refresh token.
        """
        refresh_token = self.tokens.get("refresh_token")
        if not refresh_token:
            raise TikTokAPIError("No refresh token available. User must re-authenticate.")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache"
        }
        data = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        response = requests.post(self.TOKEN_URL, headers=headers, data=data, timeout=30)
        res_json = response.json()

        if response.status_code != 200 or res_json.get("error"):
            err_code = res_json.get("error", "token_refresh_failed")
            err_desc = res_json.get("error_description", response.text)
            raise TikTokAPIError(f"Failed to refresh token: {err_desc} ({err_code})", code=err_code)

        token_data = res_json.get("data", res_json)
        # Preserve original refresh token if new one is not provided
        if "refresh_token" not in token_data:
            token_data["refresh_token"] = refresh_token
            
        self.save_tokens(token_data)
        return token_data

    def get_valid_access_token(self) -> str:
        """
        Returns a valid access token, automatically refreshing if it has expired.
        """
        access_token = self.tokens.get("access_token")
        if not access_token:
            raise TikTokAPIError("Not authenticated. Please connect your TikTok account first.")

        expires_in = self.tokens.get("expires_in", 86400)
        acquired_at = self.tokens.get("acquired_at", 0)
        elapsed = time.time() - acquired_at

        # Refresh 5 minutes before expiration
        if elapsed >= (expires_in - 300):
            logger.info("Access token expired or expiring soon; refreshing...")
            new_tokens = self.refresh_access_token()
            access_token = new_tokens["access_token"]

        return access_token

    def get_user_info(self) -> Dict[str, Any]:
        """
        Retrieves basic profile info of the authenticated user.
        """
        token = self.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}"
        }
        params = {
            "fields": "open_id,union_id,avatar_url,display_name"
        }
        res = requests.get(self.USER_INFO_URL, headers=headers, params=params, timeout=20)
        res_json = res.json()
        if res_json.get("error", {}).get("code") != "ok" and res.status_code != 200:
            raise TikTokAPIError(f"Failed to fetch user info: {res_json}", details=res_json)
        return res_json.get("data", {}).get("user", {})

    def query_creator_info(self) -> Dict[str, Any]:
        """
        Queries creator post limitations, privacy options, and allowed features.
        """
        token = self.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        res = requests.post(self.CREATOR_INFO_URL, headers=headers, json={}, timeout=20)
        res_json = res.json()
        if res_json.get("error", {}).get("code") != "ok" and res.status_code != 200:
            raise TikTokAPIError(f"Failed to query creator info: {res_json}", details=res_json)
        return res_json.get("data", {})

    def init_video_upload(
        self,
        video_path: str,
        title: str,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
        disable_duet: bool = False,
        disable_stitch: bool = False,
        disable_comment: bool = False,
        video_cover_timestamp_ms: int = 1000,
        brand_content_toggle: bool = False,
        brand_organic_toggle: bool = False
    ) -> tuple[str, str, int, int]:
        """
        Initializes the video upload session with TikTok Content Posting API.
        Returns: (publish_id, upload_url, chunk_size, total_chunk_count)
        """
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        file_size = os.path.getsize(video_path)
        if file_size == 0:
            raise ValueError("Video file is empty (0 bytes).")

        # Determine appropriate chunk size
        if file_size <= self.MAX_CHUNK_SIZE:
            chunk_size = file_size
            total_chunks = 1
        else:
            chunk_size = self.DEFAULT_CHUNK_SIZE
            total_chunks = math.ceil(file_size / chunk_size)

        payload = {
            "post_info": {
                "title": title,
                "privacy_level": privacy_level,
                "disable_duet": disable_duet,
                "disable_stitch": disable_stitch,
                "disable_comment": disable_comment,
                "video_cover_timestamp_ms": video_cover_timestamp_ms,
                "brand_content_toggle": brand_content_toggle,
                "brand_organic_toggle": brand_organic_toggle
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks
            }
        }

        token = self.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        res = requests.post(self.VIDEO_INIT_URL, headers=headers, json=payload, timeout=30)
        res_json = res.json()

        err_info = res_json.get("error", {})
        if err_info.get("code") != "ok":
            code = err_info.get("code")
            msg = err_info.get("message", "Unknown initialization error")
            raise TikTokAPIError(f"Video init failed: {msg} (code: {code})", code=code, details=res_json)

        data = res_json.get("data", {})
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")

        if not publish_id or not upload_url:
            raise TikTokAPIError(f"Missing publish_id or upload_url in response: {res_json}")

        return publish_id, upload_url, chunk_size, total_chunks

    def upload_chunks(
        self,
        upload_url: str,
        video_path: str,
        chunk_size: int,
        progress_callback: Optional[Callable[[float, int, int], None]] = None
    ) -> None:
        """
        Uploads video chunks sequentially to the presigned upload_url.
        Calls progress_callback(progress_percentage, bytes_uploaded, total_bytes).
        """
        total_size = os.path.getsize(video_path)
        bytes_uploaded = 0

        with open(video_path, "rb") as f:
            chunk_index = 0
            while bytes_uploaded < total_size:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break

                current_chunk_size = len(chunk_data)
                start_byte = bytes_uploaded
                end_byte = bytes_uploaded + current_chunk_size - 1

                headers = {
                    "Content-Range": f"bytes {start_byte}-{end_byte}/{total_size}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(current_chunk_size)
                }

                # Upload chunk with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        res = requests.put(upload_url, headers=headers, data=chunk_data, timeout=60)
                        # Success statuses for chunk upload: 200, 201, 204, or 308
                        if res.status_code in [200, 201, 204, 308]:
                            break
                        else:
                            raise requests.RequestException(f"Status code {res.status_code}: {res.text}")
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise TikTokAPIError(f"Failed to upload chunk {chunk_index} after {max_retries} attempts: {e}")
                        time.sleep(2 ** attempt)

                bytes_uploaded += current_chunk_size
                chunk_index += 1

                if progress_callback:
                    pct = (bytes_uploaded / total_size) * 100.0
                    progress_callback(pct, bytes_uploaded, total_size)

    def fetch_publish_status(self, publish_id: str) -> Dict[str, Any]:
        """
        Checks the status of the published video.
        Returns: Dict containing 'status', 'fail_reason', etc.
        """
        token = self.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        payload = {"publish_id": publish_id}

        res = requests.post(self.STATUS_FETCH_URL, headers=headers, json=payload, timeout=20)
        res_json = res.json()

        err_info = res_json.get("error", {})
        if err_info.get("code") != "ok":
            code = err_info.get("code")
            msg = err_info.get("message", "Status fetch error")
            raise TikTokAPIError(f"Status fetch failed: {msg} (code: {code})", code=code)

        return res_json.get("data", {})

    def upload_and_publish(
        self,
        video_path: str,
        title: str,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
        disable_duet: bool = False,
        disable_stitch: bool = False,
        disable_comment: bool = False,
        progress_callback: Optional[Callable[[float, int, int], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Full end-to-end publishing pipeline:
        1. Initialize upload session
        2. Stream chunks
        3. Poll publish status until terminal state (SUCCESS or FAILED)
        """
        if status_callback:
            status_callback("Initializing video upload with TikTok...")

        publish_id, upload_url, chunk_size, total_chunks = self.init_video_upload(
            video_path=video_path,
            title=title,
            privacy_level=privacy_level,
            disable_duet=disable_duet,
            disable_stitch=disable_stitch,
            disable_comment=disable_comment
        )

        if status_callback:
            status_callback(f"Upload initialized (Publish ID: {publish_id}). Uploading {total_chunks} chunk(s)...")

        self.upload_chunks(
            upload_url=upload_url,
            video_path=video_path,
            chunk_size=chunk_size,
            progress_callback=progress_callback
        )

        if status_callback:
            status_callback("Chunks uploaded! Waiting for TikTok processing...")

        # Poll status
        max_polls = 60
        poll_interval = 3
        for poll_count in range(max_polls):
            time.sleep(poll_interval)
            status_data = self.fetch_publish_status(publish_id)
            status = status_data.get("status")

            if status_callback:
                status_callback(f"TikTok Processing: {status} ({poll_count + 1}/{max_polls})")

            if status == "SUCCESS":
                return {
                    "success": True,
                    "publish_id": publish_id,
                    "status_data": status_data
                }
            elif status == "FAILED":
                fail_reason = status_data.get("fail_reason", "Unknown failure reason")
                raise TikTokAPIError(f"TikTok publication failed: {fail_reason}", details=status_data)

        return {
            "success": True,
            "publish_id": publish_id,
            "status": "PROCESSING_TIMEOUT",
            "message": "Video was uploaded but TikTok processing is still running in background."
        }

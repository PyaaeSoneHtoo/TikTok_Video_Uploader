"""
Local OAuth Callback Listener Server
Captures the TikTok OAuth code from the browser redirect and handles shutdown cleanly.
"""

import sys
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Callable


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    server: "OAuthServer"

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]
            error_description = params.get("error_description", ["Unknown error"])[0]

            if error:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>TikTok Auth Failed</title>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #121212; color: #fff; text-align: center; padding: 60px 20px; }}
                        .card {{ background: #1e1e1e; max-width: 480px; margin: auto; padding: 30px; border-radius: 12px; border: 1px solid #ef4444; }}
                        h2 {{ color: #ef4444; }}
                        p {{ color: #a1a1aa; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>⚠️ Authorization Failed</h2>
                        <p><strong>Error:</strong> {error}</p>
                        <p>{error_description}</p>
                        <p>You can close this window and try again in the app.</p>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(html.encode("utf-8"))
                self.server.received_error = f"{error}: {error_description}"
            elif code:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>TikTok Auth Successful</title>
                    <style>
                        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f12; color: #ffffff; text-align: center; padding: 60px 20px; }
                        .card { background: #18181b; max-width: 480px; margin: auto; padding: 40px 30px; border-radius: 16px; border: 1px solid #27272a; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
                        .badge { display: inline-block; width: 60px; height: 60px; line-height: 60px; border-radius: 50%; background: #22c55e; color: #fff; font-size: 32px; margin-bottom: 20px; }
                        h2 { margin: 0 0 10px; font-size: 24px; color: #f4f4f5; }
                        p { color: #a1a1aa; line-height: 1.5; font-size: 15px; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <div class="badge">✓</div>
                        <h2>Authentication Successful!</h2>
                        <p>Your TikTok account is connected.</p>
                        <p>You can safely close this browser tab and return to the TikTok Video Uploader application.</p>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(html.encode("utf-8"))
                self.server.received_code = code
                self.server.received_state = state
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing authorization code in query parameters.")

            # Trigger server shutdown in another thread
            threading.Thread(target=self.server.shutdown_server).start()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        # Suppress noisy console logs
        pass


class OAuthServer(HTTPServer):
    def __init__(self, host: str = "localhost", port: int = 5000):
        super().__init__((host, port), OAuthCallbackHandler)
        self.received_code: Optional[str] = None
        self.received_state: Optional[str] = None
        self.received_error: Optional[str] = None
        self.is_running = True

    def shutdown_server(self):
        import time
        time.sleep(1)
        self.shutdown()
        self.server_close()
        self.is_running = False


def wait_for_oauth_code(
    host: str = "localhost",
    port: int = 5000,
    timeout_seconds: int = 180
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Starts local server, waits for the redirect with code or timeout.
    Returns: (code, state, error)
    """
    server = OAuthServer(host=host, port=port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    server_thread.join(timeout=timeout_seconds)
    if server.is_running:
        server.shutdown_server()

    return server.received_code, server.received_state, server.received_error

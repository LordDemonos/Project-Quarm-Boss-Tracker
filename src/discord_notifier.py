"""Send notifications to Discord via webhook."""
import requests
import re
import json as _json
from pathlib import Path
from typing import Optional
from queue import Queue
import threading
import time

def _webhook_id(url):
    if not url or not isinstance(url, str):
        return ""
    m = re.search(r"/webhooks/(\d+)", url.strip())
    return m.group(1) if m else ""

def _debug_log(location, message, data, hypothesis_id):
    try:
        p = Path(__file__).resolve().parent.parent / ".cursor" / "debug.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(_json.dumps({"location": location, "message": message, "data": data or {}, "hypothesisId": hypothesis_id, "timestamp": time.time() * 1000}) + "\n")
    except Exception:
        pass

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


def _mask_webhook(url: str) -> str:
    """Return a safe string for logging (avoid exposing full webhook URL)."""
    if not url or not isinstance(url, str):
        return "(empty)"
    s = url.strip()
    if len(s) <= 20:
        return "****"
    return f"{s[:30]}...{s[-4:]}" if len(s) > 40 else f"{s[:15]}...{s[-4:]}"


class DiscordNotifier:
    """Handles Discord webhook notifications."""
    
    def __init__(self, default_webhook_url: Optional[str] = None,
                 timestamp_formatter=None):
        """
        Initialize the Discord notifier.

        Args:
            default_webhook_url: Webhook URL from settings (used for all Discord posts)
            timestamp_formatter: TimestampFormatter instance for Discord timestamp formatting
        """
        self.default_webhook_url = default_webhook_url
        self.timestamp_formatter = timestamp_formatter
        self.message_queue = Queue()
        self.worker_thread = None
        self.running = False
    
    def start(self) -> None:
        """Start the notification worker thread."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
            logger.info("Discord notifier worker thread started")
    
    def stop(self) -> None:
        """Stop the notification worker thread."""
        self.running = False
        if self.worker_thread:
            self.message_queue.put(None)  # Signal to stop
            self.worker_thread.join(timeout=5)
            logger.info("Discord notifier worker thread stopped")
    
    def _worker(self) -> None:
        """Worker thread that processes queued messages."""
        while self.running:
            try:
                item = self.message_queue.get(timeout=1)
                if item is None:  # Stop signal
                    break
                
                webhook_url, message = item
                # #region agent log
                _debug_log("discord_notifier._worker", "item from queue", {"webhook_id": _webhook_id(webhook_url)}, "H4")
                # #endregion
                if not (webhook_url and webhook_url.strip()):
                    logger.warning("[DISCORD] Worker: skipping queued message - webhook URL is empty")
                    self.message_queue.task_done()
                    continue
                logger.debug(f"[DISCORD] Worker: sending queued message to webhook {_mask_webhook(webhook_url)}")
                self._send_message(webhook_url, message)
                self.message_queue.task_done()
                
                # Rate limiting: wait a bit between messages
                time.sleep(0.5)
            except:
                continue
    
    def _send_message(self, webhook_url: str, message: str) -> None:
        """
        Send a message to Discord webhook.

        Args:
            webhook_url: Discord webhook URL
            message: Message content to send
        """
        if not webhook_url:
            logger.warning("Attempted to send Discord message but no webhook URL provided")
            return
        # #region agent log
        _debug_log("discord_notifier._send_message", "about to requests.post", {"webhook_id": _webhook_id(webhook_url)}, "H4")
        # #endregion
        try:
            logger.info(f"[DISCORD] Sending to webhook {_mask_webhook(webhook_url)}")
            logger.debug(f"[DISCORD] Message preview: {message[:80]}...")
            response = requests.post(
                webhook_url,
                json={'content': message},
                timeout=10
            )
            response.raise_for_status()
            logger.info(f"[DISCORD] Message sent successfully to webhook {_mask_webhook(webhook_url)}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Discord notification: {e}")
    
    def format_message(self, template: str, timestamp: Optional[str] = None, **kwargs) -> str:
        """
        Format a message using template variables.
        
        Supports Discord timestamp variables:
        - {discord_timestamp} - Full date/time format
        - {discord_timestamp_relative} - Relative format
        
        Special handling for {note} variable:
        - If note is empty, {note} and surrounding parentheses/spaces are removed
        
        Args:
            template: Message template with {variable} placeholders
            timestamp: Timestamp string from log (for Discord timestamp formatting)
            **kwargs: Variables to substitute in template
            
        Returns:
            Formatted message string
        """
        # Add Discord timestamp variables if timestamp formatter available
        if self.timestamp_formatter and timestamp:
            kwargs['discord_timestamp'] = self.timestamp_formatter.format_discord_timestamp_full(timestamp)
            kwargs['discord_timestamp_relative'] = self.timestamp_formatter.format_discord_timestamp_relative(timestamp)
            logger.debug(f"Added Discord timestamp variables for timestamp: {timestamp}")
        
        # Ensure timestamp variable exists (original log timestamp)
        if 'timestamp' not in kwargs and timestamp:
            kwargs['timestamp'] = timestamp
        
        # Handle {note} variable - remove it if note is empty
        note = kwargs.get('note', '').strip()
        if not note:
            # Remove {note} and clean up surrounding spaces/punctuation
            # Remove {note} and any surrounding parentheses and spaces
            template = re.sub(r'\s*\(?\s*\{note\}\s*\)?\s*', ' ', template)
            # Clean up multiple spaces
            template = re.sub(r'\s+', ' ', template).strip()
            # Remove note from kwargs so format() doesn't try to use it
            kwargs = {k: v for k, v in kwargs.items() if k != 'note'}
        
        try:
            result = template.format(**kwargs)
            logger.debug(f"Formatted message template: {result[:100]}...")
            return result
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            return template
    
    def notify(self, message: str, webhook_url: Optional[str] = None) -> None:
        """
        Queue a notification to be sent.

        Args:
            message: Message content
            webhook_url: Webhook URL to use. None = use instance default; '' = do not post.
                CRITICAL: When caller passes any value (including ''), that value is used and
                we never fall back to default_webhook_url. This ensures main's file-based URL wins.
        """
        # Only use instance default when caller did not pass a value (None). Otherwise use exactly what was passed.
        if webhook_url is None:
            url = (self.default_webhook_url or "").strip()
        else:
            url = (webhook_url or "").strip()
        # #region agent log
        _debug_log("discord_notifier.notify", "url chosen", {"param_webhook_id": _webhook_id(webhook_url), "default_webhook_id": _webhook_id(self.default_webhook_url), "url_used_id": _webhook_id(url), "param_is_none": webhook_url is None}, "H3")
        # #endregion
        if url:
            logger.debug(f"[DISCORD] Queueing notification to webhook {_mask_webhook(url)}: {message[:60]}...")
            self.message_queue.put((url, message))
        else:
            logger.warning("Cannot queue notification: no webhook URL available")


"""Quick Start dialog: one-pager for Discord Bot/Token and Webhook URL setup."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser, QPushButton
)
from PyQt6.QtCore import Qt
from pathlib import Path
import sys
import urllib.parse

try:
    from .logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


def _get_base_dir() -> Path:
    """Base directory for assets (script or frozen)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def _get_assets_dir() -> Path:
    """Directory for Quick Start images."""
    return _get_base_dir() / "assets" / "quick_start"


def _file_url(path: Path) -> str:
    """Return file:// URL for local path (QTextBrowser img src)."""
    return "file:///" + urllib.parse.quote(str(path.resolve().as_posix()))


def _build_html(assets_dir: Path) -> str:
    """Build HTML for the one-pager. Embeds images only if files exist."""
    bot_img = assets_dir / "bot_token.png"
    webhook_img = assets_dir / "webhook_url.png"

    bot_img_html = ""
    if bot_img.exists():
        bot_img_html = f'<p><img src="{_file_url(bot_img)}" alt="Discord Bot Token" style="max-width:100%;"/></p>'
    webhook_img_html = ""
    if webhook_img.exists():
        webhook_img_html = f'<p><img src="{_file_url(webhook_img)}" alt="Discord Webhook URL" style="max-width:100%;"/></p>'

    return f"""
<h2>1. Discord Bot and Bot Token</h2>
<p>You need a Bot Token for optional features (e.g. Discord sync and duplicate detection).</p>
<ol>
<li>Open the <a href="https://discord.com/developers/applications">Discord Developer Portal</a> and log in.</li>
<li>Click <strong>New Application</strong>, name it (e.g. "Boss Tracker"), and create it.</li>
<li>In the left sidebar, open <strong>Bot</strong>.</li>
<li>Click <strong>Add Bot</strong> and confirm.</li>
<li>Under <strong>Token</strong>, click <strong>Reset Token</strong> (or <strong>Copy</strong> if you already have one). Copy and save the token somewhere safe — you'll paste it in Settings in this app.</li>
<li>Scroll down to <strong>Privileged Gateway Intents</strong>.</li>
<li>Enable <strong>Message Content Intent</strong> (required so the bot can read messages for duplicate detection).</li>
<li>Click <strong>Save Changes</strong>.</li>
</ol>
<h3>Invite the bot to your server</h3>
<ol>
<li>In the Developer Portal, go to <strong>OAuth2</strong> → <strong>URL Generator</strong>.</li>
<li>Under <strong>Scopes</strong>, select <code>bot</code> (and optionally <code>applications.commands</code>).</li>
<li>Under <strong>Bot Permissions</strong>, select <strong>Read Message History</strong> and <strong>View Channels</strong>.</li>
<li>Copy the generated URL and open it in your browser. Select your server and authorize the bot.</li>
<li>Ensure the bot has access to the channel where your webhook posts messages.</li>
</ol>
{bot_img_html}

<h2>2. Discord Webhook URL (for server admins)</h2>
<p>To post kill messages to a channel, you need a Webhook URL. Only someone with permission to manage webhooks can create it.</p>
<ol>
<li>Open Discord and go to your server.</li>
<li>Go to <strong>Server Settings</strong> → <strong>Integrations</strong> → <strong>Webhooks</strong>.</li>
<li>Click <strong>New Webhook</strong> or <strong>Create Webhook</strong>.</li>
<li>Configure: set <strong>Name</strong> (e.g. "Boss Tracker"), select the <strong>Channel</strong> where kill messages should appear, then click <strong>Copy Webhook URL</strong>. Save this URL — you'll paste it in this app's Settings.</li>
<li>Click <strong>Save Changes</strong>.</li>
</ol>
{webhook_img_html}
"""


class QuickStartDialog(QDialog):
    """Modal dialog showing Quick Start text and optional images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Start")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)
        logger.debug("Showing Quick Start dialog")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        assets_dir = _get_assets_dir()
        html = _build_html(assets_dir)
        browser.setHtml(html)
        layout.addWidget(browser)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumWidth(100)
        button_layout.addWidget(close_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

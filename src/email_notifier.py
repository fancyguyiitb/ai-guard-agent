"""
Email notification system for escalation alerts.
Sends email notifications when Level 3 escalation is triggered.
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
import os
from datetime import datetime
from pathlib import Path

# Load .env file manually if it exists
def load_env_file():
    """Load environment variables from .env file."""
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    os.environ[key] = value
        print("Environment variables loaded successfully")
    else:
        print(f"No .env file found at {env_path}")

# Try to load .env file if python-dotenv is available, otherwise load manually
try:
    from dotenv import load_dotenv
    # Load .env file from project root
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment variables from {env_path}")
except ImportError:
    # python-dotenv not installed, load manually
    load_env_file()

class EmailNotifier:
    """Handles email notifications for security alerts."""
    
    def __init__(self):
        self.logger = logging.getLogger("EmailNotifier")
        self.smtp_server = None
        self.smtp_port = None
        self.sender_email = None
        self.sender_password = None
        self.recipients = []
        self._load_config()
    
    def _load_config(self):
        """Load email configuration from environment variables or defaults."""
        # SMTP Configuration
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        
        # Sender credentials
        self.sender_email = os.getenv('SENDER_EMAIL', '')
        self.sender_password = os.getenv('SENDER_PASSWORD', '')
        
        # Recipients (comma-separated list)
        recipients_str = os.getenv('RECIPIENT_EMAILS', '')
        if recipients_str:
            self.recipients = [email.strip() for email in recipients_str.split(',')]
        else:
            # Default recipients if none specified
            self.recipients = ['security@example.com']
        
        self.logger.info(f"Email notifier initialized. Recipients: {self.recipients}")
    
    def send_escalation_alert(self, escalation_details=None, snapshot_path=None):
        """
        Send email alert for Level 3 escalation.
        
        Args:
            escalation_details (dict): Optional details about the escalation
            snapshot_path (str): Path to intruder snapshot image to attach
        """
        if not self.recipients or not self.sender_email:
            self.logger.warning("Email configuration incomplete. Cannot send alert.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipients)
            msg['Subject'] = "🚨 SECURITY ALERT - Level 3 Escalation Triggered"
            
            # Create email body
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            body = f"""
SECURITY ALERT - AI ROOM GUARD SYSTEM

⚠️  LEVEL 3 ESCALATION TRIGGERED ⚠️

Time: {timestamp}
Location: AI Room Guard System
Status: INTRUDER DETECTED

ESCALATION DETAILS:
- Stage 1: Warning issued - "Excuse me, I don't recognize you. Please identify yourself."
- Stage 2: Second warning - "You are not authorized to be here. Please leave immediately."
- Stage 3: FINAL ALERT - "ALERT. Intruder detected. Security and the room owner have been notified."

IMMEDIATE ACTION REQUIRED:
1. Check security cameras
2. Contact security personnel
3. Verify room access logs
4. Investigate the incident

SYSTEM STATUS:
- Face recognition: Active
- Escalation system: Triggered
- Alert level: Maximum (Level 3)
- Intruder snapshot: Attached to this email

This is an automated alert from the AI Room Guard System.
Please investigate immediately.

---
AI Room Guard Security System
Generated at: {timestamp}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach snapshot if provided
            if snapshot_path and os.path.exists(snapshot_path):
                try:
                    with open(snapshot_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    filename = os.path.basename(snapshot_path)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}',
                    )
                    msg.attach(part)
                    self.logger.info(f"Attached snapshot: {filename}")
                except Exception as e:
                    self.logger.error(f"Failed to attach snapshot: {e}")
            else:
                if snapshot_path:
                    self.logger.warning(f"Snapshot file not found: {snapshot_path}")
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                
                text = msg.as_string()
                server.sendmail(self.sender_email, self.recipients, text)
                
            self.logger.info(f"Security alert email sent successfully to {len(self.recipients)} recipients")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            return False
    
    def test_email_config(self):
        """Test email configuration by sending a test message."""
        if not self.recipients or not self.sender_email:
            self.logger.error("Email configuration incomplete. Cannot send test email.")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(self.recipients)
            msg['Subject'] = "AI Room Guard - Email Configuration Test"
            
            body = """
This is a test email from the AI Room Guard System.

If you receive this email, the email notification system is properly configured and ready to send security alerts.

System Status: Email notifications ACTIVE
Test Time: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """

---
AI Room Guard Security System
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                
                text = msg.as_string()
                server.sendmail(self.sender_email, self.recipients, text)
                
            self.logger.info("Test email sent successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send test email: {e}")
            return False

# Global instance for easy access
email_notifier = EmailNotifier()

def send_escalation_alert(escalation_details=None, snapshot_path=None):
    """Send escalation alert email."""
    return email_notifier.send_escalation_alert(escalation_details, snapshot_path)

def test_email_config():
    """Test email configuration."""
    return email_notifier.test_email_config()

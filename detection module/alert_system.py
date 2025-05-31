import smtplib
import os
import cv2
import threading
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import requests

class AlertSystem:
    def __init__(self, config):
        self.config = config
        self.last_alert_time = {}
        self.recording = False
        
    def should_send_alert(self, zone_name):
        """Check if enough time has passed since last alert for this zone"""
        current_time = time.time()
        if zone_name not in self.last_alert_time:
            self.last_alert_time[zone_name] = current_time
            return True
        
        if current_time - self.last_alert_time[zone_name] > self.config.ALERT_COOLDOWN:
            self.last_alert_time[zone_name] = current_time
            return True
        
        return False
    
    def send_email_alert(self, subject, body, video_path=None):
        """Send email alert with optional video attachment"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.EMAIL_USER
            msg['To'] = self.config.ALERT_EMAIL
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach video if provided
            if video_path and os.path.exists(video_path):
                with open(video_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(video_path)}'
                )
                msg.attach(part)
            
            # Send email
            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT)
            server.starttls()
            server.login(self.config.EMAIL_USER, self.config.EMAIL_PASS)
            text = msg.as_string()
            server.sendmail(self.config.EMAIL_USER, self.config.ALERT_EMAIL, text)
            server.quit()
            
            logging.info(f"Email alert sent successfully to {self.config.ALERT_EMAIL}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to send email alert: {str(e)}")
            return False
    
    def send_telegram_alert(self, message, video_path=None):
        """Send Telegram alert with optional video"""
        try:
            if not self.config.TELEGRAM_BOT_TOKEN or not self.config.TELEGRAM_CHAT_ID:
                logging.warning("Telegram credentials not configured")
                return False
            
            url = f"https://api.telegram.org/bot{self.config.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': self.config.TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data)
            
            # Send video if provided
            if video_path and os.path.exists(video_path):
                video_url = f"https://api.telegram.org/bot{self.config.TELEGRAM_BOT_TOKEN}/sendVideo"
                with open(video_path, 'rb') as video:
                    files = {'video': video}
                    video_data = {'chat_id': self.config.TELEGRAM_CHAT_ID}
                    requests.post(video_url, data=video_data, files=files)
            
            if response.status_code == 200:
                logging.info("Telegram alert sent successfully")
                return True
            else:
                logging.error(f"Telegram alert failed: {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Failed to send Telegram alert: {str(e)}")
            return False
    
    def record_incident(self, cap, duration=10):
        """Record video incident"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"incident_{timestamp}.avi"
            filepath = os.path.join('static/uploads', filename)
            
            # Ensure directory exists
            os.makedirs('static/uploads', exist_ok=True)
            
            # Set up video writer
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            fps = int(cap.get(cv2.CAP_PROP_FPS)) or 20
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
            
            # Record for specified duration
            start_time = time.time()
            frames_recorded = 0
            
            while (time.time() - start_time) < duration:
                ret, frame = cap.read()
                if ret:
                    out.write(frame)
                    frames_recorded += 1
                else:
                    break
            
            out.release()
            
            if frames_recorded > 0:
                logging.info(f"Incident recorded: {filepath} ({frames_recorded} frames)")
                return filepath
            else:
                os.remove(filepath)
                return None
                
        except Exception as e:
            logging.error(f"Error recording incident: {str(e)}")
            return None
    
    def trigger_alert(self, alert_type, zone_name, confidence, coordinates, cap=None):
        """Main method to trigger all alert mechanisms"""
        if not self.should_send_alert(zone_name):
            return False
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Record incident video
        video_path = None
        if cap is not None:
            video_path = self.record_incident(cap, self.config.RECORDING_DURATION)
        
        # Prepare alert messages
        subject = f"🚨 SECURITY ALERT - {alert_type.upper()}"
        email_body = f"""
SECURITY ALERT DETECTED

Time: {timestamp}
Alert Type: {alert_type}
Zone: {zone_name}
Confidence: {confidence:.2f}%
Coordinates: {coordinates}

This is an automated alert from your Smart Surveillance System.
Please check the attached video for details.

System Status: Active
Location: Your Security System
        """
        
        telegram_message = f"""
🚨 <b>SECURITY ALERT</b> 🚨

📅 <b>Time:</b> {timestamp}
🔍 <b>Type:</b> {alert_type}
📍 <b>Zone:</b> {zone_name}
📊 <b>Confidence:</b> {confidence:.1f}%

⚠️ Immediate attention required!
        """
        
        # Send alerts in parallel threads
        email_thread = threading.Thread(
            target=self.send_email_alert,
            args=(subject, email_body, video_path)
        )
        telegram_thread = threading.Thread(
            target=self.send_telegram_alert,
            args=(telegram_message, video_path)
        )
        
        email_thread.start()
        telegram_thread.start()
        
        logging.info(f"Alert triggered for {zone_name}: {alert_type}")
        return True
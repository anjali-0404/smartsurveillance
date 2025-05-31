import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database Configuration
    DATABASE_PATH = 'database/surveillance.db'
    
    # Camera Configuration
    CAMERA_INDEX = 0  # 0 for default webcam, or IP camera URL
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 480
    FPS = 30
    
    # Detection Configuration
    CONFIDENCE_THRESHOLD = 0.5
    NMS_THRESHOLD = 0.4
    MODEL_PATH = 'models/yolov8n.pt'
    
    # Alert Configuration
    ALERT_COOLDOWN = 30  # seconds between alerts
    RECORDING_DURATION = 10  # seconds
    
    # Email Configuration
    SMTP_SERVER = 'smtp.gmail.com'
    SMTP_PORT = 587
    EMAIL_USER = os.getenv('EMAIL_USER', 'your_email@gmail.com')
    EMAIL_PASS = os.getenv('EMAIL_PASS', 'your_app_password')
    ALERT_EMAIL = os.getenv('ALERT_EMAIL', 'alert_recipient@gmail.com')
    
    # Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key_here')
    DEBUG = True
    
    # Surveillance Zones (normalized coordinates)
    RESTRICTED_ZONES = [
        {'name': 'Main Entrance', 'coords': [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]},
        {'name': 'Office Area', 'coords': [(0.3, 0.3), (0.7, 0.3), (0.7, 0.7), (0.3, 0.7)]}
    ]
import sqlite3
import os
from datetime import datetime
import json
import logging

class DatabaseManager:
    def __init__(self, db_path='database/surveillance.db'):
        self.db_path = db_path
        self.ensure_directory()
        self.init_database()
    
    def ensure_directory(self):
        """Ensure database directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def init_database(self):
        """Initialize database tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create alerts table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        alert_type VARCHAR(50),
                        confidence FLOAT,
                        zone_name VARCHAR(100),
                        coordinates TEXT,
                        video_path VARCHAR(255),
                        status VARCHAR(20) DEFAULT 'active',
                        notes TEXT
                    )
                ''')
                
                # Create system_logs table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        log_level VARCHAR(20),
                        message TEXT,
                        module VARCHAR(50)
                    )
                ''')
                
                # Create settings table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        setting_name VARCHAR(100) UNIQUE,
                        setting_value TEXT,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logging.info("Database initialized successfully")
                
        except Exception as e:
            logging.error(f"Database initialization error: {str(e)}")
    
    def add_alert(self, alert_type, confidence, zone_name, coordinates, video_path=None):
        """Add new alert to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alerts (alert_type, confidence, zone_name, coordinates, video_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (alert_type, confidence, zone_name, json.dumps(coordinates), video_path))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Error adding alert: {str(e)}")
            return None
    
    def get_recent_alerts(self, limit=50):
        """Get recent alerts"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM alerts 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching alerts: {str(e)}")
            return []
    
    def add_log(self, level, message, module):
        """Add system log entry"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO system_logs (log_level, message, module)
                    VALUES (?, ?, ?)
                ''', (level, message, module))
                conn.commit()
        except Exception as e:
            logging.error(f"Error adding log: {str(e)}")
    
    def get_system_stats(self):
        """Get system statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total alerts today
                cursor.execute('''
                    SELECT COUNT(*) FROM alerts 
                    WHERE DATE(timestamp) = DATE('now')
                ''')
                alerts_today = cursor.fetchone()[0]
                
                # Total alerts this week
                cursor.execute('''
                    SELECT COUNT(*) FROM alerts 
                    WHERE timestamp >= datetime('now', '-7 days')
                ''')
                alerts_week = cursor.fetchone()[0]
                
                # Most active zone
                cursor.execute('''
                    SELECT zone_name, COUNT(*) as count 
                    FROM alerts 
                    WHERE timestamp >= datetime('now', '-7 days')
                    GROUP BY zone_name 
                    ORDER BY count DESC 
                    LIMIT 1
                ''')
                active_zone = cursor.fetchone()
                
                return {
                    'alerts_today': alerts_today,
                    'alerts_week': alerts_week,
                    'most_active_zone': active_zone[0] if active_zone else 'None',
                    'zone_activity_count': active_zone[1] if active_zone else 0
                }
        except Exception as e:
            logging.error(f"Error getting stats: {str(e)}")
            return {}
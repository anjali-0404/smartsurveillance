import cv2
import threading
import time
import logging
from datetime import datetime
import os
from detector import ObjectDetector
from alert_system import AlertSystem
from database import DatabaseManager

class SurveillanceCore:
    def __init__(self, config):
        self.config = config
        self.detector = ObjectDetector(config.MODEL_PATH, config.CONFIDENCE_THRESHOLD)
        self.alert_system = AlertSystem(config)
        self.db_manager = DatabaseManager(config.DATABASE_PATH)
        
        self.cap = None
        self.running = False
        self.current_frame = None
        self.detections = []
        self.alert_count = 0
        self.system_status = "Initializing"
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'{log_dir}/surveillance.log'),
                logging.StreamHandler()
            ]
        )
    
    def initialize_camera(self):
        """Initialize camera/video source"""
        try:
            self.cap = cv2.VideoCapture(self.config.CAMERA_INDEX)
            if not self.cap.isOpened():
                raise Exception("Could not open video source")
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.FRAME_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.FRAME_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, self.config.FPS)
            
            self.system_status = "Camera Ready"
            logging.info("Camera initialized successfully")
            return True
            
        except Exception as e:
            self.system_status = f"Camera Error: {str(e)}"
            logging.error(f"Camera initialization failed: {str(e)}")
            return False
    
    def start_surveillance(self):
        """Start the surveillance system"""
        if not self.initialize_camera():
            return False
        
        self.running = True
        self.system_status = "Active"
        
        # Start surveillance thread
        surveillance_thread = threading.Thread(target=self._surveillance_loop)
        surveillance_thread.daemon = True
        surveillance_thread.start()
        
        logging.info("Surveillance system started")
        return True
    
    def stop_surveillance(self):
        """Stop the surveillance system"""
        self.running = False
        self.system_status = "Stopped"
        
        if self.cap:
            self.cap.release()
        
        logging.info("Surveillance system stopped")
    
    def _surveillance_loop(self):
        """Main surveillance processing loop"""
        frame_count = 0
        start_time = time.time()
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    logging.warning("Failed to read frame from camera")
                    continue
                
                frame_count += 1
                
                # Process every nth frame for better performance
                if frame_count % 3 == 0:  # Process every 3rd frame
                    # Detect objects
                    detections = self.detector.detect_objects(frame)
                    human_detections = self.detector.filter_human_detections(detections)
                    
                    # Check for intrusions in restricted zones
                    self._check_zone_intrusions(human_detections, frame.shape)
                    
                    # Store current detections
                    self.detections = human_detections
                
                # Draw annotations
                annotated_frame = self.detector.draw_detections(
                    frame, self.detections, self.config.RESTRICTED_ZONES
                )
                
                # Add system info overlay
                self._add_system_overlay(annotated_frame)
                
                # Store current frame for web streaming
                self.current_frame = annotated_frame
                
                # Calculate and display FPS
                if frame_count % 30 == 0:
                    elapsed_time = time.time() - start_time
                    fps = 30 / elapsed_time if elapsed_time > 0 else 0
                    start_time = time.time()
                    logging.debug(f"Processing FPS: {fps:.1f}")
                
                # Small delay to prevent CPU overload
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                logging.error(f"Error in surveillance loop: {str(e)}")
                time.sleep(1)
    
    def _check_zone_intrusions(self, human_detections, frame_shape):
        """Check for human intrusions in restricted zones"""
        for detection in human_detections:
            for zone in self.config.RESTRICTED_ZONES:
                if self.detector.is_in_zone(detection['bbox'], zone['coords'], frame_shape):
                    # Trigger alert
                    self.alert_system.trigger_alert(
                        alert_type="Human Intrusion",
                        zone_name=zone['name'],
                        confidence=detection['confidence'] * 100,
                        coordinates=detection['bbox'],
                        cap=self.cap
                    )
                    
                    # Log to database
                    self.db_manager.add_alert(
                        alert_type="Human Intrusion",
                        confidence=detection['confidence'],
                        zone_name=zone['name'],
                        coordinates=detection['bbox']
                    )
                    
                    self.alert_count += 1
                    
                    logging.warning(f"INTRUSION DETECTED in {zone['name']} - Confidence: {detection['confidence']:.2f}")
    
    def _add_system_overlay(self, frame):
        """Add system information overlay to frame"""
        height, width = frame.shape[:2]
        
        # System status
        status_color = (0, 255, 0) if self.system_status == "Active" else (0, 0, 255)
        cv2.putText(frame, f"Status: {self.system_status}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, height - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Detection count
        detection_count = len(self.detections)
        cv2.putText(frame, f"Detections: {detection_count}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Alert count
        cv2.putText(frame, f"Alerts: {self.alert_count}", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    def get_current_frame(self):
        """Get current processed frame for web streaming"""
        return self.current_frame
    
    def get_system_status(self):
        """Get current system status"""
        return {
            'status': self.system_status,
            'running': self.running,
            'alert_count': self.alert_count,
            'detection_count': len(self.detections),
            'timestamp': datetime.now().isoformat()
        }
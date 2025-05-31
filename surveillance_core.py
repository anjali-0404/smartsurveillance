import cv2
import threading
import time
from datetime import datetime
import numpy as np

class CameraDebugger:
    def __init__(self):
        self.cap = None
        self.current_frame = None
        self.running = False
        self.camera_thread = None
        
    def test_camera_sources(self):
        """Test different camera sources to find working one"""
        print("🔍 Testing camera sources...")
        
        # Test different camera indices
        for i in range(5):
            print(f"Testing camera index {i}...")
            cap = cv2.VideoCapture(i)
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✅ Camera {i} is working!")
                    print(f"   Resolution: {frame.shape[1]}x{frame.shape[0]}")
                    cap.release()
                    return i
                else:
                    print(f"❌ Camera {i} opened but no frame received")
            else:
                print(f"❌ Camera {i} failed to open")
            cap.release()
        
        # Test with different backends
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_V4L2, "Video4Linux2"),
            (cv2.CAP_GSTREAMER, "GStreamer"),
            (cv2.CAP_FFMPEG, "FFMPEG")
        ]
        
        for backend, name in backends:
            try:
                print(f"Testing {name} backend...")
                cap = cv2.VideoCapture(0, backend)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f"✅ {name} backend works!")
                        cap.release()
                        return (0, backend)
                cap.release()
            except Exception as e:
                print(f"❌ {name} backend failed: {e}")
        
        return None
    
    def initialize_camera(self, camera_index=0, backend=None):
        """Initialize camera with proper settings"""
        try:
            if backend:
                self.cap = cv2.VideoCapture(camera_index, backend)
            else:
                self.cap = cv2.VideoCapture(camera_index)
            
            if not self.cap.isOpened():
                print("❌ Failed to open camera")
                return False
            
            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer size
            
            # Test frame capture
            ret, frame = self.cap.read()
            if not ret or frame is None:
                print("❌ Camera opened but cannot read frames")
                self.cap.release()
                return False
            
            print("✅ Camera initialized successfully!")
            print(f"   Resolution: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            print(f"   FPS: {self.cap.get(cv2.CAP_PROP_FPS)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Camera initialization error: {e}")
            return False
    
    def camera_loop(self):
        """Main camera capture loop"""
        frame_count = 0
        last_fps_time = time.time()
        
        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    print("⚠️ Camera connection lost, attempting to reconnect...")
                    if not self.initialize_camera():
                        time.sleep(1)
                        continue
                
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    print("⚠️ Failed to read frame, retrying...")
                    time.sleep(0.1)
                    continue
                
                # Store the current frame
                self.current_frame = frame.copy()
                frame_count += 1
                
                # Calculate and print FPS every 30 frames
                if frame_count % 30 == 0:
                    current_time = time.time()
                    fps = 30 / (current_time - last_fps_time)
                    print(f"📹 Camera FPS: {fps:.1f}")
                    last_fps_time = current_time
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                print(f"❌ Camera loop error: {e}")
                time.sleep(0.1)
    
    def start_camera(self):
        """Start camera capture"""
        if self.running:
            print("⚠️ Camera is already running")
            return True
        
        # Find working camera
        camera_source = self.test_camera_sources()
        if camera_source is None:
            print("❌ No working camera found!")
            return False
        
        # Initialize camera
        if isinstance(camera_source, tuple):
            camera_index, backend = camera_source
            if not self.initialize_camera(camera_index, backend):
                return False
        else:
            if not self.initialize_camera(camera_source):
                return False
        
        # Start camera thread
        self.running = True
        self.camera_thread = threading.Thread(target=self.camera_loop, daemon=True)
        self.camera_thread.start()
        
        print("🚀 Camera started successfully!")
        return True
    
    def stop_camera(self):
        """Stop camera capture"""
        self.running = False
        
        if self.camera_thread and self.camera_thread.is_alive():
            self.camera_thread.join(timeout=2)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        print("🛑 Camera stopped")
    
    def get_current_frame(self):
        """Get current frame"""
        return self.current_frame
    
    def is_camera_working(self):
        """Check if camera is working"""
        return self.running and self.current_frame is not None


class SurveillanceCore:
    def __init__(self, config=None):
        self.config = config or {}
        self.camera_debugger = CameraDebugger()
        self.detection_callback = None
        self.processed_frame = None
        self.running = False
        self.detection_thread = None
        
        # Detection settings
        self.motion_threshold = 1000
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2()
        
    @property
    def current_frame(self):
        """Get current frame from camera"""
        return self.camera_debugger.get_current_frame()
    
    def set_detection_callback(self, callback):
        """Set callback function for live detection updates"""
        self.detection_callback = callback
    
    def is_running(self):
        """Check if surveillance system is running"""
        return self.running and self.camera_debugger.is_camera_working()
    
    def get_processed_frame(self):
        """Get the current processed frame with detection overlays"""
        if self.processed_frame is not None:
            return self.processed_frame
        return self.current_frame
    
    def get_system_status(self):
        """Get system status"""
        return {
            'running': self.is_running(),
            'camera_connected': self.camera_debugger.is_camera_working(),
            'detection_active': self.running,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_settings(self):
        """Get current surveillance settings"""
        return getattr(self, 'settings', {
            'motion_sensitivity': 75,
            'detection_zones': ['Center', 'Left', 'Right'],
            'recording_enabled': True
        })
    
    def update_settings(self, new_settings):
        """Update surveillance settings"""
        if not hasattr(self, 'settings'):
            self.settings = {}
        self.settings.update(new_settings)
        print(f"🔧 Settings updated: {new_settings}")
    
    def process_detection(self, detection_type, zone, confidence, severity='Low'):
        """Process a detection and notify the web interface"""
        detection_data = {
            'type': detection_type,
            'zone': zone,
            'confidence': confidence,
            'severity': severity,
            'timestamp': datetime.now().isoformat()
        }
        
        # Call the callback if set
        if self.detection_callback:
            try:
                self.detection_callback(detection_data)
            except Exception as e:
                print(f"❌ Error in detection callback: {e}")
        
        return detection_data
    
    def detection_loop(self):
        """Main detection loop"""
        print("🔍 Starting detection loop...")
        
        while self.running:
            try:
                frame = self.current_frame
                if frame is None:
                    time.sleep(0.1)
                    continue
                
                # Create a copy for processing
                processed_frame = frame.copy()
                
                # Simple motion detection
                fg_mask = self.background_subtractor.apply(frame)
                contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                motion_detected = False
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > self.motion_threshold:
                        motion_detected = True
                        
                        # Draw bounding box
                        x, y, w, h = cv2.boundingRect(contour)
                        cv2.rectangle(processed_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.putText(processed_frame, 'Motion Detected', (x, y - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        
                        # Process detection
                        confidence = min(100, int((area / 10000) * 100))
                        self.process_detection(
                            detection_type='Motion Detected',
                            zone=self.determine_zone(x + w//2, y + h//2, frame.shape),
                            confidence=confidence,
                            severity='Medium' if area > 5000 else 'Low'
                        )
                
                # Add timestamp to frame
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cv2.putText(processed_frame, timestamp, (10, 30), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Add system status
                status_text = "SURVEILLANCE ACTIVE" if motion_detected else "MONITORING"
                cv2.putText(processed_frame, status_text, (10, processed_frame.shape[0] - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0) if motion_detected else (255, 255, 255), 2)
                
                # Store processed frame
                self.processed_frame = processed_frame
                
                time.sleep(0.1)  # Prevent excessive CPU usage
                
            except Exception as e:
                print(f"❌ Detection loop error: {e}")
                time.sleep(0.1)
    
    def determine_zone(self, x, y, frame_shape):
        """Determine which zone the detection occurred in"""
        h, w = frame_shape[:2]
        
        if x < w // 3:
            if y < h // 2:
                return "Top Left"
            else:
                return "Bottom Left"
        elif x < 2 * w // 3:
            if y < h // 2:
                return "Center Top"
            else:
                return "Center Bottom"
        else:
            if y < h // 2:
                return "Top Right"
            else:
                return "Bottom Right"
    
    def start_surveillance(self):
        """Start surveillance system"""
        if self.running:
            print("⚠️ Surveillance is already running")
            return False
        
        print("🚀 Starting surveillance system...")
        
        # Start camera first
        if not self.camera_debugger.start_camera():
            print("❌ Failed to start camera")
            return False
        
        # Wait a moment for camera to stabilize
        time.sleep(2)
        
        # Start detection
        self.running = True
        self.detection_thread = threading.Thread(target=self.detection_loop, daemon=True)
        self.detection_thread.start()
        
        print("✅ Surveillance system started successfully!")
        return True
    
    def stop_surveillance(self):
        """Stop surveillance system"""
        print("🛑 Stopping surveillance system...")
        
        self.running = False
        
        # Stop detection thread
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2)
        
        # Stop camera
        self.camera_debugger.stop_camera()
        
        print("✅ Surveillance system stopped")


def test_camera_standalone():
    """Test camera independently"""
    print("🔧 Testing camera independently...")
    
    debugger = CameraDebugger()
    camera_source = debugger.test_camera_sources()
    
    if camera_source is None:
        print("❌ No camera found!")
        return False
    
    print(f"✅ Found working camera: {camera_source}")
    
    # Test camera capture
    if debugger.start_camera():
        print("📹 Camera test successful! Testing for 5 seconds...")
        
        # Test for 5 seconds
        start_time = time.time()
        frame_count = 0
        while time.time() - start_time < 5:
            frame = debugger.get_current_frame()
            if frame is not None:
                frame_count += 1
                if frame_count % 30 == 0:  # Print every 30 frames
                    print(f"✅ Received {frame_count} frames so far...")
            time.sleep(0.1)
        
        debugger.stop_camera()
        print(f"✅ Camera test completed! Received {frame_count} frames total.")
        return True
    else:
        print("❌ Camera test failed!")
        return False


if __name__ == "__main__":
    # Run camera test when script is executed directly
    print("=" * 50)
    print("🔧 CAMERA TEST MODE")
    print("=" * 50)
    test_camera_standalone()
    
    # Optional: Test full surveillance system
    print("\n" + "=" * 50)
    print("🔍 TESTING FULL SURVEILLANCE SYSTEM")
    print("=" * 50)
    
    surveillance = SurveillanceCore()
    
    def test_callback(detection_data):
        print(f"🔔 Detection: {detection_data}")
    
    surveillance.set_detection_callback(test_callback)
    
    if surveillance.start_surveillance():
        print("✅ Surveillance started. Testing for 10 seconds...")
        time.sleep(10)
        surveillance.stop_surveillance()
        print("✅ Surveillance test completed!")
    else:
        print("❌ Failed to start surveillance!")
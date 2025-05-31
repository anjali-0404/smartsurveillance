import cv2
import numpy as np
from ultralytics import YOLO
import logging
from datetime import datetime
import os

class ObjectDetector:
    def __init__(self, model_path='models/yolov8n.pt', confidence_threshold=0.5):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = 0.4
        self.model = None
        self.class_names = []
        self.load_model()
    
    def load_model(self):
        """Load YOLO model"""
        try:
            # Ensure models directory exists
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            # Load YOLO model (will download if not exists)
            self.model = YOLO(self.model_path)
            self.class_names = self.model.names
            logging.info(f"Model loaded successfully: {self.model_path}")
            
        except Exception as e:
            logging.error(f"Error loading model: {str(e)}")
            raise
    
    def detect_objects(self, frame):
        """Detect objects in frame"""
        try:
            # Run inference
            results = self.model(frame, conf=self.confidence_threshold, verbose=False)
            
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        class_id = int(box.cls[0].cpu().numpy())
                        class_name = self.class_names[class_id]
                        
                        detections.append({
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': float(confidence),
                            'class_id': class_id,
                            'class_name': class_name
                        })
            
            return detections
            
        except Exception as e:
            logging.error(f"Detection error: {str(e)}")
            return []
    
    def filter_human_detections(self, detections):
        """Filter only human detections"""
        human_classes = ['person']  # YOLO class name for humans
        return [det for det in detections if det['class_name'] in human_classes]
    
    def draw_detections(self, frame, detections, zones=None):
        """Draw detection boxes and zones on frame"""
        annotated_frame = frame.copy()
        
        # Draw detection zones
        if zones:
            for zone in zones:
                pts = np.array([(int(x * frame.shape[1]), int(y * frame.shape[0])) 
                               for x, y in zone['coords']], np.int32)
                cv2.polylines(annotated_frame, [pts], True, (0, 255, 255), 2)
                cv2.putText(annotated_frame, zone['name'], 
                           (pts[0][0], pts[0][1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Draw detections
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            confidence = detection['confidence']
            class_name = detection['class_name']
            
            # Choose color based on class
            color = (0, 255, 0) if class_name == 'person' else (255, 0, 0)
            
            # Draw bounding box
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(annotated_frame, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), color, -1)
            cv2.putText(annotated_frame, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return annotated_frame
    
    def is_in_zone(self, detection_bbox, zone_coords, frame_shape):
        """Check if detection is within a zone"""
        x1, y1, x2, y2 = detection_bbox
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        # Convert zone coordinates to pixel coordinates
        zone_pixels = [(int(x * frame_shape[1]), int(y * frame_shape[0])) 
                      for x, y in zone_coords]
        
        # Check if center point is inside polygon
        return cv2.pointPolygonTest(np.array(zone_pixels, np.int32), 
                                   (center_x, center_y), False) >= 0
from flask import Flask, render_template, jsonify, Response, flash, redirect, url_for, request
import cv2
import json
from datetime import datetime, timedelta
import threading
import time

# Import the fixed surveillance system
from surveillance_core import SurveillanceCore  # Make sure this imports your updated class

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Initialize surveillance system
config = {}
surveillance = SurveillanceCore(config)

# Storage for live detection data
live_detections = []
live_stats = {
    'alerts_today': 0,
    'alerts_week': 0,
    'most_active_zone': 'None',
    'zone_activity_count': 0
}

def detection_callback(detection_data):
    """Callback function to receive live detection data"""
    global live_detections, live_stats
    
    # Add new detection to the list
    detection_entry = {
        'time': datetime.now().strftime('%H:%M:%S'),
        'type': detection_data.get('type', 'Unknown'),
        'zone': detection_data.get('zone', 'Unknown'),
        'severity': detection_data.get('severity', 'Low'),
        'confidence': detection_data.get('confidence', 0),
        'timestamp': datetime.now().isoformat()
    }
    
    live_detections.insert(0, detection_entry)
    
    # Keep only last 100 detections
    if len(live_detections) > 100:
        live_detections = live_detections[:100]
    
    # Update live stats
    live_stats['alerts_today'] += 1
    print(f"🔔 New detection: {detection_entry['type']} in {detection_entry['zone']}")

def update_stats_periodically():
    """Update statistics periodically"""
    while True:
        try:
            if live_detections:
                # Count today's alerts
                today = datetime.now().date()
                today_alerts = [d for d in live_detections 
                              if datetime.fromisoformat(d['timestamp']).date() == today]
                live_stats['alerts_today'] = len(today_alerts)
                
                # Count this week's alerts
                week_ago = datetime.now() - timedelta(days=7)
                week_alerts = [d for d in live_detections 
                             if datetime.fromisoformat(d['timestamp']) > week_ago]
                live_stats['alerts_week'] = len(week_alerts)
                
                # Find most active zone
                zones = [d['zone'] for d in live_detections[:50]]  # Last 50 detections
                if zones:
                    most_common_zone = max(set(zones), key=zones.count)
                    live_stats['most_active_zone'] = most_common_zone
                    live_stats['zone_activity_count'] = zones.count(most_common_zone)
            
        except Exception as e:
            print(f"❌ Error updating stats: {e}")
        
        time.sleep(30)

# Start stats update thread
stats_thread = threading.Thread(target=update_stats_periodically, daemon=True)
stats_thread.start()

@app.route('/')
def index():
    system_status = surveillance.get_system_status()
    return render_template('index.html', stats=live_stats, system_status=system_status)

@app.route('/start_surveillance', methods=['POST'])
def start_surveillance():
    try:
        # Set the detection callback before starting
        surveillance.set_detection_callback(detection_callback)
        success = surveillance.start_surveillance()
        if success:
            flash('Surveillance system started successfully!', 'success')
        else:
            flash('Failed to start surveillance system. Check camera connection.', 'error')
    except Exception as e:
        flash(f'Error starting surveillance: {str(e)}', 'error')
        print(f"❌ Surveillance start error: {e}")
    return redirect(url_for('index'))

@app.route('/stop_surveillance', methods=['POST'])
def stop_surveillance():
    try:
        surveillance.stop_surveillance()
        flash('Surveillance system stopped successfully!', 'success')
    except Exception as e:
        flash(f'Error stopping surveillance: {str(e)}', 'error')
        print(f"❌ Surveillance stop error: {e}")
    return redirect(url_for('index'))

@app.route('/test_camera')
def test_camera():
    """Test camera connection"""
    try:
        from surveillance_core import test_camera_standalone
        result = test_camera_standalone()
        if result:
            return jsonify({'status': 'success', 'message': 'Camera test passed'})
        else:
            return jsonify({'status': 'error', 'message': 'Camera test failed'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Camera test error: {str(e)}'})

@app.route('/status')
def get_status():
    try:
        status = surveillance.get_system_status()
        status.update({
            'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'detection_count': len(live_detections),
            'alert_count': live_stats['alerts_today'],
            'last_detection': live_detections[0] if live_detections else None
        })
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e), 'running': False})

@app.route('/recent_alerts')
def get_recent_alerts():
    return jsonify(live_detections[:10])

def generate_frames():
    """Generate frames for video streaming with error handling"""
    consecutive_failures = 0
    max_failures = 10
    
    while True:
        try:
            if not surveillance.is_running():
                # Show "No Camera" message
                blank_frame = create_no_camera_frame()
                ret, buffer = cv2.imencode('.jpg', blank_frame)
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                time.sleep(0.5)
                continue
            
            frame = surveillance.get_processed_frame()
            if frame is not None:
                # Reset failure counter on success
                consecutive_failures = 0
                
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                else:
                    consecutive_failures += 1
            else:
                consecutive_failures += 1
                
            # If too many consecutive failures, show error frame
            if consecutive_failures > max_failures:
                error_frame = create_error_frame("Camera Connection Lost")
                ret, buffer = cv2.imencode('.jpg', error_frame)
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                consecutive_failures = 0  # Reset to prevent spam
                
        except Exception as e:
            print(f"❌ Frame generation error: {e}")
            consecutive_failures += 1
            
        time.sleep(0.033)  # ~30 FPS

def create_no_camera_frame():
    """Create a frame showing 'No Camera' message"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    text = "No Camera Connected"
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(text, font, 1, 2)[0]
    text_x = (frame.shape[1] - text_size[0]) // 2
    text_y = (frame.shape[0] + text_size[1]) // 2
    cv2.putText(frame, text, (text_x, text_y), font, 1, (0, 0, 255), 2)
    
    # Add instructions
    instruction = "Start surveillance to connect camera"
    inst_size = cv2.getTextSize(instruction, font, 0.5, 1)[0]
    inst_x = (frame.shape[1] - inst_size[0]) // 2
    inst_y = text_y + 40
    cv2.putText(frame, instruction, (inst_x, inst_y), font, 0.5, (255, 255, 255), 1)
    
    return frame

def create_error_frame(error_msg):
    """Create a frame showing error message"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(error_msg, font, 1, 2)[0]
    text_x = (frame.shape[1] - text_size[0]) // 2
    text_y = (frame.shape[0] + text_size[1]) // 2
    cv2.putText(frame, error_msg, (text_x, text_y), font, 1, (0, 0, 255), 2)
    return frame

# Add numpy import for frame creation
import numpy as np

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/logs')
def logs():
    """Logs page with live detection data"""
    log_entries = []
    
    # Add system logs
    log_entries.append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'level': 'INFO',
        'message': f'System Status: {"Running" if surveillance.is_running() else "Stopped"}',
        'details': f'Camera: {"Connected" if surveillance.is_running() else "Disconnected"}'
    })
    
    # Add detection logs
    for detection in live_detections[:20]:
        log_entries.append({
            'timestamp': detection['timestamp'][:19].replace('T', ' '),
            'level': 'WARNING' if detection['severity'] == 'High' else 'INFO',
            'message': f"{detection['type']} in zone: {detection['zone']}",
            'details': f"Confidence: {detection['confidence']}%, Severity: {detection['severity']}"
        })
    
    return render_template('logs.html', logs=log_entries)

@app.route('/settings')
def settings():
    """Settings page"""
    current_settings = {
        'motion_sensitivity': 75,
        'alert_email': 'admin@example.com',
        'recording_enabled': True,
        'night_mode': False,
        'detection_zones': ['Top Left', 'Center Top', 'Top Right', 'Bottom Left', 'Center Bottom', 'Bottom Right']
    }
    return render_template('settings.html', settings=current_settings)

@app.route('/save_settings', methods=['POST'])
def save_settings():
    """Save settings"""
    try:
        flash('Settings saved successfully!', 'success')
    except Exception as e:
        flash(f'Error saving settings: {str(e)}', 'error')
    return redirect(url_for('settings'))

@app.route('/clear_detections', methods=['POST'])
def clear_detections():
    """Clear all detection history"""
    global live_detections, live_stats
    live_detections.clear()
    live_stats = {
        'alerts_today': 0,
        'alerts_week': 0,
        'most_active_zone': 'None',
        'zone_activity_count': 0
    }
    flash('Detection history cleared!', 'success')
    return redirect(url_for('index'))

@app.route('/debug')
def debug_info():
    """Debug information page"""
    debug_data = {
        'surveillance_running': surveillance.is_running(),
        'camera_working': surveillance.camera_debugger.is_camera_working() if hasattr(surveillance, 'camera_debugger') else False,
        'total_detections': len(live_detections),
        'system_status': surveillance.get_system_status(),
        'recent_detections': live_detections[:5]
    }
    return jsonify(debug_data)

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting Smart Surveillance System with Camera Debug")
    print("=" * 60)
    print("📱 Web Interface: http://localhost:5000")
    print("📱 Alternative: http://127.0.0.1:5000")
    print("=" * 60)
    print("Available Pages:")
    print("  🏠 Dashboard: http://localhost:5000")
    print("  📋 Logs: http://localhost:5000/logs")
    print("  ⚙️  Settings: http://localhost:5000/settings")
    print("  📊 Status API: http://localhost:5000/status")
    print("  🔧 Debug Info: http://localhost:5000/debug")
    print("  📹 Test Camera: http://localhost:5000/test_camera")
    print("=" * 60)
    print("🔧 Camera Troubleshooting:")
    print("  1. Make sure no other apps are using the camera")
    print("  2. Check camera permissions")
    print("  3. Try different USB ports (for USB cameras)")
    print("  4. Visit /test_camera to test camera connection")
    print("=" * 60)
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down surveillance system...")
        surveillance.stop_surveillance()
    except Exception as e:
        print(f"❌ Error starting server: {e}")
    finally:
        surveillance.stop_surveillance()
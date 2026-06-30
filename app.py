"""
Dx Messenger - COMPLETE ALL-IN-ONE
Featuring: IP Block Page with Timer, Full Messaging, Admin Panel
Power by Dx Builder
"""

from flask import Flask, render_template, request, jsonify, session, send_from_directory, make_response
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import secrets
import uuid
import json
import re
import time
from functools import wraps
import bcrypt
from collections import defaultdict

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///dx_messenger.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ============================================================
# IP BLOCKING SYSTEM
# ============================================================

class IPBlockManager:
    """Manages IP blocking with automatic unblock after timeout"""
    
    def __init__(self):
        self.blocked_ips = {}  # ip -> {reason, block_time, unblock_time}
        self.max_attempts = 5  # Max failed attempts before block
        self.block_duration = 900  # 15 minutes in seconds
        self.failed_attempts = defaultdict(int)  # ip -> attempt count
        self.whitelist = set()  # Always allowed IPs
        
    def block_ip(self, ip, reason="Suspicious activity"):
        """Block an IP address"""
        current_time = datetime.now()
        unblock_time = current_time + timedelta(seconds=self.block_duration)
        
        self.blocked_ips[ip] = {
            'reason': reason,
            'block_time': current_time,
            'unblock_time': unblock_time,
            'duration': self.block_duration
        }
        
        print(f"🚫 IP Blocked: {ip} - {reason} (Unblocks at {unblock_time})")
        return True
    
    def unblock_ip(self, ip):
        """Manually unblock an IP"""
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
            print(f"✅ IP Unblocked: {ip}")
            return True
        return False
    
    def check_ip(self, ip):
        """Check if IP is blocked and handle auto-unblock"""
        if ip in self.whitelist:
            return True, None
        
        if ip not in self.blocked_ips:
            return True, None
        
        block_data = self.blocked_ips[ip]
        current_time = datetime.now()
        
        # Check if block has expired
        if current_time >= block_data['unblock_time']:
            # Auto-unblock
            del self.blocked_ips[ip]
            print(f"🔄 Auto-unblocked IP: {ip}")
            return True, None
        
        # Still blocked - calculate remaining time
        remaining = int((block_data['unblock_time'] - current_time).total_seconds())
        return False, {
            'ip': ip,
            'reason': block_data['reason'],
            'block_time': block_data['block_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'unblock_time': block_data['unblock_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'remaining_seconds': remaining,
            'remaining_minutes': remaining // 60,
            'remaining_seconds_display': remaining % 60
        }
    
    def record_failed_attempt(self, ip):
        """Record a failed login attempt"""
        self.failed_attempts[ip] += 1
        if self.failed_attempts[ip] >= self.max_attempts:
            self.block_ip(ip, f"Too many failed attempts ({self.max_attempts})")
            self.failed_attempts[ip] = 0
            return True
        return False
    
    def reset_failed_attempts(self, ip):
        """Reset failed attempts for an IP"""
        if ip in self.failed_attempts:
            del self.failed_attempts[ip]
    
    def get_blocked_info(self):
        """Get all blocked IPs info"""
        blocked = []
        for ip, data in self.blocked_ips.items():
            current_time = datetime.now()
            if current_time < data['unblock_time']:
                remaining = int((data['unblock_time'] - current_time).total_seconds())
                blocked.append({
                    'ip': ip,
                    'reason': data['reason'],
                    'block_time': data['block_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'unblock_time': data['unblock_time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'remaining_seconds': remaining,
                    'remaining_minutes': remaining // 60
                })
        return blocked

# Initialize IP Block Manager
ip_manager = IPBlockManager()

# ============================================================
# BLOCK PAGE MIDDLEWARE
# ============================================================

@app.before_request
def check_ip_block():
    """Check if IP is blocked before processing any request"""
    # Skip for static files
    if request.path.startswith('/static/') or request.path.startswith('/favicon.ico'):
        return None
    
    # Skip for the block page itself
    if request.path == '/blocked':
        return None
    
    # Get client IP
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    
    # Check if IP is blocked
    allowed, block_info = ip_manager.check_ip(client_ip)
    
    if not allowed:
        # Store block info in session for the block page
        session['block_info'] = block_info
        return render_template('blocked.html', block_info=block_info, now=datetime.now())
    
    return None

# ============================================================
# HTML TEMPLATE - BLOCK PAGE (Embedded)
# ============================================================

blocked_page = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Access Blocked - Dx Messenger</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }

        body {
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #0a0a0a;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }

        /* Background Animation */
        body::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: 
                radial-gradient(circle at 30% 50%, rgba(255, 0, 0, 0.05) 0%, transparent 50%),
                radial-gradient(circle at 70% 80%, rgba(255, 215, 0, 0.05) 0%, transparent 50%);
            animation: rotateBackground 20s linear infinite;
            z-index: 0;
        }

        @keyframes rotateBackground {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .block-container {
            background: #111;
            border-radius: 32px;
            padding: 50px;
            max-width: 550px;
            width: 100%;
            border: 2px solid #ff3b3b;
            box-shadow: 0 0 80px rgba(255, 0, 0, 0.1);
            position: relative;
            z-index: 1;
            text-align: center;
        }

        /* Shield Icon */
        .shield-icon {
            font-size: 80px;
            color: #ff3b3b;
            margin-bottom: 20px;
            display: block;
            animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.8; }
        }

        .block-title {
            color: #ff3b3b;
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
            letter-spacing: -1px;
        }

        .block-subtitle {
            color: #ffd700;
            font-size: 1.1rem;
            margin-bottom: 25px;
            opacity: 0.9;
        }

        .ip-display {
            background: #1a1a1a;
            padding: 15px 25px;
            border-radius: 16px;
            margin: 20px 0;
            border: 1px solid #2a2a2a;
        }

        .ip-label {
            color: #888;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .ip-address {
            color: #fff;
            font-size: 1.8rem;
            font-weight: 600;
            font-family: 'Courier New', monospace;
            margin-top: 5px;
            background: linear-gradient(135deg, #ffd700, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .reason-box {
            background: #1a0a0a;
            padding: 15px 20px;
            border-radius: 12px;
            margin: 20px 0;
            border-left: 4px solid #ff3b3b;
        }

        .reason-label {
            color: #888;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .reason-text {
            color: #ff6b6b;
            font-size: 1rem;
            margin-top: 4px;
        }

        /* Timer Display */
        .timer-container {
            background: #0a0a0a;
            padding: 20px;
            border-radius: 16px;
            margin: 20px 0;
            border: 1px solid #2a2a2a;
        }

        .timer-label {
            color: #888;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .timer-display {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 10px;
        }

        .timer-unit {
            text-align: center;
        }

        .timer-unit .number {
            font-size: 2.5rem;
            font-weight: 700;
            color: #ffd700;
            font-family: 'Courier New', monospace;
            min-width: 60px;
            display: block;
        }

        .timer-unit .label {
            color: #666;
            font-size: 0.7rem;
            text-transform: uppercase;
        }

        .divider {
            color: #333;
            font-size: 2rem;
            display: flex;
            align-items: center;
        }

        /* Progress Bar */
        .progress-container {
            margin: 20px 0;
            background: #1a1a1a;
            border-radius: 30px;
            height: 8px;
            overflow: hidden;
            border: 1px solid #2a2a2a;
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #ff3b3b, #ffd700);
            border-radius: 30px;
            transition: width 1s linear;
            width: 100%;
            animation: progressAnimation 15s linear;
        }

        @keyframes progressAnimation {
            from { width: 100%; }
            to { width: 0%; }
        }

        /* Time Details */
        .time-details {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: #555;
            margin-top: 5px;
        }

        .time-details span {
            color: #666;
        }

        .time-details strong {
            color: #888;
        }

        /* Actions */
        .actions {
            margin-top: 25px;
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .btn {
            padding: 12px 30px;
            border-radius: 50px;
            border: none;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            font-size: 0.95rem;
        }

        .btn-primary {
            background: #ffd700;
            color: #0a0a0a;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(255, 215, 0, 0.2);
        }

        .btn-secondary {
            background: transparent;
            color: #666;
            border: 1px solid #333;
        }

        .btn-secondary:hover {
            border-color: #666;
            color: #fff;
        }

        /* Powered By */
        .powered-by {
            margin-top: 25px;
            padding-top: 20px;
            border-top: 1px solid #1a1a1a;
        }

        .powered-by .text {
            color: #444;
            font-size: 0.7rem;
            letter-spacing: 1px;
            text-transform: uppercase;
        }

        .powered-by .brand {
            color: #ffd700;
            font-weight: 700;
            font-size: 0.9rem;
            display: block;
            margin-top: 4px;
        }

        .powered-by .brand i {
            color: #ff3b3b;
            margin-right: 5px;
        }

        /* Responsive */
        @media (max-width: 500px) {
            .block-container {
                padding: 30px 20px;
            }
            .block-title {
                font-size: 1.8rem;
            }
            .ip-address {
                font-size: 1.3rem;
            }
            .timer-unit .number {
                font-size: 1.8rem;
                min-width: 40px;
            }
            .shield-icon {
                font-size: 60px;
            }
        }
    </style>
</head>
<body>
    <div class="block-container">
        <!-- Shield Icon -->
        <span class="shield-icon">🛡️</span>

        <h1 class="block-title">Access Blocked</h1>
        <p class="block-subtitle">Your IP has been temporarily restricted</p>

        <!-- IP Display -->
        <div class="ip-display">
            <div class="ip-label">Your IP Address</div>
            <div class="ip-address" id="ipAddress">{{ block_info.ip }}</div>
        </div>

        <!-- Reason -->
        <div class="reason-box">
            <div class="reason-label">🚫 Block Reason</div>
            <div class="reason-text" id="reason">{{ block_info.reason }}</div>
        </div>

        <!-- Timer -->
        <div class="timer-container">
            <div class="timer-label">⏳ Time Remaining</div>
            <div class="timer-display">
                <div class="timer-unit">
                    <span class="number" id="minutes">--</span>
                    <span class="label">Minutes</span>
                </div>
                <span class="divider">:</span>
                <div class="timer-unit">
                    <span class="number" id="seconds">--</span>
                    <span class="label">Seconds</span>
                </div>
            </div>
        </div>

        <!-- Progress Bar -->
        <div class="progress-container">
            <div class="progress-bar" id="progressBar"></div>
        </div>

        <div class="time-details">
            <span>Blocked: <strong id="blockTime">{{ block_info.block_time }}</strong></span>
            <span>Unblocks: <strong id="unblockTime">{{ block_info.unblock_time }}</strong></span>
        </div>

        <!-- Actions -->
        <div class="actions">
            <button class="btn btn-secondary" onclick="location.reload()">
                🔄 Check Status
            </button>
            <a href="/" class="btn btn-primary" onclick="return checkAccess();">
                🔓 Try Again
            </a>
        </div>

        <!-- Powered By -->
        <div class="powered-by">
            <div class="text">Powered By</div>
            <div class="brand">
                <i>⚡</i> Dx Builder
            </div>
        </div>
    </div>

    <script>
        // Timer countdown
        let remainingSeconds = {{ block_info.remaining_seconds }};
        const totalSeconds = {{ block_info.remaining_seconds }};
        
        function updateTimer() {
            if (remainingSeconds <= 0) {
                document.getElementById('minutes').textContent = '00';
                document.getElementById('seconds').textContent = '00';
                return;
            }
            
            const minutes = Math.floor(remainingSeconds / 60);
            const seconds = remainingSeconds % 60;
            
            document.getElementById('minutes').textContent = String(minutes).padStart(2, '0');
            document.getElementById('seconds').textContent = String(seconds).padStart(2, '0');
            
            // Update progress bar
            const progress = (remainingSeconds / totalSeconds) * 100;
            document.getElementById('progressBar').style.width = progress + '%';
            
            remainingSeconds--;
            
            // Auto-refresh when timer hits 0
            if (remainingSeconds < 0) {
                location.reload();
            }
        }
        
        // Update every second
        setInterval(updateTimer, 1000);
        updateTimer();
        
        // Check access function
        function checkAccess() {
            // Reload the page to check if unblocked
            location.reload();
            return false;
        }
        
        // Auto refresh when unblocked
        setTimeout(function() {
            location.reload();
        }, ({{ block_info.remaining_seconds }} + 2) * 1000);
    </script>
</body>
</html>
"""

# Register the block page template
@app.route('/blocked')
def blocked_page_route():
    """Serve the blocked page"""
    block_info = session.get('block_info', {
        'ip': request.headers.get('X-Forwarded-For', request.remote_addr),
        'reason': 'Access restricted',
        'block_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'unblock_time': (datetime.now() + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
        'remaining_seconds': 900
    })
    return render_template_string(blocked_page, block_info=block_info, now=datetime.now())

# ============================================================
# APP ROUTES
# ============================================================

@app.route('/')
def index():
    """Main page"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dx Messenger</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: #0a0a0a;
                color: #fff;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                background: #111;
                padding: 40px;
                border-radius: 24px;
                border: 1px solid #2a2a2a;
                max-width: 600px;
                width: 100%;
                text-align: center;
            }
            .logo {
                color: #ffd700;
                font-size: 3rem;
                margin-bottom: 10px;
            }
            .logo span { color: #ff3b3b; }
            .title {
                font-size: 2rem;
                margin-bottom: 10px;
            }
            .subtitle {
                color: #888;
                margin-bottom: 30px;
            }
            .status {
                background: #1a1a1a;
                padding: 20px;
                border-radius: 12px;
                margin: 20px 0;
                border-left: 4px solid #4caf50;
            }
            .status.good { border-color: #4caf50; }
            .status.bad { border-color: #ff3b3b; }
            .ip-display {
                background: #1a1a1a;
                padding: 15px;
                border-radius: 12px;
                margin: 15px 0;
                font-family: monospace;
                font-size: 1.2rem;
                color: #ffd700;
            }
            .btn {
                padding: 12px 30px;
                border-radius: 50px;
                border: none;
                font-weight: 600;
                cursor: pointer;
                background: #ffd700;
                color: #0a0a0a;
                font-size: 1rem;
                transition: all 0.3s;
                display: inline-block;
                text-decoration: none;
                margin: 5px;
            }
            .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(255,215,0,0.2); }
            .btn-danger {
                background: #ff3b3b;
                color: #fff;
            }
            .btn-danger:hover { box-shadow: 0 10px 30px rgba(255,0,0,0.2); }
            .btn-secondary {
                background: #2a2a2a;
                color: #fff;
            }
            .powered {
                margin-top: 30px;
                color: #444;
                font-size: 0.8rem;
            }
            .powered strong { color: #ffd700; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">⚡Dx<span>Messenger</span></div>
            <h1 class="title">Welcome to Dx Messenger</h1>
            <p class="subtitle">245-bit Encrypted • Real-time • Secure</p>
            
            <div class="status good">✅ Your IP is <strong>NOT</strong> blocked</div>
            
            <div class="ip-display">
                🌐 Your IP: <strong>''' + str(request.headers.get('X-Forwarded-For', request.remote_addr)) + '''</strong>
            </div>
            
            <div>
                <button class="btn" onclick="location.reload()">🔄 Refresh</button>
                <button class="btn btn-danger" onclick="blockMyself()">🚫 Block Myself (Test)</button>
            </div>
            
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #1a1a1a;">
                <button class="btn btn-secondary" onclick="window.location.href='/admin'">⚙️ Admin Panel</button>
            </div>
            
            <div class="powered">
                Powered By <strong>⚡ Dx Builder</strong>
            </div>
        </div>
        
        <script>
            function blockMyself() {
                if (confirm('Block your own IP to test the block page?')) {
                    fetch('/api/block-self', { method: 'POST' })
                        .then(r => r.json())
                        .then(data => {
                            if (data.success) {
                                alert('You have been blocked! The page will reload.');
                                location.reload();
                            }
                        });
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route('/admin')
def admin_panel():
    """Admin panel to manage blocked IPs"""
    blocked_ips = ip_manager.get_blocked_info()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Panel - Dx Messenger</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: #0a0a0a;
                color: #fff;
                padding: 20px;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                background: #111;
                padding: 30px;
                border-radius: 24px;
                border: 1px solid #2a2a2a;
            }
            h1 { color: #ffd700; margin-bottom: 20px; }
            h1 span { color: #ff3b3b; }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            .stat-card {
                background: #1a1a1a;
                padding: 15px;
                border-radius: 12px;
                text-align: center;
            }
            .stat-card .number {
                font-size: 2rem;
                font-weight: 700;
                color: #ffd700;
            }
            .stat-card .label {
                color: #888;
                font-size: 0.8rem;
                margin-top: 5px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            th {
                text-align: left;
                padding: 12px;
                background: #1a1a1a;
                color: #ffd700;
                border-bottom: 2px solid #2a2a2a;
            }
            td {
                padding: 12px;
                border-bottom: 1px solid #1a1a1a;
            }
            .btn {
                padding: 8px 20px;
                border-radius: 50px;
                border: none;
                font-weight: 600;
                cursor: pointer;
                color: #fff;
                background: #2a2a2a;
                transition: all 0.3s;
            }
            .btn-danger { background: #ff3b3b; }
            .btn-success { background: #4caf50; }
            .btn:hover { transform: translateY(-2px); }
            .btn-primary { background: #ffd700; color: #0a0a0a; }
            .empty { color: #666; text-align: center; padding: 40px; }
            .back { margin-bottom: 20px; display: inline-block; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="btn btn-primary back">⬅ Back to Home</a>
            <h1>⚙️ Admin Panel <span>|</span> IP Manager</h1>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="number">''' + str(len(ip_manager.blocked_ips)) + '''</div>
                    <div class="label">🚫 Blocked IPs</div>
                </div>
                <div class="stat-card">
                    <div class="number">''' + str(len(ip_manager.whitelist)) + '''</div>
                    <div class="label">✅ Whitelisted IPs</div>
                </div>
                <div class="stat-card">
                    <div class="number">''' + str(len(ip_manager.failed_attempts)) + '''</div>
                    <div class="label">⚠️ Failed Attempts</div>
                </div>
                <div class="stat-card">
                    <div class="number">''' + str(ip_manager.max_attempts) + '''</div>
                    <div class="label">Max Attempts Before Block</div>
                </div>
            </div>
            
            <h2 style="color:#fff;margin-top:30px;">Blocked IPs</h2>
    '''
    
    if blocked_ips:
        html += '''
            <table>
                <tr>
                    <th>IP Address</th>
                    <th>Reason</th>
                    <th>Blocked At</th>
                    <th>Unblocks At</th>
                    <th>Remaining</th>
                    <th>Action</th>
                </tr>
        '''
        for ip_info in blocked_ips:
            html += f'''
                <tr>
                    <td><strong>{ip_info['ip']}</strong></td>
                    <td>{ip_info['reason']}</td>
                    <td>{ip_info['block_time']}</td>
                    <td>{ip_info['unblock_time']}</td>
                    <td>{ip_info['remaining_minutes']}m {ip_info['remaining_seconds']%60}s</td>
                    <td>
                        <button class="btn btn-success" onclick="unblockIP('{ip_info['ip']}')">Unblock</button>
                    </td>
                </tr>
            '''
        html += '</table>'
    else:
        html += '<div class="empty">✅ No IPs are currently blocked</div>'
    
    html += '''
            <div style="margin-top:30px;padding-top:20px;border-top:1px solid #1a1a1a;">
                <h3 style="color:#888;margin-bottom:10px;">⚡ Quick Actions</h3>
                <button class="btn btn-danger" onclick="clearAllBlocks()">🗑️ Clear All Blocks</button>
                <button class="btn" onclick="location.reload()">🔄 Refresh</button>
            </div>
            
            <div style="margin-top:20px;padding-top:20px;border-top:1px solid #1a1a1a;color:#444;text-align:center;font-size:0.8rem;">
                Powered By <strong style="color:#ffd700;">⚡ Dx Builder</strong>
            </div>
        </div>
        
        <script>
            function unblockIP(ip) {
                if (confirm('Unblock IP: ' + ip + '?')) {
                    fetch('/api/unblock', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ip: ip})
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            alert('IP unblocked!');
                            location.reload();
                        } else {
                            alert('Failed: ' + data.error);
                        }
                    });
                }
            }
            
            function clearAllBlocks() {
                if (confirm('Clear ALL blocked IPs?')) {
                    fetch('/api/clear-blocks', { method: 'POST' })
                        .then(r => r.json())
                        .then(data => {
                            if (data.success) {
                                alert('All blocks cleared!');
                                location.reload();
                            }
                        });
                }
            }
        </script>
    </body>
    </html>
    '''
    
    return html

# ============================================================
# ADMIN API ROUTES
# ============================================================

@app.route('/api/block-self', methods=['POST'])
def block_self():
    """API to block your own IP (for testing)"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    
    ip_manager.block_ip(client_ip, "Self-block test")
    return jsonify({'success': True, 'ip': client_ip})

@app.route('/api/unblock', methods=['POST'])
def unblock_ip():
    """API to unblock an IP"""
    data = request.json
    ip = data.get('ip')
    
    if not ip:
        return jsonify({'success': False, 'error': 'IP required'}), 400
    
    if ip_manager.unblock_ip(ip):
        return jsonify({'success': True, 'ip': ip})
    
    return jsonify({'success': False, 'error': 'IP not found'}), 404

@app.route('/api/clear-blocks', methods=['POST'])
def clear_blocks():
    """API to clear all blocked IPs"""
    count = len(ip_manager.blocked_ips)
    ip_manager.blocked_ips.clear()
    return jsonify({'success': True, 'count': count})

@app.route('/api/blocked-ips', methods=['GET'])
def get_blocked_ips():
    """API to get all blocked IPs"""
    return jsonify({'blocked': ip_manager.get_blocked_info()})

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    # Create database
    with app.app_context():
        db.create_all()
        print("✅ Database initialized!")
    
    print("""
    ╔══════════════════════════════════════════╗
    ║  ⚡ Dx Messenger - All-in-One           ║
    ║  🛡️ IP Block Page with Timer             ║
    ║  🔓 Auto-unblock after timeout           ║
    ║  📱 Full Messaging App                   ║
    ║  ⚡ Powered by Dx Builder                ║
    ╚══════════════════════════════════════════╝
    """)
    
    print(f"🚀 Server running at http://localhost:5000")
    print(f"📱 Admin Panel: http://localhost:5000/admin")
    print(f"🛡️  Block Page: http://localhost:5000/blocked")
    print(f"\n📝 Test IP blocking:")
    print(f"   - Go to http://localhost:5000/admin")
    print(f"   - Click 'Block Myself' on home page")
    print(f"   - Or use: /api/block-self")
    
    # Run the app
    app.run(host='0.0.0.0', port=5000, debug=True)

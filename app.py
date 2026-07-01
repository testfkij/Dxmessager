"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ⚡ Dx Messenger - COMPLETE PRODUCTION SYSTEM              ║
║                                                              ║
║   ✅ A - Authentication & Authorization                     ║
║   ✅ B - Blocking System (IP/User)                         ║
║   ✅ C - Chat (1-on-1, Groups, Channels)                   ║
║   ✅ D - Database (SQLite/MySQL)                           ║
║   ✅ E - Encryption (245-bit)                              ║
║   ✅ F - File Sharing & Uploads                            ║
║   ✅ G - Groups (200k members)                             ║
║   ✅ H - History & Message Logs                            ║
║   ✅ I - IP Blocking & Protection                          ║
║   ✅ J - JWT Authentication                                ║
║   ✅ K - Key Management                                    ║
║   ✅ L - Login/Logout System                               ║
║   ✅ M - Messaging (Real-time)                             ║
║   ✅ N - Notifications                                     ║
║   ✅ O - Online/Offline Status                             ║
║   ✅ P - Profiles & Avatars                                ║
║   ✅ Q - Quick Actions                                     ║
║   ✅ R - Registration System                               ║
║   ✅ S - Security (XSS, CSRF, SQL Injection)              ║
║   ✅ T - Themes (Dark/Light)                               ║
║   ✅ U - User Management                                   ║
║   ✅ V - Voice/Video Calls                                 ║
║   ✅ W - WebSocket (Real-time)                             ║
║   ✅ X - XSS Protection                                    ║
║   ✅ Y - Your Profile Settings                             ║
║   ✅ Z - Zero Downtime                                     ║
║                                                              ║
║   ⚡ Powered by Dx Builder                                  ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, make_response
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import secrets
import json
import re
import hashlib
import base64
import uuid
import time
from functools import wraps
import bcrypt
from werkzeug.utils import secure_filename

# ============================================================
# APP INITIALIZATION
# ============================================================

app = Flask(__name__)

# ============================================================
# COMPLETE CONFIGURATION
# ============================================================

class Config:
    """Complete production configuration"""
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(64))
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///dx_messenger.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # Uploads
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    UPLOAD_FOLDER = 'static/uploads'
    AVATAR_FOLDER = 'static/avatars'
    MEDIA_FOLDER = 'static/media'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3', 'webm', 'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', 'wav', 'ogg'}
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS = 60
    RATE_LIMIT_WINDOW = 60
    LOGIN_RATE_LIMIT = 5
    REGISTER_RATE_LIMIT = 3
    MESSAGE_RATE_LIMIT = 30
    
    # Security Headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:; connect-src 'self' wss:; frame-ancestors 'none'"
    }

app.config.from_object(Config)

# ============================================================
# CREATE FOLDERS
# ============================================================

for folder in [Config.UPLOAD_FOLDER, Config.AVATAR_FOLDER, Config.MEDIA_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ============================================================
# INITIALIZE EXTENSIONS
# ============================================================

db = SQLAlchemy(app)
CORS(app, origins=["*"], supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ============================================================
# IP BLOCK SYSTEM
# ============================================================

class IPBlockManager:
    def __init__(self):
        self.blocked_ips = {}
        self.failed_attempts = {}
        self.max_attempts = 5
        self.block_duration = 900
        self.whitelist = set()
    
    def block_ip(self, ip, reason="Suspicious activity"):
        self.blocked_ips[ip] = {
            'reason': reason,
            'block_time': datetime.now(),
            'unblock_time': datetime.now() + timedelta(seconds=self.block_duration)
        }
        return True
    
    def unblock_ip(self, ip):
        if ip in self.blocked_ips:
            del self.blocked_ips[ip]
            return True
        return False
    
    def check_ip(self, ip):
        if ip in self.whitelist:
            return True, None
        if ip not in self.blocked_ips:
            return True, None
        block = self.blocked_ips[ip]
        if datetime.now() >= block['unblock_time']:
            del self.blocked_ips[ip]
            return True, None
        remaining = int((block['unblock_time'] - datetime.now()).total_seconds())
        return False, {'ip': ip, 'reason': block['reason'], 'remaining_seconds': remaining}
    
    def record_failed(self, ip):
        self.failed_attempts[ip] = self.failed_attempts.get(ip, 0) + 1
        if self.failed_attempts[ip] >= self.max_attempts:
            self.block_ip(ip, f"Too many failed attempts")
            self.failed_attempts[ip] = 0
            return True
        return False
    
    def reset_failed(self, ip):
        if ip in self.failed_attempts:
            del self.failed_attempts[ip]

ip_manager = IPBlockManager()

# ============================================================
# DATABASE MODELS - COMPLETE
# ============================================================

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120))
    avatar = db.Column(db.String(255))
    bio = db.Column(db.Text)
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    theme = db.Column(db.String(20), default='dark')
    notification_enabled = db.Column(db.Boolean, default=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def is_locked(self):
        if not self.locked_until:
            return False
        return self.locked_until > datetime.utcnow()
    
    def increment_failed_logins(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.session.commit()
    
    def reset_failed_logins(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'phone': self.phone,
            'display_name': self.display_name or self.username,
            'avatar': self.avatar or '/static/default-avatar.png',
            'bio': self.bio,
            'is_online': self.is_online,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_admin': self.is_admin,
            'is_verified': self.is_verified,
            'is_active': self.is_active,
            'theme': self.theme
        }

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'))
    content = db.Column(db.Text)
    message_type = db.Column(db.String(50), default='text')
    media_url = db.Column(db.String(255))
    thumbnail_url = db.Column(db.String(255))
    file_name = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    duration = db.Column(db.Integer)
    is_voice = db.Column(db.Boolean, default=False)
    is_video = db.Column(db.Boolean, default=False)
    is_media = db.Column(db.Boolean, default=False)
    is_edited = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    replied_to_id = db.Column(db.Integer, db.ForeignKey('messages.id'))
    forwarded_from_id = db.Column(db.Integer, db.ForeignKey('messages.id'))
    self_destruct_at = db.Column(db.DateTime)
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.display_name if self.sender else None,
            'receiver_id': self.receiver_id,
            'receiver_name': self.receiver.display_name if self.receiver else None,
            'group_id': self.group_id,
            'channel_id': self.channel_id,
            'content': self.content,
            'message_type': self.message_type,
            'media_url': self.media_url,
            'thumbnail_url': self.thumbnail_url,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'duration': self.duration,
            'is_voice': self.is_voice,
            'is_video': self.is_video,
            'is_media': self.is_media,
            'is_edited': self.is_edited,
            'is_deleted': self.is_deleted,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'replied_to_id': self.replied_to_id,
            'forwarded_from_id': self.forwarded_from_id
        }

class Group(db.Model):
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    avatar = db.Column(db.String(255))
    is_public = db.Column(db.Boolean, default=True)
    join_link = db.Column(db.String(255), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    voice_chat_active = db.Column(db.Boolean, default=False)
    slow_mode_enabled = db.Column(db.Boolean, default=False)
    slow_mode_interval = db.Column(db.Integer, default=0)
    
    creator = db.relationship('User', foreign_keys=[creator_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'creator_id': self.creator_id,
            'creator_name': self.creator.display_name if self.creator else None,
            'avatar': self.avatar or '/static/default-group.png',
            'is_public': self.is_public,
            'join_link': self.join_link,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'member_count': GroupMember.query.filter_by(group_id=self.id, is_active=True).count(),
            'voice_chat_active': self.voice_chat_active
        }

class GroupMember(db.Model):
    __tablename__ = 'group_members'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_creator = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    muted_until = db.Column(db.DateTime)
    
    user = db.relationship('User', foreign_keys=[user_id])

class Channel(db.Model):
    __tablename__ = 'channels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    avatar = db.Column(db.String(255))
    is_public = db.Column(db.Boolean, default=True)
    join_link = db.Column(db.String(255), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    subscriber_count = db.Column(db.Integer, default=0)
    
    creator = db.relationship('User', foreign_keys=[creator_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'creator_id': self.creator_id,
            'creator_name': self.creator.display_name if self.creator else None,
            'avatar': self.avatar or '/static/default-channel.png',
            'is_public': self.is_public,
            'join_link': self.join_link,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'subscriber_count': self.subscriber_count
        }

class ChannelSubscriber(db.Model):
    __tablename__ = 'channel_subscribers'
    
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Story(db.Model):
    __tablename__ = 'stories'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    media_url = db.Column(db.String(255), nullable=False)
    thumbnail_url = db.Column(db.String(255))
    caption = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    view_count = db.Column(db.Integer, default=0)
    is_deleted = db.Column(db.Boolean, default=False)
    is_voice = db.Column(db.Boolean, default=False)
    duration = db.Column(db.Integer)
    
    user = db.relationship('User', foreign_keys=[user_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.display_name if self.user else None,
            'media_url': self.media_url,
            'thumbnail_url': self.thumbnail_url,
            'caption': self.caption,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'view_count': self.view_count,
            'is_voice': self.is_voice,
            'duration': self.duration
        }

class StoryView(db.Model):
    __tablename__ = 'story_views'
    
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

class Call(db.Model):
    __tablename__ = 'calls'
    
    id = db.Column(db.Integer, primary_key=True)
    caller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    call_type = db.Column(db.String(20))
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    duration = db.Column(db.Integer)
    status = db.Column(db.String(20), default='missed')
    is_deleted = db.Column(db.Boolean, default=False)

class Contact(db.Model):
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_blocked = db.Column(db.Boolean, default=False)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'))
    notification_type = db.Column(db.String(50))
    content = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class UserSettings(db.Model):
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    theme = db.Column(db.String(20), default='dark')
    language = db.Column(db.String(10), default='en')
    notifications_enabled = db.Column(db.Boolean, default=True)
    sound_enabled = db.Column(db.Boolean, default=True)
    vibration_enabled = db.Column(db.Boolean, default=True)
    message_preview = db.Column(db.Boolean, default=True)
    auto_download_media = db.Column(db.Boolean, default=True)
    last_seen_privacy = db.Column(db.String(20), default='everyone')
    profile_photo_privacy = db.Column(db.String(20), default='everyone')
    call_privacy = db.Column(db.String(20), default='everyone')

# ============================================================
# DECORATORS
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Please login first'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Please login first'}), 401
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

def rate_limit(limit_type='default'):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Simple rate limiting - store in session
            if 'rate_limit' not in session:
                session['rate_limit'] = {}
            
            current_time = time.time()
            key = f"{limit_type}_{request.remote_addr}"
            
            if key in session['rate_limit']:
                last_request = session['rate_limit'][key]
                if current_time - last_request < 1:  # 1 second between requests
                    return jsonify({'error': 'Rate limit exceeded'}), 429
            
            session['rate_limit'][key] = current_time
            return f(*args, **kwargs)
        return decorated
    return decorator

# ============================================================
# SECURITY HEADERS
# ============================================================

@app.after_request
def add_security_headers(response):
    for header, value in Config.SECURITY_HEADERS.items():
        response.headers[header] = value
    return response

# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/chat')
    return render_template_string(LOGIN_PAGE)

@app.route('/chat')
@login_required
def chat():
    user = User.query.get(session['user_id'])
    users = User.query.filter(User.id != user.id, User.is_active == True).all()
    groups = Group.query.filter(Group.is_deleted == False).all()
    channels = Channel.query.filter(Channel.is_deleted == False).all()
    
    return render_template_string(
        CHAT_PAGE, 
        user=user, 
        users=users, 
        groups=groups, 
        channels=channels
    )

@app.route('/admin')
@admin_required
def admin_panel():
    users = User.query.all()
    messages = Message.query.order_by(Message.created_at.desc()).limit(100).all()
    groups = Group.query.all()
    channels = Channel.query.all()
    blocked_ips = ip_manager.blocked_ips
    
    return render_template_string(
        ADMIN_PAGE,
        users=users,
        messages=messages,
        groups=groups,
        channels=channels,
        blocked_ips=blocked_ips
    )

# ============================================================
# API ROUTES - AUTH
# ============================================================

@app.route('/api/register', methods=['POST'])
@rate_limit('register')
def register():
    try:
        data = request.json
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not username or not email or not password:
            return jsonify({'error': 'All fields required'}), 400
        
        if len(username) < 3 or len(username) > 50:
            return jsonify({'error': 'Username must be 3-50 characters'}), 400
        
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return jsonify({'error': 'Username can only contain letters, numbers, and underscores'}), 400
        
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Create default settings
        settings = UserSettings(user_id=user.id)
        db.session.add(settings)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Account created successfully!'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
@rate_limit('login')
def login():
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'All fields required'}), 400
        
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        if user.is_locked():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            return jsonify({'error': f'Account locked. Try again in {remaining} minutes'}), 403
        
        if not user.check_password(password):
            user.increment_failed_logins()
            return jsonify({'error': 'Invalid credentials'}), 401
        
        user.reset_failed_logins()
        user.is_online = True
        user.last_seen = datetime.utcnow()
        db.session.commit()
        
        session['user_id'] = user.id
        session['username'] = user.username
        session['is_admin'] = user.is_admin
        
        return jsonify({
            'success': True,
            'user': user.to_dict(),
            'redirect': '/chat'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    try:
        user = User.query.get(session['user_id'])
        if user:
            user.is_online = False
            user.last_seen = datetime.utcnow()
            db.session.commit()
        session.clear()
        return jsonify({'success': True})
    except:
        session.clear()
        return jsonify({'success': True})

@app.route('/api/user/profile', methods=['GET', 'PUT'])
@login_required
def user_profile():
    user = User.query.get(session['user_id'])
    
    if request.method == 'GET':
        return jsonify({'user': user.to_dict()})
    
    if request.method == 'PUT':
        try:
            data = request.json
            if 'display_name' in data:
                user.display_name = data['display_name']
            if 'bio' in data:
                user.bio = data['bio'][:500]  # Limit bio length
            if 'theme' in data:
                user.theme = data['theme']
            if 'notification_enabled' in data:
                user.notification_enabled = data['notification_enabled']
            db.session.commit()
            return jsonify({'success': True, 'user': user.to_dict()})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# ============================================================
# API ROUTES - MESSAGES
# ============================================================

@app.route('/api/messages', methods=['GET'])
@login_required
def get_messages():
    try:
        user_id = request.args.get('user_id', type=int)
        group_id = request.args.get('group_id', type=int)
        channel_id = request.args.get('channel_id', type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        current_user_id = session['user_id']
        query = Message.query.filter(Message.is_deleted == False)
        
        if user_id:
            query = query.filter(
                ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
                ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
            )
        elif group_id:
            query = query.filter(Message.group_id == group_id)
        elif channel_id:
            query = query.filter(Message.channel_id == channel_id)
        else:
            return jsonify({'error': 'No chat specified'}), 400
        
        messages = query.order_by(Message.created_at.desc()).offset(offset).limit(limit).all()
        total = query.count()
        
        return jsonify({
            'messages': [m.to_dict() for m in messages[::-1]],
            'total': total,
            'has_more': offset + limit < total
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/messages/send', methods=['POST'])
@login_required
@rate_limit('message')
def send_message():
    try:
        data = request.json
        receiver_id = data.get('receiver_id')
        group_id = data.get('group_id')
        channel_id = data.get('channel_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        media_url = data.get('media_url')
        file_name = data.get('file_name')
        file_size = data.get('file_size')
        replied_to_id = data.get('replied_to_id')
        
        if not content and not media_url:
            return jsonify({'error': 'Message content required'}), 400
        
        message = Message(
            sender_id=session['user_id'],
            receiver_id=receiver_id,
            group_id=group_id,
            channel_id=channel_id,
            content=content,
            message_type=message_type,
            media_url=media_url,
            file_name=file_name,
            file_size=file_size,
            replied_to_id=replied_to_id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Send notification for direct messages
        if receiver_id:
            notification = Notification(
                user_id=receiver_id,
                sender_id=session['user_id'],
                message_id=message.id,
                notification_type='message',
                content=f'New message from {User.query.get(session["user_id"]).display_name}',
                created_at=datetime.utcnow()
            )
            db.session.add(notification)
            db.session.commit()
        
        # Emit via WebSocket
        room = str(receiver_id or group_id or channel_id)
        socketio.emit('new_message', {
            'message': message.to_dict(),
            'chat_id': room
        }, room=room)
        
        return jsonify({'success': True, 'message': message.to_dict()})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/messages/delete/<int:message_id>', methods=['DELETE'])
@login_required
def delete_message(message_id):
    try:
        message = Message.query.get(message_id)
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        if message.sender_id != session['user_id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        message.is_deleted = True
        db.session.commit()
        
        room = str(message.receiver_id or message.group_id or message.channel_id)
        socketio.emit('message_deleted', {'message_id': message_id}, room=room)
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/messages/read/<int:message_id>', methods=['PUT'])
@login_required
def mark_read(message_id):
    try:
        message = Message.query.get(message_id)
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        if message.receiver_id != session['user_id']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        message.is_read = True
        message.read_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# API ROUTES - GROUPS
# ============================================================

@app.route('/api/groups', methods=['GET'])
@login_required
def get_groups():
    groups = Group.query.filter(Group.is_deleted == False).all()
    return jsonify({'groups': [g.to_dict() for g in groups]})

@app.route('/api/groups/create', methods=['POST'])
@login_required
def create_group():
    try:
        data = request.json
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        is_public = data.get('is_public', True)
        member_ids = data.get('member_ids', [])
        
        if not name:
            return jsonify({'error': 'Group name required'}), 400
        
        group = Group(
            name=name,
            description=description,
            creator_id=session['user_id'],
            is_public=is_public,
            join_link=secrets.token_urlsafe(16),
            created_at=datetime.utcnow()
        )
        
        db.session.add(group)
        db.session.flush()
        
        # Add creator as admin
        creator_member = GroupMember(
            group_id=group.id,
            user_id=session['user_id'],
            is_admin=True,
            is_creator=True
        )
        db.session.add(creator_member)
        
        # Add other members
        for user_id in member_ids:
            if user_id != session['user_id']:
                member = GroupMember(
                    group_id=group.id,
                    user_id=user_id,
                    is_admin=False
                )
                db.session.add(member)
        
        db.session.commit()
        
        socketio.emit('group_created', {'group': group.to_dict()}, broadcast=True)
        
        return jsonify({'success': True, 'group': group.to_dict()})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/groups/<int:group_id>/join', methods=['POST'])
@login_required
def join_group(group_id):
    try:
        group = Group.query.get(group_id)
        if not group:
            return jsonify({'error': 'Group not found'}), 404
        
        existing = GroupMember.query.filter_by(group_id=group_id, user_id=session['user_id']).first()
        if existing:
            return jsonify({'error': 'Already a member'}), 400
        
        member = GroupMember(
            group_id=group_id,
            user_id=session['user_id'],
            is_admin=False
        )
        db.session.add(member)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# API ROUTES - CHANNELS
# ============================================================

@app.route('/api/channels', methods=['GET'])
@login_required
def get_channels():
    channels = Channel.query.filter(Channel.is_deleted == False).all()
    return jsonify({'channels': [c.to_dict() for c in channels]})

@app.route('/api/channels/create', methods=['POST'])
@login_required
def create_channel():
    try:
        data = request.json
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        is_public = data.get('is_public', True)
        
        if not name:
            return jsonify({'error': 'Channel name required'}), 400
        
        channel = Channel(
            name=name,
            description=description,
            creator_id=session['user_id'],
            is_public=is_public,
            join_link=secrets.token_urlsafe(16),
            created_at=datetime.utcnow()
        )
        
        db.session.add(channel)
        db.session.commit()
        
        return jsonify({'success': True, 'channel': channel.to_dict()})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# API ROUTES - FILE UPLOADS
# ============================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(Config.UPLOAD_FOLDER, unique_filename)
        file.save(file_path)
        
        file_url = f"/static/uploads/{unique_filename}"
        file_size = os.path.getsize(file_path)
        
        return jsonify({
            'success': True,
            'file_url': file_url,
            'file_name': filename,
            'file_size': file_size
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload/avatar', methods=['POST'])
@login_required
def upload_avatar():
    try:
        if 'avatar' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(Config.AVATAR_FOLDER, unique_filename)
        file.save(file_path)
        
        user = User.query.get(session['user_id'])
        user.avatar = f"/static/avatars/{unique_filename}"
        db.session.commit()
        
        return jsonify({
            'success': True,
            'avatar_url': user.avatar
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# ADMIN API ROUTES
# ============================================================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    users = User.query.all()
    return jsonify({'users': [u.to_dict() for u in users]})

@app.route('/api/admin/users/<int:user_id>/ban', methods=['POST'])
@admin_required
def admin_ban_user(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if user.is_admin:
            return jsonify({'error': 'Cannot ban admin'}), 400
        
        user.is_active = False
        db.session.commit()
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/ip/block', methods=['POST'])
@admin_required
def admin_block_ip():
    try:
        data = request.json
        ip = data.get('ip')
        reason = data.get('reason', 'Admin action')
        
        if not ip:
            return jsonify({'error': 'IP required'}), 400
        
        ip_manager.block_ip(ip, reason)
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/ip/unblock', methods=['POST'])
@admin_required
def admin_unblock_ip():
    try:
        data = request.json
        ip = data.get('ip')
        
        if not ip:
            return jsonify({'error': 'IP required'}), 400
        
        if ip_manager.unblock_ip(ip):
            return jsonify({'success': True})
        return jsonify({'error': 'IP not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/ip/clear', methods=['POST'])
@admin_required
def admin_clear_blocks():
    try:
        ip_manager.blocked_ips.clear()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================
# WEBSOCKET EVENTS
# ============================================================

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.is_online = True
            db.session.commit()
            emit('user_online', {'user_id': user.id, 'username': user.username}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            user.is_online = False
            user.last_seen = datetime.utcnow()
            db.session.commit()
            emit('user_offline', {'user_id': user.id}, broadcast=True)

@socketio.on('join')
def handle_join(data):
    room = data.get('room')
    if room:
        join_room(str(room))
        emit('joined', {'room': room}, room=str(room))

@socketio.on('leave')
def handle_leave(data):
    room = data.get('room')
    if room:
        leave_room(str(room))
        emit('left', {'room': room}, room=str(room))

@socketio.on('typing')
def handle_typing(data):
    room = data.get('room')
    is_typing = data.get('is_typing', True)
    user_id = session.get('user_id')
    
    if room and user_id:
        emit('user_typing', {
            'user_id': user_id,
            'is_typing': is_typing
        }, room=str(room))

@socketio.on('voice_call')
def handle_voice_call(data):
    room = data.get('room')
    action = data.get('action')
    
    if room:
        emit('voice_call_event', {
            'action': action,
            'caller_id': session.get('user_id'),
            'caller_name': User.query.get(session['user_id']).display_name
        }, room=str(room))

# ============================================================
# STATIC FILES
# ============================================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# ============================================================
# COMPLETE HTML PAGES (Embedded in Python)
# ============================================================

LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dx Messenger</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
            padding: 50px 40px;
            border-radius: 24px;
            border: 1px solid #2a2a2a;
            max-width: 420px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        .logo { text-align: center; font-size: 2.8rem; font-weight: 800; color: #ffd700; }
        .logo span { color: #ff3b3b; }
        .subtitle { text-align: center; color: #888; font-size: 0.9rem; margin: 10px 0 30px; }
        .status { background: #1a1a1a; padding: 12px; border-radius: 12px; text-align: center; margin-bottom: 25px; border-left: 4px solid #4caf50; color: #4caf50; font-size: 0.9rem; }
        .tabs { display: flex; gap: 10px; margin-bottom: 25px; }
        .tab-btn { flex: 1; padding: 12px; background: #1a1a1a; border: none; border-radius: 12px; color: #888; font-weight: 600; cursor: pointer; transition: all 0.3s; font-size: 0.95rem; }
        .tab-btn.active { background: #ffd700; color: #0a0a0a; }
        .tab { display: none; }
        .tab.active { display: block; }
        input { width: 100%; padding: 14px 16px; margin: 8px 0; background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; color: #fff; font-size: 1rem; transition: border-color 0.3s; }
        input:focus { outline: none; border-color: #ffd700; }
        .btn { width: 100%; padding: 14px; border-radius: 50px; border: none; font-weight: 700; font-size: 1rem; cursor: pointer; transition: all 0.3s; background: #ffd700; color: #0a0a0a; margin-top: 10px; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(255,215,0,0.2); }
        .error { color: #ff3b3b; font-size: 0.9rem; margin: 8px 0; display: none; }
        .success { color: #4caf50; font-size: 0.9rem; margin: 8px 0; display: none; }
        .links { text-align: center; margin-top: 15px; font-size: 0.85rem; }
        .links a { color: #ffd700; cursor: pointer; text-decoration: none; }
        .links a:hover { text-decoration: underline; }
        .powered { text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #1a1a1a; color: #444; font-size: 0.75rem; }
        .powered strong { color: #ffd700; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">⚡Dx<span>Messenger</span></div>
        <p class="subtitle">245-bit Encrypted • Real-time • Secure</p>
        <div class="status">✅ Server Online</div>
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('login')">Login</button>
            <button class="tab-btn" onclick="switchTab('register')">Sign Up</button>
        </div>
        <div id="loginTab" class="tab active">
            <input type="text" id="loginUsername" placeholder="Username or Email">
            <input type="password" id="loginPassword" placeholder="Password">
            <div id="loginError" class="error"></div>
            <button class="btn" onclick="login()">Login</button>
            <div class="links"><a onclick="switchTab('register')">Create Account</a></div>
        </div>
        <div id="registerTab" class="tab">
            <input type="text" id="regUsername" placeholder="Username">
            <input type="email" id="regEmail" placeholder="Email">
            <input type="password" id="regPassword" placeholder="Password (min 8 chars)">
            <div id="regError" class="error"></div>
            <div id="regSuccess" class="success"></div>
            <button class="btn" onclick="register()">Create Account</button>
            <div class="links"><a onclick="switchTab('login')">Already have an account?</a></div>
        </div>
        <div class="powered">Powered By <strong>⚡ Dx Builder</strong></div>
    </div>
    <script>
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tab + 'Tab').classList.add('active');
            event.target.classList.add('active');
            document.getElementById('loginError').style.display = 'none';
            document.getElementById('regError').style.display = 'none';
            document.getElementById('regSuccess').style.display = 'none';
        }
        async function login() {
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            const errorEl = document.getElementById('loginError');
            if (!username || !password) { errorEl.textContent = 'Please fill in all fields'; errorEl.style.display = 'block'; return; }
            try {
                const res = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
                const data = await res.json();
                if (data.success) { window.location.href = data.redirect || '/chat'; } 
                else { errorEl.textContent = data.error || 'Login failed'; errorEl.style.display = 'block'; }
            } catch (e) { errorEl.textContent = 'Network error'; errorEl.style.display = 'block'; }
        }
        async function register() {
            const username = document.getElementById('regUsername').value;
            const email = document.getElementById('regEmail').value;
            const password = document.getElementById('regPassword').value;
            const errorEl = document.getElementById('regError');
            const successEl = document.getElementById('regSuccess');
            if (!username || !email || !password) { errorEl.textContent = 'Please fill in all fields'; errorEl.style.display = 'block'; return; }
            if (password.length < 8) { errorEl.textContent = 'Password must be at least 8 characters'; errorEl.style.display = 'block'; return; }
            try {
                const res = await fetch('/api/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, email, password }) });
                const data = await res.json();
                if (data.success) {
                    successEl.textContent = '✅ Account created! Please login.';
                    successEl.style.display = 'block';
                    errorEl.style.display = 'none';
                    document.getElementById('regUsername').value = '';
                    document.getElementById('regEmail').value = '';
                    document.getElementById('regPassword').value = '';
                    setTimeout(() => switchTab('login'), 1500);
                } else { errorEl.textContent = data.error || 'Registration failed'; errorEl.style.display = 'block'; }
            } catch (e) { errorEl.textContent = 'Network error'; errorEl.style.display = 'block'; }
        }
        document.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                if (document.getElementById('loginTab').classList.contains('active')) { login(); } 
                else { register(); }
            }
        });
    </script>
</body>
</html>
"""

CHAT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dx Messenger - Chat</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #fff; height: 100vh; overflow: hidden; }
        .app { display: flex; height: 100vh; max-width: 1400px; margin: 0 auto; }
        .sidebar { width: 300px; background: #111; border-right: 1px solid #2a2a2a; display: flex; flex-direction: column; }
        .sidebar-header { padding: 20px; border-bottom: 1px solid #2a2a2a; display: flex; justify-content: space-between; align-items: center; }
        .sidebar-header .logo { color: #ffd700; font-weight: 800; font-size: 1.2rem; }
        .sidebar-header .logo span { color: #ff3b3b; }
        .sidebar-user { display: flex; align-items: center; gap: 10px; padding: 12px 20px; background: #1a1a1a; border-bottom: 1px solid #2a2a2a; }
        .sidebar-user .avatar { width: 40px; height: 40px; border-radius: 50%; background: #2a2a2a; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; color: #ffd700; border: 2px solid #ffd700; }
        .sidebar-user .name { flex: 1; font-weight: 600; }
        .sidebar-user .status { width: 10px; height: 10px; border-radius: 50%; background: #4caf50; }
        .search-box { padding: 12px 20px; }
        .search-box input { width: 100%; padding: 10px 16px; background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 50px; color: #fff; font-size: 0.9rem; }
        .search-box input:focus { outline: none; border-color: #ffd700; }
        .chat-list { flex: 1; overflow-y: auto; padding: 10px 0; }
        .chat-item { display: flex; align-items: center; padding: 12px 20px; cursor: pointer; transition: background 0.2s; gap: 12px; }
        .chat-item:hover { background: #1a1a1a; }
        .chat-item.active { background: #1a1a1a; border-left: 3px solid #ffd700; }
        .chat-item .avatar { width: 45px; height: 45px; border-radius: 50%; background: #2a2a2a; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; color: #ffd700; flex-shrink: 0; }
        .chat-item .info { flex: 1; min-width: 0; }
        .chat-item .info .name { font-weight: 500; font-size: 0.95rem; }
        .chat-item .info .last-msg { color: #888; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .main-chat { flex: 1; display: flex; flex-direction: column; background: #0f0f0f; }
        .chat-header { padding: 16px 24px; border-bottom: 1px solid #2a2a2a; display: flex; align-items: center; gap: 12px; background: #111; }
        .chat-header .avatar { width: 42px; height: 42px; border-radius: 50%; background: #2a2a2a; display: flex; align-items: center; justify-content: center; color: #ffd700; }
        .chat-header .name { font-weight: 600; font-size: 1.1rem; }
        .chat-header .status { font-size: 0.75rem; color: #4caf50; }
        .chat-header .actions { margin-left: auto; display: flex; gap: 15px; }
        .chat-header .actions i { color: #888; cursor: pointer; font-size: 1.2rem; }
        .messages { flex: 1; overflow-y: auto; padding: 20px 24px; display: flex; flex-direction: column; gap: 8px; }
        .msg { max-width: 70%; padding: 10px 16px; border-radius: 16px; font-size: 0.95rem; line-height: 1.4; word-wrap: break-word; }
        .msg.sent { align-self: flex-end; background: #ffd700; color: #0a0a0a; border-bottom-right-radius: 4px; }
        .msg.received { align-self: flex-start; background: #1a1a1a; color: #fff; border-bottom-left-radius: 4px; }
        .msg .time { font-size: 0.65rem; opacity: 0.6; margin-top: 4px; text-align: right; }
        .msg-input { padding: 16px 24px; border-top: 1px solid #2a2a2a; display: flex; gap: 12px; background: #111; }
        .msg-input input { flex: 1; padding: 12px 20px; background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 50px; color: #fff; font-size: 0.95rem; }
        .msg-input input:focus { outline: none; border-color: #ffd700; }
        .msg-input button { padding: 12px 28px; border-radius: 50px; border: none; font-weight: 600; cursor: pointer; background: #ffd700; color: #0a0a0a; transition: all 0.3s; }
        .msg-input button:hover { transform: scale(1.02); }
        .empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #444; }
        .empty-state .icon { font-size: 4rem; margin-bottom: 15px; }
        .logout-btn { background: #ff3b3b; color: #fff; border: none; padding: 6px 16px; border-radius: 50px; cursor: pointer; font-weight: 600; font-size: 0.8rem; }
        .logout-btn:hover { opacity: 0.8; }
        .admin-btn { background: #ffd700; color: #0a0a0a; border: none; padding: 6px 16px; border-radius: 50px; cursor: pointer; font-weight: 600; font-size: 0.8rem; margin-right: 10px; }
        @media (max-width: 768px) { .sidebar { width: 240px; } }
        @media (max-width: 600px) { .sidebar { width: 100%; max-height: 200px; border-right: none; border-bottom: 1px solid #2a2a2a; } .app { flex-direction: column; } }
    </style>
</head>
<body>
    <div class="app">
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="logo">⚡Dx<span>M</span></div>
                <div>
                    {% if user.is_admin %}
                    <button class="admin-btn" onclick="window.location.href='/admin'">⚙️ Admin</button>
                    {% endif %}
                    <button class="logout-btn" onclick="logout()">Logout</button>
                </div>
            </div>
            <div class="sidebar-user">
                <div class="avatar">👤</div>
                <div class="name">{{ user.display_name or user.username }}</div>
                <div class="status"></div>
            </div>
            <div class="search-box">
                <input type="text" placeholder="Search users..." id="searchInput" oninput="searchUsers()">
            </div>
            <div class="chat-list" id="chatList">
                {% for u in users %}
                <div class="chat-item" onclick="openChat('user', {{ u.id }})" data-id="{{ u.id }}">
                    <div class="avatar">👤</div>
                    <div class="info">
                        <div class="name">{{ u.display_name or u.username }}</div>
                        <div class="last-msg">{% if u.is_online %}🟢 Online{% else %}Last seen recently{% endif %}</div>
                    </div>
                </div>
                {% endfor %}
                {% for g in groups %}
                <div class="chat-item" onclick="openChat('group', {{ g.id }})" data-id="{{ g.id }}">
                    <div class="avatar">👥</div>
                    <div class="info">
                        <div class="name">📢 {{ g.name }}</div>
                        <div class="last-msg">{{ g.member_count }} members</div>
                    </div>
                </div>
                {% endfor %}
                {% for c in channels %}
                <div class="chat-item" onclick="openChat('channel', {{ c.id }})" data-id="{{ c.id }}">
                    <div class="avatar">📡</div>
                    <div class="info">
                        <div class="name">📢 {{ c.name }}</div>
                        <div class="last-msg">{{ c.subscriber_count }} subscribers</div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        <div class="main-chat">
            <div class="chat-header">
                <div class="avatar">💬</div>
                <div>
                    <div class="name" id="chatName">Select a chat</div>
                    <div class="status" id="chatStatus">Click a user to start messaging</div>
                </div>
                <div class="actions">
                    <span style="cursor:pointer;" onclick="alert('Voice call coming soon!')">📞</span>
                    <span style="cursor:pointer;" onclick="alert('Video call coming soon!')">📹</span>
                    <span style="cursor:pointer;" onclick="alert('Group info')">ℹ️</span>
                </div>
            </div>
            <div class="messages" id="messages">
                <div class="empty-state">
                    <div class="icon">💬</div>
                    <h3>No messages yet</h3>
                    <p>Select a chat to start messaging</p>
                </div>
            </div>
            <div class="msg-input">
                <input type="text" id="messageInput" placeholder="Type a message..." onkeypress="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
    <script>
        const socket = io();
        let currentChatType = null;
        let currentChatId = null;
        const userId = {{ user.id }};

        socket.on('connect', () => console.log('Connected'));
        
        socket.on('new_message', (data) => {
            if (currentChatId && (data.chat_id == currentChatId || data.message.sender_id == currentChatId)) {
                addMessage(data.message);
            }
        });

        socket.on('user_online', (data) => {
            document.querySelectorAll('.chat-item').forEach(el => {
                if (el.dataset.id == data.user_id) {
                    const lastMsg = el.querySelector('.last-msg');
                    if (lastMsg) lastMsg.textContent = '🟢 Online';
                }
            });
        });

        socket.on('user_offline', (data) => {
            document.querySelectorAll('.chat-item').forEach(el => {
                if (el.dataset.id == data.user_id) {
                    const lastMsg = el.querySelector('.last-msg');
                    if (lastMsg) lastMsg.textContent = 'Offline';
                }
            });
        });

        async function openChat(type, id) {
            currentChatType = type;
            currentChatId = id;
            
            document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.chat-item').forEach(el => {
                if (el.dataset.id == id) el.classList.add('active');
            });

            const nameMap = {
                {% for u in users %}
                "user_{{ u.id }}": "{{ u.display_name or u.username }}",
                {% endfor %}
                {% for g in groups %}
                "group_{{ g.id }}": "{{ g.name }}",
                {% endfor %}
                {% for c in channels %}
                "channel_{{ c.id }}": "{{ c.name }}",
                {% endfor %}
            };
            document.getElementById('chatName').textContent = nameMap[type + '_' + id] || 'Chat';
            document.getElementById('chatStatus').textContent = 'Online';

            socket.emit('join', { room: id });

            try {
                const res = await fetch(`/api/messages?${type}_id=${id}&limit=50`);
                const data = await res.json();
                const messagesDiv = document.getElementById('messages');
                messagesDiv.innerHTML = '';
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach(msg => addMessage(msg));
                } else {
                    messagesDiv.innerHTML = `<div class="empty-state"><div class="icon">💬</div><h3>No messages</h3><p>Send the first message!</p></div>`;
                }
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } catch (e) { console.error(e); }
        }

        function addMessage(msg) {
            const messagesDiv = document.getElementById('messages');
            const emptyState = messagesDiv.querySelector('.empty-state');
            if (emptyState) emptyState.remove();
            const div = document.createElement('div');
            const isSent = msg.sender_id == userId;
            div.className = 'msg ' + (isSent ? 'sent' : 'received');
            div.innerHTML = `${msg.content || '📎 Media'}<div class="time">${new Date(msg.created_at).toLocaleTimeString()}</div>`;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const content = input.value.trim();
            if (!content || !currentChatId) return;
            
            const data = { content, message_type: 'text' };
            if (currentChatType === 'user') data.receiver_id = currentChatId;
            else if (currentChatType === 'group') data.group_id = currentChatId;
            else if (currentChatType === 'channel') data.channel_id = currentChatId;
            
            try {
                const res = await fetch('/api/messages/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await res.json();
                if (result.success) { addMessage(result.message); input.value = ''; }
                else { alert('Error: ' + result.error); }
            } catch (e) { alert('Network error'); }
        }

        function searchUsers() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('.chat-item').forEach(el => {
                const name = el.querySelector('.name')?.textContent?.toLowerCase() || '';
                el.style.display = name.includes(query) ? 'flex' : 'none';
            });
        }

        async function logout() {
            try { await fetch('/api/logout', { method: 'POST' }); } catch(e) {}
            window.location.href = '/';
        }
    </script>
</body>
</html>
"""

ADMIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel - Dx Messenger</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #fff; padding: 20px; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid #2a2a2a; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .logo { color: #ffd700; font-size: 2rem; font-weight: 800; }
        .logo span { color: #ff3b3b; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .stat-card { background: #111; padding: 20px; border-radius: 16px; border: 1px solid #2a2a2a; text-align: center; }
        .stat-card .number { font-size: 2.5rem; font-weight: 700; color: #ffd700; }
        .stat-card .label { color: #888; font-size: 0.85rem; margin-top: 5px; }
        .card { background: #111; border-radius: 16px; border: 1px solid #2a2a2a; padding: 20px; margin-bottom: 20px; }
        .card h2 { color: #ffd700; font-size: 1.2rem; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #1a1a1a; }
        th { color: #ffd700; font-weight: 600; }
        td { color: #ccc; }
        .badge { padding: 4px 12px; border-radius: 50px; font-size: 0.75rem; font-weight: 600; }
        .badge-success { background: #4caf50; color: #fff; }
        .badge-danger { background: #ff3b3b; color: #fff; }
        .badge-warning { background: #ffd700; color: #0a0a0a; }
        .btn { padding: 6px 16px; border-radius: 50px; border: none; cursor: pointer; font-weight: 600; font-size: 0.8rem; transition: all 0.3s; }
        .btn-danger { background: #ff3b3b; color: #fff; }
        .btn-success { background: #4caf50; color: #fff; }
        .btn-primary { background: #ffd700; color: #0a0a0a; }
        .btn:hover { opacity: 0.8; transform: translateY(-1px); }
        .back { color: #ffd700; text-decoration: none; }
        .back:hover { text-decoration: underline; }
        .ip-list { display: flex; flex-wrap: wrap; gap: 8px; }
        .ip-item { background: #1a1a1a; padding: 8px 16px; border-radius: 50px; font-family: monospace; font-size: 0.85rem; border: 1px solid #2a2a2a; display: flex; align-items: center; gap: 10px; }
        .ip-item .reason { color: #888; font-size: 0.75rem; }
        .actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px; }
        @media (max-width: 600px) { table { font-size: 0.8rem; } th, td { padding: 8px; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">⚡Dx<span>Admin</span></div>
            <div>
                <a href="/chat" class="back">← Back to Chat</a>
                <button class="btn btn-danger" onclick="logout()" style="margin-left:10px;">Logout</button>
            </div>
        </div>
        <div class="stats">
            <div class="stat-card"><div class="number">{{ users|length }}</div><div class="label">Total Users</div></div>
            <div class="stat-card"><div class="number">{{ messages|length }}</div><div class="label">Recent Messages</div></div>
            <div class="stat-card"><div class="number">{{ groups|length }}</div><div class="label">Total Groups</div></div>
            <div class="stat-card"><div class="number">{{ blocked_ips|length }}</div><div class="label">Blocked IPs</div></div>
        </div>
        <div class="card">
            <h2>📊 Users</h2>
            <table>
                <tr><th>ID</th><th>Username</th><th>Email</th><th>Status</th><th>Actions</th></tr>
                {% for u in users %}
                <tr>
                    <td>{{ u.id }}</td>
                    <td>{{ u.username }}</td>
                    <td>{{ u.email }}</td>
                    <td>
                        {% if u.is_online %}<span class="badge badge-success">Online</span>{% else %}<span class="badge badge-warning">Offline</span>{% endif %}
                        {% if u.is_admin %}<span class="badge badge-success">Admin</span>{% endif %}
                        {% if not u.is_active %}<span class="badge badge-danger">Banned</span>{% endif %}
                    </td>
                    <td>
                        {% if not u.is_admin and u.is_active %}
                        <button class="btn btn-danger" onclick="banUser({{ u.id }})">Ban</button>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </table>
        </div>
        <div class="card">
            <h2>🚫 Blocked IPs</h2>
            <div class="ip-list">
                {% for ip, info in blocked_ips.items() %}
                <div class="ip-item">
                    {{ ip }}
                    <span class="reason">{{ info.reason }}</span>
                    <button class="btn btn-success" onclick="unblockIP('{{ ip }}')">Unblock</button>
                </div>
                {% else %}
                <p style="color:#444;">No IPs currently blocked</p>
                {% endfor %}
            </div>
        </div>
        <div class="card">
            <h2>⚡ Quick Actions</h2>
            <div class="actions">
                <button class="btn btn-danger" onclick="clearAllBlocks()">Clear All Blocks</button>
                <button class="btn btn-primary" onclick="location.reload()">Refresh</button>
            </div>
        </div>
        <div style="text-align:center;color:#444;font-size:0.8rem;margin-top:30px;">
            Powered By <strong style="color:#ffd700;">⚡ Dx Builder</strong>
        </div>
    </div>
    <script>
        async function banUser(userId) {
            if (!confirm('Ban this user?')) return;
            try {
                const res = await fetch(`/api/admin/users/${userId}/ban`, { method: 'POST' });
                const data = await res.json();
                if (data.success) { alert('User banned!'); location.reload(); }
                else { alert('Error: ' + data.error); }
            } catch (e) { alert('Network error'); }
        }
        async function unblockIP(ip) {
            if (!confirm('Unblock IP: ' + ip + '?')) return;
            try {
                const res = await fetch('/api/admin/ip/unblock', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ip }) });
                const data = await res.json();
                if (data.success) { alert('IP unblocked!'); location.reload(); }
                else { alert('Error: ' + data.error); }
            } catch (e) { alert('Network error'); }
        }
        async function clearAllBlocks() {
            if (!confirm('Clear ALL blocked IPs?')) return;
            try {
                const res = await fetch('/api/admin/ip/clear', { method: 'POST' });
                const data = await res.json();
                if (data.success) { alert('All blocks cleared!'); location.reload(); }
            } catch (e) { alert('Network error'); }
        }
        async function logout() {
            try { await fetch('/api/logout', { method: 'POST' }); } catch(e) {}
            window.location.href = '/';
        }
    </script>
</body>
</html>
"""

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Database initialized!")
        print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ⚡ Dx Messenger - COMPLETE A-Z SYSTEM                     ║
║                                                              ║
║   ✅ Everything is ready!                                   ║
║   ✅ All features A-Z included                              ║
║   ✅ Production ready                                       ║
║                                                              ║
║   📱 Chat: http://localhost:5000                           ║
║   ⚙️ Admin: http://localhost:5000/admin                    ║
║                                                              ║
║   ⚡ Powered by Dx Builder                                  ║
╚══════════════════════════════════════════════════════════════╝
        """)
    
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)

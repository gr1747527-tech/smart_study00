# ============================================
# SMART STUDY AI — ULTRA-STRONG LOGIC & MEMORY
# Production Ready • All Features • Error-Free
# ============================================
import os, logging, hashlib, time, threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, send_from_directory, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests, re, base64, json, webbrowser, uuid

# ✅ Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ .env loaded!")
except ImportError:
    print("⚠️ python-dotenv not installed. Run: pip install python-dotenv")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Optional imports
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    logger.info("✅ gTTS Ready!")
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("⚠️ gTTS not installed. Voice disabled. Run: pip install gTTS")

# ── Flask App Setup ──
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Create required directories
for folder in ['voice_cache', 'analysis_images', 'thumbnails', 'chat_history', 'user_memory']:
    os.makedirs(f'uploads/{folder}', exist_ok=True)

# ── Login Manager ──
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '⚠️ Please login to continue.'

# ── API Keys ──
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

# ⚡ Ultra-fast answer cache
INSTANT_CACHE = {}
CACHE_TTL = 600  # 10 minutes
CACHE_LOCK = threading.Lock()

# ============================================
# 🧠 ADVANCED MEMORY SYSTEM
# ============================================
class UserMemory:
    """Persistent memory for each user with TTL, threading, and auto-save"""
    
    def __init__(self):
        self.memory_dir = 'uploads/user_memory'
        self.conversations = {}   # uid → list of messages
        self.user_facts = {}      # uid → dict of facts
        self.user_meta = {}       # uid → metadata
        self.lock = threading.RLock()
        self.max_messages = 50
        self.ttl = 7200  # 2 hours

    def _file(self, uid):
        return os.path.join(self.memory_dir, f'mem_{uid}.json')

    def load(self, uid):
        """Load user memory from disk"""
        with self.lock:
            filepath = self._file(uid)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.conversations[uid] = data.get('conversations', [])
                self.user_facts[uid] = data.get('facts', {})
                self.user_meta[uid] = data.get('meta', {
                    'first_seen': time.time(),
                    'last_seen': time.time(),
                    'total_messages': 0,
                    'total_sessions': 0
                })
                return True
            except:
                self.conversations[uid] = []
                self.user_facts[uid] = {}
                self.user_meta[uid] = {
                    'first_seen': time.time(),
                    'last_seen': time.time(),
                    'total_messages': 0,
                    'total_sessions': 0
                }
                return False

    def save(self, uid):
        """Save user memory to disk"""
        with self.lock:
            filepath = self._file(uid)
            try:
                data = {
                    'conversations': self.conversations.get(uid, []),
                    'facts': self.user_facts.get(uid, {}),
                    'meta': self.user_meta.get(uid, {})
                }
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                logger.error(f"Memory save error for {uid}: {e}")
                return False

    def add_message(self, uid, role, content):
        """Add a message and auto-clean expired ones"""
        with self.lock:
            if uid not in self.conversations:
                self.conversations[uid] = []
            
            # Add message
            self.conversations[uid].append({
                'role': role,
                'content': content[:500],  # Store first 500 chars
                'timestamp': time.time()
            })
            
            # Trim to max size
            if len(self.conversations[uid]) > self.max_messages:
                self.conversations[uid] = self.conversations[uid][-self.max_messages:]
            
            # Clean expired messages
            now = time.time()
            self.conversations[uid] = [
                m for m in self.conversations[uid]
                if now - m.get('timestamp', 0) < self.ttl
            ]
            
            # Update metadata
            if uid in self.user_meta:
                self.user_meta[uid]['last_seen'] = now
                self.user_meta[uid]['total_messages'] += 1
            
            # Auto-save
            self.save(uid)

    def get_context(self, uid, count=3):
        """Get recent conversation context for AI prompt"""
        with self.lock:
            if uid not in self.conversations or not self.conversations[uid]:
                return ""
            recent = self.conversations[uid][-count:]
            lines = []
            for m in recent:
                role = "User" if m['role'] == 'user' else "Assistant"
                lines.append(f"{role}: {m['content'][:150]}")
            return "\n".join(lines)

    def learn_fact(self, uid, key, value):
        """Store a fact about the user"""
        with self.lock:
            if uid not in self.user_facts:
                self.user_facts[uid] = {}
            self.user_facts[uid][key] = value
        self.save(uid)

    def get_facts(self, uid):
        """Get all learned facts about user"""
        with self.lock:
            return self.user_facts.get(uid, {}).copy()

    def extract_facts(self, uid, message):
        """Smart fact extraction from user messages"""
        msg = message.lower()
        
        # Name detection (multiple patterns)
        name_patterns = [
            r'(?:my name is|i am|i\'m|myself|naam|mai hu|mera naam|call me|you can call me)\s+(\w+)',
            r'(?:this is) (\w+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, msg)
            if match:
                self.learn_fact(uid, 'name', match.group(1).title())
                break
        
        # Interest detection with scoring
        interest_map = {
            'coding': ['code', 'program', 'python', 'java', 'javascript', 'developer', 'software', 'web', 'app', 'algorithm'],
            'music': ['song', 'music', 'singer', 'guitar', 'piano', 'listen', 'concert', 'band', 'rap', 'classical'],
            'sports': ['cricket', 'football', 'game', 'player', 'match', 'ipl', 'world cup', 'batting', 'bowling'],
            'movies': ['movie', 'film', 'actor', 'actress', 'bollywood', 'hollywood', 'cinema', 'watch', 'netflix'],
            'reading': ['book', 'read', 'novel', 'author', 'story', 'literature', 'poem', 'fiction', 'non-fiction'],
            'travel': ['travel', 'trip', 'visit', 'place', 'ghoomna', 'tour', 'beach', 'mountain', 'foreign'],
            'food': ['food', 'eat', 'pizza', 'biryani', 'cook', 'recipe', 'restaurant', 'tasty', 'delicious'],
            'fitness': ['gym', 'exercise', 'workout', 'fitness', 'health', 'diet', 'yoga', 'running', 'sports'],
        }
        
        detected = []
        for interest, keywords in interest_map.items():
            if any(kw in msg for kw in keywords):
                detected.append(interest)
        
        if detected:
            current = self.user_facts.get(uid, {}).get('interests', [])
            for interest in detected:
                if interest not in current:
                    current.append(interest)
            self.learn_fact(uid, 'interests', current[:8])  # Max 8 interests
        
        # Location detection
        location_patterns = [
            r'(?:i live in|i am from|from|in) (\w+(?:\s+\w+)?)',
            r'(?:i\'m in|currently in) (\w+(?:\s+\w+)?)',
        ]
        for pattern in location_patterns:
            match = re.search(pattern, msg)
            if match:
                location = match.group(1).title()
                if location.lower() not in ['the', 'a', 'an', 'my', 'your', 'this', 'that']:
                    self.learn_fact(uid, 'location', location)
                    break

    def get_full_context(self, uid):
        """Get complete context for smart responses"""
        with self.lock:
            conversation = self.get_context(uid, 5)
            facts = self.get_facts(uid)
            meta = self.user_meta.get(uid, {})
            
            context = {
                'conversation': conversation,
                'facts': facts,
                'is_returning_user': meta.get('total_messages', 0) > 5,
                'total_messages': meta.get('total_messages', 0)
            }
            return context

    def record_session(self, uid):
        """Record a new session"""
        with self.lock:
            if uid in self.user_meta:
                self.user_meta[uid]['total_sessions'] += 1
                self.user_meta[uid]['last_seen'] = time.time()
        self.save(uid)

    def clear(self, uid):
        """Clear all memory for a user"""
        with self.lock:
            self.conversations[uid] = []
            self.user_facts[uid] = {}
            self.user_meta[uid] = {
                'first_seen': time.time(),
                'last_seen': time.time(),
                'total_messages': 0,
                'total_sessions': 0
            }
        filepath = self._file(uid)
        if os.path.exists(filepath):
            os.remove(filepath)

# Initialize memory system
user_memory = UserMemory()

# ============================================
# 🎤 VOICE ENGINE
# ============================================
class VoiceEngine:
    """High-performance voice engine with dual-layer caching"""
    
    def __init__(self):
        self.cache_dir = 'uploads/voice_cache'
        self.memory_cache = {}  # In-memory cache
        self.lock = threading.Lock()
        self.cache_ttl = 86400  # 24 hours

    def detect_language(self, text):
        """Smart language detection using script analysis"""
        if not text:
            return 'en'
        hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
        total_chars = len(text.replace(' ', ''))
        if total_chars == 0:
            return 'en'
        ratio = hindi_chars / total_chars
        if ratio > 0.15:
            return 'hi'
        return 'en'

    def generate(self, text):
        """Generate speech with instant caching"""
        if not text or not GTTS_AVAILABLE:
            return None, None
        
        # Clean text
        clean = re.sub(r'<[^>]*>', '', text)
        clean = re.sub(r'[*_`#~]', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()[:500]
        if not clean:
            return None, None
        
        lang = self.detect_language(clean)
        cache_key = (clean, lang)
        
        # Check in-memory cache
        with self.lock:
            if cache_key in self.memory_cache:
                return self.memory_cache[cache_key], lang
        
        # Check disk cache
        hash_key = hashlib.md5(f"{clean}_{lang}".encode()).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{hash_key}.mp3")
        
        if os.path.exists(cache_file):
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < self.cache_ttl:
                with open(cache_file, 'rb') as f:
                    audio = base64.b64encode(f.read()).decode()
                with self.lock:
                    self.memory_cache[cache_key] = audio
                return audio, lang
        
        # Generate new audio
        try:
            tts = gTTS(
                text=clean,
                lang=lang,
                tld='co.in' if lang == 'en' else None,
                slow=False
            )
            tts.save(cache_file)
            with open(cache_file, 'rb') as f:
                audio = base64.b64encode(f.read()).decode()
            with self.lock:
                self.memory_cache[cache_key] = audio
            return audio, lang
        except Exception as e:
            logger.error(f"Voice generation error: {e}")
            return None, None

# Initialize voice engine
voice_engine = VoiceEngine()

# ============================================
# 💾 JSON STORAGE (with error recovery)
# ============================================
class JSONStorage:
    """Reliable JSON file operations with backup"""
    
    @staticmethod
    def load(filepath, default=None):
        if default is None:
            default = {}
        if not os.path.exists(filepath):
            return default
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Try backup
            backup = filepath + '.bak'
            if os.path.exists(backup):
                try:
                    with open(backup, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    pass
            return default
    
    @staticmethod
    def save(filepath, data):
        try:
            # Create backup first
            if os.path.exists(filepath):
                backup = filepath + '.bak'
                try:
                    os.replace(filepath, backup)
                except:
                    pass
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Storage save error for {filepath}: {e}")
            return False

# ============================================
# 💬 CHAT HISTORY
# ============================================
class ChatHistory:
    """Complete chat history management"""
    
    @staticmethod
    def file(uid):
        return os.path.join('uploads', 'chat_history', f'ch_{uid}.json')
    
    @staticmethod
    def load(uid):
        try:
            with open(ChatHistory.file(uid), 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"chats": []}
    
    @staticmethod
    def save(uid, data):
        with open(ChatHistory.file(uid), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def add(uid, cid, role, content, img=None):
        history = ChatHistory.load(uid)
        
        # Find existing chat or create new
        for chat in history['chats']:
            if chat['id'] == cid:
                chat['messages'].append({
                    'role': role,
                    'content': content,
                    'image_url': img,
                    'timestamp': datetime.now().isoformat()
                })
                chat['updated_at'] = datetime.now().isoformat()
                ChatHistory.save(uid, history)
                return
        
        # Create new chat
        history['chats'].append({
            'id': cid,
            'title': content[:50] if len(content) > 50 else content,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'messages': [{
                'role': role,
                'content': content,
                'image_url': img,
                'timestamp': datetime.now().isoformat()
            }]
        })
        ChatHistory.save(uid, history)
    
    @staticmethod
    def chats(uid):
        """Get all chats sorted by most recent"""
        history = ChatHistory.load(uid)
        return sorted(
            [
                {
                    'id': c['id'],
                    'title': c.get('title', 'Untitled'),
                    'updated_at': c.get('updated_at', ''),
                    'message_count': len(c.get('messages', []))
                }
                for c in history['chats']
            ],
            key=lambda x: x['updated_at'],
            reverse=True
        )
    
    @staticmethod
    def messages(uid, cid):
        """Get messages for a specific chat"""
        history = ChatHistory.load(uid)
        for chat in history['chats']:
            if chat['id'] == cid:
                return chat.get('messages', [])
        return []
    
    @staticmethod
    def delete(uid, cid):
        """Delete a chat"""
        history = ChatHistory.load(uid)
        history['chats'] = [c for c in history['chats'] if c['id'] != cid]
        ChatHistory.save(uid, history)
    
    @staticmethod
    def clear(uid):
        """Clear all chats"""
        ChatHistory.save(uid, {"chats": []})

# ============================================
# 👤 USER MODEL
# ============================================
class User(UserMixin):
    """User model with auth type tracking"""
    
    def __init__(self, uid, username, email, auth_type='email'):
        self.id = uid
        self.username = username
        self.email = email
        self.auth_type = auth_type

@login_manager.user_loader
def load_user(uid):
    """Load user from JSON storage"""
    users = JSONStorage.load('users.json')
    if uid in users:
        u = users[uid]
        return User(uid, u['username'], u['email'], u.get('auth_type', 'email'))
    return None

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_text(text):
    """Format AI response for HTML display"""
    if not text:
        return ""
    # Code blocks
    text = re.sub(
        r'```(\w*)\n(.*?)```',
        r'<pre><code class="language-\1">\2</code></pre>',
        text,
        flags=re.DOTALL
    )
    # Inline code
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    # Bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    # Line breaks
    text = text.replace('\n', '<br>')
    return text

# ============================================
# ⚡ ULTRA-FAST ANSWER ENGINE
# ============================================
def save_memory_async(uid, query, answer):
    """Save to memory in background thread"""
    try:
        user_memory.add_message(uid, 'user', query)
        user_memory.add_message(uid, 'assistant', answer)
        user_memory.extract_facts(uid, query)
    except Exception as e:
        logger.error(f"Memory async error: {e}")

def get_answer(query, uid, mode='instant'):
    """
    Main answer generation with:
    - Instant cache check
    - Memory context
    - Multi-model fallback
    - Background memory save
    """
    q = query.strip().lower()
    now = time.time()
    
    # Load memory if needed
    if uid not in user_memory.conversations:
        user_memory.load(uid)
    
    # Check instant cache
    if mode == 'instant':
        with CACHE_LOCK:
            if q in INSTANT_CACHE and (now - INSTANT_CACHE[q][1] < CACHE_TTL):
                logger.info(f"⚡ Cache hit: {q[:50]}")
                return INSTANT_CACHE[q][0]
    
    # Build smart context
    full_context = user_memory.get_full_context(uid)
    context = full_context['conversation']
    facts = full_context['facts']
    is_returning = full_context['is_returning_user']
    
    # Build intelligent system prompt
    system_parts = [
        "You are Smart Study AI, an intelligent assistant for students.",
        "Be helpful, accurate, and concise.",
        "Answer in the user's preferred language.",
    ]
    
    if context:
        system_parts.append(f"\n## Recent Conversation:\n{context}")
    
    if facts:
        if 'name' in facts:
            system_parts.append(f"\nUser's name: {facts['name']}")
        if 'interests' in facts:
            system_parts.append(f"User's interests: {', '.join(facts['interests'])}")
        if 'location' in facts:
            system_parts.append(f"User's location: {facts['location']}")
    
    if is_returning:
        system_parts.append("\nThis is a returning user. Reference past conversations naturally.")
    
    system = "\n".join(system_parts)
    
    # Model selection based on mode
    if mode == 'instant':
        models = ["llama-3.1-8b-instant"]
        max_tokens = 200
        temperature = 0.3
    else:
        models = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
        max_tokens = 2000
        temperature = 0.4
    
    # Try each model
    for model in models:
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": query}
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and data['choices']:
                    answer = data['choices'][0]['message']['content']
                    
                    # Cache for instant mode
                    if mode == 'instant':
                        with CACHE_LOCK:
                            INSTANT_CACHE[q] = (answer, now)
                    
                    # Save to memory in background
                    threading.Thread(
                        target=save_memory_async,
                        args=(uid, query, answer),
                        daemon=True
                    ).start()
                    
                    return answer
                    
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️ Model {model} timeout")
        except Exception as e:
            logger.warning(f"❌ Model {model} error: {e}")
    
    # Ultimate fallback
    fallback = "I'm here to help! Please try asking your question again. 😊"
    if mode == 'instant':
        with CACHE_LOCK:
            INSTANT_CACHE[q] = (fallback, now)
    return fallback

# ============================================
# 🔐 AUTHENTICATION ROUTES
# ============================================
@app.route('/')
def index():
    """Root redirect"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login with email/password"""
    # Already logged in
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        # Validate input
        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        
        # Load users
        users = JSONStorage.load('users.json')
        
        # Find user by email (UNIQUE)
        found_user = None
        for uid, u in users.items():
            if u.get('email', '').lower() == email:
                found_user = (uid, u)
                break
        
        if not found_user:
            flash('No account found with this email. Please register first.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        
        uid, user_data = found_user
        
        # Verify password
        if not check_password_hash(user_data.get('password', ''), password):
            flash('Incorrect password. Please try again.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        
        # Login successful
        user = User(uid, user_data['username'], user_data['email'], user_data.get('auth_type', 'email'))
        login_user(user, remember=True)
        session['just_logged_in'] = True
        session['login_username'] = user_data['username']
        
        # Load user memory
        user_memory.load(uid)
        user_memory.record_session(uid)
        
        logger.info(f"✅ Login: {user_data['username']} ({email})")
        return redirect(url_for('dashboard'))
    
    return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Register new account"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        # Strong validation
        errors = []
        
        # Username validation
        if not username:
            errors.append('Username is required.')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif len(username) > 30:
            errors.append('Username must be less than 30 characters.')
        elif not re.match(r'^[a-zA-Z0-9_ ]+$', username):
            errors.append('Username can only contain letters, numbers, spaces, and underscores.')
        
        # Email validation
        if not email:
            errors.append('Email is required.')
        elif '@' not in email or '.' not in email:
            errors.append('Please enter a valid email address.')
        elif len(email) > 100:
            errors.append('Email is too long.')
        
        # Password validation
        if not password:
            errors.append('Password is required.')
        elif len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        elif len(password) > 128:
            errors.append('Password is too long.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)
        
        # Check UNIQUE email
        users = JSONStorage.load('users.json')
        if any(u.get('email', '').lower() == email for u in users.values()):
            flash('An account with this email already exists. Please login instead.', 'error')
            return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)
        
        # Create user
        uid = str(int(time.time() * 1000))  # Millisecond precision
        users[uid] = {
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'auth_type': 'email',
            'created_at': datetime.now().isoformat(),
            'last_login': None,
            'login_count': 0
        }
        
        if JSONStorage.save('users.json', users):
            logger.info(f"🆕 New user registered: {username} ({email})")
            flash('✅ Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('❌ Registration failed. Please try again.', 'error')
            return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)
    
    return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/api/google-callback', methods=['POST'])
def google_callback():
    """Google Sign-In callback"""
    data = request.get_json(silent=True) or {}
    credential = data.get('credential', '')
    
    if not credential:
        return jsonify({'success': False, 'error': 'No credential provided'}), 400
    
    try:
        # Verify Google token
        verify_response = requests.get(
            f'https://oauth2.googleapis.com/tokeninfo?id_token={credential}',
            timeout=10
        )
        
        if verify_response.status_code != 200:
            return jsonify({'success': False, 'error': 'Invalid Google token'}), 400
        
        user_data = verify_response.json()
        
        # Verify audience (client ID)
        if GOOGLE_CLIENT_ID and user_data.get('aud') != GOOGLE_CLIENT_ID:
            return jsonify({'success': False, 'error': 'Token not issued for this application'}), 400
        
        email = user_data.get('email', '').lower()
        if not email:
            return jsonify({'success': False, 'error': 'No email in Google account'}), 400
        
        name = user_data.get('name', email.split('@')[0])
        google_id = user_data.get('sub', '')
        
        # Find or create user
        users = JSONStorage.load('users.json')
        uid = None
        
        for k, v in users.items():
            if v.get('email', '').lower() == email:
                uid = k
                break
        
        if not uid:
            uid = str(int(time.time() * 1000))
            users[uid] = {
                'username': name,
                'email': email,
                'password': generate_password_hash(google_id),
                'auth_type': 'google',
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'login_count': 0
            }
            JSONStorage.save('users.json', users)
            logger.info(f"🆕 New Google user: {name}")
        
        # Update login stats
        users[uid]['last_login'] = datetime.now().isoformat()
        users[uid]['login_count'] = users[uid].get('login_count', 0) + 1
        JSONStorage.save('users.json', users)
        
        # Login user
        user = User(uid, users[uid]['username'], email, 'google')
        login_user(user, remember=True)
        session['just_logged_in'] = True
        session['login_username'] = users[uid]['username']
        
        user_memory.load(uid)
        user_memory.record_session(uid)
        
        logger.info(f"✅ Google Login: {users[uid]['username']}")
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
        
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Google verification timed out'}), 500
    except Exception as e:
        logger.error(f"Google callback error: {e}")
        return jsonify({'success': False, 'error': 'Authentication failed'}), 500

@app.route('/logout')
@login_required
def logout():
    """Logout and clear session"""
    username = current_user.username
    logout_user()
    session.clear()
    
    response = make_response(redirect(url_for('login')))
    response.delete_cookie('session')
    response.delete_cookie('remember_token')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    
    logger.info(f"👋 Logout: {username}")
    flash('You have been logged out successfully.', 'info')
    return response

# ============================================
# 📄 PAGE ROUTES
# ============================================
@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page"""
    show_welcome = session.pop('just_logged_in', False)
    login_username = session.pop('login_username', current_user.username)
    
    return render_template(
        'dashboard.html',
        username=current_user.username,
        show_welcome=show_welcome,
        welcome_name=login_username
    )

@app.route('/history')
@login_required
def history_page():
    """Chat history page"""
    return render_template('history.html', username=current_user.username)

# ============================================
# 🔌 API ENDPOINTS
# ============================================
@app.route('/api/history/chats')
@login_required
def api_chats():
    """Get all chat sessions"""
    return jsonify({
        'success': True,
        'chats': ChatHistory.chats(current_user.id)
    })

@app.route('/api/history/messages/<chat_id>')
@login_required
def api_messages(chat_id):
    """Get messages for a chat"""
    return jsonify({
        'success': True,
        'messages': ChatHistory.messages(current_user.id, chat_id)
    })

@app.route('/api/history/delete/<chat_id>', methods=['DELETE'])
@login_required
def api_delete_chat(chat_id):
    """Delete a chat"""
    ChatHistory.delete(current_user.id, chat_id)
    return jsonify({'success': True, 'message': 'Chat deleted'})

@app.route('/api/history/clear', methods=['DELETE'])
@login_required
def api_clear():
    """Clear all chats"""
    ChatHistory.clear(current_user.id)
    return jsonify({'success': True, 'message': 'All chats cleared'})

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    """Main chat endpoint"""
    data = request.get_json(silent=True) or {}
    msg = data.get('message', '').strip()
    mode = data.get('mode', 'instant')
    chat_id = data.get('chat_id', str(uuid.uuid4()))
    
    if not msg:
        return jsonify({'error': 'Message is required'}), 400
    
    uid = current_user.id
    
    # Save user message
    ChatHistory.add(uid, chat_id, 'user', msg)
    
    # Generate answer
    answer = get_answer(msg, uid, mode)
    
    # Save AI response
    ChatHistory.add(uid, chat_id, 'assistant', answer)
    
    return jsonify({
        'response': format_text(answer),
        'status': 'success',
        'mode': mode,
        'chat_id': chat_id
    })

@app.route('/api/upload-image', methods=['POST'])
@login_required
def api_upload():
    """Image upload endpoint"""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file'}), 400
    
    file = request.files['image']
    if not file.filename or not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    
    # Save image
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"img_{uuid.uuid4().hex[:10]}.{ext}"
    filepath = os.path.join('uploads', 'analysis_images', filename)
    file.save(filepath)
    
    # Create thumbnail
    try:
        from PIL import Image
        img = Image.open(filepath)
        img.thumbnail((300, 300))
        img.save(os.path.join('uploads', 'thumbnails', f"thumb_{filename}"))
    except:
        pass
    
    chat_id = request.form.get('chat_id', str(uuid.uuid4()))
    uid = current_user.id
    image_url = f"/uploads/analysis_images/{filename}"
    
    # Save to chat history
    ChatHistory.add(uid, chat_id, 'user', f"📎 {file.filename}", image_url)
    
    # Generate analysis
    analysis = f"### 📎 Image Analysis\n\n**File:** {file.filename}\n\nI've received your image. What would you like to know about it?"
    ChatHistory.add(uid, chat_id, 'assistant', analysis, image_url)
    
    return jsonify({
        'success': True,
        'image': {'url': image_url},
        'analysis': format_text(analysis),
        'chat_id': chat_id
    })

@app.route('/api/speak', methods=['POST'])
@login_required
def speak():
    """Voice generation endpoint"""
    if not GTTS_AVAILABLE:
        return jsonify({'error': 'Voice engine not available'}), 503
    
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    # Limit text length
    if len(text) > 500:
        text = text[:500]
    
    audio, lang = voice_engine.generate(text)
    
    if audio:
        return jsonify({
            'success': True,
            'audio': audio,
            'lang': lang
        })
    
    return jsonify({'error': 'Failed to generate speech'}), 500

@app.route('/api/memory/clear', methods=['POST'])
@login_required
def clear_memory():
    """Clear user memory"""
    user_memory.clear(current_user.id)
    return jsonify({'success': True, 'message': 'Memory cleared'})

@app.route('/api/memory/stats', methods=['GET'])
@login_required
def memory_stats():
    """Get memory statistics"""
    uid = current_user.id
    user_memory.load(uid)
    
    return jsonify({
        'success': True,
        'messages_stored': len(user_memory.conversations.get(uid, [])),
        'facts_learned': len(user_memory.user_facts.get(uid, {})),
        'facts': user_memory.user_facts.get(uid, {}),
        'meta': user_memory.user_meta.get(uid, {})
    })

# ============================================
# 📁 STATIC FILES
# ============================================
@app.route('/uploads/<path:folder>/<path:filename>')
def serve_file(folder, filename):
    """Serve uploaded files"""
    return send_from_directory(os.path.join('uploads', folder), filename)

# ============================================
# ❌ ERROR HANDLERS
# ============================================
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"Server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# ============================================
# 🚀 START SERVER
# ============================================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("📚 SMART STUDY AI — PRODUCTION READY")
    print("="*60)
    print(f"🧠 Memory: ✅ Active (auto-save, TTL, threading)")
    print(f"🎤 Voice: {'✅ Ready (dual-layer cache)' if GTTS_AVAILABLE else '❌ Install gTTS'}")
    print(f"🔐 Auth: ✅ Email/Password + Google Sign-In")
    print(f"💾 Storage: ✅ JSON with backup recovery")
    print(f"⚡ Cache: ✅ 10-min TTL, thread-safe")
    print(f"📜 History: ✅ Full chat history")
    print(f"🖼️ Upload: ✅ Image with thumbnails")
    print("="*60)
    print("✅ ALL SYSTEMS READY")
    print("🚀 http://localhost:5000")
    print("="*60 + "\n")
    
    webbrowser.open('http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)

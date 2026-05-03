# ============================================
# SMART STUDY AI – ULTRA-FAST & STRONG MEMORY
# Sub‑second replies, instant voice, full logic
# STRONG AUTH – Unique emails, secure passwords
# ✅ ENHANCED LONG‑TERM MEMORY (remembers old chats)
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
    print("⚠️ python-dotenv not installed.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    logger.info("✅ gTTS Ready!")
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("⚠️ gTTS not installed.")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

for folder in ['voice_cache', 'analysis_images', 'thumbnails', 'chat_history', 'user_memory']:
    os.makedirs(f'uploads/{folder}', exist_ok=True)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ── Keys ──
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '277477438725-rij0soje78ekof9j00aade2j0k1042k3.apps.googleusercontent.com')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

# ⚡ Ultra‑fast cache
INSTANT_CACHE = {}
CACHE_TTL = 600
CACHE_LOCK = threading.Lock()

# ============================================
# 🧠 ENHANCED MEMORY SYSTEM (LONG‑TERM)
# ============================================
class UserMemory:
    """Advanced memory with permanent storage + retrieval from chat history"""
    
    def __init__(self):
        self.memory_dir = 'uploads/user_memory'
        self.conversations = {}   # uid -> list of messages
        self.user_facts = {}      # uid -> dict of learned facts
        self.user_meta = {}       # uid -> metadata & stats
        self.lock = threading.RLock()
        self.max_memory = 200      # ← increased from 50 (holds more recent context)
        # No TTL – memory persists forever (only trimmed by max_memory)

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
                    'total_sessions': 0,
                    'login_count': 0
                })
                logger.info(f"🧠 Memory loaded for user {uid}: {len(self.conversations[uid])} messages")
                return True
            except Exception as e:
                logger.warning(f"Memory load failed for {uid}: {e}")
                self.conversations[uid] = []
                self.user_facts[uid] = {}
                self.user_meta[uid] = {
                    'first_seen': time.time(),
                    'last_seen': time.time(),
                    'total_messages': 0,
                    'total_sessions': 0,
                    'login_count': 0
                }
                return False

    def save(self, uid):
        with self.lock:
            filepath = self._file(uid)
            try:
                data = {
                    'conversations': self.conversations.get(uid, []),
                    'facts': self.user_facts.get(uid, {}),
                    'meta': self.user_meta.get(uid, {})
                }
                if os.path.exists(filepath):
                    try:
                        os.replace(filepath, filepath + '.bak')
                    except:
                        pass
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                logger.error(f"Memory save failed for {uid}: {e}")
                return False

    def add_message(self, uid, role, content):
        with self.lock:
            if uid not in self.conversations:
                self.conversations[uid] = []
            
            self.conversations[uid].append({
                'role': role,
                'content': content[:500],
                'timestamp': time.time()
            })
            
            # Trim to max_memory (no time expiration)
            if len(self.conversations[uid]) > self.max_memory:
                self.conversations[uid] = self.conversations[uid][-self.max_memory:]
            
            if uid in self.user_meta:
                self.user_meta[uid]['last_seen'] = time.time()
                self.user_meta[uid]['total_messages'] += 1
            
            self.save(uid)

    def get_context(self, uid, count=8):   # ← more recent messages for context
        with self.lock:
            if uid not in self.conversations or not self.conversations[uid]:
                return ""
            recent = self.conversations[uid][-count:]
            lines = []
            for m in recent:
                role = "User" if m['role'] == 'user' else "Assistant"
                lines.append(f"{role}: {m['content'][:150]}")
            return "\n".join(lines)

    def get_full_context(self, uid):
        with self.lock:
            return {
                'conversation': self.get_context(uid, 8),
                'facts': self.get_facts(uid),
                'is_returning': self.user_meta.get(uid, {}).get('total_messages', 0) > 5,
                'total_messages': self.user_meta.get(uid, {}).get('total_messages', 0),
                'total_sessions': self.user_meta.get(uid, {}).get('total_sessions', 0)
            }

    def learn_fact(self, uid, key, value):
        with self.lock:
            if uid not in self.user_facts:
                self.user_facts[uid] = {}
            self.user_facts[uid][key] = value
        self.save(uid)

    def get_facts(self, uid):
        with self.lock:
            return self.user_facts.get(uid, {}).copy()

    def extract_facts(self, uid, message):
        msg = message.lower()
        # Name detection
        name_patterns = [
            r'(?:my name is|i am|i\'m|myself|naam|mai hu|mera naam|call me)\s+(\w+)',
        ]
        for p in name_patterns:
            m = re.search(p, msg)
            if m:
                self.learn_fact(uid, 'name', m.group(1).title())
                break
        
        # Interest detection (same as before)
        interests_map = {
            'coding': ['code', 'program', 'python', 'java', 'javascript', 'developer'],
            'music': ['song', 'music', 'singer', 'guitar', 'piano', 'listen'],
            'sports': ['cricket', 'football', 'game', 'player', 'match', 'ipl'],
            'movies': ['movie', 'film', 'actor', 'actress', 'bollywood', 'hollywood'],
            'reading': ['book', 'read', 'novel', 'author', 'story'],
            'travel': ['travel', 'trip', 'visit', 'place', 'ghoomna', 'tour'],
            'food': ['food', 'eat', 'pizza', 'biryani', 'cook', 'tasty'],
            'fitness': ['gym', 'exercise', 'workout', 'fitness', 'health', 'yoga'],
        }
        detected = []
        for interest, keywords in interests_map.items():
            if any(kw in msg for kw in keywords):
                detected.append(interest)
        if detected:
            current = self.user_facts.get(uid, {}).get('interests', [])
            for i in detected:
                if i not in current:
                    current.append(i)
            self.learn_fact(uid, 'interests', current[:8])

    def record_session(self, uid):
        with self.lock:
            if uid in self.user_meta:
                self.user_meta[uid]['total_sessions'] += 1
                self.user_meta[uid]['login_count'] += 1
                self.user_meta[uid]['last_seen'] = time.time()
        self.save(uid)

    def clear(self, uid):
        with self.lock:
            self.conversations[uid] = []
            self.user_facts[uid] = {}
            self.user_meta[uid] = {
                'first_seen': time.time(),
                'last_seen': time.time(),
                'total_messages': 0,
                'total_sessions': 0,
                'login_count': 0
            }
        fp = self._file(uid)
        if os.path.exists(fp):
            os.remove(fp)

user_memory = UserMemory()

# ============================================
# 🔍 LONG‑TERM HISTORY RETRIEVAL (NEW)
# ============================================
def retrieve_relevant_history(uid, query, top_k=3):
    """
    Search all past chat sessions (including old conversations) for messages
    that are semantically close to the current query using simple keyword overlap.
    Returns a formatted string of relevant past exchanges.
    """
    try:
        all_chats = ChatHistory.load(uid).get('chats', [])
    except:
        return ""
    
    query_words = set(query.lower().split())
    if not query_words:
        return ""
    
    scored = []
    for chat in all_chats:
        messages = chat.get('messages', [])
        # Walk through messages to find user→assistant pairs
        i = 0
        while i < len(messages) - 1:
            if messages[i].get('role') == 'user' and messages[i+1].get('role') == 'assistant':
                user_msg = messages[i].get('content', '')
                assistant_msg = messages[i+1].get('content', '')
                # Count common words between query and old user message
                user_words = set(user_msg.lower().split())
                overlap = len(query_words.intersection(user_words))
                if overlap > 0:
                    # Format nicely, limit length
                    context_str = f"User: {user_msg[:200]}\nAssistant: {assistant_msg[:200]}"
                    scored.append((overlap, context_str))
                i += 2
            else:
                i += 1
    
    # Sort by relevance (higher overlap first) and take top_k
    scored.sort(reverse=True, key=lambda x: x[0])
    if not scored:
        return ""
    
    relevant = [text for _, text in scored[:top_k]]
    return "\n\n---\n".join(relevant)

# ============================================
# 🎤 VOICE ENGINE (unchanged)
# ============================================
class VoiceEngine:
    def __init__(self):
        self.cache_dir = 'uploads/voice_cache'
        self.memory_cache = {}
        self.lock = threading.Lock()

    def detect_language(self, text):
        if not text: return 'en'
        hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
        total = len(text.replace(' ', ''))
        return 'hi' if (total > 0 and hindi_chars / total > 0.2) else 'en'

    def generate(self, text):
        if not text or not GTTS_AVAILABLE: return None, None
        clean = re.sub(r'<[^>]*>', '', text)
        clean = re.sub(r'[*_`#~]', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()[:500]
        if not clean: return None, None
        lang = self.detect_language(clean)
        cache_key = (clean, lang)
        with self.lock:
            if cache_key in self.memory_cache: return self.memory_cache[cache_key], lang
        hash_key = hashlib.md5(f"{clean}_{lang}".encode()).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{hash_key}.mp3")
        if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file) < 86400):
            with open(cache_file, 'rb') as f: audio = base64.b64encode(f.read()).decode()
            with self.lock: self.memory_cache[cache_key] = audio
            return audio, lang
        try:
            tts = gTTS(text=clean, lang=lang, tld='co.in' if lang == 'en' else None, slow=False)
            tts.save(cache_file)
            with open(cache_file, 'rb') as f: audio = base64.b64encode(f.read()).decode()
            with self.lock: self.memory_cache[cache_key] = audio
            return audio, lang
        except Exception as e:
            logger.error(f"Voice error: {e}")
            return None, None

voice_engine = VoiceEngine()

# ============================================
# JSON STORAGE
# ============================================
class JSONStorage:
    @staticmethod
    def load(filepath, default=None):
        if default is None: default = {}
        if not os.path.exists(filepath): return default
        try:
            with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default
    @staticmethod
    def save(filepath, data):
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except: return False

# ============================================
# CHAT HISTORY (persistent storage)
# ============================================
class ChatHistory:
    @staticmethod
    def file(uid): return os.path.join('uploads', 'chat_history', f'ch_{uid}.json')
    @staticmethod
    def load(uid):
        try: return json.load(open(ChatHistory.file(uid), 'r', encoding='utf-8'))
        except: return {"chats": []}
    @staticmethod
    def save(uid, d): json.dump(d, open(ChatHistory.file(uid), 'w', encoding='utf-8'), indent=2)
    @staticmethod
    def add(uid, cid, role, content, img=None):
        h = ChatHistory.load(uid)
        for c in h['chats']:
            if c['id'] == cid:
                c['messages'].append({'role': role, 'content': content, 'image_url': img, 'timestamp': datetime.now().isoformat()})
                c['updated_at'] = datetime.now().isoformat()
                ChatHistory.save(uid, h)
                return
        h['chats'].append({'id': cid, 'title': content[:50], 'created_at': datetime.now().isoformat(), 'updated_at': datetime.now().isoformat(), 'messages': [{'role': role, 'content': content, 'image_url': img, 'timestamp': datetime.now().isoformat()}]})
        ChatHistory.save(uid, h)
    @staticmethod
    def chats(uid):
        return sorted([{'id': c['id'], 'title': c.get('title', ''), 'updated_at': c.get('updated_at', ''), 'message_count': len(c.get('messages', []))} for c in ChatHistory.load(uid)['chats']], key=lambda x: x['updated_at'], reverse=True)
    @staticmethod
    def messages(uid, cid):
        for c in ChatHistory.load(uid)['chats']:
            if c['id'] == cid: return c.get('messages', [])
        return []
    @staticmethod
    def delete(uid, cid):
        h = ChatHistory.load(uid); h['chats'] = [c for c in h['chats'] if c['id'] != cid]; ChatHistory.save(uid, h)
    @staticmethod
    def clear(uid): ChatHistory.save(uid, {"chats": []})

# ============================================
# USER MODEL
# ============================================
class User(UserMixin):
    def __init__(self, uid, username, email, auth_type='email'):
        self.id = uid; self.username = username; self.email = email; self.auth_type = auth_type

@login_manager.user_loader
def load_user(uid):
    users = JSONStorage.load('users.json')
    if uid in users:
        u = users[uid]; return User(uid, u['username'], u['email'], u.get('auth_type', 'email'))
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_text(text):
    if not text: return ""
    text = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code class="language-\1">\2</code></pre>', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    return text.replace('\n', '<br>')

# ============================================
# ⚡ ULTRA-FAST ANSWER (with long‑term memory)
# ============================================
def save_memory_async(uid, query, answer):
    user_memory.add_message(uid, 'user', query)
    user_memory.add_message(uid, 'assistant', answer)
    user_memory.extract_facts(uid, query)

def get_answer(query, uid, mode='instant'):
    q = query.strip().lower()
    now = time.time()
    if uid not in user_memory.conversations:
        user_memory.load(uid)
    
    # 1. Check instant cache
    if mode == 'instant':
        with CACHE_LOCK:
            if q in INSTANT_CACHE and (now - INSTANT_CACHE[q][1] < CACHE_TTL):
                return INSTANT_CACHE[q][0]
    
    # 2. Get recent context from UserMemory (short term)
    full_ctx = user_memory.get_full_context(uid)
    recent_context = full_ctx['conversation']
    facts = full_ctx['facts']
    is_returning = full_ctx['is_returning']
    
    # 3. NEW: Retrieve relevant old conversations from full chat history
    long_term_memory = retrieve_relevant_history(uid, query, top_k=2)
    
    # Build system prompt with all memory sources
    system = "You are Smart Study AI. Be helpful and concise."
    if facts and 'name' in facts:
        system += f" User's name: {facts['name']}."
    if is_returning:
        system += " This is a returning user."
    
    # Add long‑term memory if available
    if long_term_memory:
        system += f"\n\nRelevant past conversations (use these to remember what we talked about before):\n{long_term_memory}"
    
    # Add recent context
    if recent_context:
        system += f"\n\nRecent conversation:\n{recent_context}"
    
    # Choose model based on mode
    if mode == 'instant':
        models = ["llama-3.1-8b-instant"]
        max_tokens, temp = 200, 0.3
    else:
        models = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
        max_tokens, temp = 2000, 0.4
    
    for model in models:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, 
                      "messages": [{"role": "system", "content": system}, 
                                   {"role": "user", "content": query}],
                      "temperature": temp, 
                      "max_tokens": max_tokens}, 
                timeout=15)
            if r.status_code == 200:
                data = r.json()
                if 'choices' in data and data['choices']:
                    answer = data['choices'][0]['message']['content']
                    if mode == 'instant':
                        with CACHE_LOCK:
                            INSTANT_CACHE[q] = (answer, now)
                    # Store in short-term memory asynchronously
                    threading.Thread(target=save_memory_async, args=(uid, query, answer), daemon=True).start()
                    return answer
        except Exception as e:
            logger.error(f"Groq error with {model}: {e}")
            continue
    
    return "I'm here! Ask me anything. 😊"

# ============================================
# 🔐 STRONG AUTH ROUTES (unchanged)
# ============================================
@app.route('/')
def index():
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        if not password:
            flash('Please enter your password.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        if '@' not in email or '.' not in email:
            flash('Please enter a valid email address.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        
        users = JSONStorage.load('users.json')
        found = None
        for uid, u in users.items():
            if u.get('email', '').lower() == email:
                found = (uid, u)
                break
        
        if not found:
            flash('No account found with this email. Please register first.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        
        uid, u = found
        if not check_password_hash(u.get('password', ''), password):
            flash('Incorrect password. Please try again.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        
        user = User(uid, u['username'], u['email'], u.get('auth_type', 'email'))
        login_user(user, remember=True)
        session['just_logged_in'] = True
        session['login_username'] = u['username']
        
        user_memory.load(uid)
        user_memory.record_session(uid)
        
        logger.info(f"✅ Login: {u['username']} ({email})")
        return redirect(url_for('dashboard'))
    
    return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        errors = []
        if not username:
            errors.append('Username is required.')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif len(username) > 30:
            errors.append('Username must be less than 30 characters.')
        elif not re.match(r'^[a-zA-Z0-9_ ]+$', username):
            errors.append('Username can only contain letters, numbers, spaces, and underscores.')
        
        if not email:
            errors.append('Email is required.')
        elif '@' not in email or '.' not in email:
            errors.append('Please enter a valid email address.')
        
        if not password:
            errors.append('Password is required.')
        elif len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        elif len(password) > 128:
            errors.append('Password is too long.')
        
        if errors:
            for e in errors: flash(e, 'error')
            return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)
        
        users = JSONStorage.load('users.json')
        if any(u.get('email', '').lower() == email for u in users.values()):
            flash('An account with this email already exists. Please login instead.', 'error')
            return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)
        
        uid = str(int(time.time() * 1000))
        users[uid] = {
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'auth_type': 'email',
            'created_at': datetime.now().isoformat()
        }
        
        if JSONStorage.save('users.json', users):
            logger.info(f"🆕 New user: {username} ({email})")
            flash('✅ Account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('❌ Registration failed. Please try again.', 'error')
    
    return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/api/google-callback', methods=['POST'])
def google_callback():
    data = request.get_json(silent=True) or {}
    credential = data.get('credential', '')
    if not credential: return jsonify({'success': False, 'error': 'No credential'}), 400
    try:
        vr = requests.get(f'https://oauth2.googleapis.com/tokeninfo?id_token={credential}', timeout=10)
        if vr.status_code != 200: return jsonify({'success': False, 'error': 'Invalid token'}), 400
        ud = vr.json()
        if ud.get('aud') != GOOGLE_CLIENT_ID: return jsonify({'success': False, 'error': 'Wrong client'}), 400
        email = ud.get('email', '').lower()
        if not email: return jsonify({'success': False, 'error': 'No email'}), 400
        users = JSONStorage.load('users.json')
        uid = next((k for k, v in users.items() if v.get('email', '').lower() == email), None)
        if not uid:
            uid = str(int(time.time() * 1000))
            users[uid] = {'username': ud.get('name', email.split('@')[0]), 'email': email, 'password': generate_password_hash(ud.get('sub', '')), 'auth_type': 'google', 'created_at': datetime.now().isoformat()}
            JSONStorage.save('users.json', users)
        login_user(User(uid, users[uid]['username'], email, 'google'), remember=True)
        session['just_logged_in'] = True
        session['login_username'] = users[uid]['username']
        user_memory.load(uid)
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
    except Exception as e:
        logger.error(f"Google error: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/logout')
@login_required
def logout():
    username = current_user.username
    logout_user(); session.clear()
    resp = make_response(redirect(url_for('login')))
    resp.delete_cookie('session'); resp.delete_cookie('remember_token')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    logger.info(f"👋 Logout: {username}")
    return resp

@app.route('/dashboard')
@login_required
def dashboard():
    show_welcome = session.pop('just_logged_in', False)
    login_username = session.pop('login_username', current_user.username)
    return render_template('dashboard.html', username=current_user.username, show_welcome=show_welcome, welcome_name=login_username)

@app.route('/history')
@login_required
def history_page():
    return render_template('history.html', username=current_user.username)

# ── API ──
@app.route('/api/history/chats')
@login_required
def api_chats():
    return jsonify({'success': True, 'chats': ChatHistory.chats(current_user.id)})

@app.route('/api/history/messages/<chat_id>')
@login_required
def api_messages(chat_id):
    return jsonify({'success': True, 'messages': ChatHistory.messages(current_user.id, chat_id)})

@app.route('/api/history/delete/<chat_id>', methods=['DELETE'])
@login_required
def api_delete_chat(chat_id):
    ChatHistory.delete(current_user.id, chat_id)
    return jsonify({'success': True})

@app.route('/api/history/clear', methods=['DELETE'])
@login_required
def api_clear():
    ChatHistory.clear(current_user.id)
    return jsonify({'success': True})

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    msg = data.get('message', '').strip()
    mode = data.get('mode', 'instant')
    chat_id = data.get('chat_id', str(uuid.uuid4()))
    if not msg: return jsonify({'error': 'Message required'}), 400
    uid = current_user.id
    ChatHistory.add(uid, chat_id, 'user', msg)
    answer = get_answer(msg, uid, mode)
    ChatHistory.add(uid, chat_id, 'assistant', answer)
    return jsonify({'response': format_text(answer), 'status': 'success', 'mode': mode, 'chat_id': chat_id})

@app.route('/api/upload-image', methods=['POST'])
@login_required
def api_upload():
    if 'image' not in request.files: return jsonify({'success': False}), 400
    file = request.files['image']
    if not file.filename or not allowed_file(file.filename): return jsonify({'success': False}), 400
    ext = file.filename.rsplit('.', 1)[1].lower()
    fn = f"img_{uuid.uuid4().hex[:10]}.{ext}"; fp = os.path.join('uploads', 'analysis_images', fn)
    file.save(fp)
    try:
        from PIL import Image; img = Image.open(fp); img.thumbnail((300, 300)); img.save(os.path.join('uploads', 'thumbnails', f"thumb_{fn}"))
    except: pass
    chat_id = request.form.get('chat_id', str(uuid.uuid4())); uid = current_user.id; img_url = f"/uploads/analysis_images/{fn}"
    ChatHistory.add(uid, chat_id, 'user', f"📎 {file.filename}", img_url)
    analysis = "### 📎 Image Analysis\n\nImage received. What would you like to know?"
    ChatHistory.add(uid, chat_id, 'assistant', analysis, img_url)
    return jsonify({'success': True, 'image': {'url': img_url}, 'analysis': format_text(analysis), 'chat_id': chat_id})

@app.route('/api/speak', methods=['POST'])
@login_required
def speak():
    if not GTTS_AVAILABLE: return jsonify({'error': 'Voice not available'}), 503
    data = request.get_json(silent=True) or {}
    text = data.get('text', '').strip()[:500]
    if not text: return jsonify({'error': 'No text'}), 400
    audio, lang = voice_engine.generate(text)
    if audio: return jsonify({'success': True, 'audio': audio, 'lang': lang})
    return jsonify({'error': 'Failed to generate'}), 500

@app.route('/api/memory/clear', methods=['POST'])
@login_required
def clear_memory():
    user_memory.clear(current_user.id)
    return jsonify({'success': True})

@app.route('/api/memory/stats', methods=['GET'])
@login_required
def memory_stats():
    uid = current_user.id; user_memory.load(uid)
    return jsonify({'success': True, 'messages_stored': len(user_memory.conversations.get(uid, [])), 'facts_learned': len(user_memory.user_facts.get(uid, {})), 'facts': user_memory.user_facts.get(uid, {})})

@app.route('/uploads/<path:folder>/<path:filename>')
def serve_file(folder, filename):
    return send_from_directory(os.path.join('uploads', folder), filename)

@app.errorhandler(404)
def not_found(e):
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

if __name__ == '__main__':
    print("\n" + "="*60)
    print("📚 SMART STUDY AI – STRONG MEMORY & AUTH (LONG‑TERM CHAT MEMORY)")
    print("="*60)
    print(f"🧠 Memory: ✅ Enhanced with long‑term retrieval from all past chats")
    print(f"🎤 Voice: {'✅ Ready' if GTTS_AVAILABLE else '❌'}")
    print(f"🔐 Auth: ✅ Unique emails, strong validation")
    print("🚀 http://localhost:5000")
    print("="*60 + "\n")
    webbrowser.open('http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)
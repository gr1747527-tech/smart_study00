# ============================================
# SMART STUDY AI – ULTIMATE ROBUST BACKEND
# Sub‑second replies, instant voice, full logic
# ============================================
import os, logging, hashlib, time, threading
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, send_from_directory, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests, re, base64, json, webbrowser, uuid

# ✅ LOAD .env FILE
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ .env loaded successfully!")
except ImportError:
    print("⚠️ python-dotenv not installed. Run: pip install python-dotenv")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    logger.info("✅ gTTS Ready!")
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("⚠️ gTTS not installed. Voice disabled. Run: pip install gTTS")

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

# ✅ API KEYS — NOW FROM .env (with fallback)
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '277477438725-rij0soje78ekof9j00aade2j0k1042k3.apps.googleusercontent.com')

# ✅ DEBUG: Print to verify keys are loaded
print(f"🔑 GROQ_API_KEY loaded: {'✅ Yes' if GROQ_API_KEY else '❌ No'}")
print(f"🔑 GOOGLE_CLIENT_ID loaded: {'✅ Yes' if GOOGLE_CLIENT_ID else '❌ No'}")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

# ⚡ Rest of your code remains EXACTLY the same below this line...
# (Instant cache, VoiceEngine, JSONStorage, ChatHistory, User, routes, etc.)

# ⚡ Instant answer cache (thread‑safe)
INSTANT_CACHE = {}
CACHE_TTL = 300
CACHE_LOCK = threading.Lock()

# ============================================
# 🎤 VOICE ENGINE (cached, language‑aware)
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
            if cache_key in self.memory_cache:
                return self.memory_cache[cache_key], lang

        hash_key = hashlib.md5(f"{clean}_{lang}".encode()).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{hash_key}.mp3")
        if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file) < 86400):
            with open(cache_file, 'rb') as f:
                audio = base64.b64encode(f.read()).decode()
            with self.lock:
                self.memory_cache[cache_key] = audio
            return audio, lang

        try:
            tts = gTTS(text=clean, lang=lang, tld='co.in' if lang == 'en' else None, slow=False)
            tts.save(cache_file)
            with open(cache_file, 'rb') as f:
                audio = base64.b64encode(f.read()).decode()
            with self.lock:
                self.memory_cache[cache_key] = audio
            return audio, lang
        except Exception as e:
            logger.error(f"Voice error: {e}")
            return None, None

voice_engine = VoiceEngine()

# ============================================
# JSON STORAGE & CHAT HISTORY (unchanged)
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
                ChatHistory.save(uid, h); return
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
# ⚡ ULTRA‑FAST ANSWER ENGINE (cached, multi‑model)
# ============================================
def get_answer(query, uid, mode='instant'):
    q = query.strip().lower()
    now = time.time()
    if mode == 'instant':
        with CACHE_LOCK:
            if q in INSTANT_CACHE and (now - INSTANT_CACHE[q][1] < CACHE_TTL):
                return INSTANT_CACHE[q][0]

    system = "You are Smart Study AI, a fast learning assistant for students created by Govind Singh Rajput. Be helpful, accurate, and concise."
    if mode == 'instant':
        models = ["llama-3.1-8b-instant", "mixtral-8x7b-32768"]
        max_tokens, temp = 400, 0.5
    else:
        models = ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
        max_tokens, temp = 2000, 0.4

    for model in models:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": query}],
                "temperature": temp, "max_tokens": max_tokens}, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if 'choices' in data and data['choices']:
                    answer = data['choices'][0]['message']['content']
                    if mode == 'instant':
                        with CACHE_LOCK: INSTANT_CACHE[q] = (answer, now)
                    return answer
        except Exception as e: logger.warning(f"Model {model} failed: {e}")

    fallback = "I'm here to help! Try rephrasing your question."
    if mode == 'instant':
        with CACHE_LOCK: INSTANT_CACHE[q] = (fallback, now)
    return fallback

# ============================================
# ROUTES (Login/Register/Google/Logout same as before)
# ============================================
@app.route('/')
def index():
    return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Please fill all fields.', 'error')
            return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)
        users = JSONStorage.load('users.json')
        for uid, u in users.items():
            if u.get('email', '').lower() == email and check_password_hash(u.get('password', ''), password):
                user = User(uid, u['username'], u['email'], u.get('auth_type', 'email'))
                login_user(user, remember=True)
                session['just_logged_in'] = True
                session['login_username'] = u['username']
                return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        errs = []
        if not username: errs.append('Username is required.')
        if not email: errs.append('Email is required.')
        if not password: errs.append('Password is required.')
        elif len(password) < 6: errs.append('Password must be at least 6 characters.')
        if errs:
            for e in errs: flash(e, 'error')
            return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)
        users = JSONStorage.load('users.json')
        if any(u.get('email', '').lower() == email for u in users.values()):
            flash('Email already registered.', 'error')
            return render_template('register.html', google_client_id=GOOGLE_CLIENT_ID)
        uid = str(int(time.time()))
        users[uid] = {'username': username, 'email': email, 'password': generate_password_hash(password), 'auth_type': 'email', 'created_at': datetime.now().isoformat()}
        JSONStorage.save('users.json', users)
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
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
            uid = str(int(time.time()))
            users[uid] = {'username': ud.get('name', email.split('@')[0]), 'email': email, 'password': generate_password_hash(ud.get('sub', '')), 'auth_type': 'google', 'created_at': datetime.now().isoformat()}
            JSONStorage.save('users.json', users)
        login_user(User(uid, users[uid]['username'], email, 'google'), remember=True)
        session['just_logged_in'] = True
        session['login_username'] = users[uid]['username']
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
def api_chats(): return jsonify({'success': True, 'chats': ChatHistory.chats(current_user.id)})

@app.route('/api/history/messages/<chat_id>')
@login_required
def api_messages(chat_id): return jsonify({'success': True, 'messages': ChatHistory.messages(current_user.id, chat_id)})

@app.route('/api/history/delete/<chat_id>', methods=['DELETE'])
@login_required
def api_delete_chat(chat_id): ChatHistory.delete(current_user.id, chat_id); return jsonify({'success': True})

@app.route('/api/history/clear', methods=['DELETE'])
@login_required
def api_clear(): ChatHistory.clear(current_user.id); return jsonify({'success': True})

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

@app.route('/uploads/<path:folder>/<path:filename>')
def serve_file(folder, filename): return send_from_directory(os.path.join('uploads', folder), filename)

@app.errorhandler(404)
def not_found(e): return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

if __name__ == '__main__':
    print("\n📚 SMART STUDY AI – ULTIMATE BACKEND\n" + "="*60)
    webbrowser.open('http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)
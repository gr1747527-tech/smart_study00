import os
import json
import re
import math
import random
import requests
import logging

logger = logging.getLogger(__name__)

class SmartAIEngine:
    """
    Advanced Multi-Domain AI Engine for Smart Study
    Provides intelligent answers for:
    - Coding & DSA (Python, JS, C++, Java, SQL, Web)
    - Mathematics (Calculus, Algebra, Arithmetic, Trigonometry)
    - Science (Physics, Chemistry, Biology)
    - Concept Explanations & Study Notes
    - Quizzes, Flashcards & Practice questions
    - Multilingual support (Hindi, Hinglish, English)
    - Fallback Free AI Provider (zero API key needed)
    """

    def __init__(self, kb_path=None):
        if kb_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            kb_path = os.path.join(base_dir, 'data', 'knowledge_base.json')
        self.kb_path = kb_path
        self.knowledge = {}
        self.load_knowledge_base()

    def load_knowledge_base(self):
        """Safely load domain knowledge base"""
        try:
            if os.path.exists(self.kb_path):
                with open(self.kb_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        self.knowledge = json.loads(content)
                        logger.info(f"Loaded knowledge base with {len(self.knowledge)} domains")
                        return
        except Exception as e:
            logger.warning(f"Knowledge base load error: {e}")
        self.knowledge = {}

    def detect_language(self, text):
        """Detect English, Hindi or Hinglish"""
        if not text:
            return 'english'
        # Devanagari script detection
        if any('\u0900' <= char <= '\u097f' for char in text):
            return 'hindi'
        # Hinglish indicators
        hinglish_words = [
            'kya', 'kaise', 'hai', 'batao', 'samjhao', 'padhao', 'kare', 'kyun', 'kab',
            'hoga', 'mera', 'meri', 'naam', 'kripya', 'shukriya', 'theek', 'padhai',
            'kavita', 'kahani', 'sunao', 'bnao', 'karo', 'mujhe', 'sikhna'
        ]
        words = text.lower().split()
        if any(w in words for w in hinglish_words):
            return 'hinglish'
        return 'english'

    def detect_intention(self, text):
        """Analyze intent of the user message"""
        msg = text.lower().strip()
        
        # Greeting
        if any(w in msg for w in ['hello', 'hi', 'hey', 'namaste', 'नमस्ते', 'pranam', 'good morning', 'good evening', 'who are you', 'kaun ho']):
            return 'greeting'
        
        # Quiz / Practice
        if any(w in msg for w in ['quiz', 'test', 'question', 'practice', 'flashcard', 'mock test', 'prashna', 'mcq']):
            return 'quiz'
            
        # Math & Numerical expressions
        math_ops = ['+', '-', '*', '/', '^', '%', 'sqrt', 'sin', 'cos', 'tan', 'derivative', 'integral', 'solve', 'calculate', 'hisab', 'solve karo']
        if (any(c.isdigit() for c in msg) and any(op in msg for op in ['+', '-', '*', '/', '=', 'solve', 'calculate', 'root', 'square'])) or \
           any(w in msg for w in ['derivative', 'integration', 'matrix', 'quadratic', 'trigonometry', 'sin(', 'cos(']):
            return 'math'
            
        # Coding & Technical
        code_keywords = [
            'code', 'program', 'python', 'javascript', 'java', 'c++', 'html', 'css', 'sql',
            'function', 'algorithm', 'sort', 'array', 'loop', 'class', 'debug', 'script',
            'react', 'flask', 'django', 'api', 'database', 'stack', 'queue', 'tree', 'graph',
            'dsa', 'recursion', 'binary search', 'linked list'
        ]
        if any(w in msg for w in code_keywords):
            return 'coding'
            
        # Study plan / Tips
        if any(w in msg for w in ['timetable', 'study plan', 'tips', 'strategy', 'how to study', 'focus', 'exam prep', 'padhai kaise']):
            return 'study_tips'
            
        # Creative / Poetry / Story
        if any(w in msg for w in ['poem', 'poetry', 'kavita', 'कविता', 'story', 'kahani', 'shayari', 'गीत', 'joke', 'chutkula']):
            return 'creative'
            
        # Educational Concept
        if any(w in msg for w in ['what is', 'explain', 'define', 'difference between', 'kya hai', 'samjhao', 'batao', 'law', 'theory', 'notes']):
            return 'concept'
            
        return 'general'

    def generate_response(self, message, mode='instant', user_name=None, context=""):
        """Main entry point to generate an intelligent AI response"""
        msg = message.strip()
        lang = self.detect_language(msg)
        intent = self.detect_intention(msg)

        # 1. Try Free Public Open AI Endpoint first for dynamic real-time reasoning
        open_ai_res = self._query_free_ai_network(msg, mode, user_name, context)
        if open_ai_res:
            return open_ai_res

        # 2. Robust Built-in Knowledge & Reasoning Engine
        if intent == 'greeting':
            return self._handle_greeting(lang, user_name)
        elif intent == 'math':
            return self._solve_math(msg, lang)
        elif intent == 'coding':
            return self._handle_coding(msg, lang, mode)
        elif intent == 'quiz':
            return self._generate_quiz(msg, lang)
        elif intent == 'study_tips':
            return self._study_tips(lang)
        elif intent == 'creative':
            return self._generate_creative(msg, lang)
        elif intent == 'concept':
            res = self._handle_concept(msg, lang, mode)
            if res:
                return res
        
        # General search in knowledge base or synthesis
        return self._synthesize_general_answer(msg, lang, mode, user_name)

    def _query_free_ai_network(self, message, mode, user_name=None, context=""):
        """Query free public AI endpoints with robust timeout handling"""
        # Try Pollinations Text AI (free, no-key, very fast and powerful)
        try:
            system_prompt = (
                "You are Smart Study AI, an intelligent, inspiring, and expert educational tutor and assistant. "
                "Provide accurate, clearly structured, well-formatted Markdown answers. Use headings, bullet points, and code blocks where helpful. "
            )
            if user_name:
                system_prompt += f"The student's name is {user_name}. "
            if mode == 'expert':
                system_prompt += "Provide an in-depth, thorough, step-by-step master explanation with examples and key takeaways. "
            else:
                system_prompt += "Provide a clear, direct, and easy-to-understand concise answer. "

            messages = [
                {"role": "system", "content": system_prompt}
            ]
            if context:
                messages.append({"role": "system", "content": f"Recent conversation context:\n{context[:300]}"})
            messages.append({"role": "user", "content": message})

            url = "https://text.pollinations.ai/"
            payload = {
                "messages": messages,
                "model": "openai",
                "seed": random.randint(1, 10000),
                "jsonMode": False
            }
            res = requests.post(url, json=payload, timeout=7)
            if res.status_code == 200 and len(res.text.strip()) > 10:
                return res.text.strip()
        except Exception as e:
            logger.debug(f"Free AI network probe exception: {e}")

        return None

    def _handle_greeting(self, lang, user_name=None):
        name_str = f", {user_name}" if user_name else ""
        if lang == 'hindi':
            return (
                f"### 🙏 नमस्ते{name_str}!\n\n"
                "मैं **Smart Study AI** हूँ — आपका 24x7 निजी अध्ययन और कोडिंग सहायक! 📚✨\n\n"
                "**मैं आपकी इन चीज़ों में मदद कर सकता हूँ:**\n"
                "- 💻 **प्रोग्रामिंग व कोडिंग:** Python, JavaScript, C++, Java, Web, DSA\n"
                "- 🧮 **गणित व विज्ञान:** स्टेप-बाय-स्टेप हल, सूत्र, भौतिकी, रसायन, जीवविज्ञान\n"
                "- 📖 **कॉन्सेप्ट एक्सप्लेनेशन:** किसी भी विषय के नोट्स व सरल भाषा में व्याख्या\n"
                "- 🎯 **क्विज़ व मॉक टेस्ट:** आपकी तैयारी जांचने के लिए प्रश्न\n\n"
                "आज आप क्या सीखना या पूछना चाहते हैं? 🚀"
            )
        elif lang == 'hinglish':
            return (
                f"### 👋 Hey{name_str}! Welcome to Smart Study AI! 🚀\n\n"
                "Main aapka personal AI Study Buddy hoon! Padhai, coding ya kisi bhi subject me doubt ho toh bina hichkichaaye puchiye.\n\n"
                "**Aap mujhse pooch sakte hain:**\n"
                "- 🐍 *Python ya Web Development ke codes aur projects*\n"
                "- 📐 *Math equations aur complex numerical problems*\n"
                "- ⚛️ *Physics, Chemistry aur Biology ke concepts*\n"
                "- 📝 *Exam notes, study plans aur quick revisions*\n\n"
                "Bataiye, aaj hum kya shuru karein? 💡"
            )
        else:
            return (
                f"### 👋 Hello{name_str}! Welcome to Smart Study AI! 📚✨\n\n"
                "I am your all-in-one AI study companion and programming mentor, ready to help you excel.\n\n"
                "**How I can assist you today:**\n"
                "- 💻 **Coding & DSA:** Clean code snippets, debugging, and algorithms in Python, JS, C++, etc.\n"
                "- 🧮 **Math & Science:** Step-by-step solutions, physics formulas, and chemistry equations.\n"
                "- 📖 **Concept Mastery:** In-depth breakdowns, notes, and intuitive analogies.\n"
                "- 🎯 **Quizzes & Tests:** Test your knowledge on any topic.\n\n"
                "What would you like to explore today? Type your question or topic below! 🚀"
            )

    def _solve_math(self, query, lang):
        """Mathematical solver with step-by-step logic"""
        clean_q = query.lower().replace('solve', '').replace('calculate', '').replace('what is', '').replace('karo', '').strip()
        
        # Check for simple arithmetic evaluation
        simple_expr_match = re.search(r'[\d\.\s\+\-\*\/\^\(\)\%]+', clean_q)
        if simple_expr_match:
            expr = simple_expr_match.group(0).strip()
            # Clean power operator
            eval_expr = expr.replace('^', '**')
            # Security check: only allow digits and math symbols
            if re.match(r'^[\d\.\s\+\-\*\/\(\)\%]+$', eval_expr) and len(eval_expr) >= 3:
                try:
                    result = eval(eval_expr, {"__builtins__": None}, {"math": math})
                    if isinstance(result, float):
                        result = round(result, 6)
                        if result.is_integer():
                            result = int(result)
                    
                    if lang in ['hindi', 'hinglish']:
                        return (
                            f"### 🧮 गणितीय समाधान (Math Solution)\n\n"
                            f"**दिया गया समीकरण:** `{expr}`\n\n"
                            f"**उत्तर (Result):** `{result}`\n\n"
                            f"**चरण-दर-चरण व्याख्या (Steps):**\n"
                            f"1. संक्रिया (Operation): `{expr}` का मान ज्ञात किया गया।\n"
                            f"2. BODMAS/PEMDAS नियम के अनुसार कोष्ठक, गुणा/भाग और जोड़/घटाव किया गया।\n"
                            f"3. अंतिम मान = **`{result}`**"
                        )
                    else:
                        return (
                            f"### 🧮 Mathematical Solution\n\n"
                            f"**Expression:** `{expr}`\n\n"
                            f"**Final Answer:** `{result}`\n\n"
                            f"**Step-by-Step Breakdown:**\n"
                            f"1. **Input:** Evaluated the expression `{expr}`.\n"
                            f"2. **Order of Operations (PEMDAS/BODMAS):** Evaluated parentheses, exponents, multiplication/division, and addition/subtraction.\n"
                            f"3. **Result:** **`{result}`**"
                        )
                except Exception:
                    pass

        # Check for Quadratic / Derivative / Algebra matches
        if 'quadratic' in clean_q or re.search(r'x\^2|x\*x', clean_q):
            return (
                "### 📐 Quadratic Equation Solver\n\n"
                "Standard Form: $ax^2 + bx + c = 0$\n\n"
                "**Quadratic Formula:**\n"
                "$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\n"
                "**Key Concepts:**\n"
                "- **Discriminant ($D = b^2 - 4ac$):**\n"
                "  - $D > 0$: Two distinct real roots\n"
                "  - $D = 0$: Two equal real roots ($x = -b/2a$)\n"
                "  - $D < 0$: Complex / imaginary roots\n\n"
                "**Example:** Solve $x^2 - 5x + 6 = 0$\n"
                "- Here $a=1, b=-5, c=6$\n"
                "- $D = (-5)^2 - 4(1)(6) = 25 - 24 = 1$\n"
                "- $x = \\frac{5 \\pm \\sqrt{1}}{2} \\implies x = 3, x = 2$"
            )

        if 'derivative' in clean_q or 'differentiation' in clean_q:
            return (
                "### 📈 Calculus: Derivative Rules & Formulas\n\n"
                "**Fundamental Rules:**\n"
                "- **Power Rule:** $\\frac{d}{dx}[x^n] = n x^{n-1}$\n"
                "- **Product Rule:** $\\frac{d}{dx}[u \\cdot v] = u'v + uv'$\n"
                "- **Quotient Rule:** $\\frac{d}{dx}\\left[\\frac{u}{v}\\right] = \\frac{u'v - uv'}{v^2}$\n"
                "- **Chain Rule:** $\\frac{d}{dx}[f(g(x))] = f'(g(x)) \\cdot g'(x)$\n\n"
                "**Trigonometric Derivatives:**\n"
                "- $\\frac{d}{dx}(\\sin x) = \\cos x$\n"
                "- $\\frac{d}{dx}(\\cos x) = -\\sin x$\n"
                "- $\\frac{d}{dx}(\\tan x) = \\sec^2 x$\n"
                "- $\\frac{d}{dx}(e^x) = e^x, \\quad \\frac{d}{dx}(\\ln x) = \\frac{1}{x}$"
            )

        # Default helpful math guide
        return (
            "### 🧮 Math Assistant\n\n"
            "I can help solve arithmetic, algebra, trigonometry, and calculus! You can type:\n"
            "- Arithmetic: `25 * 4 + 100` or `sqrt(144)`\n"
            "- Quadratic: `solve x^2 - 5x + 6 = 0`\n"
            "- Derivatives & Integrals: `derivative of sin(x) * x^2`\n"
            "- Trigonometry formulas and identities\n\n"
            "Please share your specific problem!"
        )

    def _handle_coding(self, query, lang, mode):
        """Generates comprehensive code with explanations"""
        q = query.lower()
        
        # Detect language
        target_lang = 'python'
        if 'javascript' in q or ' js' in q or 'node' in q:
            target_lang = 'javascript'
        elif 'c++' in q or 'cpp' in q:
            target_lang = 'cpp'
        elif 'java' in q and 'javascript' not in q:
            target_lang = 'java'
        elif 'html' in q or 'css' in q:
            target_lang = 'html'
        elif 'sql' in q or 'database' in q or 'query' in q:
            target_lang = 'sql'

        # Sorting algorithms
        if 'sort' in q:
            if target_lang == 'python':
                code = (
                    "def quick_sort(arr):\n"
                    "    \"\"\"Quick Sort Algorithm - O(n log n) average\"\"\"\n"
                    "    if len(arr) <= 1:\n"
                    "        return arr\n"
                    "    pivot = arr[len(arr) // 2]\n"
                    "    left = [x for x in arr if x < pivot]\n"
                    "    middle = [x for x in arr if x == pivot]\n"
                    "    right = [x for x in arr if x > pivot]\n"
                    "    return quick_sort(left) + middle + quick_sort(right)\n\n"
                    "# Example Usage\n"
                    "numbers = [64, 34, 25, 12, 22, 11, 90]\n"
                    "sorted_numbers = quick_sort(numbers)\n"
                    "print('Sorted Array:', sorted_numbers)"
                )
            elif target_lang == 'javascript':
                code = (
                    "function quickSort(arr) {\n"
                    "    if (arr.length <= 1) return arr;\n"
                    "    const pivot = arr[Math.floor(arr.length / 2)];\n"
                    "    const left = arr.filter(x => x < pivot);\n"
                    "    const middle = arr.filter(x => x === pivot);\n"
                    "    const right = arr.filter(x => x > pivot);\n"
                    "    return [...quickSort(left), ...middle, ...quickSort(right)];\n"
                    "}\n\n"
                    "const numbers = [64, 34, 25, 12, 22, 11, 90];\n"
                    "console.log('Sorted:', quickSort(numbers));"
                )
            else:
                code = (
                    "// Quick Sort Example\n"
                    "void quickSort(int arr[], int low, int high) {\n"
                    "    if (low < high) {\n"
                    "        int pi = partition(arr, low, high);\n"
                    "        quickSort(arr, low, pi - 1);\n"
                    "        quickSort(arr, pi + 1, high);\n"
                    "    }\n"
                    "}"
                )

            return (
                f"### 🚀 Quick Sort in {target_lang.title()}\n\n"
                f"**Concept:** Quick Sort is an efficient **Divide and Conquer** algorithm that picks an element as a pivot and partitions the array around it.\n\n"
                f"```{target_lang}\n{code}\n```\n\n"
                f"**Complexity Analysis:**\n"
                f"- **Time Complexity:** Average: `O(n log n)`, Worst Case: `O(n²)`\n"
                f"- **Space Complexity:** `O(log n)` call stack\n\n"
                f"💡 **Tip:** In Python, the built-in `.sort()` uses **Timsort** (hybrid of Merge & Insertion Sort) with `O(n log n)` performance."
            )

        # Fibonacci / Recursion
        if 'fibonacci' in q:
            code = (
                "def fibonacci_dp(n):\n"
                "    \"\"\"Optimized Fibonacci using Dynamic Programming - O(n) time, O(1) space\"\"\"\n"
                "    if n <= 0: return 0\n"
                "    if n == 1: return 1\n"
                "    prev2, prev1 = 0, 1\n"
                "    for _ in range(2, n + 1):\n"
                "        curr = prev1 + prev2\n"
                "        prev2 = prev1\n"
                "        prev1 = curr\n"
                "    return prev1\n\n"
                "print([fibonacci_dp(i) for i in range(10)])\n"
                "# Output: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]"
            )
            return (
                "### 🔢 Fibonacci Sequence (Optimized)\n\n"
                "The Fibonacci sequence begins: $0, 1, 1, 2, 3, 5, 8, 13, \\dots$ where $F(n) = F(n-1) + F(n-2)$.\n\n"
                f"```python\n{code}\n```\n\n"
                "- **Time Complexity:** `O(n)`\n"
                "- **Space Complexity:** `O(1)` space optimization"
            )

        # Web / API / Flask
        if 'flask' in q or 'api' in q:
            code = (
                "from flask import Flask, jsonify, request\n\n"
                "app = Flask(__name__)\n\n"
                "@app.route('/api/greet', methods=['GET'])\n"
                "def greet():\n"
                "    name = request.args.get('name', 'Learner')\n"
                "    return jsonify({'message': f'Hello, {name}!', 'status': 'success'})\n\n"
                "if __name__ == '__main__':\n"
                "    app.run(port=5000, debug=True)"
            )
            return (
                "### 🌐 REST API Example with Flask\n\n"
                "Here is a clean RESTful API endpoint using Flask in Python:\n\n"
                f"```python\n{code}\n```\n\n"
                "**How to test:**\n"
                "1. Run `python app.py`\n"
                "2. Visit `http://localhost:5000/api/greet?name=Govind` in your browser."
            )

        # General programming starter
        return (
            f"### 💻 {target_lang.title()} Programming Guide\n\n"
            f"Here is a clean, structured example demonstrating essential concepts in **{target_lang.title()}**:\n\n"
            f"```{target_lang}\n"
            f"# Core Pattern Example\n"
            f"def process_data(items):\n"
            f"    \"\"\"Process and transform list items\"\"\"\n"
            f"    return [item.strip().title() for item in items if item]\n\n"
            f"sample_data = ['smart', 'study', 'ai', 'chatbot']\n"
            f"result = process_data(sample_data)\n"
            f"print('Processed Items:', result)\n"
            f"```\n\n"
            f"**Best Practices:**\n"
            f"- Use descriptive variable names\n"
            f"- Write modular, reusable functions\n"
            f"- Handle exceptions with `try/except` blocks\n"
            f"- Keep time and space complexity in mind!"
        )

    def _handle_concept(self, message, lang, mode):
        """Looks up educational concept in knowledge base"""
        msg = message.lower()
        
        # Search all categories and topics in knowledge base
        for domain, topics in self.knowledge.items():
            for key, item in topics.items():
                title_lower = item.get('title', '').lower()
                title_hi = item.get('title_hi', '').lower()
                key_lower = key.lower().replace('_', ' ')
                
                if key_lower in msg or title_lower in msg or title_hi in msg:
                    if lang in ['hindi', 'hinglish']:
                        title = item.get('title_hi', item.get('title', key))
                        defn = item.get('definition_hi', item.get('definition', ''))
                        expl = item.get('explanation_hi', item.get('explanation', ''))
                        pts = item.get('key_points_hi', item.get('key_points', []))
                        pts_formatted = "\n".join([f"- {p}" for p in pts])
                        ex = item.get('example_hi', item.get('example', ''))
                        
                        return (
                            f"### 📚 {title}\n\n"
                            f"**📖 परिभाषा (Definition):**\n{defn}\n\n"
                            f"**🔍 विस्तृत व्याख्या (Detailed Explanation):**\n{expl}\n\n"
                            f"**💡 उदाहरण (Example):**\n{ex}\n\n"
                            f"**🎯 मुख्य बिंदु (Key Takeaways):**\n{pts_formatted}"
                        )
                    else:
                        title = item.get('title', key)
                        defn = item.get('definition', '')
                        expl = item.get('explanation', '')
                        pts = item.get('key_points', [])
                        pts_formatted = "\n".join([f"- {p}" for p in pts])
                        ex = item.get('example', '')
                        
                        return (
                            f"### 📚 {title}\n\n"
                            f"**📖 Definition:**\n{defn}\n\n"
                            f"**🔍 Detailed Explanation:**\n{expl}\n\n"
                            f"**💡 Example & Application:**\n{ex}\n\n"
                            f"**🎯 Key Points:**\n{pts_formatted}"
                        )
        return None

    def _generate_quiz(self, query, lang):
        """Generates practice quizzes and questions"""
        quizzes = [
            {
                "topic": "Python & Data Structures",
                "q": "What is the average time complexity of searching in a Hash Table (Python Dictionary)?",
                "options": ["A) O(1)", "B) O(n)", "C) O(log n)", "D) O(n²)"],
                "answer": "A) O(1)",
                "explanation": "Hash Tables compute a hash of the key to index directly into an array bucket, giving O(1) constant average lookup time."
            },
            {
                "topic": "Physics: Motion",
                "q": "Which law states that every action has an equal and opposite reaction?",
                "options": ["A) Newton's 1st Law", "B) Newton's 2nd Law", "C) Newton's 3rd Law", "D) Law of Gravitation"],
                "answer": "C) Newton's 3rd Law",
                "explanation": "Newton's Third Law states that forces always occur in matched action-reaction pairs on interacting bodies."
            },
            {
                "topic": "Biology: Cell Structure",
                "q": "Which organelle is known as the 'Powerhouse of the Cell'?",
                "options": ["A) Nucleus", "B) Mitochondria", "C) Ribosome", "D) Golgi Apparatus"],
                "answer": "B) Mitochondria",
                "explanation": "Mitochondria generate most of the cell's supply of adenosine triphosphate (ATP), used as a source of chemical energy."
            }
        ]
        
        selected = random.choice(quizzes)
        opts = "\n".join([f"- {opt}" for opt in selected['options']])
        
        return (
            f"### 🎯 Quick Knowledge Quiz: {selected['topic']}\n\n"
            f"**Question:**\n**{selected['q']}**\n\n"
            f"{opts}\n\n"
            f"<details><summary>👉 <b>Click here to view Answer & Explanation</b></summary>\n\n"
            f"**Correct Answer:** `{selected['answer']}`\n\n"
            f"**Explanation:** {selected['explanation']}\n"
            f"</details>\n\n"
            f"💡 *Reply with your answer or ask for another question!*"
        )

    def _study_tips(self, lang):
        if lang in ['hindi', 'hinglish']:
            return (
                "### 🎓 प्रभावी अध्ययन तकनीकें (Smart Study Strategies)\n\n"
                "1. **पोमोडोरो तकनीक (Pomodoro Technique):**\n"
                "   - 25 मिनट एकाग्रता से पढ़ाई करें, फिर 5 मिनट का ब्रेक लें।\n"
                "2. **सक्रिय स्मरण (Active Recall):**\n"
                "   - सिर्फ बार-बार पढ़ने के बजाय खुद से सवाल पूछें और बिना देखे याद करने की कोशिश करें।\n"
                "3. **स्पेस्ड रिपीटिशन (Spaced Repetition):**\n"
                "   - पढ़े हुए टॉपिक को 1 दिन, 3 दिन, 7 दिन और 1 महीने बाद दोहराएं।\n"
                "4. **फेनमैन तकनीक (Feynman Technique):**\n"
                "   - कठिन कॉन्सेप्ट को ऐसे समझाएं जैसे किसी 10 साल के बच्चे को सिखा रहे हों।"
            )
        else:
            return (
                "### 🎓 Proven Scientific Study Strategies\n\n"
                "1. **Active Recall (Testing Effect):**\n"
                "   - Instead of passively re-reading notes, close your book and quiz yourself. Forcing memory retrieval strengthens neural pathways.\n\n"
                "2. **Spaced Repetition (Combating the Forgetting Curve):**\n"
                "   - Review concepts at increasing intervals: Day 1 $\\rightarrow$ Day 3 $\\rightarrow$ Day 7 $\\rightarrow$ Day 30.\n\n"
                "3. **The Feynman Technique:**\n"
                "   - Teach the concept in simple words without jargon. If you get stuck, review that specific section.\n\n"
                "4. **Pomodoro Focus Cycles:**\n"
                "   - 25 minutes of deep undistracted work + 5 minutes restorative break."
            )

    def _generate_creative(self, query, lang):
        if lang in ['hindi', 'hinglish']:
            return (
                "### ✨ सीखने की प्रेरणा (Motivational Poem)\n\n"
                "मेहनत की राहों पर जो कदम बढ़ाता है,\n"
                "वही ज्ञान का दीप इस जग में जलाता है।\n"
                "हर मुश्किल सवाल का हल ढूंढ निकालेंगे,\n"
                "Smart Study AI के संग नई मंजिल पाएंगे! 🚀📚"
            )
        else:
            return (
                "### ✨ Words of Inspiration\n\n"
                "*In the realm of code and light,*\n"
                "*Where curiosity takes its flight,*\n"
                "*Every challenge that you face,*\n"
                "*Builds your strength and wins the race.* 🌟📖\n\n"
                "Keep learning, keep building, and stay curious!"
            )

    def _synthesize_general_answer(self, query, lang, mode, user_name=None):
        """General high-quality synthetic answer"""
        name_prefix = f"{user_name}, " if user_name else ""
        if lang in ['hindi', 'hinglish']:
            return (
                f"### 💡 Smart Study AI Assistant\n\n"
                f"{name_prefix}आपके सवाल **'{query}'** पर:\n\n"
                f"मैं एक बुद्धिमान अध्ययन सहायक हूँ। आप किसी भी विषय जैसे:\n"
                f"- **प्रोग्रामिंग (Python, JS, C++, Web)**\n"
                f"- **गणित, भौतिकी, रसायन, जीवविज्ञान**\n"
                f"- **परीक्षा तैयारी, नोट्स और क्विज़**\n\n"
                f"के बारे में विस्तार से पूछ सकते हैं! क्या आप इस विषय में कोई विशेष उदाहरण या व्याख्या देखना चाहते हैं?"
            )
        else:
            return (
                f"### 💡 Smart Study AI Analysis\n\n"
                f"{name_prefix}Regarding your query on **'{query}'**:\n\n"
                f"Here is how we can break this down:\n"
                f"1. **Core Concept:** Understanding the fundamental principles behind '{query}'.\n"
                f"2. **Practical Approach:** Breaking the problem into structured components.\n"
                f"3. **Application & Testing:** Applying formulas, code, or logical steps to solve it.\n\n"
                f"Feel free to ask for a specific code sample, step-by-step math solution, or in-depth study notes on this topic! 🚀"
            )
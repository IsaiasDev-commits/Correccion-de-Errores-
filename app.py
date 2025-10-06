from flask import Flask, render_template, request, jsonify, session, send_from_directory
import os
import groq
from dotenv import load_dotenv
import json
from datetime import datetime
import uuid
import logging
from logging.handlers import RotatingFileHandler
import threading
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cyber-dev-key-2024-render")

# Configuración optimizada para Render
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hora

if os.environ.get('FLASK_ENV') == 'production' or 'RENDER' in os.environ:
    app.config.update(
        DEBUG=False,
        TESTING=False,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax"
    )

if 'RENDER' in os.environ:
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['SERVER_NAME'] = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

# Configuración de logging para Render
if not os.path.exists('logs'):
    os.makedirs('logs')

handler = RotatingFileHandler('logs/app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# Log de información del sistema en Render
if 'RENDER' in os.environ:
    app.logger.info(f"🚀 Iniciando CyberCode AI en Render")
    app.logger.info(f"📁 Directorio actual: {os.getcwd()}")
    app.logger.info(f"📁 Archivos: {os.listdir('.')}")

# Inicializar cliente Groq con manejo de errores
try:
    client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
    GROQ_AVAILABLE = True
    app.logger.info("✅ Groq client initialized successfully")
except Exception as e:
    GROQ_AVAILABLE = False
    app.logger.error(f"⚠️ Groq API key no configurada: {e}")

class SistemaAprendizaje:
    def __init__(self):
        self.respuestas_efectivas = {}  
        self.patrones_conversacion = {}  
        self.archivo_aprendizaje = "datos/aprendizaje.json"
        self.lock = threading.Lock()  
        self.cargar_aprendizaje()
    
    def cargar_aprendizaje(self):
        try:
            with self.lock:
                if os.path.exists(self.archivo_aprendizaje):
                    with open(self.archivo_aprendizaje, 'r', encoding='utf-8') as f:
                        datos = json.load(f)
                        self.respuestas_efectivas = datos.get('respuestas_efectivas', {})
                        self.patrones_conversacion = datos.get('patrones_conversacion', {})
        except Exception as e:
            app.logger.error(f"Error cargando aprendizaje: {e}")
    
    def guardar_aprendizaje(self):
        try:
            with self.lock:
                os.makedirs(os.path.dirname(self.archivo_aprendizaje), exist_ok=True)
                with open(self.archivo_aprendizaje, 'w', encoding='utf-8') as f:
                    json.dump({
                        'respuestas_efectivas': self.respuestas_efectivas,
                        'patrones_conversacion': self.patrones_conversacion
                    }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            app.logger.error(f"Error guardando aprendizaje: {e}")
    
    def evaluar_respuesta(self, lenguaje, respuesta_usuario, respuesta_bot, engagement):
        if not isinstance(lenguaje, str) or not lenguaje.strip():
            return
            
        if not isinstance(respuesta_bot, str) or not respuesta_bot.strip():
            return
            
        efectividad = min(10, max(1, engagement))
        
        if lenguaje not in self.respuestas_efectivas:
            self.respuestas_efectivas[lenguaje] = {}
        
        if respuesta_bot not in self.respuestas_efectivas[lenguaje]:
            self.respuestas_efectivas[lenguaje][respuesta_bot] = {
                'efectividad_total': 0,
                'veces_usada': 0,
                'ultimo_uso': datetime.now().isoformat()
            }
        
        self.respuestas_efectivas[lenguaje][respuesta_bot]['efectividad_total'] += efectividad
        self.respuestas_efectivas[lenguaje][respuesta_bot]['veces_usada'] += 1
        self.respuestas_efectivas[lenguaje][respuesta_bot]['ultimo_uso'] = datetime.now().isoformat()
        
        self.guardar_aprendizaje()
    
    def obtener_mejor_respuesta(self, lenguaje, contexto):
        if lenguaje in self.respuestas_efectivas and self.respuestas_efectivas[lenguaje]:
            respuestas_ordenadas = sorted(
                self.respuestas_efectivas[lenguaje].items(),
                key=lambda x: x[1]['efectividad_total'] / x[1]['veces_usada'] if x[1]['veces_usada'] > 0 else 0,
                reverse=True
            )
            
            for respuesta, stats in respuestas_ordenadas[:3]: 
                ultimo_uso = datetime.fromisoformat(stats['ultimo_uso'])
                if (datetime.now() - ultimo_uso).total_seconds() > 3600:
                    return respuesta
        
        return None

# Lenguajes de programación disponibles
lenguajes_disponibles = [
    "Python", "JavaScript", "Java", "C++", "C#", "PHP", "Ruby", "Go", "Rust",
    "TypeScript", "Swift", "Kotlin", "HTML/CSS", "React", "Vue.js", "Angular",
    "Node.js", "Express.js", "Django", "Flask", "Spring Boot", "Laravel",
    "SQL", "MongoDB", "PostgreSQL", "MySQL", "Firebase", "AWS", "Docker", "Kubernetes"
]

class CodeChatAssistant:
    def __init__(self):
        self.history = []
        self.session_id = str(uuid.uuid4())
        self.contador_interacciones = 0
        self.max_historial = 20
        self.sistema_aprendizaje = SistemaAprendizaje()
        self.lenguaje_actual = None
    
    def add_message(self, role, content, code_snippet=None):
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'code_snippet': code_snippet
        }
        self.history.append(message)
        # Mantener solo últimos mensajes
        if len(self.history) > self.max_historial:
            self.history = self.history[-self.max_historial:]
        
        self.contador_interacciones += 1
    
    def get_conversation_context(self):
        return self.history[-6:]  # Últimos 6 mensajes para contexto
    
    def to_dict(self):
        return {
            'history': self.history,
            'session_id': self.session_id,
            'contador_interacciones': self.contador_interacciones,
            'lenguaje_actual': self.lenguaje_actual
        }
    
    @classmethod
    def from_dict(cls, data):
        instance = cls()
        instance.history = data.get('history', [])
        instance.session_id = data.get('session_id', str(uuid.uuid4()))
        instance.contador_interacciones = data.get('contador_interacciones', 0)
        instance.lenguaje_actual = data.get('lenguaje_actual', None)
        return instance
    
    def detectar_lenguaje(self, user_message):
        """Detecta el lenguaje de programación del mensaje del usuario"""
        lenguajes_keywords = {
            "Python": ["python", "def ", "import ", "print(", "numpy", "pandas"],
            "JavaScript": ["javascript", "js", "function()", "console.log", "react", "vue", "angular"],
            "Java": ["java", "public class", "System.out", "spring"],
            "HTML/CSS": ["html", "css", "<div>", "class=", "style="],
            "React": ["react", "useState", "component", "jsx"],
            "Node.js": ["node", "express", "require(", "npm"],
            "SQL": ["sql", "select", "insert", "update", "delete", "where"],
        }
        
        user_message_lower = user_message.lower()
        for lenguaje, keywords in lenguajes_keywords.items():
            for keyword in keywords:
                if keyword in user_message_lower:
                    return lenguaje
        return "General"
    
    def analyze_with_ai(self, user_message):
        try:
            if not GROQ_AVAILABLE:
                return {
                    "success": False,
                    "error": "Servicio AI no configurado. Por favor, configura GROQ_API_KEY en Render."
                }
            
            # Detectar lenguaje automáticamente
            lenguaje_detectado = self.detectar_lenguaje(user_message)
            self.lenguaje_actual = lenguaje_detectado

            system_prompt = f"""Eres CyberCode AI, un asistente de programación futurista y experto. 

ESPECIALIDAD EN: {lenguaje_detectado.upper() if lenguaje_detectado != "General" else "TODOS LOS LENGUAJES"}

CARACTERÍSTICAS:
🎯 ANALIZA código y detecta errores
🔍 SUGIERE optimizaciones y mejores prácticas
💡 EXPLICA conceptos de programación claramente
🚀 PROPORCIONA ejemplos prácticos y código corregido
🤖 MANTÉN un tono profesional pero amigable

INSTRUCCIONES ESPECÍFICAS:
1. Responde en formato Markdown cuando muestres código
2. Usa bloques de código con sintaxis highlighting
3. Sé específico y técnicamente preciso
4. Explica el "por qué" detrás de las correcciones
5. Ofrece alternativas cuando sea relevante
6. Mantén las respuestas concisas pero completas

EJEMPLO DE RESPUESTA:
```{lenguaje_detectado.lower() if lenguaje_detectado != "General" else "python"}
// Código optimizado
function ejemploMejorado() {{
    console.log('Hola mundo optimizado');
}}
💡 Explicación: Aquí se mejoró [explicación técnica]...

¿Necesitas más ayuda con algún concepto específico?"""

            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Agregar historial de conversación
            for msg in self.get_conversation_context():
                messages.append({
                    "role": 'user' if msg['role'] == 'user' else 'assistant',
                    "content": msg['content']
                })
            
            # Agregar mensaje actual
            messages.append({"role": "user", "content": user_message})
            
            # Usar modelos de Groq
            modelos = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            response = None
            
            for modelo in modelos:
                try:
                    response = client.chat.completions.create(
                        model=modelo,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=2000,
                        timeout=30
                    )
                    app.logger.info(f"✅ Modelo {modelo} funcionando para {lenguaje_detectado}")
                    break
                except Exception as e:
                    app.logger.warning(f"Modelo {modelo} falló: {e}")
                    continue
            
            if not response:
                return {
                    "success": False,
                    "error": "No se pudo conectar con ningún modelo AI"
                }
            
            ai_response = response.choices[0].message.content
            self.add_message('assistant', ai_response)
            
            # Aprender de esta interacción
            engagement = min(10, len(user_message) / 10)
            self.sistema_aprendizaje.evaluar_respuesta(lenguaje_detectado, user_message, ai_response, engagement)
            
            return {
                "success": True,
                "response": ai_response,
                "session_id": self.session_id,
                "lenguaje": lenguaje_detectado,
                "history_length": len(self.history),
                "interacciones": self.contador_interacciones
            }
            
        except Exception as e:
            app.logger.error(f"Error en análisis: {str(e)}")
            return {
                "success": False,
                "error": f"Error en análisis: {str(e)}"
            }

@app.route('/')
def index():
    # Inicializar nueva sesión de chat
    session.permanent = True
    if 'chat_session' not in session:
        session['chat_session'] = CodeChatAssistant().to_dict()
    
    # Log de sesión para debug
    if 'RENDER' in os.environ:
        app.logger.info(f"📱 Nueva sesión iniciada: {session.get('chat_session', {}).get('session_id', 'new')}")
    
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '').strip()
        
        if not user_message:
            return jsonify({"success": False, "error": "El mensaje no puede estar vacío"})
        
        # Recuperar o crear sesión de chat
        if 'chat_session' not in session:
            session['chat_session'] = CodeChatAssistant().to_dict()
        
        chat_assistant = CodeChatAssistant.from_dict(session['chat_session'])
        
        # Agregar mensaje del usuario
        chat_assistant.add_message('user', user_message)
        
        # Procesar mensaje
        result = chat_assistant.analyze_with_ai(user_message)
        
        # Guardar sesión actualizada
        session['chat_session'] = chat_assistant.to_dict()
        session.modified = True
        
        # Log de interacción
        app.logger.info(f"💬 Chat interaction - Lenguaje: {chat_assistant.lenguaje_actual}, Messages: {chat_assistant.contador_interacciones}")
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error en endpoint /chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/new_chat', methods=['POST'])
def new_chat():
    try:
        # Reiniciar conversación
        session['chat_session'] = CodeChatAssistant().to_dict()
        session.modified = True
        
        app.logger.info("🆕 Nueva conversación iniciada")
        
        return jsonify({
            "success": True, 
            "message": "Nueva conversación iniciada",
            "session_id": session['chat_session']['session_id']
        })
    except Exception as e:
        app.logger.error(f"Error al crear nuevo chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/logo.png')
def serve_logo():
    return send_from_directory('static', 'logo.png')

@app.route('/health')
def health():
    groq_status = "groq_connected" if GROQ_AVAILABLE else "groq_missing_key"
    return jsonify({
        "status": "cyber_ready",
        "ai": groq_status,
        "environment": os.getenv("FLASK_ENV", "production"),
        "render": 'RENDER' in os.environ,
        "session_active": 'chat_session' in session
    })

@app.route('/test')
def test():
    return jsonify({
        "message": "Flask is working!",
        "status": "success",
        "timestamp": datetime.now().isoformat()
    })

# Manejo de errores mejorado
@app.errorhandler(404)
def not_found(error):
    app.logger.warning(f"404 Not Found: {request.url}")
    return jsonify({
        "error": "Endpoint no encontrado",
        "available_routes": ["/", "/chat", "/new_chat", "/health", "/test", "/logo.png"]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f"500 Internal Error: {error}")
    return jsonify({"error": "Error interno del servidor"}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    app.logger.warning(f"429 Rate Limit Exceeded: {e}")
    return jsonify({"error": "Demasiadas solicitudes. Por favor, intenta más tarde."}), 429

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    app.logger.info(f"🚀 Starting CyberCode AI on port {port}")
    
    # Para Render, usar gunicorn compatible
    if 'RENDER' in os.environ:
        app.logger.info("🌐 Running in Render environment")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
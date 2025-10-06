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

class CodeChatAssistant:
    def __init__(self):
        self.history = []
        self.session_id = str(uuid.uuid4())
        self.contador_interacciones = 0
        self.max_historial = 20
    
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
            'contador_interacciones': self.contador_interacciones
        }
    
    @classmethod
    def from_dict(cls, data):
        instance = cls()
        instance.history = data.get('history', [])
        instance.session_id = data.get('session_id', str(uuid.uuid4()))
        instance.contador_interacciones = data.get('contador_interacciones', 0)
        return instance
    
    def analyze_with_ai(self, user_message):
        try:
            if not GROQ_AVAILABLE:
                return {
                    "success": False,
                    "error": "Servicio AI no configurado. Por favor, configura GROQ_API_KEY en Render."
                }
            
            system_prompt = """Eres CyberCode AI, un asistente de programación futurista y experto. 

CARACTERÍSTICAS:
🎯 ANALIZA código en JavaScript, Python, HTML, CSS, React, etc.
🔍 DETECTA errores, sugiere optimizaciones y mejores prácticas
💡 EXPLICA conceptos de manera clara y didáctica
🚀 PROPORCIONA ejemplos prácticos y código corregido
🤖 MANTÉN un tono profesional pero amigable

RESPONDE en formato Markdown cuando sea útil para código.

EJEMPLOS DE RESPUESTA:
```javascript
// Código corregido
function ejemplo() {
    console.log('Hola mundo');
}
💡 Consejo: Siempre declara variables con let/const...

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
            
            # Usar modelos disponibles en Groq
            modelos = ["llama3-8b-8192", "llama3.1-8b-instant", "llama3.1-70b-versatile"]
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
                    break
                except Exception as e:
                    app.logger.warning(f"Modelo {modelo} falló, probando siguiente: {e}")
                    continue
            
            if not response:
                return {
                    "success": False,
                    "error": "No se pudo conectar con el servicio AI"
                }
            
            ai_response = response.choices[0].message.content
            self.add_message('assistant', ai_response)
            
            return {
                "success": True,
                "response": ai_response,
                "session_id": self.session_id,
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
        session['chat_session'] = CodeChatAssistant().__dict__
    
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
            session['chat_session'] = CodeChatAssistant().__dict__
        
        chat_assistant = CodeChatAssistant()
        chat_assistant.__dict__ = session['chat_session']
        
        # Agregar mensaje del usuario
        chat_assistant.add_message('user', user_message)
        
        # Procesar mensaje
        result = chat_assistant.analyze_with_ai(user_message)
        
        # Guardar sesión actualizada
        session['chat_session'] = chat_assistant.__dict__
        session.modified = True
        
        # Log de interacción
        app.logger.info(f"💬 Chat interaction - Session: {chat_assistant.session_id}, Messages: {chat_assistant.contador_interacciones}")
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error en endpoint /chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/new_chat', methods=['POST'])
def new_chat():
    try:
        # Reiniciar conversación
        session['chat_session'] = CodeChatAssistant().__dict__
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
        "session_active": 'chat_session' in session,
        "debug_info": {
            "python_version": os.sys.version,
            "current_directory": os.getcwd(),
            "files_in_root": len(os.listdir('.')) if os.path.exists('.') else 0
        }
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
    app.logger.info(f"📁 Current directory: {os.getcwd()}")
    
    if os.path.exists('templates'):
        app.logger.info(f"📁 Templates: {os.listdir('templates')}")
    if os.path.exists('static'):
        app.logger.info(f"📁 Static files: {os.listdir('static')}")
    
    # Para Render, usar gunicorn compatible
    if 'RENDER' in os.environ:
        app.logger.info("🌐 Running in Render environment")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
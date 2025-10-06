from flask import Flask, render_template, request, jsonify, session, send_from_directory
import os
import groq
from dotenv import load_dotenv
import json
from datetime import datetime
import uuid

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cyber-dev-key-2024-render")
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hora

# Configuración para Render
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'

# Inicializar cliente Groq solo si hay API key
try:
    client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
    GROQ_AVAILABLE = True
    print("✅ Groq client initialized successfully")
except Exception as e:
    GROQ_AVAILABLE = False
    print(f"⚠️  Groq API key no configurada: {e}")

class CodeChatAssistant:
    def __init__(self):
        self.history = []
        self.session_id = str(uuid.uuid4())
    
    def add_message(self, role, content, code_snippet=None):
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'code_snippet': code_snippet
        }
        self.history.append(message)
        # Mantener solo últimos 20 mensajes
        if len(self.history) > 20:
            self.history = self.history[-20:]
    
    def get_conversation_context(self):
        return self.history[-6:]  # Últimos 6 mensajes para contexto
    
    def analyze_with_ai(self, user_message):
        try:
            if not GROQ_AVAILABLE:
                return {
                    "success": False,
                    "error": "Servicio AI no configurado. Por favor, configura GROQ_API_KEY en las variables de entorno de Render."
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
            
            # Usar un modelo disponible en Groq
            response = client.chat.completions.create(
                model="llama3-8b-8192",  # Modelo disponible en Groq
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=30
            )
            
            ai_response = response.choices[0].message.content
            self.add_message('assistant', ai_response)
            
            return {
                "success": True,
                "response": ai_response,
                "session_id": self.session_id,
                "history_length": len(self.history)
            }
            
        except Exception as e:
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
        
        # Procesar mensaje
        result = chat_assistant.analyze_with_ai(user_message)
        
        # Guardar sesión actualizada
        session['chat_session'] = chat_assistant.__dict__
        session.modified = True
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/new_chat', methods=['POST'])
def new_chat():
    # Reiniciar conversación
    session['chat_session'] = CodeChatAssistant().__dict__
    session.modified = True
    return jsonify({"success": True, "message": "Nueva conversación iniciada"})

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
        "debug_info": {
            "templates_path": os.path.exists('templates'),
            "static_path": os.path.exists('static'),
            "template_files": os.listdir('templates') if os.path.exists('templates') else []
        }
    })

# Ruta de prueba para verificar que Flask funciona
@app.route('/test')
def test():
    return jsonify({"message": "Flask is working!", "status": "success"})

# Manejo de errores
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint no encontrado", "available_routes": ["/", "/chat", "/new_chat", "/health", "/test"]}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    print(f"🚀 Starting CyberCode AI on port {port}")
    print(f"📁 Current directory: {os.getcwd()}")
    print(f"📁 Files in directory: {os.listdir('.')}")
    if os.path.exists('templates'):
        print(f"📁 Templates files: {os.listdir('templates')}")
    if os.path.exists('static'):
        print(f"📁 Static files: {os.listdir('static')}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
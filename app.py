import os
import json
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify, session, send_from_directory
from dotenv import load_dotenv
from datetime import datetime
import uuid
import threading
import re
import groq

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "cyber-dev-key-2024-render")
app.config['PERMANENT_SESSION_LIFETIME'] = 3600

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

if not os.path.exists('logs'):
    os.makedirs('logs')
handler = RotatingFileHandler('logs/app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

if 'RENDER' in os.environ:
    app.logger.info(f"🚀 Iniciando CyberCode AI en Render")
    app.logger.info(f"📁 Directorio actual: {os.getcwd()}")
    app.logger.info(f"📁 Archivos: {os.listdir('.')}")

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
        self.history.append({"role": role, "content": content, "code_snippet": code_snippet})
        self.contador_interacciones += 1
    def get_conversation_context(self):
        return self.history[-self.max_historial:]
    def to_dict(self):
        return {
            "history": self.history,
            "session_id": self.session_id,
            "contador_interacciones": self.contador_interacciones,
            "max_historial": self.max_historial,
            "lenguaje_actual": self.lenguaje_actual
        }
    @classmethod
    def from_dict(cls, data):
        obj = cls()
        obj.history = data.get("history", [])
        obj.session_id = data.get("session_id", str(uuid.uuid4()))
        obj.contador_interacciones = data.get("contador_interacciones", 0)
        obj.max_historial = data.get("max_historial", 20)
        obj.lenguaje_actual = data.get("lenguaje_actual", None)
        return obj
    def detectar_lenguaje(self, user_message):
        lenguajes_keywords = {
            "Python": ["python", "def ", "import ", "print(", "numpy", "pandas", "__main__", "if __name__"],
            "JavaScript": ["javascript", "js", "function()", "console.log", "react", "vue", "angular", "document.", "window."],
            "Java": ["java", "public class", "System.out", "spring", "void main", "String[]", "import java"],
            "HTML/CSS": ["html", "css", "<div>", "class=", "style=", "<html", "<body", "color:", "font-size"],
            "React": ["react", "useState", "component", "jsx", "useEffect", "props", "setState"],
            "Node.js": ["node", "express", "require(", "npm", "module.exports", "app.get", "app.post"],
            "SQL": ["sql", "select", "insert", "update", "delete", "where", "from", "join", "table"],
            "C++": ["c++", "#include", "cout <<", "cin >>", "std::", "vector<", "class "],
            "TypeScript": ["typescript", "ts", "interface", "type ", "const:", "function("]
        }
        user_message_lower = user_message.lower()
        for lenguaje, keywords in lenguajes_keywords.items():
            for keyword in keywords:
                if keyword.lower() in user_message_lower:
                    return lenguaje
        return "General"
    def extraer_codigo_usuario(self, user_message):
        codigo_bloques = re.findall(r'```(?:\w+)?\n(.*?)```', user_message, re.DOTALL)
        if codigo_bloques:
            return codigo_bloques[0].strip()
        codigo_inline = re.findall(r'`([^`]+)`', user_message)
        if codigo_inline:
            return codigo_inline[0]
        lineas = user_message.split('\n')
        lineas_codigo = [linea for linea in lineas if any(keyword in linea for keyword in [
            'def ', 'function', 'class ', 'import ', 'var ', 'let ', 'const ', 'if ', 'for ', 'while ', 'return ', 'print', 'console.log'])]
        if lineas_codigo:
            return '\n'.join(lineas_codigo)
        return user_message
    def analizar_codigo_estructura(self, codigo, lenguaje):
        problemas = []
        sugerencias = []
        if lenguaje == "Python":
            if 'import ' in codigo and 'import os' not in codigo and 'import sys' not in codigo:
                sugerencias.append("Considera agregar imports estándar como os, sys para mejor funcionalidad")
            if 'def ' in codigo and ':' in codigo and '    ' not in codigo and '\t' not in codigo:
                problemas.append("Falta indentación en funciones")
                sugerencias.append("Usa 4 espacios para indentación en Python")
            if 'print(' in codigo and 'f"' not in codigo and 'format(' not in codigo:
                sugerencias.append("Considera usar f-strings para formateo más legible")
        elif lenguaje == "JavaScript":
            if 'function(' in codigo and '=>' not in codigo:
                sugerencias.append("Considera usar arrow functions para código más moderno")
            if 'var ' in codigo:
                problemas.append("Uso de 'var' en lugar de 'let' o 'const'")
                sugerencias.append("Usa 'const' para valores constantes y 'let' para variables que cambian")
            if 'console.log' in codigo and '//' not in codigo:
                sugerencias.append("Agrega comentarios para explicar los logs de debug")
        return problemas, sugerencias
    def generar_respuesta_estructurada(self, user_message, ai_response_raw, lenguaje):
        codigo_usuario = self.extraer_codigo_usuario(user_message)
        problemas, sugerencias = self.analizar_codigo_estructura(codigo_usuario, lenguaje)
        respuesta_estructurada = f"""**🤖 CYBERCODE AI - ASISTENTE {lenguaje.upper()}**\n\n"""
        if codigo_usuario and len(codigo_usuario) > 10:
            respuesta_estructurada += f"""**🔍 ANÁLISIS DEL CÓDIGO**\n\n```{lenguaje.lower()}\n{codigo_usuario}\n``"""
            if problemas:
                respuesta_estructurada += "**⚠️ PROBLEMAS IDENTIFICADOS:**\n"
                for problema in problemas:
                    respuesta_estructurada += f"• {problema}\n"
                respuesta_estructurada += "\n"
            if sugerencias:
                respuesta_estructurada += "**💡 SUGERENCIAS INMEDIATAS:**\n"
                for sugerencia in sugerencias:
                    respuesta_estructurada += f"• {sugerencia}\n"
                respuesta_estructurada += "\n"
        respuesta_estructurada += f"""**🚀 RESPUESTA ESPECIALIZADA**\n{ai_response_raw}\n\n"""
        mejores_practicas = self.obtener_mejores_practicas(lenguaje)
        if mejores_practicas:
            respuesta_estructurada += f"""**📚 MEJORES PRÁCTICAS - {lenguaje.upper()}**\n{mejores_practicas}\n\n"""
        respuesta_estructurada += """**¿Necesitas más ayuda?** \nPuedo:\n• 🔍 Analizar código más complejo\n• 💡 Explicar conceptos específicos\n• ⚡ Optimizar rendimiento\n• 🐛 Debuggear errores\n• 📚 Mostrar ejemplos avanzados\n\n¡Solo pregúntame! 🚀"""
        return respuesta_estructurada
    def obtener_mejores_practicas(self, lenguaje):
        practicas = {
            "Python": """• Usa type hints para mejor legibilidad\n• Aplica el principio DRY (Don't Repeat Yourself)\n• Usa context managers (with) para manejo de recursos\n• Sigue PEP 8 para estilo de código\n• Escribe docstrings para documentación\n• Usa virtual environments para dependencias\n• Implementa manejo de excepciones específico""",
            "JavaScript": """• Usa const/let en lugar de var\n• Implementa async/await para operaciones asíncronas\n• Usa arrow functions para callbacks\n• Aplica destructuring para objetos/arrays\n• Usa template literals para strings\n• Sigue ESLint para consistencia\n• Implementa error handling con try/catch""",
            "Java": """• Sigue convenciones de nombrado Java\n• Usa streams para procesamiento de datos\n• Implementa optional para valores nulos\n• Aplica principios SOLID\n• Usa Lombok para reducir boilerplate\n• Implementa logging apropiado\n• Usa constructores para inmutabilidad""",
            "React": """• Usa functional components con hooks\n• Implementa useEffect correctamente\n• Aplica propTypes o TypeScript\n• Usa context API para estado global\n• Optimiza con React.memo y useMemo\n• Separa concerns con custom hooks\n• Implementa error boundaries"""
        }
        return practicas.get(lenguaje, "• Escribe código limpio y legible\n• Usa nombres descriptivos\n• Comenta cuando sea necesario\n• Prueba tu código\n• Sigue las convenciones del lenguaje")
    def analyze_with_ai(self, user_message):
        try:
            if not GROQ_AVAILABLE:
                return {"success": False, "error": "Servicio AI no configurado. Por favor, configura GROQ_API_KEY en Render."}
            lenguaje_detectado = self.detectar_lenguaje(user_message)
            self.lenguaje_actual = lenguaje_detectado
            system_prompt = f"Eres CyberCode AI, un experto asistente de programación especializado en {lenguaje_detectado if lenguaje_detectado != 'General' else 'múltiples lenguajes'}..."
            messages = [{"role": "system", "content": system_prompt}]
            for msg in self.get_conversation_context():
                messages.append({"role": 'user' if msg['role'] == 'user' else 'assistant', "content": msg['content']})
            messages.append({"role": "user", "content": user_message})
            modelos = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
            response = None
            for modelo in modelos:
                try:
                    response = client.chat.completions.create(
                        model=modelo,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=3000,
                        timeout=45
                    )
                    app.logger.info(f"✅ Modelo {modelo} funcionando para {lenguaje_detectado}")
                    break
                except Exception as e:
                    app.logger.warning(f"Modelo {modelo} falló: {e}")
                    continue
            if not response:
                return {"success": False, "error": "No se pudo conectar con ningún modelo AI"}
            ai_response_raw = response.choices[0].message.content
            ai_response_mejorada = self.generar_respuesta_estructurada(user_message, ai_response_raw, lenguaje_detectado)
            self.add_message('assistant', ai_response_mejorada)
            engagement = min(10, len(user_message) / 10 + 2)
            self.sistema_aprendizaje.evaluar_respuesta(lenguaje_detectado, user_message, ai_response_mejorada, engagement)
            return {
                "success": True,
                "response": ai_response_mejorada,
                "session_id": self.session_id,
                "lenguaje": lenguaje_detectado,
                "history_length": len(self.history),
                "interacciones": self.contador_interacciones
            }
        except Exception as e:
            app.logger.error(f"Error en análisis: {str(e)}")
            return {"success": False, "error": f"Error en análisis: {str(e)}"}

# --- RUTAS FLASK ---
@app.route('/')
def index():
    session.permanent = True
    if 'chat_session' not in session:
        session['chat_session'] = CodeChatAssistant().to_dict()
    if 'RENDER' in os.environ:
        app.logger.info(f"📱 Nueva sesión iniciada: {session.get('chat_session', {}).get('session_id', 'new')}")
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '').strip()
        if not user_message:
            return jsonify({"success": False, "error": "El mensaje no puede estar vacío"})
        if 'chat_session' not in session:
            session['chat_session'] = CodeChatAssistant().to_dict()
        chat_assistant = CodeChatAssistant.from_dict(session['chat_session'])
        chat_assistant.add_message('user', user_message)
        result = chat_assistant.analyze_with_ai(user_message)
        session['chat_session'] = chat_assistant.to_dict()
        session.modified = True
        app.logger.info(f"💬 Chat interaction - Lenguaje: {chat_assistant.lenguaje_actual}, Messages: {chat_assistant.contador_interacciones}")
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error en endpoint /chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/new_chat', methods=['POST'])
def new_chat():
    try:
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

# --- MANEJO DE ERRORES ---
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

# --- EJECUCIÓN DEL SERVIDOR ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.logger.info(f"🚀 Starting CyberCode AI on port {port}")
    if 'RENDER' in os.environ:
        app.logger.info("🌐 Running in Render environment")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

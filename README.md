# Tasador Online Córdoba Capital

Lead Magnet inmobiliario con inteligencia artificial para captar propietarios de inmuebles en Córdoba Capital, Argentina.

## Características
- **Frontend 2 Pasos**: Formulario interactivo y adaptable a móviles (Tailwind CSS).
- **Valuación con IA**: Utiliza Gemini para estimar valores en USD (conservador, de mercado sugerido y optimista), precio por m² y 3 recomendaciones clave para defender el precio.
- **Notificación Instantánea**: Envío de alerta inmediata con los datos del propietario y la tasación a WhatsApp mediante CallMeBot.
- **Registro de Leads**: Almacenamiento local en CSV (`leads_tasador.csv`).

## Despliegue en Render.com
1. Crea un nuevo **Web Service** en Render conectado a este repositorio.
2. Render detectará automáticamente el archivo `render.yaml` y `Procfile`.
3. Configura las siguientes **Environment Variables** en el panel de Render:
   - `GEMINI_API_KEY`: Tu API Key de Google Gemini.
   - `CALLMEBOT_API_KEY`: Tu API Key de CallMeBot.
   - `MI_WHATSAPP`: Tu número telefónico con código internacional (ej: `5493573499317`).
4. El comando de inicio es `gunicorn app:app`.

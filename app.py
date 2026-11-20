import os
import csv
import json
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY", "").strip()
MI_WHATSAPP = os.getenv("MI_WHATSAPP", "").strip()
CSV_FILE = "leads_tasador.csv"

# Inicializar cliente de Google GenAI
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)

def inicializar_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Fecha", "Nombre", "Telefono", "Motivo", 
                "Tipo", "Barrio", "M2 Cubiertos", "M2 Descubiertos", 
                "Dormitorios", "Cochera", "Estado", 
                "Antiguedad", "Disposicion", "Situacion Juridica", "Amenities",
                "Valor Sugerido USD"
            ])

def guardar_lead(datos, valor_sugerido):
    inicializar_csv()
    amenities_str = ", ".join(datos.get("amenities", [])) if isinstance(datos.get("amenities"), list) else str(datos.get("amenities", ""))
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            datos.get("nombre", ""),
            datos.get("telefono", ""),
            datos.get("motivo", ""),
            datos.get("tipo", ""),
            datos.get("barrio", ""),
            datos.get("m2_cubiertos", ""),
            datos.get("m2_descubiertos", "0"),
            datos.get("dormitorios", ""),
            datos.get("cochera", ""),
            datos.get("estado", ""),
            datos.get("antiguedad", "No especificado"),
            datos.get("disposicion", "No especificado"),
            datos.get("situacion_juridica", "No especificado"),
            amenities_str,
            valor_sugerido
        ])

def enviar_notificacion_callmebot(datos, tasacion):
    if not CALLMEBOT_API_KEY or not MI_WHATSAPP:
        print("CallMeBot no configurado correctamente.")
        return False
    
    amenities_str = ", ".join(datos.get("amenities", [])) if isinstance(datos.get("amenities"), list) and datos.get("amenities") else datos.get("amenities", "Ninguno")
    if not amenities_str:
        amenities_str = "Ninguno"

    mensaje = (
        "🔥 *NUEVO PROPIETARIO TASÓ SU INMUEBLE*\n\n"
        f"👤 *Nombre:* {datos.get('nombre')}\n"
        f"📱 *Teléfono:* {datos.get('telefono')}\n"
        f"🎯 *Motivo:* {datos.get('motivo')}\n\n"
        "🏠 *Datos de la Propiedad:*\n"
        f"• Tipo: {datos.get('tipo')}\n"
        f"• Barrio: {datos.get('barrio')}\n"
        f"• M² Cubiertos: {datos.get('m2_cubiertos')} m²\n"
        f"• M² Patio/Balcón: {datos.get('m2_descubiertos', 0)} m²\n"
        f"• Dormitorios: {datos.get('dormitorios')}\n"
        f"• Cochera: {datos.get('cochera')}\n"
        f"• Estado: {datos.get('estado')}\n"
        f"• Antigüedad: {datos.get('antiguedad', 'No especificado')}\n"
        f"• Disposición: {datos.get('disposicion', 'No especificado')}\n"
        f"• Situación Jurídica: {datos.get('situacion_juridica', 'No especificado')}\n"
        f"• Amenities: {amenities_str}\n\n"
        f"💵 *Tasación Sugerida:* USD {tasacion.get('valor_sugerido', 0):,}\n"
        f"📊 *Rango:* USD {tasacion.get('valor_min', 0):,} - USD {tasacion.get('valor_max', 0):,}\n"
        f"📍 *USD/M²:* USD {tasacion.get('valor_m2', 0)}"
    )

    try:
        url = f"https://api.callmebot.com/whatsapp.php?phone={MI_WHATSAPP}&text={urllib.parse.quote(mensaje)}&apikey={CALLMEBOT_API_KEY}"
        response = requests.get(url, timeout=10)
        print(f"CallMeBot Status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error enviando WhatsApp con CallMeBot: {e}")
        return False

def obtener_tasacion_gemini(datos):
    amenities_str = ", ".join(datos.get("amenities", [])) if isinstance(datos.get("amenities"), list) and datos.get("amenities") else datos.get("amenities", "Ninguno")
    if not amenities_str:
        amenities_str = "Ninguno"

    prompt = f"""
Eres un tasador inmobiliario profesional, perito y martillero matriculado de Córdoba Capital, Argentina, con más de 20 años de experiencia analizando el mercado local.

Debes realizar una tasación precisa, prudente y realista en dólares estadounidenses (USD) para el siguiente inmueble en Córdoba Capital:
- Tipo: {datos.get('tipo')}
- Barrio: {datos.get('barrio')}
- Metros cuadrados cubiertos: {datos.get('m2_cubiertos')} m²
- Metros cuadrados de balcón / terraza / patio: {datos.get('m2_descubiertos', 0)} m²
- Dormitorios: {datos.get('dormitorios')}
- Cochera: {datos.get('cochera')}
- Estado de conservación: {datos.get('estado')}
- Antigüedad: {datos.get('antiguedad', 'No especificado')}
- Disposición: {datos.get('disposicion', 'No especificado')}
- Situación Jurídica / Título: {datos.get('situacion_juridica', 'No especificado')}
- Amenities destacados: {amenities_str}

Referencias de mercado inmobiliario de Córdoba Capital a considerar por zonas y barrios:
- ZONA CENTRO Y ALREDEDORES UNIVERSITARIOS:
  * Nueva Córdoba: USD 1.400 a 2.200/m² (alta demanda estudiantil e inversores; premium sobre Av. Yrigoyen, Chacabuco, Rondeau).
  * General Paz y Juniors: USD 1.100 a 1.700/m² (polo gastronómico, residencial de categoría).
  * Güemes y Observatorio: USD 950 a 1.500/m² (área cultural y comercial en auge).
  * Centro, Alberdi, Alto Alberdi y Quintas de Santa Ana: USD 750 a 1.150/m² (zona comercial, conectividad y consolidación).
- ZONA NORTE RESIDENCIAL / ALTA GAMA:
  * Cerro de las Rosas, Villa Belgrano, Urca: USD 1.250 a 1.900/m² (lotes amplios, casas de categoría y condominios modernos).
  * Alto Verde, Colinas del Cerro, Bajo Palermo, Las Rosas, Chateau Carreras: USD 1.100 a 1.600/m².
  * Argüello, Villa Cabrera, Poeta Lugones, Alejandro Centeno: USD 850 a 1.350/m².
- ZONA NORTE / CENTRO RESIDENCIAL:
  * Alta Córdoba y Cofico: USD 950 a 1.500/m² (gran demanda residencial tradicional y gastronómica).
  * San Martín, Lomas de San Martín, Providencia, Ducasse, Escobar, La France, Marqués de Sobremonte: USD 750 a 1.100/m².
- ZONA SUR / SUROESTE:
  * Manantiales: USD 1.100 a 1.650/m² (urbanización moderna en fuerte expansión).
  * Barrio Jardín, Iponá, Inaudi, Parque Vélez Sarsfield: USD 950 a 1.450/m² (cercano a Ciudad Universitaria y countries sur).
  * Bella Vista, Paso de los Andes, Parque Capital, Los Naranjos, Los Plátanos, Las Palmas: USD 700 a 1.050/m².
- ZONA ESTE / SURESTE:
  * San Vicente, Crisol Norte, Crisol Sur, Maipú 1ª Sección, Maipú 2ª Sección, General Bustos, Pueyrredón, Independiente: USD 700 a 1.100/m².

Ponderación técnica de variables adicionales en Córdoba:
- Antigüedad: A estrenar (+5% a +10%), 1 a 10 años (neutro / óptimo), 10 a 25 años (-5% a -12%), +25 años (-15% a -25% salvo reciclado integral).
- Disposición: Frente suele cotizar 5% a 10% más que contrafrente en Nueva Córdoba y General Paz por luminosidad y vistas. Interno castiga entre 10% y 15%.
- Situación Jurídica: 'Escritura inmediata' es el valor estándar pleno de mercado (apto crédito hipotecario Bancor/UVA, gran valor agregado en Córdoba). 'Boleto de compraventa' suele requerir un descuento de negociación del 5% al 12% por falta de apto crédito inmediato.
- Amenities: La presencia de Pileta, Quincho/SUM, Asador y Seguridad 24hs defiende el techo de mercado y acelera la venta en zonas como Nueva Córdoba, General Paz o Condominios de Zona Norte.
- Patios, jardines y balcones computan entre el 30% y el 50% del valor m² cubierto.
- Cochera cubierta suma entre USD 8.000 y USD 16.000 según la demanda del barrio.

Responde ÚNICAMENTE en formato JSON plano (sin markdown, JSON válido) con esta estructura exacta:
{{
  "valor_min": <entero en USD, valor conservador / venta rápida>,
  "valor_sugerido": <entero en USD, valor promedio de mercado recomendado>,
  "valor_max": <entero en USD, valor optimista / techo de mercado>,
  "valor_m2": <entero en USD por m² promedio ponderado estimado para la propiedad>,
  "analisis_breve": "<1 o 2 oraciones profesionales explicando el posicionamiento en el mercado cordobés actual, ponderando su estado, título y comodidades>",
  "consejos": [
    "<Consejo 1 específico y accionable para defender el valor en Córdoba Capital>",
    "<Consejo 2 sobre documentación (escritura/apto crédito), mejoras o presentación>",
    "<Consejo 3 sobre estrategia comercial y velocidad de venta>"
  ]
}}
"""

    if not client:
        # Fallback de contingencia si no hay API Key activa
        m2 = float(datos.get('m2_cubiertos', 60))
        val_base = int(m2 * 1100)
        return {
            "valor_min": int(val_base * 0.9),
            "valor_sugerido": val_base,
            "valor_max": int(val_base * 1.12),
            "valor_m2": 1100,
            "analisis_breve": "Tasación estimada basada en estadísticas medias de Córdoba Capital.",
            "consejos": [
                "Verificar planos aprobados y estado de expensas o impuestos para agilizar escrituración.",
                "Realizar pequeñas mejoras estéticas (pintura neutra e iluminación cálida).",
                "Fijar precio alineado a la oferta real para no quemar la propiedad en portales."
            ]
        }

    # Intentar con gemini-2.5-flash y fallback inteligente a gemini-3.5-flash-lite
    modelos_a_probar = ['gemini-2.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.8-flash']
    
    for modelo in modelos_a_probar:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            data = json.loads(response.text)
            return data
        except Exception as e:
            print(f"Intento con modelo {modelo} no exitoso: {e}")
            continue
        # En caso de error, calculamos un estimado técnico y devolvemos estructura válida
        m2 = float(datos.get('m2_cubiertos', 50))
        val_base = int(m2 * 1200)
        return {
            "valor_min": int(val_base * 0.9),
            "valor_sugerido": val_base,
            "valor_max": int(val_base * 1.15),
            "valor_m2": 1200,
            "analisis_breve": "Tasación referencial de mercado en base a parámetros inmobiliarios de Córdoba Capital.",
            "consejos": [
                "Contar con informe de dominio e impuestos al día para cerrar operaciones con celeridad.",
                "Optimizar la presentación con fotos profesionales y despersonalización de ambientes.",
                "Iniciar la comercialización en valor competitivo para atraer compradores calificados en los primeros 30 días."
            ]
        }

@app.route("/")
def index():
    return render_template("index.html", mi_whatsapp=MI_WHATSAPP)

@app.route("/api/tasar", methods=["POST"])
def tasar():
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({"error": "No se recibieron datos"}), 400

        # Validaciones básicas
        campos_requeridos = ["tipo", "barrio", "m2_cubiertos", "dormitorios", "estado", "nombre", "telefono", "motivo"]
        for campo in campos_requeridos:
            if not datos.get(campo):
                return jsonify({"error": f"El campo {campo} es obligatorio"}), 400

        # 1. Obtener tasación con Gemini
        tasacion = obtener_tasacion_gemini(datos)

        # 2. Guardar lead en CSV
        try:
            guardar_lead(datos, tasacion.get("valor_sugerido", 0))
        except Exception as e:
            print(f"Error guardando CSV: {e}")

        # 3. Notificar vía WhatsApp (CallMeBot)
        try:
            enviar_notificacion_callmebot(datos, tasacion)
        except Exception as e:
            print(f"Error enviando alerta: {e}")

        return jsonify({
            "success": True,
            "tasacion": tasacion,
            "contacto": {
                "mi_whatsapp": MI_WHATSAPP
            }
        })

    except Exception as e:
        print(f"Error en endpoint /api/tasar: {e}")
        return jsonify({"error": "Ocurrió un error al procesar la tasación"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

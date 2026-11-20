import os
import csv
import json
import io
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
import requests
from google import genai
from google.genai import types
from fpdf import FPDF

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

def limpiar_texto_pdf(texto):
    """Limpia caracteres especiales, emojis o comillas tipográficas para compatibilidad con FPDF latin-1"""
    if not texto:
        return ""
    texto = str(texto)
    reemplazos = {
        "—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'",
        "•": "-", "…": "...", "🔥": "", "👤": "", "📱": "", "🎯": "",
        "🏠": "", "💵": "", "📊": "", "📍": "", "✨": "", "💡": ""
    }
    for orig, dest in reemplazos.items():
        texto = texto.replace(orig, dest)
    # Codificar a latin-1 ignorando caracteres no soportados para evitar crashes
    return texto.encode('latin-1', 'replace').decode('latin-1')

def formatear_usd(valor):
    try:
        return f"{int(valor):,}".replace(",", ".")
    except Exception:
        return str(valor)

@app.route("/descargar-pdf", methods=["POST"])
def descargar_pdf():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No se recibieron datos para el reporte"}), 400

        datos = payload.get("datos", {})
        tasacion = payload.get("tasacion", {})

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()
        pdf.set_margins(12, 10, 12)

        # 1. HEADER (Banda superior azul marino)
        pdf.set_fill_color(15, 23, 42) # Slate 900
        pdf.rect(0, 0, 210, 28, 'F')
        
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_xy(12, 7)
        pdf.cell(0, 7, limpiar_texto_pdf("INFORME DE ESTIMACION DE VALOR DE MERCADO"), ln=1, align="L")
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(147, 197, 253) # Blue 300
        fecha_str = datetime.now().strftime("%d/%m/%Y")
        pdf.set_xy(12, 14)
        pdf.cell(0, 6, limpiar_texto_pdf(f"Cordoba Capital, Argentina | Fecha de emision: {fecha_str} | Ref: INM-COR"), ln=1, align="L")

        # 2. DATOS DEL PROPIETARIO Y PROPIEDAD
        pdf.set_text_color(30, 41, 59)
        pdf.set_xy(12, 32)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(241, 245, 249) # Slate 100
        pdf.cell(186, 6, limpiar_texto_pdf(f" 1. RESUMEN DEL INMUEBLE - PROPIETARIO: {datos.get('nombre', 'Titular')}"), ln=1, fill=True)

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(51, 65, 85)
        
        amenities = datos.get("amenities", [])
        if isinstance(amenities, list):
            amenities_str = ", ".join(amenities) if amenities else "Ninguno reportado"
        else:
            amenities_str = str(amenities) if amenities else "Ninguno reportado"

        col_w = 93
        y_pos = 40
        
        # Fila 1
        pdf.set_xy(12, y_pos)
        pdf.cell(col_w, 5, limpiar_texto_pdf(f"Tipo: {datos.get('tipo', 'Inmueble')}"), ln=0)
        pdf.cell(col_w, 5, limpiar_texto_pdf(f"Barrio: {datos.get('barrio', 'Cordoba')}"), ln=1)
        # Fila 2
        y_pos += 5
        pdf.set_xy(12, y_pos)
        pdf.cell(col_w, 5, limpiar_texto_pdf(f"Superficie: {datos.get('m2_cubiertos')} m2 cubiertos | {datos.get('m2_descubiertos', 0)} m2 patio/balcon"), ln=0)
        pdf.cell(col_w, 5, limpiar_texto_pdf(f"Dormitorios: {datos.get('dormitorios')} | Cochera: {datos.get('cochera')}"), ln=1)
        # Fila 3
        y_pos += 5
        pdf.set_xy(12, y_pos)
        pdf.cell(col_w, 5, limpiar_texto_pdf(f"Antiguedad: {datos.get('antiguedad', 'No especificado')} | Estado: {datos.get('estado', 'Bueno')}"), ln=0)
        pdf.cell(col_w, 5, limpiar_texto_pdf(f"Disposicion: {datos.get('disposicion', 'Frente')}"), ln=1)
        # Fila 4
        y_pos += 5
        pdf.set_xy(12, y_pos)
        pdf.cell(col_w, 5, limpiar_texto_pdf(f"Situacion Juridica: {datos.get('situacion_juridica', 'Escritura')}"), ln=0)
        pdf.cell(col_w, 5, limpiar_texto_pdf(f"Amenities: {amenities_str}"), ln=1)

        # 3. CUADRO DE VALORES EN USD (3 Escenarios de Mercado)
        y_pos += 9
        pdf.set_xy(12, y_pos)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(238, 242, 255) # Indigo 50
        pdf.set_text_color(30, 41, 59)
        pdf.cell(186, 6, limpiar_texto_pdf(" 2. RANGO DE VALUACION ESTIMADA EN DOLARES (USD)"), ln=1, fill=True)

        y_pos += 8
        card_w = 60
        card_h = 24
        
        # Tarjeta Min
        pdf.set_xy(12, y_pos)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(203, 213, 225)
        pdf.rect(12, y_pos, card_w, card_h, 'DF')
        pdf.set_xy(12, y_pos + 2)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(card_w, 4, limpiar_texto_pdf("VALOR CONSERVADOR (Venta Rapida)"), ln=1, align="C")
        pdf.set_xy(12, y_pos + 8)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(51, 65, 85)
        pdf.cell(card_w, 7, f"USD {formatear_usd(tasacion.get('valor_min', 0))}", ln=1, align="C")
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(card_w, 4, limpiar_texto_pdf("Cierre agil / Ofertas contado"), ln=1, align="C")

        # Tarjeta Sugerida (Destacada)
        pdf.set_xy(75, y_pos)
        pdf.set_fill_color(239, 246, 255) # Blue 50
        pdf.set_draw_color(37, 99, 235) # Blue 600
        pdf.rect(75, y_pos, card_w, card_h, 'DF')
        pdf.set_xy(75, y_pos + 2)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(29, 78, 216)
        pdf.cell(card_w, 4, limpiar_texto_pdf("VALOR DE MERCADO SUGERIDO"), ln=1, align="C")
        pdf.set_xy(75, y_pos + 8)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(29, 78, 216)
        pdf.cell(card_w, 7, f"USD {formatear_usd(tasacion.get('valor_sugerido', 0))}", ln=1, align="C")
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(37, 99, 235)
        pdf.cell(card_w, 4, limpiar_texto_pdf("Equilibrio optimo / Tiempo 45-90 dias"), ln=1, align="C")

        # Tarjeta Max
        pdf.set_xy(138, y_pos)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(203, 213, 225)
        pdf.rect(138, y_pos, card_w, card_h, 'DF')
        pdf.set_xy(138, y_pos + 2)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(card_w, 4, limpiar_texto_pdf("VALOR OPTIMISTA (Techo Negociacion)"), ln=1, align="C")
        pdf.set_xy(138, y_pos + 8)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(51, 65, 85)
        pdf.cell(card_w, 7, f"USD {formatear_usd(tasacion.get('valor_max', 0))}", ln=1, align="C")
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(card_w, 4, limpiar_texto_pdf("Comprador especifico / +150 dias"), ln=1, align="C")

        # Cinta informativa m2
        y_pos += card_h + 3
        pdf.set_xy(12, y_pos)
        pdf.set_fill_color(241, 245, 249)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(12, y_pos, 186, 6, 'DF')
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(30, 41, 59)
        pdf.set_xy(15, y_pos + 1)
        pdf.cell(90, 4, limpiar_texto_pdf(f"Valor Promedio Estimado por m2 en la zona: USD {tasacion.get('valor_m2', 0)} / m2"), ln=0)
        pdf.cell(90, 4, limpiar_texto_pdf(f"Ubicacion de Referencia: {datos.get('barrio', 'Cordoba')}"), ln=1, align="R")

        # 4. ANALISIS PROFESIONAL DE MERCADO
        y_pos += 10
        pdf.set_xy(12, y_pos)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(186, 6, limpiar_texto_pdf(" 3. DIAGNOSTICO Y POSICIONAMIENTO EN MERCADO ACTUAL"), ln=1, fill=True)

        y_pos += 8
        pdf.set_xy(12, y_pos)
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(51, 65, 85)
        analisis = tasacion.get("analisis_breve", "Propiedad con parametros acordes al mercado cordobes.")
        pdf.multi_cell(186, 4.5, limpiar_texto_pdf(f'"{analisis}"'))

        # 5. RECOMENDACIONES CLAVE DE EXPERTOS
        y_pos = pdf.get_y() + 4
        pdf.set_xy(12, y_pos)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(241, 245, 249)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(186, 6, limpiar_texto_pdf(" 4. RECOMENDACIONES CLAVE PARA DEFENDER ESTE PRECIO EN CORDOBA"), ln=1, fill=True)

        consejos = tasacion.get("consejos", [])
        y_pos += 8
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(51, 65, 85)
        for i, consejo in enumerate(consejos[:3], start=1):
            pdf.set_xy(12, y_pos)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(6, 4.5, f"{i}.", ln=0)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(180, 4.5, limpiar_texto_pdf(consejo))
            y_pos = pdf.get_y() + 1.5

        # 6. FOOTER Y LLAMADA A LA ACCIÓN (Banda inferior de cierre)
        pdf.set_fill_color(236, 253, 245) # Emerald 50
        pdf.set_draw_color(16, 185, 129) # Emerald 500
        pdf.rect(12, 260, 186, 24, 'DF')

        pdf.set_xy(15, 262)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(6, 95, 70)
        pdf.cell(180, 4.5, limpiar_texto_pdf("IMPORTANTE: CONFIRMACION DE VALOR EXACTO CON VISITA PRESENCIAL"), ln=1, align="C")

        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(4, 120, 87)
        pdf.set_xy(15, 267)
        pdf.cell(180, 4, limpiar_texto_pdf("Este informe es un calculo estadistico. Factores como luminosidad, piso y mantenimiento definen el precio final."), ln=1, align="C")
        
        pdf.set_xy(15, 272)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(6, 78, 59)
        pdf.cell(180, 5, limpiar_texto_pdf(f"Agenda tu visita presencial sin cargo | WhatsApp Directo: +{MI_WHATSAPP}"), ln=1, align="C")

        # Generar buffer en memoria
        buffer = io.BytesIO()
        pdf.output(buffer)
        buffer.seek(0)

        barrio_limpio = "".join(c for c in datos.get("barrio", "Cordoba") if c.isalnum() or c in (' ', '_')).strip().replace(' ', '_')
        filename = f"Informe_Tasacion_{barrio_limpio}.pdf"

        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f"Error generando PDF: {e}")
        return jsonify({"error": f"Error al generar PDF: {str(e)}"}), 500


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
Eres un tasador inmobiliario perito y martillero matriculado de Córdoba Capital y Gran Córdoba, Argentina, con más de 20 años de experiencia cerrando operaciones efectivas en plaza.

REGLA CRUCIAL DE VALUACIÓN:
Debes calcular VALORES REALES DE CIERRE (operaciones efectivas de compraventa cerradas en USD billete), y NO precios inflados de lista o publicación en portales (los cuales en Córdoba suelen estar sobrevaluados entre un 15% y un 25%). La tasación debe ser prudente, precisa y aterrizada a la liquidez real del mercado.

Inmueble a tasar:
- Tipo: {datos.get('tipo')}
- Barrio / Country / Zona: {datos.get('barrio')}
- Metros cuadrados cubiertos: {datos.get('m2_cubiertos')} m²
- Metros cuadrados de balcón / terraza / patio: {datos.get('m2_descubiertos', 0)} m²
- Dormitorios: {datos.get('dormitorios')}
- Cochera: {datos.get('cochera')}
- Estado de conservación: {datos.get('estado')}
- Antigüedad: {datos.get('antiguedad', 'No especificado')}
- Disposición: {datos.get('disposicion', 'No especificado')}
- Situación Jurídica / Título: {datos.get('situacion_juridica', 'No especificado')}
- Amenities destacados: {amenities_str}

REFERENCIAS REALES DE CIERRE POR METRO CUADRADO (USD BILLETE EFECTIVO):
1. DEPARTAMENTOS USADOS ESTÁNDAR (Centro, Alberdi, Cofico, Alta Córdoba, Pueyrredón, San Martín):
   - USD 850 a 1.150 / m² cubierto según estado.
2. DEPARTAMENTOS EN ZONAS DE ALTA DEMANDA (Nueva Córdoba, General Paz, Güemes):
   - Usados consolidados: USD 1.150 a 1.500 / m².
   - A estrenar o categoría alta: USD 1.500 a 1.950 / m².
3. CASAS EN BARRIOS TRADICIONALES (Argüello, Villa Cabrera, Barrio Jardín, Cerro Chico, Poeta Lugones, Urca):
   - USD 750 a 1.100 / m² cubierto (ponderando el terreno en su justa medida sin inflar m² descubiertos).
4. BARRIOS CERRADOS, URBANIZACIONES Y COUNTRIES (Valle Escondido, Docta, Manantiales I y II, Cuesta Colorada, La Calera, La Rufina, Lomas de la Carolina, Las Delicias, Country Jockey Club, Cañuelas, Causana, Q2, Cinco Lomas, Tejas del Sur, Tejas 4):
   - Entre USD 1.100 y 1.750 / m² cubierto según la categoría del country, seguridad y calidad constructiva. En Cuesta Colorada y urbanizaciones abiertas/semicerradas de La Calera promediar entre USD 800 y 1.150 / m² cubierto.

CRITERIOS ESTRICTOS DE CASTIGO Y PONDERACIÓN:
- Antigüedad: +20 años sin reciclar penaliza fuertemente entre un 15% y 25%.
- Cochera: En departamentos de Nueva Córdoba, General Paz o Centro la falta de cochera resta un 10% de competitividad. Si tiene cochera suma USD 8.000 a 14.000 de cierre.
- Disposición: Interno o planta baja sin patio propio castiga un 10% a 15% respecto a frente con balcón.
- Título / Situación: Boleto de compraventa sin escritura inmediata penaliza un 10% a 12% por falta de apto crédito hipotecario Bancor/UVA.
- Brecha de precios: Mantén una brecha estrecha y realista entre 'valor_min' (venta rápida en 30-45 días), 'valor_sugerido' (precio óptimo de mercado para cerrar en 60-90 días) y 'valor_max' (techo máximo de negociación, no más del 8% al 12% por encima del sugerido).

Responde ÚNICAMENTE en formato JSON plano (sin markdown, JSON válido) con esta estructura exacta:
{{
  "valor_min": <entero en USD, valor conservador / venta rápida>,
  "valor_sugerido": <entero en USD, valor promedio de mercado recomendado de cierre>,
  "valor_max": <entero en USD, valor optimista / techo de mercado>,
  "valor_m2": <entero en USD por m² promedio ponderado estimado para la propiedad>,
  "analisis_breve": "<1 o 2 oraciones profesionales explicando el posicionamiento real de cierre en Córdoba/Gran Córdoba>",
  "consejos": [
    "<Consejo 1 específico y accionable para defender el valor en Córdoba>",
    "<Consejo 2 sobre documentación (escritura/apto crédito) o presentación>",
    "<Consejo 3 sobre estrategia de negociación de precio de cierre efectivo>"
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
        y_pos = pdf.get_y() + 3
        pdf.set_xy(12, y_pos)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(241, 245, 249)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(186, 6, limpiar_texto_pdf(" 4. RECOMENDACIONES CLAVE PARA DEFENDER ESTE PRECIO EN CORDOBA"), ln=1, fill=True)

        consejos = tasacion.get("consejos", [])
        y_pos += 7
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(51, 65, 85)
        for i, consejo in enumerate(consejos[:3], start=1):
            pdf.set_xy(12, y_pos)
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.cell(5, 4, f"{i}.", ln=0)
            pdf.set_font("Helvetica", "", 7.5)
            pdf.multi_cell(181, 4, limpiar_texto_pdf(consejo))
            y_pos = pdf.get_y() + 1

        # AVISO LEGAL Y ESTIMACIÓN ORIENTATIVA
        y_pos = max(y_pos + 1, 238)
        pdf.set_xy(12, y_pos)
        pdf.set_fill_color(254, 243, 199) # Amber 100
        pdf.set_draw_color(245, 158, 11) # Amber 500
        pdf.rect(12, y_pos, 186, 17, 'DF')
        pdf.set_xy(14, y_pos + 1.5)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(146, 64, 14) # Amber 800
        pdf.cell(182, 3.5, limpiar_texto_pdf("AVISO DE ESTIMACION ORIENTATIVA:"), ln=1)
        pdf.set_xy(14, y_pos + 5)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(120, 53, 15)
        aviso_legal = "Importante: Esta tasacion es una estimacion preliminar generada por inteligencia artificial en base a promedios estadisticos de la zona. No constituye una tasacion oficial ni un valor definitivo de cierre, ya que factores como la calidad constructiva, luminosidad, entorno inmediato, estado real de conservacion y documentacion pueden modificar el precio final. Para obtener una valoracion exacta y profesional, recomendamos coordinar una visita presencial sin cargo."
        pdf.multi_cell(182, 3.2, limpiar_texto_pdf(aviso_legal))

        # 6. FOOTER Y LLAMADA A LA ACCIÓN (Banda inferior de cierre)
        pdf.set_fill_color(236, 253, 245) # Emerald 50
        pdf.set_draw_color(16, 185, 129) # Emerald 500
        pdf.rect(12, 258, 186, 26, 'DF')

        pdf.set_xy(15, 260)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(6, 95, 70)
        pdf.cell(180, 4.5, limpiar_texto_pdf("COORDINAR TASACION PRESENCIAL EXACTA SIN CARGO"), ln=1, align="C")

        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(4, 120, 87)
        pdf.set_xy(15, 265)
        pdf.cell(180, 4, limpiar_texto_pdf("Inspeccion ocular de terminaciones, estado de conservacion y documentacion para fijar precio final de venta."), ln=1, align="C")
        
        pdf.set_xy(15, 271)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(6, 78, 59)
        pdf.cell(180, 6, limpiar_texto_pdf(f"Agenda tu visita presencial sin cargo | WhatsApp Directo: +{MI_WHATSAPP}"), ln=1, align="C")

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


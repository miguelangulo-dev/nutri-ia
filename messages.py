"""
messages.py — Textos bilingües (ES/EN) y personalidad del bot.

Personalidad: firme, retadora y sin rodeos. Regaña por CONDUCTA (porciones,
constancia, excusas), nunca por el cuerpo de la persona. Ante señales de
riesgo (bajada muy rápida) el bot NO celebra: alerta y deriva.

Si cambias el texto de un aviso legal (privacy, disclaimer, sworn), sube
DISCLAIMER_VERSION en .env: la huella SHA-256 cambiará y quedará registrada.
"""

T: dict[str, dict[str, str]] = {
    # ----- Inicio -----
    "choose_language": {
        "es": (
            "👋 ¡Hola! Soy *Nutri-IA*.\n"
            "Genero *guías nutricionales* de *orientación alimentaria educativa* y hábitos de bienestar. "
            "Su resultado depende 100 % de la veracidad de los datos que captures.\n\n"
            "Hi! I'm *Nutri-IA*.\n"
            "I create *nutrition guides* for *educational food guidance* and wellness habits. "
            "The result depends 100% on the accuracy of the data you enter.\n\n"
            "❌ En el momento que decidas, escribe *CANCELAR* para empezar de nuevo.\n"
            "❌ Whenever you want, type *CANCEL* to start over.\n\n"
            "Elige tu idioma / Choose your language:"
        ),
    },
    "choose_role": {
        "es": "¿Cómo quieres usar Nutri-IA?",
        "en": "How do you want to use Nutri-IA?",
    },
    "role_user": {"es": "Quiero mi guía", "en": "I want my guide"},
    "role_pro": {"es": "Soy profesionista", "en": "I'm a professional"},
    "pro_unavailable": {
        "es": "El canal de profesionistas no está disponible por ahora.",
        "en": "The professional channel is not available right now.",
    },

    # ----- Aviso de privacidad (ANTES de pedir datos sensibles) -----
    "privacy": {
        "es": (
            "🔒 *Aviso de Privacidad*\n"
            "{company} es responsable del uso y protección de tus datos personales.\n\n"
            "Para generar tu guía te pediremos *datos personales sensibles*: edad, sexo, peso, "
            "estatura y cintura. Se guardan *cifrados*, ligados a un alias y no a tu nombre real. "
            "Tu número de WhatsApp también se guarda cifrado y solo se usa para tu seguimiento.\n\n"
            "Puedes ejercer tus derechos ARCO escribiendo a {email}.\n"
            "Aviso completo: {url}\n\n"
            "¿Otorgas tu *consentimiento expreso* para el uso de estos datos?"
        ),
        "en": (
            "🔒 *Privacy Notice*\n"
            "{company} is responsible for processing your personal data.\n\n"
            "To build your guide we will ask for *sensitive personal data*: age, sex, weight, "
            "height and waist. It is stored *encrypted*, linked to an alias, not your real name. "
            "Your WhatsApp number is also encrypted and used only for your follow-up.\n\n"
            "To exercise your data rights, write to {email}.\n"
            "Full notice: {url}\n\n"
            "Do you give your *express consent* to the processing of this data?"
        ),
    },
    "btn_accept": {"es": "Acepto", "en": "I accept"},
    "btn_decline": {"es": "No acepto", "en": "I decline"},
    "privacy_declined": {
        "es": "Entendido. Sin tu consentimiento no podemos generar tu guía. Escribe cualquier mensaje si cambias de opinión.",
        "en": "Understood. Without your consent we can't build your guide. Send any message if you change your mind.",
    },

    # ----- Datos -----
    "ask_alias": {
        "es": "🕶️ ¿Cómo quieres que te llame? Usa un *alias*, no tu nombre real.",
        "en": "🕶️ What should I call you? Use an *alias*, not your real name.",
    },
    "invalid_alias": {
        "es": "Ese alias no sirve. Escribe entre 2 y 40 caracteres.",
        "en": "That alias won't work. Use 2 to 40 characters.",
    },
    "ask_age": {"es": "🎂 ¿Cuántos años tienes?", "en": "🎂 How old are you?"},
    "underage": {
        "es": "Nutri-IA es solo para mayores de {min} años. Acude con un profesional de la salud acompañado de tu madre, padre o tutor.",
        "en": "Nutri-IA is only for people {min} and older. Please see a health professional with your parent or guardian.",
    },
    "age_over": {
        "es": "A partir de los {max} años, la orientación nutricional debe darla un profesional de la salud en consulta. Nutri-IA no puede generar tu guía.",
        "en": "From age {max}, nutrition guidance should come from a health professional in person. Nutri-IA can't build your guide.",
    },
    "ask_sex": {
        "es": "⚧ Sexo biológico (lo pide la fórmula de gasto energético):",
        "en": "⚧ Biological sex (required by the energy formula):",
    },
    "sex_female": {"es": "Mujer", "en": "Female"},
    "sex_male": {"es": "Hombre", "en": "Male"},
    "ask_weight": {
        "es": "⚖️ ¿Cuál es tu peso actual en kg? (ej. 72.5)",
        "en": "⚖️ What is your current weight in kg? (e.g. 72.5)",
    },
    "ask_height": {
        "es": "📏 ¿Cuál es tu estatura en cm? (ej. 168)",
        "en": "📏 What is your height in cm? (e.g. 168)",
    },
    "ask_waist": {
        "es": "📐 ¿Cuánto mide tu cintura en cm? Mide a la altura del ombligo, sin apretar.",
        "en": "📐 What is your waist in cm? Measure at navel level, without squeezing.",
    },
    "invalid_range": {
        "es": "Dato inválido. Escribe un número entre {lo} y {hi} {unit}.",
        "en": "Invalid value. Enter a number between {lo} and {hi} {unit}.",
    },
    "ask_activity": {
        "es": (
            "🏃 *¿Cuánto ejercicio haces a la semana?*\n"
            "Cuenta solo ejercicio real y sostenido. Estirar unos minutos o caminar dentro de casa NO cuenta.\n\n"
            "• *Sedentario:* menos de 60 minutos de ejercicio a la semana / trabajo de oficina.\n"
            "• *Ligero:* de 1 a 3 horas de ejercicio estructurado a la semana (caminar, yoga, cardio suave).\n"
            "• *Moderado:* de 3 a 5 horas de ejercicio a la semana (gym, natación, correr).\n"
            "• *Intenso / Alto rendimiento:* más de 6 horas de entrenamiento pesado o exigente a la semana "
            "(pesas pesadas, deportes competitivos).\n\n"
            "Si dudas entre dos niveles, elige el *menor*."
        ),
        "en": (
            "🏃 *How much exercise do you do per week?*\n"
            "Count only real, sustained exercise. A few minutes of stretching or walking around the house does NOT count.\n\n"
            "• *Sedentary:* less than 60 minutes of exercise per week / office work.\n"
            "• *Light:* 1 to 3 hours of structured exercise per week (walking, yoga, light cardio).\n"
            "• *Moderate:* 3 to 5 hours of exercise per week (gym, swimming, running).\n"
            "• *Intense / High performance:* more than 6 hours of heavy or demanding training per week "
            "(heavy weights, competitive sports).\n\n"
            "If you're between two levels, pick the *lower* one."
        ),
    },
    "btn_options": {"es": "Ver opciones", "en": "See options"},
    "act_sedentary": {"es": "Sedentario (<60 min)", "en": "Sedentary (<60 min)"},
    "act_light": {"es": "Ligero (1-3 h/sem)", "en": "Light (1-3 h/wk)"},
    "act_moderate": {"es": "Moderado (3-5 h/sem)", "en": "Moderate (3-5 h/wk)"},
    "act_intense": {"es": "Intenso (+6 h/sem)", "en": "Intense (6+ h/wk)"},
    "ask_goal": {"es": "🎯 ¿Cuál es tu meta?", "en": "🎯 What's your goal?"},
    "goal_lose": {"es": "Bajar de peso", "en": "Lose weight"},
    "goal_maintain": {"es": "Mantener", "en": "Maintain"},
    "goal_gain": {"es": "Subir de peso", "en": "Gain weight"},
    "low_bmi_maintain": {
        "es": "⚠️ Tu IMC está por debajo del rango saludable. No voy a darte un plan para bajar: tu guía será de *mantenimiento*. Considera consultar a un profesional.",
        "en": "⚠️ Your BMI is below the healthy range. I won't give you a weight-loss plan: your guide will be for *maintenance*. Consider seeing a professional.",
    },

    # ----- Aviso educativo -----
    "disclaimer": {
        "es": (
            "⚠️ *Aviso de orientación alimentaria educativa*\n"
            "Nutri-IA genera una *guía nutricional* de carácter *educativo* y de *hábitos de bienestar*, "
            "basada en El Plato del Bien Comer (NOM-043-SSA2-2012), el Sistema Mexicano de Alimentos "
            "Equivalentes y literatura de referencia en nutrición (Krause; Williams).\n\n"
            "• Es *orientación alimentaria educativa*: *no sustituye* la consulta con un profesional de la salud.\n"
            "• La guía depende *100 % de la veracidad* de los datos que tú captures. Datos falsos o "
            "inexactos generan una guía inadecuada y son tu responsabilidad.\n\n"
            "¿Aceptas estas condiciones?"
        ),
        "en": (
            "⚠️ *Educational food guidance notice*\n"
            "Nutri-IA creates an *educational nutrition guide* focused on *wellness habits*, "
            "based on Mexico's Healthy Eating Plate (NOM-043-SSA2-2012), the Mexican Food Exchange "
            "System and reference nutrition literature (Krause; Williams).\n\n"
            "• It is *educational food guidance*: it does *not replace* a consultation with a health professional.\n"
            "• The guide depends *100% on the accuracy* of the data you enter. False or inaccurate "
            "data produces an unsuitable guide and is your responsibility.\n\n"
            "Do you accept these terms?"
        ),
    },
    "disclaimer_declined": {
        "es": "Sin aceptar el aviso no puedo continuar.",
        "en": "I can't continue unless you accept the notice.",
    },

    # ----- Declaración bajo protesta -----
    "sworn": {
        "es": (
            "📜 *Declaración bajo protesta de decir verdad*\n"
            "¿Tienes actualmente alguna de estas condiciones?\n"
            "• Diabetes o prediabetes\n"
            "• Enfermedad renal, hepática o cardiovascular\n"
            "• Hipertensión no controlada\n"
            "• Cáncer activo\n"
            "• Embarazo o lactancia\n"
            "• Trastorno de la conducta alimentaria (actual o previo)\n"
            "• Cirugía bariátrica o del aparato digestivo\n"
            "• Cualquier condición por la que un profesional de la salud te haya indicado una alimentación especial\n\n"
            "Tu respuesta queda registrada como declaración bajo protesta de decir verdad. "
            "Tu guía depende 100 % de que esta información sea verídica."
        ),
        "en": (
            "📜 *Sworn statement*\n"
            "Do you currently have any of these conditions?\n"
            "• Diabetes or prediabetes\n"
            "• Kidney, liver or cardiovascular disease\n"
            "• Uncontrolled high blood pressure\n"
            "• Active cancer\n"
            "• Pregnancy or breastfeeding\n"
            "• Eating disorder (current or past)\n"
            "• Bariatric or digestive surgery\n"
            "• Any condition for which a health professional advised a special eating plan\n\n"
            "Your answer is recorded as a sworn statement of truth. "
            "Your guide depends 100% on this information being accurate."
        ),
    },
    "btn_yes_cond": {"es": "Sí, tengo alguna", "en": "Yes, I have one"},
    "btn_no_cond": {"es": "No, ninguna", "en": "No, none"},
    "pathology_block": {
        "es": "🛑 Por tu seguridad, Nutri-IA no genera guías con estas condiciones. Necesitas un profesional de la salud con cédula profesional.",
        "en": "🛑 For your safety, Nutri-IA does not build guides for these conditions. You need a licensed health professional.",
    },
    "referral_ask_city": {
        "es": "Te puedo conectar con un especialista verificado. ¿En qué ciudad vives?",
        "en": "I can connect you with a verified specialist. Which city do you live in?",
    },
    "referral_found": {
        "es": "👩‍⚕️ Especialista verificado en tu ciudad:\n*{name}*\n📧 {email}\n💬 {wa}\n\nEscríbele directamente.",
        "en": "👩‍⚕️ Verified specialist in your city:\n*{name}*\n📧 {email}\n💬 {wa}\n\nContact them directly.",
    },
    "referral_none": {
        "es": "Aún no tenemos especialistas verificados en tu ciudad.",
        "en": "We don't have verified specialists in your city yet.",
    },
    "pro_referral_notice": {
        "es": "📥 Nutri-IA te derivó a una persona de {city}. Si te contacta, mencionará que viene de Nutri-IA.",
        "en": "📥 Nutri-IA referred someone from {city} to you. If they reach out, they'll mention Nutri-IA.",
    },

    # ----- Flexi-Menú -----
    "food_intro": {
        "es": "🍽️ Ahora arma tu *Flexi-Menú*. Elige los alimentos que SÍ vas a comer. Toca una opción a la vez y al final *✅ Listo*.",
        "en": "🍽️ Now build your *Flexi-Menu*. Pick the foods you WILL eat. Tap one at a time, then *✅ Done*.",
    },
    "food_protein": {"es": "🥩 *Proteínas*", "en": "🥩 *Proteins*"},
    "food_carb": {"es": "🌾 *Carbohidratos y fibra*", "en": "🌾 *Carbs & fiber*"},
    "food_veg": {
        "es": "🥒 *Verduras de volumen* (colaciones contra la ansiedad)",
        "en": "🥒 *Volume veggies* (anti-craving snacks)",
    },
    "food_flex": {
        "es": "🍔🍻 *Gustos flexibles* (opcional, con moderación)",
        "en": "🍔🍻 *Flexible treats* (optional, in moderation)",
    },
    "food_chosen": {"es": "Elegidos: {items}", "en": "Chosen: {items}"},
    "row_done": {"es": "✅ Listo", "en": "✅ Done"},
    "food_need_one": {
        "es": "Elige al menos una opción de esta categoría.",
        "en": "Pick at least one option in this category.",
    },

    # ----- Pago -----
    "payment_link": {
        "es": (
            "💳 *Último paso.* Tu guía personalizada + {weeks} semanas de check-in cuestan "
            "*{price}* (pago único).\n\nPaga aquí: {url}\n\n"
            "¿Necesitas factura CFDI 4.0? Captura tu RFC en la página de pago.\n"
            "En cuanto se confirme el pago, tu guía llega aquí mismo."
        ),
        "en": (
            "💳 *Last step.* Your personalized guide + {weeks} weeks of check-ins cost "
            "*{price}* (one-time payment).\n\nPay here: {url}\n\n"
            "As soon as the payment is confirmed, your guide arrives right here."
        ),
    },
    "awaiting_payment": {
        "es": "Tu guía se genera en cuanto se confirme tu pago: {url}",
        "en": "Your guide is generated as soon as your payment is confirmed: {url}",
    },
    "payment_ok": {
        "es": "✅ Pago confirmado. Aquí está tu guía. Sin excusas a partir de hoy 👇",
        "en": "✅ Payment confirmed. Here's your guide. No excuses from today on 👇",
    },
    "invoice_pending": {
        "es": "🧾 Recibimos tu solicitud de factura. Para timbrar tu CFDI 4.0 envía a {email}: régimen fiscal, uso de CFDI y código postal fiscal, con el folio *{folio}*.",
        "en": "🧾 We received your invoice request. Email {email} your tax details with reference *{folio}*.",
    },
    "active_status": {
        "es": "Tu guía está activa ✅. Escribe *GUIA* para verla de nuevo. Tu check-in llega cada semana; no lo ignores.",
        "en": "Your guide is active ✅. Type *GUIDE* to see it again. Your check-in arrives every week; don't ignore it.",
    },
    "followup_ended": {
        "es": "Tu periodo de seguimiento terminó. Ya sabes lo que funciona: ahora depende de ti sostenerlo.",
        "en": "Your follow-up period has ended. You know what works: now it's on you to keep it up.",
    },

    # ----- Check-in semanal (personalidad) -----
    "checkin_celebrate": {
        "es": "🔥 ¡ESO ES, {alias}! Avanzaste {delta:.1f} kg hacia tu meta. Esto es disciplina, no suerte. No aflojes: la próxima semana se repite.",
        "en": "🔥 THAT'S IT, {alias}! You moved {delta:.1f} kg toward your goal. That's discipline, not luck. Don't slack: same again next week.",
    },
    "checkin_scold": {
        "es": "😤 {alias}, te moviste {delta:.1f} kg en contra de tu meta. Eso no aparece solo: porciones, gustos flexibles o constancia. Sin excusas: esta semana sigues la guía al gramo.",
        "en": "😤 {alias}, you moved {delta:.1f} kg away from your goal. That doesn't happen by itself: portions, treats or consistency. No excuses: this week you follow the guide to the gram.",
    },
    "checkin_stall": {
        "es": "😐 Mismo peso, {alias}. ¿Seguiste la guía o solo la leíste? Esta semana demuéstralo.",
        "en": "😐 Same weight, {alias}. Did you follow the guide or just read it? Prove it this week.",
    },
    "checkin_hold": {
        "es": "✅ {alias}, mantuviste tu peso (variación de {delta:.1f} kg). Así se sostiene un resultado. Sigue igual.",
        "en": "✅ {alias}, you held your weight ({delta:.1f} kg change). That's how results last. Keep it up.",
    },
    "checkin_off_target": {
        "es": "📏 {alias}, te moviste {delta:.1f} kg y tu meta es mantener. Ajusta porciones y gustos flexibles esta semana.",
        "en": "📏 {alias}, you moved {delta:.1f} kg and your goal is to maintain. Adjust portions and treats this week.",
    },
    "checkin_fast_loss": {
        "es": "⚠️ {alias}, bajaste {delta:.1f} kg en una semana. Es demasiado rápido: no es un logro, es una alerta. Come TODAS las porciones de tu guía. Si sientes debilidad, mareo o falta de energía, consulta a un profesional de la salud.",
        "en": "⚠️ {alias}, you lost {delta:.1f} kg in one week. That's too fast: it's not an achievement, it's a warning. Eat ALL the portions in your guide. If you feel weak, dizzy or low on energy, see a health professional.",
    },

    # ----- Comando CANCELAR -----
    "cancelled": {
        "es": "❌ Proceso cancelado. Los datos que capturaste se descartaron. Empecemos de nuevo 👇",
        "en": "❌ Process canceled. The data you entered was discarded. Let's start over 👇",
    },
    "cancel_checkin": {
        "es": "Check-in cancelado. Tu guía sigue activa; te lo vuelvo a pedir la próxima semana.",
        "en": "Check-in canceled. Your guide is still active; I'll ask again next week.",
    },
    "cancel_paid": {
        "es": "Tu guía ya está pagada, así que no hay nada que cancelar. Escribe *GUIA* para verla.",
        "en": "Your guide is already paid, so there's nothing to cancel. Type *GUIDE* to see it.",
    },

    # ----- General -----
    "blocked": {
        "es": "Nutri-IA no puede atender tu caso. Para dudas escribe a {email}.",
        "en": "Nutri-IA can't handle your case. For questions, write to {email}.",
    },
    "use_buttons": {
        "es": "No entendí. Usa los botones 👇",
        "en": "I didn't get that. Use the buttons 👇",
    },
    "error_generic": {
        "es": "Ocurrió un error. Intenta de nuevo en un momento. / Something went wrong. Please try again shortly.",
    },

    # ----- Canal 2: profesionistas -----
    "pro_ask_name": {
        "es": "👩‍⚕️ Registro de profesionistas. Escribe tu *nombre completo* como aparece en tu cédula.",
        "en": "👩‍⚕️ Professional registration. Enter your *full name* as it appears on your license.",
    },
    "pro_ask_email": {"es": "📧 Tu correo profesional:", "en": "📧 Your professional email:"},
    "invalid_email": {"es": "Correo inválido. Intenta de nuevo.", "en": "Invalid email. Try again."},
    "pro_ask_city": {"es": "📍 ¿En qué ciudad das consulta?", "en": "📍 Which city do you practice in?"},
    "pro_ask_cedula": {
        "es": "🪪 Número de cédula profesional (solo dígitos):",
        "en": "🪪 Professional license number (digits only):",
    },
    "invalid_cedula": {
        "es": "La cédula debe tener entre 7 y 8 dígitos.",
        "en": "The license number must have 7 to 8 digits.",
    },
    "pro_pending": {
        "es": "✅ Datos recibidos. Validaremos tu cédula y te enviaremos el enlace de tu membresía ({price}/mes).",
        "en": "✅ Details received. We'll validate your license and send your membership link ({price}/month).",
    },
    "pro_checkout": {
        "es": "✅ Cédula validada. Activa tu membresía ({price}/mes) aquí: {url}",
        "en": "✅ License validated. Activate your membership ({price}/month) here: {url}",
    },
    "pro_active": {
        "es": "Tu membresía está activa ✅. Recibirás personas derivadas de tu ciudad.",
        "en": "Your membership is active ✅. You'll receive referrals from your city.",
    },
    "pro_past_due": {
        "es": "⚠️ No pudimos cobrar tu membresía. Actualiza tu método de pago para seguir recibiendo derivaciones.",
        "en": "⚠️ We couldn't charge your membership. Update your payment method to keep receiving referrals.",
    },
    "pro_canceled": {
        "es": "Tu membresía fue cancelada. Escribe cualquier mensaje para recibir un enlace y reactivarla.",
        "en": "Your membership was canceled. Send any message to get a link to reactivate it.",
    },
    "pro_rejected": {
        "es": "No pudimos validar tu cédula. Escribe a {email} para revisarlo.",
        "en": "We couldn't validate your license. Write to {email} to review it.",
    },
}


def t(key: str, lang: str, **kw) -> str:
    """Devuelve el texto en el idioma pedido (o español si no existe)."""
    entry = T[key]
    template = entry.get(lang) or entry["es"]
    return template.format(**kw) if kw else template

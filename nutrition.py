"""
nutrition.py — Motor de cálculo nutricional (reglas matemáticas, sin IA).

1. Gasto basal: Mifflin-St Jeor
     Hombre: 10·peso(kg) + 6.25·estatura(cm) − 5·edad + 5
     Mujer:  10·peso(kg) + 6.25·estatura(cm) − 5·edad − 161
2. Gasto total = basal × factor de actividad.
3. Ajuste por meta: bajar −20 % (máx. −500 kcal) · subir +10 % (máx. +300 kcal).
4. Piso calórico de seguridad por sexo (variables MIN_DAILY_KCAL_*).
5. Distribución 50 % HCO / 20 % proteína / 30 % lípidos, convertida a
   equivalentes del SMAE (Sistema Mexicano de Alimentos Equivalentes) y luego
   a gramos de cada alimento elegido.

Los gramos por equivalente son aproximaciones del SMAE (peso cocido salvo
indicación). Revísalos con un nutriólogo antes de producción.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

ACTIVITY_FACTORS = {
    # Rangos semanales definidos en messages.py → ask_activity
    "sedentary": 1.2,    # < 60 min de ejercicio a la semana
    "light": 1.375,      # 1 a 3 h
    "moderate": 1.55,    # 3 a 5 h
    "intense": 1.725,    # > 6 h de entrenamiento pesado
}
SPLIT_CHO, SPLIT_PRO, SPLIT_FAT = 0.50, 0.20, 0.30
FLEX_SHARE = 0.10  # 10 % de la energía semanal reservada a gustos flexibles

# Composición por equivalente SMAE: (kcal, HCO g, proteína g, lípidos g)
EQ = {
    "veg": (25, 4, 2, 0),
    "fruit": (60, 15, 0, 0),
    "legume": (120, 20, 8, 1),
    "carb": (70, 15, 2, 0),       # Cereales y tubérculos sin grasa
    "protein": (55, 0, 7, 3),     # Alimentos de origen animal, bajo aporte de grasa
    "fat": (45, 0, 0, 5),         # Aceites y grasas sin proteína
}


@dataclass(frozen=True)
class Food:
    code: str
    emoji: str
    es: str
    en: str
    grams_per_eq: float | None   # None = libre
    note_es: str = ""
    note_en: str = ""


@dataclass(frozen=True)
class Treat:
    code: str
    emoji: str
    es: str
    en: str
    kcal: int


CATALOG: dict[str, tuple[Food, ...]] = {
    "protein": (
        Food("pollo", "🍗", "Pechuga de pollo", "Chicken breast", 30),
        Food("res", "🥩", "Res magra", "Lean beef", 30),
        Food("huevo", "🥚", "Huevo", "Egg", 50, "1 pieza ≈ 50 g", "1 egg ≈ 50 g"),
        Food("pescado", "🐟", "Filete de pescado", "Fish fillet", 40),
        Food("atun", "🥫", "Atún en agua", "Tuna in water", 30),
        Food("panela", "🧀", "Queso panela", "Panela cheese", 40),
        Food("cerdo", "🍖", "Lomo de cerdo", "Pork loin", 30),
        Food("pavo", "🦃", "Pechuga de pavo", "Turkey breast", 30),
    ),
    "carb": (
        Food("arroz", "🍚", "Arroz cocido", "Cooked rice", 50),
        Food("avena", "🥣", "Avena (cruda)", "Oats (dry)", 20),
        Food("papa", "🥔", "Papa cocida", "Boiled potato", 85),
        Food("tortilla", "🌮", "Tortilla de maíz", "Corn tortilla", 30, "1 pieza ≈ 30 g", "1 piece ≈ 30 g"),
        Food("pan", "🍞", "Pan integral", "Whole-wheat bread", 30, "1 rebanada ≈ 30 g", "1 slice ≈ 30 g"),
        Food("pasta", "🍝", "Pasta cocida", "Cooked pasta", 50),
        Food("camote", "🍠", "Camote cocido", "Cooked sweet potato", 75),
        Food("quinoa", "🌾", "Quinoa cocida", "Cooked quinoa", 70),
    ),
    "veg": (
        Food("pepino", "🥒", "Pepino", "Cucumber", None),
        Food("lechuga", "🥬", "Lechuga", "Lettuce", None),
        Food("apio", "🌿", "Apio", "Celery", None),
        Food("nopal", "🌵", "Nopal", "Nopal cactus", None),
        Food("zanahoria", "🥕", "Zanahoria", "Carrot", 60),
        Food("cebolla", "🧅", "Cebolla", "Onion", 60),
        Food("jitomate", "🍅", "Jitomate", "Tomato", 120),
        Food("brocoli", "🥦", "Brócoli cocido", "Cooked broccoli", 90),
        Food("calabacita", "🫑", "Calabacita", "Zucchini", 120),
    ),
}

TREATS: tuple[Treat, ...] = (
    Treat("hamburguesa", "🍔", "Hamburguesa artesanal", "Craft burger", 750),
    Treat("pizza", "🍕", "Pizza (2 rebanadas)", "Pizza (2 slices)", 570),
    Treat("tacos", "🌮", "Tacos al pastor (3)", "Al pastor tacos (3)", 450),
    Treat("cerveza", "🍺", "Cerveza (355 ml)", "Beer (355 ml)", 150),
    Treat("vino", "🍷", "Copa de vino (150 ml)", "Glass of wine (150 ml)", 125),
)


def menu_items(category: str) -> tuple:
    return TREATS if category == "flex" else CATALOG[category]


def item_title(item: Food | Treat, lang: str) -> str:
    return f"{item.emoji} {item.es if lang == 'es' else item.en}"[:24]


def bmi(weight_kg: float, height_cm: float) -> float:
    return weight_kg / (height_cm / 100) ** 2


def bmr_mifflin(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


def _half(x: float) -> float:
    """Redondea a medio equivalente (0.5)."""
    return max(0.0, round(x * 2) / 2)


def _g5(x: float) -> int:
    """Redondea gramos al múltiplo de 5 más cercano."""
    return int(5 * round(x / 5))


@dataclass
class Plan:
    bmr: int
    tee: int
    kcal: int
    floor_applied: bool
    bmi: float
    whtr: float | None          # Índice cintura/estatura
    goal: str
    eq: dict[str, float]        # Equivalentes diarios por grupo
    choices: dict[str, list[str]]
    flex_weekly_kcal: int


def calculate(
    *, sex: str, age: int, weight_kg: float, height_cm: float, waist_cm: float | None,
    activity: str, goal: str, choices: dict[str, list[str]], kcal_floor: int,
) -> Plan:
    bmr = bmr_mifflin(sex, weight_kg, height_cm, age)
    tee = bmr * ACTIVITY_FACTORS[activity]

    if goal == "lose":
        kcal = tee - min(tee * 0.20, 500)
    elif goal == "gain":
        kcal = tee + min(tee * 0.10, 300)
    else:
        kcal = tee

    floor_applied = kcal < kcal_floor
    kcal = max(kcal, kcal_floor)

    # Grupos fijos (Plato del Bien Comer): verduras, fruta y leguminosas
    eq = {"veg": 4.0, "fruit": 2.0 if kcal < 1800 else 3.0, "legume": 1.0}

    # Cereales cubren el HCO restante
    cho_left = kcal * SPLIT_CHO / 4 - sum(eq[g] * EQ[g][1] for g in ("veg", "fruit", "legume"))
    eq["carb"] = _half(max(3, cho_left / EQ["carb"][1]))

    # Origen animal cubre la proteína restante
    pro_left = kcal * SPLIT_PRO / 4 - sum(eq[g] * EQ[g][2] for g in ("veg", "legume", "carb"))
    eq["protein"] = _half(max(3, pro_left / EQ["protein"][2]))

    # Grasas cubren los lípidos restantes
    fat_left = kcal * SPLIT_FAT / 9 - eq["protein"] * EQ["protein"][3] - eq["legume"] * EQ["legume"][3]
    eq["fat"] = _half(max(2, fat_left / EQ["fat"][3]))

    return Plan(
        bmr=round(bmr),
        tee=round(tee),
        kcal=int(10 * round(kcal / 10)),
        floor_applied=floor_applied,
        bmi=round(bmi(weight_kg, height_cm), 1),
        whtr=round(waist_cm / height_cm, 2) if waist_cm else None,
        goal=goal,
        eq=eq,
        choices={k: list(v) for k, v in choices.items()},
        flex_weekly_kcal=round(kcal * 7 * FLEX_SHARE),
    )


def _treat_frequency(treat: Treat, budget: int, n_treats: int, es: bool) -> str:
    per_week = budget / max(n_treats, 1) / treat.kcal
    if per_week >= 1:
        k = min(math.floor(per_week), 3)
        return f"hasta {k} {'vez' if k == 1 else 'veces'} por semana" if es else f"up to {k}x per week"
    if per_week >= 0.5:
        return "1 vez cada 2 semanas" if es else "once every 2 weeks"
    return "1 vez al mes" if es else "once a month"


def render(plan: Plan, lang: str, alias: str | None) -> str:
    """Texto final de la guía para WhatsApp."""
    es = lang == "es"
    tr = (lambda a, b: a) if es else (lambda a, b: b)
    by_code = {f.code: f for cat in CATALOG.values() for f in cat}
    lines: list[str] = []

    lines.append(tr(f"🥗 *Tu Guía Nutri-IA* — {alias or ''}", f"🥗 *Your Nutri-IA Guide* — {alias or ''}"))
    lines.append(tr(
        f"🔥 Energía diaria: *{plan.kcal} kcal*\n(gasto estimado {plan.tee} kcal · basal {plan.bmr} kcal, Mifflin-St Jeor)",
        f"🔥 Daily energy: *{plan.kcal} kcal*\n(estimated expenditure {plan.tee} kcal · resting {plan.bmr} kcal, Mifflin-St Jeor)",
    ))
    if plan.floor_applied:
        lines.append(tr("🛡️ Ajustada al mínimo de seguridad.", "🛡️ Adjusted to the safety minimum."))
    body = tr(f"📊 IMC: {plan.bmi}", f"📊 BMI: {plan.bmi}")
    if plan.whtr:
        body += tr(f" · Cintura/estatura: {plan.whtr}", f" · Waist-to-height: {plan.whtr}")
        if plan.whtr >= 0.5:
            body += tr(" ⚠️ (≥0.5 se asocia a mayor riesgo cardiometabólico)",
                       " ⚠️ (≥0.5 is linked to higher cardiometabolic risk)")
    lines.append(body)
    lines.append("")
    lines.append(tr("*Porciones diarias* (peso cocido salvo indicación):",
                    "*Daily portions* (cooked weight unless noted):"))

    def food_block(header: str, cat: str) -> None:
        eq = plan.eq[cat]
        lines.append("")
        lines.append(header.format(eq=f"{eq:g}"))
        for code in plan.choices.get(cat, []):
            f = by_code.get(code)
            if not f:
                continue
            name = f.es if es else f.en
            if f.grams_per_eq is None:
                lines.append(tr(f"• {name}: *libre* 🟢", f"• {name}: *unlimited* 🟢"))
            else:
                note = f.note_es if es else f.note_en
                lines.append(f"• {name}: *{_g5(eq * f.grams_per_eq)} g*" + (f" ({note})" if note else ""))

    food_block(tr("🥩 *Proteína* — {eq} porciones. Son intercambiables: elige una o combínalas proporcionalmente.",
                  "🥩 *Protein* — {eq} portions. Interchangeable: pick one or combine proportionally."), "protein")
    food_block(tr("🌾 *Cereales y tubérculos* — {eq} porciones (intercambiables):",
                  "🌾 *Grains & tubers* — {eq} portions (interchangeable):"), "carb")
    lines.append("")
    lines.append(tr(f"🫘 *Leguminosas* — {plan.eq['legume']:g} porción: frijol, lenteja o garbanzo cocidos, 90 g (½ taza)",
                    f"🫘 *Legumes* — {plan.eq['legume']:g} portion: cooked beans, lentils or chickpeas, 90 g (½ cup)"))
    food_block(tr("🥒 *Verduras* — mínimo {eq} porciones (las libres, ideales para colaciones):",
                  "🥒 *Vegetables* — at least {eq} portions (unlimited ones are great snacks):"), "veg")
    lines.append("")
    lines.append(tr(f"🍎 *Fruta* — {plan.eq['fruit']:g} porciones (1 pieza mediana o 1 taza picada c/u)",
                    f"🍎 *Fruit* — {plan.eq['fruit']:g} portions (1 medium piece or 1 cup chopped each)"))
    lines.append(tr(f"🫒 *Grasas* — {plan.eq['fat']:g} porciones (1 cdita de aceite = 5 ml, o 30 g de aguacate c/u)",
                    f"🫒 *Fats* — {plan.eq['fat']:g} portions (1 tsp oil = 5 ml, or 30 g avocado each)"))
    lines.append(tr("💧 Agua simple como bebida principal.", "💧 Plain water as your main drink."))

    treats = [tr_ for tr_ in TREATS if tr_.code in plan.choices.get("flex", [])]
    if treats:
        lines.append("")
        lines.append(tr(f"🍔 *Gustos flexibles* (presupuesto semanal ≈ {plan.flex_weekly_kcal} kcal):",
                        f"🍔 *Flexible treats* (weekly budget ≈ {plan.flex_weekly_kcal} kcal):"))
        for treat in treats:
            freq = _treat_frequency(treat, plan.flex_weekly_kcal, len(treats), es)
            lines.append(f"• {treat.es if es else treat.en}: {freq}")
        lines.append(tr("El día que lo comas, omite los cereales y el aceite de esa comida.",
                        "On that day, skip the grains and oil of that meal."))

    lines.append("")
    lines.append(tr("🕒 Reparte en 3 comidas y hasta 2 colaciones de verduras libres.",
                    "🕒 Split into 3 meals and up to 2 snacks of unlimited veggies."))
    lines.append("")
    lines.append(tr(
        "ℹ️ Orientación alimentaria educativa y de hábitos de bienestar, basada en El Plato del Bien Comer "
        "(NOM-043-SSA2-2012), el SMAE y literatura de referencia en nutrición (Krause; Williams). Depende 100 % "
        "de la veracidad de los datos que capturaste. No sustituye la consulta con un profesional de la salud.",
        "ℹ️ Educational food guidance and wellness habits, based on Mexico's Healthy Eating Plate (NOM-043-SSA2-2012), "
        "the Mexican Food Exchange System and reference nutrition literature (Krause; Williams). It depends 100% on "
        "the accuracy of the data you entered. It does not replace a consultation with a health professional.",
    ))
    return "\n".join(lines)

"""
Seed script — 8 projects matching the frontend mock data (EcoSync ecosystem).

Local:
    python seed.py

Inside Docker:
    docker compose exec api python seed.py
"""

import asyncio
import uuid

from sqlalchemy import delete

from app.database import AsyncSessionLocal, Base, engine
from app.models import Project  # noqa: F401 — registers model on Base.metadata

# ── helpers ───────────────────────────────────────────────────────────────────

def uid() -> str:
    return str(uuid.uuid4())


def ci(text: str) -> dict:
    """Canvas item."""
    return {"id": uid(), "text": text, "is_ai_generated": True}


def ei(idx: int, text: str) -> dict:
    """Empathy item."""
    return {"id": idx, "text": text}


def hyp(h_id: str, text: str, category: str, quadrant: str) -> dict:
    return {"id": h_id, "text": text, "category": category, "quadrant": quadrant}


# ══════════════════════════════════════════════════════════════════════════════
# SHARED BLOCKS — EcoSync (primary project, all mocks point here)
# ══════════════════════════════════════════════════════════════════════════════

ECOSYNC_CANVAS = {
    "key_partners": [
        ci("Local data integrators and ERP vendors"),
        ci("Cloud infrastructure providers (AWS, Azure)"),
        ci("ESG certification bodies (ISO 14064)"),
    ],
    "key_activities": [
        ci("Automated data ingestion and normalization"),
        ci("Real-time carbon footprint calculation engine"),
        ci("Regulatory report generation (CSRD, GRI, CDP)"),
    ],
    "key_resources": [
        ci("Sensor & IoT connectors"),
        ci("ML models for Scope 1/2/3 estimation"),
        ci("Multi-tenant SaaS platform"),
    ],
    "value_propositions": [
        ci("Real-time carbon footprint monitoring for assets"),
        ci("15-minute ESG report instead of 3 days"),
        ci("Audit-ready compliance documentation"),
    ],
    "customer_relationships": [
        ci("Dedicated onboarding and monthly check-ins"),
        ci("In-app guided workflows for sustainability managers"),
        ci("Quarterly ESG benchmarking reports by industry"),
    ],
    "channels": [
        ci("API integrations and one-click export"),
        ci("Direct B2B sales via enterprise AEs"),
        ci("Partner channel through ERP vendors (SAP, Oracle)"),
    ],
    "customer_segments": [
        ci("Mid-market corporate sustainability teams"),
        ci("EU enterprises subject to CSRD directive"),
        ci("Fortune 500 supply chain ESG programs"),
    ],
    "cost_structure": [
        ci("Cloud compute for model training and inference"),
        ci("R&D: connector development and compliance updates"),
        ci("Customer success and onboarding team"),
    ],
    "revenue_streams": [
        ci("Subscription tiers (Core, Pro, Enterprise)"),
        ci("API access for third-party integrations"),
        ci("Professional services: custom ESG frameworks"),
    ],
}

ECOSYNC_EMPATHY_MAP = {
    "uk": {
        "says": [
            ei(1, "Нам потрібно автоматизувати ESG-звітність, щоб уникнути штрафів CSRD"),
            ei(2, "Поточні процеси занадто повільні — ми витрачаємо 3 дні на квартальний звіт"),
            ei(3, "Акціонери вимагають прозорості, а ми досі збираємо дані в Excel"),
        ],
        "thinks": [
            ei(1, "Чи можна реально довіряти точності даних перед аудитом ISO?"),
            ei(2, "Як інтегрувати нову систему з нашим SAP / Oracle ERP без зупинки процесів?"),
            ei(3, "Чи виправдає автоматизація вкладені інвестиції перед фінансовим директором?"),
        ],
        "does": [
            ei(1, "Вручну збирає Excel-таблиці з 8 департаментів щомісяця"),
            ei(2, "Презентує ESG-метрики через статичні PowerPoint-слайди на раді директорів"),
            ei(3, "Координує дані між постачальниками через email-ланцюжки"),
        ],
        "feels": [
            ei(1, "Розгубленість через постійні зміни регуляцій ЄС (CSRD, ESRS)"),
            ei(2, "Фрустрація від закритості департаментів і відсутності єдиного джерела даних"),
            ei(3, "Тиск від топ-менеджменту, який вимагає результатів «вже вчора»"),
        ],
        "pains": [
            ei(1, "Ризик людського фактору: помилки в Excel призводять до хибної звітності"),
            ei(2, "Відсутність real-time CO₂ трекінгу — дані завжди застарілі на місяць"),
            ei(3, "Обмежений бюджет ESG-команди при зростаючих регуляторних вимогах"),
        ],
        "gains": [
            ei(1, "Автоматизація звітів — звільнити 3 дні на квартал для стратегічної роботи"),
            ei(2, "Довести ROI ESG-програми CFO на основі реальних даних платформи"),
            ei(3, "Безшовна API-інтеграція з SAP/Oracle без ручного втручання"),
        ],
    },
    "en": {
        "says": [
            ei(1, "We need to automate ESG reporting to avoid CSRD penalties"),
            ei(2, "Current processes are too slow — we spend 3 days on a quarterly report"),
            ei(3, "Shareholders demand transparency, yet we still collect data in Excel"),
        ],
        "thinks": [
            ei(1, "Can we really trust data accuracy before an ISO audit?"),
            ei(2, "How do we integrate a new system with our SAP / Oracle ERP without disrupting operations?"),
            ei(3, "Will automation justify the investment in front of the CFO?"),
        ],
        "does": [
            ei(1, "Manually consolidates Excel sheets from 8 departments every month"),
            ei(2, "Presents ESG metrics via static PowerPoint slides at board meetings"),
            ei(3, "Coordinates supplier data through email chains"),
        ],
        "feels": [
            ei(1, "Confused by the constant stream of EU regulation changes (CSRD, ESRS)"),
            ei(2, "Frustrated by siloed departments and lack of a single source of truth"),
            ei(3, "Pressured by senior management demanding results immediately"),
        ],
        "pains": [
            ei(1, "Human error risk: Excel mistakes lead to inaccurate disclosures"),
            ei(2, "No real-time CO₂ tracking — data is always one month out of date"),
            ei(3, "Limited ESG team budget against growing regulatory requirements"),
        ],
        "gains": [
            ei(1, "Automated reports — free up 3 days per quarter for strategic work"),
            ei(2, "Prove ESG program ROI to the CFO with real platform data"),
            ei(3, "Seamless API integration with SAP/Oracle without manual intervention"),
        ],
    },
}

ECOSYNC_HYPOTHESES = [
    hyp("H1.1", "Менеджери зі сталого розвитку витрачають 6+ годин/тиждень на ручну агрегацію ESG-даних", "Desirability", "q1"),
    hyp("H1.2", "CFO не можуть обґрунтувати ROI ESG-програми без автоматизованої звітності", "Viability", "q2"),
    hyp("H1.3", "Real-time Scope 3 трекінг технічно реалізований через ERP connector APIs", "Feasibility", "q3"),
    hyp("H2.1", "Дедлайни CSRD (2025) створюють термінований попит на автоматизацію по всьому ЄС", "Desirability", "q1"),
    hyp("H2.2", "Mid-market компанії готові платити €12k–€36k/рік за повну автоматизацію ESG", "Viability", "q2"),
    hyp("H3.1", "ESG-команди хочуть no-code onboarding без залучення IT-департаменту", "Desirability", "q3"),
    hyp("H3.2", "Інтеграція SAP & Oracle можлива без впровадження сторонньої консалтингової фірми", "Feasibility", "q4"),
]

ECOSYNC_PITCH = {
    "uk": {
        "investor": [
            {
                "type": "hook",
                "headline": "$1.2 трлн штрафів очікує компанії ЄС до 2027 року",
                "content": "Директива CSRD зобов'язує 50 000+ компаній автоматизувати ESG-звітність. Ті, хто не встигне — заплатять.",
            },
            {
                "type": "problem",
                "headline": "ESG-звітність досі виглядає як 2005 рік",
                "content": "Команди витрачають 3+ дні на квартал на ручну агрегацію даних у Excel. Помилки, затримки, ризики аудиту.",
            },
            {
                "type": "solution",
                "headline": "EcoSync: від 3 днів до 15 хвилин",
                "content": "Автоматичний збір даних із SAP/Oracle, real-time CO₂ калькулятор та генерація CSRD-звіту одним кліком.",
            },
            {
                "type": "traction",
                "headline": "3 пілоти. €2.1М ARR pipeline. NPS 72.",
                "content": "Пілоти в Henkel, Metinvest, DTEK. Середня економія клієнта — 18 людино-днів на квартал. Churn 0%.",
            },
            {
                "type": "ask",
                "headline": "Залучаємо €4М Series A",
                "content": "Масштабування команди продажів у Німеччині та Польщі, R&D нових ERP-коннекторів, вихід на Fortune 500.",
            },
        ],
        "client": [
            {
                "type": "opening",
                "headline": "Олено, уявіть: кінець кварталу, і у вас ще 3 дні роботи попереду",
                "content": "Три офіси. Вісім постачальників. Сотні рядків у Excel. І дедлайн завтра вранці.",
            },
            {
                "type": "empathy",
                "headline": "Ми розуміємо, як це виглядає зсередини",
                "content": "Координація між департаментами, email-ланцюжки з постачальниками, перевірка формул о 23:00. Це не ваша робота — це баг у системі.",
            },
            {
                "type": "transformation",
                "headline": "15 хвилин замість 3 днів",
                "content": "EcoSync автоматично збирає дані з ваших систем, розраховує Scope 1/2/3 та генерує готовий CSRD-звіт. Ви просто натискаєте «Експортувати».",
            },
            {
                "type": "social_proof",
                "headline": "«Ми скоротили час підготовки звіту з 4 днів до 20 хвилин»",
                "content": "— Head of Sustainability, Fortune 500 хімічна компанія. NPS нашої платформи: 72.",
            },
            {
                "type": "invitation",
                "headline": "Спробуйте безкоштовно 14 днів",
                "content": "Підключіть свій SAP або Oracle за 30 хвилин. Перший автоматичний звіт — сьогодні ввечері.",
            },
        ],
    },
    "en": {
        "investor": [
            {
                "type": "hook",
                "headline": "$1.2 trillion in fines awaits EU companies by 2027",
                "content": "The CSRD directive mandates 50,000+ companies to automate ESG reporting. Those who miss the deadline will pay.",
            },
            {
                "type": "problem",
                "headline": "ESG reporting still looks like 2005",
                "content": "Teams spend 3+ days per quarter manually aggregating data in Excel. Errors, delays, and audit risks follow.",
            },
            {
                "type": "solution",
                "headline": "EcoSync: from 3 days to 15 minutes",
                "content": "Automatic data collection from SAP/Oracle, real-time CO₂ calculator, and one-click CSRD report generation.",
            },
            {
                "type": "traction",
                "headline": "3 pilots. €2.1M ARR pipeline. NPS 72.",
                "content": "Pilots at Henkel, Metinvest, DTEK. Average customer savings: 18 person-days per quarter. Churn: 0%.",
            },
            {
                "type": "ask",
                "headline": "Raising €4M Series A",
                "content": "Scaling sales teams in Germany and Poland, R&D for new ERP connectors, and entering the Fortune 500 segment.",
            },
        ],
        "client": [
            {
                "type": "opening",
                "headline": "Imagine: end of quarter and you still have 3 days of work ahead",
                "content": "Three offices. Eight suppliers. Hundreds of Excel rows. And the deadline is tomorrow morning.",
            },
            {
                "type": "empathy",
                "headline": "We know what this looks like from the inside",
                "content": "Cross-department coordination, supplier email chains, formula checks at 11 PM. This isn't your job — it's a system bug.",
            },
            {
                "type": "transformation",
                "headline": "15 minutes instead of 3 days",
                "content": "EcoSync automatically collects data from your systems, calculates Scope 1/2/3, and generates a ready CSRD report. You just click Export.",
            },
            {
                "type": "social_proof",
                "headline": "\"We cut report preparation from 4 days to 20 minutes\"",
                "content": "— Head of Sustainability, Fortune 500 chemical company. Our platform NPS: 72.",
            },
            {
                "type": "invitation",
                "headline": "Try it free for 14 days",
                "content": "Connect your SAP or Oracle in 30 minutes. First automated report — tonight.",
            },
        ],
    },
}

ECOSYNC_SCENARIO = {
    "uk": {
        "persona": {
            "name": "Олена Морозова",
            "initials": "ОМ",
            "role": "Corporate Sustainability Manager",
            "pain_point": "Щокварталу витрачає 3 дні на консолідацію даних про викиди з 3 офісів",
        },
        "timeline": [
            {"icon_key": "calendar",     "label_key": "scenario.step.context", "text": "Кінець кварталу. Потрібно консолідувати дані про викиди з офісів у Києві, Варшаві та Франкфурті.", "highlight": False},
            {"icon_key": "target",       "label_key": "scenario.step.goal",    "text": "Зібрати Scope 1, 2, 3 дані від 3 офісів і сформувати CSRD-звіт для аудитора до п'ятниці.", "highlight": False},
            {"icon_key": "zap",          "label_key": "scenario.step.action",  "text": "Один клік → EcoSync автоматично підтягує дані з SAP та IoT-сенсорів, розраховує викиди та генерує звіт.", "highlight": True},
            {"icon_key": "check-circle", "label_key": "scenario.step.result",  "text": "Повний CSRD-звіт готовий за 15 хвилин. Олена надсилає його аудитору у вівторок вранці.", "highlight": True},
            {"icon_key": "trending-up",  "label_key": "scenario.step.impact",  "text": "Вивільнені 2.5 дні Олена витрачає на розробку нової ініціативи з декарбонізації ланцюга постачання.", "highlight": False},
        ],
        "metrics": {
            "before": {"value": "3 дні", "label": "Ручне збирання даних у Excel"},
            "after": {"value": "15 хвилин", "label": "Готовий звіт з AI-аналітикою"},
        },
    },
    "en": {
        "persona": {
            "name": "Olena Morozova",
            "initials": "OM",
            "role": "Corporate Sustainability Manager",
            "pain_point": "Spends 3 days every quarter consolidating emissions data from 3 offices",
        },
        "timeline": [
            {"icon_key": "calendar",     "label_key": "scenario.step.context", "text": "End of quarter. Need to consolidate emissions data from offices in Kyiv, Warsaw, and Frankfurt.", "highlight": False},
            {"icon_key": "target",       "label_key": "scenario.step.goal",    "text": "Collect Scope 1, 2, 3 data from 3 offices and generate a CSRD report for the auditor by Friday.", "highlight": False},
            {"icon_key": "zap",          "label_key": "scenario.step.action",  "text": "One click → EcoSync automatically pulls data from SAP and IoT sensors, calculates emissions, and generates the report.", "highlight": True},
            {"icon_key": "check-circle", "label_key": "scenario.step.result",  "text": "Full CSRD report ready in 15 minutes. Olena sends it to the auditor on Tuesday morning.", "highlight": True},
            {"icon_key": "trending-up",  "label_key": "scenario.step.impact",  "text": "Olena uses the freed 2.5 days to develop a new supply chain decarbonization initiative.", "highlight": False},
        ],
        "metrics": {
            "before": {"value": "3 days", "label": "Manual Excel data collection"},
            "after": {"value": "15 minutes", "label": "Ready report with AI analytics"},
        },
    },
}

ECOSYNC_WHAT_IF = {
    "scenarios": [
        {
            "id": uid(),
            "vector": "Financial",
            "color": "indigo",
            "icon": "coins",
            "title": "Що якби ми перейшли на Revenue Share замість підписки?",
            "description": "Замість фіксованої підписки стягувати % від підтвердженої економії клієнта на ESG-аудитах. Це знижує поріг входу та вирівнює інтереси.",
            "value": "Клієнт платить лише коли бачить результат — вища довіра, нижчий churn",
            "revenue": "Потенційний ARPU зростає до €8 000+/рік на великих клієнтах при підтвердженій економії €50k+",
            "status": "applied",
        },
        {
            "id": uid(),
            "vector": "Technical",
            "color": "teal",
            "icon": "cpu",
            "title": "Що якби ми додали on-premise розгортання для regulated industries?",
            "description": "Фінансовий та енергетичний сектор не може передавати ESG-дані в публічний хмарний сервіс. On-premise версія відкриває Enterprise-сегмент.",
            "value": "Доступ до 300+ регульованих компаній ЄС, які зараз заблоковані compliance-вимогами",
            "revenue": "On-premise ліцензія від €24 000/рік — x4 до поточного Enterprise-плану",
            "status": "draft",
        },
        {
            "id": uid(),
            "vector": "Emotional",
            "color": "slate",
            "icon": "heartHandshake",
            "title": "Що якби ми зробили ESG-score публічним і видимим для партнерів?",
            "description": "Публічний ESG-рейтинг компанії у профілі платформи стає інструментом B2B-довіри при тендерах та закупівлях.",
            "value": "Вірусний ефект: кожен клієнт залучає постачальників через вимогу показати ESG-score",
            "revenue": "Нова монетизація: верифікація ESG-score третіх сторін за €299/перевірку",
            "status": "draft",
        },
    ]
}

ECOSYNC_ARCHITECTURE = {
    "epicenter": "finance_driven",
    "epicenter_rationale_uk": "Монетизація та грошові потоки — ключовий рушій моделі. Платформа будується навколо підписки та преміум-апгрейдів, де кожна функція прив'язана до доходу.",
    "epicenter_rationale_en": "Monetization and cash flows are the key drivers of the model. The platform is built around subscriptions and premium upgrades, where every feature is tied to revenue.",
    "pattern": "free",
    "pattern_subtype": "freemium",
    "pattern_rationale_uk": "Безкоштовний базовий план для залучення, преміум-функції конвертують у підписку. Акцент на швидкому onboarding та вірусному поширенні всередині корпорацій.",
    "pattern_rationale_en": "Free basic plan for acquisition, premium features convert to subscriptions. Focus on fast onboarding and viral spread within corporations.",
}

ECOSYNC_MODELS_OPTIONS = {
    "models": [
        {
            "id": uid(),
            "name": "B2B SaaS · EcoSync",
            "tagline": "Підписка + onboarding для команд середнього бізнесу",
            "description": "Щомісячна або річна підписка з диференційованими тарифами. Акцент на швидкому self-serve onboarding без залучення IT. Цільовий сегмент: ESG-команди 200–2000 осіб.",
            "monetization": "subscription",
            "target_segment": "mid-market",
            "key_metric": "MRR / NRR",
            "time_to_value": "30 хвилин до першого звіту",
            "score": 91,
        },
        {
            "id": uid(),
            "name": "Marketplace · EcoSync",
            "tagline": "Транзакційна монетизація для enterprise-екосистеми",
            "description": "Платформа, де ESG-консультанти, верифікатори та постачальники даних пропонують послуги. Комісія 15–20% з кожної транзакції. Цільовий сегмент: enterprise + supply chain.",
            "monetization": "transaction_fee",
            "target_segment": "enterprise",
            "key_metric": "GMV / Take rate",
            "time_to_value": "Перша транзакція за 1–2 тижні",
            "score": 74,
        },
        {
            "id": uid(),
            "name": "Advisory Platform · EcoSync",
            "tagline": "AI-консалтинг та premium-пакети для фаундерів",
            "description": "Поєднання SaaS-інструменту та AI-асистованого консалтингу. Preміум-пакети включають персоналізовані roadmap, виділеного ESG-аналітика та участь у регуляторних слуханнях.",
            "monetization": "retainer_plus_saas",
            "target_segment": "founders_and_cxo",
            "key_metric": "ACV / CSAT",
            "time_to_value": "Перший advisory session за 48 годин",
            "score": 62,
        },
    ],
    "selected_id": None,
}

# ══════════════════════════════════════════════════════════════════════════════
# PROJECT DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

# ── Active projects ───────────────────────────────────────────────────────────

ECOSYNC = Project(
    id=uuid.uuid4(),
    title="EcoSync Platform",
    idea="AI-платформа автоматизації ESG-звітності для корпоративних команд сталого розвитку. Інтегрується з SAP/Oracle, розраховує Scope 1/2/3 та генерує CSRD-звіти за 15 хвилин.",
    status="completed",
    translation_key="project.ecosync",
    models_options=ECOSYNC_MODELS_OPTIONS,
    canvas_data=ECOSYNC_CANVAS,
    empathy_map=ECOSYNC_EMPATHY_MAP,
    hypotheses=ECOSYNC_HYPOTHESES,
    pitch=ECOSYNC_PITCH,
    scenario=ECOSYNC_SCENARIO,
    what_if=ECOSYNC_WHAT_IF,
    architecture=ECOSYNC_ARCHITECTURE,
)

SMART_GRID = Project(
    id=uuid.uuid4(),
    title="Smart Grid Automation",
    idea="IoT-платформа для автоматизації управління електромережами. Передбачає пікові навантаження, оптимізує розподіл енергії та знижує втрати в мережі на 22%.",
    status="completed",
    translation_key="project.smart_grid",
    models_options={
        "models": [
            {"id": uid(), "name": "B2B SaaS · Smart Grid", "tagline": "Підписка для енергетичних операторів", "monetization": "subscription", "score": 88},
            {"id": uid(), "name": "Marketplace · Smart Grid", "tagline": "Платформа для агрегаторів попиту", "monetization": "transaction_fee", "score": 71},
            {"id": uid(), "name": "Advisory Platform · Smart Grid", "tagline": "Consulting для DSO/TSO", "monetization": "retainer_plus_saas", "score": 55},
        ],
        "selected_id": None,
    },
    canvas_data={
        "key_partners": [ci("Distribution system operators (DSO)"), ci("Smart meter manufacturers"), ci("SCADA vendors")],
        "key_activities": [ci("Real-time grid load forecasting"), ci("Automated demand response"), ci("Fault detection and isolation")],
        "key_resources": [ci("IoT edge computing nodes"), ci("Proprietary ML forecasting models"), ci("Grid topology data")],
        "value_propositions": [ci("22% reduction in grid losses"), ci("Predictive maintenance for transformers"), ci("Automated regulatory reporting for ENTSO-E")],
        "customer_relationships": [ci("24/7 NOC support"), ci("Monthly performance reviews with grid operators")],
        "channels": [ci("Direct enterprise sales"), ci("Government procurement tenders"), ci("Energy industry conferences")],
        "customer_segments": [ci("Regional distribution system operators"), ci("Industrial parks with own substations"), ci("Renewable energy aggregators")],
        "cost_structure": [ci("Edge hardware deployment and maintenance"), ci("Cloud ML infrastructure"), ci("Regulatory compliance team")],
        "revenue_streams": [ci("Annual SaaS license per substation"), ci("Performance-based bonus: % of saved losses"), ci("Consulting and integration services")],
    },
    empathy_map={
        "uk": {
            "says": [ei(1, "Нам потрібно знизити втрати в мережі — регулятор вимагає звіти щомісяця"), ei(2, "SCADA-системи не дають прогнозу — тільки факт")],
            "thinks": [ei(1, "Чи витримає IoT-рішення навантаження нашої мережі?"), ei(2, "Як обґрунтувати CAPEX перед держрегулятором?")],
            "does": [ei(1, "Аналізує графіки навантаження вручну в Excel"), ei(2, "Проводить щотижневі наради з операторами підстанцій")],
            "feels": [ei(1, "Тривога через аварійні відключення в пікові години"), ei(2, "Розчарування від застарілої інфраструктури")],
            "pains": [ei(1, "Реактивне обслуговування замість предиктивного"), ei(2, "Відсутність єдиного дашборду по всій мережі")],
            "gains": [ei(1, "Прогноз навантаження за 24 год наперед"), ei(2, "Автоматичне відключення аварійних ділянок")],
        },
        "en": {
            "says": [ei(1, "We need to reduce grid losses — the regulator demands monthly reports"), ei(2, "SCADA systems only show facts, not forecasts")],
            "thinks": [ei(1, "Will the IoT solution handle our grid load?"), ei(2, "How do we justify CAPEX to the regulator?")],
            "does": [ei(1, "Manually analyzes load profiles in Excel"), ei(2, "Holds weekly meetings with substation operators")],
            "feels": [ei(1, "Anxiety over emergency outages during peak hours"), ei(2, "Frustration with aging infrastructure")],
            "pains": [ei(1, "Reactive maintenance instead of predictive"), ei(2, "No single dashboard across the entire grid")],
            "gains": [ei(1, "24-hour-ahead load forecasting"), ei(2, "Automated isolation of faulty grid sections")],
        },
    },
    hypotheses=[
        hyp("H1.1", "Оператори DSO витрачають 8+ год/тиждень на ручний аналіз графіків навантаження", "Desirability", "q1"),
        hyp("H1.2", "Предиктивне обслуговування знижує OPEX трансформаторів на 30%", "Viability", "q1"),
        hyp("H2.1", "IoT-датчики можна встановити без зупинки мережі", "Feasibility", "q2"),
        hyp("H2.2", "Автоматична балансування знижує втрати на 22% у реальних умовах України", "Feasibility", "q3"),
    ],
    pitch={
        "uk": {
            "investor": [
                {"type": "hook", "headline": "Енергосистема України втрачає $400M/рік на технічні втрати в мережі", "content": "22% електроенергії губиться при передачі через застарілу інфраструктуру та відсутність автоматизації."},
                {"type": "solution", "headline": "Smart Grid Automation: IoT + ML для розумної мережі", "content": "Предиктивний контроль навантаження, автоматична ізоляція аварій, єдиний дашборд для оператора."},
                {"type": "traction", "headline": "2 пілоти з Обленерго. €1.8М ARR pipeline.", "content": "Київобленерго та Харківобленерго. Підтверджене зниження втрат на 19% за 3 місяці пілоту."},
                {"type": "ask", "headline": "Залучаємо €3М на масштабування", "content": "Вихід на 5 обленерго у 2025 році та пілот у Польщі (PSE оператор)."},
            ],
            "client": [
                {"type": "opening", "headline": "Андрію, уявіть: понеділок, 18:30, і ваша підстанція №12 знову відключила 3 000 абонентів", "content": "Черговий дзвінок від керівництва. Черговий звіт регулятору. Це відбувається вже третій тиждень поспіль."},
                {"type": "empathy", "headline": "Ми знаємо, як виглядає реактивне управління мережею зсередини", "content": "Диспетчер стежить за SCADA цілодобово, але дізнається про проблему вже після того, як вона сталась. Це не ваша помилка — це обмеження старої системи."},
                {"type": "transformation", "headline": "Попередження за 15 хвилин замість ліквідації аварії", "content": "Smart Grid Automation прогнозує пікові навантаження наперед і автоматично перерозподіляє потужності. Ваш диспетчер отримує сповіщення — і просто підтверджує рішення системи."},
                {"type": "social_proof", "headline": "«Кількість аварійних відключень знизилась з 8 до 1 на місяць за перші 60 днів»", "content": "— Головний інженер, регіональний оператор мережі, Харківська область. Мережеві втрати скорочено на 19%."},
                {"type": "invitation", "headline": "Безкоштовний пілот на 10 підстанцій протягом 30 днів", "content": "Підключення за 3 дні через інтеграцію з вашою SCADA. Перший автоматичний прогноз навантаження — наступного ранку."},
            ],
        },
        "en": {
            "investor": [
                {"type": "hook", "headline": "Ukraine's power grid loses $400M/year in technical losses", "content": "22% of electricity is lost during transmission due to aging infrastructure and lack of automation."},
                {"type": "solution", "headline": "Smart Grid Automation: IoT + ML for intelligent grids", "content": "Predictive load control, automated fault isolation, unified operator dashboard."},
                {"type": "traction", "headline": "2 pilots with regional DSOs. €1.8M ARR pipeline.", "content": "Kyivoblenergo and Kharkivoblenergo. Confirmed 19% loss reduction in 3-month pilot."},
                {"type": "ask", "headline": "Raising €3M to scale", "content": "Expanding to 5 regional DSOs in 2025 and launching a pilot in Poland (PSE operator)."},
            ],
            "client": [
                {"type": "opening", "headline": "Imagine: Monday, 18:30, and substation #12 just cut power to 3,000 subscribers again", "content": "Another call from management. Another report to the regulator. This is the third week in a row."},
                {"type": "empathy", "headline": "We know what reactive grid management looks like from the inside", "content": "Dispatchers watch SCADA around the clock, but only find out about problems after they happen. That's not your failure — it's the limitation of legacy systems."},
                {"type": "transformation", "headline": "15-minute warning instead of post-incident response", "content": "Smart Grid Automation forecasts peak loads in advance and automatically redistributes capacity. Your dispatcher gets a notification and simply confirms the system's decision."},
                {"type": "social_proof", "headline": "\"Emergency outages dropped from 8 to 1 per month in the first 60 days\"", "content": "— Chief Engineer, regional grid operator, Kharkiv region. Grid losses reduced by 19%."},
                {"type": "invitation", "headline": "Free 30-day pilot on 10 substations", "content": "3-day integration with your existing SCADA. First automated load forecast — the next morning."},
            ],
        },
    },
    scenario={
        "uk": {
            "persona": {"name": "Андрій Коваль", "initials": "АК", "role": "Головний інженер регіонального оператора мережі", "pain_point": "Щотижня 2 аварійних відключення через перевантаження підстанцій у піковий час"},
            "timeline": [
                {"icon_key": "calendar",     "label_key": "scenario.step.context", "text": "Підстанція №12 стабільно перевантажується щопонеділка о 18:30 — 2 аварійних відключення на тиждень.", "highlight": False},
                {"icon_key": "target",       "label_key": "scenario.step.goal",    "text": "Запобігти перевантаженню підстанцій у піковий час без ручного втручання диспетчера.", "highlight": False},
                {"icon_key": "zap",          "label_key": "scenario.step.action",  "text": "Smart Grid Automation прогнозує перевантаження за 15 хв та автоматично перерозподіляє навантаження на резервну лінію.", "highlight": True},
                {"icon_key": "check-circle", "label_key": "scenario.step.result",  "text": "Відключення не сталося. Андрій отримує автоматичний звіт о 18:16.", "highlight": True},
                {"icon_key": "trending-up",  "label_key": "scenario.step.impact",  "text": "Кількість аварій знизилася з 2 до 0.2 на тиждень. Мережеві втрати скорочено з 22% до 4%.", "highlight": False},
            ],
            "metrics": {"before": {"value": "2 аварії/тиждень", "label": "Ручне управління підстанціями"}, "after": {"value": "0.2 аварії/тиждень", "label": "Автоматичне балансування навантаження"}},
        },
        "en": {
            "persona": {"name": "Andriy Koval", "initials": "AK", "role": "Chief Engineer, Regional Grid Operator", "pain_point": "2 emergency outages per week due to substation overload during peak hours"},
            "timeline": [
                {"icon_key": "calendar",     "label_key": "scenario.step.context", "text": "Substation #12 consistently overloads every Monday at 18:30 — 2 emergency outages per week.", "highlight": False},
                {"icon_key": "target",       "label_key": "scenario.step.goal",    "text": "Prevent substation overloads during peak hours without manual dispatcher intervention.", "highlight": False},
                {"icon_key": "zap",          "label_key": "scenario.step.action",  "text": "Smart Grid Automation forecasts overload 15 min ahead and automatically redistributes load to the backup line.", "highlight": True},
                {"icon_key": "check-circle", "label_key": "scenario.step.result",  "text": "No outage occurred. Andriy receives an automated report at 18:16.", "highlight": True},
                {"icon_key": "trending-up",  "label_key": "scenario.step.impact",  "text": "Outages reduced from 2 to 0.2 per week. Grid losses cut from 22% to 4%.", "highlight": False},
            ],
            "metrics": {"before": {"value": "2 outages/week", "label": "Manual substation management"}, "after": {"value": "0.2 outages/week", "label": "Automated load balancing"}},
        },
    },
    what_if={
        "scenarios": [
            {"id": uid(), "vector": "Financial", "color": "indigo", "icon": "coins", "title": "Що якби ми перейшли на performance-based pricing?", "description": "Стягувати % від підтвердженої економії замість фіксованої підписки.", "value": "Нижчий поріг входу для нових клієнтів", "revenue": "ARPU зростає пропорційно до цінності для клієнта", "status": "applied"},
            {"id": uid(), "vector": "Technical", "color": "teal", "icon": "cpu", "title": "Що якби додати edge-computing модуль для критичної інфраструктури?", "description": "Обробка даних локально без передачі в хмару для regulated industries.", "value": "Доступ до сегменту з жорсткими data sovereignty вимогами", "revenue": "Edge-ліцензія від €18 000/рік на об'єкт", "status": "draft"},
            {"id": uid(), "vector": "Emotional", "color": "slate", "icon": "heartHandshake", "title": "Що якби зробити публічний дашборд стану мережі для споживачів?", "description": "Прозорість у реальному часі підвищує довіру та знижує кількість дзвінків в підтримку.", "value": "Репутаційна перевага оператора, менше скарг регулятору", "revenue": "Монетизація через рекламу або B2B-дані агрегаторам попиту", "status": "draft"},
        ]
    },
    architecture={
        "epicenter": "resource_driven",
        "epicenter_rationale_uk": "Надійність інфраструктури та операційна ефективність — основа цінності. Платформа будується навколо якості даних та uptime мережі.",
        "epicenter_rationale_en": "Infrastructure reliability and operational efficiency are the core value drivers. The platform is built around data quality and grid uptime.",
        # Was "Multi-sided Platform" + subtype "Freemium" in the old schema — an
        # invalid combination under bizstruct_domain (only free/open_business_model
        # have subtypes). The rationale text is genuinely a freemium tiering
        # story, so reclassified as free/freemium rather than dropping the subtype.
        "pattern": "free",
        "pattern_subtype": "freemium",
        "pattern_rationale_uk": "Базовий моніторинг безкоштовно, предиктивна аналітика — платно. Підключення операторів та регуляторів на одній платформі.",
        "pattern_rationale_en": "Basic monitoring free, predictive analytics paid. Connecting operators and regulators on one platform.",
    },
)

CARBON_TRACK = Project(
    id=uuid.uuid4(),
    title="CarbonTrack IoT",
    idea="Мережа IoT-сенсорів для безперервного моніторингу вуглецевих викидів на виробничих майданчиках у реальному часі. Інтегрується з MES/SCADA та автоматично формує звіти EU ETS.",
    status="completed",
    translation_key="project.carbon_track",
    models_options={
        "models": [
            {"id": uid(), "name": "B2B SaaS · CarbonTrack", "tagline": "Підписка per site для виробників", "monetization": "subscription", "score": 85},
            {"id": uid(), "name": "Marketplace · CarbonTrack", "tagline": "Продаж carbon credits через платформу", "monetization": "transaction_fee", "score": 68},
            {"id": uid(), "name": "Advisory Platform · CarbonTrack", "tagline": "EU ETS compliance consulting", "monetization": "retainer_plus_saas", "score": 59},
        ],
        "selected_id": None,
    },
    canvas_data={
        "key_partners": [ci("Industrial IoT sensor manufacturers (Siemens, Honeywell)"), ci("EU ETS registry operators"), ci("MES/SCADA integration partners")],
        "key_activities": [ci("Continuous emissions monitoring from sensor arrays"), ci("EU ETS compliance calculation and reporting"), ci("Carbon credit allocation optimization")],
        "key_resources": [ci("Certified emissions measurement sensors"), ci("EU ETS calculation engine"), ci("Edge computing modules for factories")],
        "value_propositions": [ci("Real-time factory emissions dashboard"), ci("Automated EU ETS annual reports"), ci("Early warning for emissions quota breaches")],
        "customer_relationships": [ci("Annual compliance audit support"), ci("Dedicated environmental engineer per client")],
        "channels": [ci("Industrial automation trade shows"), ci("Direct to EHS departments of manufacturers"), ci("ERP vendor partnerships (SAP Environment)")],
        "customer_segments": [ci("Heavy industry manufacturers (steel, cement, chemicals)"), ci("Energy-intensive EU facilities under EU ETS"), ci("Export-oriented manufacturers facing CBAM")],
        "cost_structure": [ci("Sensor hardware manufacturing and deployment"), ci("Cloud data processing and storage"), ci("EU regulatory compliance team")],
        "revenue_streams": [ci("Hardware + SaaS bundle: €2k setup + €500/mo"), ci("EU ETS report generation fee per submission"), ci("Carbon credit advisory: % of optimized allocation")],
    },
    empathy_map={
        "uk": {
            "says": [ei(1, "EU ETS квоти закінчуються — нам загрожує штраф €100/тонну CO₂"), ei(2, "Наш EHS-директор витрачає місяць на підготовку річного звіту")],
            "thinks": [ei(1, "Чи акредитовані сенсори для EU ETS верифікації?"), ei(2, "Як CBAM вплине на наш бізнес у 2026 році?")],
            "does": [ei(1, "Замовляє щорічний аудит у зовнішніх верифікаторів за €50k+"), ei(2, "Веде журнали викидів у Excel зі щоденним ручним введенням")],
            "feels": [ei(1, "Страх перед штрафами та репутаційними ризиками"), ei(2, "Невизначеність щодо майбутніх регуляторних змін")],
            "pains": [ei(1, "Ризик перевищення квот через неточний моніторинг"), ei(2, "Висока вартість зовнішньої верифікації викидів")],
            "gains": [ei(1, "Безперервний моніторинг замість щорічного аудиту"), ei(2, "Оптимізація розподілу квот — економія до €200k/рік")],
        },
        "en": {
            "says": [ei(1, "EU ETS quotas are running out — we face a €100/tonne CO₂ fine"), ei(2, "Our EHS director spends a month preparing the annual report")],
            "thinks": [ei(1, "Are the sensors accredited for EU ETS verification?"), ei(2, "How will CBAM affect our business in 2026?")],
            "does": [ei(1, "Commissions annual audits from external verifiers at €50k+"), ei(2, "Maintains emissions logs in Excel with daily manual entry")],
            "feels": [ei(1, "Fear of fines and reputational damage"), ei(2, "Uncertainty about future regulatory changes")],
            "pains": [ei(1, "Risk of quota breach due to inaccurate monitoring"), ei(2, "High cost of external emissions verification")],
            "gains": [ei(1, "Continuous monitoring instead of annual audit"), ei(2, "Quota allocation optimization — savings up to €200k/year")],
        },
    },
    hypotheses=[
        hyp("H1.1", "EHS-менеджери витрачають 20+ людино-днів на підготовку щорічного EU ETS звіту", "Desirability", "q1"),
        hyp("H1.2", "Виробники EU ETS готові платити €500/міс за автоматизацію замість €50k аудиту", "Viability", "q1"),
        hyp("H2.1", "IoT-сенсори з акредитацією EN 14181 можна встановити без зупинки виробництва", "Feasibility", "q2"),
        hyp("H2.2", "CBAM 2026 подвоїть попит на автоматизований моніторинг серед експортерів", "Desirability", "q1"),
    ],
    pitch={
        "uk": {
            "investor": [
                {"type": "hook", "headline": "CBAM 2026: €50B нових штрафів для промисловості ЄС", "content": "Carbon Border Adjustment Mechanism робить точний моніторинг викидів обов'язковим для всіх EU-експортерів."},
                {"type": "solution", "headline": "CarbonTrack IoT: безперервний моніторинг замість щорічного аудиту", "content": "Акредитовані сенсори + MES-інтеграція + автоматичний EU ETS звіт. Від €50k аудиту до €6k/рік."},
                {"type": "traction", "headline": "4 заводи підключено. €980k ARR. Churn 0%.", "content": "Металургія, хімія, цемент. Середня економія клієнта на аудитах: €44k/рік."},
                {"type": "ask", "headline": "Залучаємо €2.5М на сертифікацію EN 14181 та вихід у Польщу/Чехію", "content": "EU ETS охоплює 11 000 установок — TAM €5.5B."},
            ],
            "client": [
                {"type": "opening", "headline": "Дмитре, ваш EU ETS аудит коштує €52k і займає 3 тижні — щороку", "content": "Зовнішній верифікатор приїжджає раз на рік, збирає дані вручну, і виставляє рахунок. А між аудитами ви не знаєте, де стоїте по квотах."},
                {"type": "empathy", "headline": "Compliance заради compliance — це не управління викидами", "content": "Ваша команда витрачає місяць на підготовку документів замість реальної роботи з декарбонізацією. Регулятор вимагає все більше, а інструментів не додається."},
                {"type": "transformation", "headline": "Від щорічного аудиту до real-time моніторингу за €6k/рік", "content": "CarbonTrack IoT встановлює акредитовані сенсори на ваших трубах за 2 дні. EU ETS звіт формується автоматично і відправляється в реєстр одним кліком."},
                {"type": "social_proof", "headline": "«Скасували контракт із аудитором після першого ж автоматичного звіту»", "content": "— EHS Director, металургійний завод, 4 виробничих майданчики. Економія €46k у перший рік."},
                {"type": "invitation", "headline": "Безкоштовна установка сенсорів на 1 майданчику протягом 30 днів", "content": "Якщо перший автоматичний EU ETS звіт не буде прийнятий регулятором — повернемо кошти повністю."},
            ],
        },
        "en": {
            "investor": [
                {"type": "hook", "headline": "CBAM 2026: €50B in new penalties for EU industry", "content": "Carbon Border Adjustment Mechanism makes accurate emissions monitoring mandatory for all EU exporters."},
                {"type": "solution", "headline": "CarbonTrack IoT: continuous monitoring instead of annual audits", "content": "Accredited sensors + MES integration + automatic EU ETS report. From €50k audit to €6k/year."},
                {"type": "traction", "headline": "4 factories connected. €980k ARR. Churn 0%.", "content": "Steel, chemicals, cement. Average client savings on audits: €44k/year."},
                {"type": "ask", "headline": "Raising €2.5M for EN 14181 certification and expansion to Poland/Czech Republic", "content": "EU ETS covers 11,000 installations — TAM €5.5B."},
            ],
            "client": [
                {"type": "opening", "headline": "Your EU ETS audit costs €52k and takes 3 weeks — every single year", "content": "An external verifier shows up once a year, collects data manually, and sends the invoice. Between audits, you have no idea where you stand on quotas."},
                {"type": "empathy", "headline": "Compliance for compliance's sake isn't emissions management", "content": "Your team spends a month preparing documents instead of doing real decarbonization work. Regulators demand more, but the tools don't keep up."},
                {"type": "transformation", "headline": "From annual audit to real-time monitoring for €6k/year", "content": "CarbonTrack IoT installs accredited sensors on your stacks in 2 days. EU ETS reports are generated automatically and submitted to the registry with one click."},
                {"type": "social_proof", "headline": "\"Cancelled the auditor contract after the very first automated report\"", "content": "— EHS Director, steel plant, 4 production sites. €46k savings in year one."},
                {"type": "invitation", "headline": "Free sensor installation on 1 site for 30 days", "content": "If the first automated EU ETS report isn't accepted by the regulator, we'll give you a full refund."},
            ],
        },
    },
    scenario={
        "uk": {
            "persona": {"name": "Дмитро Петренко", "initials": "ДП", "role": "EHS Director, металургійний завод", "pain_point": "Щорічний аудит EU ETS коштує €52k і займає 3 тижні підготовки"},
            "timeline": [
                {"icon_key": "calendar",     "label_key": "scenario.step.context", "text": "Щорічний EU ETS аудит коштує €52k і займає 3 тижні підготовки вручну.", "highlight": False},
                {"icon_key": "target",       "label_key": "scenario.step.goal",    "text": "Автоматизувати моніторинг викидів і скасувати залежність від зовнішнього аудитора.", "highlight": False},
                {"icon_key": "zap",          "label_key": "scenario.step.action",  "text": "Акредитовані IoT-сенсори встановлено за 2 дні. Один клік — EU ETS річний звіт сформовано і відправлено в реєстр.", "highlight": True},
                {"icon_key": "check-circle", "label_key": "scenario.step.result",  "text": "Звіт прийнято регулятором. Дмитро скасував контракт із зовнішнім аудитором — €52k повернулися в бюджет.", "highlight": True},
                {"icon_key": "trending-up",  "label_key": "scenario.step.impact",  "text": "Витрати на compliance знизилися з €52k до €6k/рік. Real-time дашборд показує викиди цілодобово.", "highlight": False},
            ],
            "metrics": {"before": {"value": "€52 000/рік", "label": "Зовнішній аудит EU ETS вручну"}, "after": {"value": "€6 000/рік", "label": "Автоматична звітність через IoT-сенсори"}},
        },
        "en": {
            "persona": {"name": "Dmytro Petrenko", "initials": "DP", "role": "EHS Director, steel plant", "pain_point": "Annual EU ETS audit costs €52k and takes 3 weeks of preparation"},
            "timeline": [
                {"icon_key": "calendar",     "label_key": "scenario.step.context", "text": "Annual EU ETS audit costs €52k and takes 3 weeks of manual preparation.", "highlight": False},
                {"icon_key": "target",       "label_key": "scenario.step.goal",    "text": "Automate emissions monitoring and eliminate dependency on the external auditor.", "highlight": False},
                {"icon_key": "zap",          "label_key": "scenario.step.action",  "text": "Accredited IoT sensors installed in 2 days. One click — EU ETS annual report auto-generated and submitted to registry.", "highlight": True},
                {"icon_key": "check-circle", "label_key": "scenario.step.result",  "text": "Report accepted by regulator. Dmytro cancelled the external auditor contract — €52k returned to the budget.", "highlight": True},
                {"icon_key": "trending-up",  "label_key": "scenario.step.impact",  "text": "Compliance costs reduced from €52k to €6k/year. Real-time dashboard shows emissions 24/7.", "highlight": False},
            ],
            "metrics": {"before": {"value": "€52,000/year", "label": "External EU ETS audit"}, "after": {"value": "€6,000/year", "label": "Automated IoT sensor reporting"}},
        },
    },
    what_if={
        "scenarios": [
            {"id": uid(), "vector": "Financial", "color": "indigo", "icon": "coins", "title": "Що якби ми перейшли на performance-based pricing?", "description": "Стягувати % від підтвердженої економії замість фіксованої підписки.", "value": "Нижчий поріг входу для нових клієнтів", "revenue": "ARPU зростає пропорційно до цінності для клієнта", "status": "applied"},
            {"id": uid(), "vector": "Technical", "color": "teal", "icon": "cpu", "title": "Що якби додати edge-computing модуль для критичної інфраструктури?", "description": "Обробка даних локально без передачі в хмару для regulated industries.", "value": "Доступ до сегменту з жорсткими data sovereignty вимогами", "revenue": "Edge-ліцензія від €18 000/рік на об'єкт", "status": "draft"},
            {"id": uid(), "vector": "Emotional", "color": "slate", "icon": "heartHandshake", "title": "Що якби зробити публічний дашборд стану мережі для споживачів?", "description": "Прозорість у реальному часі підвищує довіру та знижує кількість дзвінків в підтримку.", "value": "Репутаційна перевага оператора, менше скарг регулятору", "revenue": "Монетизація через рекламу або B2B-дані агрегаторам попиту", "status": "draft"},
        ]
    },
    architecture={
        "epicenter": "offer_driven",
        "epicenter_rationale_uk": "Compliance-продукт із чіткою регуляторною цінністю. Пропозиція будується навколо автоматизації EU ETS звітності як основного deliverable.",
        "epicenter_rationale_en": "A compliance product with a clear regulatory value proposition. The offering is built around automating EU ETS reporting as the core deliverable.",
        # Was "Long Tail" + subtype "Bait & Hook" in the old schema — invalid
        # under bizstruct_domain (long_tail has no subtypes). The rationale
        # describes a textbook bait-and-hook story, so reclassified as
        # free/bait_and_hook rather than dropping the subtype.
        "pattern": "free",
        "pattern_subtype": "bait_and_hook",
        "pattern_rationale_uk": "Початкова інсталяція сенсорів як вхідна точка, подальший recurring revenue через SaaS-підписку на аналітику та звітність.",
        "pattern_rationale_en": "Initial sensor installation as the entry point, followed by recurring revenue through SaaS subscription for analytics and reporting.",
    },
)

BIOWASTE = Project(
    id=uuid.uuid4(),
    title="BioWaste Circular",
    idea="Платформа циркулярної економіки для переробки органічних відходів: з'єднує харчові підприємства з біогазовими заводами через маркетплейс залишків і оптимізатор логістики.",
    status="completed",
    translation_key="project.biowaste",
    models_options={
        "models": [
            {"id": uid(), "name": "B2B SaaS · BioWaste Circular", "tagline": "Підписка для харчових підприємств", "monetization": "subscription", "score": 79},
            {"id": uid(), "name": "Marketplace · BioWaste Circular", "tagline": "Комісія з угод на маркетплейсі", "monetization": "transaction_fee", "score": 86},
            {"id": uid(), "name": "Advisory Platform · BioWaste Circular", "tagline": "Circular economy roadmap consulting", "monetization": "retainer_plus_saas", "score": 61},
        ],
        "selected_id": None,
    },
    canvas_data={
        "key_partners": [ci("Biogas plant operators"), ci("Food & beverage manufacturers"), ci("Logistics companies with refrigerated transport"), ci("EU Circular Economy certification bodies")],
        "key_activities": [ci("Waste stream matching between food producers and biogas plants"), ci("Route optimization for organic waste logistics"), ci("Compliance tracking for EU Waste Framework Directive")],
        "key_resources": [ci("Waste exchange marketplace algorithm"), ci("Network of 200+ verified biogas plants"), ci("IoT weight sensors for waste tracking")],
        "value_propositions": [ci("Zero organic waste to landfill — 100% circular"), ci("30% lower waste disposal costs via marketplace"), ci("Automated EU taxonomy compliance documentation")],
        "customer_relationships": [ci("Dedicated circular economy advisor per enterprise client"), ci("Monthly circularity score benchmarking report")],
        "channels": [ci("Food industry trade associations"), ci("Sustainability officers in FMCG companies"), ci("EU Circular Economy Action Plan grants ecosystem")],
        "customer_segments": [ci("Large food & beverage manufacturers (1000+ employees)"), ci("Retail chains with own production facilities"), ci("Municipal organic waste management programs")],
        "cost_structure": [ci("Platform development and marketplace operations"), ci("Logistics optimization engine (routing algorithms)"), ci("Partner biogas plant network development")],
        "revenue_streams": [ci("Marketplace commission: 8% per waste transaction"), ci("SaaS subscription: €799/mo per facility"), ci("EU grant facilitation: 5% of grant value")],
    },
    empathy_map={
        "uk": {
            "says": [ei(1, "Ми платимо €80k/рік за вивіз органіки на полігон — це нераціонально"), ei(2, "Регулятор вже питає про нашу стратегію нульових відходів")],
            "thinks": [ei(1, "Чи надійні біогазові заводи-партнери? Де гарантія якості?"), ei(2, "Як довести ROI переходу на циркулярну модель CFO?")],
            "does": [ei(1, "Укладає окремі контракти з кількома переробниками вручну"), ei(2, "Готує щорічний EU taxonomy sound alignment звіт у консультантів")],
            "feels": [ei(1, "Тиск від ESG-рейтингів та закупівельних вимог великих рітейлерів"), ei(2, "Невизначеність щодо майбутніх штрафів за EU Waste Directive")],
            "pains": [ei(1, "Складна логістика: хтось забирає відходи, але не завжди вчасно"), ei(2, "Відсутність автоматичної документації для EU taxonomy")],
            "gains": [ei(1, "Зниження витрат на утилізацію відходів на 30%"), ei(2, "Готова EU taxonomy-документація для ESG-звіту")],
        },
        "en": {
            "says": [ei(1, "We pay €80k/year to send organics to landfill — that's irrational"), ei(2, "The regulator is already asking about our zero-waste strategy")],
            "thinks": [ei(1, "Are the biogas plant partners reliable? Where's the quality guarantee?"), ei(2, "How do I prove the ROI of going circular to the CFO?")],
            "does": [ei(1, "Signs separate contracts with multiple recyclers manually"), ei(2, "Hires consultants to prepare the annual EU taxonomy alignment report")],
            "feels": [ei(1, "Pressure from ESG ratings and procurement requirements of large retailers"), ei(2, "Uncertainty about future EU Waste Directive penalties")],
            "pains": [ei(1, "Logistics complexity: someone picks up waste, but not always on time"), ei(2, "No automatic documentation for EU taxonomy")],
            "gains": [ei(1, "30% reduction in waste disposal costs"), ei(2, "Ready EU taxonomy documentation for ESG report")],
        },
    },
    hypotheses=[
        hyp("H1.1", "Харчові підприємства готові перейти на маркетплейс замість прямих контрактів з переробниками", "Desirability", "q1"),
        hyp("H1.2", "Комісія 8% з угод забезпечить беззбитковість маркетплейсу при GMV €2M/міс", "Viability", "q2"),
        hyp("H2.1", "Алгоритм маршрутизації знизить логістичні витрати на 30% порівняно з прямими контрактами", "Feasibility", "q2"),
        hyp("H2.2", "EU taxonomy автодокументація підвищить NPS серед enterprise-клієнтів до 65+", "Desirability", "q3"),
    ],
    pitch={
        "uk": {
            "investor": [
                {"type": "hook", "headline": "€140B органічних відходів на звалищах ЄС щороку", "content": "EU Waste Framework Directive забороняє органіку на полігонах з 2027 року. Всі харчові підприємства мусять знайти альтернативу."},
                {"type": "solution", "headline": "BioWaste Circular: маркетплейс органічних відходів", "content": "З'єднуємо 5 000+ харчових підприємств з мережею біогазових заводів. Оптимізований підбір партнера + логістика + EU-документація автоматично."},
                {"type": "traction", "headline": "180 підключених підприємств. GMV €1.2М. NPS 68.", "content": "Середнє зниження витрат клієнта: €31k/рік. Churn 3%. 94% клієнтів продовжили підписку."},
                {"type": "ask", "headline": "Залучаємо €1.8М на розширення мережі біогазових заводів у Польщі та Румунії", "content": "EU Waste Directive TAM: €8B у Центральній Європі до 2027."},
            ],
            "client": [
                {"type": "opening", "headline": "Наталіє, €80k на рік за вивіз органіки на полігон — і жодної EU taxonomy документації", "content": "Шість окремих контрактів з переробниками, координація через email, і щороку консультанти за €15k для підготовки ESG-звіту."},
                {"type": "empathy", "headline": "Циркулярна економіка на папері, хаос у логістиці на практиці", "content": "Знайти надійного біогазового партнера — це тижні переговорів. Відстежити статус вивозу — дзвінок водієві. Документація для EU taxonomy — окремий проєкт наприкінці року."},
                {"type": "transformation", "headline": "Надійний партнер за 5 хвилин, EU taxonomy — автоматично", "content": "BioWaste Circular підбирає верифікованих біогазових партнерів поруч із вашим виробництвом, оформляє контракт онлайн і оновлює EU taxonomy документацію після кожної транзакції."},
                {"type": "social_proof", "headline": "«Знизили витрати на утилізацію з €80k до €54k і нарешті отримали EU taxonomy без консультантів»", "content": "— Head of Sustainability, харчовий холдинг, 3 виробничі майданчики. Економія €26k у перший рік + €15k на консалтингу."},
                {"type": "invitation", "headline": "Безкоштовно підключіться та знайдіть першого партнера цього тижня", "content": "Реєстрація займає 10 хвилин. Перший підібраний партнер і попередня ціна — протягом 24 годин. Без зобов'язань."},
            ],
        },
        "en": {
            "investor": [
                {"type": "hook", "headline": "€140B in organic waste going to EU landfills every year", "content": "The EU Waste Framework Directive bans organics from landfills from 2027. All food companies must find an alternative."},
                {"type": "solution", "headline": "BioWaste Circular: organic waste marketplace", "content": "Connecting 5,000+ food companies with a network of biogas plants. Optimized partner matching + logistics + EU documentation automatically."},
                {"type": "traction", "headline": "180 connected companies. GMV €1.2M. NPS 68.", "content": "Average client cost reduction: €31k/year. Churn 3%. 94% of clients renewed subscriptions."},
                {"type": "ask", "headline": "Raising €1.8M to expand biogas plant network in Poland and Romania", "content": "EU Waste Directive TAM: €8B in Central Europe by 2027."},
            ],
            "client": [
                {"type": "opening", "headline": "€80k a year for organic waste disposal — and zero EU taxonomy documentation", "content": "Six separate contracts with recyclers, email coordination, and consultants at €15k every year just to prepare the ESG report."},
                {"type": "empathy", "headline": "Circular economy on paper, logistics chaos in practice", "content": "Finding a reliable biogas partner takes weeks of negotiations. Tracking pickup status means calling the driver. EU taxonomy documentation is a separate year-end project."},
                {"type": "transformation", "headline": "A verified partner in 5 minutes, EU taxonomy updated automatically", "content": "BioWaste Circular matches verified biogas partners near your facility, handles the contract online, and updates EU taxonomy documentation after every transaction."},
                {"type": "social_proof", "headline": "\"Cut disposal costs from €80k to €54k and finally got EU taxonomy without consultants\"", "content": "— Head of Sustainability, food holding, 3 production sites. €26k saved in year one + €15k on consulting."},
                {"type": "invitation", "headline": "Sign up free and find your first partner this week", "content": "Registration takes 10 minutes. First matched partner and indicative price — within 24 hours. No commitment required."},
            ],
        },
    },
    scenario={
        "uk": {
            "persona": {"name": "Наталія Бондар", "initials": "НБ", "role": "Head of Sustainability, харчовий холдинг", "pain_point": "Платить €80k/рік за вивіз органіки та не має документації для EU taxonomy"},
            "timeline": [
                {"icon_key": "calendar",     "label_key": "scenario.step.context", "text": "Наталія платить €80k/рік за вивіз органіки на полігон і не має EU taxonomy документації.", "highlight": False},
                {"icon_key": "target",       "label_key": "scenario.step.goal",    "text": "Знайти надійного біогазового партнера, скоротити витрати та автоматизувати EU taxonomy звітність.", "highlight": False},
                {"icon_key": "zap",          "label_key": "scenario.step.action",  "text": "BioWaste Circular підібрав 3 партнери за 5 хвилин. Контракт підписано онлайн, логістика — автоматична.", "highlight": True},
                {"icon_key": "check-circle", "label_key": "scenario.step.result",  "text": "EU taxonomy звіт оновився автоматично після першої транзакції. Готовий до аудиту.", "highlight": True},
                {"icon_key": "trending-up",  "label_key": "scenario.step.impact",  "text": "Витрати на утилізацію знизилися з €80k до €54k/рік. Наталія отримала EU taxonomy документацію без жодного консультанта.", "highlight": False},
            ],
            "metrics": {"before": {"value": "€80 000/рік", "label": "Вивіз органіки на полігон вручну"}, "after": {"value": "€54 000/рік", "label": "Автоматичний підбір біогазового партнера"}},
        },
        "en": {
            "persona": {"name": "Natalia Bondar", "initials": "NB", "role": "Head of Sustainability, food holding", "pain_point": "Pays €80k/year for organic waste removal with no EU taxonomy documentation"},
            "timeline": [
                {"icon_key": "calendar",     "label_key": "scenario.step.context", "text": "Natalia pays €80k/year for organic waste disposal with no EU taxonomy documentation.", "highlight": False},
                {"icon_key": "target",       "label_key": "scenario.step.goal",    "text": "Find a reliable biogas partner, cut disposal costs, and automate EU taxonomy reporting.", "highlight": False},
                {"icon_key": "zap",          "label_key": "scenario.step.action",  "text": "BioWaste Circular matched 3 partners in 5 minutes. Contract signed online, logistics automated.", "highlight": True},
                {"icon_key": "check-circle", "label_key": "scenario.step.result",  "text": "EU taxonomy report updated automatically after the first transaction. Audit-ready.", "highlight": True},
                {"icon_key": "trending-up",  "label_key": "scenario.step.impact",  "text": "Disposal costs dropped from €80k to €54k/year. Natalia got full EU taxonomy documentation without a single consultant.", "highlight": False},
            ],
            "metrics": {"before": {"value": "€80,000/year", "label": "Manual organic waste to landfill"}, "after": {"value": "€54,000/year", "label": "Automated biogas partner matching"}},
        },
    },
    what_if={
        "scenarios": [
            {"id": uid(), "vector": "Financial", "color": "indigo", "icon": "coins", "title": "Що якби ми перейшли на performance-based pricing?", "description": "Стягувати % від підтвердженої економії замість фіксованої підписки.", "value": "Нижчий поріг входу для нових клієнтів", "revenue": "ARPU зростає пропорційно до цінності для клієнта", "status": "applied"},
            {"id": uid(), "vector": "Technical", "color": "teal", "icon": "cpu", "title": "Що якби додати edge-computing модуль для критичної інфраструктури?", "description": "Обробка даних локально без передачі в хмару для regulated industries.", "value": "Доступ до сегменту з жорсткими data sovereignty вимогами", "revenue": "Edge-ліцензія від €18 000/рік на об'єкт", "status": "draft"},
            {"id": uid(), "vector": "Emotional", "color": "slate", "icon": "heartHandshake", "title": "Що якби зробити публічний дашборд стану мережі для споживачів?", "description": "Прозорість у реальному часі підвищує довіру та знижує кількість дзвінків в підтримку.", "value": "Репутаційна перевага оператора, менше скарг регулятору", "revenue": "Монетизація через рекламу або B2B-дані агрегаторам попиту", "status": "draft"},
        ]
    },
    architecture={
        "epicenter": "customer_driven",
        "epicenter_rationale_uk": "Харчові підприємства — центр екосистеми. Платформа будується навколо їхнього бажання знизити витрати та отримати EU taxonomy документацію без зусиль.",
        "epicenter_rationale_en": "Food companies are at the center of the ecosystem. The platform is built around their desire to cut costs and get EU taxonomy documentation effortlessly.",
        # Was "Open Business Model" + subtype "Ad-supported" in the old schema —
        # invalid under bizstruct_domain (ad_supported is a subtype of free,
        # not open_business_model). The rationale describes a two-sided
        # marketplace monetized by transaction commission, which is a
        # multi_sided_platform story, not free or open_business_model — and
        # multi_sided_platform takes no subtype.
        "pattern": "multi_sided_platform",
        "pattern_subtype": None,
        "pattern_rationale_uk": "Вільна реєстрація для харчових підприємств і біогазових заводів, монетизація через комісію 8% з кожної угоди на маркетплейсі.",
        "pattern_rationale_en": "Free registration for food companies and biogas plants, monetization through 8% commission on each marketplace transaction.",
    },
)

# ── Archived projects ─────────────────────────────────────────────────────────

def _archived(title: str, idea: str, key: str) -> Project:
    """Minimal archived project — has canvas and hypotheses, rest null."""
    return Project(
        id=uuid.uuid4(),
        title=title,
        idea=idea,
        status="archived",
        translation_key=key,
        models_options={
            "models": [
                {"id": uid(), "name": f"B2B SaaS · {title}", "tagline": "Підписка", "monetization": "subscription", "score": 72},
                {"id": uid(), "name": f"Marketplace · {title}", "tagline": "Транзакційна монетизація", "monetization": "transaction_fee", "score": 58},
                {"id": uid(), "name": f"Advisory Platform · {title}", "tagline": "Консалтинг", "monetization": "retainer_plus_saas", "score": 45},
            ],
            "selected_id": None,
        },
        canvas_data={
            "key_partners": [ci("Technology vendors"), ci("Industry associations")],
            "key_activities": [ci("Platform development"), ci("Customer onboarding")],
            "key_resources": [ci("Engineering team"), ci("Proprietary data")],
            "value_propositions": [ci("Automation of manual processes"), ci("Real-time analytics")],
            "customer_relationships": [ci("Dedicated account management")],
            "channels": [ci("Direct sales"), ci("Partner network")],
            "customer_segments": [ci("Mid-market B2B")],
            "cost_structure": [ci("Engineering and infrastructure")],
            "revenue_streams": [ci("Subscription revenue")],
        },
        hypotheses=[
            hyp("H1.1", "Target users spend 5+ hours/week on manual tasks this product automates", "Desirability", "q1"),
            hyp("H1.2", "Willingness to pay exceeds €500/month for the core use case", "Viability", "q2"),
        ],
        empathy_map=None,
        pitch=None,
        scenario=None,
        what_if=None,
        architecture=None,
    )


ECOSYNC_LEGACY = _archived(
    "EcoSync Legacy",
    "Перша версія EcoSync — монолітний веб-додаток для ручного введення ESG-даних. Замінений поточною платформою з автоматичною інтеграцією.",
    "project.ecosync_legacy",
)

GRIDWATCH_PRO = _archived(
    "GridWatch Pro",
    "Ранній прототип системи моніторингу електромереж без ML-компоненту. Замінений Smart Grid Automation із предиктивною аналітикою.",
    "project.gridwatch_pro",
)

CARBON_LENS = _archived(
    "CarbonLens",
    "MVP для ручного розрахунку вуглецевого сліду через веб-форми. Концептуально замінений CarbonTrack IoT із сенсорним моніторингом.",
    "project.carbon_lens",
)

WASTE_LOOP = _archived(
    "WasteLoop Analytics",
    "Аналітичний дашборд для відстеження відходів без функції маркетплейсу. Попередник BioWaste Circular.",
    "project.waste_loop",
)

# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

ALL_PROJECTS = [
    ECOSYNC, SMART_GRID, CARBON_TRACK, BIOWASTE,
    ECOSYNC_LEGACY, GRIDWATCH_PRO, CARBON_LENS, WASTE_LOOP,
]

SEED_TITLES = {p.title for p in ALL_PROJECTS}


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for title in SEED_TITLES:
            await session.execute(delete(Project).where(Project.title == title))

        session.add_all(ALL_PROJECTS)
        await session.commit()

    await engine.dispose()

    active = sum(1 for p in ALL_PROJECTS if p.status != "archived")
    archived = len(ALL_PROJECTS) - active
    print(f"Seed complete — {active} active + {archived} archived projects inserted.")


if __name__ == "__main__":
    asyncio.run(seed())

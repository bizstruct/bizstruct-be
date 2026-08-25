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
    "says": [
        {"id": 1, "text_uk": "Нам потрібно автоматизувати ESG-звітність, щоб уникнути штрафів CSRD", "text_en": "We need to automate ESG reporting to avoid CSRD penalties"},
        {"id": 2, "text_uk": "Поточні процеси занадто повільні — ми витрачаємо 3 дні на квартальний звіт", "text_en": "Current processes are too slow — we spend 3 days on a quarterly report"},
        {"id": 3, "text_uk": "Акціонери вимагають прозорості, а ми досі збираємо дані в Excel", "text_en": "Shareholders demand transparency, yet we still collect data in Excel"},
    ],
    "thinks": [
        {"id": 1, "text_uk": "Чи можна реально довіряти точності даних перед аудитом ISO?", "text_en": "Can we really trust data accuracy before an ISO audit?"},
        {"id": 2, "text_uk": "Як інтегрувати нову систему з нашим SAP / Oracle ERP без зупинки процесів?", "text_en": "How do we integrate a new system with our SAP / Oracle ERP without disrupting operations?"},
        {"id": 3, "text_uk": "Чи виправдає автоматизація вкладені інвестиції перед фінансовим директором?", "text_en": "Will automation justify the investment in front of the CFO?"},
    ],
    "does": [
        {"id": 1, "text_uk": "Вручну збирає Excel-таблиці з 8 департаментів щомісяця", "text_en": "Manually consolidates Excel sheets from 8 departments every month"},
        {"id": 2, "text_uk": "Презентує ESG-метрики через статичні PowerPoint-слайди на раді директорів", "text_en": "Presents ESG metrics via static PowerPoint slides at board meetings"},
        {"id": 3, "text_uk": "Координує дані між постачальниками через email-ланцюжки", "text_en": "Coordinates supplier data through email chains"},
    ],
    "feels": [
        {"id": 1, "text_uk": "Розгубленість через постійні зміни регуляцій ЄС (CSRD, ESRS)", "text_en": "Confused by the constant stream of EU regulation changes (CSRD, ESRS)"},
        {"id": 2, "text_uk": "Фрустрація від закритості департаментів і відсутності єдиного джерела даних", "text_en": "Frustrated by siloed departments and lack of a single source of truth"},
        {"id": 3, "text_uk": "Тиск від топ-менеджменту, який вимагає результатів «вже вчора»", "text_en": "Pressured by senior management demanding results immediately"},
    ],
    "pains": [
        {"id": 1, "text_uk": "Ризик людського фактору: помилки в Excel призводять до хибної звітності", "text_en": "Human error risk: Excel mistakes lead to inaccurate disclosures"},
        {"id": 2, "text_uk": "Відсутність real-time CO₂ трекінгу — дані завжди застарілі на місяць", "text_en": "No real-time CO₂ tracking — data is always one month out of date"},
        {"id": 3, "text_uk": "Обмежений бюджет ESG-команди при зростаючих регуляторних вимогах", "text_en": "Limited ESG team budget against growing regulatory requirements"},
    ],
    "gains": [
        {"id": 1, "text_uk": "Автоматизація звітів — звільнити 3 дні на квартал для стратегічної роботи", "text_en": "Automated reports — free up 3 days per quarter for strategic work"},
        {"id": 2, "text_uk": "Довести ROI ESG-програми CFO на основі реальних даних платформи", "text_en": "Prove ESG program ROI to the CFO with real platform data"},
        {"id": 3, "text_uk": "Безшовна API-інтеграція з SAP/Oracle без ручного втручання", "text_en": "Seamless API integration with SAP/Oracle without manual intervention"},
    ],
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
    "persona": {
        "name_uk": 'Олена Морозова',
        "name_en": 'Olena Morozova',
        "role_uk": 'Corporate Sustainability Manager',
        "role_en": 'Corporate Sustainability Manager',
        "pain_point_uk": 'Щокварталу витрачає 3 дні на консолідацію даних про викиди з 3 офісів',
        "pain_point_en": 'Spends 3 days every quarter consolidating emissions data from 3 offices',
    },
    "timeline": [
        {
            "step_type": 'context',
            "icon_key": 'calendar',
            "text_uk": 'Кінець кварталу. Потрібно консолідувати дані про викиди з офісів у Києві, Варшаві та Франкфурті.',
            "text_en": 'End of quarter. Need to consolidate emissions data from offices in Kyiv, Warsaw, and Frankfurt.',
        },
        {
            "step_type": 'goal',
            "icon_key": 'target',
            "text_uk": "Зібрати Scope 1, 2, 3 дані від 3 офісів і сформувати CSRD-звіт для аудитора до п'ятниці.",
            "text_en": 'Collect Scope 1, 2, 3 data from 3 offices and generate a CSRD report for the auditor by Friday.',
        },
        {
            "step_type": 'action',
            "icon_key": 'zap',
            "text_uk": 'Один клік → EcoSync автоматично підтягує дані з SAP та IoT-сенсорів, розраховує викиди та генерує звіт.',
            "text_en": 'One click → EcoSync automatically pulls data from SAP and IoT sensors, calculates emissions, and generates the report.',
        },
        {
            "step_type": 'result',
            "icon_key": 'check-circle',
            "text_uk": 'Повний CSRD-звіт готовий за 15 хвилин. Олена надсилає його аудитору у вівторок вранці.',
            "text_en": 'Full CSRD report ready in 15 minutes. Olena sends it to the auditor on Tuesday morning.',
        },
        {
            "step_type": 'impact',
            "icon_key": 'trending-up',
            "text_uk": 'Вивільнені 2.5 дні Олена витрачає на розробку нової ініціативи з декарбонізації ланцюга постачання.',
            "text_en": 'Olena uses the freed 2.5 days to develop a new supply chain decarbonization initiative.',
        },
    ],
    "metrics": {
        "before": {
            "value_uk": '3 дні',
            "value_en": '3 days',
            "label_uk": 'Ручне збирання даних у Excel',
            "label_en": 'Manual Excel data collection',
        },
        "after": {
            "value_uk": '15 хвилин',
            "value_en": '15 minutes',
            "label_uk": 'Готовий звіт з AI-аналітикою',
            "label_en": 'Ready report with AI analytics',
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
    "says": [
        {"id": 1, "text_uk": "Нам потрібно знизити втрати в мережі — регулятор вимагає звіти щомісяця", "text_en": "We need to reduce grid losses — the regulator demands monthly reports"},
        {"id": 2, "text_uk": "SCADA-системи не дають прогнозу — тільки факт", "text_en": "SCADA systems only show facts, not forecasts"},
        {"id": 3, "text_uk": "Диспетчери дізнаються про аварію постфактум", "text_en": "Dispatchers find out about outages after the fact"},
    ],
    "thinks": [
        {"id": 1, "text_uk": "Чи витримає IoT-рішення навантаження нашої мережі?", "text_en": "Will the IoT solution handle our grid load?"},
        {"id": 2, "text_uk": "Як обґрунтувати CAPEX перед держрегулятором?", "text_en": "How do we justify CAPEX to the regulator?"},
        {"id": 3, "text_uk": "Чи витримає стара інфраструктура ще один сезон пікових навантажень?", "text_en": "Will the aging infrastructure survive another peak-load season?"},
    ],
    "does": [
        {"id": 1, "text_uk": "Аналізує графіки навантаження вручну в Excel", "text_en": "Manually analyzes load profiles in Excel"},
        {"id": 2, "text_uk": "Проводить щотижневі наради з операторами підстанцій", "text_en": "Holds weekly meetings with substation operators"},
        {"id": 3, "text_uk": "Виїжджає на місце після кожного аварійного сигналу", "text_en": "Dispatches a crew on-site after every alarm"},
    ],
    "feels": [
        {"id": 1, "text_uk": "Тривога через аварійні відключення в пікові години", "text_en": "Anxiety over emergency outages during peak hours"},
        {"id": 2, "text_uk": "Розчарування від застарілої інфраструктури", "text_en": "Frustration with aging infrastructure"},
        {"id": 3, "text_uk": "Виснаження від постійного реагування на аварії замість планування", "text_en": "Burnout from constantly reacting to outages instead of planning"},
    ],
    "pains": [
        {"id": 1, "text_uk": "Реактивне обслуговування замість предиктивного", "text_en": "Reactive maintenance instead of predictive"},
        {"id": 2, "text_uk": "Відсутність єдиного дашборду по всій мережі", "text_en": "No single dashboard across the entire grid"},
        {"id": 3, "text_uk": "Штрафи регулятора за понаднормові втрати в мережі", "text_en": "Regulator fines for excess grid losses"},
    ],
    "gains": [
        {"id": 1, "text_uk": "Прогноз навантаження за 24 год наперед", "text_en": "24-hour-ahead load forecasting"},
        {"id": 2, "text_uk": "Автоматичне відключення аварійних ділянок", "text_en": "Automated isolation of faulty grid sections"},
        {"id": 3, "text_uk": "Менше штрафів завдяки нижчим втратам у мережі", "text_en": "Fewer fines thanks to lower grid losses"},
    ],
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
        "persona": {
            "name_uk": 'Андрій Коваль',
            "name_en": 'Andriy Koval',
            "role_uk": 'Головний інженер регіонального оператора мережі',
            "role_en": 'Chief Engineer, Regional Grid Operator',
            "pain_point_uk": 'Щотижня 2 аварійних відключення через перевантаження підстанцій у піковий час',
            "pain_point_en": '2 emergency outages per week due to substation overload during peak hours',
        },
        "timeline": [
            {
                "step_type": 'context',
                "icon_key": 'calendar',
                "text_uk": 'Підстанція №12 стабільно перевантажується щопонеділка о 18:30 — 2 аварійних відключення на тиждень.',
                "text_en": 'Substation #12 consistently overloads every Monday at 18:30 — 2 emergency outages per week.',
            },
            {
                "step_type": 'goal',
                "icon_key": 'target',
                "text_uk": 'Запобігти перевантаженню підстанцій у піковий час без ручного втручання диспетчера.',
                "text_en": 'Prevent substation overloads during peak hours without manual dispatcher intervention.',
            },
            {
                "step_type": 'action',
                "icon_key": 'zap',
                "text_uk": 'Smart Grid Automation прогнозує перевантаження за 15 хв та автоматично перерозподіляє навантаження на резервну лінію.',
                "text_en": 'Smart Grid Automation forecasts overload 15 min ahead and automatically redistributes load to the backup line.',
            },
            {
                "step_type": 'result',
                "icon_key": 'check-circle',
                "text_uk": 'Відключення не сталося. Андрій отримує автоматичний звіт о 18:16.',
                "text_en": 'No outage occurred. Andriy receives an automated report at 18:16.',
            },
            {
                "step_type": 'impact',
                "icon_key": 'trending-up',
                "text_uk": 'Кількість аварій знизилася з 2 до 0.2 на тиждень. Мережеві втрати скорочено з 22% до 4%.',
                "text_en": 'Outages reduced from 2 to 0.2 per week. Grid losses cut from 22% to 4%.',
            },
        ],
        "metrics": {
            "before": {
                "value_uk": '2 аварії/тиждень',
                "value_en": '2 outages/week',
                "label_uk": 'Ручне управління підстанціями',
                "label_en": 'Manual substation management',
            },
            "after": {
                "value_uk": '0.2 аварії/тиждень',
                "value_en": '0.2 outages/week',
                "label_uk": 'Автоматичне балансування навантаження',
                "label_en": 'Automated load balancing',
            },
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
    "says": [
        {"id": 1, "text_uk": "EU ETS квоти закінчуються — нам загрожує штраф €100/тонну CO₂", "text_en": "EU ETS quotas are running out — we face a €100/tonne CO₂ fine"},
        {"id": 2, "text_uk": "Наш EHS-директор витрачає місяць на підготовку річного звіту", "text_en": "Our EHS director spends a month preparing the annual report"},
        {"id": 3, "text_uk": "CBAM змусить наших покупців вимагати верифіковані дані про викиди", "text_en": "CBAM will force our buyers to demand verified emissions data"},
    ],
    "thinks": [
        {"id": 1, "text_uk": "Чи акредитовані сенсори для EU ETS верифікації?", "text_en": "Are the sensors accredited for EU ETS verification?"},
        {"id": 2, "text_uk": "Як CBAM вплине на наш бізнес у 2026 році?", "text_en": "How will CBAM affect our business in 2026?"},
        {"id": 3, "text_uk": "Чи витримає інтеграція навантаження без зупинки виробництва?", "text_en": "Will the integration hold up without stopping production?"},
    ],
    "does": [
        {"id": 1, "text_uk": "Замовляє щорічний аудит у зовнішніх верифікаторів за €50k+", "text_en": "Commissions annual audits from external verifiers at €50k+"},
        {"id": 2, "text_uk": "Веде журнали викидів у Excel зі щоденним ручним введенням", "text_en": "Maintains emissions logs in Excel with daily manual entry"},
        {"id": 3, "text_uk": "Звіряє дані сенсорів вручну перед кожною подачею звіту в реєстр", "text_en": "Manually reconciles sensor data before every registry submission"},
    ],
    "feels": [
        {"id": 1, "text_uk": "Страх перед штрафами та репутаційними ризиками", "text_en": "Fear of fines and reputational damage"},
        {"id": 2, "text_uk": "Невизначеність щодо майбутніх регуляторних змін", "text_en": "Uncertainty about future regulatory changes"},
        {"id": 3, "text_uk": "Втома від постійного ручного збору даних щомісяця", "text_en": "Fatigue from constant manual data collection every month"},
    ],
    "pains": [
        {"id": 1, "text_uk": "Ризик перевищення квот через неточний моніторинг", "text_en": "Risk of quota breach due to inaccurate monitoring"},
        {"id": 2, "text_uk": "Висока вартість зовнішньої верифікації викидів", "text_en": "High cost of external emissions verification"},
        {"id": 3, "text_uk": "Немає видимості по викидах між щорічними аудитами", "text_en": "No visibility into emissions between annual audits"},
    ],
    "gains": [
        {"id": 1, "text_uk": "Безперервний моніторинг замість щорічного аудиту", "text_en": "Continuous monitoring instead of annual audit"},
        {"id": 2, "text_uk": "Оптимізація розподілу квот — економія до €200k/рік", "text_en": "Quota allocation optimization — savings up to €200k/year"},
        {"id": 3, "text_uk": "Автоматична готовність до CBAM-звітності без додаткових витрат", "text_en": "Automatic CBAM reporting readiness at no extra cost"},
    ],
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
        "persona": {
            "name_uk": 'Дмитро Петренко',
            "name_en": 'Dmytro Petrenko',
            "role_uk": 'EHS Director, металургійний завод',
            "role_en": 'EHS Director, steel plant',
            "pain_point_uk": 'Щорічний аудит EU ETS коштує €52k і займає 3 тижні підготовки',
            "pain_point_en": 'Annual EU ETS audit costs €52k and takes 3 weeks of preparation',
        },
        "timeline": [
            {
                "step_type": 'context',
                "icon_key": 'calendar',
                "text_uk": 'Щорічний EU ETS аудит коштує €52k і займає 3 тижні підготовки вручну.',
                "text_en": 'Annual EU ETS audit costs €52k and takes 3 weeks of manual preparation.',
            },
            {
                "step_type": 'goal',
                "icon_key": 'target',
                "text_uk": 'Автоматизувати моніторинг викидів і скасувати залежність від зовнішнього аудитора.',
                "text_en": 'Automate emissions monitoring and eliminate dependency on the external auditor.',
            },
            {
                "step_type": 'action',
                "icon_key": 'zap',
                "text_uk": 'Акредитовані IoT-сенсори встановлено за 2 дні. Один клік — EU ETS річний звіт сформовано і відправлено в реєстр.',
                "text_en": 'Accredited IoT sensors installed in 2 days. One click — EU ETS annual report auto-generated and submitted to registry.',
            },
            {
                "step_type": 'result',
                "icon_key": 'check-circle',
                "text_uk": 'Звіт прийнято регулятором. Дмитро скасував контракт із зовнішнім аудитором — €52k повернулися в бюджет.',
                "text_en": 'Report accepted by regulator. Dmytro cancelled the external auditor contract — €52k returned to the budget.',
            },
            {
                "step_type": 'impact',
                "icon_key": 'trending-up',
                "text_uk": 'Витрати на compliance знизилися з €52k до €6k/рік. Real-time дашборд показує викиди цілодобово.',
                "text_en": 'Compliance costs reduced from €52k to €6k/year. Real-time dashboard shows emissions 24/7.',
            },
        ],
        "metrics": {
            "before": {
                "value_uk": '€52 000/рік',
                "value_en": '€52,000/year',
                "label_uk": 'Зовнішній аудит EU ETS вручну',
                "label_en": 'External EU ETS audit',
            },
            "after": {
                "value_uk": '€6 000/рік',
                "value_en": '€6,000/year',
                "label_uk": 'Автоматична звітність через IoT-сенсори',
                "label_en": 'Automated IoT sensor reporting',
            },
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
    "says": [
        {"id": 1, "text_uk": "Ми платимо €80k/рік за вивіз органіки на полігон — це нераціонально", "text_en": "We pay €80k/year to send organics to landfill — that's irrational"},
        {"id": 2, "text_uk": "Регулятор вже питає про нашу стратегію нульових відходів", "text_en": "The regulator is already asking about our zero-waste strategy"},
        {"id": 3, "text_uk": "Великі рітейлери вимагають ESG-звітність від постачальників", "text_en": "Major retailers require ESG reporting from their suppliers"},
    ],
    "thinks": [
        {"id": 1, "text_uk": "Чи надійні біогазові заводи-партнери? Де гарантія якості?", "text_en": "Are the biogas plant partners reliable? Where's the quality guarantee?"},
        {"id": 2, "text_uk": "Як довести ROI переходу на циркулярну модель CFO?", "text_en": "How do I prove the ROI of going circular to the CFO?"},
        {"id": 3, "text_uk": "Чи впораємось із об'ємами органіки без зриву виробничого графіку?", "text_en": "Can we handle the organics volume without disrupting the production schedule?"},
    ],
    "does": [
        {"id": 1, "text_uk": "Укладає окремі контракти з кількома переробниками вручну", "text_en": "Signs separate contracts with multiple recyclers manually"},
        {"id": 2, "text_uk": "Готує щорічний EU taxonomy sound alignment звіт у консультантів", "text_en": "Hires consultants to prepare the annual EU taxonomy alignment report"},
        {"id": 3, "text_uk": "Координує графіки вивозу відходів телефоном і email-листуванням", "text_en": "Coordinates waste pickup schedules over phone calls and email"},
    ],
    "feels": [
        {"id": 1, "text_uk": "Тиск від ESG-рейтингів та закупівельних вимог великих рітейлерів", "text_en": "Pressure from ESG ratings and procurement requirements of large retailers"},
        {"id": 2, "text_uk": "Невизначеність щодо майбутніх штрафів за EU Waste Directive", "text_en": "Uncertainty about future EU Waste Directive penalties"},
        {"id": 3, "text_uk": "Розчарування від негнучкості чинних контрактів з переробниками", "text_en": "Frustration with the inflexibility of current recycler contracts"},
    ],
    "pains": [
        {"id": 1, "text_uk": "Складна логістика: хтось забирає відходи, але не завжди вчасно", "text_en": "Logistics complexity: someone picks up waste, but not always on time"},
        {"id": 2, "text_uk": "Відсутність автоматичної документації для EU taxonomy", "text_en": "No automatic documentation for EU taxonomy"},
        {"id": 3, "text_uk": "Немає єдиної точки контролю над кількома переробниками одразу", "text_en": "No single point of control across multiple recyclers at once"},
    ],
    "gains": [
        {"id": 1, "text_uk": "Зниження витрат на утилізацію відходів на 30%", "text_en": "30% reduction in waste disposal costs"},
        {"id": 2, "text_uk": "Готова EU taxonomy-документація для ESG-звіту", "text_en": "Ready EU taxonomy documentation for ESG report"},
        {"id": 3, "text_uk": "Один надійний партнер замість розрізнених контрактів", "text_en": "One reliable partner instead of fragmented contracts"},
    ],
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
        "persona": {
            "name_uk": 'Наталія Бондар',
            "name_en": 'Natalia Bondar',
            "role_uk": 'Head of Sustainability, харчовий холдинг',
            "role_en": 'Head of Sustainability, food holding',
            "pain_point_uk": 'Платить €80k/рік за вивіз органіки та не має документації для EU taxonomy',
            "pain_point_en": 'Pays €80k/year for organic waste removal with no EU taxonomy documentation',
        },
        "timeline": [
            {
                "step_type": 'context',
                "icon_key": 'calendar',
                "text_uk": 'Наталія платить €80k/рік за вивіз органіки на полігон і не має EU taxonomy документації.',
                "text_en": 'Natalia pays €80k/year for organic waste disposal with no EU taxonomy documentation.',
            },
            {
                "step_type": 'goal',
                "icon_key": 'target',
                "text_uk": 'Знайти надійного біогазового партнера, скоротити витрати та автоматизувати EU taxonomy звітність.',
                "text_en": 'Find a reliable biogas partner, cut disposal costs, and automate EU taxonomy reporting.',
            },
            {
                "step_type": 'action',
                "icon_key": 'zap',
                "text_uk": 'BioWaste Circular підібрав 3 партнери за 5 хвилин. Контракт підписано онлайн, логістика — автоматична.',
                "text_en": 'BioWaste Circular matched 3 partners in 5 minutes. Contract signed online, logistics automated.',
            },
            {
                "step_type": 'result',
                "icon_key": 'check-circle',
                "text_uk": 'EU taxonomy звіт оновився автоматично після першої транзакції. Готовий до аудиту.',
                "text_en": 'EU taxonomy report updated automatically after the first transaction. Audit-ready.',
            },
            {
                "step_type": 'impact',
                "icon_key": 'trending-up',
                "text_uk": 'Витрати на утилізацію знизилися з €80k до €54k/рік. Наталія отримала EU taxonomy документацію без жодного консультанта.',
                "text_en": 'Disposal costs dropped from €80k to €54k/year. Natalia got full EU taxonomy documentation without a single consultant.',
            },
        ],
        "metrics": {
            "before": {
                "value_uk": '€80 000/рік',
                "value_en": '€80,000/year',
                "label_uk": 'Вивіз органіки на полігон вручну',
                "label_en": 'Manual organic waste to landfill',
            },
            "after": {
                "value_uk": '€54 000/рік',
                "value_en": '€54,000/year',
                "label_uk": 'Автоматичний підбір біогазового партнера',
                "label_en": 'Automated biogas partner matching',
            },
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

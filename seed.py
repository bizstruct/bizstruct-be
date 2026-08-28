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


def mo(title: str, monetization: str, score: int) -> dict:
    """A minimal but valid BusinessModelOption (bizstruct_domain.blocks.models_options)
    for projects that don't need the full detail ECOSYNC_MODELS_OPTIONS has."""
    return {
        "id": uid(),
        "title": title,
        "audience": f"Цільова аудиторія для варіанта «{title}»",
        "value_proposition": f"Ціннісна пропозиція варіанта «{title}»",
        "description": f"Опис бізнес-моделі «{title}» — монетизація {monetization}, довший за 20 символів.",
        "monetization": monetization,
        "key_metric": "MRR" if monetization == "subscription" else "GMV" if monetization == "transaction_fee" else "ACV",
        "time_to_value": "2 тижні",
        "score": score,
        "score_rationale": f"Обґрунтування оцінки {score} для варіанта «{title}» довше за 15 символів.",
    }


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
        {"id": 1, "text": "We need to automate ESG reporting to avoid CSRD penalties"},
        {"id": 2, "text": "Current processes are too slow — we spend 3 days on a quarterly report"},
        {"id": 3, "text": "Shareholders demand transparency, yet we still collect data in Excel"},
    ],
    "thinks": [
        {"id": 1, "text": "Can we really trust data accuracy before an ISO audit?"},
        {"id": 2, "text": "How do we integrate a new system with our SAP / Oracle ERP without disrupting operations?"},
        {"id": 3, "text": "Will automation justify the investment in front of the CFO?"},
    ],
    "does": [
        {"id": 1, "text": "Manually consolidates Excel sheets from 8 departments every month"},
        {"id": 2, "text": "Presents ESG metrics via static PowerPoint slides at board meetings"},
        {"id": 3, "text": "Coordinates supplier data through email chains"},
    ],
    "feels": [
        {"id": 1, "text": "Confused by the constant stream of EU regulation changes (CSRD, ESRS)"},
        {"id": 2, "text": "Frustrated by siloed departments and lack of a single source of truth"},
        {"id": 3, "text": "Pressured by senior management demanding results immediately"},
    ],
    "pains": [
        {"id": 1, "text": "Human error risk: Excel mistakes lead to inaccurate disclosures"},
        {"id": 2, "text": "No real-time CO₂ tracking — data is always one month out of date"},
        {"id": 3, "text": "Limited ESG team budget against growing regulatory requirements"},
    ],
    "gains": [
        {"id": 1, "text": "Automated reports — free up 3 days per quarter for strategic work"},
        {"id": 2, "text": "Prove ESG program ROI to the CFO with real platform data"},
        {"id": 3, "text": "Seamless API integration with SAP/Oracle without manual intervention"},
    ],
}

ECOSYNC_HYPOTHESES = [
    hyp("H1.1", "Менеджери зі сталого розвитку витрачають 6+ годин/тиждень на ручну агрегацію ESG-даних", "desirability", "q1"),
    hyp("H1.2", "CFO не можуть обґрунтувати ROI ESG-програми без автоматизованої звітності", "viability", "q2"),
    hyp("H1.3", "Real-time Scope 3 трекінг технічно реалізований через ERP connector APIs", "feasibility", "q3"),
    hyp("H2.1", "Дедлайни CSRD (2025) створюють термінований попит на автоматизацію по всьому ЄС", "desirability", "q1"),
    hyp("H2.2", "Mid-market компанії готові платити €12k–€36k/рік за повну автоматизацію ESG", "viability", "q2"),
    hyp("H3.1", "ESG-команди хочуть no-code onboarding без залучення IT-департаменту", "desirability", "q3"),
    hyp("H3.2", "Інтеграція SAP & Oracle можлива без впровадження сторонньої консалтингової фірми", "feasibility", "q4"),
]

ECOSYNC_PITCH = {
    "investor": [
        {
            "type": 'hook',
            "headline": '$1.2 trillion in fines awaits EU companies by 2027',
            "content": 'The CSRD directive mandates 50,000+ companies to automate ESG reporting. Those who miss the deadline will pay.',
        },
        {
            "type": 'problem',
            "headline": 'ESG reporting still looks like 2005',
            "content": 'Teams spend 3+ days per quarter manually aggregating data in Excel. Errors, delays, and audit risks follow.',
        },
        {
            "type": 'solution',
            "headline": 'EcoSync: from 3 days to 15 minutes',
            "content": 'Automatic data collection from SAP/Oracle, real-time CO₂ calculator, and one-click CSRD report generation.',
        },
        {
            "type": 'traction',
            "headline": '3 pilots. €2.1M ARR pipeline. NPS 72.',
            "content": 'Pilots at Henkel, Metinvest, DTEK. Average customer savings: 18 person-days per quarter. Churn: 0%.',
        },
        {
            "type": 'ask',
            "headline": 'Raising €4M Series A',
            "content": 'Scaling sales teams in Germany and Poland, R&D for new ERP connectors, and entering the Fortune 500 segment.',
        },
    ],
    "customer": [
        {
            "type": 'opening',
            "headline": 'Imagine: end of quarter and you still have 3 days of work ahead',
            "content": 'Three offices. Eight suppliers. Hundreds of Excel rows. And the deadline is tomorrow morning.',
        },
        {
            "type": 'empathy',
            "headline": 'We know what this looks like from the inside',
            "content": "Cross-department coordination, supplier email chains, formula checks at 11 PM. This isn't your job — it's a system bug.",
        },
        {
            "type": 'transformation',
            "headline": '15 minutes instead of 3 days',
            "content": 'EcoSync automatically collects data from your systems, calculates Scope 1/2/3, and generates a ready CSRD report. You just click Export.',
        },
        {
            "type": 'social_proof',
            "headline": '"We cut report preparation from 4 days to 20 minutes"',
            "content": '— Head of Sustainability, Fortune 500 chemical company. Our platform NPS: 72.',
        },
        {
            "type": 'invitation',
            "headline": 'Try it free for 14 days',
            "content": 'Connect your SAP or Oracle in 30 minutes. First automated report — tonight.',
        },
    ],
}

ECOSYNC_SCENARIO = {
    "persona": {
        "name": 'Olena Morozova',
        "role": 'Corporate Sustainability Manager',
        "pain_point": 'Spends 3 days every quarter consolidating emissions data from 3 offices',
    },
    "timeline": [
        {
            "step_type": 'context',
            "text": 'End of quarter. Need to consolidate emissions data from offices in Kyiv, Warsaw, and Frankfurt.',
        },
        {
            "step_type": 'goal',
            "text": 'Collect Scope 1, 2, 3 data from 3 offices and generate a CSRD report for the auditor by Friday.',
        },
        {
            "step_type": 'action',
            "text": 'One click → EcoSync automatically pulls data from SAP and IoT sensors, calculates emissions, and generates the report.',
        },
        {
            "step_type": 'result',
            "text": 'Full CSRD report ready in 15 minutes. Olena sends it to the auditor on Tuesday morning.',
        },
        {
            "step_type": 'impact',
            "text": 'Olena uses the freed 2.5 days to develop a new supply chain decarbonization initiative.',
        },
    ],
    "metrics": {
        "before": {
            "value": '3 days',
            "label": 'Manual Excel data collection',
        },
        "after": {
            "value": '15 minutes',
            "label": 'Ready report with AI analytics',
        },
    },
}

def _errc_move(action: str, section: str, target: str, rationale: str, new_text: str | None = None) -> dict:
    move = {
        "action": action,
        "target_section": section,
        "target": target,
        "rationale": rationale,
    }
    if new_text is not None:
        move["new_text"] = new_text
    return move


# ERRC alternatives, replacing the old Financial/Technical/Emotional-vector
# design. Each move's `target` is the EXACT text of an existing ECOSYNC_CANVAS
# card in `target_section` (for eliminate/reduce/raise) — see
# bizstruct_domain.blocks.what_if's module docstring for why this is a text
# match, not a UUID reference.
#
# The first alternative is seeded as already `applied`, same as before —
# but note it has no `canvas_snapshot_before` (that's only ever produced by
# actually calling POST .../apply, which this seed data bypasses), so
# reverting THIS seeded alternative via the API will 409 until it's
# re-applied for real. Acceptable for seed/demo data.
ECOSYNC_WHAT_IF = {
    "alternatives": [
        {
            "id": uid(),
            "title": "Revenue share instead of subscription",
            "premise": "Charge a % of the client's confirmed ESG-audit cost savings instead of a fixed subscription.",
            "moves": [
                _errc_move(
                    "eliminate", "revenue_streams", "Subscription tiers (Core, Pro, Enterprise)",
                    "Removing the fixed subscription — it conflicts with pay-for-outcome pricing.",
                ),
                _errc_move(
                    "raise", "value_propositions", "Real-time carbon footprint monitoring for assets",
                    "Strengthening the value proposition with a savings guarantee tied to the new pricing.",
                    new_text="Real-time carbon footprint monitoring, with a savings guarantee tied to revenue-share pricing",
                ),
                _errc_move(
                    "create", "revenue_streams", "Revenue share: % of confirmed audit-cost savings",
                    "New revenue stream aligning platform and client incentives.",
                ),
            ],
            "expected_impact": "Client pays only when they see results — higher trust, lower churn, potential ARPU up to €8,000+/year on large accounts.",
            "status": "applied",
        },
        {
            "id": uid(),
            "title": "On-premise for regulated industries",
            "premise": "Finance and energy sectors can't send ESG data to a public cloud service.",
            "moves": [
                _errc_move(
                    "eliminate", "channels", "Partner channel through ERP vendors (SAP, Oracle)",
                    "On-premise deals with regulated clients need direct sales, not a vendor partner channel.",
                ),
                _errc_move(
                    "raise", "key_resources", "Multi-tenant SaaS platform",
                    "The platform needs an on-premise deployment option for clients barred from the cloud.",
                    new_text="Multi-tenant SaaS platform with an on-premise deployment option for regulated industries",
                ),
                _errc_move(
                    "create", "revenue_streams", "On-premise enterprise license",
                    "New tier for the Enterprise segment currently blocked by compliance requirements.",
                ),
            ],
            "expected_impact": "Access to 300+ regulated EU companies; on-premise license from €24,000/year — 4x the current Enterprise plan.",
            "status": "draft",
        },
        {
            "id": uid(),
            "title": "Public ESG-score as a trust signal",
            "premise": "A public company ESG rating becomes a B2B trust signal in tenders and procurement.",
            "moves": [
                _errc_move(
                    "reduce", "customer_relationships", "Dedicated onboarding and monthly check-ins",
                    "Cheaper self-serve onboarding frees budget for the public ESG-score showcase.",
                    new_text="Lightweight self-serve onboarding",
                ),
                _errc_move(
                    "raise", "value_propositions", "Audit-ready compliance documentation",
                    "Compliance documentation becomes a public trust proof for partners, not just an internal artifact.",
                    new_text="Audit-ready compliance documentation, publicly showcased as a partner trust signal",
                ),
                _errc_move(
                    "create", "channels", "Public ESG-score profile visible to B2B partners",
                    "New channel: a viral loop where clients push their own suppliers to show their ESG-score.",
                ),
                _errc_move(
                    "create", "revenue_streams", "Third-party ESG-score verification fee",
                    "New monetization: verifying third-party ESG-scores.",
                ),
            ],
            "expected_impact": "Viral supplier-acquisition effect; new verification monetization at €299/check.",
            "status": "draft",
        },
    ]
}

ECOSYNC_ARCHITECTURE = {
    "epicenter": "finance_driven",
    "epicenter_rationale": "Monetization and cash flows are the key drivers of the model. The platform is built around subscriptions and premium upgrades, where every feature is tied to revenue.",
    "pattern": "free",
    "pattern_subtype": "freemium",
    "pattern_rationale": "Free basic plan for acquisition, premium features convert to subscriptions. Focus on fast onboarding and viral spread within corporations.",
}

ECOSYNC_MODELS_OPTIONS = {
    "options": [
        {
            "id": uid(),
            "title": "B2B SaaS · EcoSync",
            "audience": "ESG-команди середнього бізнесу (200–2000 осіб)",
            "value_proposition": "Підписка + швидкий self-serve onboarding для команд середнього бізнесу",
            "description": "Щомісячна або річна підписка з диференційованими тарифами. Акцент на швидкому self-serve onboarding без залучення IT. Цільовий сегмент: ESG-команди 200–2000 осіб.",
            "monetization": "subscription",
            "key_metric": "MRR / NRR",
            "time_to_value": "30 хвилин до першого звіту",
            "score": 91,
            "score_rationale": "Високий бал: передплата напряму монетизує щомісячну болючу точку зі звітністю, а self-serve onboarding знижує вартість залучення клієнта.",
        },
        {
            "id": uid(),
            "title": "Marketplace · EcoSync",
            "audience": "Enterprise ESG-команди та їх ланцюги постачання",
            "value_proposition": "Транзакційна монетизація для enterprise-екосистеми",
            "description": "Платформа, де ESG-консультанти, верифікатори та постачальники даних пропонують послуги. Комісія 15–20% з кожної транзакції. Цільовий сегмент: enterprise + supply chain.",
            "monetization": "transaction_fee",
            "key_metric": "GMV / Take rate",
            "time_to_value": "Перша транзакція за 1–2 тижні",
            "score": 74,
            "score_rationale": "Помірний бал: більший потенціал доходу на транзакцію, але довший цикл продажу через потребу в мережевому ефекті постачальників.",
        },
        {
            "id": uid(),
            "title": "Advisory Platform · EcoSync",
            "audience": "Фаундери та CxO, яким потрібен персональний ESG-roadmap",
            "value_proposition": "AI-консалтинг та premium-пакети для фаундерів",
            "description": "Поєднання SaaS-інструменту та AI-асистованого консалтингу. Преміум-пакети включають персоналізовані roadmap, виділеного ESG-аналітика та участь у регуляторних слуханнях.",
            "monetization": "retainer_plus_saas",
            "key_metric": "ACV / CSAT",
            "time_to_value": "Перший advisory session за 48 годин",
            "score": 62,
            "score_rationale": "Нижчий бал: висока цінність на клієнта, але обмежена масштабованість через залежність від людських консультантів.",
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
    language="en",
    translation_key="project.ecosync",
    models_options=ECOSYNC_MODELS_OPTIONS,
    canvas=ECOSYNC_CANVAS,
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
    language="en",
    translation_key="project.smart_grid",
    models_options={
        "options": [
            mo("B2B SaaS · Smart Grid", "subscription", 88),
            mo("Marketplace · Smart Grid", "transaction_fee", 71),
            mo("Advisory Platform · Smart Grid", "retainer_plus_saas", 55),
        ],
        "selected_id": None,
    },
    canvas={
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
        {"id": 1, "text": "We need to reduce grid losses — the regulator demands monthly reports"},
        {"id": 2, "text": "SCADA systems only show facts, not forecasts"},
        {"id": 3, "text": "Dispatchers find out about outages after the fact"},
    ],
    "thinks": [
        {"id": 1, "text": "Will the IoT solution handle our grid load?"},
        {"id": 2, "text": "How do we justify CAPEX to the regulator?"},
        {"id": 3, "text": "Will the aging infrastructure survive another peak-load season?"},
    ],
    "does": [
        {"id": 1, "text": "Manually analyzes load profiles in Excel"},
        {"id": 2, "text": "Holds weekly meetings with substation operators"},
        {"id": 3, "text": "Dispatches a crew on-site after every alarm"},
    ],
    "feels": [
        {"id": 1, "text": "Anxiety over emergency outages during peak hours"},
        {"id": 2, "text": "Frustration with aging infrastructure"},
        {"id": 3, "text": "Burnout from constantly reacting to outages instead of planning"},
    ],
    "pains": [
        {"id": 1, "text": "Reactive maintenance instead of predictive"},
        {"id": 2, "text": "No single dashboard across the entire grid"},
        {"id": 3, "text": "Regulator fines for excess grid losses"},
    ],
    "gains": [
        {"id": 1, "text": "24-hour-ahead load forecasting"},
        {"id": 2, "text": "Automated isolation of faulty grid sections"},
        {"id": 3, "text": "Fewer fines thanks to lower grid losses"},
    ],
},
    hypotheses=[
        hyp("H1.1", "Оператори DSO витрачають 8+ год/тиждень на ручний аналіз графіків навантаження", "desirability", "q1"),
        hyp("H1.2", "Предиктивне обслуговування знижує OPEX трансформаторів на 30%", "viability", "q1"),
        hyp("H2.1", "IoT-датчики можна встановити без зупинки мережі", "feasibility", "q2"),
        hyp("H2.2", "Автоматична балансування знижує втрати на 22% у реальних умовах України", "feasibility", "q3"),
        hyp("H3.1", "Регіональні оператори готові платити €3000/міс за предиктивну аналітику мережі", "viability", "q4"),
    ],
    pitch={
        "investor": [
            {
                "type": 'hook',
                "headline": "Ukraine's power grid loses $400M/year in technical losses",
                "content": '22% of electricity is lost during transmission due to aging infrastructure and lack of automation.',
            },
            {
                "type": 'problem',
                "headline": 'Dispatchers learn about outages only after they happen',
                "content": 'SCADA shows facts, not forecasts. Grid losses run 22%, and regulator fines climb every year.',
            },
            {
                "type": 'solution',
                "headline": 'Smart Grid Automation: IoT + ML for intelligent grids',
                "content": 'Predictive load control, automated fault isolation, unified operator dashboard.',
            },
            {
                "type": 'traction',
                "headline": '2 pilots with regional DSOs. €1.8M ARR pipeline.',
                "content": 'Kyivoblenergo and Kharkivoblenergo. Confirmed 19% loss reduction in 3-month pilot.',
            },
            {
                "type": 'ask',
                "headline": 'Raising €3M to scale',
                "content": 'Expanding to 5 regional DSOs in 2025 and launching a pilot in Poland (PSE operator).',
            },
        ],
        "customer": [
            {
                "type": 'opening',
                "headline": 'Andriy, substation #12 just cut power to 3,000 subscribers again',
                "content": 'Another call from management. Another report to the regulator. This is the third week in a row.',
            },
            {
                "type": 'empathy',
                "headline": 'We know what reactive grid management looks like from the inside',
                "content": "Dispatchers watch SCADA around the clock, but only find out about problems after they happen. That's not your failure — it's the limitation of legacy systems.",
            },
            {
                "type": 'transformation',
                "headline": '15-minute warning instead of post-incident response',
                "content": "Smart Grid Automation forecasts peak loads in advance and automatically redistributes capacity. Your dispatcher gets a notification and simply confirms the system's decision.",
            },
            {
                "type": 'social_proof',
                "headline": '"Emergency outages dropped from 8 to 1 per month in the first 60 days"',
                "content": '— Chief Engineer, regional grid operator, Kharkiv region. Grid losses reduced by 19%.',
            },
            {
                "type": 'invitation',
                "headline": 'Free 30-day pilot on 10 substations',
                "content": '3-day integration with your existing SCADA. First automated load forecast — the next morning.',
            },
        ],
    },
    scenario={
        "persona": {
            "name": 'Andriy Koval',
            "role": 'Chief Engineer, Regional Grid Operator',
            "pain_point": '2 emergency outages per week due to substation overload during peak hours',
        },
        "timeline": [
            {
                "step_type": 'context',
                "text": 'Substation #12 consistently overloads every Monday at 18:30 — 2 emergency outages per week.',
            },
            {
                "step_type": 'goal',
                "text": 'Prevent substation overloads during peak hours without manual dispatcher intervention.',
            },
            {
                "step_type": 'action',
                "text": 'Smart Grid Automation forecasts overload 15 min ahead and automatically redistributes load to the backup line.',
            },
            {
                "step_type": 'result',
                "text": 'No outage occurred. Andriy receives an automated report at 18:16.',
            },
            {
                "step_type": 'impact',
                "text": 'Outages reduced from 2 to 0.2 per week. Grid losses cut from 22% to 4%.',
            },
        ],
        "metrics": {
            "before": {
                "value": '2 outages/week',
                "label": 'Manual substation management',
            },
            "after": {
                "value": '0.2 outages/week',
                "label": 'Automated load balancing',
            },
        },
    },
    what_if={
        "alternatives": [
            {
                "id": uid(),
                "title": "Performance-based pricing",
                "premise": "Charge a % of confirmed savings instead of a fixed subscription.",
                "moves": [
                    _errc_move("eliminate", "revenue_streams", "Annual SaaS license per substation",
                        "The fixed license conflicts with pay-for-outcome pricing."),
                    _errc_move("raise", "revenue_streams", "Performance-based bonus: % of saved losses",
                        "Making this the primary model, not a bonus on top of a subscription.",
                        new_text="Performance-based fee: % of confirmed grid-loss savings, primary pricing model"),
                    _errc_move("create", "customer_relationships", "Transparent monthly savings dashboard tied to billing",
                        "The client needs to see exactly what they're paying for each month."),
                ],
                "expected_impact": "Lower entry barrier for new clients; ARPU grows proportionally to value delivered.",
                "status": "applied",
            },
            {
                "id": uid(),
                "title": "Edge computing for critical infrastructure",
                "premise": "Local data processing without sending it to the cloud, for regulated industries.",
                "moves": [
                    _errc_move("eliminate", "channels", "Energy industry conferences",
                        "The regulated segment closes through direct sales, not conferences."),
                    _errc_move("raise", "key_resources", "IoT edge computing nodes",
                        "Edge nodes must fully process data locally to meet data sovereignty requirements.",
                        new_text="IoT edge computing nodes with full local processing, no cloud dependency"),
                    _errc_move("create", "revenue_streams", "Edge deployment license per substation",
                        "New tier for sites barred from sending data to the cloud."),
                ],
                "expected_impact": "Access to the segment with strict data sovereignty requirements; edge license from €18,000/year per site.",
                "status": "draft",
            },
            {
                "id": uid(),
                "title": "Public grid status dashboard",
                "premise": "Real-time transparency builds trust and reduces support call volume.",
                "moves": [
                    _errc_move("reduce", "customer_relationships", "24/7 NOC support",
                        "The public dashboard absorbs part of the routine status-check load.",
                        new_text="24/7 NOC support for verified incidents, routine status checks self-served via dashboard"),
                    _errc_move("raise", "value_propositions", "22% reduction in grid losses",
                        "The metric becomes a public trust proof, not just an internal number.",
                        new_text="22% reduction in grid losses, published live on the public dashboard"),
                    _errc_move("create", "channels", "Public real-time grid status page for end consumers",
                        "New direct communication channel with end consumers."),
                    _errc_move("create", "revenue_streams", "Aggregated demand data licensing to third parties",
                        "Monetizing aggregated (anonymized) demand data."),
                ],
                "expected_impact": "Reputational advantage for the operator, fewer regulator complaints; monetization via B2B data to demand aggregators.",
                "status": "draft",
            },
        ]
    },
    architecture={
        "epicenter": "resource_driven",
        "epicenter_rationale": "Infrastructure reliability and operational efficiency are the core value drivers. The platform is built around data quality and grid uptime.",
        # Was "Multi-sided Platform" + subtype "Freemium" in the old schema — an
        # invalid combination under bizstruct_domain (only free/open_business_model
        # have subtypes). The rationale text is genuinely a freemium tiering
        # story, so reclassified as free/freemium rather than dropping the subtype.
        "pattern": "free",
        "pattern_subtype": "freemium",
        "pattern_rationale": "Basic monitoring free, predictive analytics paid. Connecting operators and regulators on one platform.",
    },
)

CARBON_TRACK = Project(
    id=uuid.uuid4(),
    title="CarbonTrack IoT",
    idea="Мережа IoT-сенсорів для безперервного моніторингу вуглецевих викидів на виробничих майданчиках у реальному часі. Інтегрується з MES/SCADA та автоматично формує звіти EU ETS.",
    status="completed",
    language="en",
    translation_key="project.carbon_track",
    models_options={
        "options": [
            mo("B2B SaaS · CarbonTrack", "subscription", 85),
            mo("Marketplace · CarbonTrack", "transaction_fee", 68),
            mo("Advisory Platform · CarbonTrack", "retainer_plus_saas", 59),
        ],
        "selected_id": None,
    },
    canvas={
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
        {"id": 1, "text": "EU ETS quotas are running out — we face a €100/tonne CO₂ fine"},
        {"id": 2, "text": "Our EHS director spends a month preparing the annual report"},
        {"id": 3, "text": "CBAM will force our buyers to demand verified emissions data"},
    ],
    "thinks": [
        {"id": 1, "text": "Are the sensors accredited for EU ETS verification?"},
        {"id": 2, "text": "How will CBAM affect our business in 2026?"},
        {"id": 3, "text": "Will the integration hold up without stopping production?"},
    ],
    "does": [
        {"id": 1, "text": "Commissions annual audits from external verifiers at €50k+"},
        {"id": 2, "text": "Maintains emissions logs in Excel with daily manual entry"},
        {"id": 3, "text": "Manually reconciles sensor data before every registry submission"},
    ],
    "feels": [
        {"id": 1, "text": "Fear of fines and reputational damage"},
        {"id": 2, "text": "Uncertainty about future regulatory changes"},
        {"id": 3, "text": "Fatigue from constant manual data collection every month"},
    ],
    "pains": [
        {"id": 1, "text": "Risk of quota breach due to inaccurate monitoring"},
        {"id": 2, "text": "High cost of external emissions verification"},
        {"id": 3, "text": "No visibility into emissions between annual audits"},
    ],
    "gains": [
        {"id": 1, "text": "Continuous monitoring instead of annual audit"},
        {"id": 2, "text": "Quota allocation optimization — savings up to €200k/year"},
        {"id": 3, "text": "Automatic CBAM reporting readiness at no extra cost"},
    ],
},
    hypotheses=[
        hyp("H1.1", "EHS-менеджери витрачають 20+ людино-днів на підготовку щорічного EU ETS звіту", "desirability", "q1"),
        hyp("H1.2", "Виробники EU ETS готові платити €500/міс за автоматизацію замість €50k аудиту", "viability", "q1"),
        hyp("H2.1", "IoT-сенсори з акредитацією EN 14181 можна встановити без зупинки виробництва", "feasibility", "q2"),
        hyp("H2.2", "CBAM 2026 подвоїть попит на автоматизований моніторинг серед експортерів", "desirability", "q1"),
        hyp("H3.1", "Інтеграція з MES-системами виробників можлива без кастомної розробки", "feasibility", "q4"),
    ],
    pitch={
        "investor": [
            {
                "type": 'hook',
                "headline": 'CBAM 2026: €50B in new penalties for EU industry',
                "content": 'Carbon Border Adjustment Mechanism makes accurate emissions monitoring mandatory for all EU exporters.',
            },
            {
                "type": 'problem',
                "headline": 'Annual audits cost €50k+ and give zero visibility between checks',
                "content": 'External verifiers collect data manually once a year. Companies risk breaching quotas unnoticed.',
            },
            {
                "type": 'solution',
                "headline": 'CarbonTrack IoT: continuous monitoring instead of annual audits',
                "content": 'Accredited sensors + MES integration + automatic EU ETS report. From €50k audit to €6k/year.',
            },
            {
                "type": 'traction',
                "headline": '4 factories connected. €980k ARR. Churn 0%.',
                "content": 'Steel, chemicals, cement. Average client savings on audits: €44k/year.',
            },
            {
                "type": 'ask',
                "headline": 'Raising €2.5M for EN 14181 certification and expansion to Poland/Czech Republic',
                "content": 'EU ETS covers 11,000 installations — TAM €5.5B.',
            },
        ],
        "customer": [
            {
                "type": 'opening',
                "headline": 'Your EU ETS audit costs €52k and takes 3 weeks — every single year',
                "content": 'An external verifier shows up once a year, collects data manually, and sends the invoice. Between audits, you have no idea where you stand on quotas.',
            },
            {
                "type": 'empathy',
                "headline": "Compliance for compliance's sake isn't emissions management",
                "content": "Your team spends a month preparing documents instead of doing real decarbonization work. Regulators demand more, but the tools don't keep up.",
            },
            {
                "type": 'transformation',
                "headline": 'From annual audit to real-time monitoring for €6k/year',
                "content": 'CarbonTrack IoT installs accredited sensors on your stacks in 2 days. EU ETS reports are generated automatically and submitted to the registry with one click.',
            },
            {
                "type": 'social_proof',
                "headline": '"Cancelled the auditor contract after the very first automated report"',
                "content": '— EHS Director, steel plant, 4 production sites. €46k savings in year one.',
            },
            {
                "type": 'invitation',
                "headline": 'Free sensor installation on 1 site for 30 days',
                "content": "If the first automated EU ETS report isn't accepted by the regulator, we'll give you a full refund.",
            },
        ],
    },
    scenario={
        "persona": {
            "name": 'Dmytro Petrenko',
            "role": 'EHS Director, steel plant',
            "pain_point": 'Annual EU ETS audit costs €52k and takes 3 weeks of preparation',
        },
        "timeline": [
            {
                "step_type": 'context',
                "text": 'Annual EU ETS audit costs €52k and takes 3 weeks of manual preparation.',
            },
            {
                "step_type": 'goal',
                "text": 'Automate emissions monitoring and eliminate dependency on the external auditor.',
            },
            {
                "step_type": 'action',
                "text": 'Accredited IoT sensors installed in 2 days. One click — EU ETS annual report auto-generated and submitted to registry.',
            },
            {
                "step_type": 'result',
                "text": 'Report accepted by regulator. Dmytro cancelled the external auditor contract — €52k returned to the budget.',
            },
            {
                "step_type": 'impact',
                "text": 'Compliance costs reduced from €52k to €6k/year. Real-time dashboard shows emissions 24/7.',
            },
        ],
        "metrics": {
            "before": {
                "value": '€52,000/year',
                "label": 'External EU ETS audit',
            },
            "after": {
                "value": '€6,000/year',
                "label": 'Automated IoT sensor reporting',
            },
        },
    },
    what_if={
        "alternatives": [
            {
                "id": uid(),
                "title": "Performance-based pricing",
                "premise": "Charge a % of optimized quota allocation instead of a fixed bundle.",
                "moves": [
                    _errc_move("eliminate", "revenue_streams", "Hardware + SaaS bundle: €2k setup + €500/mo",
                        "The fixed bundle conflicts with pay-for-outcome pricing."),
                    _errc_move("raise", "revenue_streams", "Carbon credit advisory: % of optimized allocation",
                        "Making the advisory model the primary revenue stream, not a secondary one.",
                        new_text="Carbon credit advisory: % of optimized allocation, now the primary pricing model"),
                    _errc_move("create", "customer_relationships", "Monthly savings-to-billing transparency report",
                        "The client needs to see the direct link between savings and their bill."),
                ],
                "expected_impact": "Lower entry barrier for new clients; ARPU grows proportionally to value delivered.",
                "status": "applied",
            },
            {
                "id": uid(),
                "title": "Edge computing for critical infrastructure",
                "premise": "Local data processing without sending it to the cloud, for regulated industries.",
                "moves": [
                    _errc_move("eliminate", "channels", "Industrial automation trade shows",
                        "The regulated segment closes through direct sales, not trade shows."),
                    _errc_move("raise", "key_resources", "Edge computing modules for factories",
                        "Edge modules must fully process data locally to meet data sovereignty requirements.",
                        new_text="Edge computing modules with full local processing, no cloud dependency"),
                    _errc_move("create", "revenue_streams", "Edge deployment license per factory",
                        "New tier for sites barred from sending data to the cloud."),
                ],
                "expected_impact": "Access to the segment with strict data sovereignty requirements; edge license from €18,000/year per site.",
                "status": "draft",
            },
            {
                "id": uid(),
                "title": "Public CBAM-readiness showcase",
                "premise": "Transparent, verified emissions data builds buyer trust ahead of CBAM.",
                "moves": [
                    _errc_move("reduce", "customer_relationships", "Annual compliance audit support",
                        "Cheaper self-serve support frees budget for the public showcase.",
                        new_text="Self-serve compliance audit support, with escalation for complex cases"),
                    _errc_move("raise", "value_propositions", "Real-time factory emissions dashboard",
                        "The dashboard becomes a public trust proof for buyers across the CBAM supply chain.",
                        new_text="Real-time factory emissions dashboard, with a public CBAM-readiness view for buyers"),
                    _errc_move("create", "channels", "Public CBAM-readiness profile visible to buyers",
                        "New direct trust channel with buyers who demand verified data."),
                    _errc_move("create", "revenue_streams", "Third-party CBAM-readiness verification fee",
                        "New monetization: verifying third-party CBAM readiness."),
                ],
                "expected_impact": "Reputational advantage for the manufacturer; new verification monetization for supply-chain buyers.",
                "status": "draft",
            },
        ]
    },
    architecture={
        "epicenter": "offer_driven",
        "epicenter_rationale": "A compliance product with a clear regulatory value proposition. The offering is built around automating EU ETS reporting as the core deliverable.",
        # Was "Long Tail" + subtype "Bait & Hook" in the old schema — invalid
        # under bizstruct_domain (long_tail has no subtypes). The rationale
        # describes a textbook bait-and-hook story, so reclassified as
        # free/bait_and_hook rather than dropping the subtype.
        "pattern": "free",
        "pattern_subtype": "bait_and_hook",
        "pattern_rationale": "Initial sensor installation as the entry point, followed by recurring revenue through SaaS subscription for analytics and reporting.",
    },
)

BIOWASTE = Project(
    id=uuid.uuid4(),
    title="BioWaste Circular",
    idea="Платформа циркулярної економіки для переробки органічних відходів: з'єднує харчові підприємства з біогазовими заводами через маркетплейс залишків і оптимізатор логістики.",
    status="completed",
    language="en",
    translation_key="project.biowaste",
    models_options={
        "options": [
            mo("B2B SaaS · BioWaste Circular", "subscription", 79),
            mo("Marketplace · BioWaste Circular", "transaction_fee", 86),
            mo("Advisory Platform · BioWaste Circular", "retainer_plus_saas", 61),
        ],
        "selected_id": None,
    },
    canvas={
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
        {"id": 1, "text": "We pay €80k/year to send organics to landfill — that's irrational"},
        {"id": 2, "text": "The regulator is already asking about our zero-waste strategy"},
        {"id": 3, "text": "Major retailers require ESG reporting from their suppliers"},
    ],
    "thinks": [
        {"id": 1, "text": "Are the biogas plant partners reliable? Where's the quality guarantee?"},
        {"id": 2, "text": "How do I prove the ROI of going circular to the CFO?"},
        {"id": 3, "text": "Can we handle the organics volume without disrupting the production schedule?"},
    ],
    "does": [
        {"id": 1, "text": "Signs separate contracts with multiple recyclers manually"},
        {"id": 2, "text": "Hires consultants to prepare the annual EU taxonomy alignment report"},
        {"id": 3, "text": "Coordinates waste pickup schedules over phone calls and email"},
    ],
    "feels": [
        {"id": 1, "text": "Pressure from ESG ratings and procurement requirements of large retailers"},
        {"id": 2, "text": "Uncertainty about future EU Waste Directive penalties"},
        {"id": 3, "text": "Frustration with the inflexibility of current recycler contracts"},
    ],
    "pains": [
        {"id": 1, "text": "Logistics complexity: someone picks up waste, but not always on time"},
        {"id": 2, "text": "No automatic documentation for EU taxonomy"},
        {"id": 3, "text": "No single point of control across multiple recyclers at once"},
    ],
    "gains": [
        {"id": 1, "text": "30% reduction in waste disposal costs"},
        {"id": 2, "text": "Ready EU taxonomy documentation for ESG report"},
        {"id": 3, "text": "One reliable partner instead of fragmented contracts"},
    ],
},
    hypotheses=[
        hyp("H1.1", "Харчові підприємства готові перейти на маркетплейс замість прямих контрактів з переробниками", "desirability", "q1"),
        hyp("H1.2", "Комісія 8% з угод забезпечить беззбитковість маркетплейсу при GMV €2M/міс", "viability", "q2"),
        hyp("H2.1", "Алгоритм маршрутизації знизить логістичні витрати на 30% порівняно з прямими контрактами", "feasibility", "q2"),
        hyp("H2.2", "EU taxonomy автодокументація підвищить NPS серед enterprise-клієнтів до 65+", "desirability", "q3"),
        hyp("H3.1", "Біогазові заводи готові підключитись до платформи без інтеграційних витрат", "feasibility", "q4"),
    ],
    pitch={
        "investor": [
            {
                "type": 'hook',
                "headline": '€140B in organic waste going to EU landfills every year',
                "content": 'The EU Waste Framework Directive bans organics from landfills from 2027. All food companies must find an alternative.',
            },
            {
                "type": 'problem',
                "headline": 'Six fragmented recycler contracts — and zero documentation',
                "content": 'Finding a partner takes weeks of negotiation. Consultants charge €15k/year for the EU taxonomy report.',
            },
            {
                "type": 'solution',
                "headline": 'BioWaste Circular: organic waste marketplace',
                "content": 'Connecting 5,000+ food companies with a network of biogas plants. Optimized partner matching + logistics + EU documentation automatically.',
            },
            {
                "type": 'traction',
                "headline": '180 connected companies. GMV €1.2M. NPS 68.',
                "content": 'Average client cost reduction: €31k/year. Churn 3%. 94% of clients renewed subscriptions.',
            },
            {
                "type": 'ask',
                "headline": 'Raising €1.8M to expand biogas plant network in Poland and Romania',
                "content": 'EU Waste Directive TAM: €8B in Central Europe by 2027.',
            },
        ],
        "customer": [
            {
                "type": 'opening',
                "headline": '€80k a year on organic waste — and zero EU taxonomy documentation',
                "content": 'Six separate contracts with recyclers, email coordination, and consultants at €15k every year just to prepare the ESG report.',
            },
            {
                "type": 'empathy',
                "headline": 'Circular economy on paper, logistics chaos in practice',
                "content": 'Finding a reliable biogas partner takes weeks of negotiations. Tracking pickup status means calling the driver. EU taxonomy documentation is a separate year-end project.',
            },
            {
                "type": 'transformation',
                "headline": 'A verified partner in 5 minutes, EU taxonomy updated automatically',
                "content": 'BioWaste Circular matches verified biogas partners near your facility, handles the contract online, and updates EU taxonomy documentation after every transaction.',
            },
            {
                "type": 'social_proof',
                "headline": '"Cut costs from €80k to €54k, got EU taxonomy without consultants"',
                "content": '— Head of Sustainability, food holding, 3 production sites. €26k saved in year one + €15k on consulting.',
            },
            {
                "type": 'invitation',
                "headline": 'Sign up free and find your first partner this week',
                "content": 'Registration takes 10 minutes. First matched partner and indicative price — within 24 hours. No commitment required.',
            },
        ],
    },
    scenario={
        "persona": {
            "name": 'Natalia Bondar',
            "role": 'Head of Sustainability, food holding',
            "pain_point": 'Pays €80k/year for organic waste removal with no EU taxonomy documentation',
        },
        "timeline": [
            {
                "step_type": 'context',
                "text": 'Natalia pays €80k/year for organic waste disposal with no EU taxonomy documentation.',
            },
            {
                "step_type": 'goal',
                "text": 'Find a reliable biogas partner, cut disposal costs, and automate EU taxonomy reporting.',
            },
            {
                "step_type": 'action',
                "text": 'BioWaste Circular matched 3 partners in 5 minutes. Contract signed online, logistics automated.',
            },
            {
                "step_type": 'result',
                "text": 'EU taxonomy report updated automatically after the first transaction. Audit-ready.',
            },
            {
                "step_type": 'impact',
                "text": 'Disposal costs dropped from €80k to €54k/year. Natalia got full EU taxonomy documentation without a single consultant.',
            },
        ],
        "metrics": {
            "before": {
                "value": '€80,000/year',
                "label": 'Manual organic waste to landfill',
            },
            "after": {
                "value": '€54,000/year',
                "label": 'Automated biogas partner matching',
            },
        },
    },
    what_if={
        "alternatives": [
            {
                "id": uid(),
                "title": "Performance-based marketplace fee",
                "premise": "Charge a % of confirmed disposal-cost savings instead of a fixed subscription.",
                "moves": [
                    _errc_move("eliminate", "revenue_streams", "SaaS subscription: €799/mo per facility",
                        "The fixed subscription conflicts with pay-for-outcome pricing."),
                    _errc_move("raise", "revenue_streams", "Marketplace commission: 8% per waste transaction",
                        "Making the marketplace commission the primary revenue stream, not a supplementary one.",
                        new_text="Marketplace commission: 8-15% scaled to confirmed disposal-cost savings"),
                    _errc_move("create", "customer_relationships", "Monthly savings-to-billing transparency report",
                        "The client needs to see the direct link between savings and their bill."),
                ],
                "expected_impact": "Lower entry barrier for new clients; ARPU grows proportionally to value delivered.",
                "status": "applied",
            },
            {
                "id": uid(),
                "title": "Private network for regulated producers",
                "premise": "Large manufacturers can't share waste data on an open marketplace.",
                "moves": [
                    _errc_move("eliminate", "channels", "Food industry trade associations",
                        "The regulated segment closes through direct sales, not trade associations."),
                    _errc_move("raise", "key_resources", "Waste exchange marketplace algorithm",
                        "The algorithm needs private, non-public pools for sensitive data.",
                        new_text="Waste exchange marketplace algorithm with private, invite-only matching pools"),
                    _errc_move("create", "revenue_streams", "Private network enterprise license",
                        "New tier for manufacturers barred from sharing data publicly."),
                ],
                "expected_impact": "Access to the large-manufacturer segment with strict confidentiality requirements.",
                "status": "draft",
            },
            {
                "id": uid(),
                "title": "Public circularity rating",
                "premise": "A public circularity rating becomes a trust signal in FMCG procurement.",
                "moves": [
                    _errc_move("reduce", "customer_relationships", "Dedicated circular economy advisor per enterprise client",
                        "Cheaper self-serve support frees budget for the public showcase.",
                        new_text="Self-serve circularity dashboard, advisor escalation for complex cases"),
                    _errc_move("raise", "value_propositions", "Zero organic waste to landfill — 100% circular",
                        "The metric becomes a public trust proof for retail buyers.",
                        new_text="Zero organic waste to landfill — 100% circular, published live on a public rating"),
                    _errc_move("create", "channels", "Public circularity-score profile visible to retail buyers",
                        "New direct trust channel with retail buyers."),
                    _errc_move("create", "revenue_streams", "Third-party circularity-score verification fee",
                        "New monetization: verifying third-party circularity scores."),
                ],
                "expected_impact": "Reputational advantage for the manufacturer; new verification monetization for retail partners.",
                "status": "draft",
            },
        ]
    },
    architecture={
        "epicenter": "customer_driven",
        "epicenter_rationale": "Food companies are at the center of the ecosystem. The platform is built around their desire to cut costs and get EU taxonomy documentation effortlessly.",
        # Was "Open Business Model" + subtype "Ad-supported" in the old schema —
        # invalid under bizstruct_domain (ad_supported is a subtype of free,
        # not open_business_model). The rationale describes a two-sided
        # marketplace monetized by transaction commission, which is a
        # multi_sided_platform story, not free or open_business_model — and
        # multi_sided_platform takes no subtype.
        "pattern": "multi_sided_platform",
        "pattern_subtype": None,
        "pattern_rationale": "Free registration for food companies and biogas plants, monetization through 8% commission on each marketplace transaction.",
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
        language="en",
        translation_key=key,
        models_options={
            "options": [
                mo(f"B2B SaaS · {title}", "subscription", 72),
                mo(f"Marketplace · {title}", "transaction_fee", 58),
                mo(f"Advisory Platform · {title}", "retainer_plus_saas", 45),
            ],
            "selected_id": None,
        },
        canvas={
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
            hyp("H1.1", "Target users spend 5+ hours/week on manual tasks this product automates", "desirability", "q1"),
            hyp("H1.2", "Willingness to pay exceeds €500/month for the core use case", "viability", "q2"),
            hyp("H2.1", "The core integration can be built without a custom backend rewrite", "feasibility", "q2"),
            hyp("H2.2", "At least 30% of surveyed prospects rank this pain in their top 3 priorities", "desirability", "q3"),
            hyp("H3.1", "Onboarding a new customer takes under 2 weeks with existing tooling", "feasibility", "q4"),
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

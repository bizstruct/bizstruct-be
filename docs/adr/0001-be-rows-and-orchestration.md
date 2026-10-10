# ADR-0001: Рядки етапів і оркестрація в bizstruct-be

- **Status:** Accepted
- **Date:** 2026-10-08
- **Related:** bizstruct-domain ADR-0009 (граф етапів), ADR-0010 (контракти генерації), **ADR-0011 (wire contract; авторитетний)**, ADR-0012 (rule inputs)

## Context

До цього PR `bizstruct-be` зберігав по одному рядку `stages` на тип етапу (`UNIQUE(project_id, type)`) і мав `StageService`, `GenerationOrchestrator` та `QueuePort`, але не вмів ні кількох екземплярів етапу (по empathy_map на сегмент, по canvas на групу), ні приймати результат від `bizstruct-ml`. Старі роутери блоків (`blocks`, `models`, `validate_model`, `BLOCK_CHAIN`) уже були вимкнені в `routers/api.py` і лишалися мертвим кодом.

ADR-0011 визначає одиницю роботи — **рядок етапу** — і поділ ролей: be зберігає рядки, `refs`, статуси, чергу та hook і застосовує переходи стейт-машини; ml генерує, перевіряє узгодженість і повертає `StageResult`, але ніколи не пише статуси.

Цей ADR описує, як це реалізовано в be. Режим лише **pipeline**, з автопросуванням; без гейтингу користувачем і без агента.

## Decision

### Schema

- `projects`: власницькі колонки гілки без змін (`user_id`, …) + `title`, `idea`, `language`, `enabled_optional` (JSONB, список опційних `Stage`, `[]` за замовчуванням), `auto_approve` (bool, `false`), `created_at`, `updated_at`. Колонки `mode`, `status` і `consistency_loop` прибрано: статус проєкту **виводиться** з рядків (`project_status`), а режиму, окрім pipeline, немає.
- `stage_rows`: `id` (рядок з uuid), `project_id` (FK, `ON DELETE CASCADE`), `stage`, `instance_index`, `status`, `refs` (JSONB: етап → id рядків), `attempt_id`, `retry_count`, `error` (JSONB, `StageFailure`), `consistency` (JSONB, останній `ConsistencyReport`), `artifacts` (JSONB, список `ArtifactRecord`), `created_at`, `updated_at`, `started_at`, `finished_at`, `approved_at`. Індекс `(project_id, stage, instance_index)`. **Унікальності на `(project_id, stage)` немає**; `UNIQUE(id, type)` прибрано — на нього ніхто не посилався.
- Значення `stage` — 13 значень доменного `Stage`.

### Orchestration

Чисті правила — у `app/services/orchestration.py` (без FastAPI, БД і черги; працюють із доменними `StageRow`). Доменні функції (`ready_rows`, `dependent_rows`, `project_status`, `canvas_rows_for`, `row_of_artifact`, `validate_row_refs`, `parse_artifact`, стейт-машина, `MAX_SEGMENTS`) використовуються, а не переписуються.

1. **Створення проєкту:** рядок `brief` (`refs {}`) і рядки **увімкнених** опційних етапів `business_case`, `environment_scan` (`refs {brief}`). `team_info` тут не створюється ніколи.
2. **Розгортання після `DONE`** (`expand_rows`, ідемпотентне: дивиться, що вже існує за `refs` та `instance_index`, і повертає лише відсутнє):
   - `brief` → `empathy_map` на кожного кандидата (не більше `MAX_SEGMENTS`, `instance_index = k`), на кожну карту — `customer_scenario` та `ideation` (`refs {empathy_map}`, індекс 0), і один рядок `patterns` (`refs` — усі сценарії й ідеації);
   - `patterns` → рядки `canvas` з `canvas_rows_for` (`refs`: brief, карти групи через `row_of_artifact`, їхні сценарії й ідеації, patterns; `instance_index` — позиція групи);
   - `canvas` → `swot_errc_cycle` (`refs {canvas}` + `{environment_scan}`, якщо увімкнено), `storytelling` і `future_scenario` (`refs {cycle}`), `pitch` (`refs {storytelling, cycle}` + `business_case`/`team_info`, якщо увімкнено й рядок існує); індекс 0.
   - Кожен `refs` перевіряється `validate_row_refs`.
3. **Просування (`advance`):** для кожного рядка з `ready_rows`: `PENDING → RUNNING`, новий `attempt_id`, `started_at`; після коміту — одне `QueueMessage` з однією ціллю на рядок.
4. **Застосування `StageResult` (hook):** невідомий проєкт чи рядок — 404; рядок не `RUNNING` або інший `attempt_id` — 409; артефакти не проходять `parse_artifact` (або id запису ≠ власному id артефакту, або тип не може жити в цьому етапі) — рядок у `ERROR` (`generation_failed`) і 422; `failed` — `ERROR` із `StageFailure`; `success` — артефакти й звіт зберігаються (набір артефактів рядка **замінюється повністю**), `RUNNING → CONSISTENCY_CHECK → DONE`, або `→ AWAITING_DECISION` за наявності порушення рівня `error`. Далі в тій самій транзакції — розгортання й просування.
5. **Lazy watchdog:** при читанні проєкту (`GET /api/projects`, `GET /api/projects/{id}`) рядок, що `RUNNING` довше `STUCK_TIMEOUT_SECONDS` (за замовчуванням 1800), стає `ERROR` (`stuck_timeout`). Фонового воркера немає.
6. **Regenerate / approve:** `POST /api/projects/{id}/rows/{row_id}/regenerate` повертає рядок і всі `dependent_rows` у `PENDING` із очищеними артефактами (id рядків лишаються, тому похідні id артефактів лишаються чинними) і просуває; `…/approve` застосовує approve до `AWAITING_DECISION`. Допустимість визначає `available_actions` стейт-машини; недопустимо — 409.

Кожна операція — **одна транзакція**: блокується рядок проєкту (`SELECT … FOR UPDATE`), зміни фіксуються одним комітом, і лише потім публікуються події та надсилаються повідомлення. Блокування проєкту серіалізує паралельні hook-и одного проєкту, тож розгортання не створює рядок двічі.

### Auto-advance and auto_approve

Рядки запускаються автоматично, щойно всі їхні входи `DONE`. `auto_approve = true`: після `AWAITING_DECISION` одразу застосовується approve (`→ DONE`, `approved_at`), звіт узгодженості зберігається. Без `auto_approve` рядок чекає виклику approve або regenerate.

### HTTP

- `POST /api/generation` (автентифікація гілки): `{title?, idea, language, enabledOptional?, autoApprove?}` → проєкт з рядками, 201. `enabledOptional` приймає лише `business_case` і `environment_scan` (див. «Conflicts with ADR-0011», п. 3).
- `GET /api/projects/{id}` — `id, title, idea, language, enabledOptional, autoApprove, status, rows[]`; зовнішні поля camelCase, вкладені доменні моделі (`artifacts`, `consistency`, `error`) лишаються snake_case. Є також список, `PATCH` назви та видалення.
- `GET /api/internal/projects/{id}?row=<row_id>` → `ProjectSnapshot` (з `row` — цей рядок і транзитивне замикання його `refs`); `POST /api/internal/hook` ← `StageResult`: 200/404/409/422. Обидва — за `x-api-key`.
- Web PubSub: після кожного застосованого переходу публікується доменний `StageEvent`; з порожнім рядком підключення — no-op. Подія `pending` публікується й для щойно створених рядків.

## The database reset (why no data migration)

Старі рядки описують іншу модель (одна на тип, без `refs`/`attempt_id`/артефактів), а `stages` ніколи не створювалась ревізією Alembic цього ланцюга (її створював лише `create_all` у тестах). Мігрувати даних нема куди й нема чого. Нова ревізія `f1a2b3c4d5e6` лежить **поверх** наявного ланцюга (базова не переписувалась): прибирає `stages` (якщо вона є), колонки `mode`/`status`/`consistency_loop` у `projects`, додає `enabled_optional`/`auto_approve` і створює `stage_rows`. **Том бази даних слід створити заново** (або принаймні очистити `projects`) перед новою генерацією.

## What was kept, changed and removed

**`StageService`** (єдиний власник переходів):
- *Залишено:* `transition` як єдине місце зміни статусу, перевірка через доменний `is_valid_transition`, `ValueError` на несумісні прапорці, `increment_retry`/`reset_retry`, скорочення повідомлення про помилку до 500 символів, `approved`/`approved_at`, `reset_from`, правило «сервіс ніколи не комітить».
- *Змінено:* оперує `StageRow`, а не `Stage`, ключ — `row_id`, а не тип; `create_stages` → `create_rows` (приймає специфікації планувальника й не перевіряє дублікатів — що створювати, вирішує чисте планування); `get_stages`/`get_stage` → `get_rows` (порядок: граф, потім `instance_index`)/`get_row`; помилка зберігається як `StageFailure` (JSONB) замість `error_code` + `error`; вхід у `RUNNING` завжди видає новий `attempt_id`; перехід у `PENDING` очищає артефакти, звіт і спробу; `reset_from` бере рядки через `dependent_rows` за `refs`, а не `dependents_of` за типом. Додано `record_result` (заміна всього набору артефактів), `stale_running_rows` (watchdog), `to_wire_row`.
- *Прибрано:* `StagesAlreadyExist` та `create_stages` — унікальності більше немає.

**`GenerationOrchestrator`:**
- *Залишено:* `fail`, `cancel`, компенсація при збої черги (`RUNNING → ERROR`, `queue_unavailable`), правило «спершу коміт, потім сигнал назовні».
- *Змінено:* `run_stage` + `advance(project_language)` замінено на `start`, `apply_result`, `advance`, `regenerate`, `approve`, `expire_stuck`; просування бере готові рядки з `ready_rows` (за рядками, а не за типами); одна транзакція на операцію замість коміту на кожен етап. Advisory-блокування на окремому з'єднанні замінено блокуванням рядка проєкту: воно потрібне було лише тому, що `run_stage` комітив усередині циклу, а тепер коміт один.
- *Прибрано:* прапорці `force`/`comment` повідомлення (ADR-0011 Q4: прапорця `force` немає, перегенерація — це нова спроба).

**`QueuePort`:** `enqueue_generation(...)` → `enqueue(QueueMessage)` (доменна форма); `request_cancellation` тепер за `stage_row_id`. Додано `EventPort` (`publish(StageEvent)`) і адаптери `ServiceBusQueue`, `WebPubSubEvents`.

**Видалено:** `Stage`-модель із `UNIQUE(project_id, type)`, `block_chain.py`, `routers/blocks.py`, `routers/models.py`, шлях `validate_model`, `seed.py`, застарілі модулі `app/models.py`, `app/schemas.py`, `app/database.py` (затінені пакетами / без жодного імпорту після чистки), `POST /api/projects` (замінено на `POST /api/generation`) і всі тести блоків та hook-ів, які на цій гілці вже не запускалися (немає таблиць).

## Conflicts with ADR-0011 resolved

1. **Дублікат результату: 200 чи 409.** Q4 каже «дубль — 200 без змін», Q9 — «рядок уже не `RUNNING` → 409». Рішення: результат того самого `attempt_id` для рядка в `DONE`/`AWAITING_DECISION` — дубль, 200 без змін; будь-який інший не-`RUNNING` рядок або чужий `attempt_id` — 409 (зокрема пізній результат після `stuck_timeout`).
2. **Форма помилки.** be зберігає `StageFailure` (JSONB), а wire-`StageRow` має `error_code` і `error`; знімок розгортає одне в інше.
3. **`team_info` у `enabledOptional`.** ADR допускає його вмикати (споживач заблокований до введення даних), але подання даних ще немає, тож `pitch` завис би назавжди. API відхиляє `team_info` з 422, доки не з'явиться подання. Рядок `pitch` додає `refs[team_info]`, лише якщо рядок `team_info` існує в момент створення; подання, коли з'явиться, має дописати посилання в наявні `pitch`.
4. **Обмеження `MAX_SEGMENTS`.** `Brief` сам відхиляє понад 3 кандидатів, тож такий результат отримує 422 і рядок `brief` у `ERROR`; зрізання `[:MAX_SEGMENTS]` у плануванні — страховка, перевірена окремим тестом.
5. **Patterns, що називає невідому карту.** ADR мовчить. Результат `patterns`, у якому група називає id empathy map, якого не має жоден рядок `empathy_map`, відхиляється 422 до застосування (`DONE → ERROR` не існує, а canvas-рядок побудувати неможливо).
6. **Скасування.** У ADR-0011 немає повідомлення про скасування, тож `request_cancellation` у `ServiceBusQueue` лише логується; запізнілий результат скасованого рядка отримає 409.
7. **`approved_at`** лишено (ADR його не згадує, але він не конфліктує і фіксує момент approve).
8. **Події.** Окрім переходів, публікуються події зі статусом `pending` для щойно створених рядків, щоб клієнт знав про нові рядки.

## Deferred

- Режим із гейтингом користувачем (зупинка після кожного рядка) і режим агента (`StageProgress`, кілька цілей у повідомленні).
- Фронтенд (`bizstruct-fe`) і camelCase-контракт на його боці.
- Подання користувацького `team_info` (рядок одразу `DONE`) і дописування його в `refs` наявних `pitch`.
- CRUD-редагування артефактів; `validate_model`.
- Перегенерація `brief`, після якої змінюється кількість сегментів: наявні рядки не видаляються й не додаються (розгортання не прибирає зайвого); `refs` рядка `patterns` не оновлюються.
- `/health` і `/api/negotiate` у цій гілці закоментовані в `routers/api.py` і не змінювались.
- Ліміт продовження блокування повідомлень у ml (ADR-0011, «Ризики») — справа ml.

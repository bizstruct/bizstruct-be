# BizStruct Database Schema v1.1 (Core)

**Статус:** `Approved by Architect`  
**Технологічний стек:** PostgreSQL + SQLAlchemy 2.0 (Async)  
**Концепція:** Hybrid Relational-Object Model (Strict Hierarchy + JSONB for flexibility)

---

## 1. Архітектурна ієрархія
Система побудована за принципом каскадної вкладеності сутностей для забезпечення цілісності даних та контексту:
**User** $\rightarrow$ **Project** (Бізнес-ідея) $\rightarrow$ **Canvas** (Ітерація/Версія) $\rightarrow$ **Block** (9 секцій) $\rightarrow$ **Sticker** (Атом даних).

---

## 2. Специфікація таблиць

### 2.1. Таблиця `users`
Керування автентифікацією та ідентифікацією користувачів.

| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK, Default: `uuid_generate_v4()` | Унікальний ідентифікатор |
| **email** | VARCHAR(255) | Unique, Indexed, Not Null | Логін / Контактна пошта |
| **hashed_password** | VARCHAR(255) | Not Null | Хеш пароля (Bcrypt/Argon2) |
| **full_name** | VARCHAR(255) | Nullable | ПІБ користувача |
| **created_at** | TIMESTAMP | Default: `NOW()` | Дата створення акаунту |

### 2.2. Таблиця `projects`
Верхньорівневий контейнер для конкретної бізнес-ідеї стартапу.

| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | ID проекту |
| **user_id** | UUID | FK (`users.id`), Indexed | Власник проекту |
| **name** | VARCHAR(255) | Not Null | Назва ідеї (напр. "BizStruct") |
| **description** | TEXT | Nullable | Загальний опис ідеї |
| **created_at** | TIMESTAMP | Default: `NOW()` | Дата створення |
| **updated_at** | TIMESTAMP | Default: `NOW()` | Дата оновлення |

### 2.3. Таблиця `canvases`
Конкретна версія бізнес-моделі (дозволяє робити півоти та порівнювати ітерації).

| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | ID канвасу |
| **project_id** | UUID | FK (`projects.id`), Indexed | Посилання на проект |
| **title** | VARCHAR(255) | Not Null | Назва версії (напр. "MVP v1") |
| **is_active** | BOOLEAN | Default: `TRUE` | Чи є цей канвас актуальним |
| **created_at** | TIMESTAMP | Default: `NOW()` | Дата створення |
| **updated_at** | TIMESTAMP | Default: `NOW()` | Дата оновлення |

### 2.4. Таблиця `canvas_blocks`
9 структурних сегментів за методологією Остервальдера.

| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | ID блоку |
| **canvas_id** | UUID | FK (`canvases.id`), Indexed | Посилання на канвас |
| **block_type** | ENUM | Not Null | Тип блоку (див. Enums) |
| **updated_at** | TIMESTAMP | Default: `NOW()` | Мітка для інвалідації кешу |

### 2.5. Таблиця `stickers`
Атомарна одиниця інформації ("стікер"), що містить як текст, так і складні дані.

| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | ID стікера |
| **block_id** | UUID | FK (`canvas_blocks.id`) | Секція, до якої належить |
| **title** | VARCHAR(255) | Not Null | Заголовок для UI |
| **description** | TEXT | Nullable | Короткий опис |
| **priority** | INTEGER | Default: `0` | Пріоритет (для фільтрації Top-3) |
| **details** | JSONB | Default: `'{}'` | Об'єктні дані (ціни, сегменти) |
| **created_at** | TIMESTAMP | Default: `NOW()` | Дата створення |
| **updated_at** | TIMESTAMP | Default: `NOW()` | Дата оновлення |

---

## 3. Словники та типи (Enums)

### `BlockType` (9 обов'язкових блоків):
* `VALUE_PROPOSITION`
* `CUSTOMER_SEGMENTS`
* `CHANNELS`
* `CUSTOMER_RELATIONSHIPS`
* `REVENUE_STREAMS`
* `KEY_ACTIVITIES`
* `KEY_RESOURCES`
* `KEY_PARTNERSHIPS`
* `COST_STRUCTURE`

---

## 4. Дизайнерські рішення (Architectural Decisions)

* **JSONB для `details`**: Обрано для забезпечення гнучкості. Кожен тип блоку матиме свою Pydantic-схему на рівні бекенду для валідації вмісту цього поля.
* **Топ-3 фільтрація**: Поле `priority` дозволяє фронтенду та AI-агентам ідентифікувати найважливіші елементи моделі.
* **Автоматичні мітки часу**: Кожна таблиця містить `updated_at` для відстеження "свіжості" контексту для LLM-агентів та асинхронної синхронізації.




# BizStruct Database Schema v1.2 (Unified Business & Empathy Mapping)

**Статус:** `Approved by Senior Architect`  
**Технологічний стек:** PostgreSQL + SQLAlchemy 2.0 (Async)  
**Концепція:** Hybrid Relational-Object Model (Polymorphic Blocks + JSONB Details)

---

## 1. Архітектурна ієрархія
Система спроектована як ієрархічний граф, де кожна бізнес-ідея (`Project`) може мати декілька інструментів аналізу (Артефактів).

**User** $\rightarrow$ **Project** $\rightarrow$ **Artifact** (`Canvas` / `EmpathyMap`) $\rightarrow$ **Block** $\rightarrow$ **Sticker**

---

## 2. Специфікація таблиць

### 2.1. Таблиця `users` (Auth & Identity)
| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK, Default: `gen_random_uuid()` | - |
| **email** | VARCHAR | Unique, Not Null, Indexed | Логін користувача |
| **hashed_password** | VARCHAR | Not Null | Зашифрований пароль |
| **created_at** | TIMESTAMP | Default: `NOW()` | - |

### 2.2. Таблиця `projects` (Business Idea Container)
| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | - |
| **user_id** | UUID | FK (`users.id`), Indexed | Власник проекту |
| **name** | VARCHAR | Not Null | Назва стартапу/ідеї |
| **created_at** | TIMESTAMP | Default: `NOW()` | - |
| **updated_at** | TIMESTAMP | Default: `NOW()` | - |

### 2.3. Таблиця `canvases` (Business Model Canvas - BMC)
| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | - |
| **project_id** | UUID | FK (`projects.id`), Indexed | Прив'язка до проекту |
| **title** | VARCHAR | Not Null | Назва ітерації (напр. "Pivot v1") |
| **is_active** | BOOLEAN | Default: `TRUE` | Актуальна версія моделі |
| **created_at**, **updated_at** | TIMESTAMP | Default: `NOW()` | - |

### 2.4. Таблиця `empathy_maps` (Empathy Map Canvas)
| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | - |
| **project_id** | UUID | FK (`projects.id`), Indexed | Прив'язка до проекту |
| **title** | VARCHAR | Not Null | Назва персони (напр. "Student") |
| **designed_for** | VARCHAR | Nullable | Цільова група |
| **created_at**, **updated_at** | TIMESTAMP | Default: `NOW()` | - |

### 2.5. Таблиця `blocks` (Unified Sections)
Центральна таблиця для всіх секцій. Один запис належить або до Канвасу, або до Карти Емпатії.
| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | - |
| **canvas_id** | UUID | FK (`canvases.id`), Nullable | Якщо це блок BMC |
| **empathy_map_id** | UUID | FK (`empathy_maps.id`), Nullable | Якщо це блок Емпатії |
| **type** | ENUM | Not Null, Indexed | Див. секцію "Enums" |
| **updated_at** | TIMESTAMP | Default: `NOW()` | Для інвалідації кешу ШІ |
| **Constraint** | CHECK | `(canvas_id IS NULL) != (empathy_map_id IS NULL)` | Гарантує приналежність до одного артефакту |

### 2.6. Таблиця `stickers` (Atomic Data)
| Поле | Тип | Обмеження | Опис |
| :--- | :--- | :--- | :--- |
| **id** | UUID | PK | - |
| **block_id** | UUID | FK (`blocks.id`), Indexed | Секція на дошці |
| **title** | VARCHAR | Not Null | Заголовок для UI |
| **description** | TEXT | Nullable | Детальний розпис стікера |
| **priority** | INTEGER | Default: `0` | Для фільтрації "Top-3" |
| **details** | JSONB | Default: `'{}'` | Структуровані дані (ціни, теги, мета) |
| **created_at**, **updated_at** | TIMESTAMP | Default: `NOW()` | - |

---

## 3. Словники (Enums)

### `BlockType` (Повний список секцій):

#### Business Model Canvas (BMC):
`BMC_VALUE_PROP`, `BMC_CUSTOMER_SEGMENTS`, `BMC_CHANNELS`, `BMC_RELATIONSHIPS`, `BMC_REVENUE`, `BMC_ACTIVITIES`, `BMC_RESOURCES`, `BMC_PARTNERS`, `BMC_COSTS`.

#### Empathy Map (Customer Insights):
* `EMPATHY_WHO` — Хто цей клієнт?
* `EMPATHY_NEED_DO` — Що йому потрібно зробити?
* `EMPATHY_HEAR` — Що він чує?
* `EMPATHY_SEE` — Що він бачить?
* `EMPATHY_SAY` — Що він каже?
* `EMPATHY_DO` — Що він робить?
* `EMPATHY_PAIN` — Його страхи та болі (Think & Feel).
* `EMPATHY_GAIN` — Його бажання (Think & Feel).
* `EMPATHY_OTHER_THOUGHTS` — Приховані думки та мотивація.

---

## 4. Архітектурні рішення (ADR)

* **Поліморфні Блоки**: Використання однієї таблиці `blocks` з `Nullable FK` дозволяє нам мати єдину логіку для `stickers`. Це спрощує роботу ШІ-агента — йому не важливо, на якій "дошці" стікер, він просто працює з `BlockType`.
* **JSONB `details`**: Замість створення десятків таблиць для параметрів (ціна, частота, сегмент), ми використовуємо JSONB. Це дозволяє нам змінювати "глибину" розпису стікера без міграцій бази даних.
* **Гранулярність Емпатії**: Розподіл центрального блоку "Think & Feel" на `PAIN` та `GAIN` на рівні бази даних дозволяє ШІ миттєво генерувати аналітику ризиків та можливостей без текстового парсингу.
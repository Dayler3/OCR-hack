# ТЕХНИЧЕСКОЕ ЗАДАНИЕ И АРХИТЕКТУРНЫЙ ПЛАН
## Проект: «Цифровой секретарь онлайн-деканата» (Хакатон 7 дней)

---

### 1. ОБЩЕЕ ОПИСАНИЕ И ЦЕЛЬ ПРОЕКТА
Разработать автономный программный комплекс «Цифровой секретарь», автоматизирующий первичную обработку обращений студентов в деканат[cite: 1, 2].
Сервис принимает скан или фотографию документа (JPG, PNG, PDF) и текстовый вопрос студента на русском языке[cite: 4, 7].
Комплекс выполняет распознавание текста (OCR)[cite: 4, 7], заполняет карточку атрибутов документа (фиксируя «не найдено» при отсутствии данных)[cite: 4, 7], верифицирует данные по нормативному «Положению о приёме документов» вуза и генерирует обоснованный ответ со ссылкой на пункты регламента без генеративных галлюцинаций[cite: 4, 5, 7].
Интерфейс решения: веб-страница (или Telegram-бот)[cite: 7].

---

### 2. СИСТЕМНЫЕ ОГРАНИЧЕНИЯ И СРЕДА ИСПОЛНЕНИЯ
1. **Запрет внешних API:** Запрещено использование сторонних облачных LLM-сервисов (GigaChat, YandexGPT, OpenAI API, Anthropic и др.)[cite: 10].
2. **Аппаратные ресурсы:** Система должна запускаться и функционировать локально на CPU стандартного ПК/ноутбука либо в бесплатном Google Colab (CPU / 1x T4 GPU)[cite: 10].
3. **OCR-библиотеки:** Допустимо применение только открытых решений: PaddleOCR, EasyOCR, Tesseract[cite: 10]. Основной рекомендуемый движок — **PaddleOCR (PP-OCRv4)**[cite: 10].
4. **Входные данные:** Одностраничные и многостраничные файлы форматов JPG, PNG, PDF[cite: 7].
5. **Официальный датасет задачи:** Проект опирается на приложенный открытый бенчмарк **`MTSAIR/MWS-Vision-Bench`** (Hugging Face / MTS AI). Спецификация аннотаций (`metadata.jsonl`: пары `file_name` + `question`, задачи `key information extraction ru`, `text grounding ru`, `reasoning VQA ru`) выступает стандартом входных данных и валидации.

---

### 3. СТРУКТУРЫ ДАННЫХ И ТИПЫ ДОКУМЕНТОВ
Сервис обрабатывает 3 базовых типа документов со строго фиксированными атрибутами[cite: 6].
Тип документа может быть выбран пользователем вручную (базовое требование) либо определен системой автоматически (бонусный функционал)[cite: 7, 9].
Если реквизит отсутствует или не распознан, значение поля строго равно строке `«не найдено»`[cite: 7].
Для атрибутов подписи и печати допустимы исключительно бинарные статусы: `«есть»` или `«нет»`[cite: 6].
Аннотации обучающих и тестовых пар поставляются в формате `metadata.jsonl` (по стандарту `MWS-Vision-Bench`).

#### 3.1. Справка об обучении (`study_certificate`)[cite: 6]
* `fio` — ФИО студента[cite: 6]
* `university` — Название вуза[cite: 6]
* `study_direction` — Направление подготовки / специальность[cite: 6]
* `study_form` — Форма обучения (очная, заочная, очно-заочная)[cite: 6]
* `study_period` — Период обучения[cite: 6]
* `doc_number_and_date` — Номер и дата выдачи документа[cite: 6]
* `stamp_and_signature` — Подпись и печать (`есть` / `нет`)[cite: 6]

#### 3.2. Заявление на академический отпуск (`academic_leave_application`)[cite: 6]
* `fio` — ФИО студента[cite: 6]
* `group_and_course` — Номер группы и курс[cite: 6]
* `leave_reason` — Причина отпуска[cite: 6]
* `start_date` — Дата начала отпуска (`ДД.ММ.ГГГГ`)[cite: 6]
* `end_date` — Дата окончания отпуска (`ДД.ММ.ГГГГ`)[cite: 6]
* `application_date` — Дата подачи заявления (`ДД.ММ.ГГГГ`)[cite: 6]
* `signature` — Подпись студента (`есть` / `нет`)[cite: 6]

#### 3.3. Справка о практике (`internship_certificate`)[cite: 6]
* `fio` — ФИО студента[cite: 6]
* `organization` — Профильная организация / предприятие[cite: 6]
* `internship_period` — Сроки практики[cite: 6]
* `internship_supervisor` — Руководитель практики[cite: 6]
* `grade` — Оценка[cite: 6]
* `doc_number_and_date` — Номер и дата выдачи[cite: 6]
* `stamp_and_signature` — Подпись и печать (`есть` / `нет`)[cite: 6]

---

### 4. ЛОГИКА ОТВЕТОВ И БАЗА ЗНАНИЙ (RAG & RULE ENGINE)
База знаний представляет собой нормативное «Положение о приёме документов» вуза с нумерованными пунктами[cite: 5].
Ответ сервиса обязан строго соответствовать одной из 3 эталонных категорий[cite: 8]:

1. **«Документ в порядке»:** Документ содержит все обязательные реквизиты, предписанные пунктом Положения[cite: 8].
   * *Шаблон:* `«{Тип документа} содержит все данные, которые требует п. {X.X} Положения. Окончательное решение примет сотрудник деканата»`[cite: 8].
2. **«Чего-то не хватает»:** В документе отсутствуют обязательные поля для регламентированного действия[cite: 8].
   * *Шаблон:* `«Не хватает {список отсутствующих полей}. Эти поля обязательны по п. {X.X} Положения»`[cite: 8].
3. **«Ответа нет»:** В документе или Положении отсутствует информация по запрашиваемому вопросу[cite: 8].
   * *Шаблон:* `«В документе и в Положении нет информации о {тема вопроса}. Обратитесь в деканат»`[cite: 8].

---

### 5. ПРОДВИНУТЫЙ УРОВЕНЬ (БОНУСНЫЙ ФУНКЦИОНАЛ)
* **Автоопределение типа документа:** Классификация типа документа без ручного выбора пользователем (с возможностью ручной корректировки)[cite: 7, 9].
* **Устойчивость к сложным сканам:** Автоматическая компенсация наклона документа до 30°, удаление бликов, локальных теней и адаптивное повышение четкости при низком разрешении[cite: 9].
* **Конфигурирование новых типов без кода:** Добавление новых документов через YAML-схему без правки Python-кода[cite: 9].
* **Интерактивная подсветка на снимке:** Визуализация Bounding Box найденных реквизитов поверх исходного изображения[cite: 9].

---

### 6. СТЕК ТЕХНОЛОГИЙ

#### Backend:
* **Язык и среда:** Python 3.10+
* **Веб-фреймворк:** FastAPI + Uvicorn
* **OCR & Computer Vision:** PaddleOCR (PP-OCRv4), OpenCV (`opencv-python-headless`), PyMuPDF (`fitz`), NumPy[cite: 10]
* **Парсинг и NLP:** Natasha (NER для русских имен на CPU), RapidFuzz (нечеткий поиск по Левенштейну), RegEx
* **RAG / Валидация:** rank-bm25, SentenceTransformers (`cointegrated/rubert-tiny2`), Pydantic v2, PyYAML
* **Датасет и бенчмарк:** Hugging Face `datasets` (работа с `MTSAIR/MWS-Vision-Bench`)

#### Frontend:
* **Фреймворк:** React 19, TypeScript, Vite
* **Стилизация:** Tailwind CSS
* **UI-компоненты:** shadcn/ui (`Card`, `Badge`, `Alert`, `Button`, `Textarea`, `Select`)
* **Иконки:** Lucide React

---

### 7. СТРУКТУРА РЕПОЗИТОРИЯ

```text
online-dekanat/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py              # REST API: /api/analyze, /api/schemas
│   │   ├── core/
│   │   │   ├── pipeline.py            # Оркестратор сквозного пайплайна
│   │   │   ├── preprocessor.py        # Deskew (выравнивание до 30°), CLAHE, бинаризация, апскейл
│   │   │   ├── ocr_engine.py          # PaddleOCR обвязка с отдачей BBox
│   │   │   ├── classifier.py          # Автоопределение типа документа по ключевым якорям
│   │   │   ├── cv_detectors.py        # Поиск печати (HSV) и штрихов подписи
│   │   │   ├── extractor.py           # Извлечение полей по YAML-схеме (Natasha + Regex)
│   │   │   ├── rag_engine.py          # BM25 + rubert-tiny2 поиск пунктов правил
│   │   │   └── validator.py           # Детерминированный Rule Engine проверки полей
│   │   ├── schemas/
│   │   │   └── models.py              # Схемы Pydantic v2
│   │   ├── config.py
│   │   └── main.py                    # Инициализация FastAPI и CORS
│   ├── configs/
│   │   └── document_schemas.yaml      # Декларативная конфигурация типов документов
│   ├── data/
│   │   ├── regulations.json           # Структурированное Положение вуза по пунктам
│   │   └── mws_bench/                 # Выборка тестовых сэмплов MTSAIR/MWS-Vision-Bench
│   ├── scripts/
│   │   └── download_dataset.py        # Загрузка и экспорт сэмплов из Hugging Face
│   ├── batch_eval.py                  # Автоскрипт генерации results.json для тестов
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui компоненты
│   │   │   ├── DocumentViewer.tsx     # Просмотр скана + SVG Bounding Boxes
│   │   │   ├── FieldsCard.tsx         # Таблица распознанных полей
│   │   │   ├── VerdictAlert.tsx       # Баннер решения со ссылкой на Положение
│   │   │   └── UploadZone.tsx         # Загрузка скана и ввод вопроса
│   │   ├── types/
│   │   │   └── index.ts               # TypeScript интерфейсы
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── tailwind.config.js
└── README.md

```

---

### 8. ДЕТАЛЬНАЯ РЕАЛИЗАЦИЯ БЭКЕНДА

#### 8.1. `backend/configs/document_schemas.yaml`

```yaml
documents:
  study_certificate:
    name: "Справка об обучении"
    anchors: ["справка об обучении", "действительно обучается", "в том что он"]
    fields:
      fio:
        type: "ner_person"
        regex: "выдана\\s+([А-ЯЁ][а-яё]+\\s+[А-ЯЁ][а-яё]+\\s+[А-ЯЁ][а-яё]+)"
      university:
        type: "anchor_after"
        anchors: ["в", "университет", "институт", "академия"]
      study_direction:
        type: "regex"
        regex: "(?:направлени[юе]|специальност[иь])\\s*[:\\-]?\\s*([А-Яа-яA-Za-z0-9\\s\\.\\,\"]+?)(?=\\s*формы|\\n|$)"
      study_form:
        type: "options"
        options: ["очная", "заочная", "очно-заочная"]
      study_period:
        type: "regex"
        regex: "период[а-я]*\\s*с?\\s*(\\d{2}\\.\\d{2}\\.\\d{4}\\s*(?:по|-|до)\\s*\\d{2}\\.\\d{2}\\.\\d{4})"
      doc_number_and_date:
        type: "regex"
        regex: "№?\\s*([A-Za-z0-9\\-\\/]+)\\s+от\\s+(\\d{2}\\.\\d{2}\\.\\d{4})"
      stamp_and_signature:
        type: "cv_stamp_and_sign"

  academic_leave_application:
    name: "Заявление на академический отпуск"
    anchors: ["заявление", "академический отпуск", "прошу предоставить"]
    fields:
      fio:
        type: "ner_person"
        regex: "от\\s+студент[а-я]*\\s+([А-ЯЁ][а-яё]+\\s+[А-ЯЁ][а-яё]+\\s+[А-ЯЁ][а-яё]+)"
      group_and_course:
        type: "regex"
        regex: "групп[а-я]*\\s*[:\\-]?\\s*([A-Za-zА-Яа-я0-9\\-]+).*?(\\d\\s*курс)"
      leave_reason:
        type: "regex"
        regex: "причин[а-е]\\s*[:\\-]?\\s*([А-Яа-яA-Za-z0-9\\s\\,]+?)(?=\\s*с|\\n|$)"
      start_date:
        type: "regex"
        regex: "с\\s*(\\d{2}\\.\\d{2}\\.\\d{4})"
      end_date:
        type: "regex"
        regex: "(?:по|до)\\s*(\\d{2}\\.\\d{2}\\.\\d{4})"
      application_date:
        type: "regex"
        regex: "(\\d{2}\\.\\d{2}\\.\\d{4})"
      signature:
        type: "cv_signature_only"

  internship_certificate:
    name: "Справка о практике"
    anchors: ["справка о практике", "прохождении практики", "производственной практики"]
    fields:
      fio:
        type: "ner_person"
        regex: "студент[а-я]*\\s+([А-ЯЁ][а-яё]+\\s+[А-ЯЁ][а-яё]+\\s+[А-ЯЁ][а-яё]+)"
      organization:
        type: "anchor_after"
        anchors: ["организация", "предприятие", "база практики"]
      internship_period:
        type: "regex"
        regex: "сроки?\\s*с?\\s*(\\d{2}\\.\\d{2}\\.\\d{4}\\s*(?:по|-|до)\\s*\\d{2}\\.\\d{2}\\.\\d{4})"
      internship_supervisor:
        type: "ner_person"
        regex: "руководитель\\s*[:\\-]?\\s*([А-ЯЁ][а-яё]+\\s+[А-ЯЁ][а-яё]+\\s+[А-ЯЁ][а-яё]+)"
      grade:
        type: "options"
        options: ["отлично", "хорошо", "удовлетворительно", "зачтено", "5", "4", "3"]
      doc_number_and_date:
        type: "regex"
        regex: "№?\\s*([A-Za-z0-9\\-\\/]+)\\s+от\\s+(\\d{2}\\.\\d{2}\\.\\d{4})"
      stamp_and_signature:
        type: "cv_stamp_and_sign"

```

#### 8.2. Препроцессинг изображений (`backend/app/core/preprocessor.py`)

```python
import cv2
import numpy as np

def deskew_and_enhance(image: np.ndarray) -> np.ndarray:
    """
    Компенсация наклона до 30 градусов, устранение неравномерных теней,
    бликов и повышение качества при низком разрешении скана.
    """
    h, w = image.shape[:2]
    
    # 1. Адаптивный апскейл при низком разрешении (если меньшая сторона < 1200px)
    if min(h, w) < 1200:
        scale = 1200 / min(h, w)
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        h, w = image.shape[:2]

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 2. Определение угла наклона через HoughLinesP
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=20)
    
    angle = 0.0
    if lines is not None:
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            deg = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if -35.0 <= deg <= 35.0 and abs(deg) > 0.5:
                angles.append(deg)
        if len(angles) > 0:
            angle = float(np.median(angles))
            
    # Поворот изображения при наличии наклона
    if abs(angle) > 0.5:
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        image = cv2.warpAffine(image, rot_mat, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        
    # 3. Нормализация освещения через CLAHE (удаление теней/бликов)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge((cl, a, b_ch)), cv2.COLOR_LAB2BGR)
    
    return enhanced

```

#### 8.3. Детекция печати и подписи (`backend/app/core/cv_detectors.py`)

```python
import cv2
import numpy as np

def detect_stamp(image: np.ndarray) -> bool:
    """Детекция синей/фиолетовой гербовой печати в нижней половине документа."""
    h, _, _ = image.shape
    bottom_half = image[int(h * 0.45):, :]
    hsv = cv2.cvtColor(bottom_half, cv2.COLOR_BGR2HSV)
    
    # Диапазоны сине-фиолетовых чернил
    blue_mask = cv2.inRange(hsv, np.array([95, 50, 50]), np.array([130, 255, 255]))
    violet_mask = cv2.inRange(hsv, np.array([130, 50, 50]), np.array([160, 255, 255]))
    mask = cv2.bitwise_or(blue_mask, violet_mask)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000:
            perimeter = cv2.arcLength(cnt, True)
            if perimeter > 0:
                circularity = 4 * np.pi * (area / (perimeter * perimeter))
                if circularity > 0.25:  # Характерная форма круглой/овальной печати
                    return True
    return False

def detect_signature(image: np.ndarray, signature_bbox: list = None) -> bool:
    """Анализ штрихов рукописной подписи в целевой зоне."""
    if signature_bbox:
        x1, y1, x2, y2 = signature_bbox
        roi = image[y1:y2, x1:x2]
    else:
        h, w = image.shape[:2]
        roi = image[int(h * 0.7):, int(w * 0.4):]
        
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 120)
    density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
    return density > 0.015

```

#### 8.4. Логический валидатор правил (`backend/app/core/validator.py`)

```python
from typing import Dict, Any, List

def evaluate_document_rules(
    doc_type: str,
    fields: Dict[str, Any],
    rule: Dict[str, Any]
) -> Dict[str, Any]:
    """Строгая детерминированная проверка полей по правилу Положения вуза."""
    mandatory_fields: List[str] = rule.get("mandatory_fields", [])
    rule_id = rule.get("rule_id", "п. Положения")
    doc_name = rule.get("doc_display_name", "Документ")
    
    missing = []
    for field_key in mandatory_fields:
        val = fields.get(field_key, {}).get("value")
        if not val or val == "не найдено" or val == "нет":
            field_label = fields.get(field_key, {}).get("label", field_key)
            missing.append(field_label)
            
    if not missing:
        return {
            "status": "OK",
            "text": f"{doc_name} содержит все данные, которые требует {rule_id}. Окончательное решение примет сотрудник деканата.",
            "rule_source": rule_id
        }
    else:
        missing_str = ", ".join(missing)
        return {
            "status": "MISSING_FIELDS",
            "text": f"Не хватает: {missing_str}. Эти поля обязательны по {rule_id}.",
            "rule_source": rule_id
        }

```

---

### 9. ДЕТАЛЬНАЯ РЕАЛИЗАЦИЯ ФРОНТЕНДА (REACT + SHADCN/UI)

#### 9.1. Интерактивный просмотрщик документа (`DocumentViewer.tsx`)

```tsx
import React from "react";

interface FieldItem {
  key: string;
  label: string;
  value: string;
  bbox: [number, number, number, number] | null;
}

interface DocumentViewerProps {
  imageUrl: string;
  width: number;
  height: number;
  fields: FieldItem[];
  activeFieldKey: string | null;
  onHoverField: (key: string | null) => void;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  imageUrl,
  width,
  height,
  fields,
  activeFieldKey,
  onHoverField,
}) => {
  return (
    <div className="relative w-full overflow-hidden rounded-lg border bg-slate-900/5 shadow-inner">
      <img
        src={imageUrl}
        alt="Загруженный документ"
        className="w-full h-auto block select-none pointer-events-none"
      />
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox={`0 0 ${width} ${height}`}
      >
        {fields.map((field) => {
          if (!field.bbox || field.value === "не найдено") return null;
          const [x1, y1, x2, y2] = field.bbox;
          const isActive = activeFieldKey === field.key;

          return (
            <rect
              key={field.key}
              x={x1}
              y={y1}
              width={x2 - x1}
              height={y2 - y1}
              className={`transition-all duration-200 pointer-events-auto cursor-pointer ${
                isActive
                  ? "fill-primary/30 stroke-primary stroke-[3px]"
                  : "fill-blue-500/15 stroke-blue-500/60 stroke-[1.5px] hover:fill-blue-500/30"
              }`}
              onMouseEnter={() => onHoverField(field.key)}
              onMouseLeave={() => onHoverField(null)}
            />
          );
        })}
      </svg>
    </div>
  );
};

```

#### 9.2. Карточка распознанных полей (`FieldsCard.tsx`)

```tsx
import React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface FieldItem {
  key: string;
  label: string;
  value: string;
  bbox: [number, number, number, number] | null;
}

interface FieldsCardProps {
  documentName: string;
  fields: FieldItem[];
  activeFieldKey: string | null;
  onHoverField: (key: string | null) => void;
}

export const FieldsCard: React.FC<FieldsCardProps> = ({
  documentName,
  fields,
  activeFieldKey,
  onHoverField,
}) => {
  return (
    <Card className="shadow-sm">
      <CardHeader className="py-3 px-4 flex flex-row items-center justify-between border-b">
        <CardTitle className="text-base font-semibold">Карточка реквизитов</CardTitle>
        <Badge className="font-mono text-xs" variant="outline">{documentName}</Badge>
      </CardHeader>
      <CardContent className="p-0">
        <div className="divide-y divide-border text-sm">
          {fields.map((field) => {
            const isMissing = field.value === "не найдено";
            const isActive = activeFieldKey === field.key;

            return (
              <div
                key={field.key}
                onMouseEnter={() => onHoverField(field.key)}
                onMouseLeave={() => onHoverField(null)}
                className={`flex justify-between items-center py-2.5 px-4 transition-colors cursor-pointer ${
                  isActive ? "bg-muted font-medium" : "hover:bg-muted/40"
                }`}
              >
                <span className="text-muted-foreground">{field.label}</span>
                <span className="text-right">
                  {isMissing ? (
                    <Badge className="text-[11px] uppercase tracking-wider font-mono" variant="destructive">
                      не найдено
                    </Badge>
                  ) : (
                    <span className="font-medium text-foreground">{field.value}</span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

```

#### 9.3. Блок вердикта со ссылкой на Положение (`VerdictAlert.tsx`)

```tsx
import React from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CheckCircle2, AlertTriangle, HelpCircle } from "lucide-react";

interface VerdictAlertProps {
  status: "OK" | "MISSING_FIELDS" | "NO_INFO";
  text: string;
  ruleSource?: string;
}

export const VerdictAlert: React.FC<VerdictAlertProps> = ({ status, text, ruleSource }) => {
  const configs = {
    OK: {
      title: "Документ в порядке",
      icon: CheckCircle2,
      alertClass: "border-emerald-500/40 text-emerald-800 dark:text-emerald-300 bg-emerald-500/10",
    },
    MISSING_FIELDS: {
      title: "Не хватает обязательных данных",
      icon: AlertTriangle,
      alertClass: "border-amber-500/40 text-amber-800 dark:text-amber-300 bg-amber-500/10",
    },
    NO_INFO: {
      title: "Информация отсутствует",
      icon: HelpCircle,
      alertClass: "border-slate-500/40 text-slate-800 dark:text-slate-300 bg-slate-500/10",
    },
  };

  const current = configs[status];
  const Icon = current.icon;

  return (
    <Alert className={`${current.alertClass} shadow-sm`}>
      <Icon className="h-5 w-5"/>
      <div className="ml-2">
        <AlertTitle className="text-sm font-semibold">{current.title}</AlertTitle>
        <AlertDescription className="mt-1 text-xs leading-relaxed opacity-95">
          {text}
        </AlertDescription>
        {ruleSource && (
          <div className="mt-2 text-[11px] font-mono font-medium opacity-80">
            Основание: {ruleSource}
          </div>
        )}
      </div>
    </Alert>
  );
};

```

---

### 10. СКРИПТ АВТОМАТИЧЕСКОЙ ПАКЕТНОЙ ОЦЕНКИ (`batch_eval.py`)

Скрипт формирует выходной файл `results.json` для закрытой проверки жюри:

```python
import os
import json
import argparse
from pathlib import Path

# Импорт оркестратора пайплайна
# from app.core.pipeline import ProcessPipeline

def run_evaluation(input_source: str, output_path: str):
    """
    Пакетная оценка на закрытом датасете:
    Поддерживает чтение как metadata.jsonl (стандарт MTSAIR/MWS-Vision-Bench),
    так и директории с отдельными JSON-файлами.
    """
    results = []
    # pipeline = ProcessPipeline()
    path = Path(input_source)
    samples = []
    base_dir = path.parent if path.is_file() else path

    if path.is_file() and path.name.endswith(".jsonl"):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    samples.append(json.loads(line))
    elif path.is_dir():
        jsonl_file = path / "metadata.jsonl"
        if jsonl_file.exists():
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        samples.append(json.loads(line))
        else:
            for sample_file in path.glob("*.json"):
                with open(sample_file, "r", encoding="utf-8") as f:
                    samples.append(json.load(f))

    for meta in samples:
        file_name = meta["file_name"]
        question = meta["question"]
        doc_path = base_dir / file_name

        # result = pipeline.run(str(doc_path), question)
        # Mock структуры для схемы ответа:
        entry = {
            "file_name": file_name,
            "question": question,
            "document_type": meta.get("document_type", "study_certificate"),
            "extracted_fields": {
                "fio": "Иванов Иван Иванович",
                "university": "не найдено",
                "study_direction": "Информатика и ВТ",
                "study_form": "очная",
                "study_period": "2024-2026",
                "doc_number_and_date": "№12/3 от 10.09.2025",
                "stamp_and_signature": "есть"
            },
            "answer": "Не хватает названия вуза. Это поле обязательно по п. 3.4 Положения.",
            "rule_source": "п. 3.4 Положения"
        }
        results.append(entry)

    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(results, out, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="Путь к metadata.jsonl или папке с данными")
    parser.add_argument("--output", type=str, default="results.json")
    args = parser.parse_args()
    run_evaluation(args.input, args.output)

```

> **Важно:** Точная структура ключей для `results.json` должна быть окончательно верифицирована по официальному `README` к тестовому набору данных организаторов сразу после выдачи закрытого датасета (Слайды 5, 11).

---

### 11. ПОШАГОВЫЙ ПЛАН РЕАЛИЗАЦИИ НА 7 ДНЕЙ ХАКАТОНА

* День 1: Анализ данных и базовый OCR: Загрузка валидационного сплита `MTSAIR/MWS-Vision-Bench` (скрипт `download_dataset.py`, выборка `personal/hand_documents`, `business/scans`), парсинг Положения вуза в `regulations.json`, запуск PaddleOCR на CPU.


* День 2: Парсинг полей и CV-детекция: Реализация `Natasha` (ФИО), регулярных выражений дат/номеров, HSV-фильтрации печатей.


* День 3: RAG-ретривер и Rule Engine: Индексация пунктов регламента, реализация 3 категорий детерминированных ответов.


* День 4: Сквозной пайплайн и batch_eval.py: Интеграция этапов в один сервис, прогон тестов и генерация валидного `results.json`.


* День 5: Реализация бонусов: Выравнивание наклона до 30°, удаление бликов, автоопределение типа документа, конфиг `YAML`.


* День 6: Веб-интерфейс (React + Tailwind + shadcn/ui): Сборка UI, интеграция API, визуализация Bounding Boxes на скане.


* День 7: Финализация, видео-демо и презентация: Запись 3-минутного видеоролика, оформление презентации до 10 слайдов, составление финального README.



---

### 12. ЧЕКЛИСТ СДАЧИ ПРОЕКТА (DEFINITION OF DONE)

* [ ] Публичный Git-репозиторий с подробной инструкцией по запуску в `README.md`.


* [ ] Полная автономность: 0 обращений к внешним закрытым API.


* [ ] Поддержка 3 обязательных типов документов и явное заполнение `«не найдено»` для пропущенных полей.


* [ ] Безошибочное разделение ответов на 3 ветки («Документ в порядке», «Чего-то не хватает», «Ответа нет») со ссылками на пункты Положения.


* [ ] Реализация бонусов: Deskew до 30°, конфиг YAML, интерактивная подсветка BBox.


* [ ] Сформированный файл `results.json` по спецификации организаторов.


* [ ] Видеозапись демо-сценария длительностью до 3 минут.


* [ ] Презентация проекта объемом до 10 слайдов.

# src/core/answer_generator.py
import sys 
import os
import time
import json
import re
import psutil  # 🔹 НОВОЕ
import asyncio  # <--- Добавить этот импорт
from pathlib import Path
from typing import List, Dict, Optional
from api_manager import api_manager
from concurrent.futures import ThreadPoolExecutor, as_completed # <--- НОВОЕ
from config import get_law_display_name

class AnswerGenerator:
    """Генератор ответов на основе найденных статей с защитой от галлюцинаций"""
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.articles_dir = self.project_root / "search_results"
        self.articles_dir.mkdir(exist_ok=True)
# 🔹 НОВОЕ: советы для генератора
        self.hints: Dict[str, Dict] = {}
        self.hints_path = self.project_root / "generation_hints.json"
        self._load_hints()        

        # 🔹 НОВОЕ: объект процесса для замера ресурсов
        self._process = psutil.Process(os.getpid())

        self.generation_log = {
            "question": "",
            "articles_processed": 0,
            "articles_accepted": 0,
            "articles_rejected": 0,
            "rejection_reasons": [],
            "reasoning_steps": [],
            "generation_time": 0,
            "final_answer_quality": ""
        }
    
    def _load_hints(self) -> None:
        """Загружает советы генератора из JSON (если файл существует)."""
        try:
            if self.hints_path.exists():
                with open(self.hints_path, "r", encoding="utf-8") as f:
                    self.hints = json.load(f)
                print(f"💡 Генератор: загружены советы из {self.hints_path} для категорий: {list(self.hints.keys())}")
            else:
                print(f"ℹ️ Генератор: файл советов не найден ({self.hints_path}), работаю без советов")
        except Exception as e:
            print(f"⚠️ Генератор: ошибка загрузки советов: {e}")
            self.hints = {}

    async def generate_answer_from_articles_async(self, question: str, articles_file_path: Path, 
                                      category: str, search_log: Dict = None) -> Dict:
        """
        Асинхронная обертка для метода generate_answer_from_articles.
        Позволяет вызывать генератор из асинхронного кода (sequential_searcher) без блокировки событийного цикла.
        """
        loop = asyncio.get_running_loop()
        
        # Запускаем синхронный метод generate_answer_from_articles в дефолтном экзекьюторе (в отдельном потоке).
        # Это критически важно, так как внутри есть тяжелые операции ввода-вывода и API запросы.
        return await loop.run_in_executor(
            None, 
            self.generate_answer_from_articles, 
            question, 
            articles_file_path, 
            category, 
            search_log
        )
    
    def generate_answer_from_articles(self, question: str, articles_file_path: Path, 
                                      category: str, search_log: Dict = None) -> Dict:
        """Генерирует ответ на основе найденных статей с детальным логированием"""
        
        print(f"🧠 ЗАПУСК ГЕНЕРАЦИИ ОТВЕТА НА ОСНОВЕ СТАТЕЙ")
        print(f"   📁 Файл статей: {articles_file_path}")
        
        start_time = time.time()

        # 🔹 Стартовый замер ресурсов (CPU/память)
        try:
            proc = psutil.Process(os.getpid())
            cpu_start = proc.cpu_times()
            mem_start = proc.memory_info().rss  # байты
        except Exception:
            proc = None
            cpu_start = None
            mem_start = None

        self.generation_log = {
            "question": question,
            "category": category,
            "articles_file": str(articles_file_path),
            "articles_processed": 0,
            "articles_accepted": 0, 
            "articles_rejected": 0,
            "rejection_reasons": [],
            "reasoning_steps": [],
            "generation_time": 0,
            "final_answer_quality": ""
        }
        
        try:
            # 1. Чтение и парсинг статей из файла
            articles = self._read_and_parse_articles_file(articles_file_path)
            if not articles:
                return self._create_error_result("Не удалось прочитать или распарсить файл со статьями")
            
            print(f"   📖 Прочитано статей из файла: {len(articles)}")
            self.generation_log["articles_processed"] = len(articles)
            
            # 2. Анализ и фильтрация статей
            filtered_articles = self._analyze_and_filter_articles(question, articles)
            print(f"   ✅ Принято статей после фильтрации: {len(filtered_articles)}")
            print(f"   ❌ Отклонено статей: {len(articles) - len(filtered_articles)}")
            
            # 3. Генерация ответа на основе отфильтрованных статей
            if not filtered_articles:
                return self._create_no_articles_result(question)
            
            final_answer = self._generate_final_answer(question, filtered_articles, category)
            
            # 4. Завершение логирования времени
            self.generation_log["generation_time"] = time.time() - start_time
            self.generation_log["final_answer_quality"] = self._assess_answer_quality(final_answer, filtered_articles)

            # 🔹 Завершённый замер ресурсов
            resource_stats = {}
            try:
                if proc is not None and cpu_start is not None:
                    cpu_end = proc.cpu_times()
                    mem_end = proc.memory_info().rss  # байты

                    wall_time = self.generation_log["generation_time"]
                    cpu_time_start = cpu_start.user + cpu_start.system
                    cpu_time_end = cpu_end.user + cpu_end.system
                    cpu_time_delta = max(0.0, cpu_time_end - cpu_time_start)

                    if wall_time > 0:
                        avg_cpu_cores = cpu_time_delta / wall_time
                        cpu_count = psutil.cpu_count(logical=True) or 1
                        avg_cpu_percent = min(100.0, max(0.0, avg_cpu_cores * 100.0 / cpu_count))
                    else:
                        avg_cpu_cores = 0.0
                        avg_cpu_percent = 0.0

                    max_rss_mb = max(mem_start or 0, mem_end) / (1024 * 1024)

                    resource_stats = {
                        "wall_time_sec": round(wall_time, 2),
                        "cpu_time_sec": round(cpu_time_delta, 2),
                        "avg_cpu_cores": round(avg_cpu_cores, 2),
                        "avg_cpu_percent": round(avg_cpu_percent, 1),
                        "memory_mb": round(max_rss_mb, 1)
                    }

                    print(
                        f"   🧮 РЕСУРСЫ: время = {resource_stats['wall_time_sec']} c, "
                        f"CPU ≈ {resource_stats['avg_cpu_percent']:.1f}% "
                        f"({resource_stats['avg_cpu_cores']:.2f} ядер), "
                        f"RAM ≈ {resource_stats['memory_mb']:.1f} МБ"
                    )
                else:
                    print(f"   🧮 РЕСУРСЫ: замер CPU недоступен, время = {self.generation_log['generation_time']:.2f} c")
            except Exception as e:
                print(f"   ⚠️ Не удалось замерить ресурсы: {e}")

            self.generation_log["resource_stats"] = resource_stats
            
            print(f"   ✅ Генерация завершена за {self.generation_log['generation_time']:.2f}с")
            print(f"   📊 Качество ответа: {self.generation_log['final_answer_quality']}")
            
            return {
                "status": "success",
                "answer": final_answer,
                "articles_used": len(filtered_articles),
                "generation_log": self.generation_log,
                "reasoning": "Ответ сгенерирован на основе найденных статей законов"
            }
        
        except Exception as e:
            error_msg = f"Ошибка генерации ответа: {str(e)}"
            print(f"   ❌ {error_msg}")
            return self._create_error_result(error_msg)    
    
    def _read_and_parse_articles_file(self, articles_file_path: Path) -> List[Dict]:
        """Читает статьи из JSON файла (НОВАЯ ЛОГИКА)"""
        if not articles_file_path.exists():
            self._log_reasoning(f"Файл со статьями не найден: {articles_file_path}", "error")
            return []

        try:
            with open(articles_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Проверяем формат JSON
            if isinstance(data, dict) and "articles" in data:
                articles = data["articles"]
            elif isinstance(data, list):
                articles = data
            else:
                self._log_reasoning("Неизвестный формат JSON (ожидался dict с ключом 'articles' или list)", "error")
                return []

            self._log_reasoning(f"Успешно загружено {len(articles)} статей из JSON", "info")
            return articles

        except json.JSONDecodeError as e:
            self._log_reasoning(f"Ошибка декодирования JSON: {e}", "error")
            # Можно попробовать прочитать как старый текст (fallback), если очень надо,
            # но лучше просто вернуть ошибку, чтобы не путать форматы.
            return []
        except Exception as e:
            self._log_reasoning(f"Ошибка чтения файла статей: {str(e)}", "error")
            return []
    
        
    def _analyze_and_filter_articles(self, question: str, articles: List[Dict]) -> List[Dict]:
            """
            Анализирует релевантность статей параллельно с помощью ThreadPoolExecutor.
            Оставляет все статьи, которые преодолели минимальный порог полезности.
            """
            filtered_articles = []
            total_articles = len(articles)
            print(f"   🔍 Глубокий ИИ-анализ релевантности {total_articles} статей (ПАРАЛЛЕЛЬНО)...")
            
            THRESHOLD = 0.4
            MAX_WORKERS = 8  # Оптимально для API (чтобы не получить 429 Too Many Requests)

            # Внутренняя функция-обертка для выполнения в потоке
            # Она НЕ меняет состояние класса (self.logs), а только возвращает данные
            def process_single_article(idx, art):
                # Унификация заголовка
                title = art.get('article') or art.get('title') or 'Без названия'
                art_id = f"{idx+1}. {title}"
                
                # Проверка на пустой контент
                if not art.get('content'):
                    return idx, art, 0.0, "Пустой контент статьи", art_id
                
                # Вызов тяжелой функции (DeepSeek API)
                try:
                    score = self._deep_relevance_analysis(question, art)
                    return idx, art, score, None, art_id
                except Exception as e:
                    # Возвращаем ошибку, но не роняем поток
                    return idx, art, 0.0, str(e), art_id

            # Запуск параллельных задач
            futures = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for i, article in enumerate(articles):
                    futures.append(executor.submit(process_single_article, i, article))
                
                # Сбор результатов по мере завершения
                # Используем список для сбора результатов, чтобы потом обработать логи
                results = []
                for future in as_completed(futures):
                    results.append(future.result())

            # Сортируем результаты по индексу, чтобы логи шли по порядку (1, 2, 3...), 
            # а не вразнобой, как завершались потоки. Это важно для читаемости отчета.
            results.sort(key=lambda x: x[0])

            # Последовательная обработка результатов и запись в логи (БЕЗОПАСНАЯ ЗОНА)
            for idx, article, relevance_score, error, article_id in results:
                if error:
                    self._log_article_rejection(article_id, f"Ошибка анализа: {error}")
                    continue

                if relevance_score >= THRESHOLD:
                    # Явно сохраняем title для промпта
                    title = article.get('article') or article.get('title') or 'Без названия'
                    filtered_articles.append({
                        **article,
                        'title': title, 
                        'relevance_score': relevance_score,
                        'analysis_notes': f"Релевантность: {relevance_score:.2f}"
                    })
                    self._log_reasoning(f"✅ Статья {article_id} принята (оценка: {relevance_score:.2f})", "accept")
                else:
                    self._log_article_rejection(article_id, f"Низкая релевантность: {relevance_score:.2f} (Порог: {THRESHOLD})")

            # Сортируем финальный список: сначала самые релевантные
            filtered_articles.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            print(f"   📊 Итого передаем на генерацию: {len(filtered_articles)} статей")
            return filtered_articles        
    
    def _build_relevance_prompt(self, question: str, article: Dict) -> tuple[str, str]:
        # [SYSTEM PROMPT]: Role & Mental Model
        system_prompt = """
        You are an expert Legal Analyst specializing in Russian law.
        Your task is to evaluate the relevance of a legal text fragment for answering a specific user question.
        
        CORE PRINCIPLES:
        1. High Recall for Foundations: Do NOT discard definitions, general rules, or rights/duties just because they are broad.
        2. Strict Context Matching: Discard procedural details if they clearly apply to a different subject.
        3. Critical Thinking: Analyze the text deeply before assigning a score.
        """
        
        article_text = article.get('content', '')[:6000] 
        
        # [USER PROMPT]: Structured Input -> Analytical Steps -> Output
        user_prompt = f"""
        [INPUT DATA]
        USER QUESTION: "{question}"
        
        LEGAL TEXT (Article):
        Title: {article.get('title', 'Untitled')}
        Content: "{article_text}"

        [EVALUATION CRITERIA]
        Use this scale to determine the score:

        - **IRRELEVANT (0.0 - 0.2):** Different legal domain, wrong subject (Entity vs Individual), or bureaucratic noise.
        - **WEAK RELEVANCE (0.3 - 0.4):** Vague connection, keywords present but context is wrong.
        - **CONTEXTUAL (0.5 - 0.7):** Definitions, general principles, or norms necessary to understand the process. (SAFETY NET: If unsure, use this range).
        - **HIGHLY RELEVANT (0.8 - 1.0):** Direct answers, specific procedures, deadlines, or critical rights/prohibitions.

        [THOUGHT PROCESS]
        Before scoring, follow these steps:
        1. **Subject Check:** Does the text apply to the user's status (e.g., Physical Person vs Legal Entity)?
        2. **Topic Check:** Does the text address the core issue or related concepts from the question?
        3. **Utility Check:** Will this text help construct a complete answer (even as background info)?

        [OUTPUT INSTRUCTIONS]
        1. Write a concise REASONING (1-2 sentences) in English or Russian, following the steps above.
        2. On the last line, write the final score.
        
        Required Format:
        Reasoning: <Your analysis here>
        SCORE: <Number between 0.0 and 1.0>
        """
        return system_prompt, user_prompt
    
    def _deep_relevance_analysis(self, question: str, article: Dict) -> float:
        system_prompt, user_prompt = self._build_relevance_prompt(question, article)
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = api_manager.deepseek_generation(
                messages=messages,
                temperature=0.0, # Low temperature for stable classification
                timeout=30
            )

            # 1. Robust Parsing: Look for "SCORE: X.X"
            # Supports both English "SCORE" and Russian "ОЦЕНКА" just in case.
            match = re.search(r'(SCORE|ОЦЕНКА):\s*(\d+(\.\d+)?)', response, re.IGNORECASE)
            
            if match:
                score = float(match.group(2)) # Group 2 is the number
                return max(0.0, min(1.0, score))
            
            # 2. Fallback Parsing: Look for the last number in the text
            # DeepSeek often ends with the score even if it forgets the label.
            # We look for numbers like 0.5, 0.9, 1.0, 0, 1
            numbers = re.findall(r'\b(0\.\d+|1\.0|0|1)\b', response)
            if numbers:
                return float(numbers[-1])

            # 3. Safety Net: If parsing fails completely
            print(f"   ⚠️ Could not parse score from: '{response[:50]}...'")
            return 0.5 # Default to "Useful" to avoid false negatives

        except Exception as e:
            print(f"   ⚠️ API Error in relevance analysis: {e}")
            return 0.5
    
    def _parse_relevance_score(self, response: str) -> float:
        """Парсит оценку релевантности из ответа ИИ"""
        try:
            # Ищем число с плавающей точкой
            score_match = re.search(r'(\d+\.\d+|\d+)', response.strip())
            if score_match:
                score = float(score_match.group(1))
                return max(0.0, min(1.0, score))  # Ограничиваем диапазон
        except:
            pass
        
        return 0.5  # Значение по умолчанию при ошибке
    
    def _generate_final_answer(self, question: str, articles: List[Dict], category: str) -> str:
        """Генерирует финальный ответ на основе отобранных статей"""

        system_prompt, user_prompt = self._build_answer_prompt(question, articles, category)

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]            # 🔥 ИСПОЛЬЗУЕМ API ДЛЯ ГЕНЕРАЦИИ
            response = api_manager.deepseek_generation(
                messages=messages,
                temperature=0.3,
                timeout=120
            )
            
            self._log_reasoning("Финальный ответ успешно сгенерирован", "success")
            return response
            
        except Exception as e:
            error_msg = f"Ошибка генерации ответа: {str(e)}"
            self._log_reasoning(error_msg, "error")
            return f"Не удалось сгенерировать ответ на основе найденных статей. Ошибка: {str(e)}"    
    
    def _build_answer_prompt(self, question: str, articles: List[Dict], category: str) -> tuple[str, str]:
        # === SYSTEM PROMPT ===
        # Задает жесткую изоляцию и запрет на внешние знания
        system_prompt = """
    YOU ARE A ROBOT LAWYER WORKING IN STRICT ISOLATION MODE.
    ONLY TEXTS FROM THE "KNOWLEDGE BASE" SECTION BELOW ARE AVAILABLE TO YOU.
    THE OUTSIDE WORLD AND OTHER LAWS DO NOT EXIST FOR YOU.
    """

        # === USER PROMPT ===
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"\n{'='*40}\n"
            articles_text += f"DOC #{i}\n"
        
            # Получаем имя файла из разных возможных полей
            article_filename = article.get('source_file', '') or article.get('filename', '')
        
            # Преобразуем имя файла в человекочитаемое название
            if article_filename:
                display_name = get_law_display_name(article_filename)
            else:
                display_name = article.get('title', 'Untitled')
        
            articles_text += f"TITLE: {display_name}\n"
            articles_text += f"CONTENT:\n{article.get('content', '')}\n"
            articles_text += f"{'='*40}\n"

        # === НОВОЕ: мягкий совет по категории (если есть) ===
        hint_block = ""
        if category and category in self.hints:
            raw_hint = (self.hints.get(category) or {}).get("hint_text", "").strip()
            if raw_hint:
                # Совет описывает ТИПИЧНУЮ СИТУАЦИЮ и стратегию анализа.
                # Модель сама решает, подходит ли этот сценарий к текущему вопросу и содержимому KNOWLEDGE BASE.
                hint_block = f"""
    [АНАЛИТИЧЕСКИЙ СОВЕТ ДЛЯ ДАННОЙ ТЕМЫ]

    Ниже приведён совет по тому, как обычно анализируется эта категория дел.
    Этот совет НЕ является жёсткой инструкцией, а лишь подсказывает, на что стоит обратить особое внимание.

    СОВЕТ (по-русски, с юридическими терминами):

    {raw_hint}

    ОГРАНИЧЕНИЯ:
    - Используй этот совет ТОЛЬКО если ситуация пользователя и тексты в KNOWLEDGE BASE действительно соответствуют описанному контексту.
    - Если упомянутые в совете статьи или процедуры отсутствуют в KNOWLEDGE BASE, прямо укажи в ответе, что по этим аспектам в текстах нет информации, и НЕ выдумывай нормы.
    - Если совет не подходит к конкретному вопросу, игнорируй его и следуй общим инструкциям ниже.
    """

        user_prompt = f"""
            KNOWLEDGE BASE:
            {articles_text}

            USER QUESTION:
            "{question}"

            {hint_block}
        
            [INSTRUCTIONS FOR ANSWER GENERATION]
        
            1. **ANALYSIS PHASE (Evidence-Based Reasoning):**
               - **Step A (Quote Extraction):** For every procedure or rule found, EXTRACT short verbatim quotes from the text covering:
                 * Prerequisites & Conditions.
                 * Deadlines, Amounts, or Events.
                 * Required Documents or Actions.
               - **Step B (Fact Matching):** Compare these extracted quotes against the specific facts provided in the User Question.
               - **Step C (Gap Analysis):** If a crucial detail mentioned in the text (e.g., a specific prerequisite identified in Step A) is NOT present in the text for the user's specific case or is missing entirely, tag it as [MISSING]. Do NOT guess it.

            2. **DRAFTING THE RESPONSE (in Russian):**
               - **Direct Answer:** Based ONLY on the extracted quotes and analysis.
               - **Scenario Analysis:** If the texts describe multiple different legal paths or options, explain the conditions for EACH path using the quotes found.
               - **Actionable Steps:** List concrete steps verified by the text.
               - **Uncertainty:** If information is missing, explicitly write: "В текстах нет информации о..."

            3. **FORMATTING & STYLE:**
               - Use professional, accessible Russian language.
               - Avoid dry legal citation numbers in the narrative flow (e.g., "According to Art. X..."). Instead, use natural phrasing like "The law states...", "It is established that...", or "According to the rules...".
               - Use Markdown (bolding, lists) for readability.

            4. **ANTI-HALLUCINATION VERIFICATION:**
               - **The "Finger Rule":** Can you point your finger at the specific sentence in the KNOWLEDGE BASE that supports your claim?
               - **If NO:** DELETE the claim immediately.
               - **If YES:** Proceed.

            [GOAL]
            Provide a complete, legally grounded consultation based SOLELY on the KNOWLEDGE BASE.
        
            BEGIN RESPONSE IN RUSSIAN:
            Здравствуйте! На основе проанализированных документов, я могу пояснить следующее:
            """
        return system_prompt, user_prompt
    
    def _log_reasoning(self, message: str, level: str = "info"):
        """Логирует шаги рассуждения"""
        timestamp = time.time()
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message
        }
        self.generation_log["reasoning_steps"].append(log_entry)
        print(f"      [{level.upper()}] {message}")
    
    def _log_article_rejection(self, article_id: str, reason: str):
        """Логирует отклонение статьи"""
        self.generation_log["articles_rejected"] += 1
        rejection_entry = {
            "article": article_id,
            "reason": reason,
            "timestamp": time.time()
        }
        self.generation_log["rejection_reasons"].append(rejection_entry)
        print(f"      ❌ Отклонена: {article_id} - {reason}")
    
    def _assess_answer_quality(self, answer: str, articles_used: List[Dict]) -> str:
        """Оценивает качество сгенерированного ответа"""
        if not answer or len(answer) < 100:
            return "low"
        
        # Простые эвристики для оценки качества
        quality_indicators = 0
        
        if any(keyword in answer.lower() for keyword in ['рекомендац', 'совет', 'следует', 'необходимо']):
            quality_indicators += 1
            
        if any(keyword in answer.lower() for keyword in ['статья', 'норма', 'правов']):
            quality_indicators += 1
            
        if len(answer) > 300:  # Достаточно подробный ответ
            quality_indicators += 1
            
        if 'недостаточно' not in answer.lower() and 'информац' not in answer.lower():
            quality_indicators += 1
        
        if quality_indicators >= 3:
            return "high"
        elif quality_indicators >= 2:
            return "medium"
        else:
            return "low"
    
    def _create_error_result(self, error_msg: str) -> Dict:
        """Создает результат с ошибкой"""
        return {
            "status": "error",
            "answer": f"Не удалось сгенерировать ответ. Ошибка: {error_msg}",
            "articles_used": 0,
            "generation_log": self.generation_log,
            "reasoning": f"Ошибка в процессе генерации: {error_msg}"
        }
    
    def _create_no_articles_result(self, question: str) -> Dict:
        """Создает результат когда нет подходящих статей"""
        return {
            "status": "no_articles",
            "answer": f"На основе найденных статей не удалось сформировать полный ответ на вопрос: '{question}'. Рекомендуется обратиться к юристу для получения консультации с учетом конкретных обстоятельств вашего дела.",
            "articles_used": 0,
            "generation_log": self.generation_log,
            "reasoning": "Не найдено достаточно релевантных статей для формирования ответа"
        }
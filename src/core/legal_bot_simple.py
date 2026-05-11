# src/core/legal_bot_simple.py
"""
Ядро бота: Классификатор → Навигатор с рекомендациями → DeepSeek
"""

# src/core/legal_bot_simple.py
"""
Обновлённое ядро: RAG как навигатор, DeepSeek как аналитик
"""

from typing import Dict  # ✅ Добавить эту строку
from src.classification.deepseek_classifier import DeepSeekClassifier
from src.core.law_navigator import LawNavigator
import requests
import sys
from pathlib import Path
from config import Config  # ✅ Добавьте эту строку!
from api_manager import api_manager

# Добавляем корень для импорта config
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class LegalBotCore:
    """Ядро бота с рекомендательной системой"""
    
    def __init__(self):
        self.classifier = None
        self.navigator = None
        self.config = Config()
        self.is_initialized = False
    
    def initialize(self):
        """Инициализирует компоненты"""
        if self.is_initialized:
            return
        
        print("🔄 Инициализация ИИ-юриста (архитектура с рекомендациями)...")
        print("   • Классификатор: ключевые слова + DeepSeek")
        print("   • Навигатор: поиск релевантных глав")
        print("   • DeepSeek: анализ с мягкими рекомендациями\n")
        
        self.classifier = DeepSeekClassifier()
        self.navigator = LawNavigator()
        
        self.is_initialized = True
        print("✅ Система готова к работе\n")
    
    def process_question(self, question: str) -> dict:
        """
        Обрабатывает вопрос:
        1. Классификатор → категория
        2. Навигатор → релевантные главы + полный контекст
        3. DeepSeek → анализ с рекомендациями (но может искать сам)
        """
        if not self.is_initialized:
            self.initialize()
        
        print(f"🧠 Обрабатываю вопрос: '{question[:60]}...'")
        
        # Шаг 1: Классификация
        category = self.classifier.classify(question)
        category_name = self._get_category_name(category)
        
        # Шаг 2: Навигация с рекомендациями
        print(f"   📚 Собираю законы и рекомендую главы...")
        navigation = self.navigator.get_context_for_ai(category, question)
        
        print(f"      ✅ Законов: {len(navigation['laws_included'])}")
        print(f"      ✅ Рекомендуемых глав: {len(navigation['recommended_chapters'])}")
        print(f"      ✅ Размер контекста: {navigation['context_length']} символов")
        
        # Шаг 3: DeepSeek анализирует
        print(f"   🤖 DeepSeek анализирует...")
        answer = self._analyze_with_deepseek(question, navigation)
        print(f"      ✅ Ответ готов\n")
        
        return {
            'question': question,
            'category': category,
            'category_name': category_name,
            'laws_used': navigation['laws_included'],
            'recommended_chapters': navigation['recommended_chapters'],
            'total_chapters_found': navigation['total_chapters_found'],
            'answer': answer
        }
    
    def _analyze_with_deepseek(self, question: str, navigation: Dict) -> str:
        """Отправляет вопрос с рекомендациями в DeepSeek"""
        
        # Формируем описание рекомендованных глав
        if navigation['recommended_chapters']:
            recommended_text = "РЕКОМЕНДОВАННЫЕ ГЛАВЫ (проверь их в первую очередь):\n"
            for ch in navigation['recommended_chapters']:
                recommended_text += f"  • {ch['law']} → {ch['title']}\n"
            recommended_text += "\n"
        else:
            recommended_text = ""
        
        prompt = f"""Ты — эксперт по российскому праву.

ВОПРОС ПОЛЬЗОВАТЕЛЯ:
"{question}"

{recommended_text}СОВЕТ ПО АНАЛИЗУ:
{navigation['ai_hint']}

ДОСТУПНЫЕ ЗАКОНЫ:
{navigation['context']}

ИНСТРУКЦИЯ:
1. В ПЕРВУЮ ОЧЕРЕДЬ изучи рекомендованные главы (если есть)
2. Если в них нет ответа — ищи в остальном контексте
3. В КРАЙНЕМ случае можешь использовать другие разделы законов
4. ОБЯЗАТЕЛЬНО укажи статьи и цитаты из закона
5. Если ответа нет — честно скажи об этом

ФОРМАТ ОТВЕТА:
**Ответ:**
[Твой ответ]

**Правовое основание:**
- Статья [номер] [закон]: [цитата]
- ...

**Источник:**
[Откуда взял: рекомендованная глава / другой раздел]

Используй ТОЛЬКО информацию из предоставленных законов."""

        try:
            active_config = self.config.ACTIVE_CONFIG
            endpoint = f"{active_config['base_url']}/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {active_config['api_key']}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": active_config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 2000
            }
            
            response = requests.post(endpoint, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            return f"❌ Ошибка при обращении к DeepSeek: {e}"
    
    def _get_category_name(self, category_id: str) -> str:
        """Получает название категории"""
        category_data = self.config.LEGAL_CATEGORIES.get(category_id)
        return category_data["name"] if category_data else "Неизвестная категория"

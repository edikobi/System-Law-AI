# src/classification/deepseek_classifier.py
"""
Классификатор через api_manager
"""

import sys
from pathlib import Path

# Добавляем корень для импорта
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api_manager import api_manager
from config import Config

class DeepSeekClassifier:
    """Классификатор через централизованный API менеджер"""
    
    def __init__(self):
        self.config = Config()
        print(f"🔧 Классификатор готов")
    
    def classify(self, question: str) -> str:
        """Классифицирует вопрос"""
        # Сначала ключевые слова
        keyword_category = self._classify_with_keywords(question)
        if keyword_category != "unknown":
            print(f"   ✅ Категория (ключевые слова): {keyword_category}")
            return keyword_category
        
        # Затем DeepSeek
        print(f"   🤖 Использую DeepSeek API...")
        return self._classify_with_deepseek(question)
    
    def _classify_with_keywords(self, question: str) -> str:
        """Классификация по ключевым словам"""
        question_lower = question.lower()
        
        for category_id, category_data in self.config.LEGAL_CATEGORIES.items():
            if category_id == "unknown":
                continue
            
            keywords = category_data.get("keywords", [])
            if any(keyword in question_lower for keyword in keywords):
                return category_id
        
        return "unknown"
    
    def _classify_with_deepseek(self, question: str) -> str:
        """Классификация через API менеджер"""
        try:
            # Формируем промпт
            categories_list = []
            for cat_id, cat_data in self.config.LEGAL_CATEGORIES.items():
                if cat_id != "unknown":
                    categories_list.append(f"- {cat_id}: {cat_data['name']}")
            
            categories_text = "\n".join(categories_list)
            
            prompt = f"""Определи правовую категорию вопроса.

ВОПРОС:
"{question}"

ДОСТУПНЫЕ КАТЕГОРИИ:
{categories_text}

Ответь ТОЛЬКО идентификатором категории (например: family_general, consumer и т.д.)
Если не уверен — ответь: unknown

ТВОЙ ОТВЕТ:"""

            # Вызываем через api_manager
            messages = [{"role": "user", "content": prompt}]
            response = api_manager.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=20
            )
            
            category = response.strip().lower()
            
            # Валидация
            valid_categories = list(self.config.LEGAL_CATEGORIES.keys())
            if category in valid_categories:
                print(f"   ✅ Категория (DeepSeek): {category}")
                return category
            else:
                return "unknown"
                
        except Exception as e:
            print(f"   ❌ Ошибка DeepSeek: {e}")
            return "unknown"

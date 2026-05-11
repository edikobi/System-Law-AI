# src/classification/gigachat_classifier.py
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api_manager import api_manager
from config import Config

class GigaChatClassifier:
    """Классификатор через GigaChat API с RAG-ассистентом"""
    
    def __init__(self):
        self.config = Config()
        print("🔧 GigaChat классификатор с DeepSeek fallback готов")
    
    def classify_with_rag_assistance(self, question: str) -> str:
        """Классификация с помощью ИИ (GigaChat с DeepSeek fallback)"""
        rag_suggestion = self._get_rag_category_suggestion(question)
        return self._classify_with_gigachat(question, rag_suggestion)
    
    def _classify_with_keywords(self, question: str) -> str:
        """Быстрая классификация по ключевым словам"""
        question_lower = question.lower()
        
        for category_id, category_data in self.config.LEGAL_CATEGORIES.items():
            if category_id == "unknown":
                continue
            
            keywords = category_data.get("keywords", [])
            if any(keyword in question_lower for keyword in keywords):
                return category_id
        
        return "unknown"
    
    def _get_rag_category_suggestion(self, question: str) -> dict:
        """RAG система предлагает возможные категории"""
        # Здесь можно использовать вашу существующую RAG логику
        # или простой поиск по ключевым словам в законах
        
        suggestions = []
        question_lower = question.lower()
        
        for category_id, category_data in self.config.LEGAL_CATEGORIES.items():
            if category_id == "unknown":
                continue
            extended_laws = self.config.get_extended_laws_for_category(category_id)
            # Проверяем совпадение с ключевыми словами категории
            keywords = category_data.get("keywords", [])
            matches = sum(1 for keyword in keywords if keyword in question_lower)
            
            if matches > 0:
                suggestions.append({
                    "category": category_id,
                    "confidence": matches,
                    "reasoning": f"Найдено {matches} ключевых слов"
                })
        
        return {
            "suggestions": sorted(suggestions, key=lambda x: x["confidence"], reverse=True)[:3],
            "primary_suggestion": suggestions[0] if suggestions else None
        }
    
    def _classify_with_gigachat(self, question: str, rag_suggestion: dict) -> str:
        """Финальная классификация через GigaChat с учетом RAG рекомендаций"""
    
        categories_list = []
        for cat_id, cat_data in self.config.LEGAL_CATEGORIES.items():
            if cat_id != "unknown":
                categories_list.append(f"- {cat_id}: {cat_data['name']} (ключевые слова: {', '.join(cat_data.get('keywords', []))})")
    
        categories_text = "\n".join(categories_list)
    
        # Форматируем RAG рекомендации
        rag_text = "RAG не предложил категорий"
        if rag_suggestion["suggestions"]:
            rag_items = []
            for sug in rag_suggestion["suggestions"]:
                rag_items.append(f"- {sug['category']} (уверенность: {sug['confidence']}) - {sug['reasoning']}")
            rag_text = "\n".join(rag_items)
    
        prompt = f'''# ЗАДАЧА: ОПРЕДЕЛИТЬ ПРАВОВУЮ КАТЕГОРИЮ ВОПРОСА

    ## ВОПРОС ПОЛЬЗОВАТЕЛЯ:
    "{question}"

    ## РЕКОМЕНДАЦИИ RAG СИСТЕМЫ:
    {rag_text}

    ## ДОСТУПНЫЕ КАТЕГОРИИ:
    {categories_text}

    ## ИНСТРУКЦИИ:
    1. Внимательно проанализируй вопрос и рекомендации RAG
    2. Если RAG предложил хорошие варианты - выбери наиболее подходящий
    3. Если RAG ошибся - определи категорию самостоятельно
    4. Учитывай контекст и скрытые правовые аспекты

    ## ФОРМАТ ОТВЕТА:
    Верни ТОЛЬКО идентификатор категории (например: family_general, consumer, etc.)
    Если не уверен - верни: unknown

    КАТЕГОРИЯ:'''

        try:
            messages = [{"role": "user", "content": prompt}]
            response = api_manager.gigachat_completion(
                messages=messages,
                temperature=0.1
            )
        
            category = response.strip().lower()
        
            # Валидация ответа
            valid_categories = list(self.config.LEGAL_CATEGORIES.keys())
            if category in valid_categories:
                print(f"   ✅ Категория (GigaChat): {category}")
                return category
            else:
                print(f"   ⚠️  GigaChat вернул невалидную категорию: {category}")
                return "unknown"
            
        except Exception as e:
            print(f"   ❌ Ошибка GigaChat: {e}")
            # Попытка 2: DeepSeek fallback
            print("   ⚠️ GigaChat недоступен, переключаюсь на DeepSeek...")
            try:
                response = api_manager.deepseek_completion(
                    messages=messages,
                    temperature=0.1
                )
                category = response.strip().lower()
            
                # Валидация ответа DeepSeek
                valid_categories = list(self.config.LEGAL_CATEGORIES.keys())
                if category in valid_categories:
                    print(f"   ✅ Категория (DeepSeek): {category}")
                    return category
                else:
                    print(f"   ⚠️ DeepSeek вернул невалидную категорию: {category}")
            except Exception as e2:
                print(f"   ❌ Ошибка DeepSeek: {e2}")
        
            # Fallback на RAG если оба провайдера недоступны
            print("   ❌ Все ИИ провайдеры недоступны, используем RAG рекомендацию")
            if rag_suggestion["primary_suggestion"]:
                return rag_suggestion["primary_suggestion"]["category"]
            return "unknown"

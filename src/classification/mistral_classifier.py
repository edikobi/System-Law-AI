# src/classification/mistral_classifier.py
import requests
import json
from config import Config

class MistralClassifier:
    def __init__(self):
        self.config = Config()
        self.headers = {
            "Authorization": f"Bearer {self.config.HUGGINGFACE_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def classify(self, question: str) -> str:
        """Классифицирует вопрос с помощью Mistral"""
        prompt = self._create_classification_prompt(question)
        
        try:
            response = self._query_mistral_api(prompt)
            category = self._extract_category(response)
            
            # Валидация категории
            if category not in self.config.LEGAL_CATEGORIES:
                category = self._classify_with_keywords(question)
                
            return category
            
        except Exception as e:
            print(f"❌ Ошибка API классификатора: {e}")
            return self._classify_with_keywords(question)
    
    def _create_classification_prompt(self, question: str) -> str:
        """Создает промпт для классификации"""
        categories_text = "\n".join([
            f"- {cat_id}: {cat_data['name']}" 
            for cat_id, cat_data in self.config.LEGAL_CATEGORIES.items()
        ])
        
        return f"""
        Ты - российский юрист. Классифицируй вопрос пользователя по одной из следующих категорий:
        
        {categories_text}
        
        Вопрос: "{question}"
        
        Ответь ТОЛЬКО идентификатором категории (например: "consumer", "family_property" и т.д.). 
        Не добавляй никаких других слов или объяснений.
        """
    
    def _query_mistral_api(self, prompt: str) -> str:
        """Отправляет запрос к Mistral API"""
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 50,
                "temperature": 0.1,
                "return_full_text": False
            }
        }
        
        response = requests.post(
            self.config.API_URL, 
            headers=self.headers, 
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        return result[0]['generated_text'].strip()
    
    def _extract_category(self, response: str) -> str:
        """Извлекает категорию из ответа модели"""
        # Очищаем ответ от лишних символов
        cleaned = response.strip().strip('"').strip("'").lower()
        
        # Ищем идентификатор категории в ответе
        for category in self.config.LEGAL_CATEGORIES.keys():
            if category in cleaned:
                return category
        
        return "unknown"
    
    def _classify_with_keywords(self, question: str) -> str:
        """Fallback классификация по ключевым словам"""
        question_lower = question.lower()
        
        for category_id, category_data in self.config.LEGAL_CATEGORIES.items():
            keywords = category_data.get("keywords", [])
            if any(keyword in question_lower for keyword in keywords):
                return category_id
        
        return "unknown"
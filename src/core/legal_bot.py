# src/core/legal_bot.py
from src.rag.smart_rag_simple import SmartRAGSystem
from src.classification.deepseek_classifier import DeepSeekClassifier  # ← Изменено!

class LegalBotCore:
    def __init__(self):
        self.rag_system = None
        self.classifier = None
        self.is_initialized = False
        
    def initialize(self):
        """Инициализирует компоненты системы"""
        if self.is_initialized:
            return
            
        print("🔄 Инициализация ИИ-юриста...")
        
        self.rag_system = SmartRAGSystem()
        self.classifier = DeepSeekClassifier()  # ← Изменено!
        
        self.is_initialized = True
        print("✅ Система готова к работе")
    
    def process_question(self, question: str) -> dict:
        """Обрабатывает вопрос через полный цикл"""
        if not self.is_initialized:
            self.initialize()
        
        print(f"🧠 Анализирую вопрос: '{question}'")
        
        # 1. Классификация
        category = self.classifier.classify(question)
        category_name = self._get_category_name(category)
        print(f"📂 Категория: {category_name}")
        
        # 2. Умный поиск
        articles = self.rag_system.search_with_priority(question, category)
        print(f"🔍 Найдено статей: {len(articles)}")
        
        # 3. Формируем ответ
        return {
            "question": question,
            "category": category,
            "category_name": category_name,
            "relevant_articles": articles,
            "laws_used": list(set(article["law"] for article in articles))
        }
    
    def _get_category_name(self, category_id: str) -> str:
        """Получает человеко-читаемое название категории"""
        from config import Config
        config = Config()
        category_data = config.LEGAL_CATEGORIES.get(category_id)
        return category_data["name"] if category_data else "Неизвестная категория"
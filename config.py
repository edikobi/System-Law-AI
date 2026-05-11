# config.py

import os
from dotenv import load_dotenv
from typing import List
from typing import Dict

load_dotenv()

class Config:
        
    # Пути к данным
    LAWS_DIR = "laws"
    CHROMA_DIR = "chroma_db"

LEGAL_CATEGORIES = {
    "civil": {
        "name": "Гражданское право",
        "laws": ["gk_rf_1.docx", "gk_rf_2.docx", "gk_rf_3.docx", "gk_rf_4.docx"],
        "document_priority": ["codes", "plenums", "sublegal"],
        "keywords": [
            "сделка", "обязательство", "купля-продажа",
            "недействительность", "договорные отношения", "исполнение",
            "собственность", "имущество", "владение", "наследство"
        ],
        "ai_hint": "Проверь разделы о сделках, обязательствах, праве собственности и наследовании"
    },
    
    "family": {
        "name": "Семейное право",
        "laws": ["semeiniy_kodeks.docx", "gk_rf_1.docx", "gk_rf_2.docx"],
        "document_priority": ["codes", "plenums", "sublegal"],
        "keywords": [
            "развод", "расторжение брака", "супруг", "брак", "загс",
            "опека", "усыновление", "родительские права", "алименты",
            "брачный договор", "раздел имущества", "совместная собственность"
        ],
        "ai_hint": "Рекомендуется искать в главах о браке, разводе, алиментах и разделе имущества"
    },
    
    "housing": {
        "name": "Жилищное право",
        "laws": ["zhilishniy_kodeks.docx", "gk_rf_1.docx", "gk_rf_2.docx", "Postanov o mrk 491.docx", "Postanov Mos o MKD.docx", "Postanov o mkd 354.docx", "zpp.docx", "Post Gosstoya.docx", "Post pravit N 290.docx"],
        "document_priority": ["codes", "plenums", "sublegal"],
        "keywords": [
            "жилищные правоотношения",
            "управляющая компания", "капитальный ремонт", "выселение",
            "коммунальные платежи", "жкх", "многоквартирный дом"
        ],
        "ai_hint": "Проверь разделы о правах на жилое помещение, управлении МКД и коммунальных услугах"
    },
    
    "labor": {
        "name": "Трудовое право",
        "laws": ["trudovoy_kodeks.docx"],
        "document_priority": ["codes", "plenums", "sublegal"],
        "keywords": [
            "трудовой договор", "трудовые отношения", "работодатель", "работник",
            "увольнение", "прогул", "дисциплинарное взыскание",
            "трудовой спор", "охрана труда", "заработная плата", "отпуск"
        ],
        "ai_hint": "Изучи главы о трудовом договоре, увольнении, трудовых спорах и охране труда"
    },
    
    "enforcement_general": {
        "name": "Исполнительное производство",
        "laws": ["fssp.docx"],
        "document_priority": ["sublegal", "codes", "plenums"],
        "keywords": [
            "судебные приставы", "исполнительное производство",
            "взыскатель", "исполнительный лист",
            "обращение взыскания", "залоговое имущество"
        ],
        "ai_hint": "Смотри главы об исполнительном производстве и правах взыскателей"
    },
    
    "bankruptcy": {
        "name": "Банкротство",
        "laws": ["bankrotstvo.docx", "gk_rf_1.docx", "gk_rf_2.docx"],
        "document_priority": ["sublegal", "codes", "plenums"],
        "keywords": [
            "несостоятельность", "банкротство", "конкурсное производство",
            "финансовый управляющий", "реестр требований", "арбитражный управляющий"
        ],
        "ai_hint": "Проверь разделы о признании банкротом и процедурах банкротства"
    },
    
    "administrative": {
        "name": "Административное право",
        "laws": ["koap.docx"],
        "document_priority": ["codes", "plenums", "sublegal"],
        "keywords": [
            "административное правонарушение", "административный протокол",
            "административная ответственность", "административный штраф"
        ],
        "ai_hint": "Ищи в разделах об административных правонарушениях"
    },
    
    "gibdd": {
        "name": "Штрафы ГИБДД и дорожное движение",
        "laws": ["pdd.docx", "koap.docx", "police.docx"],
        "document_priority": ["sublegal", "codes", "plenums"],
        "keywords": [
            "нарушение пдд", "дтп", "превышение скорости",
            "лишение прав", "проезд на красный"
        ],
        "ai_hint": "Смотри главы ПДД и статьи КоАП о дорожных правонарушениях"
    },
    
    "consumer": {
        "name": "Защита прав потребителей",
        "laws": ["zpp.docx", "gk_rf_1.docx", "gk_rf_2.docx"],
        "document_priority": ["sublegal", "codes", "plenums"],
        "keywords": [
            "возврат товара", "защита прав потребителя",
            "гарантийный ремонт",
        ],
        "ai_hint": "Обрати внимание на права потребителя при продаже товаров"
    },
    
    "equity_construction": {
        "name": "Долевое строительство",
        "laws": ["zakon dolevoi.docx", "postanov o neusto k dolevoi.docx", "zhilishniy_kodeks.docx"],
        "document_priority": ["sublegal", "codes", "plenums"],
        "keywords": [
            "застройщик", "долевое строительство", "дольщик", "дду", "ДДУ"
        ],
        "ai_hint": "Изучи законы о долевом строительстве и правах дольщиков"
    },
    
    "unknown": {
        "name": "Общий поиск",
        "laws": [
            "gk_rf_1.docx", "gk_rf_2.docx", "gk_rf_3.docx", "gk_rf_4.docx",
            "zhilishniy_kodeks.docx", "zpp.docx", "bankrotstvo.docx",
            "fssp.docx", "koap.docx", "pdd.docx", "semeiniy_kodeks.docx",
            "trudovoy_kodeks.docx", "police.docx"
        ],
        "document_priority": ["codes", "sublegal", "plenums"],
        "keywords": [],
        "ai_hint": "Категория не определена — анализируй все доступные законы"
    }
}

# Дополнительный метод для управления распределением документов по категориям
def get_extended_laws_for_category(category_id: str) -> List[str]:
    """Возвращает расширенный список законов для категории с учетом подзаконных актов и Пленумов"""
    
    # Базовые законы из основной конфигурации
    base_laws = LEGAL_CATEGORIES[category_id]["laws"]
    
    # Маппинг дополнительных документов по категориям
    extended_mapping = {
        # Гражданское право
        "civil": [
            "Plenum on the gk 2.docx",
            "Plenum on Part 1 of gk 1.docx"
        ],
        
        # Семейное право
        "family": [
            "Plenum of the Children.docx",
            "Plenum on Consumer (general).docx"
        ],
        
        # Жилищное право
        "housing": [
            "Plenum of property.docx"
        ],
        
        # Трудовое право
        "labor": [
            "Plenum on the work of employees working for individual employers.docx",
            "Plenum of Labour.docx"
        ],
        
        # Исполнительное производство
        "enforcement_general": [
            "Plenum of Enforcement proceedings.docx"
        ],
        
        # Банкротство
        "bankruptcy": [
            "Plenum bankruptcy subsidiary.docx"
        ],
        
        # ГИБДД
        "gibdd": [
            "Plenum of gibdd.docx"
        ],
        
        # Защита прав потребителей
        "consumer": [
            "Plenum on Consumer (general).docx"
        ],
        
        # Долевое строительство
        "equity_construction": [
            "Plenum on the gk 2.docx"
        ]
    }
    
    # Объединяем базовые законы с дополнительными документами
    extended_laws = base_laws + extended_mapping.get(category_id, [])
    
    # Убираем дубликаты
    return list(dict.fromkeys(extended_laws))


# Обновляем DOCUMENT_TYPES чтобы система знала о новых файлах
DOCUMENT_TYPES = {
    "codes": [
        "trudovoy_kodeks.docx", "semeiniy_kodeks.docx", "gk_rf_1.docx", 
        "gk_rf_2.docx", "gk_rf_3.docx", "gk_rf_4.docx", "zhilishniy_kodeks.docx", 
        "koap.docx", "fssp.docx", "pdd.docx", "police.docx",
        "bankrotstvo.docx", "zpp.docx", "Postanov o mkd 354.docx",
        "Postanov Mos o MKD.docx", "Post pravit N 290.docx",
    ],
    "plenums": [
        # Пленумы по трудовому праву
        "Plenum on the work of employees working for individual employers.docx","Plenum of Labour.docx",
        
        # Пленумы по семейному праву
        "Plenum on Consumer (general).docx", "Plenum of the Children.docx",
        
        # Пленумы по гражданскому праву
        "Plenum on the gk 2.docx","Plenum on Part 1 of gk 1.docx",
        
        # Пленумы по исполнительному производству
        "Plenum of Enforcement proceedings.docx",
        
        # Пленумы по банкротству
        "Plenum bankruptcy subsidiary.docx",
                
        # Пленумы по ГИБДД
        "Plenum of gibdd.docx",
        
        # Пленумы по защите прав потребителей
        "Plenum on Consumer (general).docx",
        
        # Пленумы по жилищному праву
        "Plenum of property.docx",
        
        # Пленумы по долевому строительству
        "Plenum on the gk 2.dосx"
    ],
    "sublegal": [
        "postanov o neusto k dolevoi.docx, zakon dolevoi.docx", "Postanov o mrk 491.docx", "Post Gosstoya.docx"        
    ]
}

class Config:
    # Пути к данным
    LAWS_DIR = "laws"
    CHROMA_DIR = "chroma_db"
    
    # Делаем глобальные переменные доступными через класс
    LEGAL_CATEGORIES = LEGAL_CATEGORIES
    DOCUMENT_TYPES = DOCUMENT_TYPES
    get_extended_laws_for_category = staticmethod(get_extended_laws_for_category)

config = Config()

def get_law_display_name(filename: str) -> str:
    """Возвращает user-friendly название закона по его filename"""
    
    LAW_DISPLAY_NAMES: Dict[str, str] = {
        "bankrotstvo.docx": 'ФЗ "О НЕСОСТОЯТЕЛЬНОСТИ (БАНКРОТСТВЕ)"',
        "fssp.docx": 'ФЗ "Об исполнительном производстве"',
        "gk_rf_1.docx": "ГК РФ (часть 1)",
        "gk_rf_2.docx": "ГК РФ (часть 2)",
        "gk_rf_3.docx": "ГК РФ (часть 3)",
        "gk_rf_4.docx": "ГК РФ (часть 4)",
        "koap.docx": "КоАП РФ",
        "pdd.docx": "ПДД РФ",
        "Plenum bankruptcy subsidiary.docx": 'ПОСТАНОВЛЕНИЕ ПЛЕНУМА ВС РФ "О НЕКОТОРЫХ ВОПРОСАХ, СВЯЗАННЫХ С ПРИВЛЕЧЕНИЕМ КОНТРОЛИРУЮЩИХ ДОЛЖНИКА ЛИЦ К ОТВЕТСТВЕННОСТИ ПРИ БАНКРОТСТВЕ"',
        "Plenum of Enforcement proceedings.docx": 'Постановление Пленума ВС РФ "О ПРИМЕНЕНИИ СУДАМИ ЗАКОНОДАТЕЛЬСТВА ПРИ РАССМОТРЕНИИ НЕКОТОРЫХ ВОПРОСОВ, ВОЗНИКАЮЩИХ В ХОДЕ ИСПОЛНИТЕЛЬНОГО ПРОИЗВОДСТВА"',
        "Plenum of gibdd.docx": 'Постановление Пленума ВС РФ "О НЕКОТОРЫХ ВОПРОСАХ, ВОЗНИКАЮЩИХ В СУДЕБНОЙ ПРАКТИКЕ ПРИ РАССМОТРЕНИИ ДЕЛ ОБ АДМИНИСТРАТИВНЫХ ПРАВОНАРУШЕНИЯХ, ПРЕДУСМОТРЕННЫХ ГЛАВОЙ 12 КОДЕКСА РОССИЙСКОЙ ФЕДЕРАЦИИ ОБ АДМИНИСТРАТИВНЫХ ПРАВОНАРУШЕНИЯХ"',
        "Plenum of Heritage.docx": 'Постановление Пленума ВС РФ "О СУДЕБНОЙ ПРАКТИКЕ ПО ДЕЛАМ О НАСЛЕДОВАНИИ"',
        "Plenum of Labour.docx": 'Постановление Пленума ВС РФ от 17.04.2004 "О ПРИМЕНЕНИИ СУДАМИ РОССИЙСКОЙ ФЕДЕРАЦИИ ТРУДОВОГО КОДЕКСА РОССИЙСКОЙ ФЕДЕРАЦИИ"',
        "Plenum of property.docx": 'Постановление Пленума ВС РФ "О НЕКОТОРЫХ ВОПРОСАХ РАССМОТРЕНИЯ СУДАМИ СПОРОВ ПО ОПЛАТЕ КОММУНАЛЬНЫХ УСЛУГ И ЖИЛОГО ПОМЕЩЕНИЯ, ЗАНИМАЕМОГО ГРАЖДАНАМИ В МНОГОКВАРТИРНОМ ДОМЕ ПО ДОГОВОРУ СОЦИАЛЬНОГО НАЙМА ИЛИ ПРИНАДЛЕЖАЩЕГО ИМ НА ПРАВЕ СОБСТВЕННОСТИ"',
        "Plenum on Consumer (general).docx": 'Постановление Пленума ВС РФ "О РАССМОТРЕНИИ СУДАМИ ГРАЖДАНСКИХ ДЕЛ ПО СПОРАМ О ЗАЩИТЕ ПРАВ ПОТРЕБИТЕЛЕЙ"',
        "Plenum of the Children.docx": 'Постановление Пленума ВС РФ "О ПРИМЕНЕНИИ СУДАМИ ЗАКОНОДАТЕЛЬСТВА ПРИ РАССМОТРЕНИИ ДЕЛ, СВЯЗАННЫХ С УСТАНОВЛЕНИЕМ ПРОИСХОЖДЕНИЯ ДЕТЕЙ"',
        "Plenum on Part 1 of gk 1.docx": 'Постановление Пленума ВС РФ "О ПРИМЕНЕНИИ СУДАМИ НЕКОТОРЫХ ПОЛОЖЕНИЙ РАЗДЕЛА I ЧАСТИ ПЕРВОЙ ГРАЖДАНСКОГО КОДЕКСА РОССИЙСКОЙ ФЕДЕРАЦИИ"',
        "Plenum on the gk 2.docx": 'Постановление Пленума ВС РФ "О ПРИМЕНЕНИИ СУДАМИ НЕКОТОРЫХ ПОЛОЖЕНИЙ ГРАЖДАНСКОГО КОДЕКСА РОССИЙСКОЙ ФЕДЕРАЦИИ ОБ ОТВЕТСТВЕННОСТИ ЗА НАРУШЕНИЕ ОБЯЗАТЕЛЬСТВ"',
        "Plenum on the work of employees working for individual employers.docx": 'Постановление Пленума ВС РФ "О ПРИМЕНЕНИИ ЗАКОНОДАТЕЛЬСТВА, РЕГУЛИРУЮЩЕГО ТРУД РАБОТНИКОВ, РАБОТАЮЩИХ У РАБОТОДАТЕЛЕЙ - ФИЗИЧЕСКИХ ЛИЦ"',
        "police.docx": 'ФЗ "О полиции"',
        "Post Gosstoya.docx": 'Постановление Госстроя РФ от 27.09.2003 N 170 "Об утверждении Правил и норм технической эксплуатации жилищного фонда"',
        "Post pravit N 290.docx": 'Постановление Правительства РФ от 03.04.2013 N 290 "О минимальном перечне услуг и работ, необходимых для обеспечения надлежащего содержания общего имущества в многоквартирном доме, и порядке их оказания и выполнения"',
        "Postanov Mos o MKD.docx": 'Постановление Правительства Москвы от 9 ноября 1999 г. N 1018 "ОБ УТВЕРЖДЕНИИ ПРАВИЛ САНИТАРНОГО СОДЕРЖАНИЯ ТЕРРИТОРИЙ, ОРГАНИЗАЦИИ УБОРКИ И ОБЕСПЕЧЕНИЯ ЧИСТОТЫ И ПОРЯДКА В Г. МОСКВЕ"',
        "Postanov o mkd 354.docx": 'Постановление Правительства РФ №354 "О предоставлении коммунальных услуг собственникам и пользователям помещений в многоквартирных домах и жилых домов"',
        "Postanov o mrk 491.docx": 'Постановление Правительства РФ № 491 "Об утверждении Правил содержания общего имущества в многоквартирном доме"',
        "postanov o neusto k dolevoi.docx": 'Постановление Правительства РФ "О ПОРЯДКЕ ОПРЕДЕЛЕНИЯ РАЗМЕРА НЕУСТОЙКИ ПО ДОГОВОРУ УЧАСТИЯ В ДОЛЕВОМ СТРОИТЕЛЬСТВЕ"',
        "semeiniy_kodeks.docx": "Семейный Кодекс РФ",
        "trudovoy_kodeks.docx": "Трудовой Кодекс РФ",
        "zakon dolevoi.docx": 'ФЗ "ОБ УЧАСТИИ В ДОЛЕВОМ СТРОИТЕЛЬСТВЕ МНОГОКВАРТИРНЫХ ДОМОВ И ИНЫХ ОБЪЕКТОВ НЕДВИЖИМОСТИ"',
        "zhilishniy_kodeks.docx": "Жилищный Кодекс РФ",
        "zpp.docx": 'Закон РФ "О защите прав потребителей"',
        "crime codex.docx": "Уголовный Кодекс РФ",
    }
    
    return LAW_DISPLAY_NAMES.get(filename, filename)



# api_manager.py
"""
Централизованный менеджер для всех API запросов
С РАЗДЕЛЕНИЕМ API: поиск и генерация используют разные ключи
"""

import os
import requests
import base64
import uuid
import time
import certifi
import urllib3
import warnings
from dotenv import load_dotenv
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Отключаем только предупреждения, но не проверку SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# Загружаем .env
load_dotenv()

class APIManager:
    """Единая точка входа для всех API запросов с РАЗДЕЛЕНИЕМ API ключей"""
    
    def __init__(self):
        # 🔥 РАЗДЕЛЕНИЕ API КЛЮЧЕЙ
        self.deepseek_api_key_search = os.getenv("DEEPSEEK_API_KEY")  # Для поиска
        self.deepseek_api_key_generation = os.getenv("DEEPSEEK_API_KEY_GENERATION")  # Для генерации
        
        # GigaChat credentials
        self.gigachat_auth_key = os.getenv("GIGACHAT_AUTH_KEY")
        self.gigachat_scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.gigachat_client_id = os.getenv("GIGACHAT_CLIENT_ID")
        self.gigachat_client_secret = os.getenv("GIGACHAT_CLIENT_SECRET")
        
        # Токен GigaChat
        self.gigachat_access_token = None
        self.gigachat_token_expires = 0
        
        print("🔧 Инициализация API Manager с разделением ключей...")
        print(f"   DeepSeek API (поиск): {'✅' if self.deepseek_api_key_search else '❌'}")
        print(f"   DeepSeek API (генерация): {'✅' if self.deepseek_api_key_generation else '❌'}")
        
        gigachat_available = (self.gigachat_auth_key or 
                            (self.gigachat_client_id and self.gigachat_client_secret))
        print(f"   GigaChat API: {'✅' if gigachat_available else '❌'}")

    def _get_gigachat_token(self):
        """Получает/обновляет токен доступа GigaChat"""
        
        if self.gigachat_access_token and time.time() < self.gigachat_token_expires - 300:
            return self.gigachat_access_token
        
        auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        rq_uid = str(uuid.uuid4())
        
        # Определяем метод авторизации
        if self.gigachat_auth_key:
            encoded_credentials = self.gigachat_auth_key
        elif self.gigachat_client_id and self.gigachat_client_secret:
            credentials = f"{self.gigachat_client_id}:{self.gigachat_client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
        else:
            raise ValueError("GigaChat credentials not configured")
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'Authorization': f'Basic {encoded_credentials}',
            'RqUID': rq_uid
        }
        
        data = {'scope': self.gigachat_scope}
        
        try:
            ssl_verify = self._test_ssl_connection(auth_url)
            
            response = requests.post(
                auth_url,
                headers=headers,
                data=data,
                verify=ssl_verify,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ Ошибка получения токена GigaChat: {response.status_code}")
                response.raise_for_status()
            
            token_data = response.json()
            self.gigachat_access_token = token_data['access_token']
            
            if 'expires_in' in token_data:
                self.gigachat_token_expires = time.time() + token_data['expires_in']
            elif 'expires_at' in token_data:
                self.gigachat_token_expires = token_data['expires_at'] / 1000
            else:
                self.gigachat_token_expires = time.time() + 1800
            
            print("🔑 Получен новый токен GigaChat")
            return self.gigachat_access_token
            
        except requests.exceptions.SSLError as e:
            print(f"🔴 SSL ошибка GigaChat: {e}")
            print("⚠️  Повтор запроса без SSL проверки...")
            response = requests.post(
                auth_url,
                headers=headers,
                data=data,
                verify=False,
                timeout=30
            )
            response.raise_for_status()
            token_data = response.json()
            self.gigachat_access_token = token_data['access_token']
            self.gigachat_token_expires = time.time() + 1800
            return self.gigachat_access_token
            
        except Exception as e:
            raise Exception(f"Ошибка получения токена GigaChat: {str(e)}")

    def _test_ssl_connection(self, url):
        """Тестирует SSL подключение и возвращает оптимальные настройки"""
        try:
            test_response = requests.get(url, timeout=5, verify=certifi.where())
            print("   ✅ SSL сертификаты работают")
            return certifi.where()
        except Exception as e:
            print(f"   ⚠️  SSL ошибка: {e}")
            print("   🔧 Используется fallback без SSL проверки")
            return False

    def gigachat_completion(self, messages, temperature=0.1, response_format=None):
        """Специализированный метод для GigaChat"""
        if not self.gigachat_auth_key and not (self.gigachat_client_id and self.gigachat_client_secret):
            raise ValueError("GigaChat credentials not configured")
            
        token = self._get_gigachat_token()
        url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        payload = {
            "model": "GigaChat-2-Pro",
            "messages": messages,
            "temperature": temperature
        }
        
        # Добавляем response_format если передан
        if response_format:
            payload["response_format"] = response_format
        
        try:
            print(f"🔗 GigaChat API запрос...")
            
            ssl_verify = self._test_ssl_connection("https://gigachat.devices.sberbank.ru")
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                verify=ssl_verify,
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"❌ Ошибка GigaChat API: {response.status_code}")
                response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.SSLError:
            print("⚠️  SSL ошибка, повтор запроса без проверки...")
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                verify=False,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            raise Exception(f"Ошибка GigaChat API: {str(e)}")

    def deepseek_completion(self, messages, temperature=0.2, timeout=90, response_format=None):
        """🔍 API ДЛЯ ПОИСКА И АНАЛИЗА - использует DEEPSEEK_API_KEY"""
        if not self.deepseek_api_key_search:
            raise ValueError("DeepSeek API ключ для поиска не найден в .env файле")
        
        endpoint = "https://api.deepseek.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key_search}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        # Добавляем response_format если передан
        if response_format:
            payload["response_format"] = response_format
        
        try:
            print(f"🔗 DeepSeek API (ПОИСК) запрос...")
            
            ssl_verify = self._test_ssl_connection("https://api.deepseek.com")
            
            response = requests.post(
                endpoint, 
                headers=headers, 
                json=payload, 
                timeout=timeout,
                verify=ssl_verify
            )
            
            if response.status_code != 200:
                print(f"❌ Ошибка DeepSeek API (поиск): {response.status_code}")
                response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.SSLError:
            print("⚠️  SSL ошибка DeepSeek, повтор запроса без проверки...")
            response = requests.post(
                endpoint, 
                headers=headers, 
                json=payload, 
                timeout=timeout,
                verify=False
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            raise Exception(f"Ошибка DeepSeek API (поиск): {str(e)}")

    def deepseek_generation(self, messages, temperature=0.3, timeout=120, response_format=None):
        """🧠 API ДЛЯ ГЕНЕРАЦИИ ОТВЕТОВ - использует DEEPSEEK_API_KEY_GENERATION"""
        if not self.deepseek_api_key_generation:
            raise ValueError("DeepSeek API ключ для генерации не найден в .env файле")
        
        endpoint = "https://api.deepseek.com/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key_generation}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "stream": False,
            # 🔥 ОПТИМИЗИРОВАННЫЕ ПАРАМЕТРЫ ДЛЯ ЮРИДИЧЕСКИХ ОТВЕТОВ:
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1
        }
        
        # Добавляем response_format если передан
        if response_format:
            payload["response_format"] = response_format
        
        try:
            print(f"🔗 DeepSeek API (ГЕНЕРАЦИЯ) запрос...")
            
            ssl_verify = self._test_ssl_connection("https://api.deepseek.com")
            
            response = requests.post(
                endpoint, 
                headers=headers, 
                json=payload, 
                timeout=timeout,
                verify=ssl_verify
            )
            
            if response.status_code != 200:
                print(f"❌ Ошибка DeepSeek API (генерация): {response.status_code}")
                response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.SSLError:
            print("⚠️  SSL ошибка DeepSeek, повтор запроса без проверки...")
            response = requests.post(
                endpoint, 
                headers=headers, 
                json=payload, 
                timeout=timeout,
                verify=False
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            raise Exception(f"Ошибка DeepSeek API (генерация): {str(e)}")

# Глобальный экземпляр
api_manager = APIManager()
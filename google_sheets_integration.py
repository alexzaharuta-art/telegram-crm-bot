"""
Google Sheets Integration for RetailCRM Telegram Bot
Синхронизация данных между Telegram ботом и Google Sheets
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    """Управление Google Sheets для CRM"""
    
    def __init__(self, spreadsheet_id: str, credentials_json: str = None):
        """
        Инициализация Google Sheets менеджера
        
        Args:
            spreadsheet_id: ID Google Sheets таблицы
            credentials_json: JSON ключ для Google API (или путь к файлу)
        """
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.spreadsheet = None
        
        try:
            # Пытаемся загрузить credentials
            if credentials_json:
                if os.path.isfile(credentials_json):
                    # Это путь к файлу
                    creds = ServiceAccountCredentials.from_json_keyfile_name(
                        credentials_json,
                        scopes=['https://www.googleapis.com/auth/spreadsheets']
                    )
                else:
                    # Это JSON строка
                    creds_dict = json.loads(credentials_json)
                    creds = ServiceAccountCredentials.from_json_keyfile_dict(
                        creds_dict,
                        scopes=['https://www.googleapis.com/auth/spreadsheets']
                    )
                
                self.client = gspread.authorize(creds)
                self.spreadsheet = self.client.open_by_key(spreadsheet_id)
                logger.info(f"✅ Google Sheets подключен: {self.spreadsheet.title}")
            else:
                logger.warning("⚠️ Google Sheets credentials не установлены")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
    
    def get_worksheet(self, title: str) -> Optional[gspread.Worksheet]:
        """Получить лист по названию"""
        try:
            return self.spreadsheet.worksheet(title)
        except Exception as e:
            logger.error(f"Лист '{title}' не найден: {e}")
            return None
    
    def add_customer(self, customer_id: str, name: str, email: str, phone: str, city: str) -> bool:
        """Добавить клиента в Google Sheets"""
        try:
            worksheet = self.get_worksheet("Клиенты")
            if not worksheet:
                return False
            
            row = [
                customer_id,
                name,
                email,
                phone,
                city,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            worksheet.append_row(row)
            logger.info(f"✅ Клиент добавлен: {name}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении клиента: {e}")
            return False
    
    def add_sale(self, sale_id: str, product_name: str, quantity: int, 
                 price_usd: float, seller: str) -> bool:
        """Добавить продажу в Google Sheets"""
        try:
            worksheet = self.get_worksheet("Продажи")
            if not worksheet:
                return False
            
            row = [
                sale_id,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                product_name,
                quantity,
                price_usd * quantity,
                seller,
                "✅ Завершено"
            ]
            worksheet.append_row(row)
            logger.info(f"✅ Продажа добавлена: {product_name} x{quantity}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении продажи: {e}")
            return False
    
    def log_operation(self, user: str, operation: str, details: str) -> bool:
        """Записать операцию в историю"""
        try:
            worksheet = self.get_worksheet("История операций")
            if not worksheet:
                return False
            
            row = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                user,
                operation,
                details,
                "✅ OK"
            ]
            worksheet.append_row(row)
            logger.info(f"✅ Операция записана: {operation}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при записи операции: {e}")
            return False
    
    def get_customers(self) -> List[Dict]:
        """Получить всех клиентов из Google Sheets"""
        try:
            worksheet = self.get_worksheet("Клиенты")
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            logger.info(f"✅ Загружено {len(records)} клиентов")
            return records
        except Exception as e:
            logger.error(f"Ошибка при получении клиентов: {e}")
            return []
    
    def get_products(self) -> List[Dict]:
        """Получить все товары из Google Sheets"""
        try:
            worksheet = self.get_worksheet("Товары")
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            logger.info(f"✅ Загружено {len(records)} товаров")
            return records
        except Exception as e:
            logger.error(f"Ошибка при получении товаров: {e}")
            return []
    
    def get_employees(self) -> List[Dict]:
        """Получить всех сотрудников из Google Sheets"""
        try:
            worksheet = self.get_worksheet("Сотрудники")
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            logger.info(f"✅ Загружено {len(records)} сотрудников")
            return records
        except Exception as e:
            logger.error(f"Ошибка при получении сотрудников: {e}")
            return []
    
    def get_sales(self) -> List[Dict]:
        """Получить все продажи из Google Sheets"""
        try:
            worksheet = self.get_worksheet("Продажи")
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            logger.info(f"✅ Загружено {len(records)} продаж")
            return records
        except Exception as e:
            logger.error(f"Ошибка при получении продаж: {e}")
            return []
    
    def update_product_stock(self, product_id: str, new_stock: int) -> bool:
        """Обновить запас товара"""
        try:
            worksheet = self.get_worksheet("Товары")
            if not worksheet:
                return False
            
            # Найти товар и обновить запас
            records = worksheet.get_all_records()
            for idx, record in enumerate(records, start=2):  # +2 потому что строка 1 - заголовок
                if record.get("ID") == product_id:
                    worksheet.update_cell(idx, 5, new_stock)  # Столбец 5 - Запас
                    logger.info(f"✅ Запас товара {product_id} обновлен: {new_stock}")
                    return True
            
            logger.warning(f"Товар {product_id} не найден")
            return False
        except Exception as e:
            logger.error(f"Ошибка при обновлении запаса: {e}")
            return False
    
    def get_salary_report(self) -> Dict:
        """Получить отчет по зарплате"""
        try:
            worksheet = self.get_worksheet("Отчеты")
            if not worksheet:
                return {}
            
            records = worksheet.get_all_records()
            logger.info(f"✅ Отчет по зарплате получен")
            return records
        except Exception as e:
            logger.error(f"Ошибка при получении отчета: {e}")
            return {}

# Глобальный экземпляр менеджера
sheets_manager = None

def init_sheets_manager(spreadsheet_id: str, credentials_json: str = None) -> GoogleSheetsManager:
    """Инициализировать глобальный менеджер Google Sheets"""
    global sheets_manager
    sheets_manager = GoogleSheetsManager(spreadsheet_id, credentials_json)
    return sheets_manager

def get_sheets_manager() -> Optional[GoogleSheetsManager]:
    """Получить глобальный менеджер Google Sheets"""
    return sheets_manager

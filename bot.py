#!/usr/bin/env python3
"""
RetailCRM Telegram Bot - Українська версія
Повнофункціональна CRM система для управління магазином
Розгорнуто на Railway з webhook підтримкою
"""

import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.error import TelegramError
import requests
from io import BytesIO

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константи - читаємо з змінних оточення
BOT_TOKEN = os.getenv("BOT_TOKEN", "8747572018:AAFEFoum-bcnSCCTuEwJkKBow9tR0DfcIc0")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-key")
PORT = int(os.getenv("PORT", 8080))
RAILWAY_STATIC_URL = os.getenv("RAILWAY_STATIC_URL", "")

# Дані для демонстрації (локальне сховище)
USERS_DB = {
    "david@company.com": {"name": "Давид Джонсон", "role": "менеджер", "salary_base": 500, "commission": 5},
    "sarah@company.com": {"name": "Сара Уільямс", "role": "керівник", "salary_base": 800, "commission": 3},
    "michael@company.com": {"name": "Майкл Браун", "role": "менеджер", "salary_base": 400, "commission": 5},
    "anna@company.com": {"name": "Анна Смирнова", "role": "менеджер", "salary_base": 450, "commission": 4},
}

CUSTOMERS_DB = [
    {"id": "C001", "name": "Іван Петров", "email": "ivan@example.com", "phone": "+380-50-1234567", "city": "Київ"},
    {"id": "C002", "name": "Марія Сидорова", "email": "maria@example.com", "phone": "+380-50-7654321", "city": "Харків"},
    {"id": "C003", "name": "Петро Іванов", "email": "petr@example.com", "phone": "+380-50-9876543", "city": "Львів"},
    {"id": "C004", "name": "Анна Смирнова", "email": "anna@example.com", "phone": "+380-50-5555555", "city": "Одеса"},
    {"id": "C005", "name": "Сергій Козлов", "email": "sergey@example.com", "phone": "+380-50-3333333", "city": "Дніпро"},
]

PRODUCTS_DB = [
    {"id": "P001", "name": "iPhone 16 128GB", "price_usd": 799, "price_uah": 31960, "stock": 15, "min_stock": 5},
    {"id": "P002", "name": "iPhone 16 Pro 256GB", "price_usd": 1280, "price_uah": 51200, "stock": 8, "min_stock": 5},
    {"id": "P003", "name": "iPad Pro 12.9\"", "price_usd": 1600, "price_uah": 64000, "stock": 12, "min_stock": 5},
    {"id": "P004", "name": "AirPods Pro 2", "price_usd": 320, "price_uah": 12800, "stock": 25, "min_stock": 10},
    {"id": "P005", "name": "Apple Watch Series 9", "price_usd": 399, "price_uah": 15960, "stock": 12, "min_stock": 5},
    {"id": "P006", "name": "MacBook Air M3", "price_usd": 1199, "price_uah": 47960, "stock": 3, "min_stock": 2},
    {"id": "P007", "name": "iPad Air 11\"", "price_usd": 960, "price_uah": 38400, "stock": 10, "min_stock": 5},
    {"id": "P008", "name": "iPad Mini 7\"", "price_usd": 499, "price_uah": 19960, "stock": 8, "min_stock": 3},
    {"id": "P009", "name": "Apple TV 4K", "price_usd": 129, "price_uah": 5160, "stock": 20, "min_stock": 10},
    {"id": "P010", "name": "iPhone 16 Pro Max", "price_usd": 1599, "price_uah": 63960, "stock": 5, "min_stock": 3},
]

SALES_DB = []
OPERATION_HISTORY = []

# Стани для ConversationHandler
(MENU, ADD_CUSTOMER, ADD_SALE, VIEW_INVENTORY, VIEW_SALES, CALC_SALARY, 
 CUSTOMER_NAME, CUSTOMER_PHONE, CUSTOMER_CITY, SALE_CUSTOMER, SALE_PRODUCT, SALE_QUANTITY) = range(12)

# Функції для роботи з даними
def log_operation(user_email: str, operation: str, details: str):
    """Записує операцію в історію"""
    OPERATION_HISTORY.append({
        "timestamp": datetime.now().isoformat(),
        "user": user_email,
        "operation": operation,
        "details": details
    })

def get_main_menu_keyboard():
    """Повертає клавіатуру головного меню"""
    keyboard = [
        [KeyboardButton("👥 Клієнти"), KeyboardButton("🛍️ Продажі")],
        [KeyboardButton("📦 Склад"), KeyboardButton("💰 Зарплата")],
        [KeyboardButton("📊 Звіти"), KeyboardButton("⚙️ Налаштування")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привіт, {user.first_name}!\n\n"
        f"Ласкаво просимо до RetailCRM 🏪\n\n"
        f"Оберіть дію:",
        reply_markup=get_main_menu_keyboard()
    )
    return MENU

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору з меню"""
    text = update.message.text
    user = update.effective_user
    
    if text == "👥 Клієнти":
        keyboard = [
            [InlineKeyboardButton("➕ Додати клієнта", callback_data="add_customer")],
            [InlineKeyboardButton("📋 Список клієнтів", callback_data="list_customers")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text(
            "👥 Управління клієнтами:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif text == "🛍️ Продажі":
        keyboard = [
            [InlineKeyboardButton("➕ Нова продаж", callback_data="add_sale")],
            [InlineKeyboardButton("📊 Мої продажі", callback_data="my_sales")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text(
            "🛍️ Управління продажами:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif text == "📦 Склад":
        stock_info = "📦 Статус складу:\n\n"
        for product in PRODUCTS_DB:
            status = "✅ OK" if product["stock"] > product["min_stock"] else "⚠️ Низько"
            stock_info += f"{product['name']}\n"
            stock_info += f"  Запас: {product['stock']} шт. | {status}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await update.message.reply_text(stock_info, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "💰 Зарплата":
        salary_info = "💰 Розрахунок зарплати (квітень 2026):\n\n"
        for email, user_data in USERS_DB.items():
            # Підраховуємо продажі користувача
            user_sales = sum(s["amount_usd"] for s in SALES_DB if s["seller_email"] == email)
            commission = (user_sales * user_data["commission"]) / 100
            total = user_data["salary_base"] + commission
            
            salary_info += f"👤 {user_data['name']}\n"
            salary_info += f"  Оклад: ${user_data['salary_base']}\n"
            salary_info += f"  Комісія ({user_data['commission']}%): ${commission:.2f}\n"
            salary_info += f"  Всього: ${total:.2f}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await update.message.reply_text(salary_info, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "📊 Звіти":
        total_sales = len(SALES_DB)
        total_revenue = sum(s["amount_usd"] for s in SALES_DB)
        
        report = f"📊 Звіти:\n\n"
        report += f"📈 Всього продаж: {total_sales}\n"
        report += f"💵 Загальний дохід: ${total_revenue:.2f}\n"
        report += f"👥 Активних клієнтів: {len(CUSTOMERS_DB)}\n"
        report += f"📦 Товарів на складі: {sum(p['stock'] for p in PRODUCTS_DB)}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await update.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "⚙️ Налаштування":
        keyboard = [
            [InlineKeyboardButton("👤 Мій профіль", callback_data="profile")],
            [InlineKeyboardButton("📝 Історія операцій", callback_data="history")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text(
            "⚙️ Налаштування:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    return MENU

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_menu":
        await query.edit_message_text(
            text="Оберіть дію:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Оновити меню", callback_data="refresh_menu")
            ]])
        )
        await query.message.reply_text("Оберіть дію:", reply_markup=get_main_menu_keyboard())
    
    elif query.data == "list_customers":
        customers_text = "👥 Список клієнтів:\n\n"
        for customer in CUSTOMERS_DB:
            customers_text += f"👤 {customer['name']}\n"
            customers_text += f"  Email: {customer['email']}\n"
            customers_text += f"  Телефон: {customer['phone']}\n"
            customers_text += f"  Місто: {customer['city']}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(customers_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "add_customer":
        await query.edit_message_text("Введіть ім'я клієнта:")
        return CUSTOMER_NAME
    
    elif query.data == "add_sale":
        products_text = "🛍️ Оберіть товар:\n\n"
        keyboard = []
        for product in PRODUCTS_DB:
            products_text += f"{product['name']} - ${product['price_usd']}\n"
            keyboard.append([InlineKeyboardButton(product['name'], callback_data=f"product_{product['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_menu")])
        await query.edit_message_text(products_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "profile":
        user_email = "david@company.com"  # Для демонстрації
        if user_email in USERS_DB:
            user_data = USERS_DB[user_email]
            profile_text = f"👤 Мій профіль:\n\n"
            profile_text += f"Ім'я: {user_data['name']}\n"
            profile_text += f"Email: {user_email}\n"
            profile_text += f"Посада: {user_data['role']}\n"
            profile_text += f"Оклад: ${user_data['salary_base']}\n"
            profile_text += f"Комісія: {user_data['commission']}%\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "history":
        history_text = "📝 Історія операцій (останні 5):\n\n"
        for op in OPERATION_HISTORY[-5:]:
            history_text += f"⏰ {op['timestamp']}\n"
            history_text += f"👤 {op['user']}\n"
            history_text += f"📌 {op['operation']}: {op['details']}\n\n"
        
        if not OPERATION_HISTORY:
            history_text = "📝 Історія операцій порожня"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(history_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("product_"):
        product_id = query.data.split("_")[1]
        product = next((p for p in PRODUCTS_DB if p["id"] == product_id), None)
        
        if product:
            await query.edit_message_text(
                f"Ви вибрали: {product['name']}\n"
                f"Ціна: ${product['price_usd']}\n\n"
                f"Введіть кількість:"
            )
            context.user_data["selected_product"] = product
            return SALE_QUANTITY
    
    return MENU

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка помилок"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

async def post_init(app: Application) -> None:
    """Налаштування webhook після запуску"""
    try:
        # Отримуємо публічний URL з Railway
        if RAILWAY_STATIC_URL:
            webhook_url = f"{RAILWAY_STATIC_URL}/webhook"
        else:
            # Якщо RAILWAY_STATIC_URL не встановлено, використовуємо polling
            logger.info("RAILWAY_STATIC_URL не встановлено, використовуємо polling")
            return
        
        # Встановлюємо webhook
        await app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook встановлено: {webhook_url}")
    except Exception as e:
        logger.error(f"Помилка при встановленні webhook: {e}")

def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Обробники команд
    app.add_handler(CommandHandler("start", start))
    
    # Обробник текстових повідомлень
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    # Обробник кнопок
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Обробник помилок
    app.add_error_handler(error_handler)
    
    # Post-init для webhook
    app.post_init = post_init
    
    # Запуск бота
    print("🤖 RetailCRM Telegram Bot запущено...")
    print(f"📱 Бот готовий до роботи!")
    
    # Використовуємо polling (простіше для Railway)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

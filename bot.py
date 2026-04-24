#!/usr/bin/env python3
"""
RetailCRM Telegram Bot - Українська версія
Повнофункціональна CRM система для управління магазином
Розгорнуто на Railway з Google Sheets синхронізацією
"""

import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.error import TelegramError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
from google_sheets_integration import init_sheets_manager, get_sheets_manager

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константи - читаємо з змінних оточення
BOT_TOKEN = os.getenv("BOT_TOKEN", "8747572018:AAFEFoum-bcnSCCTuEwJkKBow9tR0DfcIc0")
PORT = int(os.getenv("PORT", 8000))
WEBHOOK_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "1D7jcMc-xDzdd1r5rFYlsNrYeSblwmK-HDgvjIstOsK4")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")

# Дані для демонстрації (локальне сховище)
USERS_DB = {
    "david@company.com": {"name": "Давид Джонсон", "role": "менеджер", "salary_base": 500, "commission": 5},
    "sarah@company.com": {"name": "Сара Уільямс", "role": "керівник", "salary_base": 800, "commission": 3},
    "michael@company.com": {"name": "Майкл Браун", "role": "менеджер", "salary_base": 400, "commission": 5},
    "anna@company.com": {"name": "Анна Смирнова", "role": "менеджер", "salary_base": 450, "commission": 4},
}

CUSTOMERS_DB = []
PRODUCTS_DB = []
SALES_DB = []
OPERATION_HISTORY = []

# Стани для ConversationHandler
(MENU, ADD_CUSTOMER, ADD_SALE, VIEW_INVENTORY, VIEW_SALES, CALC_SALARY, 
 CUSTOMER_NAME, CUSTOMER_PHONE, CUSTOMER_CITY, SALE_CUSTOMER, SALE_PRODUCT, SALE_QUANTITY) = range(12)

# FastAPI app
app = FastAPI()

# Telegram application (глобальна)
application = None
sheets_manager = None

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
        # Завантажуємо товари з Google Sheets
        if sheets_manager:
            PRODUCTS_DB.clear()
            products = sheets_manager.get_products()
            PRODUCTS_DB.extend(products)
        
        stock_info = "📦 Статус складу:\n\n"
        if PRODUCTS_DB:
            for product in PRODUCTS_DB:
                name = product.get("Название", "N/A")
                stock = product.get("Запас", 0)
                min_stock = product.get("Минимум", 5)
                status = "✅ OK" if stock > min_stock else "⚠️ Низко"
                stock_info += f"{name}\n"
                stock_info += f"  Запас: {stock} шт. | {status}\n"
        else:
            stock_info = "📦 Складу порожній"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await update.message.reply_text(stock_info, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "💰 Зарплата":
        salary_info = "💰 Розрахунок зарплати (квітень 2026):\n\n"
        for email, user_data in USERS_DB.items():
            user_sales = sum(float(s.get("Цена USD", 0)) for s in SALES_DB if s.get("Продавец", "") == user_data["name"])
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
        total_revenue = sum(float(s.get("Цена USD", 0)) for s in SALES_DB)
        
        report = f"📊 Звіти:\n\n"
        report += f"📈 Всього продаж: {total_sales}\n"
        report += f"💵 Загальний дохід: ${total_revenue:.2f}\n"
        report += f"👥 Активних клієнтів: {len(CUSTOMERS_DB)}\n"
        report += f"📦 Товарів на складі: {sum(int(p.get('Запас', 0)) for p in PRODUCTS_DB)}\n"
        
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
        # Завантажуємо клієнтів з Google Sheets
        if sheets_manager:
            CUSTOMERS_DB.clear()
            customers = sheets_manager.get_customers()
            CUSTOMERS_DB.extend(customers)
        
        customers_text = "👥 Список клієнтів:\n\n"
        if CUSTOMERS_DB:
            for customer in CUSTOMERS_DB:
                name = customer.get("Имя", "N/A")
                email = customer.get("Email", "N/A")
                phone = customer.get("Телефон", "N/A")
                city = customer.get("Город", "N/A")
                customers_text += f"👤 {name}\n"
                customers_text += f"  Email: {email}\n"
                customers_text += f"  Телефон: {phone}\n"
                customers_text += f"  Місто: {city}\n\n"
        else:
            customers_text = "👥 Клієнтів немає"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(customers_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "add_customer":
        await query.edit_message_text("Введіть ім'я клієнта:")
        return CUSTOMER_NAME
    
    elif query.data == "add_sale":
        # Завантажуємо товари з Google Sheets
        if sheets_manager:
            PRODUCTS_DB.clear()
            products = sheets_manager.get_products()
            PRODUCTS_DB.extend(products)
        
        products_text = "🛍️ Оберіть товар:\n\n"
        keyboard = []
        if PRODUCTS_DB:
            for product in PRODUCTS_DB:
                name = product.get("Название", "N/A")
                price = product.get("Цена USD", 0)
                products_text += f"{name} - ${price}\n"
                keyboard.append([InlineKeyboardButton(name, callback_data=f"product_{product.get('ID', 'unknown')}")])
        else:
            products_text = "🛍️ Товарів немає"
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_menu")])
        await query.edit_message_text(products_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "profile":
        user_email = "david@company.com"
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
        # Завантажуємо історію з Google Sheets
        if sheets_manager:
            OPERATION_HISTORY.clear()
            history = sheets_manager.get_sales()
            OPERATION_HISTORY.extend(history)
        
        history_text = "📝 Історія операцій (останні 5):\n\n"
        if OPERATION_HISTORY:
            for op in OPERATION_HISTORY[-5:]:
                history_text += f"⏰ {op.get('Дата/Время', 'N/A')}\n"
                history_text += f"📌 {op.get('Операция', 'N/A')}: {op.get('Детали', 'N/A')}\n\n"
        else:
            history_text = "📝 Історія операцій порожня"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(history_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("product_"):
        product_id = query.data.split("_")[1]
        product = next((p for p in PRODUCTS_DB if p.get("ID") == product_id), None)
        
        if product:
            await query.edit_message_text(
                f"Ви вибрали: {product.get('Название', 'N/A')}\n"
                f"Ціна: ${product.get('Цена USD', 0)}\n\n"
                f"Введіть кількість:"
            )
            context.user_data["selected_product"] = product
            return SALE_QUANTITY
    
    return MENU

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка помилок"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

@app.post("/webhook")
async def webhook(request: Request):
    """Webhook для отримання оновлень від Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "bot": "running", "sheets": "connected" if sheets_manager else "disconnected"}

@app.on_event("startup")
async def startup():
    """Запуск бота при старті FastAPI"""
    global application, sheets_manager
    
    # Ініціалізуємо Google Sheets
    try:
        if GOOGLE_SHEETS_CREDENTIALS:
            sheets_manager = init_sheets_manager(GOOGLE_SHEETS_ID, GOOGLE_SHEETS_CREDENTIALS)
            logger.info("✅ Google Sheets підключен")
            
            # Завантажуємо дані з Google Sheets
            CUSTOMERS_DB.extend(sheets_manager.get_customers())
            PRODUCTS_DB.extend(sheets_manager.get_products())
            SALES_DB.extend(sheets_manager.get_sales())
        else:
            logger.warning("⚠️ GOOGLE_SHEETS_CREDENTIALS не встановлено")
    except Exception as e:
        logger.error(f"❌ Ошибка при ініціалізації Google Sheets: {e}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обробники команд
    application.add_handler(CommandHandler("start", start))
    
    # Обробник текстових повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    # Обробник кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обробник помилок
    application.add_error_handler(error_handler)
    
    # Запуск Application
    await application.initialize()
    await application.start()
    
    # Встановлення webhook або запуск polling
    if WEBHOOK_URL:
        webhook_url = f"https://{WEBHOOK_URL}/webhook"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"✅ Webhook встановлено: {webhook_url}")
    else:
        logger.info("⚠️ RAILWAY_PUBLIC_DOMAIN не встановлено, використовуємо polling")
        asyncio.create_task(application.updater.start_polling(allowed_updates=Update.ALL_TYPES))
    
    logger.info("🤖 RetailCRM Telegram Bot запущено!")

@app.on_event("shutdown")
async def shutdown():
    """Зупинка бота при завершенні FastAPI"""
    global application
    if application:
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

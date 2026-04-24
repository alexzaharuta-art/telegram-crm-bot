#!/usr/bin/env python3
"""
RetailCRM Telegram Bot - Українська версія
Повнофункціональна CRM система з двосторонньою синхронізацією Google Sheets
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
import uuid

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константи
BOT_TOKEN = os.getenv("BOT_TOKEN", "8747572018:AAFEFoum-bcnSCCTuEwJkKBow9tR0DfcIc0")
PORT = int(os.getenv("PORT", 8000))
WEBHOOK_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "1D7jcMc-xDzdd1r5rFYlsNrYeSblwmK-HDgvjIstOsK4")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")

# Дані для демонстрації
USERS_DB = {
    "david@company.com": {"name": "Давид Джонсон", "role": "менеджер", "salary_base": 500, "commission": 5},
    "sarah@company.com": {"name": "Сара Уільямс", "role": "керівник", "salary_base": 800, "commission": 3},
    "michael@company.com": {"name": "Майкл Браун", "role": "менеджер", "salary_base": 400, "commission": 5},
    "anna@company.com": {"name": "Анна Смирнова", "role": "менеджер", "salary_base": 450, "commission": 4},
}

CUSTOMERS_DB = []
PRODUCTS_DB = []
SALES_DB = []

# Стани для ConversationHandler
(MENU, ADD_CUSTOMER_NAME, ADD_CUSTOMER_EMAIL, ADD_CUSTOMER_PHONE, ADD_CUSTOMER_CITY,
 ADD_PRODUCT_NAME, ADD_PRODUCT_PRICE_USD, ADD_PRODUCT_STOCK,
 ADD_SALE_PRODUCT, ADD_SALE_QUANTITY) = range(10)

# FastAPI app
app = FastAPI()
application = None
sheets_manager = None

def get_main_menu_keyboard():
    """Повертає клавіатуру головного меню"""
    keyboard = [
        [KeyboardButton("👥 Клієнти"), KeyboardButton("🛍️ Продажі")],
        [KeyboardButton("📦 Товари"), KeyboardButton("💰 Зарплата")],
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
    
    if text == "👥 Клієнти":
        keyboard = [
            [InlineKeyboardButton("➕ Додати клієнта", callback_data="add_customer")],
            [InlineKeyboardButton("📋 Список клієнтів", callback_data="list_customers")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("👥 Управління клієнтами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "🛍️ Продажі":
        keyboard = [
            [InlineKeyboardButton("➕ Нова продаж", callback_data="add_sale")],
            [InlineKeyboardButton("📊 Мої продажі", callback_data="my_sales")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("🛍️ Управління продажами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "📦 Товари":
        keyboard = [
            [InlineKeyboardButton("➕ Додати товар", callback_data="add_product")],
            [InlineKeyboardButton("📋 Список товарів", callback_data="list_products")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("📦 Управління товарами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "💰 Зарплата":
        salary_info = "💰 Розрахунок зарплати (квітень 2026):\n\n"
        for email, user_data in USERS_DB.items():
            user_sales = sum(float(s.get("Цена USD", 0)) * int(s.get("Количество", 1)) 
                           for s in SALES_DB if s.get("Продавец", "") == user_data["name"])
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
        total_revenue = sum(float(s.get("Цена USD", 0)) * int(s.get("Количество", 1)) for s in SALES_DB)
        
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
            [InlineKeyboardButton("🔄 Оновити дані", callback_data="refresh_data")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("⚙️ Налаштування:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return MENU

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_menu":
        await query.message.reply_text("Оберіть дію:", reply_markup=get_main_menu_keyboard())
    
    elif query.data == "list_customers":
        reload_customers()
        customers_text = "👥 Список клієнтів:\n\n"
        if CUSTOMERS_DB:
            for customer in CUSTOMERS_DB:
                name = customer.get("Имя", "N/A")
                email = customer.get("Email", "N/A")
                phone = customer.get("Телефон", "N/A")
                city = customer.get("Город", "N/A")
                customers_text += f"👤 {name}\n  Email: {email}\n  Телефон: {phone}\n  Місто: {city}\n\n"
        else:
            customers_text = "👥 Клієнтів немає"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(customers_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "add_customer":
        await query.edit_message_text("Введіть ім'я клієнта:")
        return ADD_CUSTOMER_NAME
    
    elif query.data == "list_products":
        reload_products()
        products_text = "📦 Список товарів:\n\n"
        if PRODUCTS_DB:
            for product in PRODUCTS_DB:
                name = product.get("Название", "N/A")
                price = product.get("Цена USD", 0)
                stock = product.get("Запас", 0)
                products_text += f"📦 {name}\n  Ціна: ${price}\n  Запас: {stock} шт.\n\n"
        else:
            products_text = "📦 Товарів немає"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(products_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "add_product":
        await query.edit_message_text("Введіть назву товара:")
        return ADD_PRODUCT_NAME
    
    elif query.data == "add_sale":
        reload_products()
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
            profile_text = f"👤 Мій профіль:\n\nІм'я: {user_data['name']}\nEmail: {user_email}\nПосада: {user_data['role']}\nОклад: ${user_data['salary_base']}\nКомісія: {user_data['commission']}%"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "refresh_data":
        reload_customers()
        reload_products()
        reload_sales()
        await query.edit_message_text("✅ Дані оновлені з Google Sheets!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]))
    
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
            return ADD_SALE_QUANTITY
    
    return MENU

async def add_customer_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання імені клієнта"""
    context.user_data["customer_name"] = update.message.text
    await update.message.reply_text("Введіть email клієнта:")
    return ADD_CUSTOMER_EMAIL

async def add_customer_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання email клієнта"""
    context.user_data["customer_email"] = update.message.text
    await update.message.reply_text("Введіть телефон клієнта:")
    return ADD_CUSTOMER_PHONE

async def add_customer_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання телефону клієнта"""
    context.user_data["customer_phone"] = update.message.text
    await update.message.reply_text("Введіть місто клієнта:")
    return ADD_CUSTOMER_CITY

async def add_customer_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання міста клієнта і збереження"""
    customer_id = f"C{len(CUSTOMERS_DB) + 1:03d}"
    customer = {
        "ID": customer_id,
        "Имя": context.user_data["customer_name"],
        "Email": context.user_data["customer_email"],
        "Телефон": context.user_data["customer_phone"],
        "Город": update.message.text,
        "Дата добавления": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Додаємо в локальну БД
    CUSTOMERS_DB.append(customer)
    
    # Записуємо в Google Sheets
    if sheets_manager:
        sheets_manager.add_customer(
            customer_id,
            customer["Имя"],
            customer["Email"],
            customer["Телефон"],
            customer["Город"]
        )
    
    await update.message.reply_text(
        f"✅ Клієнт додан!\n\n"
        f"Ім'я: {customer['Имя']}\n"
        f"Email: {customer['Email']}\n"
        f"Телефон: {customer['Телефон']}\n"
        f"Місто: {customer['Город']}",
        reply_markup=get_main_menu_keyboard()
    )
    return MENU

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання назви товара"""
    context.user_data["product_name"] = update.message.text
    await update.message.reply_text("Введіть ціну товара (USD):")
    return ADD_PRODUCT_PRICE_USD

async def add_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання ціни товара"""
    try:
        context.user_data["product_price"] = float(update.message.text)
        await update.message.reply_text("Введіть запас товара (кількість):")
        return ADD_PRODUCT_STOCK
    except ValueError:
        await update.message.reply_text("❌ Невірна ціна. Введіть число:")
        return ADD_PRODUCT_PRICE_USD

async def add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання запасу товара і збереження"""
    try:
        product_id = f"P{len(PRODUCTS_DB) + 1:03d}"
        product = {
            "ID": product_id,
            "Название": context.user_data["product_name"],
            "Цена USD": context.user_data["product_price"],
            "Цена UAH": context.user_data["product_price"] * 40,  # Примерно
            "Запас": int(update.message.text),
            "Минимум": 5,
            "Статус": "✅ OK"
        }
        
        # Додаємо в локальну БД
        PRODUCTS_DB.append(product)
        
        # Записуємо в Google Sheets (якщо є функція)
        if sheets_manager:
            # Додаємо товар в таблицю
            worksheet = sheets_manager.get_worksheet("Товары")
            if worksheet:
                row = [
                    product["ID"],
                    product["Название"],
                    product["Цена USD"],
                    product["Цена UAH"],
                    product["Запас"],
                    product["Минимум"],
                    product["Статус"]
                ]
                worksheet.append_row(row)
        
        await update.message.reply_text(
            f"✅ Товар додан!\n\n"
            f"Назва: {product['Название']}\n"
            f"Ціна: ${product['Цена USD']}\n"
            f"Запас: {product['Запас']} шт.",
            reply_markup=get_main_menu_keyboard()
        )
        return MENU
    except ValueError:
        await update.message.reply_text("❌ Невірна кількість. Введіть число:")
        return ADD_PRODUCT_STOCK

async def add_sale_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримання кількості для продажу і збереження"""
    try:
        product = context.user_data["selected_product"]
        quantity = int(update.message.text)
        
        sale_id = f"S{len(SALES_DB) + 1:03d}"
        sale = {
            "ID": sale_id,
            "Дата": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Товар": product.get("Название", "N/A"),
            "Количество": quantity,
            "Цена USD": product.get("Цена USD", 0),
            "Продавец": "Давид Джонсон",
            "Статус": "✅ Завершено"
        }
        
        # Додаємо в локальну БД
        SALES_DB.append(sale)
        
        # Записуємо в Google Sheets
        if sheets_manager:
            sheets_manager.add_sale(
                sale_id,
                sale["Товар"],
                quantity,
                sale["Цена USD"],
                sale["Продавец"]
            )
        
        await update.message.reply_text(
            f"✅ Продаж додана!\n\n"
            f"Товар: {sale['Товар']}\n"
            f"Кількість: {quantity}\n"
            f"Сума: ${sale['Цена USD'] * quantity}",
            reply_markup=get_main_menu_keyboard()
        )
        return MENU
    except ValueError:
        await update.message.reply_text("❌ Невірна кількість. Введіть число:")
        return ADD_SALE_QUANTITY

def reload_customers():
    """Перезавантажити клієнтів з Google Sheets"""
    global CUSTOMERS_DB
    if sheets_manager:
        CUSTOMERS_DB = sheets_manager.get_customers()

def reload_products():
    """Перезавантажити товари з Google Sheets"""
    global PRODUCTS_DB
    if sheets_manager:
        PRODUCTS_DB = sheets_manager.get_products()

def reload_sales():
    """Перезавантажити продажі з Google Sheets"""
    global SALES_DB
    if sheets_manager:
        SALES_DB = sheets_manager.get_sales()

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
            reload_customers()
            reload_products()
            reload_sales()
        else:
            logger.warning("⚠️ GOOGLE_SHEETS_CREDENTIALS не встановлено")
    except Exception as e:
        logger.error(f"❌ Ошибка при ініціалізації Google Sheets: {e}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler для додавання клієнта
    conv_handler_customer = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^add_customer$")],
        states={
            ADD_CUSTOMER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_customer_name)],
            ADD_CUSTOMER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_customer_email)],
            ADD_CUSTOMER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_customer_phone)],
            ADD_CUSTOMER_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_customer_city)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Conversation handler для додавання товара
    conv_handler_product = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^add_product$")],
        states={
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)],
            ADD_PRODUCT_PRICE_USD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_price)],
            ADD_PRODUCT_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_stock)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Conversation handler для додавання продажи
    conv_handler_sale = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^add_sale$")],
        states={
            ADD_SALE_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_sale_quantity)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    # Обробники команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler_customer)
    application.add_handler(conv_handler_product)
    application.add_handler(conv_handler_sale)
    
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

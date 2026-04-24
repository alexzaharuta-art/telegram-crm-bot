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
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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

# Константи
BOT_TOKEN = os.getenv("BOT_TOKEN", "8747572018:AAFEFoum-bcnSCCTuEwJkKBow9tR0DfcIc0")
PORT = int(os.getenv("PORT", 8000))
WEBHOOK_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "1D7jcMc-xDzdd1r5rFYlsNrYeSblwmK-HDgvjIstOsK4")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")

# Дані
USERS_DB = {
    "david@company.com": {"name": "Давид Джонсон", "role": "менеджер", "salary_base": 500, "commission": 5},
    "sarah@company.com": {"name": "Сара Уільямс", "role": "керівник", "salary_base": 800, "commission": 3},
    "michael@company.com": {"name": "Майкл Браун", "role": "менеджер", "salary_base": 400, "commission": 5},
    "anna@company.com": {"name": "Анна Смирнова", "role": "менеджер", "salary_base": 450, "commission": 4},
}

CUSTOMERS_DB = []
PRODUCTS_DB = []
SALES_DB = []

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привіт, {user.first_name}!\n\n"
        f"Ласкаво просимо до RetailCRM 🏪\n\n"
        f"Оберіть дію:",
        reply_markup=get_main_menu_keyboard()
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка вибору з меню"""
    text = update.message.text
    
    if text == "👥 Клієнти":
        keyboard = [
            [InlineKeyboardButton("➕ Додати клієнта", callback_data="add_customer_form")],
            [InlineKeyboardButton("📋 Список клієнтів", callback_data="list_customers")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("👥 Управління клієнтами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "🛍️ Продажі":
        keyboard = [
            [InlineKeyboardButton("➕ Нова продаж", callback_data="add_sale_form")],
            [InlineKeyboardButton("📊 Мої продажі", callback_data="my_sales")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("🛍️ Управління продажами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "📦 Товари":
        keyboard = [
            [InlineKeyboardButton("➕ Додати товар", callback_data="add_product_form")],
            [InlineKeyboardButton("📋 Список товарів", callback_data="list_products")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("📦 Управління товарами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "💰 Зарплата":
        reload_sales()
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
        reload_sales()
        reload_customers()
        reload_products()
        
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_menu":
        await query.message.reply_text("Оберіть дію:", reply_markup=get_main_menu_keyboard())
    
    elif query.data == "add_customer_form":
        await query.edit_message_text(
            "📝 Введіть дані клієнта в форматі:\n\n"
            "<b>Ім'я | Email | Телефон | Місто</b>\n\n"
            "Приклад:\n"
            "Іван Петров | ivan@example.com | +380-50-1234567 | Київ"
        )
        context.user_data["waiting_for"] = "customer"
    
    elif query.data == "add_product_form":
        await query.edit_message_text(
            "📝 Введіть дані товара в форматі:\n\n"
            "<b>Назва | Ціна USD | Запас</b>\n\n"
            "Приклад:\n"
            "iPhone 16 Pro | 1280 | 10"
        )
        context.user_data["waiting_for"] = "product"
    
    elif query.data == "add_sale_form":
        reload_products()
        if not PRODUCTS_DB:
            await query.edit_message_text("❌ Товарів немає. Спочатку додайте товари!")
            return
        
        products_text = "🛍️ Оберіть товар:\n\n"
        keyboard = []
        for i, product in enumerate(PRODUCTS_DB):
            name = product.get("Название", "N/A")
            price = product.get("Цена USD", 0)
            products_text += f"{i+1}. {name} - ${price}\n"
            keyboard.append([InlineKeyboardButton(f"{i+1}. {name}", callback_data=f"select_product_{i}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_menu")])
        await query.edit_message_text(products_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("select_product_"):
        product_idx = int(query.data.split("_")[2])
        if product_idx < len(PRODUCTS_DB):
            product = PRODUCTS_DB[product_idx]
            await query.edit_message_text(
                f"📝 Введіть кількість для товара:\n\n"
                f"<b>{product.get('Название', 'N/A')}</b>\n"
                f"Ціна: ${product.get('Цена USD', 0)}"
            )
            context.user_data["waiting_for"] = "sale_quantity"
            context.user_data["selected_product_idx"] = product_idx
    
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

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробка текстового вводу для форм"""
    text = update.message.text
    
    waiting_for = context.user_data.get("waiting_for")
    
    if waiting_for == "customer":
        try:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) != 4:
                await update.message.reply_text("❌ Невірний формат! Використовуйте: Ім'я | Email | Телефон | Місто")
                return
            
            name, email, phone, city = parts
            customer_id = f"C{len(CUSTOMERS_DB) + 1:03d}"
            
            # Записуємо в Google Sheets
            if sheets_manager:
                sheets_manager.add_customer(customer_id, name, email, phone, city)
                logger.info(f"✅ Клієнт додан: {name}")
            
            # Перезавантажуємо дані
            reload_customers()
            
            await update.message.reply_text(
                f"✅ Клієнт додан!\n\n"
                f"Ім'я: {name}\n"
                f"Email: {email}\n"
                f"Телефон: {phone}\n"
                f"Місто: {city}",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data["waiting_for"] = None
        except Exception as e:
            logger.error(f"Error adding customer: {e}")
            await update.message.reply_text(f"❌ Помилка: {str(e)}")
    
    elif waiting_for == "product":
        try:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) != 3:
                await update.message.reply_text("❌ Невірний формат! Використовуйте: Назва | Ціна USD | Запас")
                return
            
            name, price_str, stock_str = parts
            price = float(price_str)
            stock = int(stock_str)
            product_id = f"P{len(PRODUCTS_DB) + 1:03d}"
            
            # Записуємо в Google Sheets
            if sheets_manager:
                worksheet = sheets_manager.get_worksheet("Товары")
                if worksheet:
                    row = [product_id, name, price, price * 40, stock, 5, "✅ OK"]
                    worksheet.append_row(row)
                    logger.info(f"✅ Товар додан: {name}")
            
            # Перезавантажуємо дані
            reload_products()
            
            await update.message.reply_text(
                f"✅ Товар додан!\n\n"
                f"Назва: {name}\n"
                f"Ціна: ${price}\n"
                f"Запас: {stock} шт.",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data["waiting_for"] = None
        except Exception as e:
            logger.error(f"Error adding product: {e}")
            await update.message.reply_text(f"❌ Помилка: {str(e)}")
    
    elif waiting_for == "sale_quantity":
        try:
            quantity = int(text)
            product_idx = context.user_data.get("selected_product_idx")
            
            if product_idx is None or product_idx >= len(PRODUCTS_DB):
                await update.message.reply_text("❌ Товар не знайдений!")
                return
            
            product = PRODUCTS_DB[product_idx]
            sale_id = f"S{len(SALES_DB) + 1:03d}"
            
            # Записуємо в Google Sheets
            if sheets_manager:
                sheets_manager.add_sale(
                    sale_id,
                    product.get("Название", "N/A"),
                    quantity,
                    product.get("Цена USD", 0),
                    "Давид Джонсон"
                )
                logger.info(f"✅ Продаж додана: {product.get('Название', 'N/A')} x{quantity}")
            
            # Перезавантажуємо дані
            reload_sales()
            
            await update.message.reply_text(
                f"✅ Продаж додана!\n\n"
                f"Товар: {product.get('Название', 'N/A')}\n"
                f"Кількість: {quantity}\n"
                f"Сума: ${product.get('Цена USD', 0) * quantity}",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data["waiting_for"] = None
        except ValueError:
            await update.message.reply_text("❌ Введіть число!")
        except Exception as e:
            logger.error(f"Error adding sale: {e}")
            await update.message.reply_text(f"❌ Помилка: {str(e)}")

def reload_customers():
    """Перезавантажити клієнтів з Google Sheets"""
    global CUSTOMERS_DB
    if sheets_manager:
        try:
            CUSTOMERS_DB = sheets_manager.get_customers()
        except Exception as e:
            logger.error(f"Error reloading customers: {e}")

def reload_products():
    """Перезавантажити товари з Google Sheets"""
    global PRODUCTS_DB
    if sheets_manager:
        try:
            PRODUCTS_DB = sheets_manager.get_products()
        except Exception as e:
            logger.error(f"Error reloading products: {e}")

def reload_sales():
    """Перезавантажити продажі з Google Sheets"""
    global SALES_DB
    if sheets_manager:
        try:
            SALES_DB = sheets_manager.get_sales()
        except Exception as e:
            logger.error(f"Error reloading sales: {e}")

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
    
    # Обробники команд
    application.add_handler(CommandHandler("start", start))
    
    # Обробник текстових повідомлень
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    # Обробник кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обробник меню
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
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

#!/usr/bin/env python3
"""
RetailCRM Telegram Bot - Українська версія
Повнофункціональна CRM система з двосторонньою синхронізацією Google Sheets
Синхронізація з усіма вкладками: Клієнти, Товари, Продажі, Склад, Зарплата, Звіти
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

# FastAPI app
app = FastAPI()
application = None
sheets_manager = None

# Кеш для даних
cache = {
    "customers": [],
    "products": [],
    "sales": [],
    "employees": [],
    "last_update": None
}

def get_main_menu_keyboard():
    """Повертає клавіатуру головного меню"""
    keyboard = [
        [KeyboardButton("👥 Клієнти"), KeyboardButton("🛍️ Продажі")],
        [KeyboardButton("📦 Товари"), KeyboardButton("💰 Зарплата")],
        [KeyboardButton("📊 Звіти"), KeyboardButton("⚙️ Налаштування")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def reload_all_data():
    """Перезавантажити всі дані з Google Sheets"""
    global sheets_manager, cache
    if sheets_manager:
        try:
            cache["customers"] = sheets_manager.get_customers()
            cache["products"] = sheets_manager.get_products()
            cache["sales"] = sheets_manager.get_sales()
            cache["employees"] = sheets_manager.get_employees()
            cache["last_update"] = datetime.now()
            logger.info(f"✅ Дані оновлені: {len(cache['customers'])} клієнтів, {len(cache['products'])} товарів, {len(cache['sales'])} продаж")
        except Exception as e:
            logger.error(f"❌ Помилка при оновленні даних: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    user = update.effective_user
    reload_all_data()
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
        reload_all_data()
        salary_info = "💰 Розрахунок зарплати (квітень 2026):\n\n"
        
        for employee in cache["employees"]:
            name = employee.get("Имя", "N/A")
            salary_base = float(employee.get("Оклад", 0))
            commission_percent = float(employee.get("Комиссия", 0))
            
            # Рахуємо комісію з продаж цього працівника
            employee_sales = [s for s in cache["sales"] if s.get("Продавец", "") == name]
            commission = sum(float(s.get("Сумма", 0)) * commission_percent / 100 for s in employee_sales)
            total = salary_base + commission
            
            salary_info += f"👤 {name}\n"
            salary_info += f"  Оклад: ${salary_base}\n"
            salary_info += f"  Комісія ({commission_percent}%): ${commission:.2f}\n"
            salary_info += f"  Всього: ${total:.2f}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await update.message.reply_text(salary_info, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "📊 Звіти":
        reload_all_data()
        
        total_sales = len(cache["sales"])
        total_revenue = sum(float(s.get("Сумма", 0)) for s in cache["sales"])
        total_stock = sum(int(p.get("Запас", 0)) for p in cache["products"])
        
        report = f"📊 Звіти:\n\n"
        report += f"📈 Всього продаж: {total_sales}\n"
        report += f"💵 Загальний дохід: ${total_revenue:.2f}\n"
        report += f"👥 Активних клієнтів: {len(cache['customers'])}\n"
        report += f"📦 Товарів на складі: {total_stock} шт.\n"
        report += f"👨‍💼 Сотрудників: {len(cache['employees'])}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await update.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "⚙️ Налаштування":
        keyboard = [
            [InlineKeyboardButton("🔄 Оновити дані", callback_data="refresh_data")],
            [InlineKeyboardButton("👤 Мій профіль", callback_data="profile")],
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
        reload_all_data()
        if not cache["products"]:
            await query.edit_message_text("❌ Товарів немає. Спочатку додайте товари!")
            return
        
        products_text = "🛍️ Оберіть товар:\n\n"
        keyboard = []
        for i, product in enumerate(cache["products"]):
            name = product.get("Название", "N/A")
            price = product.get("Цена USD", 0)
            products_text += f"{i+1}. {name} - ${price}\n"
            keyboard.append([InlineKeyboardButton(f"{i+1}. {name}", callback_data=f"select_product_{i}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_menu")])
        await query.edit_message_text(products_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data.startswith("select_product_"):
        product_idx = int(query.data.split("_")[2])
        if product_idx < len(cache["products"]):
            product = cache["products"][product_idx]
            await query.edit_message_text(
                f"📝 Введіть кількість для товара:\n\n"
                f"<b>{product.get('Название', 'N/A')}</b>\n"
                f"Ціна: ${product.get('Цена USD', 0)}"
            )
            context.user_data["waiting_for"] = "sale_quantity"
            context.user_data["selected_product_idx"] = product_idx
    
    elif query.data == "list_customers":
        reload_all_data()
        customers_text = "👥 Список клієнтів:\n\n"
        if cache["customers"]:
            for customer in cache["customers"]:
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
        reload_all_data()
        products_text = "📦 Список товарів:\n\n"
        if cache["products"]:
            for product in cache["products"]:
                name = product.get("Название", "N/A")
                price = product.get("Цена USD", 0)
                stock = product.get("Запас", 0)
                products_text += f"📦 {name}\n  Ціна: ${price}\n  Запас: {stock} шт.\n\n"
        else:
            products_text = "📦 Товарів немає"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(products_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "refresh_data":
        reload_all_data()
        await query.edit_message_text("✅ Дані оновлені з Google Sheets!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]))
    
    elif query.data == "profile":
        user_email = "david@company.com"
        profile_text = f"👤 Мій профіль:\n\nEmail: {user_email}\nПосада: менеджер\nОклад: $500\nКомісія: 5%"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "my_sales":
        reload_all_data()
        my_sales_text = "🛍️ Мої продажі:\n\n"
        user_sales = [s for s in cache["sales"] if s.get("Продавец", "") == "Давид Джонсон"]
        if user_sales:
            for sale in user_sales:
                product = sale.get("Название", "N/A")
                quantity = sale.get("Количество", 0)
                amount = sale.get("Сумма", 0)
                my_sales_text += f"🛍️ {product}\n  Кількість: {quantity}\n  Сума: ${amount}\n\n"
        else:
            my_sales_text = "🛍️ Продаж немає"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(my_sales_text, reply_markup=InlineKeyboardMarkup(keyboard))

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
            customer_id = f"C{len(cache['customers']) + 1:03d}"
            
            # Записуємо в Google Sheets
            if sheets_manager:
                sheets_manager.add_customer(customer_id, name, email, phone, city)
                logger.info(f"✅ Клієнт додан: {name}")
            
            # Перезавантажуємо дані
            reload_all_data()
            
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
            product_id = f"P{len(cache['products']) + 1:03d}"
            
            # Записуємо в Google Sheets
            if sheets_manager:
                worksheet = sheets_manager.get_worksheet("Товары")
                if worksheet:
                    row = [product_id, name, price, price * 40, stock, 5, "✅ OK"]
                    worksheet.append_row(row)
                    logger.info(f"✅ Товар додан: {name}")
            
            # Перезавантажуємо дані
            reload_all_data()
            
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
            
            if product_idx is None or product_idx >= len(cache["products"]):
                await update.message.reply_text("❌ Товар не знайдений!")
                return
            
            product = cache["products"][product_idx]
            sale_id = f"S{len(cache['sales']) + 1:03d}"
            
            # Записуємо в Google Sheets
            if sheets_manager:
                sheets_manager.add_sale(
                    sale_id,
                    product.get("Название", "N/A"),
                    quantity,
                    float(product.get("Цена USD", 0)),
                    "Давид Джонсон"
                )
                logger.info(f"✅ Продаж додана: {product.get('Название', 'N/A')} x{quantity}")
            
            # Перезавантажуємо дані
            reload_all_data()
            
            await update.message.reply_text(
                f"✅ Продаж додана!\n\n"
                f"Товар: {product.get('Название', 'N/A')}\n"
                f"Кількість: {quantity}\n"
                f"Сума: ${float(product.get('Цена USD', 0)) * quantity}",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data["waiting_for"] = None
        except ValueError:
            await update.message.reply_text("❌ Введіть число!")
        except Exception as e:
            logger.error(f"Error adding sale: {e}")
            await update.message.reply_text(f"❌ Помилка: {str(e)}")

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
    return {
        "status": "ok",
        "bot": "running",
        "sheets": "connected" if sheets_manager else "disconnected",
        "cache": {
            "customers": len(cache["customers"]),
            "products": len(cache["products"]),
            "sales": len(cache["sales"]),
            "employees": len(cache["employees"])
        }
    }

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
            reload_all_data()
        else:
            logger.warning("⚠️ GOOGLE_SHEETS_CREDENTIALS не встановлено")
    except Exception as e:
        logger.error(f"❌ Ошибка при ініціалізації Google Sheets: {e}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обробники команд
    application.add_handler(CommandHandler("start", start))
    
    # Обробник текстових повідомлень для форм
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

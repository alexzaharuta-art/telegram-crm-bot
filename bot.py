#!/usr/bin/env python3
"""
RetailCRM Telegram Bot - Русская версия
Полнофункциональная CRM система с двусторонней синхронизацией Google Sheets
Синхронизация со всеми вкладками: Клиенты, Товары, Продажи, Сотрудники, Зарплата, Отчеты
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

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
BOT_TOKEN = os.getenv("BOT_TOKEN", "8747572018:AAFEFoum-bcnSCCTuEwJkKBow9tR0DfcIc0")
PORT = int(os.getenv("PORT", 8000))
WEBHOOK_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "1D7jcMc-xDzdd1r5rFYlsNrYeSblwmK-HDgvjIstOsK4")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")

# FastAPI app
app = FastAPI()
application = None
sheets_manager = None

# Кеш для данных
cache = {
    "customers": [],
    "products": [],
    "sales": [],
    "employees": [],
    "last_update": None
}

def get_main_menu_keyboard():
    """Возвращает клавиатуру главного меню"""
    keyboard = [
        [KeyboardButton("👥 Клиенты"), KeyboardButton("🛍️ Продажи")],
        [KeyboardButton("📦 Товары"), KeyboardButton("💰 Зарплата")],
        [KeyboardButton("📊 Отчеты"), KeyboardButton("⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def reload_all_data():
    """Перезагрузить все данные из Google Sheets"""
    global sheets_manager, cache
    if sheets_manager:
        try:
            cache["customers"] = sheets_manager.get_customers()
            cache["products"] = sheets_manager.get_products()
            cache["sales"] = sheets_manager.get_sales()
            cache["employees"] = sheets_manager.get_employees()
            cache["last_update"] = datetime.now()
            logger.info(f"✅ Данные обновлены: {len(cache['customers'])} клиентов, {len(cache['products'])} товаров, {len(cache['sales'])} продаж")
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении данных: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start"""
    user = update.effective_user
    reload_all_data()
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"Добро пожаловать в RetailCRM 🏪\n\n"
        f"Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка выбора из меню"""
    text = update.message.text
    
    if text == "👥 Клиенты":
        keyboard = [
            [InlineKeyboardButton("➕ Добавить клиента", callback_data="add_customer_form")],
            [InlineKeyboardButton("📋 Список клиентов", callback_data="list_customers")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("👥 Управление клиентами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "🛍️ Продажи":
        keyboard = [
            [InlineKeyboardButton("➕ Новая продажа", callback_data="add_sale_form")],
            [InlineKeyboardButton("📊 Мои продажи", callback_data="my_sales")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("🛍️ Управление продажами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "📦 Товары":
        keyboard = [
            [InlineKeyboardButton("➕ Добавить товар", callback_data="add_product_form")],
            [InlineKeyboardButton("📋 Список товаров", callback_data="list_products")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("📦 Управление товарами:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "💰 Зарплата":
        reload_all_data()
        salary_info = "💰 Расчет зарплаты (апрель 2026):\n\n"
        
        for employee in cache["employees"]:
            name = employee.get("Имя", "N/A")
            salary_base = float(employee.get("Оклад", 0))
            commission_percent = float(employee.get("Комиссия", 0))
            
            # Считаем комиссию из продаж этого сотрудника
            employee_sales = [s for s in cache["sales"] if s.get("Продавец", "") == name]
            commission = sum(float(s.get("Сумма", 0)) * commission_percent / 100 for s in employee_sales)
            total = salary_base + commission
            
            salary_info += f"👤 {name}\n"
            salary_info += f"  Оклад: ${salary_base}\n"
            salary_info += f"  Комиссия ({commission_percent}%): ${commission:.2f}\n"
            salary_info += f"  Всего: ${total:.2f}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await update.message.reply_text(salary_info, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "📊 Отчеты":
        reload_all_data()
        
        total_sales = len(cache["sales"])
        total_revenue = sum(float(s.get("Сумма", 0)) for s in cache["sales"])
        total_stock = sum(int(p.get("На складе", 0)) for p in cache["products"])
        
        report = f"📊 Отчеты:\n\n"
        report += f"📈 Всего продаж: {total_sales}\n"
        report += f"💵 Общий доход: ${total_revenue:.2f}\n"
        report += f"👥 Активных клиентов: {len(cache['customers'])}\n"
        report += f"📦 Товаров на складе: {total_stock} шт.\n"
        report += f"👨‍💼 Сотрудников: {len(cache['employees'])}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await update.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "⚙️ Настройки":
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить данные", callback_data="refresh_data")],
            [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]
        ]
        await update.message.reply_text("⚙️ Настройки:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка кнопок"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_menu":
        await query.message.reply_text("Выберите действие:", reply_markup=get_main_menu_keyboard())
    
    elif query.data == "add_customer_form":
        await query.edit_message_text(
            "📝 Введите данные клиента в формате:\n\n"
            "<b>Имя | Email | Телефон | Город</b>\n\n"
            "Пример:\n"
            "Иван Петров | ivan@example.com | +380-50-1234567 | Киев"
        )
        context.user_data["waiting_for"] = "customer"
    
    elif query.data == "add_product_form":
        await query.edit_message_text(
            "📝 Введите данные товара в формате:\n\n"
            "<b>Название | Цена USD | Запас</b>\n\n"
            "Пример:\n"
            "iPhone 16 Pro | 1280 | 10"
        )
        context.user_data["waiting_for"] = "product"
    
    elif query.data == "add_sale_form":
        reload_all_data()
        if not cache["products"]:
            await query.edit_message_text("❌ Товаров нет. Сначала добавьте товары!")
            return
        
        products_text = "🛍️ Выберите товар:\n\n"
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
                f"📝 Введите количество для товара:\n\n"
                f"<b>{product.get('Название', 'N/A')}</b>\n"
                f"Цена: ${product.get('Цена USD', 0)}"
            )
            context.user_data["waiting_for"] = "sale_quantity"
            context.user_data["selected_product_idx"] = product_idx
    
    elif query.data == "list_customers":
        reload_all_data()
        customers_text = "👥 Список клиентов:\n\n"
        if cache["customers"]:
            for customer in cache["customers"]:
                name = customer.get("Имя", "N/A")
                email = customer.get("Email", "N/A")
                phone = customer.get("Телефон", "N/A")
                city = customer.get("Город", "N/A")
                customers_text += f"👤 {name}\n  Email: {email}\n  Телефон: {phone}\n  Город: {city}\n\n"
        else:
            customers_text = "👥 Клиентов нет"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(customers_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "list_products":
        reload_all_data()
        products_text = "📦 Список товаров:\n\n"
        if cache["products"]:
            for product in cache["products"]:
                name = product.get("Название", "N/A")
                price = product.get("Цена USD", 0)
                stock = product.get("На складе", 0)
                products_text += f"📦 {name}\n  Цена: ${price}\n  Запас: {stock} шт.\n\n"
        else:
            products_text = "📦 Товаров нет"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(products_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "refresh_data":
        reload_all_data()
        await query.edit_message_text("✅ Данные обновлены из Google Sheets!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]))
    
    elif query.data == "profile":
        user_email = "david@company.com"
        profile_text = f"👤 Мой профиль:\n\nEmail: {user_email}\nДолжность: менеджер\nОклад: $500\nКомиссия: 5%"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "my_sales":
        reload_all_data()
        my_sales_text = "🛍️ Мои продажи:\n\n"
        user_sales = [s for s in cache["sales"] if s.get("Продавец", "") == "Давид Джонсон"]
        if user_sales:
            for sale in user_sales:
                product = sale.get("Название", "N/A")
                quantity = sale.get("Количество", 0)
                amount = sale.get("Сумма", 0)
                my_sales_text += f"🛍️ {product}\n  Количество: {quantity}\n  Сумма: ${amount}\n\n"
        else:
            my_sales_text = "🛍️ Продаж нет"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_menu")]]
        await query.edit_message_text(my_sales_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текстового ввода для форм"""
    text = update.message.text
    
    waiting_for = context.user_data.get("waiting_for")
    
    if waiting_for == "customer":
        try:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) != 4:
                await update.message.reply_text("❌ Неверный формат! Используйте: Имя | Email | Телефон | Город")
                return
            
            name, email, phone, city = parts
            customer_id = f"C{len(cache['customers']) + 1:03d}"
            
            # Записываем в Google Sheets
            if sheets_manager:
                sheets_manager.add_customer(customer_id, name, email, phone, city)
                logger.info(f"✅ Клиент добавлен: {name}")
            
            # Перезагружаем данные
            reload_all_data()
            
            await update.message.reply_text(
                f"✅ Клиент добавлен!\n\n"
                f"Имя: {name}\n"
                f"Email: {email}\n"
                f"Телефон: {phone}\n"
                f"Город: {city}",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data["waiting_for"] = None
        except Exception as e:
            logger.error(f"Ошибка при добавлении клиента: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    elif waiting_for == "product":
        try:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) != 3:
                await update.message.reply_text("❌ Неверный формат! Используйте: Название | Цена USD | Запас")
                return
            
            name, price_str, stock_str = parts
            price_usd = float(price_str)
            stock = int(stock_str)
            product_id = f"P{len(cache['products']) + 1:03d}"
            price_uah = price_usd * 40  # Примерный курс USD -> UAH
            
            # Записываем в Google Sheets
            if sheets_manager:
                sheets_manager.add_product(product_id, name, price_usd, price_uah, stock)
                logger.info(f"✅ Товар добавлен: {name}")
            
            # Перезагружаем данные
            reload_all_data()
            
            await update.message.reply_text(
                f"✅ Товар добавлен!\n\n"
                f"Название: {name}\n"
                f"Цена: ${price_usd}\n"
                f"Запас: {stock} шт.",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data["waiting_for"] = None
        except Exception as e:
            logger.error(f"Ошибка при добавлении товара: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    elif waiting_for == "sale_quantity":
        try:
            quantity = int(text)
            product_idx = context.user_data.get("selected_product_idx")
            
            if product_idx is None or product_idx >= len(cache["products"]):
                await update.message.reply_text("❌ Товар не найден!")
                return
            
            product = cache["products"][product_idx]
            sale_id = f"S{len(cache['sales']) + 1:03d}"
            
            # Записываем в Google Sheets
            if sheets_manager:
                sheets_manager.add_sale(
                    sale_id,
                    product.get("Название", "N/A"),
                    quantity,
                    float(product.get("Цена USD", 0)),
                    "Давид Джонсон"
                )
                logger.info(f"✅ Продажа добавлена: {product.get('Название', 'N/A')} x{quantity}")
            
            # Перезагружаем данные
            reload_all_data()
            
            await update.message.reply_text(
                f"✅ Продажа добавлена!\n\n"
                f"Товар: {product.get('Название', 'N/A')}\n"
                f"Количество: {quantity}\n"
                f"Сумма: ${float(product.get('Цена USD', 0)) * quantity}",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data["waiting_for"] = None
        except ValueError:
            await update.message.reply_text("❌ Введите число!")
        except Exception as e:
            logger.error(f"Ошибка при добавлении продажи: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ошибок"""
    logger.error(msg="Исключение при обработке обновления:", exc_info=context.error)

@app.post("/webhook")
async def webhook(request: Request):
    """Webhook для получения обновлений от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")
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
    """Запуск бота при старте FastAPI"""
    global application, sheets_manager
    
    # Инициализируем Google Sheets
    try:
        if GOOGLE_SHEETS_CREDENTIALS:
            sheets_manager = init_sheets_manager(GOOGLE_SHEETS_ID, GOOGLE_SHEETS_CREDENTIALS)
            logger.info("✅ Google Sheets подключен")
            
            # Загружаем данные из Google Sheets
            reload_all_data()
        else:
            logger.warning("⚠️ GOOGLE_SHEETS_CREDENTIALS не установлено")
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации Google Sheets: {e}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    
    # Обработчик текстовых сообщений для форм
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    # Обработчик кнопок
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик меню
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск Application
    await application.initialize()
    await application.start()
    
    # Установка webhook или запуск polling
    if WEBHOOK_URL:
        webhook_url = f"https://{WEBHOOK_URL}/webhook"
        await application.bot.set_webhook(webhook_url)
        logger.info(f"✅ Webhook установлен: {webhook_url}")
    else:
        logger.info("⚠️ RAILWAY_PUBLIC_DOMAIN не установлено, используем polling")
        asyncio.create_task(application.updater.start_polling(allowed_updates=Update.ALL_TYPES))
    
    logger.info("🤖 RetailCRM Telegram Bot запущен!")

@app.on_event("shutdown")
async def shutdown():
    """Остановка бота при завершении FastAPI"""
    global application
    if application:
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

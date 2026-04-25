from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline, UserStatusOffline
import os
import asyncio

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# Переменные окружения (Railway)
API_HASH = os.environ.get('API_HASH')
API_ID = int(os.environ.get('API_ID'))
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Запуск бота
bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Хранилище: {chat_id: {'contacts': [Contact], 'running': bool, 'delay': int}}
data = {}

class Contact:
    def __init__(self, user_id, name, username=''):
        self.user_id = user_id
        self.name = name
        self.username = username
        self.last_status = None

    def __str__(self):
        return f'{self.name}: {self.username or self.user_id}'

print('✅ Бот запущен!')

# ============ КОМАНДЫ ============

@bot.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    await event.respond('👋 Бот для отслеживания онлайн статуса!\n\nКоманды:\n/add @username Имя\n/start_monitor - запуск\n/stop_monitor - остановка\n/status - проверить статус\n/debug - диагностика\n/help - все команды')

@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.respond("""
📋 КОМАНДЫ:

/add @username Имя - добавить пользователя
/list - показать список
/remove 1 - удалить по номеру
/clear - очистить список

/start_monitor - запустить мониторинг
/stop_monitor - остановить мониторинг
/setdelay 30 - задержка в секундах

/status - проверить статус сейчас
/debug - диагностика проблемы
/logs - показать логи
    """)

@bot.on(events.NewMessage(pattern='/add'))
async def add_user(event):
    message = event.message
    parts = message.message.split(maxsplit=2)
    
    if len(parts) < 3:
        await event.respond('❌ Использование: /add @username Имя')
        return
    
    identifier = parts[1]
    name = parts[2]
    chat_id = message.chat_id
    
    temp = TelegramClient(f'temp_{chat_id}', API_ID, API_HASH)
    await temp.start(bot_token=BOT_TOKEN)
    
    try:
        entity = await temp.get_entity(identifier)
        
        if chat_id not in data:
            data[chat_id] = {'contacts': [], 'running': False, 'delay': 30}
        
        contact = Contact(entity.id, name, identifier)
        data[chat_id]['contacts'].append(contact)
        
        status_text = "неизвестно"
        if isinstance(entity.status, UserStatusOnline):
            status_text = "🟢 В сети"
        elif isinstance(entity.status, UserStatusOffline):
            status_text = "⚫ Не в сети"
            
        await event.respond(f'✅ Добавлен: {name}\n📊 Статус: {status_text}')
        
    except Exception as e:
        await event.respond(f'❌ Ошибка: {str(e)[:150]}\n\n👉 Сделайте так:\n1. Второй аккаунт пишет боту "привет"\n2. /add @username Имя')
    finally:
        await temp.disconnect()

@bot.on(events.NewMessage(pattern='/list'))
async def list_users(event):
    chat_id = event.chat_id
    
    if chat_id not in data or not data[chat_id].get('contacts'):
        await event.respond('📭 Список пуст. Добавьте /add @username Имя')
        return
    
    response = "📋 СПИСОК ПОЛЬЗОВАТЕЛЕЙ:\n\n"
    for i, c in enumerate(data[chat_id]['contacts']):
        response += f"{i}. {c.name} - {c.username or c.user_id}\n"
    
    await event.respond(response)

@bot.on(events.NewMessage(pattern='/remove'))
async def remove_user(event):
    parts = event.message.message.split()
    if len(parts) < 2:
        await event.respond('❌ /remove 1 (номер из /list)')
        return
    
    try:
        index = int(parts[1])
        chat_id = event.chat_id
        
        if chat_id in data and data[chat_id].get('contacts') and 0 <= index < len(data[chat_id]['contacts']):
            removed = data[chat_id]['contacts'].pop(index)
            await event.respond(f'✅ Удален: {removed.name}')
        else:
            await event.respond('❌ Неверный номер')
    except:
        await event.respond('❌ Ошибка')

@bot.on(events.NewMessage(pattern='/clear'))
async def clear_users(event):
    chat_id = event.chat_id
    if chat_id in data:
        data[chat_id]['contacts'] = []
    await event.respond('🗑️ Список очищен')

@bot.on(events.NewMessage(pattern='/setdelay'))
async def set_delay(event):
    parts = event.message.message.split()
    if len(parts) < 2:
        await event.respond('❌ /setdelay 30')
        return
    
    try:
        delay = int(parts[1])
        if delay < 5:
            await event.respond('⚠️ Минимум 5 секунд')
            return
        
        chat_id = event.chat_id
        if chat_id not in data:
            data[chat_id] = {'contacts': [], 'running': False, 'delay': delay}
        else:
            data[chat_id]['delay'] = delay
        
        await event.respond(f'⏱️ Задержка: {delay} сек')
    except:
        await event.respond('❌ Введите число')

@bot.on(events.NewMessage(pattern='/status'))
async def check_status(event):
    chat_id = event.chat_id
    
    if chat_id not in data or not data[chat_id].get('contacts'):
        await event.respond('📭 Нет пользователей')
        return
    
    temp = TelegramClient(f'status_{chat_id}', API_ID, API_HASH)
    await temp.start(bot_token=BOT_TOKEN)
    
    response = "📊 ТЕКУЩИЙ СТАТУС:\n\n"
    
    for contact in data[chat_id]['contacts']:
        try:
            entity = await temp.get_entity(contact.user_id)
            if isinstance(entity.status, UserStatusOnline):
                response += f"🟢 {contact.name} - В СЕТИ ПРЯМО СЕЙЧАС!\n"
            elif isinstance(entity.status, UserStatusOffline):
                response += f"⚫ {contact.name} - Не в сети\n"
            else:
                response += f"⚠️ {contact.name} - Статус скрыт\n"
        except Exception as e:
            response += f"❌ {contact.name} - Ошибка\n"
    
    await temp.disconnect()
    await event.respond(response)

@bot.on(events.NewMessage(pattern='/debug'))
async def debug(event):
    chat_id = event.chat_id
    
    if chat_id not in data or not data[chat_id].get('contacts'):
        await event.respond('❌ Нет пользователей. Сначала /add @username Имя')
        return
    
    temp = TelegramClient(f'debug_{chat_id}', API_ID, API_HASH)
    await temp.start(bot_token=BOT_TOKEN)
    
    msg = "🔍 ДИАГНОСТИКА:\n\n"
    
    for contact in data[chat_id]['contacts']:
        try:
            entity = await temp.get_entity(contact.user_id)
            status_type = type(entity.status).__name__
            msg += f"👤 {contact.name}\n"
            msg += f"   ID: {contact.user_id}\n"
            msg += f"   Статус в API: {status_type}\n"
            
            if status_type == 'UserStatusOnline':
                msg += f"   ✅ Бот ВИДИТ онлайн!\n"
            elif status_type == 'UserStatusOffline':
                msg += f"   ✅ Бот ВИДИТ оффлайн!\n"
            else:
                msg += f"   ⚠️ ПРОБЛЕМА: статус скрыт\n"
                msg += f"   РЕШЕНИЕ:\n"
                msg += f"   1. Второй аккаунт пишет боту\n"
                msg += f"   2. Добавить бота в контакты\n"
                msg += f"   3. Настройки → Last Seen → Everybody\n"
            msg += "\n"
        except Exception as e:
            msg += f"❌ {contact.name}: {str(e)[:80]}\n\n"
    
    msg += "\n💡 Если статус 'Recently/LastWeek' — значит приватность включена"
    
    await temp.disconnect()
    await event.respond(msg)

@bot.on(events.NewMessage(pattern='/start_monitor'))
async def start_monitor(event):
    chat_id = event.chat_id
    
    if chat_id not in data or not data[chat_id].get('contacts'):
        await event.respond('❌ Сначала добавьте /add @username Имя')
        return
    
    if data[chat_id].get('running'):
        await event.respond('⚠️ Мониторинг уже запущен')
        return
    
    data[chat_id]['running'] = True
    delay = data[chat_id].get('delay', 30)
    
    await event.respond(f'🟢 МОНИТОРИНГ ЗАПУЩЕН\n📊 Проверка каждые {delay} сек\n\n✅ ПРОВЕРЬТЕ:\n1. Второй аккаунт написал боту?\n2. Бот в контактах второго аккаунта?\n3. Настройки приватности: Last Seen → Everybody\n\n🔍 Используйте /status для проверки')
    
    asyncio.create_task(monitor_loop(chat_id))

async def monitor_loop(chat_id):
    temp = TelegramClient(f'monitor_{chat_id}', API_ID, API_HASH)
    await temp.start(bot_token=BOT_TOKEN)
    
    last_status = {}
    
    # Инициализация
    for contact in data[chat_id]['contacts']:
        try:
            entity = await temp.get_entity(contact.user_id)
            last_status[contact.user_id] = type(entity.status).__name__
        except:
            pass
    
    while data.get(chat_id, {}).get('running', False):
        try:
            for contact in data[chat_id]['contacts']:
                try:
                    entity = await temp.get_entity(contact.user_id)
                    current = type(entity.status).__name__
                    
                    if contact.user_id in last_status and last_status[contact.user_id] != current:
                        # Статус изменился!
                        if current == 'UserStatusOnline':
                            await bot.send_message(chat_id, f'🟢🟢🟢 {contact.name} ВОШЕЛ В СЕТЬ! 🟢🟢🟢')
                        elif current == 'UserStatusOffline':
                            await bot.send_message(chat_id, f'⚫⚫⚫ {contact.name} ВЫШЕЛ ИЗ СЕТИ! ⚫⚫⚫')
                        else:
                            await bot.send_message(chat_id, f'⚠️ {contact.name}: статус изменился на {current}')
                    
                    last_status[contact.user_id] = current
                    
                except Exception as e:
                    print(f"Ошибка {contact.name}: {e}")
            
            delay = data.get(chat_id, {}).get('delay', 30)
            await asyncio.sleep(delay)
            
        except Exception as e:
            print(f"Цикл упал: {e}")
            await asyncio.sleep(10)
    
    await temp.disconnect()

@bot.on(events.NewMessage(pattern='/stop_monitor'))
async def stop_monitor(event):
    chat_id = event.chat_id
    if chat_id in data:
        data[chat_id]['running'] = False
    await event.respond('🔴 МОНИТОРИНГ ОСТАНОВЛЕН')

@bot.on(events.NewMessage(pattern='/logs'))
async def show_logs(event):
    try:
        with open('spy_log.txt', 'r') as f:
            content = f.read()[-3000:]
            await event.respond(f'📄 ЛОГИ (последние 3000 символов):\n\n{content}')
    except:
        await event.respond('📭 Логи пусты')

@bot.on(events.NewMessage())
async def log_all(event):
    with open('spy_log.txt', 'a') as f:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        f.write(f'[{timestamp}] [{event.chat_id}]: {event.message.message}\n')

print('🚀 Бот готов! Команды: /start_monitor, /add, /debug, /status')
bot.run_until_disconnected()

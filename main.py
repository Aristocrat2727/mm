from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import UserStatusOnline, UserStatusOffline, UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth, UserStatusEmpty
from time import sleep
import collections
import os
import asyncio

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# Переменные окружения
API_HASH = os.environ.get('API_HASH')
API_ID = int(os.environ.get('API_ID'))
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Запуск бота
bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

data = {}

help_messages = [
    '/start - запустить мониторинг',
    '/stop - остановить мониторинг',
    '/help - показать помощь',
    '/add @username Имя - добавить пользователя',
    '/list - показать список',
    '/clear - очистить список',
    '/remove 1 - удалить по номеру',
    '/setdelay 30 - задержка в секундах',
    '/logs - показать логи',
    '/clearlogs - очистить логи',
    '/status - проверить статус сейчас'
]

print('✅ Бот запущен!')

class Contact:
    def __init__(self, user_id, name, username=''):
        self.user_id = user_id
        self.name = name
        self.username = username
        self.online = False
        self.last_change = None
        self.last_status = None
    
    def __str__(self):
        return f'{self.name}: {self.username or self.user_id}'

def format_time_diff(diff):
    """Форматирует timedelta в человеческий формат"""
    if not diff:
        return "только что"
    
    total_seconds = int(diff.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds} сек"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes} мин {seconds} сек"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours} ч {minutes} мин"

def get_status_text(status):
    """Переводит статус в читаемый текст"""
    if isinstance(status, UserStatusOnline):
        return "🟢 В сети"
    elif isinstance(status, UserStatusOffline):
        if status.was_online:
            diff = datetime.now().astimezone() - status.was_online
            return f"⚫ Был(а) {format_time_diff(diff)} назад"
        return "⚫ Не в сети"
    elif isinstance(status, UserStatusRecently):
        return "🟡 Был(а) недавно"
    elif isinstance(status, UserStatusLastWeek):
        return "🟡 Был(а) на этой неделе"
    elif isinstance(status, UserStatusLastMonth):
        return "🟡 Был(а) в этом месяце"
    else:
        return "⚪ Статус скрыт"

@bot.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    await event.respond('👋 Бот запущен!\nИспользуйте /help для списка команд')

@bot.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    await event.respond('\n'.join(help_messages))

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
    
    temp_client = TelegramClient(f'temp_{chat_id}', API_ID, API_HASH)
    await temp_client.start(bot_token=BOT_TOKEN)
    
    try:
        entity = await temp_client.get_entity(identifier)
        
        if chat_id not in data:
            data[chat_id] = {'contacts': [], 'is_running': False, 'delay': 30}
        
        if 'contacts' not in data[chat_id]:
            data[chat_id]['contacts'] = []
        
        contact = Contact(entity.id, name, identifier)
        data[chat_id]['contacts'].append(contact)
        
        status_text = get_status_text(entity.status)
        await event.respond(f'✅ Добавлен: {name}\n📊 Текущий статус: {status_text}')
        
    except Exception as e:
        await event.respond(f'❌ Ошибка: {str(e)[:200]}\n\nПопробуйте:\n1. @username\n2. Числовой ID\n3. Убедитесь что пользователь писал боту')
    finally:
        await temp_client.disconnect()

@bot.on(events.NewMessage(pattern='/list'))
async def list_users(event):
    chat_id = event.message.chat_id
    
    if chat_id not in data or 'contacts' not in data[chat_id] or not data[chat_id]['contacts']:
        await event.respond('📭 Список пуст. Добавьте пользователей через /add')
        return
    
    response = "📋 Список отслеживаемых:\n\n"
    for i, contact in enumerate(data[chat_id]['contacts']):
        response += f"{i}. {contact.name} - {contact.username or contact.user_id}\n"
    
    await event.respond(response)

@bot.on(events.NewMessage(pattern='/remove'))
async def remove_user(event):
    parts = event.message.message.split()
    
    if len(parts) < 2:
        await event.respond('❌ Использование: /remove 1 (номер из /list)')
        return
    
    try:
        index = int(parts[1])
        chat_id = event.message.chat_id
        
        if chat_id not in data or 'contacts' not in data[chat_id]:
            await event.respond('❌ Список пуст')
            return
        
        if 0 <= index < len(data[chat_id]['contacts']):
            removed = data[chat_id]['contacts'].pop(index)
            await event.respond(f'✅ Удален: {removed.name}')
        else:
            await event.respond('❌ Неверный номер')
    except ValueError:
        await event.respond('❌ Введите число')

@bot.on(events.NewMessage(pattern='/clear'))
async def clear_users(event):
    chat_id = event.message.chat_id
    if chat_id in data:
        data[chat_id]['contacts'] = []
    await event.respond('🗑️ Список очищен')

@bot.on(events.NewMessage(pattern='/setdelay'))
async def set_delay(event):
    parts = event.message.message.split()
    
    if len(parts) < 2:
        await event.respond('❌ Использование: /setdelay 30 (секунд)')
        return
    
    try:
        delay = int(parts[1])
        if delay < 5:
            await event.respond('⚠️ Минимальная задержка 5 секунд')
            return
        
        chat_id = event.message.chat_id
        if chat_id not in data:
            data[chat_id] = {'contacts': [], 'is_running': False, 'delay': delay}
        else:
            data[chat_id]['delay'] = delay
        
        await event.respond(f'⏱️ Задержка установлена: {delay} сек')
    except ValueError:
        await event.respond('❌ Введите число секунд')

@bot.on(events.NewMessage(pattern='/status'))
async def check_status(event):
    chat_id = event.message.chat_id
    
    if chat_id not in data or 'contacts' not in data[chat_id]:
        await event.respond('📭 Нет отслеживаемых пользователей')
        return
    
    temp_client = TelegramClient(f'status_{chat_id}', API_ID, API_HASH)
    await temp_client.start(bot_token=BOT_TOKEN)
    
    response = "📊 ТЕКУЩИЙ СТАТУС:\n\n"
    
    for contact in data[chat_id]['contacts']:
        try:
            entity = await temp_client.get_entity(contact.user_id)
            status_text = get_status_text(entity.status)
            response += f"👤 {contact.name}\n   {status_text}\n\n"
        except Exception as e:
            response += f"❌ {contact.name}: Ошибка доступа\n"
    
    await temp_client.disconnect()
    await event.respond(response)

@bot.on(events.NewMessage(pattern='/start_monitor'))
async def start_monitor(event):
    chat_id = event.message.chat_id
    
    if chat_id not in data:
        data[chat_id] = {'contacts': [], 'is_running': False, 'delay': 30}
    
    if not data[chat_id].get('contacts'):
        await event.respond('❌ Сначала добавьте пользователей через /add')
        return
    
    if data[chat_id].get('is_running'):
        await event.respond('⚠️ Мониторинг уже запущен')
        return
    
    data[chat_id]['is_running'] = True
    delay = data[chat_id].get('delay', 30)
    
    await event.respond(f'🟢 МОНИТОРИНГ ЗАПУЩЕН\n📊 Проверка каждые {delay} сек\n/users - показать список')
    
    asyncio.create_task(monitor_loop(chat_id))

async def monitor_loop(chat_id):
    temp_client = TelegramClient(f'monitor_{chat_id}', API_ID, API_HASH)
    await temp_client.start(bot_token=BOT_TOKEN)
    
    while data.get(chat_id, {}).get('is_running', False):
        try:
            for contact in data[chat_id]['contacts']:
                try:
                    entity = await temp_client.get_entity(contact.user_id)
                    current_status = type(entity.status).__name__
                    
                    # Проверяем изменение статуса
                    if contact.last_status != current_status:
                        # Статус изменился!
                        contact.last_status = current_status
                        contact.last_change = datetime.now()
                        
                        if isinstance(entity.status, UserStatusOnline):
                            msg = f"🟢 {contact.name} ВОШЕЛ В СЕТЬ!"
                            if contact.last_change:
                                msg += f"\n⏰ {contact.last_change.strftime('%H:%M:%S')}"
                            await bot.send_message(chat_id, msg)
                            
                        elif isinstance(entity.status, UserStatusOffline):
                            msg = f"⚫ {contact.name} ВЫШЕЛ ИЗ СЕТИ"
                            if entity.status.was_online:
                                diff = datetime.now().astimezone() - entity.status.was_online
                                msg += f"\n⏰ Был(а) онлайн: {format_time_diff(diff)}"
                            await bot.send_message(chat_id, msg)
                            
                        elif isinstance(entity.status, UserStatusRecently):
                            if contact.online:
                                await bot.send_message(chat_id, f"⚠️ {contact.name}: статус изменился на 'недавно'")
                        
                        contact.online = isinstance(entity.status, UserStatusOnline)
                    
                except Exception as e:
                    print(f"Ошибка проверки {contact.name}: {e}")
            
            delay = data.get(chat_id, {}).get('delay', 30)
            await asyncio.sleep(delay)
            
        except Exception as e:
            print(f"Ошибка в цикле мониторинга: {e}")
            await asyncio.sleep(10)
    
    await temp_client.disconnect()

@bot.on(events.NewMessage(pattern='/stop_monitor'))
async def stop_monitor(event):
    chat_id = event.message.chat_id
    
    if chat_id in data:
        data[chat_id]['is_running'] = False
    
    await event.respond('🔴 МОНИТОРИНГ ОСТАНОВЛЕН')

@bot.on(events.NewMessage(pattern='/logs'))
async def show_logs(event):
    try:
        with open('spy_log.txt', 'r') as f:
            content = f.read()
            if len(content) > 4000:
                content = content[-4000:] + "\n... (обрезано)"
            await event.respond(f'📄 ЛОГИ:\n\n{content}')
    except:
        await event.respond('📭 Логи пусты')

@bot.on(events.NewMessage(pattern='/clearlogs'))
async def clear_logs(event):
    open('spy_log.txt', 'w').close()
    await event.respond('🗑️ Логи очищены')

@bot.on(events.NewMessage(pattern='/users'))
async def show_users(event):
    chat_id = event.message.chat_id
    
    if chat_id not in data or 'contacts' not in data[chat_id]:
        await event.respond('📭 Нет пользователей')
        return
    
    response = "👥 ОТСЛЕЖИВАЕМЫЕ ПОЛЬЗОВАТЕЛИ:\n\n"
    for contact in data[chat_id]['contacts']:
        status = "🟢" if contact.online else "⚫"
        response += f"{status} {contact.name}\n"
    
    await event.respond(response)

def printToFile(msg):
    with open('spy_log.txt', 'a') as f:
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        log_msg = f'[{timestamp}] {msg}'
        print(log_msg)
        f.write(log_msg + '\n')

@bot.on(events.NewMessage())
async def log_all(event):
    chat_id = event.message.chat_id
    text = event.message.message
    printToFile(f'[{chat_id}]: {text}')

print('🚀 Бот готов к работе!')
print('Команды: /start_monitor - запуск, /stop_monitor - остановка, /add - добавить')

bot.run_until_disconnected()

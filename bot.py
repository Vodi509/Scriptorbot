import logging
import asyncio
import os
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from dotenv import load_dotenv

# ================================================
# 1. ЗАГРУЖАЕМ ТОКЕНЫ ИЗ ФАЙЛА .env
# ================================================
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not GEMINI_API_KEY:
    print("❌ ОШИБКА: Создай файл .env с токенами!")
    print("BOT_TOKEN=твой_токен")
    print("GEMINI_API_KEY=твой_ключ")
    exit()

# ================================================
# 2. НАСТРАИВАЕМ GEMINI
# ================================================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ================================================
# 3. СОЗДАЁМ БОТА
# ================================================
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================================================
# 4. СОСТОЯНИЯ
# ================================================
class ScriptState(StatesGroup):
    waiting_for_place = State()
    waiting_for_idea_choice = State()
    waiting_for_script_request = State()

# ================================================
# 5. ГЕНЕРАЦИЯ ИДЕЙ
# ================================================
async def generate_ideas(place_name: str) -> list:
    prompt = f"""
    Игра в Roblox: {place_name}
    Придумай 5 конкретных идей для скриптов (авто-фарм, автоматизация, улучшения).
    Каждая идея должна быть полезной и выполнимой в Lua.
    Формат: просто список с цифрами (1. Идея, 2. Идея...)
    """
    
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, model.generate_content, prompt
        )
        text = response.text.strip()
        
        ideas = []
        for line in text.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                clean = line.lstrip('0123456789.-• ').strip()
                if clean:
                    ideas.append(clean)
        
        if len(ideas) < 3:
            ideas = [line.strip() for line in text.split('\n') if line.strip()][:5]
        
        return ideas[:5]
    
    except Exception as e:
        print(f"Ошибка Gemini: {e}")
        return [
            "Автоматический сбор ресурсов по радиусу",
            "Телепортация по координатам с интерфейсом",
            "Авто-фарм с анти-афк системой",
            "Спавн предметов по нажатию кнопки",
            "Автоматическое выполнение квестов"
        ]

# ================================================
# 6. КОМАНДА /start
# ================================================
@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я **Креатор скриптов** для Roblox!\n\n"
        "🎮 Напиши название игры (Place), и я придумаю идеи.\n"
        "Примеры: `Grow a Garden 2`, `Brookhaven`, `Adopt Me`\n\n"
        "Или опиши свою задачу 😉"
    )
    await state.set_state(ScriptState.waiting_for_place)

# ================================================
# 7. ПОЛЬЗОВАТЕЛЬ НАПИСАЛ НАЗВАНИЕ ИГРЫ
# ================================================
@dp.message(ScriptState.waiting_for_place)
async def get_place(message: Message, state: FSMContext):
    place_name = message.text.strip()
    
    loading_msg = await message.answer("⏳ Думаю над идеями для **" + place_name + "**...")
    
    ideas = await generate_ideas(place_name)
    await state.update_data(place=place_name, ideas=ideas)
    
    text = f"🎯 **Игра:** {place_name}\n\n"
    text += "💡 Вот что я могу предложить:\n"
    for i, idea in enumerate(ideas, 1):
        text += f"{i}. {idea}\n"
    
    text += "\n📌 Напиши **номер идеи** (1-5) или свою задачу."
    
    await loading_msg.edit_text(text)
    await state.set_state(ScriptState.waiting_for_idea_choice)

# ================================================
# 8. ПОЛЬЗОВАТЕЛЬ ВЫБРАЛ ИДЕЮ
# ================================================
@dp.message(ScriptState.waiting_for_idea_choice)
async def generate_script(message: Message, state: FSMContext):
    data = await state.get_data()
    ideas = data.get("ideas", [])
    place = data.get("place", "игры")
    
    user_input = message.text.strip()
    
    try:
        choice_num = int(user_input)
        if 1 <= choice_num <= len(ideas):
            idea_text = ideas[choice_num - 1]
        else:
            idea_text = user_input
    except:
        idea_text = user_input
    
    await message.answer("⚙️ Пишу скрипт... Подожди немного.")
    
    prompt = f"""
    Игра в Roblox: {place}
    Задача скрипта: {idea_text}
    
    Напиши готовый Lua скрипт для Roblox, который:
    - Работает в LocalScript или ServerScript
    - Содержит комментарии на русском
    - Безопасный и оптимизированный
    - Использует game:GetService() где нужно
    
    Формат ответа: только код в блоке ```lua
    """
    
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, model.generate_content, prompt
        )
        code = response.text.strip()
        
        if not code.startswith("```lua"):
            code = "```lua\n" + code + "\n```"
        
        await message.answer(
            f"✅ **Готово!** Скрипт для **{place}**\n"
            f"📝 Задача: {idea_text}\n\n"
            f"{code}\n\n"
            "🔧 Если что-то не работает — напиши ошибку, я исправлю!"
        )
        
        await state.set_state(ScriptState.waiting_for_script_request)
        
    except Exception as e:
        await message.answer(
            "❌ Ошибка при создании скрипта. Попробуй ещё раз."
        )
        print(f"Ошибка: {e}")

# ================================================
# 9. ПОЛЬЗОВАТЕЛЬ ПРИСЛАЛ ОШИБКУ
# ================================================
@dp.message(ScriptState.waiting_for_script_request)
async def fix_error(message: Message, state: FSMContext):
    error_text = message.text
    
    await message.answer("🛠️ Анализирую ошибку...")
    
    prompt = f"""
    Пользователь написал ошибку в скрипте для Roblox:
    "{error_text}"
    
    Дай решение на русском языке:
    1. Что могло вызвать ошибку
    2. Как исправить
    3. Пример исправленного кода (если нужно)
    """
    
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, model.generate_content, prompt
        )
        answer = response.text.strip()
        
        await message.answer(
            f"🔧 **Решение ошибки:**\n\n{answer}\n\n"
            "Попробуй, и если что-то ещё — пиши 😉"
        )
    except:
        await message.answer(
            "❌ Не смог разобрать ошибку. Опиши подробнее."
        )

# ================================================
# 10. ЗАПУСК
# ================================================
async def main():
    logging.basicConfig(level=logging.INFO)
    print("=" * 40)
    print("🤖 БОТ ЗАПУЩЕН НА ТЕЛЕФОНЕ!")
    print("📱 Напиши /start в Telegram")
    print("=" * 40)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

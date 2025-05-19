import asyncio
import sys
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from tortoise import Tortoise

from config import BOT_TOKEN, DATABASE_URL, VERIFICATION_TIMEOUT, FORBIDDEN_WORDS
from models import BlacklistedUser, PendingVerification


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def init_db():
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas()


def contains_forbidden_words(text):
    if text is None:
        return False
    
    text_lower = text.lower()
    for word in FORBIDDEN_WORDS:
        if word.lower() in text_lower:
            return True
    return False


@dp.callback_query(lambda c: c.data.startswith("verify_"))
async def process_verification(callback_query: CallbackQuery):
    user_id_str = callback_query.data.split("_")[1]
    user_id = int(user_id_str)
    

    if callback_query.from_user.id != user_id:
        await callback_query.answer("Эта кнопка не для вас", show_alert=True)
        return
    

    verification = await PendingVerification.filter(
        user_id=user_id,
        chat_id=callback_query.message.chat.id
    ).first()
    
    if verification:
  
        await verification.delete()
        

        await callback_query.message.edit_text(
            f"@{callback_query.from_user.username or callback_query.from_user.first_name} "
            "успешно подтвердил, что не является роботом."
        )
        
        await callback_query.answer("Верификация пройдена успешно!", show_alert=True)
    else:
        await callback_query.answer("Верификация не найдена или истекла", show_alert=True)


async def check_verification_timeout(user_id, chat_id, message_id):

    await asyncio.sleep(VERIFICATION_TIMEOUT)
    

    verification = await PendingVerification.filter(
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id
    ).first()
    
    if verification:

        try:
            chat_member = await bot.get_chat_member(chat_id, user_id)
            username = chat_member.user.username
            first_name = chat_member.user.first_name
            last_name = chat_member.user.last_name
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе: {e}")
            username = None
            first_name = None
            last_name = None
        

        await BlacklistedUser.create(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            chat_id=chat_id,
            reason="Не прошел верификацию"
        )
        

        try:
            await bot.ban_chat_member(chat_id, user_id)
            
            await bot.edit_message_text(
                f"Пользователь не подтвердил, что не является роботом, и был занесен в черный список.",
                chat_id=chat_id,
                message_id=message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при бане пользователя: {e}")
            
            await bot.edit_message_text(
                f"Пользователь не подтвердил, что не является роботом, но бот не смог его забанить. "
                f"Возможно, у бота недостаточно прав.",
                chat_id=chat_id,
                message_id=message_id
            )
        

        await verification.delete()


@dp.message(F.text == 'статус')
async def cmd_status(message: Message):
    blacklisted_count = await BlacklistedUser.filter(chat_id=message.chat.id).count()
    await message.answer(
        f"Статус бота:\n"
        f"Забанено пользователей: {blacklisted_count}\n"
        f"Бот работает и готов обнаруживать подозрительную активность."
    )


@dp.message(Command("blacklist"))
async def cmd_blacklist(message: Message):
    print('вызван бллек')

    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in ["administrator", "creator"]:
        await message.answer("Эта команда доступна только администраторам чата.")
        return
    

    blacklisted_users = await BlacklistedUser.filter(chat_id=message.chat.id).all()
    
    if not blacklisted_users:
        await message.answer("Черный список пуст.")
        return
    

    blacklist_text = "Черный список пользователей:\n\n"
    for user in blacklisted_users:
        user_info = f"ID: {user.user_id}\n"
        if user.username:
            user_info += f"Username: @{user.username}\n"
        if user.first_name:
            user_info += f"Имя: {user.first_name}\n"
        if user.last_name:
            user_info += f"Фамилия: {user.last_name}\n"
        user_info += f"Причина: {user.reason}\n"
        user_info += f"Дата: {user.created_at.strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        

        if len(blacklist_text + user_info) > 4000:
            await message.answer(blacklist_text)
            blacklist_text = user_info
        else:
            blacklist_text += user_info
    
    await message.answer(blacklist_text)


@dp.message(Command("clear_blacklist"))
async def cmd_clear_blacklist(message: Message):

    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status != "creator":
        await message.answer("Эта команда доступна только создателю чата.")
        return
    
    deleted_count = await BlacklistedUser.filter(chat_id=message.chat.id).delete()
    
    await message.answer(f"Черный список очищен. Удалено записей: {deleted_count}")


@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    # Проверка прав администратора
    chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    if chat_member.status not in ["administrator", "creator"]:
        await message.answer("Эта команда доступна только администраторам чата.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /unban <user_id>")
        return
    
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("Некорректный ID пользователя.")
        return
    
    deleted_count = await BlacklistedUser.filter(chat_id=message.chat.id, user_id=user_id).delete()
    
    if deleted_count:

        try:
            chat_info = await bot.get_chat(message.chat.id)
            is_supergroup = chat_info.type in ["supergroup", "channel"]
            
            if is_supergroup:
                try:
                    await bot.unban_chat_member(message.chat.id, user_id, only_if_banned=True)
                    await message.answer(f"Пользователь с ID {user_id} удален из черного списка и разбанен.")
                except Exception as e:
                    logger.error(f"Ошибка при разбане пользователя: {e}")
                    await message.answer(
                        f"Пользователь с ID {user_id} удален из черного списка, "
                        f"но бот не смог его разбанить. Возможно, у бота недостаточно прав."
                    )
            else:
                await message.answer(
                    f"Пользователь с ID {user_id} удален из черного списка. "
                    f"Разбан невозможен, так как эта функция доступна только для супергрупп и каналов. "
                    f"Пожалуйста, разбаньте пользователя вручную."
                )
        except Exception as e:
            logger.error(f"Ошибка при получении информации о чате: {e}")
            await message.answer(
                f"Пользователь с ID {user_id} удален из черного списка, "
                f"но бот не смог проверить тип чата. Пожалуйста, разбаньте пользователя вручную."
            )
    else:
        await message.answer(f"Пользователь с ID {user_id} не найден в черном списке.")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "Команды бота:\n"
        "/status - Показать статус бота\n"
        "/blacklist - Показать черный список (только для администраторов)\n"
        "/unban <user_id> - Удалить пользователя из черного списка (только для администраторов)\n"
        "/clear_blacklist - Очистить черный список (только для создателя чата)\n"
        "/help - Показать эту справку\n\n"
        "Бот автоматически обнаруживает подозрительную активность и запрашивает верификацию."
    )
    await message.answer(help_text)


@dp.errors()
async def handle_errors(update, exception):
    logger.error(f"Ошибка при обработке сообщения: {exception}")
    logger.exception(exception)


@dp.message()
async def process_message(message: Message):

    if message.text or message.caption:
        text = message.text or message.caption
        

        if contains_forbidden_words(text):

            user_id = message.from_user.id
            chat_id = message.chat.id
            

            is_blacklisted = await BlacklistedUser.filter(user_id=user_id, chat_id=chat_id).exists()
            if is_blacklisted:
                return
            

            pending = await PendingVerification.filter(user_id=user_id, chat_id=chat_id).exists()
            if pending:
                return
            

            keyboard = InlineKeyboardBuilder()
            keyboard.button(
                text="Я не робот", 
                callback_data=f"verify_{user_id}"
            )
            
            verification_message = await message.answer(
                f"@{message.from_user.username or message.from_user.first_name}, "
                "подтвердите, что вы не робот, нажмите кнопку ниже в течение одной минуты.",
                reply_markup=keyboard.as_markup()
            )
            

            expires_at = datetime.now() + timedelta(seconds=VERIFICATION_TIMEOUT)
            await PendingVerification.create(
                user_id=user_id,
                chat_id=chat_id,
                message_id=verification_message.message_id,
                expires_at=expires_at
            )
            

            asyncio.create_task(
                check_verification_timeout(user_id, chat_id, verification_message.message_id)
            )


async def main():

    await init_db()
    

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await Tortoise.close_connections()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
import config
import logging
from bitrix24 import *
from aiogram import Bot, Dispatcher, executor, types
import aiogram.utils.markdown as md
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton

# log level
logging.basicConfig(level=logging.INFO)

# bot init
bot = Bot(token=config.TOKEN)
contact_bot = config.CONTACT_BOT_LINK
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
bx24 = Bitrix24(domain=config.BITRIX_LINK)


#  форма с состояниями
class Form(StatesGroup):
    taskName = State()
    taskPhone = State()
    taskConfirm = State()


def markup(arg):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    if arg == "add":
        markup.add("Поставить задачу")
        markup.add("Связаться с сотрудником")
    if arg == "abrt":
        markup.add("Отмена")

    return markup


# начало общения
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply('Добро пожаловать в бот компании СкайСервис для постановки задач!\nЧтобы начать, нажмите кнопку "Поставить задачу".', reply_markup=markup("add"))


@dp.message_handler(Text(equals='поставить задачу', ignore_case=True))
async def cmd_start(message: types.Message):
    await Form.taskName.set()
    await message.reply("Опишите новую задачу", reply_markup=markup("abrt"))


@dp.message_handler(commands=['help'])
async def helper(message: types.Message):
    await message.reply("Вы используете бот компании СкайСервис для автоматического создания задач. \n"
                        'Отправьте "Поставить задачу" чтобы начать \n'
                        f"Возникли вопросы? Свяжитесь с сотрудником: {contact_bot}")

@dp.message_handler(Text(equals='связаться с сотрудником', ignore_case=True))
async def contact(message: types.Message):
    await message.reply(f'<a href="{contact_bot}">Нажмите чтобы перейти в чат</a>', parse_mode="HTML")


# добавляем возможность отмены, если пользователь передумал заполнять
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='отмена', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.reply('Добавление задачи отменено', reply_markup=markup("add"))
        return

    await state.finish()
    await message.reply('Добавление задачи отменено', reply_markup=markup("add"))


# обработчик названия
@dp.message_handler(state=Form.taskName)
async def process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['taskName'] = message.text

    await Form.next()
    await message.reply("Введите контактный телефон")
    print(message)


# обработчик номера телефона, вывод callback подтверждения
@dp.message_handler(state=Form.taskPhone)
async def process_date(message: types.Message, state: FSMContext):
    print(message)
    async with state.proxy() as data:
        data['taskPhone'] = message.text
    main_menu = InlineKeyboardMarkup(row_width=2)
    btn_confirm = InlineKeyboardButton(text="Подтвердить", callback_data="btnConfirm")
    btn_rejct = InlineKeyboardButton(text="Отменить", callback_data="btnReject")
    main_menu.insert(btn_rejct)
    main_menu.insert(btn_confirm)
    await bot.send_message(message.chat.id, "Проверьте правильность данных:")
    await bot.send_message(
        message.chat.id,
        md.text(
            md.text('Описание задачи: ', md.bold(data['taskName']), '\n'),
            md.text('Контактный телефон: ', md.code(data['taskPhone'])),
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu
    )
    await Form.next()


# callback кнопка подтвердить, bitrix24
@dp.callback_query_handler(text="btnConfirm", state=Form.taskConfirm)
async def callback_btn(callback: types.CallbackQuery, state: FSMContext):
    print(callback)
    async with state.proxy() as data:
        try:
            bx24.callMethod(
                "tasks.task.add",
                fields=
                {
                    "TITLE": "от " + callback.from_user.first_name + " т:" + data['taskPhone'],
                    "DESCRIPTION": "<b>" + data["taskName"] + "</b>" + "\n\n————————————————————————————————\nссылка: " + "https://t.me/" + callback.from_user.username,
                    "GROUP_ID": "70",
                    "RESPONSIBLE_ID": "52",
                    "CREATED_BY": "1",
                    "AUDITORS": ["1"],
                    "STATUS": "2",
                }
            )
            await callback.message.answer("Задача сохранена", reply_markup=markup("add"))
            print("task added")
        except UnboundLocalError or BitrixError as error:
            await callback.message.answer("Проблемы с сервером. Попробуйте позже", reply_markup=markup("add"))
            print(error)

    await bot.answer_callback_query(callback_query_id=callback.id)
    # await callback.answer(callback.id, cache_time=300)
    await state.finish()


# callback кнопка отмена
@dp.callback_query_handler(text="btnReject", state=Form.taskConfirm)
async def callback_btn(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.reply('Добавление задачи отменено', reply_markup=markup("add"))
    await callback.answer()


# пустые callback кнопки
@dp.callback_query_handler(text="btnConfirm")
@dp.callback_query_handler(text="btnReject")
async def empty_callback(callback: types.CallbackQuery):
    await callback.answer()


# пустые сообщения
@dp.message_handler()
async def text(message: types.Message):
    await message.answer("Я не понимаю простой текст. \n"
                         "Используйте команду /help чтобы узнать больше", reply_markup=markup("add"))


# run long-polling
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='📥 Новые', callback_data='dialogs:new')],
            [InlineKeyboardButton(text='👩‍💻 Мои', callback_data='dialogs:my')],
            [InlineKeyboardButton(text='✅ Закрытые', callback_data='dialogs:closed')],
            [InlineKeyboardButton(text='📈 Статистика', callback_data='dialogs:stats')],
        ]
    )


def dialog_actions_keyboard(dialog_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🧾 Карточка', callback_data=f'dialog:{dialog_id}:card')],
            [InlineKeyboardButton(text='🫱 Взять в работу', callback_data=f'dialog:{dialog_id}:take')],
            [InlineKeyboardButton(text='✉️ Отправить вариант 1', callback_data=f'dialog:{dialog_id}:send1')],
            [InlineKeyboardButton(text='✉️ Отправить вариант 2', callback_data=f'dialog:{dialog_id}:send2')],
            [InlineKeyboardButton(text='🔄 Регенерация', callback_data=f'dialog:{dialog_id}:regen')],
            [InlineKeyboardButton(text='⌨️ Ручной ответ', callback_data=f'dialog:{dialog_id}:manual')],
            [InlineKeyboardButton(text='✅ Закрыть', callback_data=f'dialog:{dialog_id}:close')],
            [InlineKeyboardButton(text='↩️ Вернуть в очередь', callback_data=f'dialog:{dialog_id}:requeue')],
        ]
    )

from aiogram.fsm.state import State, StatesGroup


class DialogState(StatesGroup):
    waiting_for_message = State()

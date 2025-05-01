from aiogram.fsm.state import StatesGroup, State

class Conversation(StatesGroup):
    waiting_for_message = State()
    waiting_for_image = State()

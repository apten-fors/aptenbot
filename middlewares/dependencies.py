from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

class DependencyMiddleware(BaseMiddleware):
    def __init__(self, **deps):
        self.deps = deps
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Inject all dependencies into data
        for key, value in self.deps.items():
            data[key] = value

        return await handler(event, data)

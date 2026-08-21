from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Message

from middlewares.logging import LoggingMiddleware


@pytest.mark.asyncio
async def test_business_logging_middleware_does_not_log_message_text():
    secret_text = "private customer message"
    message = Message.model_validate(
        {
            "message_id": 10,
            "date": 0,
            "chat": {"id": 456, "type": "private"},
            "from": {"id": 789, "is_bot": False, "first_name": "Guest"},
            "text": secret_text,
            "business_connection_id": "business-123",
        }
    )
    handler = AsyncMock()
    middleware = LoggingMiddleware(redact_message_text=True)

    with patch("middlewares.logging.logger.info") as log_info:
        await middleware(handler, message, {})

    logged_call = repr(log_info.call_args)
    assert secret_text not in logged_call
    assert "business-123" in logged_call
    handler.assert_awaited_once_with(message, {})

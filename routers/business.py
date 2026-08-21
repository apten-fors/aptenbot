"""Telegram Business / Secretary Mode update handlers."""

from aiogram import F, Router
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message

from managers.session_manager import SessionManager
from services.answer_service import select_client
from utils.logging_config import logger
from utils.telegram_utils import send_long_message

router = Router()


def build_business_session_key(business_connection_id: str, chat_id: int) -> str:
    """Return a session key isolated from normal and guest conversations."""
    return f"telegram_business:{business_connection_id}:{chat_id}"


@router.business_connection()
async def handle_business_connection(connection: BusinessConnection) -> None:
    """Log connection lifecycle changes without persisting connection data."""
    status = "active" if connection.is_enabled else "inactive"
    logger.info(
        "event=business_connection_updated connection_id=%s user_id=%s "
        "user_chat_id=%s is_enabled=%s status=%s rights=%s",
        connection.id,
        connection.user.id,
        connection.user_chat_id,
        connection.is_enabled,
        status,
        connection.rights,
    )


@router.business_message(F.text)
async def handle_business_message(
    message: Message,
    session_manager: SessionManager,
    provider_clients: dict[str, object],
) -> None:
    """Generate and send a reply through the incoming business connection."""
    business_connection_id = message.business_connection_id
    chat_id = message.chat.id
    from_user_id = message.from_user.id if message.from_user else None
    text = message.text or ""

    logger.info(
        "event=business_message_received business_connection_id=%s chat_id=%s "
        "from_user_id=%s message_id=%s text_len=%s",
        business_connection_id,
        chat_id,
        from_user_id,
        message.message_id,
        len(text),
    )

    if not business_connection_id:
        logger.warning(
            "Business message ignored: missing business_connection_id chat_id=%s "
            "message_id=%s",
            chat_id,
            message.message_id,
        )
        return

    session_key = build_business_session_key(business_connection_id, chat_id)
    session = session_manager.get_or_create_session(session_key)
    model_provider = session_manager.get_model_provider(session_key)
    client = select_client(provider_clients, model_provider)
    reply = await client.process_message(session, text)

    sent_messages = await send_long_message(message, reply)
    for sent_message in sent_messages:
        logger.info(
            "event=business_message_answer_sent business_connection_id=%s "
            "chat_id=%s message_id=%s",
            business_connection_id,
            chat_id,
            getattr(sent_message, "message_id", None),
        )


@router.edited_business_message()
async def handle_edited_business_message(message: Message) -> None:
    """Safely acknowledge edits without invoking the LLM again."""
    logger.info(
        "event=edited_business_message_ignored business_connection_id=%s "
        "chat_id=%s message_id=%s",
        message.business_connection_id,
        message.chat.id,
        message.message_id,
    )


@router.deleted_business_messages()
async def handle_deleted_business_messages(
    deleted: BusinessMessagesDeleted,
) -> None:
    """Safely acknowledge deletions without invoking the LLM again."""
    logger.info(
        "event=deleted_business_messages_ignored business_connection_id=%s "
        "chat_id=%s message_ids=%s",
        deleted.business_connection_id,
        deleted.chat.id,
        deleted.message_ids,
    )

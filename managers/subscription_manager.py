from utils.logging_config import logger
from config import CHANNEL_ID, CHANNEL_USER_ID

class SubscriptionManager:
    @staticmethod
    async def is_subscriber(user_id: int, bot) -> bool:
        logger.info(f"Checking subscription status for user: {user_id}")
        try:
            # Check if the user is posting on behalf of the channel
            if user_id == int(CHANNEL_USER_ID):
                logger.info("Message sent on behalf of a channel, considering as subscribed")
                return True

            member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            logger.info(f"Member status: {member.status}")
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            logger.error(f"Error checking subscription status: {e}")
            return False

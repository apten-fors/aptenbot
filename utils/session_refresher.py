import asyncio
from utils.redis_client import RedisClient
from utils.session_store import IgSessionStore
from clients.ig_client import IgClient
from utils.logging_config import logger


async def main() -> None:
    redis = RedisClient().get_master()
    store = IgSessionStore(redis)
    client = IgClient(store)
    await client.login()
    logger.info("Instagram session refreshed")
    await redis.close()


if __name__ == "__main__":
    asyncio.run(main())

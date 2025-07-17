from redis.asyncio.sentinel import Sentinel
from redis.asyncio.client import Redis
from typing import List, Tuple
from settings import REDIS_SENTINEL_HOSTS, REDIS_SENTINEL_MASTER, REDIS_PASSWORD


def _parse_hosts() -> List[Tuple[str, int]]:
    hosts = []
    for item in REDIS_SENTINEL_HOSTS.split(','):
        if not item:
            continue
        host, port = item.split(':')
        hosts.append((host, int(port)))
    return hosts


class RedisClient:
    def __init__(self) -> None:
        self.sentinel = Sentinel(
            _parse_hosts(),
            password=REDIS_PASSWORD,
            socket_timeout=5,
            sentinel_kwargs={"password": REDIS_PASSWORD},
        )

    def get_master(self) -> Redis:
        return self.sentinel.master_for(
            REDIS_SENTINEL_MASTER,
            password=REDIS_PASSWORD,
            socket_timeout=5,
        )

    async def ping(self) -> bool:
        client = self.get_master()
        try:
            pong = await client.ping()
            return pong is True
        finally:
            await client.close()

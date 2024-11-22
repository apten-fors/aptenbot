import aiohttp
from config import BFL_API_KEY, FLUX_MODEL
from utils.logging_config import logger

class FluxClient:
    def __init__(self):
        self.api_key = BFL_API_KEY
        self.model = FLUX_MODEL
        self.url = "https://api.bfl.ml/v1"

    async def generate_image(self, prompt: str) -> str:
        endpoint = f"{self.url}/{self.model}"
        payload = {
            "prompt": prompt,
            "width": 1024,
            "height": 768,
            "prompt_upsampling": False,
            "safety_tolerance": 2,
            "output_format": "jpeg"
        }
        headers = {
            "Content-Type": "application/json",
            "X-Key": self.api_key
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(endpoint, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    query_params = await response.json()
                logger.info(f"Get task id: {query_params}")
                get_url = f"{self.url}/get_result"
                async with session.get(get_url, params=query_params) as get_response:
                    get_response.raise_for_status()
                    result = await get_response.json()
                    logger.info(f"Get result with image: {result}")
                    return result["result"]["sample"]

            except aiohttp.ClientError as e:
                logger.error(f"HTTP request failed: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                raise

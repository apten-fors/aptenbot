import os
import instaloader
from utils.logging_config import logger

class InstaloaderClient:
    def __init__(self):
        self.loader = instaloader.Instaloader(
            download_comments=False,
            download_geotags=False,
            download_pictures=False,
            download_video_thumbnails=False,
            save_metadata=False
        )

    def download_video(self, url: str) -> tuple[bool, str]:
        if not url:
            return False, "Invalid URL provided"

        try:
            shortcode = url.split('/')[-2]
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            if not post.is_video:
                return False, "This post does not contain a video"

            video_url = post.video_url
            extension = video_url.split('?')[0].split('.')[-1] if video_url else 'mp4'
            filename = f"{shortcode}/{post.date_utc.strftime('%Y-%m-%d_%H-%M-%S')}_UTC.{extension}"

            # Try to download
            logger.info(f"Downloading video to {filename}")
            self.loader.download_post(post, target=shortcode)

            # Verify if file exists after attempting download
            if os.path.exists(filename):
                return True, filename
            else:
                return False, "no file exists"

        except Exception as e:
            logger.error(f'Something went wrong while downloading video: {e}')
            return False, f"Failed to download video: {str(e)}"

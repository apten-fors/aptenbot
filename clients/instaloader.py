import os
import instaloader
from utils.logging_config import logger
from settings import IG_USERNAME, IG_PASSWORD
from pathlib import Path

class InstaloaderClient:
    def __init__(self):
        self.loader = instaloader.Instaloader(
            download_comments=False,
            download_geotags=False,
            download_pictures=False,
            download_video_thumbnails=False,
            save_metadata=False
        )
        self._logged_in = False
        self._session_file = f".instaloader_session_{IG_USERNAME}" if IG_USERNAME else None
        self._ensure_login()

    def _ensure_login(self) -> None:
        if self._logged_in:
            return
        if not IG_USERNAME or not IG_PASSWORD:
            logger.warning("IG credentials are not set (IG_USERNAME/IG_PASSWORD). Proceeding unauthenticated.")
            return
        # Try to load a persisted session first
        try:
            if self._session_file and Path(self._session_file).exists():
                logger.info(f"Loading Instagram session from file: {self._session_file}")
                self.loader.load_session_from_file(IG_USERNAME, filename=self._session_file)
                self._logged_in = True
                return
            else:
                # Try default session file path used by Instaloader CLI
                try:
                    logger.info("Trying to load default Instaloader session file")
                    self.loader.load_session_from_file(IG_USERNAME)
                    self._logged_in = True
                    return
                except Exception as e2:
                    logger.info(f"Default session load failed, will try fresh login: {e2}")
        except Exception as e:
            logger.warning(f"Failed to load saved IG session file, will try login: {e}")
        # Fallback to fresh login
        logger.info("Logging in to Instagram via Instaloader")
        self.loader.login(IG_USERNAME, IG_PASSWORD)
        # Persist session to file for reuse
        try:
            if self._session_file:
                self.loader.save_session_to_file(filename=self._session_file)
                logger.info(f"Saved Instagram session to file: {self._session_file}")
        except Exception as e:
            logger.warning(f"Failed to save IG session file: {e}")
        self._logged_in = True

    def download_video(self, url: str) -> tuple[bool, str]:
        if not url:
            return False, "Invalid URL provided"

        # Ensure we are authenticated before attempting to access post data
        try:
            self._ensure_login()
        except Exception as e:
            logger.warning(f"Proceeding without IG login due to error: {e}")

        def _do_download() -> tuple[bool, str]:
            shortcode = url.split('/')[-2]
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            if not post.is_video:
                return False, "This post does not contain a video"

            video_url = post.video_url
            extension = video_url.split('?')[0].split('.')[-1] if video_url else 'mp4'
            filename = f"{shortcode}/{post.date_utc.strftime('%Y-%m-%d_%H-%M-%S')}_UTC.{extension}"

            logger.info(f"Downloading video to {filename}")
            self.loader.download_post(post, target=shortcode)

            if os.path.exists(filename):
                return True, filename
            else:
                return False, "no file exists"

        try:
            return _do_download()
        except Exception as e:
            msg = str(e)
            logger.warning(f"Download failed on first attempt: {msg}")
            if any(err in msg for err in ["401", "403", "Please wait a few minutes"]):
                # Clear persisted session and re-login once
                try:
                    if self._session_file and Path(self._session_file).exists():
                        Path(self._session_file).unlink(missing_ok=True)
                        logger.info("Removed stale IG session file. Re-authenticating...")
                except Exception as del_err:
                    logger.warning(f"Failed to remove session file: {del_err}")
                self._logged_in = False
                try:
                    self._ensure_login()
                    return _do_download()
                except Exception as e2:
                    logger.error(f"Retry after re-login failed: {e2}")
                    return False, f"Failed to download video after re-login: {e2}"
            logger.error(f'Something went wrong while downloading video: {e}')
            return False, f"Failed to download video: {msg}"

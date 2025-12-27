
import shutil
import os
import yaml
from datetime import datetime, timezone
import logging
import uuid

logger = logging.getLogger(__name__)

FEEDS_FILE_PATH = os.path.expandvars(os.environ.get('FEEDS_FILE_PATH', '/var/mbz-rss-feeder/feeds.yml'))
CONFIG_FILE_PATH = os.path.expandvars(os.environ.get('CONFIG_FILE_PATH', '/var/mbz-rss-feeder/etc/mbz-rss-feeder.yml'))
CACHE_DIR = os.path.expandvars(os.environ.get('CACHE_DIR', '/var/mbz-rss-feeder/cache'))
MB_APP_NAME = os.path.expandvars(os.environ.get('MB_APP_NAME', 'mbz-rss-service'))
MB_VERSION = os.path.expandvars(os.environ.get('MB_VERSION', '1'))
MB_CONTACT = os.path.expandvars(os.environ.get('MB_CONTACT', 'someone@somewhere.com'))

# file system dir check
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
if not os.path.exists(os.path.dirname(FEEDS_FILE_PATH)):
    os.makedirs(os.path.dirname(FEEDS_FILE_PATH))
if not os.path.exists(os.path.dirname(CONFIG_FILE_PATH)):
    os.makedirs(os.path.dirname(CONFIG_FILE_PATH))

class Config:
    def __init__(self):
        self._feeds_data = self._load_yaml(FEEDS_FILE_PATH)
        if os.path.exists(CONFIG_FILE_PATH):
            self._settings = self._load_yaml(CONFIG_FILE_PATH)
        else:
            self._settings = {
               'service': {
                    'days_back': 0,
                    'cache_time_hours': 8
                }
            }
        self.FEEDS_FILE_PATH = FEEDS_FILE_PATH
        self.CONFIG_FILE_PATH = CONFIG_FILE_PATH
        self.CACHE_DIR = CACHE_DIR
        self.MB_APP_NAME = MB_APP_NAME
        self.MB_VERSION = MB_VERSION
        self.MB_CONTACT = MB_CONTACT
        try:
            with open(os.path.join(os.path.dirname(__file__), '..', 'VERSION')) as f:
                self.VERSION = f.read().strip()
        except FileNotFoundError:
            self.VERSION = '0.0.0'

    def __getattr__(self, name):
        if name == 'feeds':
            return self._feeds_data.get('feeds', [])
        if name in self._settings['service']:
            return self._settings['service'][name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def get_settings(self):
        return self._settings

    def _load_yaml(self, file_path):
        if not os.path.exists(file_path):
            return {}
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}

    def _save_yaml(self, data, file_path):
        if os.path.exists(file_path):
            backup_path = f"{file_path}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
            shutil.copy(file_path, backup_path)

        logger.debug(f"Saving yaml to {file_path}")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.debug(f"Saved yaml to {file_path}")

    @property
    def feeds(self):
        return self._feeds_data.get('feeds', [])

    def save_feeds(self):
        self._save_yaml(self._feeds_data, FEEDS_FILE_PATH)

    def get_feed(self, feed_id):
        for feed in self.feeds:
            if feed['id'] == feed_id:
                return feed
        return None

    def add_feed(self, name):
        now = datetime.now(timezone.utc).isoformat()
        new_feed = {
            'id': str(uuid.uuid4()),
            'name': name,
            'artists': [],
            'created_at': now,
            'updated_at': now
        }
        if 'feeds' not in self._feeds_data:
            self._feeds_data['feeds'] = []
        self._feeds_data['feeds'].append(new_feed)
        self.save_feeds()
        return new_feed

    def delete_feed(self, feed_id):
        if 'feeds' in self._feeds_data:
            self._feeds_data['feeds'] = [feed for feed in self.feeds if feed['id'] != feed_id]
            self.save_feeds()

    def add_artist_to_feed(self, feed_id, artist_id, artist_name, links = None):
        for feed in self.feeds:
            if feed['id'] == feed_id:
                if 'artists' not in feed:
                    feed['artists'] = []
                if not any(a['id'] == artist_id for a in feed['artists']):
                    artist_data = {'id': artist_id, 'name': artist_name}
                    if links:
                        artist_data['links'] = links
                    feed['artists'].append(artist_data)
                    feed['updated_at'] = datetime.now(timezone.utc).isoformat()
                    self.save_feeds()
                break

    def remove_artist_from_feed(self, feed_id, artist_id):
        for feed in self.feeds:
            if feed['id'] == feed_id and 'artists' in feed:
                original_artist_count = len(feed['artists'])
                feed['artists'] = [a for a in feed['artists'] if a['id'] != artist_id]
                if len(feed['artists']) < original_artist_count:
                    feed['updated_at'] = datetime.now(timezone.utc).isoformat()
                    self.save_feeds()
                break

    def get_artist_name(self, artist_id):
        for feed in self.feeds:
            for artist in feed.get('artists', []):
                if artist['id'] == artist_id:
                    return artist['name']
        return 'unknown artist'

    def save_settings(self, days_back, cache_time_hours):
        logger.debug(f"Saving settings: days_back={days_back}, cache_time_hours={cache_time_hours}")
        if 'service' not in self._settings:
            self._settings['service'] = {}
        if days_back is not None:
            self._settings['service']['days_back'] = int(days_back)
        if cache_time_hours is not None:
            self._settings['service']['cache_time_hours'] = int(cache_time_hours)
        self._save_yaml(self._settings, CONFIG_FILE_PATH)

# Global instance
config = Config()

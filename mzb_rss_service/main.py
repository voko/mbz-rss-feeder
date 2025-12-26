
from .config import config
import logging
from flask import Flask, jsonify, render_template, request, redirect, url_for
from datetime import datetime, timedelta, timezone
from email.utils import formatdate, parsedate_to_datetime
import xml.etree.ElementTree as ET
import os
import sys
from . import musicbrainz

log_level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
log_file = os.path.expandvars(os.environ.get('LOG_FILE', '/var/mbz-rss-feeder/log/mbz-rss-feeder.log'))
log_format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
mbz_log_level_str = os.environ.get('MBZ_LOG_LEVEL', 'WARNING').upper()
mbz_log_level = getattr(logging, mbz_log_level_str, logging.WARNING)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(log_level)
formatter = logging.Formatter(log_format)

# configure musicbrainz logger
logging.getLogger('musicbrainzngs').setLevel(mbz_log_level)

# Clear existing handlers
if root_logger.hasHandlers():
    root_logger.handlers.clear()

# Add file handler
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

# Add stdout handler if running with gunicorn (in container)
if 'gunicorn' in sys.argv[0]:
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)


# Get the werkzeug logger and remove its default handlers
werkzeug_logger = logging.getLogger('werkzeug')
for handler in werkzeug_logger.handlers:
    werkzeug_logger.removeHandler(handler)

logger = logging.getLogger(__name__)


logger.info("Starting mzb-rss-service with the following configuration:")
logger.info(f"  - Log Level: {log_level_str}")
logger.info(f"  - Log File: {log_file}")
logger.info(f"  - Feeds File: {config.FEEDS_FILE_PATH}")
logger.info(f"  - Config File: {config.CONFIG_FILE_PATH}")
logger.info(f"  - MusicBrainz App Name: {config.MB_APP_NAME}")
logger.info(f"  - MusicBrainz App Version: {config.MB_VERSION}")
logger.info(f"  - MusicBrainz Contact: {config.MB_CONTACT}")
logger.info(f"  - MusicBrainz Log Level: {mbz_log_level_str}")


# init
musicbrainz.init_musicbrainz()
app = Flask(__name__)
app.template_folder = 'templates'


def _get_cache_file_path(feed_id):
    """Constructs the full path for a feed's cache file."""
    return os.path.join(config.CACHE_DIR, f"{feed_id}.xml")


def _get_cache_last_build_date(cache_file):
    """Parses the cache file and returns its last build date as a timezone-aware datetime object."""
    if not os.path.exists(cache_file):
        return None

    try:
        tree = ET.parse(cache_file)
        root = tree.getroot()
        last_build_date_str = root.findtext('channel/lastBuildDate')
        if not last_build_date_str:
            return None

        last_build_date = parsedate_to_datetime(last_build_date_str)
        # Ensure last_build_date is timezone-aware (in UTC)
        if last_build_date.tzinfo is None:
            return last_build_date.replace(tzinfo=timezone.utc)
        return last_build_date
    except (ET.ParseError, FileNotFoundError) as e:
        logger.warning(f"Could not read or parse cache file {cache_file}: {e}")
        return None


def _is_cache_stale(last_build_date, feed_data, cache_time_hours):
    """Determines if the cache is stale based on update times and age."""
    if not last_build_date:
        return True  # No build date means it's stale

    # Invalidate if feed config was updated since last cache build
    if 'updated_at' in feed_data and feed_data['updated_at']:
        feed_updated_at = datetime.fromisoformat(feed_data['updated_at'])
        if feed_updated_at > last_build_date:
            logger.debug(f"Feed {feed_data['id']} has been updated. Invalidating cache.")
            return True

    # Invalidate if cache is older than the configured time
    if datetime.now(timezone.utc) - last_build_date > timedelta(hours=cache_time_hours):
        logger.debug(f"Cache for feed {feed_data['id']} is older than {cache_time_hours} hours. Invalidating.")
        return True

    return False


def _check_cache(feed_id):
    """Checks for a valid cached feed and returns it if found."""
    feed_data = config.get_feed(feed_id)
    if not feed_data:
        return None  # Feed doesn't exist, so no cache.

    cache_file = _get_cache_file_path(feed_id)
    last_build_date = _get_cache_last_build_date(cache_file)

    cache_time_hours = int(config.get_settings().get('service', {}).get('cache_time_hours', 24))

    if not _is_cache_stale(last_build_date, feed_data, cache_time_hours):
        try:
            with open(cache_file, 'r') as f:
                logger.debug(f"Serving cached feed for {feed_id}")
                return f.read(), {"Content-Type": "application/xml"}
        except IOError as e:
            logger.warning(f"Could not read cache file {cache_file}: {e}")

    return None


@app.route("/")
def index():
    logger.debug("Request for index page")
    feeds = config.feeds
    return render_template('index.html', feeds=feeds)

@app.route("/feed/create", methods=["POST"])
def create_feed():
    feed_name = request.form.get('name')
    logger.debug(f"Request to create feed with name: {feed_name}")
    if feed_name and feed_name.strip():
        config.add_feed(feed_name.strip())
    return redirect(url_for('index'))

@app.route("/feed/<feed_id>/delete", methods=["POST"])
def delete_feed(feed_id):
    logger.debug(f"Request to delete feed with id: {feed_id}")
    config.delete_feed(feed_id)
    return redirect(url_for('index'))

@app.route("/feed/<feed_id>/edit")
def edit_feed(feed_id):
    logger.debug(f"Request to edit feed with id: {feed_id}")
    feed = config.get_feed(feed_id)
    if not feed:
        return "Feed not found", 404
    return render_template('feed.html', feed=feed)

@app.route("/feed/<feed_id>/artist/add", methods=["POST"])
def add_artist(feed_id):
    artist_id = request.form.get('artist_id')
    artist_name = request.form.get('artist_name')
    logger.debug(f"Request to add artist '{artist_name}' ({artist_id}) to feed {feed_id}")
    if artist_id and artist_name:
        config.add_artist_to_feed(feed_id, artist_id, artist_name)
    return redirect(url_for('edit_feed', feed_id=feed_id))

@app.route("/feed/<feed_id>/artist/<artist_id>/remove", methods=["POST"])
def remove_artist(feed_id, artist_id):
    logger.debug(f"Request to remove artist {artist_id} from feed {feed_id}")
    config.remove_artist_from_feed(feed_id, artist_id)
    return redirect(url_for('edit_feed', feed_id=feed_id))

@app.route("/artist/search")
def search_artist():
    query = request.args.get('q', '')
    logger.debug(f"Request to search for artist with query: '{query}'")
    artists = musicbrainz.search_artists(query)
    return jsonify(artists)

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        logger.debug("Request to update settings")
        days_back = request.form.get('days_back')
        cache_time_hours = request.form.get('cache_time_hours')
        config.save_settings(days_back, cache_time_hours)
        return redirect(url_for('settings'))

    logger.debug("Request for settings page")
    return render_template('settings.html', settings=config)

@app.route("/opml")
def opml():
    logger.debug("Request for OPML file")
    feeds = config.feeds
    opml_content = render_template('opml.xml', feeds=feeds)
    return opml_content, {"Content-Type": "application/xml"}

@app.route('/feed/<feed_id>')
def get_feed_rss(feed_id):
    logger.debug(f"Request for RSS feed with id: {feed_id}")

    # Check cache for a valid feed before generating it
    cached_response = _check_cache(feed_id)
    if cached_response:
        return cached_response
    
    # cache outdated or not found, generate a new feed
    logger.debug(f"Generating new feed for {feed_id}")
    feed_data = config.get_feed(feed_id)
    if not feed_data:
        return "Feed not found", 404

    # Add rfc822 formatted updated_at for template
    if 'updated_at' in feed_data and feed_data['updated_at']:
        updated_at_dt = datetime.fromisoformat(feed_data['updated_at'])
        feed_data['updated_at_rfc822'] = formatdate(updated_at_dt.timestamp())
    else:
        # Fallback for older feeds without updated_at
        now_utc = datetime.now(timezone.utc)
        feed_data['updated_at_rfc822'] = formatdate(now_utc.timestamp())

    all_releases = []
    if 'artists' in feed_data:
        for artist in feed_data['artists']:
            releases = musicbrainz.get_artist_releases(artist['id'])
            all_releases.extend(releases)

    # Sort releases by date, newest first
    all_releases.sort(key=lambda r: r.get('date', '0000-00-00'), reverse=True)

    last_build_date = formatdate(datetime.now(timezone.utc).timestamp())
    
    rss_content = render_template('feed.xml', feed=feed_data, releases=all_releases, last_build_date=last_build_date)
    
    cache_dir = config.CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{feed_id}.xml")
    try:
        with open(cache_file, 'w') as f:
            f.write(rss_content)
        logger.debug(f"Cached feed '{feed_data['name']}' at {cache_file}")
    except IOError as e:
        logger.warning(f"Could not write feed '{feed_data['name']}' to cache file {cache_file}: {e}")

    return rss_content, {"Content-Type": "application/xml"}

@app.route("/health")
def health_check():
    logger.debug("Health check requested")
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

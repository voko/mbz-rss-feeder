import re
import musicbrainzngs
import logging
from .config import config
from datetime import datetime
from email.utils import formatdate

logger = logging.getLogger(__name__)

def init_musicbrainz():
    app_name = config.MB_APP_NAME
    version = config.MB_VERSION
    contact = config.MB_CONTACT

    logger.debug(f"Initializing MusicBrainz API with user agent: {app_name}/{version} ( {contact} )")
    musicbrainzngs.set_useragent(app_name, version, contact)

def search_artists(query):
    logger.debug(f"Searching for artists with query: '{query}'")
    try:
        result = musicbrainzngs.search_artists(query=query, limit=10)
        artists = []
        if 'artist-list' in result:
            for artist in result['artist-list']:
                artists.append({
                    'id': artist['id'],
                    'name': artist['name'],
                    'disambiguation': artist.get('disambiguation', '')
                })
        logger.debug(f"Found {len(artists)} artists for query: '{query}'")
        return artists
    except musicbrainzngs.MusicBrainzError as e:
        logger.error(f"MusicBrainz API error while searching for '{query}': {e}")
        return []

def _parse_release_date(release_date_str, release_title):
    """Parse a release date string which can be YYYY, YYYY-MM, or YYYY-MM-DD."""
    if not release_date_str:
        return None, None

    date_formats = ['%Y-%m-%d', '%Y-%m', '%Y']
    dt = None
    for fmt in date_formats:
        try:
            dt = datetime.strptime(release_date_str, fmt)
            if fmt == '%Y-%m':
                dt = dt.replace(day=1)
            elif fmt == '%Y':
                dt = dt.replace(month=1, day=1)
            break  # Found a valid format
        except (ValueError, TypeError):
            continue

    if dt:
        return dt, formatdate(dt.timestamp())
    
    logger.warning(f"Could not parse date format '{release_date_str}' for release '{release_title}'")
    return None, None

def _process_release(release, artist_id):
    """Process a single release from the MusicBrainz API response."""
    release_date = release.get('date', 'Unknown')
    _, pub_date = _parse_release_date(release_date, release['title'])

    links = {}
    if 'url-relation-list' in release:
        links = get_artist_relation_links(release['url-relation-list'])

    return {
        'artist': {
            'name': config.get_artist_name(artist_id),
            'id': artist_id,
        },
        'hasCoverArt': release.get('cover-art-archive', {}).get('artwork') == 'true',
        'id': release['id'],
        'title': release['title'],
        'date': release_date,
        'pub_date': pub_date,
        'release-group': release.get('release-group', {}),
        'links': links,
    }
def get_artist_meta_by_id(artist_id):
    """get additional meta data about an artist"""
    meta = {
        'links': {}
    }
    try:
        logger.debug(f"Fetching artist {artist_id} meta data")
        # Fetch artist data including URL relations
        result = musicbrainzngs.get_artist_by_id(artist_id, includes=["url-rels"])
        artist_data = result.get('artist', {})

        if 'url-relation-list' in artist_data:
            meta['links'] = get_artist_relation_links(artist_data['url-relation-list'])
        else:
            meta['links'] = None

        return meta

    except musicbrainzngs.WebServiceError as exc:
        logger.error(f"Error fetching artist {artist_id} meta data from MusicBrainz: {exc}")

    return meta

def get_artist_relation_links(relationlist):
    """Parse and extract named links from a MusicBrainz URL relation list."""
    links = {}
    for rel in relationlist:
        target = rel.get('target')
        if not target:
            continue
        if re.match(r'^https://([^/]+\.)?imdb\.com', target):
            links['IMDb'] = target
        elif re.match(r'^https://music\.apple\.com', target):
            links['apple'] = target
        elif re.match(r'^https://music\.amazon\.com', target):
            links['amazon'] = target
        elif re.match(r'^https://open\.spotify\.com', target):
            links['spotify'] = target
        elif re.match(r'^https://([^/]+\.)?qobuz\.com', target):
            links['qobuz'] = target
        elif re.match(r'^https://([^/]+\.)?deezer\.com', target):
            links['deezer'] = target
        elif re.match(r'^https://([^/]+\.)?beatport\.com', target):
            links['beatport'] = target
    return links

def get_artist_releases(artist_id):
    """Fetch releases for a given artist ID from MusicBrainz."""
    artist_name = config.get_artist_name(artist_id)
    logger.debug(f"Fetching releases for artist {artist_name} ({artist_id})")
    try:
        result = musicbrainzngs.browse_releases(
            artist=artist_id,
            release_type=['album'],
            includes=['release-groups', 'url-rels']
        )
        
        releases = []
        if 'release-list' in result:
            releases = [_process_release(r, artist_id) for r in result['release-list']]

        logger.debug(f"Found {len(releases)} releases for artist {artist_name} ({artist_id})")
        return releases
    except musicbrainzngs.MusicBrainzError as e:
        logger.error(f"MusicBrainz API error while fetching releases for artist '{artist_id}': {e}")
        return []

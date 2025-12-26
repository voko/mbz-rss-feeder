# MusicBrainz RSS Feeder
`mbz-rss-feeder`

## Overview
A small webserver that provides OPML, RSS and a minimal management UI to generate and manage feeds for artist release on 
[MusicBrainz](musicbrainz.org).

The OPML can be used to discover the current feeds. 
A feed lists all new releases for a group of artists.

## Web UI 
### Feeds and artists
You can manage feeds and artists in the web UI:
- create a new feed or delete a feed
- edit a feed: give it a name and manage the artists in the feed
  - add an artist
  - remove an artist

**Artist Search**

When adding an artist, the service will query the musicbrainz API for the given string and return a list of matching artists. 
The user can then click on the artist to add to the feed.

### Settings
In the settings page, you can
* set the number of days to look back (default: 90 days) 
* the caching time (default: 8 hours)

## Technical Features
### Persistence
These files should be mounted to persist the configuration.
* the feed and artist information is stored in `/var/mbz-rss-feeder/feeds.yml` 
* the service configuration is stored in `/etc/mbz-rss-feeder.yml`

Cached data is stored under `/var/mbz-rss-feeder/cache` but is not required to persist.

Updates to the configuration will also create a timestamped backup of the previous configuration.

### Persistence updates

### deployment
#### docker
This is a local container running with data stored in ./local/testdata 
`docker run \
  -p 8080:8080 -e LOG_LEVEL=debug --rm --name mbz-rss\
  -v ./local/testdata/:/var/mbz-rss-feeder \
  --env-file ./local/testdata/.env \
  docker.io/library/mzb-rss-feeder:1.0.0`

After startup the server can be accessed through http://docker-host:8080.

**Environment**
```bash
# User Agent for MusicBrainz API 
MB_APP_NAME=MinifluxRSSGenerator
MB_VERSION=2.0
MB_CONTACT=yourname@example.com
```

### Dependencies/Requirements
The pypi package musicbrainzngs is used to communicate with MusicBrainz.

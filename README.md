# Plex Media Reanalyzer

This project is a tool/webserver to trigger reanalyzing of media in a Plex Media Server library, because Plex does not provide this functionality through their API. Specifically the currently internal ratingkey ID needed to make the PUT to `analyze-media`` via Plex API.

This allows you to use powerful tools like [Tdarr](https://github.com/HaveAGitGat/Tdarr) to reorder audio streams, transcode, create new audio tracks for compatibility, and then have Tdarr send a webhook to this server with the Movie title in the body and the media will be reanlyzed by Plex picking up these changes.

## Installation

### Bare installation

1. Clone this repository:
   ```bash
   git clone https://github.com/brandon099/plex-media-reanalyzer.git
   ```

2. Navigate to the project directory:
   ```bash
   cd plex-media-reanalyzer
   ```
3. Install the required system dependencies (Required for webserver bjoern):
   
   Ubuntu:
   ```bash
   sudo apt install python3-dev libev-dev
   ``` 
   Alpine Linux:
   ```bash
   apk add gcc python3-dev libev-dev musl-dev
   ```

4. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ``` 

### Docker installation
This repository also builds a Docker image through Github Actions, and pushes it to the GitHub Container Registry. You can find the image here: https://github.com/brandon099/plex-media-reanalyzer/pkgs/container/plex-media-reanalyzer or by clicking on the Packages link in the side bar to the right.

You can pull the image like this:

```bash
docker pull ghcr.io/brandon099/plex-media-reanalyzer:latest
```

## Usage Examples
There are two run modes of this tool. Server mode and through commandline flags.

### Server Mode
Running plex-media-reanalyzer in server mode will listen for web requests to trigger reanalysis with the following command:

   ```bash
   python plex-media-reanalyzer.py --config config.yaml --listen
   ```

Then you can call it from another tool via a web request like the following. As you can see the request data (-d) is simply the title of the media you want to trigger a reanalyze in Plex.

To analyze by title:
   ```bash
   curl -X POST -H "Content-Type: application/json" -d '{"title": "The Matrix"}' http://localhost:8080/analyze_media
   ```
To analyze by filename (requires local DB to be loaded or synced with Plex):
   ```bash
   curl -X POST -H "Content-Type: application/json" -d '{"filename": "The.Matrix.1999.mkv"}' http://localhost:8080/analyze_media
   ```

To analyze by title and override the Library:
   ```bash
   curl -X POST -H "Content-Type: application/json" -d '{"filename": "The.Matrix.1999.mkv", "library_section": "Movies-4K"}' http://localhost:5000/analyze_media
   ```

#### Available endoints:
##### GET /
This returns an empty 200 for now

##### GET /health
This returns an empty 200. Useful for Kubernetes deployments.

##### POST /load_ratingkeys
This calls the `load_all_ratingkeys` function that calls Plex to get all rating keys (media IDs) from Plex and caches them to the local TinyDB JSON database, to reduce total calls to Plex. This is useful when you initially deploy or set this tool up, or on a recurring schedule.

##### POST /analyze_media
This calls the `analyze_media` function that in turn makes a PUT request to the Plex API to begin analyzing a media file. It will attempt to look up the rating key in the local DB file first, but if it is not present there it will first call Plex to retrieve it.

##### PUT /sync_db
This calls the `sync_db_with_plex` function that syncs the local cache DB with Plex, meaning it removes anything removed from Plex, and adds anything added to Plex but missing from the local cache DB.

### Commandline Mode

```bash
$ python3 plex_media_reanalyzer.py -h
usage: plex_media_reanalyzer.py [-h] [-c CONFIG] [-t MEDIA_TITLE] [-f MEDIA_FILENAME] [-d DB_PATH]
                                [-L LIBRARY_SECTION] (-l | -a | -m | -s)

Plex media reanalyzer.

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to the configuration file.
  -t MEDIA_TITLE, --media-title MEDIA_TITLE
                        Title of the media to analyze (required for --analyze-media and --load-ratingkey)
  -f MEDIA_FILENAME, --media-filename MEDIA_FILENAME
                        The filename of the media to analyze.
  -d DB_PATH, --db-path DB_PATH
                        Path to the database file.
  -L LIBRARY_SECTION, --library-section LIBRARY_SECTION
                        Library section to analyze (optional, allows you to override the configured library for one-
                        off to different libaries).
  -l, --listen          Start the web server.
  -a, --load-all-ratingkeys
                        Caches all rating keys to local DB. Useful for first run.
  -m, --analyze-media   Analyze media (requires --media-title or --media-filename).
  -s, --sync-db         Synchronize the database with Plex
```

Some example commands:

Start server mode at the commandline with custom config and DB paths:
```bash
python plex_media_reanalyzer.py -l -c /config/config.yaml -d /config/plex-media.db.json
```

Load all rating keys into local DB:
```bash
python plex_media_reanalyzer.py -a
```

Sync local DB with Plex (removes entries that have been removed from Plex and adds any new ones):
```bash
python plex_media_reanalyzer.py -s
```


Analyze a movie, by title:
```bash
python plex_media_reanalyzer -m -t "The Matrix"
```

Analyze a movie, by filename:
```bash
python plex_media_reanalyzer -m -f "The.Matrix.1999.mkv"
```

Analyze a movie, by filename with Library override:
```bash
python plex_media_reanalyzer -m -f "The.Matrix.1999.mkv" -L "Movies-4k"
```

## Configuration
The configuration can be done through the `config.yaml` file or through environment variables. The keys currently supported (for environment variable configuration, they are in all caps) are:

_**Required**_

`plex_server_url`: The URL of your Plex Media Server (e.g. http://plex.localhost:32400)

`plex_token`: Your Plex authentication token.

`library_section_name`: The name of the library section to target for media reanalysis. (e.g. Movies)

_Optional_

`webserver_port`: The port for the web server (default is 8080).

`auth_header`: The string to use to do basic HEADER auth for any requests to this tool's API. Optional, unless provided, then all requests except /health must have an auth header that matches.

`db_path`: Path to the TinyDB JSON file to cache media ratingkey and title (default is `./plex-media.db.json`)

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.

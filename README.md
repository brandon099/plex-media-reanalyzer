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

3. Install the required Python packages:
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

   ```bash
   curl -X POST -d "The Matrix" 0.0.0.0:8048/analyze_media
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

### Commandline Mode

```bash
$ python3 plex_media_reanalyzer.py -h
usage: plex_media_reanalyzer.py [-h] [-c CONFIG] [-t MEDIA_TITLE] (-l | -a | -m)

Plex media reanalyzer.

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to the configuration file.
  -t MEDIA_TITLE, --media-title MEDIA_TITLE
                        Title of the media to analyze (required for --analyze-media and --load-ratingkey)
  -l, --listen          Start the web server.
  -a, --load-all-ratingkeys
                        Caches all rating keys to local DB. Useful for first run.
  -m, --analyze-media   Analyze media (requires --media-title).
```

Some example commands:

Start server mode at the commandline:
```bash
python plex_media_reanalyzer.py -l
```

Load all rating keys into local DB:
```bash
python plex_media_reanalyzer.py -a
```

Analyze a movie:
```bash
python plex_media_reanalyzer -m -t "The Matrix"
```

## Configuration
The configuration can be done through the `config.yaml` file or through environment variables. The keys currently supported (for environment variable configuration, they are in all caps) are:

`plex_server_url`: The URL of your Plex Media Server (e.g. http://plex.localhost:32400)

`plex_token`: Your Plex authentication token.

`library_section_name`: The name of the library section to target for media reanalysis. (e.g. Movies)

`webserver_port`: The port for the web server (optional, default is 8080).

`auth_header`: The string to use to do basic HEADER auth for any requests to this tool's API. Optional, unless provided, then all requests must have an auth header that matches.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
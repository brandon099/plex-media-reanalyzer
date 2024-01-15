import argparse
import os
import requests
import yaml
from bottle import Bottle, request, abort
from plexapi.server import PlexServer
from tinydb import TinyDB, Query


webserver = Bottle()
db = TinyDB("plex-media.db.json")
Media = Query()


def load_config(config_file):
    """Loads configuration from config.yaml or environment variables."""
    config = {}

    # Try loading from config.yaml
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Config file {config_file} not found -- loading from "
              "environment variables.")
        pass

    # Override with environment variables
    env_vars = [
        "PLEX_SERVER_URL",
        "PLEX_TOKEN",
        "LIBRARY_SECTION_NAME",
        "AUTH_HEADER",
        "WEBSERVER_PORT",
    ]
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            config[var.lower()] = value

    # Ensure required values are present
    required_keys = ["plex_server_url", "plex_token", "library_section_name"]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Missing required configuration values:"
                         f"{', '.join(missing_keys)}")

    return config


def load_all_ratingkeys_from_plex():
    """Fetches all ratingKeys and titles from a specific library in Plex and
    stores them in the database."""

    plex = PlexServer(config["plex_server_url"], config["plex_token"])
    library_section = config["library_section_name"]
    results = plex.library.section(library_section)

    for item in results.all():
        media_data = {"ratingKey": item.ratingKey, "title": item.title}
        db.upsert(media_data, Media.ratingKey == item.ratingKey)

    print("Media data stored in embedded database successfully!")


def analyze_media(media_title):
    """Sends a PUT request to the Plex 'analyze' endpoint for a given title."""

    results = db.search(Media.title == media_title)

    if not results:
        print("Media title not found in local DB, attempting to get from Plex")
        load_ratingkey_from_title(media_title)
        results = db.search(Media.title == media_title)

    for item in results:
        ratingKey = item["ratingKey"]

        url = (f"{config['plex_server_url']}"
               f"/library/metadata/{ratingKey}/analyze")
        headers = {"X-Plex-Token": config["plex_token"]}

        try:
            response = requests.put(url, headers=headers)
            response.raise_for_status()
            print(f"Media '{media_title}' successfully sent for analysis!")
        except requests.exceptions.RequestException as e:
            print(f"Error sending request to analyze media: {e}")


def load_ratingkey_from_title(media_title):
    """Retrieves the ratingKey for a given title from Plex and saves it to the
       database. If more than one has the same title, it will return all to
       save in the DB."""

    plex = PlexServer(config["plex_server_url"], config["plex_token"])
    library_section = config["library_section_name"]
    media = plex.library.section(library_section)

    results = media.search(title=media_title)
    print(results)

    for item in results:
        db.upsert(
            {"ratingKey": item.ratingKey, "title": item.title},
            Media.ratingKey == item.ratingKey,
        )
        print(f"RatingKey for '{item.title}'\
                saved to database: {item.ratingKey}")


@webserver.post("/load_ratingkeys")
def load_ratingkeys_web_request():
    if config.get("auth_header"):
        auth_header = request.headers.get("Authorization")
        if auth_header != config.get("auth_header"):
            abort(401, "Unauthorized")

    load_all_ratingkeys_from_plex()
    return "Rating keys loaded from Plex!"


@webserver.post("/analyze_media")
def analyze_media_web_request():
    if config.get("auth_header"):
        auth_header = request.headers.get("Authorization")
        if auth_header != config.get("auth_header"):
            abort(401, "Unauthorized")

    media_title = request.body.read().decode("utf-8").strip()
    if not media_title:
        abort(400, "Missing title in request body")
    try:
        analyze_media(media_title)
        return "Media analysis triggered."
    except Exception as e:
        abort(500, f"Error analyzing media: {e}")


@webserver.get("/")
def index():
    return ""


@webserver.get("/health")
def health():
    return ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plex media reanalyzer.")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to the configuration file.",
    )
    parser.add_argument(
        "-t", "--media-title",
        help="Title of the media to analyze "
             "(required for --analyze-media and --load-ratingkey)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-l", "--listen",
        action="store_true",
        help="Start the web server.",
    )
    group.add_argument(
        "-a", "--load-all-ratingkeys",
        action="store_true",
        help="Caches all rating keys to local DB. Useful for first run.",
    )
    group.add_argument(
        "-m", "--analyze-media",
        action="store_true",
        help="Analyze media (requires --media-title).",
    )

    args = parser.parse_args()
    config = load_config(args.config)

    # Access configuration values
    plex_server_url = config["plex_server_url"]
    plex_token = config["plex_token"]
    library_section = config["library_section_name"]
    auth_header = config.get("auth_header")  # Optional, but if set, required.
    webserver_port = config.get("webserver_port", 8080)

    if args.listen:
        try:
            port = 8048
            webserver.run(server='bjoern', host='0.0.0.0', port=webserver_port)
        except KeyboardInterrupt:
            print("Stopping web server...")
    elif args.load_all_ratingkeys:
        load_all_ratingkeys_from_plex()
    elif args.analyze_media:
        if not args.media_title:
            parser.error("--media-title is required for --analyze-media")
        analyze_media(args.media_title)
    else:
        parser.error("No action specified")

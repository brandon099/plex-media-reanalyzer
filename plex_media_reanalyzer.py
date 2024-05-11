import argparse
import os
import requests
import yaml
from bottle import Bottle, request, abort
from functools import wraps
from plexapi.server import PlexServer
from tinydb import TinyDB, Query


webserver = Bottle()
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

    # Override with environment variables if they are provided
    env_vars = [
        "PLEX_SERVER_URL",
        "PLEX_TOKEN",
        "LIBRARY_SECTION_NAME",
        "AUTH_HEADER",
        "WEBSERVER_PORT",
        "DB_PATH",
    ]
    config.update({var.lower(): os.environ[var] for var in env_vars if os.environ.get(var)})

    # Ensure required values are present
    required_keys = ["plex_server_url", "plex_token", "library_section_name"]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Missing required configuration values:"
                         f"{', '.join(missing_keys)}")

    # If db_path is not present in the config, default to plex-media.db.json
    config["db_path"] = os.environ.get("DB_PATH", "plex-media.db.json")

    return config


def load_ratingkeys_from_plex(search_field=None, search_value=None, return_data=False):
    """Fetches ratingKeys, titles, and filename from a specific library in Plex and
    stores them in the database. If search_field and search_value are provided,
    only the matching media is fetched."""

    plex = PlexServer(config["plex_server_url"], config["plex_token"])
    library_section = config["library_section_name"]
    media = plex.library.section(library_section)

    if all([search_field, search_value]):
        results = media.search(**{search_field: search_value})
    else:
        results = media.all()

    if not results:
        print(f"No results found in Plex for {search_value}.")
        return

    plex_data = []
    for item in results:
        simple_filename = os.path.basename(item.media[0].parts[0].file)
        media_data = {"ratingKey": item.ratingKey, "title": item.title,
                      "fileName": simple_filename}
        db.upsert(media_data, Media.ratingKey == item.ratingKey)
        plex_data.append(media_data)

    if return_data:
        return plex_data
    else:
        print("Finished storing media data into database.")


def analyze_media(media_title=None, media_filename=None, library_section=None):
    """Sends a PUT request to the Plex 'analyze' endpoint for a given title or filename."""

    if not library_section:
        library_section = config["library_section_name"]

    search_field = 'title' if media_title else 'fileName'
    search_value = media_title or media_filename

    if not search_value:
        return "Please provide either a media title or a media filename."

    results = db.search(getattr(Media, search_field) == search_value)

    if not results:
        print(f"Media {search_field} not found in local DB, syncing with Plex")
        sync_db_with_plex()
        results = db.search(getattr(Media, search_field) == search_value)

    messages = []
    for item in results:
        ratingKey = item["ratingKey"]

        url = (f"{config['plex_server_url']}"
               f"/library/metadata/{ratingKey}/analyze")
        headers = {"X-Plex-Token": config["plex_token"]}

        try:
            response = requests.put(url, headers=headers)
            response.raise_for_status()
            messages.append(f"Media '{search_value}' successfully sent for analysis!")
        except requests.exceptions.RequestException as e:
            messages.append(f"Error sending request to analyze media: {e}")

    return messages


def sync_db_with_plex():
    """Synchronizes the TinyDB JSON database with the Plex server. It will
       remove any entries that do not exist in Plex anymore, and add/update
       entries that are not in sync in the database."""

    plex_data = load_ratingkeys_from_plex(return_data=True)
    db_data = db.all()

    if plex_data is not None:
        missing_keys = [item for item in db_data
                        if item["ratingKey"] not in
                        [data["ratingKey"] for data in plex_data]]
    else:
        missing_keys = []

    for item in missing_keys:
        db.remove(doc_ids=[item.doc_id])

    for item in plex_data:
        db.upsert(item, Media.ratingKey == item["ratingKey"])

    print("Synchronized database with Plex.")


def require_auth(f):
    """Decorator to require authentication for a web request."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if config.get("auth_header"):
            auth_header = request.headers.get("Authorization")
            if auth_header != config.get("auth_header"):
                abort(401, "Unauthorized")
        return f(*args, **kwargs)
    return decorated


@webserver.post("/load_ratingkeys")
@require_auth
def load_ratingkeys_web_request():
    """Loads all rating keys from Plex into the local database."""
    load_ratingkeys_from_plex()
    return "Rating keys loaded from Plex!"


@webserver.post("/analyze_media")
@require_auth
def analyze_media_web_request():
    """Triggers a media analysis in Plex."""
    request_data = request.json
    media_title = request_data.get('title')
    media_filename = request_data.get('filename')
    library_section = request_data.get('library_section')

    if not media_title and not media_filename:
        abort(400, "Missing title or filename in request body")

    try:
        if media_title:
            message = analyze_media(media_title=media_title, library_section=library_section)
        elif media_filename:
            message = analyze_media(media_filename=media_filename, library_section=library_section)
        return message
    except Exception as e:
        abort(500, f"Error analyzing media: {e}")


@webserver.put("/sync_db")
@require_auth
def sync_db_web_request():
    """Synchronizes the local database with Plex."""
    sync_db_with_plex()
    return "Database synchronized with Plex!"


@webserver.get("/")
@require_auth
def index():
    return ""


@webserver.get("/health")
def health():
    return "OK"


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
    parser.add_argument(
        "-f", "--media-filename",
        help="The filename of the media to analyze.",
    )
    parser.add_argument(
        "-d", "--db-path",
        default="plex-media.db.json",
        help="Path to the database file.",
    )
    parser.add_argument(
        "-L", "--library-section",
        help="Library section to analyze (optional, allows you to override "
             "the configured library for one-off to different libaries).",
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
        help="Analyze media (requires --media-title or --media-filename).",
    )
    group.add_argument(
        "-s", "--sync-db",
        action="store_true",
        help="Synchronize the database with Plex",
    )

    args = parser.parse_args()
    config = load_config(args.config)

    # Access configuration values
    db = TinyDB(config['db_path'])
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
        load_ratingkeys_from_plex()
    elif args.analyze_media:
        if not args.media_title and not args.media_filename:
            parser.error("--media-title or --media-filename is required for --analyze-media")
        if args.media_title and args.media_filename:
            parser.error("Only one of --media-title or --media-filename should be provided")
        if args.media_title:
            messages = analyze_media(media_title=args.media_title,
                                     library_section=args.library_section)
        elif args.media_filename:
            messages = analyze_media(media_filename=args.media_filename,
                                     library_section=args.library_section)
        for message in messages:
            print(message)
    elif args.sync_db:
        sync_db_with_plex()
    else:
        parser.error("No action specified")

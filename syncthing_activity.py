#!/usr/bin/env python3
"""Watches a Syncthing instance's activity."""

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import time
from types import TracebackType

import requests

__author__ = "Jan-Piet Mens <jp@mens.de>"
__copyright__ = "Copyright 2019 Jan-Piet Mens"
__license__ = "GNU General Public License"
__maintainer__ = "Arif Er <arifer612@pm.me>"
__status__ = "Development"
with open(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "VERSION"),
    "r",
    encoding="UTF-8",
) as version:
    __version__ = version.read().strip()


# Global variables
LAST_ID = 0
FOLDERS = {}
ARGS = argparse.Namespace()
UNKNOWN_ARGS = []


# Environment section
_SYNCTHING_URL = os.getenv("SYNCTHING_URL", "http://localhost:8384")
_SYNCTHING_API = os.getenv("SYNCTHING_API", "")
_HEADERS = {"X-API-Key": _SYNCTHING_API}


# argparse section
parser = argparse.ArgumentParser(
    description=(f"syncthing-activity {__version__}  ---  Watch a Syncthing server."),
)
parser.add_argument(
    "--event",
    type=str,
    nargs="?",
    const="ItemFinished",
    default="ItemFinished",
    help="Event API type. `ItemStarted' or `ItemFinished'.",
)
# Environment arguments
envs = parser.add_argument_group(
    "Environments", "Over-ride global environment variables."
)
envs.add_argument(
    "--url",
    type=str,
    default=f"{_SYNCTHING_URL}",
    help="Syncthing URL, defaults to http://localhost:8384. \
    Using the SYNCTHING_URL environment.",
)
envs.add_argument(
    "--api",
    type=str,
    default=f"{_SYNCTHING_API}",
    help="Syncthing API key. Using the SYNCTHING_API environment.",
)
# Script arguments
scripts = parser.add_argument_group("Scripts", "Run a script along the watcher.")
scripts.add_argument(
    "--script",
    type=str,
    nargs="?",
    const="",
    default="",
    help="Path to the script along with all the required arguments. \
    For example: post-processor.py positional_arg1 --option_1 option_arg_1",
)


# Logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s :: %(levelname)-8s :: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
handler.setFormatter(formatter)
logger.setLevel(logging.INFO)
logger.addHandler(handler)


def handle_exception(
    exc_type: type, exc_value: int, exc_traceback: TracebackType
) -> None:
    """Log any unexpected exceptions through the logger.

    Retrieved from https://stackoverflow.com/a/16993115
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.exception(
        "Unexpected exception", exc_info=(exc_type, exc_value, exc_traceback)
    )


def get_folders() -> None:
    """Retrieves folder labels and paths from Syncthing."""
    global FOLDERS

    FOLDERS = {}

    response = requests.get(f"{ARGS.url}/rest/system/config", headers=_HEADERS)
    data = json.loads(response.text)
    for folder in data["folders"]:
        FOLDERS[folder["id"]] = {
            "label": folder["label"],
            "path": folder["path"],
        }


def active_syncthing() -> bool:
    """Checks if Syncthing is active."""
    protocol, address = ARGS.url.split("://")
    if not address:
        protocol, address = "http", protocol

    if ":" in address:
        host, port = address.split(":")
    else:
        host = address
        try:
            port = socket.getservbyname(protocol)
        except OSError:
            port = 80

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, int(port)))
        sock.shutdown(2)
        return True
    except (ConnectionRefusedError, OSError):
        return False


def close_logger(exit_code: int) -> None:
    """Graciously closes the logger and ends the watcher.

    Args:
        exit_code: System exit code
    """
    logger.info("Ending syncthing-activity")
    logging.shutdown()
    sys.exit(exit_code)


def process(array: dict, args: argparse.Namespace, unknown_args: list) -> None:
    """Parses API results into usable information.

    With a script, a payload will be passed as a JSON dictionary. The structure
    of the payload is:
        {
      "time": Event time in ISO format YYYY-MM-DDThh:mm:ss.sTZD.
      "action": Event action (update, delete, metadata).
      "type": Data type (file, dir).
      "item": Relative path to item from folder root.
      "error": Sync error result (null, error message).
      "folder_label": Human readable folder label.
      "folder_id": Machine readable folder id.
      "path": Absolute path to item.
    }

    Args:
        array: Syncthing API response.
        args: This script's keyword and positional arguments.
        unknown_args: The remaining arguments not declared in parser and are to
    be passed into the external script.
    """
    global LAST_ID

    for event in array:
        if "type" in event and event["type"] == args.event:
            LAST_ID = event["id"]

            folder_id = event["data"]["folder"]
            if folder_id not in FOLDERS:  # Re-cache folder list
                get_folders()

            try:
                folder_label = FOLDERS[folder_id]["label"]
                folder_path = FOLDERS[folder_id]["path"]

                payload = {
                    "time": event["time"],
                    "action": event["data"]["action"],
                    "type": event["data"]["type"],
                    "item": event["data"]["item"],
                    "error": event["data"]["error"],
                    "folder_label": folder_label,
                    "folder_id": folder_id,
                    "path": os.path.join(folder_path, event["data"]["item"]),
                }

                logger.info(
                    "%(folder_label)15s %(type)-6s %(action)-10s %(item)s", payload
                )

                if args.script and args.script != "None":
                    # Note that syncs with errors will still make it here and
                    # need to be handled in external scripts by looking at the
                    # 'error' keyword of the payload.
                    main_call = [
                        sys.executable,
                        args.script,
                        "--payload",
                        json.dumps(payload, indent=4),
                    ]
                    if unknown_args:
                        main_call += unknown_args

                    subprocess.call(main_call)
            except KeyError:
                logger.warning(
                    "WARNING! Folder ID %s cannot be accessed. Skipping this.",
                    folder_id,
                )


def main(args: tuple = None) -> None:
    """Main execution block.

    Args:
        args: Tuple of known arguments declared in parser and the remaining
    unknown arguments.
    """
    global ARGS, UNKNOWN_ARGS, _HEADERS, LAST_ID

    sys.excepthook = handle_exception
    logger.info("Starting up syncthing-activity")

    ARGS, UNKNOWN_ARGS = args or parser.parse_known_args()

    if not ARGS.api:
        logger.error("Missing SYNCTHING_API in environment")
        close_logger(2)

    logger.info("Connecting to Syncthing hosted at %s", ARGS.url)

    if not active_syncthing():
        logger.info("Syncthing is not running. Stopping the watcher.")
        close_logger(127)

    _HEADERS = {"X-API-Key": ARGS.api}
    params = {
        "since": LAST_ID,
        "limit": None,
        "events": ARGS.event,
    }

    # Retrieve event ID when syncthing-activity starts up instead of starting
    # from 0 if possible.

    # Set the timeout to 5s to account for situations when Syncthing is just
    # started and do not have any recorded events matching ARGS.event.
    try:
        first_response = requests.get(
            f"{ARGS.url}/rest/events", headers=_HEADERS, params=params, timeout=5
        )
        if first_response.status_code == 200:
            LAST_ID = json.loads(first_response.content)[-1].get("id")
    except requests.exceptions.ConnectionError:
        # If timeout, then LAST_ID is 0 and needs not be changed.
        pass

    logger.info("Successfully connected to Syncthing")
    logger.info("%d %s events occurred in the past", LAST_ID, ARGS.event)
    logger.info("Starting watcher process")

    get_folders()

    while True:
        params = {
            "since": LAST_ID,
            "limit": None,
            "events": ARGS.event,
        }

        try:
            response = requests.get(
                f"{ARGS.url}/rest/events", headers=_HEADERS, params=params
            )

            if response.status_code == 200:
                process(json.loads(response.text), ARGS, UNKNOWN_ARGS)
            elif response.status_code != 304:
                time.sleep(60)
                continue
            time.sleep(10.0)

        except requests.exceptions.ChunkedEncodingError:
            # Check if Syncthing is restarted.
            time.sleep(10.0)
            if not active_syncthing():
                logger.info("Syncthing may not be running. Stopping the watcher.")
                close_logger(127)


if __name__ == "__main__":
    try:
        main(parser.parse_known_args())
    except KeyboardInterrupt:
        sys.stderr.write("\r")  # Clear ^C from showing
        close_logger(0)

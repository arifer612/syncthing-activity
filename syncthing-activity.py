#!/usr/bin/env python3
"""Watches a Syncthing instance's activity."""

import argparse
import json
import os
import subprocess
import sys
import time
import warnings

import requests

__author__ = "Jan-Piet Mens <jp@mens.de>"
__copyright__ = "Copyright 2019 Jan-Piet Mens"
__license__ = "GNU General Public License"
__maintainer__ = "Arif Er <arifer612@pm.me>"
__status__ = "Development"
with open(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "VERSION"),
        "r", encoding="UTF-8"
) as version:
    __version__ = version.read().strip()

# Global variables
LAST_ID = 0
FOLDERS = {}

# Environment section
_SYNCTHING_URL = os.getenv("SYNCTHING_URL", "http://localhost:8384")
_SYNCTHING_API = os.getenv("SYNCTHING_API")
_HEADERS = {"X-API-Key": _SYNCTHING_API}


# argparse section
parser = argparse.ArgumentParser(
    description=(f"""
    syncthing-activity {__version__}  ---  Watch a Syncthing server.
    """),
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
    Using the SYNCTHING_URL environemnt.",
)
envs.add_argument(
    "--api",
    type=str,
    default=f"{_SYNCTHING_API}",
    help="Syncthing API key. Using the SYNCTHING_API environment.",
)

# Script arguments
scripts = parser.add_argument_group(
    "Scripts", "Run a script along the watcher."
)
scripts.add_argument(
    "--script",
    type=str,
    nargs="?",
    const="",
    default="",
    help="Path to the script along with all the required arguments. \
    For example: post-processor.py positional_arg1 --option_1 option_arg_1"
)

ARGS = argparse.Namespace()
UNKNOWN_ARGS = []


def getfolders():
    """Retrieves folder labels and paths from Syncthing."""
    global FOLDERS

    FOLDERS = {}

    response = requests.get(f"{ARGS.url}/rest/system/config",
                            headers=_HEADERS)
    data = json.loads(response.text)
    for folder in data["folders"]:
        FOLDERS[folder["id"]] = {
            "label": folder["label"],
            "path": folder["path"],
        }


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

    Raises:
        ResourceWarning: If a new folder is created on Syncthing and cannot be
            updated here. Restarting the Syncthing instance may resolve this.
    """
    global LAST_ID

    for event in array:
        if "type" in event and event["type"] == args.event:
            LAST_ID = event["id"]

            folder_id = event["data"]["folder"]
            if folder_id not in FOLDERS:  # Re-cache folder list
                getfolders()

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

                print(
                    "{folder_label:>15} {type:<6s} {action:<10s} "
                    "{item}".format(**payload)
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
                warnings.warn(f"WARNING! Folder ID {folder_id} cannot be "
                              "accessed. Skipping this.", ResourceWarning)


def main(args: tuple = None) -> None:
    """Main execution block.

    Args:
        args: Tuple of known arguments declared in parser and the remaining
    unknown arguments.
    """
    global ARGS, UNKNOWN_ARGS, _HEADERS, LAST_ID

    ARGS, UNKNOWN_ARGS = args or parser.parse_known_args()

    if ARGS.api is None:
        print("Missing SYNCTHING_API in environment", file=sys.stderr)
        sys.exit(2)

    _HEADERS = {"X-API-Key": ARGS.api}
    params = {
        "since": LAST_ID,
        "limit": None,
        "events": ARGS.event,
    }

    # Retrieve event ID when syncthing-activity starts up instead of starting
    # from 0 if possible.
    first_response = requests.get(
        f"{ARGS.url}/rest/events", headers=_HEADERS, params=params
    )
    if first_response.status_code == 200:
        LAST_ID = json.loads(first_response.content)[-1].get("id")

    getfolders()

    while True:
        params = {
            "since": LAST_ID,
            "limit": None,
            "events": ARGS.event,
        }

        response = requests.get(
            f"{ARGS.url}/rest/events", headers=_HEADERS, params=params
        )
        if response.status_code == 200:
            process(json.loads(response.text), ARGS, UNKNOWN_ARGS)
        elif response.status_code != 304:
            time.sleep(60)
            continue
        time.sleep(10.0)


if __name__ == "__main__":
    try:
        main(parser.parse_known_args())
    except KeyboardInterrupt:
        sys.exit(0)

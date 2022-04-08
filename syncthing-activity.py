#!/usr/bin/env python3

import requests
import time
import json
import sys
import os
import argparse
import subprocess

__author__             = "Arif Er <arifer612@pm.me>"
__original_author__    = "Jan-Piet Mens <jp@mens.de>"
__copyright__          = "Copyright 2019 Jan-Piet Mens"
__license__            = "GNU General Public License"

last_id = 0
folders = {}

parser = argparse.ArgumentParser(description="Watch a Syncthing server")
parser.add_argument("event", default="ItemFinished", type=str, nargs="?",
                    help="Event API type. `ItemStarted' or `ItemFinished'")
parser.add_argument("--script", const="", default="", type=str, nargs="?",
                    help="Path to a script to run.")
parser.add_argument("--dry_run", action="store_true",
                    help="Perform a dry run")
parser.add_argument("--quiet", action="store_true",
                    help="Decrease verbosity")
args = argparse.Namespace()
unknown_args = []

def getfolders(data):

    global folders

    for f in data['folders']:
        folders[f["id"]] = {
            "label" : f["label"],
            "path"  : f["path"],
        }

def process(array, event_type, script, dry_run, quiet, unknown_args):

    global last_id

    for event in array:
        if "type" in event and event["type"] == event_type:
            last_id = event["id"]

            folder_id = event["data"]["folder"]
            folder_label = folders[folder_id]["label"]
            folder_path = folders[folder_id]["path"]

            path = os.path.join(folder_path, event["data"]["item"])
            time = event["time"]
            action = event["data"]["action"]
            data_type = event["data"]["type"]
            item = event["data"]["item"]

            if script and script != "None":
                main_call = ["/usr/bin/env", "python3", script,
                               folder_label, data_type, action, item]
                if True:
                    main_call.append("--dry_run")
                if quiet:
                    main_call.append("--quiet")
                if True:
                    main_call += unknown_args

                subprocess.call(main_call)

            else:
                e = {
                    "time"          : time,
                    "action"        : action,
                    "type"          : data_type,
                    "item"          : item,
                    "folder_label"  : folder_label,
                    "folder_id"     : folder_id,
                    "path"          : path,
                }

                # print(json.dumps(e, indent=4))  ## For debugging
                print("{folder_label:>15} {type:<5s} {action:<10s} {item}".format(**e))


def main(url, api, _args=None, _unknown_args=None):
    global args, unknown_args
    if _args:
        args, unknown_args = _args, _unknown_args
    else:
        args, unknown_args = parser.parse_known_args()

    headers = { "X-API-Key" : api }

    r = requests.get("{0}/rest/system/config".format(url), headers=headers)
    getfolders(json.loads(r.text))

    while True:

        params = {
            "since" : last_id,
            "limit" : None,
            "events" : args.event,
        }

        r = requests.get("{0}/rest/events".format(url), headers=headers, params=params)
        if r.status_code == 200:
            process(json.loads(r.text), args.event, args.script,
                    args.dry_run, args.quiet, unknown_args)
        elif r.status_code != 304:
            time.sleep(60)
            continue
        time.sleep(10.0)

if __name__ == "__main__":

    url = os.getenv("SYNCTHING_URL", "http://localhost:8384")
    api = os.getenv("SYNCTHING_API")
    if api is None:
        print("Missing SYNCTHING_API in environment", file=sys.stderr)
        exit(2)

    try:
        main(url, api, *parser.parse_known_args())
    except KeyboardInterrupt:
        exit(1)
    except:
        raise

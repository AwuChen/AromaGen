# Read compose.txt in aromagen/data/dialogue/, pull out just the human_input
# strings, and write them into one human_input.txt file.

'''
should build on human_input.txt and add the scent_usage so
as to allow for reproducibility of the code.
i should keep track of session_id/timestamp

plan:
-Extract the scent_sequence dict from compose.txt using a different
 out_path so as not to overwrite the human_input.txt file. 
 Then, for each scent_sequence, extract the scent_name values 
 and write them to a new file, scent_usage.csv, along with the 
 corresponding session_id and timestamp. This will allow for reproducibility of the code
and provide a clear record of the scent usage for each session.


One line per scent occurrence: session_id, timestamp, scent_name — 
so a session with 4 scents becomes 4 rows. More rows, but every row 
has the exact same shape, which makes Counter-ing scents corpus-wide,
 grouping by session, and grouping by day (parsed from timestamp) 
'''


import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPOSE_PATH = ROOT / "aromagen" / "data" / "dialogue" / "compose.txt"
OUT_PATH = COMPOSE_PATH.parent / "human_input.txt"
CSV_OUT_PATH = ROOT / "scent_usage.csv"

with open(COMPOSE_PATH, "r", encoding="utf-8") as infile, open(OUT_PATH, "w", encoding="utf-8") as outfile:
    for line in infile:
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        outfile.write(data["human_input"] + "\n")




with open(COMPOSE_PATH, "r", encoding="utf-8") as infile, open(CSV_OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["session_id", "timestamp", "scent_name"])
    writer.writeheader()

    for line in infile:
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        session_id = data.get("session_id")
        timestamp = data.get("timestamp")
        scent_sequence = data.get("response", {}).get("scent_sequence", [])
        for scent in scent_sequence:
            scent_name = scent.get("scent_name")
            if session_id and timestamp and scent_name:
                writer.writerow({"session_id": session_id, "timestamp": timestamp, "scent_name": scent_name})
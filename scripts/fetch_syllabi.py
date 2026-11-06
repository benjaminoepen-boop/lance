"""Download the public course sheets. They need no login: Nova serves them from a fixed address.

One request every 0.7 seconds, so the Nova server never notices. Files already on disk are skipped.

Run:  python3 scripts/fetch_syllabi.py seed/electives.csv seed/master_meetings.csv data/raw/syllabi
"""
import csv
import os
import sys
import time
import urllib.error
import urllib.request

URL = "https://apps.novasbe.pt/SigesAutomations/controlador?modo=FUC&CD_LECTIVO=202627&CD_DISCIP={code}&CD_DURACAO={term}"


def offerings(*csv_paths):
    found = set()
    for path in csv_paths:
        with open(path, encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if row["term"] in ("S1", "T1", "T2", "S2", "T3", "T4"):
                    found.add((row["code"], row["term"]))
    return sorted(found)


def main(electives, meetings, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    done = missing = 0
    for code, term in offerings(electives, meetings):
        path = os.path.join(out_dir, f"{code}_{term}.pdf")
        if os.path.exists(path) or os.path.exists(path + ".missing"):
            continue
        request = urllib.request.Request(URL.format(code=code, term=term), headers={"User-Agent": "lance-student-project"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
            if body[:4] == b"%PDF":
                with open(path, "wb") as file:
                    file.write(body)
                done += 1
            else:
                open(path + ".missing", "w").close()
                missing += 1
        except urllib.error.HTTPError:
            open(path + ".missing", "w").close()
            missing += 1
        except urllib.error.URLError as error:
            print("network problem, stopping:", error)
            break
        time.sleep(0.7)
    print("downloaded", done, "not published", missing)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])

"""Start over: `uv run python seed.py` rebuilds data/festival.db from seed/*.csv."""
import os

import db


def reset():
    """Throw away the saved lineup and build a fresh database: catalogue loaded, nothing booked, draft."""
    db.create_database()
    print("Rebuilt " + os.path.relpath(db.DB_PATH) + ": " + str(len(db.load_stages())) + " stages, "
          + str(len(db.load_artists())) + " artists, empty lineup, plan is a draft.")


# This block only runs when you type `uv run python seed.py`, not when tests import the file.
if __name__ == "__main__":
    reset()

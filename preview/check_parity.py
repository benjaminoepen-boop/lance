"""Compare the rules in the browser copy (lance-local.js) with logic.py on the same plans.

Runs both on three plans and compares the whole state and the course list.

Run:  uv run python preview/check_parity.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ["LANCE_DB"] = os.path.join(tempfile.mkdtemp(), "parity.db")

import db       # noqa: E402
import logic    # noqa: E402
sys.path.insert(0, HERE)
from build_preview import data_file  # noqa: E402

db.init_db()
logic.forget_catalogue()

PLANS = {
    "real": {"setup": {"programme": "Management", "semester": "Fall", "points": 165, "has_bonus": 0},
             "add": [["2459-S1-TXC", None], ["2581-S1-TXC", None], ["2966-T1-TXC", None], ["2463-T2-TXE", None],
                     ["2477-S1-TXB", 164], ["2477-S1-TXA", 164], ["2477-S1-TXC", 164], ["2277-T2-TXB", 1], ["2277-T2-TXA", 1], ["2652-S1-TXA", 33]],
             "alternate": ["2652-S1-TXA"]},
    "clashes": {"setup": {"programme": "Finance", "semester": "Fall", "points": 300, "has_bonus": 1},
                "add": [["2459-S1-TXC", 10], ["2175-S1-TXA", 400], ["2229-S1-TXG", 0], ["2229-S1-TXH", 50], ["2337-T1-TXA", 20], ["2352-T1-TXA", None], ["2337-T2-TXA", 5]],
                "alternate": []},
    "changes": {"setup": {"programme": "Management", "semester": "Fall", "points": 200, "has_bonus": 0},
                "add": [["2459-S1-TXB", None], ["2477-S1-TXC", 90], ["2477-S1-TXA", None], ["2277-T2-TXB", 12], ["2652-S1-TXA", 5]],
                "add_offering": [["2416-T1", 3], ["2229-S1", 20]],
                "alternate": ["2652-S1-TXA"], "switch": ["2477-S1-TXB", "2277-T2-TXA"], "remove_course": ["2229-S1"], "course_bid": [["2477-S1", 70]], "programme": "Finance"},
    "alternate_exam": {"setup": {"programme": "Management", "semester": "Fall", "points": 218, "has_bonus": 0},
                       "add": [["2329-T2-TXA", 20], ["2388-T2-TXA", 15], ["2277-T2-TXA", 88], ["2329-T1-TXA", None]], "alternate": ["2388-T2-TXA", "2277-T2-TXA"]},
    "spring": {"setup": {"programme": "Economics", "semester": "Spring", "points": 200, "has_bonus": 0},
               "add_offering": [["2477-S2", 100], ["2277-T3", 30], ["2206-S2", None]], "add": [], "alternate": []},
    "area": {"setup": {"programme": "Finance", "semester": "Fall", "points": 250, "has_bonus": 0, "area": "Financial Markets"},
             "add_offering": [["2218-T2", 30], ["2257-T1", 10], ["2240-T1", None]], "add": [], "alternate": []},
}


def python_side():
    out = {}
    for name, spec in PLANS.items():
        setup = spec["setup"]
        plan = db.load_plan(db.create_plan(setup["programme"], setup["semester"], setup["points"], bool(setup["has_bonus"])))
        if setup.get("area"):
            logic.update_settings(plan, setup["programme"], setup["semester"], setup["points"], bool(setup["has_bonus"]), area=setup["area"])
            plan = db.load_plan(plan["id"])
        for section_id, bid in spec["add"]:
            logic.add_to_plan(plan, section_id=section_id)
            item = [i for i in db.load_items(plan["id"]) if i["section_id"] == section_id][0]
            if bid is not None:
                logic.set_bid(plan, item["id"], bid)
        for offering_id, bid in spec.get("add_offering", []):
            logic.add_to_plan(plan, offering_id=offering_id)
            item = [i for i in db.load_items(plan["id"]) if i["offering_id"] == offering_id][0]
            if bid is not None:
                logic.set_bid(plan, item["id"], bid)
        for section_id in spec["alternate"]:
            item = [i for i in db.load_items(plan["id"]) if i["section_id"] == section_id][0]
            logic.move_item(plan, item["id"], list_name="alternate")
        for section_id in spec.get("switch", []):
            logic.switch_section(plan, section_id)
        for offering_id in spec.get("remove_course", []):
            removed, _ = logic.remove_course(plan, offering_id)
            logic.restore_items(plan, removed)
        for offering_id, bid in spec.get("course_bid", []):
            logic.set_course_bid(plan, offering_id, bid)
        if spec.get("programme"):
            logic.update_settings(plan, spec["programme"], setup["semester"], setup["points"], bool(setup["has_bonus"]))
        plan = db.load_plan(plan["id"])
        out[name] = {"state": logic.state_of(plan), "catalogue": logic.catalogue(plan)}
    return out


NODE = """
const fs = require('fs');
const [dataPath, plansPath, sourcePath] = process.argv.slice(2);
const data = fs.readFileSync(dataPath, 'utf8');
global.window = global;
window.fetch = async () => ({ json: async () => JSON.parse(data) });
global.localStorage = { getItem: () => null, setItem: () => {} };
global.Response = class { constructor(b) { this.b = b; } async json() { return JSON.parse(this.b); } };
eval(fs.readFileSync(sourcePath, 'utf8'));
(async () => {
  const L = window.__lanceLocal;
  await L.ready;
  const plans = JSON.parse(fs.readFileSync(plansPath, 'utf8'));
  const out = {};
  for (const [name, spec] of Object.entries(plans)) {
    const store = L.blank();
    L.settings(store, spec.setup);
    const errors = [];
    for (const [sectionId, bid] of spec.add) {
      errors.push(L.add(store, sectionId, null));
      const item = store.items.find((i) => i.section_id === sectionId);
      if (bid !== null && item) errors.push(L.setBid(store, item.id, bid));
    }
    for (const [offeringId, bid] of (spec.add_offering || [])) {
      errors.push(L.add(store, null, offeringId));
      const item = store.items.find((i) => i.offering_id === offeringId);
      if (bid !== null && item) errors.push(L.setBid(store, item.id, bid));
    }
    for (const sectionId of spec.alternate) {
      const item = store.items.find((i) => i.section_id === sectionId);
      L.move(store, item.id, 'alternate');
    }
    for (const sectionId of (spec.switch || [])) L.switchSection(store, sectionId);
    for (const offeringId of (spec.remove_course || [])) {
      const [removed] = L.removeCourse(store, offeringId);
      L.restoreItems(store, removed);
    }
    for (const [offeringId, bid] of (spec.course_bid || [])) L.setCourseBid(store, offeringId, bid);
    if (spec.programme) L.settings(store, { programme: spec.programme });
    out[name] = { state: L.stateOf(store, spec.today), catalogue: L.catalogue(store) };
  }
  process.stdout.write(JSON.stringify(out));
})();
"""


def normal(value):
    """Ignore what is only technical: database ids, key order, and 132 against 132.0."""
    if isinstance(value, dict):
        return {key: normal(item) for key, item in value.items() if key not in ("id", "plan_id", "created_at", "items", "offering_id_")} if "kind" in value and "first" in value else {key: normal(item) for key, item in value.items() if key not in ("id", "plan_id", "created_at")}
    if isinstance(value, list):
        return [normal(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, float):
        return round(value, 6)
    return value


def differences(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                yield f"{path}.{key}: only on one side ({'python' if key in a else 'browser'})"
            else:
                yield from differences(a[key], b[key], f"{path}.{key}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{path}: {len(a)} against {len(b)} entries"
        for index, (x, y) in enumerate(zip(a, b)):
            yield from differences(x, y, f"{path}[{index}]")
    elif a != b:
        yield f"{path}: {a!r} against {b!r}"


def main():
    with tempfile.TemporaryDirectory() as folder:
        data_path = os.path.join(folder, "data.json")
        plans_path = os.path.join(folder, "plans.json")
        node_path = os.path.join(folder, "run.cjs")
        from datetime import date
        for spec in PLANS.values():
            spec["today"] = date.today().isoformat()
        json.dump(data_file(), open(data_path, "w"))
        json.dump(PLANS, open(plans_path, "w"))
        open(node_path, "w").write(NODE)
        run = subprocess.run(["node", node_path, data_path, plans_path, os.path.join(HERE, "lance-local.js")], capture_output=True, text=True)
        if run.returncode:
            print(run.stderr[:800])
            sys.exit(1)
        browser = json.loads(run.stdout)
    python = json.loads(json.dumps(python_side()))
    total = 0
    for name in PLANS:
        for part in ("state", "catalogue"):
            found = list(differences(normal(python[name][part]), normal(browser[name][part]), f"{name}.{part}"))
            total += len(found)
            for line in found[:14]:
                print(line[:170])
    print("differences:", total)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()

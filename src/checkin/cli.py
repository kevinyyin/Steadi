"""`checkin serve | replay | seed`."""

import argparse
import json
import logging
import os
from datetime import date
from pathlib import Path

DATA = Path(os.environ.get("CHECKIN_DATA", "data"))
# Public demo (--demo): Guest can start a check-in right away, and nobody can add or edit people.
DEMO_PROFILE = {"age": 72, "sex": "female", "fallen": False, "unsteady": False, "worried": False}


def replay(path, age=None, sex=None):
    """Score every tagged step in a recording; with age and sex, also the STEADI flags."""
    from . import steadi
    from .signals import score_step
    from .store import read_recording

    rec = read_recording(path)
    if not rec.steps:
        raise SystemExit(f"{path}: no step tags; record a session with `checkin serve` first")
    t, acc, gyro = rec.data[:, 0], rec.data[:, 1:4], rec.data[:, 4:7]
    steps = {}
    for sid, (t_go, t_end) in sorted(rec.steps.items(), key=lambda kv: kv[1][0]):
        keep = (t >= t_go - 1.0) & (t <= t_end)
        steps[sid] = score_step(sid, t[keep], acc[keep], gyro[keep], t_go, t_end)
    out = {"file": str(path), "simulated": rec.simulated, "steps": steps}
    if "tug" in steps or "chair_stand" in steps:
        out["metrics"] = steadi.metrics_from_steps(steps)
        if age and sex:
            profile = {"age": age, "sex": sex}
            out["cutoffs"] = {"chair_stands": steadi.chair_norm(age, sex), "tug_s": steadi.TUG_CUTOFF_S,
                              "tandem_s": steadi.TANDEM_CUTOFF_S}
            out["flags"] = steadi.flags_for(profile, out["metrics"])
    return out


def validate(args):
    """Belt vs hand ground truth: write a template, or the agreement report (docs/VALIDATION.md)."""
    from . import report
    from . import validate as v

    truth = args.truth or DATA / "validation" / "ground_truth.csv"
    if args.template:
        added = v.write_template(args.recordings, truth)
        print(f"{truth}: added {added} rows from {args.recordings}/. Fill in the truth column, then run "
              f"`checkin validate {truth}`.")
        return
    if args.simulated:
        base = DATA / "validation" / "simulated"
        truth = v.make_simulated(base, seed=args.seed)
        print(f"Simulated: wrote recordings and made-up ground truth to {base}/")
    if not truth.exists():
        raise SystemExit(f"{truth} not found. Start one with `checkin validate --template {truth}`.")
    pairs = v.pair(truth, args.recordings)
    if not pairs:
        raise SystemExit(f"{truth}: no rows with a number in the truth column yet")
    stats = v.summarize(pairs, args.tol_time, args.tol_count)
    simulated = any(p["simulated"] for p in pairs)
    out = args.out or truth.parent / "report"
    files = report.write(out, pairs, stats, simulated, str(truth), png=not args.no_png)
    tag = " (Simulated)" if simulated else ""
    for s in stats.values():
        if not s["n"]:
            print(f"{s['label']}{tag}: none scored ({s['not_scored']} not scored)")
            continue
        agree = (f"{s['exact']}/{s['n']} exact, " if s["kind"] == "count" else "") + \
            f"{s['within']}/{s['n']} within ±{s['tol']:g} {s['unit']}"
        missed = f", {s['not_scored']} not scored" if s["not_scored"] else ""
        print(f"{s['label']}{tag}: {agree}; mean difference {s['bias']:+.2f} {s['unit']}, "
              f"typical error {s['mae']:.2f} {s['unit']}{missed}")
    print(f"Report: {files[0]}")


def serve(args):
    import uvicorn

    from .base import open_base
    from .clock import Clock
    from .controller import Controller
    from .seed import DAD_ID, seed_dad
    from .server import create_app
    from .sources import open_source
    from .store import Store

    store = Store(args.data)
    ids = {p["id"] for p in store.people()}
    if DAD_ID not in ids:
        seed_dad(store, date.today())
    guest = DEMO_PROFILE if args.demo else {"age": None, "sex": None, "fallen": False, "unsteady": False,
                                             "worried": False}
    if "guest" not in ids:
        store.create("Guest", dict(guest), pid="guest")
    elif args.demo:  # the public demo always starts ready to go, whatever a visitor did before a restart
        person = store.get("guest")
        person["profile"] = dict(guest)
        store.save(person)
    clock = Clock()
    source = open_source(args.source, clock, udp_port=args.udp_port)
    base = open_base(args.base, args.serial_port)
    app = create_app(Controller(source, base, store, clock), store, demo=args.demo)
    print(f"Dashboard: http://localhost:{args.port}  (source={args.source}, base={args.base})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="checkin", description="STEADI fall-risk screening check-in")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the session controller and dashboard")
    s.add_argument("--source", default="sim", help="sim | csv:<file> | udp | phyphox:<http://phone-ip:8080>")
    s.add_argument("--base", default="virtual", help="virtual | serial")
    s.add_argument("--serial-port", default=os.environ.get("CHECKIN_SERIAL_PORT"),
                   help="base station port, e.g. /dev/cu.usbmodem1101 or COM3 (env CHECKIN_SERIAL_PORT)")
    s.add_argument("--udp-port", type=int, default=int(os.environ.get("CHECKIN_UDP_PORT", "4210")),
                   help="port the belt broadcasts to (env CHECKIN_UDP_PORT, default 4210)")
    s.add_argument("--host", default="0.0.0.0", help="0.0.0.0 lets the tablet on the same network connect")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--data", type=Path, default=DATA)
    s.add_argument("--demo", action="store_true",
                   help="public demo: Guest is ready to start (age 72, female); adding or editing people is off")
    r = sub.add_parser("replay", help="score a recording made by `checkin serve`")
    r.add_argument("file", type=Path)
    r.add_argument("--age", type=int)
    r.add_argument("--sex", choices=["male", "female"])
    d = sub.add_parser("seed", help="rewrite the 'Simulated: Dad' history ending today")
    d.add_argument("--data", type=Path, default=DATA)
    v = sub.add_parser("validate", help="agreement between the belt and a stopwatch / hand count (docs/VALIDATION.md)")
    v.add_argument("truth", nargs="?", type=Path, help="ground-truth CSV (default data/validation/ground_truth.csv)")
    v.add_argument("--template", action="store_true", help="add a blank row to TRUTH for every recorded step")
    v.add_argument("--simulated", action="store_true",
                   help="generate simulated sessions with made-up ground truth, then report on them")
    v.add_argument("--recordings", type=Path, default=DATA / "recordings")
    v.add_argument("--out", type=Path, help="report folder (default: next to TRUTH, in report/)")
    v.add_argument("--tol-time", type=float, default=1.0, help="seconds counted as agreement (default 1.0)")
    v.add_argument("--tol-count", type=int, default=1, help="reps counted as agreement (default 1)")
    v.add_argument("--no-png", action="store_true", help="skip the PNG exports")
    v.add_argument("--seed", type=int, default=0, help="with --simulated: random seed")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "serve":
        serve(args)
    elif args.cmd == "replay":
        print(json.dumps(replay(args.file, args.age, args.sex), indent=2))
    elif args.cmd == "validate":
        validate(args)
    elif args.cmd == "seed":
        from .seed import seed_dad
        from .store import Store

        seed_dad(Store(args.data), date.today())
        print(f"Wrote {args.data / 'people' / 'sim-dad.json'}")


if __name__ == "__main__":
    main()

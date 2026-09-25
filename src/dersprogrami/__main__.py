"""Command line: python -m dersprogrami <command> ...

  solve PROJECT [--time SECONDS] [--minimal-change]   solve and save the timetable into the project
  check PROJECT                                        verify the project's timetable
  pdf PROJECT OUTDIR                                   write all PDFs
  app [PROJECT]                                        open the desktop application
"""
import argparse
import sys
from dataclasses import replace


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dersprogrami")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("solve")
    s.add_argument("project")
    s.add_argument("--time", type=float, default=120)
    s.add_argument("--minimal-change", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("project")
    pd = sub.add_parser("pdf")
    pd.add_argument("project")
    pd.add_argument("outdir")
    a = sub.add_parser("app")
    a.add_argument("project", nargs="?")
    args = ap.parse_args(argv)

    if args.cmd in (None, "app"):
        from .ui.app import run
        return run(getattr(args, "project", None))

    from .checker import check, quality
    from .model import ProjectFileError
    from .storage import load_project, save_project
    from .validate import errors

    try:
        project = load_project(args.project)
    except ProjectFileError as e:
        print(e, file=sys.stderr)
        return 2

    if args.cmd == "check":
        problems = [i.message for i in errors(project)] + check(project, project.placements)
        print("\n".join(problems) if problems else "Program geçerli.")
        q = quality(project, project.placements)
        print({k: v for k, v in q.items() if k != "details"})
        return 1 if problems else 0

    if args.cmd == "pdf":
        from .pdf import export_all
        for path in export_all(project, args.outdir):
            print(path)
        return 0

    from .explain import explain
    from .runner import SolverProcess
    bad = errors(project)
    if bad:
        print("\n".join(i.message for i in bad), file=sys.stderr)
        return 2
    job = SolverProcess(project, time_limit=args.time, minimal_change=args.minimal_change)
    job.start()
    last = 0.0
    while not job.finished:
        for elapsed, obj, bound, n in job.poll():
            if elapsed - last > 5 or n == 1:
                print(f"{elapsed:6.1f}s  çözüm {n}  puan {obj:.0f}  alt sınır {bound:.0f}")
                last = elapsed
        import time
        time.sleep(0.2)
    if job.error:
        print(job.error, file=sys.stderr)
        return 3
    r = job.result
    if not r.placements:
        print(f"Çözüm bulunamadı ({r.status}).")
        for line in explain(project).sentences:
            print(" -", line)
        return 1
    problems = check(project, r.placements)
    if problems:
        print("HATA: çözüm bağımsız denetimden geçemedi; kaydedilmedi.", *problems, sep="\n", file=sys.stderr)
        return 4
    save_project(replace(project, placements=r.placements), args.project)
    q = quality(project, r.placements)
    print(f"Kaydedildi ({r.status}, {r.elapsed:.0f} s). " + ", ".join(f"{k}={v}" for k, v in q.items() if k != "details"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

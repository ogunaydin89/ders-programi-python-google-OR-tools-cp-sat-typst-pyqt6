"""Run the solver in a separate process so the user interface can never freeze.

The child reports progress through a queue; "stop" asks it to finish with the best timetable so far,
and if it does not answer within a grace period it is killed.
"""
import multiprocessing as mp
import queue
import time
import traceback

from .solver import SolveOptions, solve

GRACE_SECONDS = 20


def _child(project, options: dict, messages, stop):
    try:
        opts = SolveOptions(**options, stop_event=stop,
                            on_progress=lambda *a: messages.put(("progress",) + a))
        messages.put(("done", solve(project, opts)))
    except BaseException:
        messages.put(("error", traceback.format_exc()))


class SolverProcess:
    def __init__(self, project, **options):
        ctx = mp.get_context("spawn")      # same behaviour on Windows and Linux
        self.messages = ctx.Queue()
        self.stop_event = ctx.Event()
        self.time_limit = options.get("time_limit", SolveOptions.time_limit)
        self.process = ctx.Process(target=_child, args=(project, options, self.messages, self.stop_event),
                                   daemon=True)
        self.started = None
        self.stop_requested = None
        self.result = None
        self.error = None

    def start(self):
        self.started = time.time()
        self.process.start()

    def request_stop(self):
        """Stop searching and keep the best timetable found so far."""
        if self.stop_requested is None:
            self.stop_requested = time.time()
        self.stop_event.set()

    def poll(self):
        """Return new progress messages; sets .result or .error when finished. Kills a stuck child."""
        out = []
        while True:
            try:
                msg = self.messages.get_nowait()
            except queue.Empty:
                break
            if msg[0] == "done":
                self.result = msg[1]
            elif msg[0] == "error":
                self.error = msg[1]
            else:
                out.append(msg[1:])
        now = time.time()
        deadline = self.started + self.time_limit + GRACE_SECONDS if self.started else None
        if self.stop_requested is not None:
            deadline = min(deadline or now, self.stop_requested + GRACE_SECONDS)
        if self.result is None and self.error is None and deadline and now > deadline:
            self.kill()
            self.error = "Çözücü zamanında yanıt vermedi ve durduruldu."
        if self.result is None and self.error is None and self.started and not self.process.is_alive():
            time.sleep(0.2)
            if self.messages.empty():
                self.error = "Çözücü beklenmedik şekilde kapandı."
        return out

    @property
    def finished(self):
        return self.result is not None or self.error is not None

    def kill(self):
        if self.process.is_alive():
            self.process.kill()
            self.process.join(5)

    def wait(self, poll_interval=0.2):
        while not self.finished:
            self.poll()
            time.sleep(poll_interval)
        self.process.join(5)
        return self.result

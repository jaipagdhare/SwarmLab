"""Process-wide Gemini pacing shared by connection checks and experiment phases."""
from threading import Lock
from time import monotonic, sleep


class RequestPacer:
    def __init__(self, interval=5.0, clock=monotonic, sleeper=sleep):
        self.interval, self.clock, self.sleeper = interval, clock, sleeper
        self.next_at = 0.0
        self.lock = Lock()

    def defer(self, seconds):
        with self.lock:
            self.next_at = max(self.next_at, self.clock() + seconds)

    def wait(self, deadline, cancelled=lambda: False, on_wait=None):
        while True:
            if cancelled():
                raise InterruptedError('cancelled')
            with self.lock:
                now = self.clock()
                if now >= deadline:
                    raise TimeoutError('rate_limit_wait_timeout')
                delay = max(0.0, self.next_at - now)
                if delay == 0:
                    self.next_at = now + self.interval
                    return
            if on_wait:
                on_wait(delay)
            self.sleeper(min(delay, 0.5, deadline-now))


GEMINI_PACER = RequestPacer()

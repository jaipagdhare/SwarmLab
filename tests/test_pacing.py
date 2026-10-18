import pytest
from swarmlab.pacing import RequestPacer


def setup():
    now = [0.0]
    def sleep(seconds): now[0] += seconds
    return now, RequestPacer(interval=10.0, clock=lambda: now[0], sleeper=sleep)


def test_requests_share_ten_second_spacing_and_cooldown():
    now, pacer = setup()
    starts=[]
    for _ in range(16):
        pacer.wait(200)
        starts.append(now[0])
    assert starts == [10*i for i in range(16)]
    assert max(sum(t <= x < t+60 for x in starts) for t in starts) == 6
    pacer.defer(60)
    pacer.wait(300)
    assert now[0] == 210


def test_wait_honors_deadline_and_cancellation():
    now, pacer = setup()
    pacer.defer(60)
    with pytest.raises(TimeoutError): pacer.wait(2)
    assert now[0] == 2
    with pytest.raises(InterruptedError): pacer.wait(100, cancelled=lambda: True)
    assert now[0] == 2

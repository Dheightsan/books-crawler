from crawler.ratelimit import HostLimiter


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, secs):
        self.slept.append(secs)
        self.now += secs


def test_waits_per_host():
    clock = FakeClock()
    lim = HostLimiter(1.0, clock=clock, sleep=clock.sleep)
    lim.wait("https://a.test/1")
    assert clock.slept == []
    clock.now += 0.25
    lim.wait("https://a.test/2")
    assert clock.slept == [0.75]
    lim.wait("https://b.test/1")
    assert clock.slept == [0.75]


def test_no_wait_after_delay_passed():
    clock = FakeClock()
    lim = HostLimiter(1.0, clock=clock, sleep=clock.sleep)
    lim.wait("https://a.test/1")
    clock.now += 5
    lim.wait("https://a.test/2")
    assert clock.slept == []

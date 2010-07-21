#!/usr/bin/python

import random
import re
import sys
import time
import urlparse
import operator
import cPickle as pickle

class Counter:
    def __init__(self):
        self.counters = []

    def add(self, generation):
        need_counters = generation + 1 - len(self.counters)
        self.counters += [0] * need_counters

        if generation > 0 and self.counters[generation-1] > 0:
            self.counters[generation-1] -= 1
        self.counters[generation] += 1

    def dump(self):
        print "Generations: %d" % len(self.counters)
        print "Histogram:"
        for i in range(len(self.counters)):
            if self.counters[i] > 0:
                print "%d: %d" % (i, self.counters[i])

    def count(self):
        return reduce(operator.__add__, self.counters)

class TestClient:
    def __init__(self):
        self.generation = 0

    def test(self): return True

    def increment(self):
        gen = self.generation
        self.generation += 1
        return gen

class RandomFailureClient(TestClient):
    def __init__(self, error_rate):
        """0 < error_rate <= 100"""

        TestClient.__init__(self)
        self.error_rate = error_rate

    def test(self):
        if random.randint(0,100) > self.error_rate:
            return True
        return False

class Simulator:
    def __init__(self):
        self.clients = []
        self.counter = Counter()

    def iterate(self, n=1):
        for i in range(n):
            for client in self.clients:
                if client.test():
                    self.counter.add(client.increment())
def test():
    sim = Simulator()

    # add 50 clients which randomly fail from 0-50% of the time
    sim.clients.extend([RandomFailureClient(random.randint(0,50)) for i in range(50)])

    # run for 100 iterations
    sim.iterate(100)

    # add 20 clients which always succeed
    sim.clients.extend(TestClient() for i in range(20))

    # run for 25 iterations
    sim.iterate(25)

    # add 30 clients which were incrementing but not phoning home until now
    stale_clients = [TestClient() for i in range(30)]
    for iteration in range(30):
        for client in stale_clients:
            client.increment()
    sim.clients.extend(stale_clients)

    # run for 25 iterations
    sim.iterate(25)

    # add 30 clients which were randomly incrementing but not phoning home until now
    stale_clients = [RandomFailureClient(random.randint(0,50)) for i in range(30)]
    for iteration in range(30):
        for client in stale_clients:
            if client.test():
                client.increment()
    sim.clients.extend(stale_clients)

    # run for 25 iterations
    sim.iterate(25)

    sim.counter.dump()
    assert sim.counter.count() == len(sim.clients)

class State:
    '''State of the entire system'''

    def __init__(self):
        '''Initialize an empty state'''

        self.channel_map = {}
        self.last_time = 0

    def load(self, path):
        '''Load state from a file'''

        f = open(path)
        (self.channel_map, self.last_time) = pickle.load(f)
        f.close()

    def update_from_log(self, path):
        '''Update status from Apache log.
        
        This will only include items which are newer than the last timestamp.
        '''
        census_re = re.compile('\d+\.\d+\.\d+\.\d+[\s-]+\[(.+?) [-+]\d{4}\] "GET /census\?([^\s"]+)')

        for line in open(path):
            m = census_re.match(line)
            if not m:
                continue
            timestamp = time.mktime(time.strptime(m.group(1), '%d/%b/%Y:%H:%M:%S'))
            if timestamp <= self.last_time:
                print 'ignoring previously seen line', line
                continue

            args = urlparse.parse_qs(m.group(2))
            try:
                dcd = args['dcd'][0]
                assert len(dcd) > 0
                count = int(args['count'][0])
            except (TypeError, ValueError, KeyError):
                print 'ERROR! Invalid census query:', m.group(2)
                continue
                
            #print 'timestamp: %f (%s), DCD: %s, count: %i' % (timestamp, m.group(1), dcd, count)

            self.channel_map.setdefault(dcd, Counter()).add(count)

    def dump(self):
        for channel, counter in self.channel_map.iteritems():
            print '---- %s ---' % channel
            print 'machines:', counter.count()
            print 'hist:', counter.counters

def main():
    if len(sys.argv) != 2:
        print >> sys.stderr, 'Usage: "%s <path to apache log>" or "%s -t"' % (
                sys.argv[0], sys.argv[0])
        sys.exit(1)

    if sys.argv[1] == '-t':
        test()
        sys.exit(0)

    state = State()
    state.update_from_log(sys.argv[1])
    state.dump()

if __name__ == '__main__':
    main()

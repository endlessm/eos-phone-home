#!/usr/bin/python

import random
import re
import sys
import time
import os
import os.path
import urlparse
import operator
import optparse
import sqlite3 as dbapi2
import subprocess
import tempfile

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

class Simulator:
    def __init__(self):
        self.clients = []
        self.counter = Counter()

    def iterate(self, n=1):
        for i in range(n):
            for client in self.clients:
                if client.test():
                    self.counter.add(client.increment())

    def test(self):
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

        # add 50 clients which randomly fail from 0-50% of the time
        self.clients.extend([RandomFailureClient(random.randint(0,50)) for i in range(50)])

        # run for 100 iterations
        self.iterate(100)

        # add 20 clients which always succeed
        self.clients.extend(TestClient() for i in range(20))

        # run for 25 iterations
        self.iterate(25)

        # add 30 clients which were incrementing but not phoning home until now
        stale_clients = [TestClient() for i in range(30)]
        for iteration in range(30):
            for client in stale_clients:
                client.increment()
        self.clients.extend(stale_clients)

        # run for 25 iterations
        self.iterate(25)

        # add 30 clients which were randomly incrementing but not phoning home until now
        stale_clients = [RandomFailureClient(random.randint(0,50)) for i in range(30)]
        for iteration in range(30):
            for client in stale_clients:
                if client.test():
                    client.increment()
        self.clients.extend(stale_clients)

        # run for 25 iterations
        self.iterate(25)

        self.counter.dump()
        assert self.counter.count() == len(self.clients)

class State:
    '''State of the entire system'''

    def __init__(self, dbpath):
        '''Initialize state from a database
        
        If the db does not exist yet, it will be created.
        '''
        init = not os.path.exists(dbpath)
        self.db = dbapi2.connect(dbpath)

        if init:
            cur = self.db.cursor()
            cur.execute('''CREATE TABLE db_version (
                version INT NOT NULL)''')

            cur.execute('''CREATE TABLE last_update (
                timestamp DOUBLE NOT NULL)''')

            cur.execute('''CREATE TABLE counters (
                channel CHAR(100) PRIMARY KEY,
                counters TEXT)''')

            cur.execute('''CREATE TABLE history (
                channel CHAR(100),
                date CHAR(12),
                day INT NOT NULL,
                count INT NOT NULL,
                PRIMARY KEY (channel, date))''')

            cur.execute('INSERT INTO db_version VALUES (0)')
            cur.execute("INSERT INTO last_update VALUES (0.0)")

            self.db.commit()

    def update_from_log(self, path):
        '''Update status from Apache log.
        
        This will only include items which are newer than the last timestamp.
        '''
        census_re = re.compile('\d+\.\d+\.\d+\.\d+[\s-]+\[(.+?) [-+]\d{4}\] "GET /census\?([^\s"]+).*?" 2\d\d')

        cur = self.db.cursor()
        cur.execute('SELECT timestamp FROM last_update')
        last_update = cur.fetchone()[0]

        channel_counters = self._counters_from_db()
        stats = self._current_stats()

        for line in open(path):
            m = census_re.match(line)
            if not m:
                continue
            timestamp = time.mktime(time.strptime(m.group(1), '%d/%b/%Y:%H:%M:%S'))
            if timestamp <= last_update:
                #print 'ignoring previously seen line', line
                continue
            last_update = max(timestamp, last_update)

            args = urlparse.parse_qs(m.group(2))
            try:
                dcd = args['dcd'][0]
                assert len(dcd) > 0
                count = int(args['count'][0])
            except (TypeError, ValueError, KeyError):
                print 'ERROR! Invalid census query:', m.group(2)
                continue
                
            #print 'timestamp: %f (%s), DCD: %s, count: %i' % (timestamp, m.group(1), dcd, count)

            channel_counters.setdefault(dcd, Counter()).add(count)

            date = time.strftime('%Y-%m-%d', time.localtime(timestamp))
            st = stats.setdefault(dcd, {}).setdefault(date, [0,0])
            st[0] += 1
            st[1] = channel_counters[dcd].count()

        cur.execute('DELETE FROM last_update')
        cur.execute('INSERT INTO last_update VALUES (?)', (last_update,))
        self._counters_to_db(channel_counters)
        self._set_current_stats(stats)
        self.db.commit()

    def dump(self):
        #print '====== COUNTERS ========'
        #for channel, counter in self._counters_from_db().iteritems():
        #    print '---- %s ---' % channel
        #    print 'machines:', counter.count()
        #    print 'hist:', counter.counters

        cur = self.db.cursor()
        cur.execute('SELECT DISTINCT channel FROM history')
        channels = [x[0] for x in cur.fetchall()]
        #print '====== HISTORY ========'
        for ch in channels:
            print '---- channel: %s -----' % ch
            cur.execute('SELECT date, day, count FROM history WHERE channel = ? ORDER BY date', 
                    (ch,))
            for (date, day, count) in cur:
                print '%s: %4i updates sent, %4i machines total' % (date, day, count)

    def plot(self, directory):
        '''Generate gnuplot charts.

        This will create <channel>.png files in given output directory.
        '''

        cur = self.db.cursor()
        cur.execute('SELECT DISTINCT channel FROM history')
        channels = [x[0] for x in cur.fetchall()]

        for ch in channels:
            gnuplot = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)
            print >> gnuplot.stdin, '''set xdata time
set timefmt "%Y-%m-%d"
set terminal png
'''
            f = tempfile.NamedTemporaryFile()
            cur.execute('SELECT date, day, count FROM history WHERE channel = ? ORDER BY date', 
                    (ch,))
            for (date, day, count) in cur:
                print >> f, '%s\t%i\t%i' % (date, day, count)

            f.flush()

            print >> gnuplot.stdin, 'set out "%s.png"\nset title "%s"' % (
                    os.path.join(directory, ch), ch)
            #print >> gnuplot.stdin, 'set multiplot'
            print >> gnuplot.stdin, 'set yrange [0:]'
            print >> gnuplot.stdin, '''
plot "%s" using 1:2 title "#updates on that day" with impulses lw 10 lt 3 , \
     "%s" using 1:3 title "#machines" with linespoints lw 4 lt 1''' % (f.name, f.name)

            print >> gnuplot.stdin, 'exit'
            assert gnuplot.wait() == 0, 'gnuplot failed with %i' % gnuplot.returncode

    def _counters_from_db(self):
        '''Return a channel->Counter map from DB.'''

        counters = {}
        cur = self.db.cursor()
        cur.execute('SELECT * FROM counters')
        for channel, counter_str in cur:
            counters[channel] = Counter()
            counters[channel].counters = eval(counter_str, {}, {})

        return counters

    def _counters_to_db(self, map):
        '''Write channel->Counter map to DB.'''

        cur = self.db.cursor()
        cur.execute('DELETE FROM counters')
        for (channel, counters) in map.iteritems():
            cur.execute('INSERT INTO counters VALUES (?, ?)', (channel,
                    repr(counters.counters)))

    def _current_stats(self):
        '''Get most recent per-day/counter stats.

        Return channel->date->[day, count] map.
        '''
        cur = self.db.cursor()
        cur.execute('SELECT timestamp FROM last_update')
        last_update = time.strftime('%Y-%m-%d',
                time.localtime(float(cur.fetchone()[0])))

        map = {}
        cur.execute('SELECT channel, day, count FROM history WHERE date = ?',
                (last_update,))
        for (channel, day, count) in cur:
            map.setdefault(channel, {})[last_update] = [day, count]

        return map

    def _set_current_stats(self, stats):
        '''Set most recent per-day/counter stats.'''

        cur = self.db.cursor()
        for channel, per_date in stats.iteritems():
            for date, (day, count) in per_date.iteritems():
                cur.execute('INSERT OR REPLACE INTO history VALUES (?, ?, ?, ?)',
                        (channel, date, day, count))

def parse_args():
    '''Parse command line args.

    Return (options, args) tuple.
    '''

    parser = optparse.OptionParser()
    parser.add_option('-t', '--test', dest='test', action='store_true',
            help='Run simulator for testing the algorithm')
    parser.add_option('-d', '--database', dest='database', metavar='PATH',
            help='Path to database')
    parser.add_option('-l', '--log', dest='logfile', metavar='PATH',
            help='Update data with Apache log file.')
    parser.add_option('-g', '--gnuplot', dest='gnuplot', metavar='DIR',
            action='store', help='Generate graphs to given output directory')

    (opts, args) = parser.parse_args()

    if not opts.test:
        if not opts.database:
            parser.error('ERROR: You need to specify a database with --database.  See --help')

    return (opts, args)

def main():
    (opts, args) = parse_args()

    if opts.test:
        Simulator().test()
        sys.exit(0)

    state = State(opts.database)

    if opts.logfile:
        state.update_from_log(opts.logfile)
        state.dump()

    if opts.gnuplot:
        state.plot(opts.gnuplot)

if __name__ == '__main__':
    main()

"""Read Linux memory, swap activity and KSM counters without changing the host."""

import datetime
import json
import os
from pathlib import Path
import time


def counters(path):
    return {line.split()[0]: int(line.split()[1])
            for line in Path(path).read_text().splitlines() if len(line.split()) == 2}


def pressure():
    path = Path('/proc/pressure/memory')
    if not path.exists():
        return None
    return {line.split()[0]: {key: float(value) for key, value in
                             (field.split('=') for field in line.split()[1:])}
            for line in path.read_text().splitlines()}


def sample(seconds=5):
    page_size = os.sysconf('SC_PAGE_SIZE')
    first = counters('/proc/vmstat')
    start = time.monotonic()
    time.sleep(seconds)
    elapsed = time.monotonic() - start
    last = counters('/proc/vmstat')
    memory = {line.split(':')[0]: int(line.split()[1]) * 1024
              for line in Path('/proc/meminfo').read_text().splitlines()
              if len(line.split()) >= 2 and line.split()[1].isdigit()}
    root = Path('/sys/kernel/mm/ksm')
    ksm = {}
    for name in ('run', 'pages_shared', 'pages_sharing', 'pages_unshared',
                 'pages_volatile', 'ksm_zero_pages', 'general_profit', 'full_scans',
                 'pages_scanned', 'sleep_millisecs', 'pages_to_scan'):
        path = root / name
        if path.exists():
            ksm[name] = int(path.read_text().strip())
    gross = (ksm.get('pages_sharing', 0) + ksm.get('ksm_zero_pages', 0)) * page_size
    enrolled = sum(ksm.get(name, 0) for name in
                   ('pages_shared', 'pages_sharing', 'pages_unshared'))
    return {
        'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'read_only': True,
        'sample_seconds': round(elapsed, 3),
        'memory_bytes': {
            'total': memory['MemTotal'], 'available': memory['MemAvailable'],
            'free': memory['MemFree'],
            'swap_total': memory['SwapTotal'],
            'swap_used': memory['SwapTotal'] - memory['SwapFree'],
        },
        'swap_bytes_per_second': {
            'in': round((last['pswpin'] - first['pswpin']) * page_size / elapsed, 2),
            'out': round((last['pswpout'] - first['pswpout']) * page_size / elapsed, 2),
        },
        'ksm': ksm,
        'ksm_gross_saved_bytes': gross,
        'ksm_net_saved_bytes': ksm.get('general_profit'),
        'ksm_saved_percent_of_enrolled_pages':
            round(100 * ksm.get('pages_sharing', 0) / enrolled, 2) if enrolled else None,
        'memory_pressure': pressure(),
        'load_average': list(os.getloadavg()),
        'logical_cpus': os.cpu_count(),
    }


if __name__ == '__main__':
    print(json.dumps(sample()))

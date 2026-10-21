"""Bounded synthetic queue lab. No network clients or production integrations."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
import platform
import queue
import resource
import tempfile
import threading
import time


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def estimates(machines=50, hz=1, event_bytes=512, days=90, replicas=1,
              overhead=1.5, fn=10, fp=20, hours=1, inspection_eur=50, infra_eur=100):
    """Decimal bytes; hypothetical counts must refer to one common evaluation period."""
    values = (machines, hz, event_bytes, days, replicas, overhead, fn, fp, hours,
              inspection_eur, infra_eur)
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('finite nonnegative assumptions required')
    raw = machines * hz * 86400 * days * event_bytes
    return {'raw_bytes': raw, 'provisioned_bytes': raw * (1 + replicas) * overhead,
            'expected_cost_eur': fn * hours * 1200 + fp * inspection_eur + infra_eur,
            'assumptions': dict(zip(('machines', 'events_per_machine_s', 'event_bytes',
                'days', 'replicas', 'storage_overhead', 'FN', 'FP', 'downtime_hours_per_FN',
                'inspection_eur_per_FP', 'infra_eur_per_period'), values))}


def run(rate, duration, workers, capacity=16, service_ms=10, fail_every=17):
    """Each run owns a temporary sink and bounded queue; losses retained for replay."""
    if not (1 <= rate <= 1000 and 0 < duration <= 5 and workers in (1, 4)
            and 1 <= capacity <= 64 and 0 <= service_ms <= 100 and fail_every >= 0):
        raise ValueError('lab bounds exceeded')
    count = int(rate * duration)
    if count < 1:
        raise ValueError('at least one event required')
    pending = queue.Queue(capacity)
    lock = threading.Lock()
    latencies, retry, ids = [], [], set()
    highwater = failures = duplicates = 0
    cpu_start = time.process_time()
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='cg23-') as directory:
        sink = open(os.path.join(directory, 'events.jsonl'), 'w', encoding='utf-8')

        def consume():
            nonlocal failures, duplicates
            while True:
                item = pending.get()
                try:
                    if item is None:
                        return
                    ident, scheduled = item
                    time.sleep(service_ms / 1000)
                    with lock:
                        if fail_every and (ident + 1) % fail_every == 0:
                            failures += 1
                            retry.append(ident)
                        else:
                            duplicates += ident in ids
                            ids.add(ident)
                            sink.write(json.dumps({'id': ident, 'payload': 'x' * 128}) + '\n')
                            latencies.append((time.perf_counter() - scheduled) * 1000)
                finally:
                    pending.task_done()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(consume) for _ in range(workers)]
            for ident in range(count):
                scheduled = start + ident / rate
                time.sleep(max(0, scheduled - time.perf_counter()))
                try:
                    pending.put_nowait((ident, scheduled))
                    highwater = max(highwater, pending.qsize())
                except queue.Full:
                    retry.append(ident)
            pending.join()
            elapsed = time.perf_counter() - start
            for _ in futures:
                pending.put(None)
            for future in futures:
                future.result()
        successful = len(ids)
        # Replay rejected/failed IDs once, then deliberately duplicate them: local ID gate.
        for ident in retry + retry:
            if ident in ids:
                duplicates += 1
                continue
            ids.add(ident)
            sink.write(json.dumps({'id': ident, 'payload': 'x' * 128}) + '\n')
        sink.close()
        disk_bytes = os.path.getsize(sink.name)
        with open(sink.name, encoding='utf-8') as source:
            records = [json.loads(line)['id'] for line in source]
        return dict(rate_events_s=rate, offered=count, offered_duration_s=duration,
            workers=workers, queue_capacity=capacity, service_delay_ms=service_ms,
            injected_failure_every=fail_every, initial_success=successful,
            initial_failure=failures, rejected=len(retry)-failures,
            drain_elapsed_s=elapsed, throughput_success_s=successful/elapsed,
            p50_end_to_end_ms=percentile(latencies, .5), p95_end_to_end_ms=percentile(latencies, .95),
            max_queue_events=highwater, replay_candidates=len(retry), duplicate_attempts_blocked=duplicates,
            final_missing=count-len(set(records)), final_duplicate_rows=len(records)-len(set(records)),
            sink_bytes=disk_bytes, cpu_process_s=time.process_time()-cpu_start,
            process_peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = {'scope': 'synthetic in-process queue and temporary JSONL sink; not pipeline capacity',
        'base_commit': '28a7754', 'script_sha256': hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
        'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                        'logical_cpus': os.cpu_count(), 'rss_scope': 'whole process lifetime, Linux KiB'},
        'runs': [run(rate, 1, workers) for rate in (25, 100, 250) for workers in (1, 4)],
        'estimates': [estimates(hours=h, days=d) for h in (.5, 1, 2) for d in (7, 30, 90)]}
    with open(args.output, 'x', encoding='utf-8') as target:
        json.dump(result, target, indent=2)
        target.write('\n')


if __name__ == '__main__':
    main()

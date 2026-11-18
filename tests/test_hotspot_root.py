"""Exercise the real shell's ownership, DNS and teardown logic with fake Android commands.

These tests do not prove kernel forwarding or OEM hotspot compatibility.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "service/src/main/assets/hotspot-sharing.sh"
MOCK = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
p = pathlib.Path(os.environ['MOCK_STATE'])
s = json.loads(p.read_text())
name = pathlib.Path(sys.argv[0]).name
a = sys.argv[1:]
s['calls'].append([name] + a)
code = 0
out = ''
if name == 'id': out = os.environ.get('MOCK_UID', '0')
elif name == 'getprop': out = os.environ.get('MOCK_SDK', '35')
elif name == 'settings':
    if a[0] == 'get':
        out = s['offload']
        if os.environ.get('MOCK_FAIL_SETTINGS'): code = 1
    elif a[0] == 'put': s['offload'] = a[-1]
    elif a[0] == 'delete': s['offload'] = 'null'
elif name == 'dumpsys': out = '  wlan1 - TetheredState - lastError = 0'
elif name == 'sleep': time.sleep(0.03)
elif name in ('iptables', 'ip6tables'):
    if a[:1] == ['-w']: a = a[2:]
    table = 'filter'
    if a[:1] == ['-t']: table, a = a[1], a[2:]
    op, chain = a[:2]
    key = name + ':' + table + ':' + chain
    if op == '-S': code = 0 if key in s['chains'] else 1
    elif op == '-N': s['chains'].append(key)
    elif op == '-X':
        if key in s['chains']: s['chains'].remove(key)
    elif op in ('-A', '-I'):
        if os.environ.get('MOCK_FAIL_DNS') and 'DNAT' in a: code = 1
elif name == 'ip':
    if a[:4] == ['-o', '-4', 'addr', 'show']:
        if 'dev' in a:
            addr = (p.parent / 'address').read_text()
            out = '8: wlan1    inet ' + addr + ' scope global wlan1'
        else:
            out = '9: tun9    inet 172.19.0.1/30 scope global tun9'
    elif a == ['-4', 'rule', 'show']:
        out = '\n'.join(' '.join(r) for r in s['rules'])
    elif a[:3] == ['-4', 'rule', 'add']: s['rules'].append(a[3:])
    elif a[:3] == ['-4', 'rule', 'del']:
        if a[3:] in s['rules']: s['rules'].remove(a[3:])
        else: code = 1
    elif a[:3] == ['-4', 'route', 'replace']: s['routes'].append(a[3:])
    elif a[:3] == ['-4', 'route', 'flush']: s['routes'] = []
    elif a[:3] == ['-4', 'route', 'show']: out = '\n'.join(' '.join(r) for r in s['routes'])
p.write_text(json.dumps(s))
if out: print(out)
sys.exit(code)
'''


class HotspotRootTest(unittest.TestCase):
    def run_session(self, extra_env=None, expected_exit=0, active=True, stale_boot=False,
                    next_address=None, existing_rules=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'state.json'
            existing_rules = existing_rules or []
            state.write_text(json.dumps(dict(calls=[], chains=[], rules=existing_rules, routes=[], offload='0')))
            address = root / 'address'
            address.write_text('192.168.43.1/24')
            binary = root / 'mock'
            binary.write_text(MOCK)
            binary.chmod(0o755)
            for name in ('ip', 'iptables', 'ip6tables', 'getprop', 'id', 'dumpsys', 'settings', 'sleep'):
                (root / name).symlink_to(binary)
            for name in ('lo', 'wlan1', 'tun9'):
                (root / 'net' / name).mkdir(parents=True)
            (root / 'boot-id').write_text('new-boot')
            if stale_boot:
                (root / 'hotspot-root.lock').mkdir()
                (root / 'hotspot-root.lock/boot').write_text('old-boot')
            script = root / 'run.sh'
            script.write_text(SCRIPT.read_text().replace('/sys/class/net/', str(root / 'net') + '/')
                              .replace('/proc/sys/kernel/random/boot_id', str(root / 'boot-id')))
            lease = root / 'active.lease'
            lease.touch()
            env = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'], MOCK_STATE=str(state))
            env.update(extra_env or {})
            proc = subprocess.Popen(['sh', str(script), str(os.getpid()), str(lease), ''],
                                    env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            output = []
            timeout = threading.Timer(20, proc.kill)
            timeout.start()
            try:
                for line in proc.stdout:
                    output.append(line)
                    if 'Rules installed' in line:
                        if next_address:
                            address.write_text(next_address)
                            next_address = None
                        else:
                            lease.unlink()
                self.assertEqual(proc.wait(timeout=15), expected_exit, ''.join(output))
            finally:
                timeout.cancel()
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
                proc.stdout.close()
            s = json.loads(state.read_text())
            self.assertEqual(any('Rules installed' in l for l in output), active, ''.join(output))
            self.assertEqual(s['chains'], [])
            self.assertEqual(s['rules'], existing_rules)
            self.assertEqual(s['routes'], [])
            self.assertEqual(s['offload'], '0')
            self.assertFalse((root / 'hotspot-root.lock').exists())
            return s

    def test_share_dns_ipv6_and_teardown(self):
        s = self.run_session(stale_boot=True)
        calls = [' '.join(c) for c in s['calls']]
        self.assertTrue(any('DNAT --to-destination 172.19.0.2:53' in c for c in calls))
        self.assertTrue(any('ip6tables -w 3 -A CMFA_HS_6 -i wlan1 -j DROP' in c for c in calls))
        self.assertTrue(any('priority 20663 iif wlan1 lookup 17963' in c for c in calls))

        adds = [c for c in calls if c.startswith('ip -4 rule add') and 'iif tun9' in c]
        self.assertEqual(adds, ['ip -4 rule add priority 20663 iif tun9 to 192.168.43.0/24 lookup 17963'])

    def test_subnet_change_on_same_interface(self):
        s = self.run_session(next_address='192.168.19.191/26')
        calls = [' '.join(c) for c in s['calls']]
        old = 'ip -4 rule del priority 20663 iif tun9 to 192.168.43.0/24 lookup 17963'
        new = 'ip -4 rule add priority 20663 iif tun9 to 192.168.19.128/26 lookup 17963'
        self.assertLess(calls.index(old), calls.index(new))
        self.assertIn('ip -4 route replace 192.168.19.128/26 dev wlan1 table 17963', calls)

    def test_existing_rule_protects_empty_reserved_table(self):
        s = self.run_session(expected_exit=1, active=False,
                             existing_rules=[['1000:', 'from', 'all', 'lookup', '17963']])
        self.assertFalse(any(c[:3] == ['ip', '-4', 'route'] and 'flush' in c for c in s['calls']))

    def test_offload_read_failure_releases_lock(self):
        self.run_session({'MOCK_FAIL_SETTINGS': '1'}, expected_exit=1, active=False)

    def test_android_10_priority(self):
        s = self.run_session({'MOCK_SDK': '29'})
        self.assertTrue(any('17663' in c for c in s['calls']))

    def test_root_denied_does_not_change_network(self):
        s = self.run_session({'MOCK_UID': '2000'}, expected_exit=1, active=False)
        self.assertFalse(any(c[0] in ('ip', 'iptables', 'ip6tables', 'settings') for c in s['calls']))

    def test_partial_failure_rolls_back(self):
        self.run_session({'MOCK_FAIL_DNS': '1'}, expected_exit=1, active=False)


if __name__ == '__main__':
    unittest.main()

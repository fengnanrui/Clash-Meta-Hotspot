"""Exercise the real shell's ownership, DNS and teardown logic with fake Android commands.

These tests do not prove kernel forwarding or OEM hotspot compatibility.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
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
    if a[0] == 'get': out = s['offload']
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
        out = '9: tun9    inet 172.19.0.1/30 scope global tun9' if 'dev' not in a else '8: wlan1    inet 192.168.43.1/24 scope global wlan1'
    elif a[:4] == ['-o', '-4', 'route', 'show']: out = '192.168.43.0/24 proto kernel scope link src 192.168.43.1'
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
    def run_session(self, extra_env=None, expected_exit=0, active=True, stale_boot=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'state.json'
            state.write_text(json.dumps(dict(calls=[], chains=[], rules=[], routes=[], offload='0')))
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
            try:
                for line in proc.stdout:
                    output.append(line)
                    if 'Rules installed' in line:
                        lease.unlink()
                self.assertEqual(proc.wait(timeout=15), expected_exit, ''.join(output))
            finally:
                proc.kill() if proc.poll() is None else None
                proc.stdout.close()
            s = json.loads(state.read_text())
            self.assertEqual(any('Rules installed' in l for l in output), active, ''.join(output))
            self.assertEqual(s['chains'], [])
            self.assertEqual(s['rules'], [])
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

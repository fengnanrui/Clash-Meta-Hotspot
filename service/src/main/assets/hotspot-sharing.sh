#!/system/bin/sh
# Private to CMFA Hotspot. Do not flush system chains or system routing tables.
set -eu
OWNER_PID=$1
LEASE=$2
OVERRIDE=${3:-}
TABLE=17963
PRIORITY=17663
[ "$(getprop ro.build.version.sdk)" -lt 31 ] || PRIORITY=20663
F=CMFA_HS_F
N=CMFA_HS_N
D=CMFA_HS_D
V6=CMFA_HS_6
LOCK="${LEASE%/*}/hotspot-root.lock"
IFACES=""
TUN=""
OLD_OFFLOAD=""
OWNED=0
say() { echo "CMFA_STATUS: $*"; }
fail() { say "Failed / 失败: $*"; exit 1; }
valid_iface() {
    case "$1" in ''|*[!a-zA-Z0-9_.-]*) return 1;; esac
    [ "${#1}" -le 15 ] && [ -d "/sys/class/net/$1" ]
}
ipt() { iptables -w 3 "$@"; }
ip6t() { ip6tables -w 3 "$@"; }
clear_routes() {
    for i in $IFACES; do
        while ip -4 rule del priority "$PRIORITY" iif "$i" lookup "$TABLE" 2>/dev/null; do :; done
    done
    if [ -n "$TUN" ]; then
        while ip -4 rule del priority "$PRIORITY" iif "$TUN" lookup "$TABLE" 2>/dev/null; do :; done
    fi
    ip -4 route flush table "$TABLE" 2>/dev/null || true
}
cleanup() {
    set +e
    [ "$OWNED" = 1 ] || return 0
    clear_routes
    ipt -D FORWARD -j "$F" 2>/dev/null
    ipt -t nat -D POSTROUTING -j "$N" 2>/dev/null
    ipt -t nat -D PREROUTING -j "$D" 2>/dev/null
    ip6t -D FORWARD -j "$V6" 2>/dev/null
    ipt -F "$F"; ipt -X "$F"
    ipt -t nat -F "$N"; ipt -t nat -X "$N"
    ipt -t nat -F "$D"; ipt -t nat -X "$D"
    ip6t -F "$V6"; ip6t -X "$V6"
    if [ "$(settings get global tether_offload_disabled)" = 1 ]; then
        if [ "$OLD_OFFLOAD" = null ]; then settings delete global tether_offload_disabled >/dev/null
        else settings put global tether_offload_disabled "$OLD_OFFLOAD"; fi
    fi
    rm -f "$LOCK/boot"
    rmdir "$LOCK"
    say "Stopped; rules cleaned / 已停止并清理共享规则"
}
[ "$(id -u)" = 0 ] || fail "root required"
[ -f "$LEASE" ] && kill -0 "$OWNER_PID" 2>/dev/null || exit 0
case "$OVERRIDE" in *[!a-zA-Z0-9_.-]*) fail "invalid interface name";; esac
[ "${#OVERRIDE}" -le 15 ] || fail "invalid interface name"
# Wait briefly for an earlier service session's lease watchdog to finish cleanup.
attempt=0
BOOT=$(cat /proc/sys/kernel/random/boot_id)
until mkdir "$LOCK" 2>/dev/null; do
    if [ -f "$LOCK/boot" ] && [ "$(cat "$LOCK/boot")" != "$BOOT" ]; then
        rm -f "$LOCK/boot"
        rmdir "$LOCK" || fail "stale session lock cannot be removed"
        continue
    fi
    attempt=$((attempt + 1))
    [ "$attempt" -lt 10 ] || fail "previous session still running; restart phone if force-killed"
    sleep 1
done
echo "$BOOT" > "$LOCK/boot"
# Refuse to overwrite unknown state; all changes below are owned by this session.
if [ -n "$(ip -4 route show table "$TABLE" 2>/dev/null)" ] ||
   ipt -S "$F" >/dev/null 2>&1 || ipt -t nat -S "$N" >/dev/null 2>&1 ||
   ipt -t nat -S "$D" >/dev/null 2>&1 || ip6t -S "$V6" >/dev/null 2>&1; then
    rm -f "$LOCK/boot"
    rmdir "$LOCK"
    fail "reserved routing state is occupied; reboot to clear stale rules"
fi
OLD_OFFLOAD=$(settings get global tether_offload_disabled)
OWNED=1
trap cleanup EXIT
trap 'exit 0' HUP INT TERM
ipt -N "$F"
ipt -t nat -N "$N"
ipt -t nat -N "$D"
ip6t -N "$V6"
ipt -I FORWARD 1 -j "$F"
ipt -t nat -I POSTROUTING 1 -j "$N"
ipt -t nat -I PREROUTING 1 -j "$D"
ip6t -I FORWARD 1 -j "$V6"
settings put global tether_offload_disabled 1
say "Waiting for hotspot / 等待热点；若热点已经开启，请关闭后重新开启热点"
LAST=""
while [ -f "$LEASE" ] && kill -0 "$OWNER_PID" 2>/dev/null; do
    # Match our established VpnService address instead of guessing tun0 or selecting another VPN.
    NEXT_TUN=$(ip -o -4 addr show | awk '$4 == "172.19.0.1/30" {print $2; exit}')
    if [ -n "$OVERRIDE" ]; then
        NEXT_IFACES=$OVERRIDE
    else
        # AOSP IpServer.dump prints "<iface> - TetheredState - ...".
        NEXT_IFACES=$({ dumpsys tethering; dumpsys connectivity; } 2>/dev/null |
            sed -n 's/^[[:space:]]*\([^[:space:]]*\) - TetheredState.*/\1/p' | sort -u)
    fi
    READY=""
    for i in $NEXT_IFACES; do
        valid_iface "$i" || continue
        [ "$i" != "$NEXT_TUN" ] && [ "$i" != lo ] || continue
        ip -o -4 addr show dev "$i" | grep -q ' inet ' || continue
        READY="$READY $i"
    done
    KEY="$NEXT_TUN:$READY"
    if [ "$KEY" != "$LAST" ]; then
        clear_routes
        ipt -F "$F"; ipt -t nat -F "$N"; ipt -t nat -F "$D"; ip6t -F "$V6"
        IFACES=$READY
        TUN=$NEXT_TUN
        # IPv6 is intentionally blocked on shared interfaces while this IPv4 feature is active.
        for i in $IFACES; do
            ip6t -A "$V6" -i "$i" -j DROP
            if [ -n "$TUN" ]; then ipt -A "$F" -i "$i" -o "$TUN" -j ACCEPT; fi
            ipt -A "$F" -i "$i" -j DROP
        done
        if [ -n "$TUN" ] && [ -n "$IFACES" ]; then
            ip -4 route replace default dev "$TUN" table "$TABLE"
            for i in $IFACES; do
                CIDR=$(ip -o -4 route show dev "$i" scope link | awk '$1 ~ /\// {print $1; exit}')
                [ -n "$CIDR" ] || fail "no connected IPv4 route for $i"
                ip -4 route replace "$CIDR" dev "$i" table "$TABLE"
                # Only NAT hotspot clients; phone-originated traffic retains normal VPN behavior.
                ipt -t nat -A "$N" -s "$CIDR" -o "$TUN" -j MASQUERADE
                for proto in udp tcp; do
                    ipt -t nat -A "$D" -i "$i" -p "$proto" --dport 53 -j DNAT --to-destination 172.19.0.2:53
                done
                ipt -I "$F" 1 -i "$TUN" -o "$i" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
                ip -4 rule add priority "$PRIORITY" iif "$i" lookup "$TABLE"
            done
            ip -4 rule add priority "$PRIORITY" iif "$TUN" lookup "$TABLE"
            say "Rules installed / 共享规则已启用: $IFACES -> $TUN (IPv4). 请用连接设备验证出口 IP"
        else
            say "Waiting for VPN/hotspot / 等待 VPN 或热点接口"
        fi
        LAST=$KEY
    fi
    sleep 3
done

import socket, ipaddress, time, re, sys, subprocess
import psutil
from typing import List, Dict, Tuple, Optional

MAC_RE = re.compile(r"(?i)([0-9A-F]{2}[:-]){5}[0-9A-F]{2}")
MODEL_HINTS = ["U6", "U7", "UAP", "USW", "UDM", "UXG", "UAP-AC", "nanoHD", "Flex", "Lite", "Pro", "Enterprise"]

def _is_windows():
    return sys.platform.startswith("win")

def local_ipv4_interfaces() -> List[Tuple[str, str, str]]:
    """Return list of (ifname, ip, netmask) for active non-loopback IPv4 interfaces."""
    out = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    for ifname, ifaddrs in addrs.items():
        st = stats.get(ifname)
        if not st or not st.isup:
            continue
        for a in ifaddrs:
            if a.family == socket.AF_INET:
                ip = a.address or ""
                mask = a.netmask or ""
                if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                    continue
                if not mask:
                    continue
                out.append((ifname, ip, mask))
    return out

def broadcast_addrs() -> List[str]:
    bcasts = set()
    for _if, ip, mask in local_ipv4_interfaces():
        try:
            net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
            bcasts.add(str(net.broadcast_address))
        except Exception:
            continue
    # Always include global broadcast as a last resort
    bcasts.add("255.255.255.255")
    return list(bcasts)

def _guess_model(text: str) -> Optional[str]:
    for hint in MODEL_HINTS:
        if hint.lower() in text.lower():
            return hint
    return None

def _arp_lookup(ip: str) -> Optional[str]:
    try:
        if _is_windows():
            cmd = ["arp", "-a", ip]
        else:
            cmd = ["arp", "-n", ip]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2).decode(errors="ignore")
        m = MAC_RE.search(out)
        if m:
            return m.group(0).replace("-", ":").lower()
    except Exception:
        pass
    return None

def ubnt_discover(timeout: float = 2.0) -> List[Dict]:
    """Send several UBNT discovery probes on UDP/10001 broadcast and collect replies.
    Heuristically parses replies to extract mac/model when present.
    Returns list of dicts: {'ip','mac','model','raw'}
    """
    probes = [
        b"\x01\x00\x00\x00",           # v1 simple probe
        b"UBNT",                           # legacy tag
        b"\x02\x00\x00\x00UBNT",       # v2-ish
        b"",                               # some firmwares answer empty
    ]
    addrs = broadcast_addrs()
    seen = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.2)
        s.bind(("", 0))
        port = 10001
        # Fire probes
        for bcast in addrs:
            for p in probes:
                try:
                    s.sendto(p, (bcast, port))
                except Exception:
                    continue
        # Collect replies up to timeout
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                data, addr = s.recvfrom(8192)
            except socket.timeout:
                continue
            except Exception:
                break
            ip = addr[0]
            raw = data or b""
            text = raw.decode(errors="ignore")
            mac = None
            m = MAC_RE.search(text)
            if m:
                mac = m.group(0).replace("-", ":").lower()
            model = None
            # look for explicit markers
            for key in ("model=", "device:", "platform:", "board=", "board name=", "hw="):
                i = text.lower().find(key)
                if i >= 0:
                    frag = text[i:i+64]
                    # split on whitespace or delimiters
                    parts = re.split(r"[\s,;]", frag)
                    if parts:
                        cand = parts[0].split("=",1)[-1].strip()
                        if cand and len(cand) < 32:
                            model = cand
                            break
            if not model:
                model = _guess_model(text) or ""
            if not mac:
                mac = _arp_lookup(ip) or ""
            if ip not in seen:
                seen[ip] = {"ip": ip, "mac": mac or "", "model": model or "", "raw": text}
        return list(seen.values())
    finally:
        try:
            s.close()
        except Exception:
            pass

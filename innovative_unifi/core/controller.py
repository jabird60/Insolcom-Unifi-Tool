import requests
from typing import List, Dict, Optional
import paramiko

class ControllerClient:
    def __init__(self, store, log_bus=None):
        self.store = store
        self.log = (log_bus.log if log_bus else (lambda s: None))
        self.base = (store.get_value("controller_url") or "https://127.0.0.1:8443").rstrip("/")
        self.inform_url = (store.get_value("inform_url") or self.base).rstrip("/")
        self.user = store.get_value("controller_user") or ""
        self.pw = store.get_value("controller_pass") or ""
        self.ssh_user = store.get_value("ssh_user") or "ubnt"
        self.ssh_pass = store.get_value("ssh_pass") or "ubnt"
        self.sess = requests.Session()
        self.sess.verify = bool(store.get_value("verify_ssl") or False)
        self.sess.headers.update({
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "InnovativeSolutions-UnifiGUI"
        })

    # ----- helpers -----
    def _host_root(self) -> str:
        try:
            from urllib.parse import urlparse
            u = urlparse(self.base)
            return f"{u.scheme}://{u.netloc}"
        except Exception:
            try:
                return self.base.split("//",1)[0] + "//" + self.base.split("//",1)[1].split("/",1)[0]
            except Exception:
                return self.base

    def _u(self, path: str, proxy_first: bool = True) -> str:
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        root = self._host_root()
        if proxy_first:
            return f"{root}/proxy/network{path}"
        return f"{root}{path}"

    def _j(self, r):
        try:
            return r.json()
        except Exception:
            return {}

    # ----- auth -----
    def login(self) -> bool:
        # Reset headers
        for h in ("X-CSRF-Token", "Authorization"):
            self.sess.headers.pop(h, None)
        self.sess.headers.setdefault("X-Requested-With", "XMLHttpRequest")
        self.sess.headers.setdefault("Referer", self.base)

        # UniFi OS CSRF preflight
        try:
            r = self.sess.get(self._u("/api/auth/csrf", proxy_first=True), timeout=10)
            if r.ok and r.headers.get("content-type","").startswith("application/json"):
                j = r.json()
                token = (j.get("csrfToken") or j.get("csrf_token") or j.get("token"))
                if token:
                    self.sess.headers["X-CSRF-Token"] = token
        except Exception:
            pass

        # UniFi OS login
        try:
            r = self.sess.post(self._u("/api/auth/login", proxy_first=True),
                               json={"username": self.user, "password": self.pw, "remember": True},
                               timeout=15)
            if r.ok:
                return True
        except Exception:
            pass

        # UniFi OS w/o preflight
        try:
            r = self.sess.post(self._u("/api/auth/login", proxy_first=True),
                               json={"username": self.user, "password": self.pw},
                               timeout=15)
            if r.ok:
                return True
        except Exception:
            pass

        # Legacy form
        try:
            r = self.sess.post(self._u("/api/login", proxy_first=False),
                               data={"username": self.user, "password": self.pw},
                               timeout=15)
            if r.ok:
                return True
        except Exception:
            pass

        # Legacy JSON
        try:
            r = self.sess.post(self._u("/api/login", proxy_first=False),
                               json={"username": self.user, "password": self.pw},
                               timeout=15)
            if r.ok:
                return True
        except Exception:
            pass

        return False

    # ----- sites -----
    def get_sites(self) -> List[Dict]:
        paths = [
            ("/api/self/sites", True),
            ("/api/self/sites", False),
            ("/api/s/default/self/sites", True),
            ("/api/s/default/self/sites", False),
        ]
        for path, proxy in paths:
            try:
                r = self.sess.get(self._u(path, proxy_first=proxy), timeout=15)
                if not r.ok:
                    continue
                obj = self._j(r)
                if isinstance(obj, dict) and isinstance(obj.get("data"), list):
                    return obj["data"]
                if isinstance(obj, list):
                    return obj
            except Exception:
                continue
        return []

    def create_site(self, name: str, desc: Optional[str] = None) -> bool:
        body = {"cmd": "add-site", "name": name, "desc": desc or name}
        for proxy in (True, False):
            try:
                r = self.sess.post(self._u("/api/s/default/cmd/sitemgr", proxy_first=proxy), json=body, timeout=15)
                if r.ok:
                    return True
            except Exception:
                pass
        return False

    # ----- devices -----
    def get_devices(self, site_key: str) -> List[Dict]:
        results: List[Dict] = []
        paths = [
            (f"/api/s/{site_key}/stat/device", True),
            (f"/api/s/{site_key}/stat/device", False),
            (f"/api/s/{site_key}/stat/device-basic", True),
            (f"/api/s/{site_key}/stat/device-basic", False),
            (f"/api/s/{site_key}/list/device", True),
            (f"/api/s/{site_key}/list/device", False),
        ]
        for path, proxy in paths:
            try:
                r = self.sess.get(self._u(path, proxy_first=proxy), timeout=20)
                if not r.ok:
                    continue
                obj = self._j(r)
                lst = []
                if isinstance(obj, dict):
                    if isinstance(obj.get("data"), list): lst = obj.get("data")
                    elif isinstance(obj.get("devices"), list): lst = obj.get("devices")
                    elif isinstance(obj.get("items"), list): lst = obj.get("items")
                    else:
                        for v in obj.values():
                            if isinstance(v, list): lst = v; break
                elif isinstance(obj, list):
                    lst = obj
                if lst:
                    results.extend(lst)
            except Exception:
                continue
        # De-dup by mac/id
        by_mac: Dict[str, Dict] = {}
        for d in results:
            mac = (d.get("mac") or "").lower()
            key = mac or (d.get("_id") or d.get("device_id") or "")
            if not key:
                continue
            if key not in by_mac:
                by_mac[key] = d
        return list(by_mac.values())

    def device_id_by_mac(self, site_key: str, mac: str) -> Optional[str]:
        for d in self.get_devices(site_key):
            if (d.get("mac") or "").lower() == mac.lower():
                return d.get("_id") or d.get("device_id")
        return None

    def adopt_device(self, site_key: str, mac: str) -> bool:
        for proxy in (True, False):
            try:
                r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                   json={"cmd": "adopt", "mac": mac}, timeout=15)
                if r.ok:
                    return True
            except Exception:
                pass
        return False

    def set_alias(self, site_key: str, mac: str, alias: str) -> bool:
        dev_id = self.device_id_by_mac(site_key, mac)
        if not dev_id:
            return False
        body = {"name": alias}
        for proxy in (True, False):
            try:
                r = self.sess.put(self._u(f"/api/s/{site_key}/rest/device/{dev_id}", proxy_first=proxy),
                                  json=body, timeout=15)
                if r.ok:
                    return True
            except Exception:
                pass
        return False

    def set_locate(self, site_key: str, mac: str, enabled: bool) -> bool:
        # For turning OFF, we need to try multiple methods as some devices don't respond to the first command
        if not enabled:
            success_count = 0
            
            # Method 1: Standard UniFi API format with duration=0
            for proxy in (False, True):
                try:
                    r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                       json={"cmd": "set-locate", "mac": mac, "duration": 0},
                                       timeout=15)
                    if r.ok:
                        success_count += 1
                except Exception:
                    pass
            
            # Method 2: Try with enabled=False
            for proxy in (False, True):
                try:
                    r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                       json={"cmd": "set-locate", "mac": mac, "enabled": False},
                                       timeout=15)
                    if r.ok:
                        success_count += 1
                except Exception:
                    pass
            
            # Method 3: Try with combined parameters
            for proxy in (False, True):
                try:
                    r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                       json={"cmd": "set-locate", "mac": mac, "enabled": False, "duration": 0},
                                       timeout=15)
                    if r.ok:
                        success_count += 1
                except Exception:
                    pass
            
            # Method 4: Try with negative duration
            for proxy in (False, True):
                try:
                    r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                       json={"cmd": "set-locate", "mac": mac, "duration": -1},
                                       timeout=15)
                    if r.ok:
                        success_count += 1
                except Exception:
                    pass
            
            # Method 5: Try with locate command
            for proxy in (False, True):
                try:
                    r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                       json={"cmd": "locate", "mac": mac, "duration": 0},
                                       timeout=15)
                    if r.ok:
                        success_count += 1
                except Exception:
                    pass
            
            return success_count > 0
        
        # For turning ON, use the standard method
        else:
            # Method 1: Standard UniFi API format with duration (works with direct endpoint)
            for proxy in (False, True):  # Try direct endpoint first since proxy returns 404
                try:
                    r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                       json={"cmd": "set-locate", "mac": mac, "duration": 60},
                                       timeout=15)
                    if r.ok:
                        return True
                except Exception:
                    pass
            
            # Fallback methods for Locate ON if the first method fails
            for proxy in (False, True):
                try:
                    r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                       json={"cmd": "set-locate", "mac": mac, "enabled": True},
                                       timeout=15)
                    if r.ok:
                        return True
                except Exception:
                    pass
        
        return False

    def upgrade_device(self, site_key: str, mac: str) -> bool:
        for proxy in (True, False):
            try:
                r = self.sess.post(self._u(f"/api/s/{site_key}/cmd/devmgr", proxy_first=proxy),
                                   json={"cmd": "upgrade", "mac": mac}, timeout=20)
                if r.ok:
                    return True
            except Exception:
                pass
        return False

    # ----- Wi‑Fi (WLAN) -----
    def get_wlans(self, site_key: str):
        paths = [
            (f"/api/s/{site_key}/list/wlanconf", True),
            (f"/api/s/{site_key}/list/wlanconf", False),
            (f"/api/s/{site_key}/rest/wlanconf", True),
            (f"/api/s/{site_key}/rest/wlanconf", False),
        ]
        for path, proxy in paths:
            try:
                r = self.sess.get(self._u(path, proxy_first=proxy), timeout=15)
                if not r.ok:
                    continue
                obj = self._j(r)
                data = obj.get("data") if isinstance(obj, dict) else obj
                if isinstance(data, list):
                    return data
            except Exception:
                continue
        return []

    def get_all_aps_group_id(self, site_key: str):
        # Inspect existing WLANs for ap_group_ids
        for proxy in (False, True):
            try:
                r = self.sess.get(self._u(f"/api/s/{site_key}/rest/wlanconf", proxy_first=proxy), timeout=15)
                if r.ok:
                    obj = self._j(r)
                    data = obj.get("data", []) if isinstance(obj, dict) else (obj if isinstance(obj, list) else [])
                    for wlan in data:
                        ids = wlan.get("ap_group_ids") or []
                        if ids:
                            return ids[0]
            except Exception:
                pass
        # Query AP groups
        for path in (f"/api/s/{site_key}/rest/apgroup", f"/api/s/{site_key}/list/apgroup"):
            for proxy in (False, True):
                try:
                    r = self.sess.get(self._u(path, proxy_first=proxy), timeout=15)
                    if not r.ok:
                        continue
                    obj = self._j(r)
                    groups = obj.get("data") if isinstance(obj, dict) else (obj if isinstance(obj, list) else [])
                    for g in groups:
                        if (g.get("name") or "").strip().lower() == "all aps":
                            return g.get("_id") or g.get("id")
                    for g in groups:
                        if g.get("attr_no_delete") or g.get("default"):
                            return g.get("_id") or g.get("id")
                    if groups:
                        return groups[0].get("_id") or groups[0].get("id")
                except Exception:
                    pass
        raise RuntimeError("Could not determine 'All APs' group id automatically. "
                           "Create or edit any SSID once in the UniFi UI so it records an ap_group_id, then retry.")

    def create_wlan(self, site_key: str, ssid: str, password: str) -> bool:
        # Always target ALL APs via AP Group per UniFi 6.x+ behavior
        body = {
            "name": ssid,
            "x_passphrase": password,
            "enabled": True,
            "security": "wpapsk",
            "wpa_mode": "wpa2",
            "wpa3_support": False,
            "pmf_mode": "optional",
            "ft_psk": True,
            "ft_over_ds": True,
            "bandsteering_mode": "off",
            "is_2ghz": True,
            "is_5ghz": True,
            "ap_group_mode": "all",
        }
        gid = self.get_all_aps_group_id(site_key)
        body["ap_group_ids"] = [gid]

        def _try(rest_first=True):
            last = ""
            if rest_first:
                endpoints = [("REST", f"/api/s/{site_key}/rest/wlanconf"),
                             ("ADD",  f"/api/s/{site_key}/add/wlanconf")]
            else:
                endpoints = [("ADD",  f"/api/s/{site_key}/add/wlanconf"),
                             ("REST", f"/api/s/{site_key}/rest/wlanconf")]
            for kind, path in endpoints:
                for proxy in (False, True):
                    try:
                        r = self.sess.post(self._u(path, proxy_first=proxy), json=body, timeout=25)
                        if r.ok:
                            return True, ""
                        last = f"{kind} {r.status_code}: {r.text[:400]}"
                    except Exception as ex:
                        last = f"{kind} exception: {ex}"
            return False, last

        ok, err = _try(rest_first=True)
        if ok:
            return True
        ok2, err2 = _try(rest_first=False)
        if ok2:
            return True
        raise Exception(f"Controller rejected WLAN create: {err or err2 or 'unknown error'}")

    # ----- SSH inform -----
    def ssh_set_inform(self, ip: str, inform_url: Optional[str]=None, username: Optional[str]=None, password: Optional[str]=None) -> bool:
        host = ip.strip()
        inform = (inform_url or self.inform_url).rstrip("/") + "/inform"
        user = username or self.ssh_user
        pw = password or self.ssh_pass
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(host, username=user, password=pw, timeout=10)
            for cmd in (f"set-inform {inform}", f"set-inform {inform}"):
                stdin, stdout, stderr = cli.exec_command(cmd, timeout=10)
                _ = stdout.read(); _ = stderr.read()
            cli.close()
            return True
        except Exception:
            return False


    def create_site_and_get_key(self, desc: str) -> str:
        """
        Create a site with 'desc' (title shown in UI) and return its site key (the internal 'name').
        Falls back to scanning the site list by matching desc.
        """
        try:
            payload = {"cmd": "add-site", "desc": desc}
            url = f"{self.base}/api/s/default/cmd/sitemgr"
            r = self.sess.post(url, json=payload, timeout=20)
            r.raise_for_status()
        except Exception as e:
            # Some controllers need a different path; try UniFi OS proxy variant as a fallback
            try:
                url2 = f"{self.base}/proxy/network/api/s/default/cmd/sitemgr"
                r2 = self.sess.post(url2, json=payload, timeout=20)
                r2.raise_for_status()
            except Exception as e2:
                raise RuntimeError(f"Site create failed: {e2}") from e

        # Now fetch sites and locate the newly created one by description match (desc)
        sites = self.get_sites() or []
        for s in sites:
            if (s.get("desc") or "").strip() == desc.strip():
                # 'name' is the site key used in API paths
                key = s.get("name") or s.get("site_name") or ""
                if key:
                    return key
        # If we can't find by desc, return empty string so caller can react
        return ""

    def set_wlan_enabled(self, site: str, wlan_id: str, enabled: bool) -> bool:
        """
        Enable/disable a WLAN using the correct UniFi API endpoints.
        Tries multiple approaches based on what works with this controller version.
        """
        # First, get the current WLAN object to understand its structure
        wlans = self.get_wlans(site)
        current_wlan = None
        for w in wlans:
            if w.get("_id") == wlan_id:
                current_wlan = w
                break
        
        if not current_wlan:
            return False
        
        # Create a copy of the WLAN object with only the enabled field changed
        updated_wlan = dict(current_wlan)
        updated_wlan["enabled"] = bool(enabled)
        
        # Remove fields that might cause issues
        for k in ("attr_hidden_id", "x_password", "x_passphrase_hash", "not_supported", "attr_no_delete"):
            updated_wlan.pop(k, None)
        
        # Try different API endpoints in order of preference
        endpoints = [
            # Try the /upd/wlanconf endpoint (most common for updates)
            f"/api/s/{site}/upd/wlanconf",
            # Try the /rest/wlanconf endpoint with PUT
            f"/api/s/{site}/rest/wlanconf/{wlan_id}",
            # Try the /add/wlanconf endpoint (sometimes works for updates)
            f"/api/s/{site}/add/wlanconf",
        ]
        
        for endpoint in endpoints:
            for proxy in (True, False):
                try:
                    url = self._u(endpoint, proxy_first=proxy)
                    
                    if "/upd/wlanconf" in endpoint:
                        # For upd endpoint, send minimal data
                        payload = {"_id": wlan_id, "enabled": bool(enabled)}
                        r = self.sess.post(url, json=payload, timeout=20)
                    elif "/rest/wlanconf" in endpoint:
                        # For REST endpoint, try PUT with full object
                        r = self.sess.put(url, json=updated_wlan, timeout=20)
                    else:
                        # For add endpoint, send full object
                        r = self.sess.post(url, json=updated_wlan, timeout=20)
                    
                    if r.status_code == 200:
                        return True
                        
                except Exception:
                    continue
        
        return False

    def set_wlan_enabled_verbose(self, site: str, wlan_id: str, enabled: bool):
        logs = []

        def rec(resp):
            try:
                return resp.status_code, (resp.json() if resp.content else {})
            except Exception:
                txt = resp.text if hasattr(resp, "text") else ""
                return getattr(resp, "status_code", "?"), {"text": str(txt)[:600]}

        # First, get the current WLAN object to understand its structure
        wlans = self.get_wlans(site)
        current_wlan = None
        for w in wlans:
            if w.get("_id") == wlan_id:
                current_wlan = w
                break
        
        if not current_wlan:
            logs.append(f"WLAN {wlan_id} not found in current WLAN list")
            return False, "\n".join(logs)
        
        # Create a copy of the WLAN object with only the enabled field changed
        updated_wlan = dict(current_wlan)
        updated_wlan["enabled"] = bool(enabled)
        
        # Remove fields that might cause issues
        for k in ("attr_hidden_id", "x_password", "x_passphrase_hash", "not_supported", "attr_no_delete"):
            updated_wlan.pop(k, None)
        
        # Try different API endpoints in order of preference
        endpoints = [
            # Try the /upd/wlanconf endpoint (most common for updates)
            f"/api/s/{site}/upd/wlanconf",
            # Try the /rest/wlanconf endpoint with PUT
            f"/api/s/{site}/rest/wlanconf/{wlan_id}",
            # Try the /add/wlanconf endpoint (sometimes works for updates)
            f"/api/s/{site}/add/wlanconf",
        ]
        
        for endpoint in endpoints:
            for proxy in (True, False):
                try:
                    url = self._u(endpoint, proxy_first=proxy)
                    
                    if "/upd/wlanconf" in endpoint:
                        # For upd endpoint, send minimal data
                        payload = {"_id": wlan_id, "enabled": bool(enabled)}
                        r = self.sess.post(url, json=payload, timeout=20)
                        s, b = rec(r)
                        logs.append(f"POST upd -> {s} {b}")
                        if s == 200:
                            return True, "\n".join(logs)
                    elif "/rest/wlanconf" in endpoint:
                        # For REST endpoint, try PUT with full object
                        r = self.sess.put(url, json=updated_wlan, timeout=20)
                        s, b = rec(r)
                        logs.append(f"PUT rest -> {s} {b}")
                        if s == 200:
                            return True, "\n".join(logs)
                    else:
                        # For add endpoint, send full object
                        r = self.sess.post(url, json=updated_wlan, timeout=20)
                        s, b = rec(r)
                        logs.append(f"POST add -> {s} {b}")
                        if s == 200:
                            return True, "\n".join(logs)
                            
                except Exception as e:
                    logs.append(f"{endpoint} EXC: {e}")

        return False, "\n".join(logs)


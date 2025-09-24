import requests
from typing import List, Dict, Optional
import paramiko
import time

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
        # Cache for system info and site data
        self._system_info_cache = None
        self._system_info_cache_time = 0
        self._sites_cache = None
        self._sites_cache_time = 0
        self._cache_duration = 300  # 5 minutes

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

    # ----- system info -----
    def get_system_info(self, force_refresh: bool = False) -> Optional[Dict]:
        """Get comprehensive system information from v2 API info endpoint"""
        current_time = time.time()
        
        # Return cached data if still valid and not forcing refresh
        if (not force_refresh and 
            self._system_info_cache and 
            (current_time - self._system_info_cache_time) < self._cache_duration):
            return self._system_info_cache
        
        try:
            self.log("Fetching system information from v2 API...")
            r = self.sess.get(self._u("/v2/api/info", proxy_first=False), timeout=15)
            
            if r.ok:
                system_info = self._j(r)
                if system_info:
                    # Cache the result
                    self._system_info_cache = system_info
                    self._system_info_cache_time = current_time
                    
                    # Log key information
                    system_data = system_info.get("system", {})
                    version = system_data.get("version", "Unknown")
                    uptime = system_data.get("uptime", 0)
                    hostname = system_data.get("hostname", "Unknown")
                    
                    self.log(f"System Info - Version: {version}, Hostname: {hostname}, Uptime: {uptime}s")
                    return system_info
                else:
                    self.log("v2 API info returned empty response")
            else:
                self.log(f"v2 API info failed: {r.status_code} - {r.text[:200]}")
                
        except Exception as e:
            self.log(f"Error fetching system info: {e}")
        
        return None
    
    def get_system_version(self) -> str:
        """Get UniFi system version"""
        system_info = self.get_system_info()
        if system_info and "system" in system_info:
            return system_info["system"].get("version", "Unknown")
        return "Unknown"
    
    def get_system_uptime(self) -> int:
        """Get system uptime in seconds"""
        system_info = self.get_system_info()
        if system_info and "system" in system_info:
            return system_info["system"].get("uptime", 0)
        return 0
    
    def get_system_hostname(self) -> str:
        """Get system hostname"""
        system_info = self.get_system_info()
        if system_info and "system" in system_info:
            return system_info["system"].get("hostname", "Unknown")
        return "Unknown"
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status information"""
        system_info = self.get_system_info()
        if not system_info:
            return {
                "version": "Unknown",
                "hostname": "Unknown", 
                "uptime": 0,
                "uptime_formatted": "Unknown",
                "platform": "Unknown",
                "device_count": 0,
                "sites_count": 0,
                "status": "offline"
            }
        
        system_data = system_info.get("system", {})
        sites_data = system_info.get("sites", [])
        
        # Calculate uptime in human readable format
        uptime_seconds = system_data.get("uptime", 0)
        uptime_formatted = self._format_uptime(uptime_seconds)
        
        # Count total devices across all sites
        total_devices = sum(site.get("device_count", 0) for site in sites_data)
        
        return {
            "version": system_data.get("version", "Unknown"),
            "hostname": system_data.get("hostname", "Unknown"),
            "uptime": uptime_seconds,
            "uptime_formatted": uptime_formatted,
            "platform": system_data.get("standalone", {}).get("platform_type", "Unknown"),
            "device_count": total_devices,
            "sites_count": len(sites_data),
            "status": "online" if uptime_seconds > 0 else "offline"
        }
    
    def _format_uptime(self, seconds: int) -> str:
        """Format uptime seconds into human readable format"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}d {hours}h"
    
    def is_v2_api_available(self) -> bool:
        """Check if v2 API is available on this controller"""
        try:
            system_info = self.get_system_info()
            return system_info is not None
        except Exception:
            return False

    # ----- enhanced sites -----
    def get_sites(self, force_refresh: bool = False) -> List[Dict]:
        """Get sites list with enhanced information from v2 API when available"""
        current_time = time.time()
        
        # Return cached data if still valid and not forcing refresh
        if (not force_refresh and 
            self._sites_cache and 
            (current_time - self._sites_cache_time) < self._cache_duration):
            return self._sites_cache
        
        # Try to get sites from v2 API info first (most comprehensive)
        try:
            system_info = self.get_system_info(force_refresh)
            if system_info and "sites" in system_info:
                sites = system_info["sites"]
                if sites:
                    # Ensure each site has a 'key' field set to the 'name' field
                    for site in sites:
                        if 'name' in site and 'key' not in site:
                            site['key'] = site['name']
                    
                    # Cache the result
                    self._sites_cache = sites
                    self._sites_cache_time = current_time
                    
                    self.log(f"Retrieved {len(sites)} sites from v2 API info")
                    return sites
        except Exception as e:
            self.log(f"Failed to get sites from v2 API info: {e}")
        
        # Fallback to traditional methods
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
                sites = []
                if isinstance(obj, dict) and isinstance(obj.get("data"), list):
                    sites = obj["data"]
                elif isinstance(obj, list):
                    sites = obj
                
                if sites:
                    # Ensure each site has a 'key' field set to the 'name' field
                    for site in sites:
                        if 'name' in site and 'key' not in site:
                            site['key'] = site['name']
                    
                    # Cache the result
                    self._sites_cache = sites
                    self._sites_cache_time = current_time
                    
                    self.log(f"Retrieved {len(sites)} sites from traditional API")
                    return sites
            except Exception:
                continue
        
        self.log("Failed to retrieve sites from any API endpoint")
        return []
    
    def get_active_sites(self) -> List[Dict]:
        """Get only active sites (sites with is_active=True or device_count > 0)"""
        all_sites = self.get_sites()
        active_sites = []
        
        for site in all_sites:
            # Include sites that are explicitly marked as active
            if site.get("is_active", False):
                active_sites.append(site)
            # Include sites with devices (likely active)
            elif site.get("device_count", 0) > 0:
                active_sites.append(site)
        
        self.log(f"Found {len(active_sites)} active sites out of {len(all_sites)} total")
        return active_sites
    
    def validate_site_key(self, site_key: str) -> bool:
        """Validate that a site key exists and is accessible"""
        if not site_key:
            return False
        
        sites = self.get_sites()
        for site in sites:
            if site.get("name") == site_key or site.get("key") == site_key:
                self.log(f"Site key '{site_key}' is valid")
                return True
        
        self.log(f"Site key '{site_key}' not found in available sites")
        return False
    
    def get_site_info(self, site_key: str) -> Optional[Dict]:
        """Get detailed information about a specific site"""
        sites = self.get_sites()
        for site in sites:
            if site.get("name") == site_key or site.get("key") == site_key:
                return site
        return None

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
        """Get the 'All APs' group ID using multiple endpoint approaches"""
        # Try multiple endpoints for different controller types
        endpoints = [
            (f"/api/s/{site_key}/rest/wlangroup", True),   # UniFi OS
            (f"/api/s/{site_key}/rest/wlangroup", False),  # Legacy
            (f"/api/s/{site_key}/wlangroup", True),        # Alternative UniFi OS
            (f"/api/s/{site_key}/wlangroup", False),       # Alternative Legacy
            (f"/api/s/{site_key}/rest/wlanconf", True),    # Sometimes wlangroup is in wlanconf
            (f"/api/s/{site_key}/rest/wlanconf", False),   # Legacy wlanconf
        ]
        
        for endpoint, proxy_first in endpoints:
            self.log(f"Trying wlangroup endpoint: {endpoint} (proxy_first={proxy_first})")
            try:
                r = self.sess.get(self._u(endpoint, proxy_first=proxy_first), timeout=15)
                if not r.ok:
                    self.log(f"Failed to get wlangroup from {endpoint}: {r.status_code} - {r.text[:100]}...")
                    continue
                
                obj = self._j(r)
                groups = obj if isinstance(obj, list) else obj.get("data", [])
                
                if not groups:
                    self.log(f"No WLAN groups found in {endpoint}")
                    continue
                
                self.log(f"Found {len(groups)} WLAN groups in {endpoint}")
                
                # Look for the "Default" or "All" group as per methodology
                for g in groups:
                    group_name = g.get("name", "")
                    group_id = g.get("_id")
                    attr_hidden_id = g.get("attr_hidden_id")
                    attr_no_delete = g.get("attr_no_delete")
                    
                    self.log(f"Group: {group_name} (ID: {group_id}, hidden_id: {attr_hidden_id}, no_delete: {attr_no_delete})")
                    
                    # Prefer groups with attr_hidden_id="default" or attr_no_delete=true
                    if attr_hidden_id == "default" or attr_no_delete is True:
                        self.log(f"Found default WLAN group: {group_name} (ID: {group_id})")
                        return group_id
                
                # If no default group found, use the first one
                first_group = groups[0]
                group_id = first_group.get("_id")
                group_name = first_group.get("name", "Unknown")
                self.log(f"Using first WLAN group: {group_name} (ID: {group_id})")
                return group_id
                
            except Exception as e:
                self.log(f"Error getting wlangroup from {endpoint}: {e}")
                continue
        
        # If all endpoints failed, try to get from existing WLANs
        self.log("All wlangroup endpoints failed, trying to get from existing WLANs...")
        try:
            existing_wlans = self._get_existing_wlans(site_key)
            if existing_wlans:
                # Look for wlangroup_id in existing WLANs
                for wlan in existing_wlans:
                    if 'wlangroup_id' in wlan:
                        self.log(f"Found wlangroup_id from existing WLAN: {wlan['wlangroup_id']}")
                        return wlan['wlangroup_id']
                    if 'ap_group_ids' in wlan and wlan['ap_group_ids']:
                        self.log(f"Found ap_group_ids from existing WLAN: {wlan['ap_group_ids'][0]}")
                        return wlan['ap_group_ids'][0]
        except Exception as e:
            self.log(f"Error getting wlangroup from existing WLANs: {e}")
        
        raise Exception("Could not find wlangroup_id from any endpoint")

    def get_site_all_ap_group_id(self, site_key: str):
        """Get the 'All APs' group ID using POST with empty JSON (as per user's working code)"""
        try:
            # Use POST with empty JSON body as per the working code
            endpoint = f"/api/s/{site_key}/list/apgroups"
            url = self._u(endpoint, proxy_first=False)  # Try legacy first
            self.log(f"Trying AP group endpoint: {endpoint}")
            
            r = self.sess.post(url, json={}, timeout=15)
            self.log(f"AP group response status: {r.status_code}")
            
            if r.status_code == 200:
                obj = self._j(r)
                groups = obj.get("data", []) if isinstance(obj, dict) else obj
                
                if groups:
                    self.log(f"Found {len(groups)} AP groups")
                    # Look for groups with attr_hidden_id == "all" or name.lower() == "all"
                    for group in groups:
                        group_name = group.get("name", "")
                        group_id = group.get("_id")
                        attr_hidden_id = group.get("attr_hidden_id")
                        
                        self.log(f"Group: {group_name} (ID: {group_id}, attr_hidden_id: {attr_hidden_id})")
                        
                        if attr_hidden_id == "all" or group_name.lower() == "all":
                            self.log(f"Found 'All' AP group: {group_name} (ID: {group_id})")
                            return group_id
                    
                    # If no "All" group found, use the first one
                    first_group = groups[0]
                    group_id = first_group.get("_id")
                    group_name = first_group.get("name", "Unknown")
                    self.log(f"Using first AP group: {group_name} (ID: {group_id})")
                    return group_id
                else:
                    self.log(f"No AP groups found in response")
            else:
                self.log(f"AP group endpoint failed: {r.status_code} - {r.text}")
        except Exception as e:
            self.log(f"Error getting AP groups: {e}")
        
        # Try with proxy if legacy failed
        try:
            endpoint = f"/api/s/{site_key}/list/apgroups"
            url = self._u(endpoint, proxy_first=True)  # Try UniFi OS
            self.log(f"Trying AP group endpoint with proxy: {endpoint}")
            
            r = self.sess.post(url, json={}, timeout=15)
            self.log(f"AP group response status: {r.status_code}")
            
            if r.status_code == 200:
                obj = self._j(r)
                groups = obj.get("data", []) if isinstance(obj, dict) else obj
                
                if groups:
                    self.log(f"Found {len(groups)} AP groups")
                    # Look for groups with attr_hidden_id == "all" or name.lower() == "all"
                    for group in groups:
                        group_name = group.get("name", "")
                        group_id = group.get("_id")
                        attr_hidden_id = group.get("attr_hidden_id")
                        
                        self.log(f"Group: {group_name} (ID: {group_id}, attr_hidden_id: {attr_hidden_id})")
                        
                        if attr_hidden_id == "all" or group_name.lower() == "all":
                            self.log(f"Found 'All' AP group: {group_name} (ID: {group_id})")
                            return group_id
                    
                    # If no "All" group found, use the first one
                    first_group = groups[0]
                    group_id = first_group.get("_id")
                    group_name = first_group.get("name", "Unknown")
                    self.log(f"Using first AP group: {group_name} (ID: {group_id})")
                    return group_id
                else:
                    self.log(f"No AP groups found in response")
            else:
                self.log(f"AP group endpoint failed: {r.status_code} - {r.text}")
        except Exception as e:
            self.log(f"Error getting AP groups with proxy: {e}")
        
        self.log("No AP groups found on any endpoint")
        return None
    
    def _get_ap_group_id_v2(self, site_key: str) -> Optional[str]:
        """Get AP group ID using v2 API with enhanced error handling"""
        try:
            self.log(f"Getting AP groups using v2 API for site: {site_key}")
            ap_groups_response = self.sess.get(self._u(f"/v2/api/site/{site_key}/apgroups", proxy_first=False), timeout=15)
            
            if ap_groups_response.ok:
                ap_groups_data = ap_groups_response.json()
                if ap_groups_data and len(ap_groups_data) > 0:
                    # Look for the "All APs" group or default group
                    for group in ap_groups_data:
                        group_name = group.get("name", "")
                        group_id = group.get("_id")
                        attr_hidden_id = group.get("attr_hidden_id")
                        
                        self.log(f"AP Group: {group_name} (ID: {group_id}, hidden_id: {attr_hidden_id})")
                        
                        # Prefer groups with attr_hidden_id="default" or name contains "All"
                        if attr_hidden_id == "default" or "all" in group_name.lower():
                            self.log(f"Found default AP group: {group_name} (ID: {group_id})")
                            return group_id
                    
                    # If no default found, use the first one
                    first_group = ap_groups_data[0]
                    group_id = first_group.get("_id")
                    group_name = first_group.get("name", "Unknown")
                    self.log(f"Using first AP group: {group_name} (ID: {group_id})")
                    return group_id
                else:
                    self.log("No AP groups found in v2 API response")
                    return None
            else:
                self.log(f"v2 API AP groups failed: {ap_groups_response.status_code}")
                return None
        except Exception as e:
            self.log(f"Error getting AP groups from v2 API: {e}")
            return None
    
    def get_all_aps_ap_group_id(self, site_key: str):
        """Get the 'All APs' group ID for broadcasting WLANs (legacy method)"""
        return self.get_site_all_ap_group_id(site_key)

    def _create_all_aps_group(self, site_key: str) -> str:
        """Create an 'All APs' group if none exists"""
        self.log("Creating 'All APs' group...")
        
        # Get all devices to include in the group
        devices = self.get_devices(site_key)
        device_ids = []
        for device in devices:
            if device.get("type") == "uap" or "ap" in (device.get("type") or "").lower():
                device_id = device.get("_id") or device.get("id")
                if device_id:
                    device_ids.append(device_id)
        
        self.log(f"Found {len(device_ids)} APs to include in group")
        
        # Create AP group payload using the structure you provided
        group_data = {
            "name": "New_AP_Group",
            "comment": "Group for new SSIDs",
            "radio_groups": {
                "na": "na_default",
                "ng": "ng_default"
            }
        }
        
        # Try to create the group via different endpoints
        endpoints = [
            f"/api/s/{site_key}/rest/apgroup",
            f"/api/s/{site_key}/add/apgroup",
            f"/api/s/{site_key}/rest/group"
        ]
        
        for endpoint in endpoints:
            try:
                self.log(f"Trying to create AP group via {endpoint}")
                r = self.sess.post(self._u(endpoint, proxy_first=True), json=group_data, timeout=15)
                if r.ok:
                    response = self._j(r)
                    group_id = response.get("_id") or response.get("id")
                    if group_id:
                        self.log(f"Successfully created 'All APs' group with ID: {group_id}")
                        return group_id
                else:
                    self.log(f"Failed to create group via {endpoint}: {r.status_code} - {r.text}")
            except Exception as e:
                self.log(f"Exception creating group via {endpoint}: {e}")
        
        # If all endpoints failed, try a simpler approach
        self.log("Trying simplified group creation...")
        simple_group = {
            "name": "New_AP_Group",
            "comment": "Group for new SSIDs"
        }
        
        for endpoint in endpoints:
            try:
                r = self.sess.post(self._u(endpoint, proxy_first=True), json=simple_group, timeout=15)
                if r.ok:
                    response = self._j(r)
                    group_id = response.get("_id") or response.get("id")
                    if group_id:
                        self.log(f"Successfully created simplified 'All APs' group with ID: {group_id}")
                        return group_id
            except Exception as e:
                self.log(f"Exception creating simplified group via {endpoint}: {e}")
        
        # Last resort: try to use a default group ID
        self.log("Trying to use default group ID as fallback...")
        try:
            # Some UniFi versions use a default group ID
            default_group_id = "default"
            self.log(f"Using default group ID: {default_group_id}")
            return default_group_id
        except Exception as e:
            self.log(f"Default group ID also failed: {e}")
            raise Exception("Failed to create AP group via all endpoints")

    def create_wlan_api_browser_method(self, site_key: str, ssid: str, password: str) -> bool:
        """Create WLAN using the exact payload structure discovered via API Browser"""
        try:
            # Validate site key first
            if not self.validate_site_key(site_key):
                self.log(f"✗ Invalid site key: {site_key}")
                return False
            
            # Handle site names with spaces (convert to underscore for API)
            api_site_key = site_key.replace(" ", "_")
            
            # Get the correct group IDs for this site
            self.log(f"Getting group IDs for site: {api_site_key}")
            
            # Try to get AP groups using v2 API (enhanced method)
            ap_group_id = self._get_ap_group_id_v2(api_site_key)
            
            # Try to get WLAN groups using v1 API
            try:
                wlan_groups_response = self.sess.get(self._u(f"/api/s/{api_site_key}/rest/wlangroup", proxy_first=False), timeout=15)
                if wlan_groups_response.ok:
                    wlan_groups_data = wlan_groups_response.json()
                    if wlan_groups_data.get("data") and len(wlan_groups_data["data"]) > 0:
                        wlangroup_id = wlan_groups_data["data"][0].get("_id")
                        self.log(f"Found WLAN group ID: {wlangroup_id}")
                    else:
                        self.log("No WLAN groups found, will try without WLAN group ID")
                        wlangroup_id = None
                else:
                    self.log(f"Failed to get WLAN groups: {wlan_groups_response.status_code}")
                    wlangroup_id = None
            except Exception as e:
                self.log(f"Error getting WLAN groups: {e}")
                wlangroup_id = None
            
            # Build payload with discovered group IDs - EXACT structure from working tests
            wlan_payload = {
                "name": ssid,
                "x_passphrase": password,
                "security": "wpapsk",
                "wpa_mode": "wpa2",
                "enabled": True,
                "is_guest": False,
                "vlan_enabled": False,
                # WiFi Performance Settings
                "fast_roaming_enabled": True,        # Fast Roaming On
                "bss_transition": True,              # BSS Transition On  
                "minrate_ng_enabled": True,          # Minimum Data Rate Control Auto
                "minrate_na_enabled": True,          # Minimum Data Rate Control Auto for 5GHz
                "minrate_setting_preference": "auto" # Auto minimum rate setting
            }
            
            # Add group IDs if we found them
            if wlangroup_id:
                wlan_payload["wlangroup_id"] = wlangroup_id
                
            if ap_group_id:
                wlan_payload["ap_group_mode"] = "all"
                wlan_payload["ap_group_ids"] = [ap_group_id]
            
            # Try the EXACT working endpoint from our successful tests
            endpoint = f"/api/s/{api_site_key}/rest/wlanconf"
            self.log(f"Creating WLAN with API Browser payload structure: {endpoint}")
            self.log(f"Payload: {wlan_payload}")
            
            # Try direct endpoint first (this worked in our tests)
            r = self.sess.post(self._u(endpoint, proxy_first=False), json=wlan_payload, timeout=30)
            self.log(f"Direct endpoint response status: {r.status_code}")
            self.log(f"Direct endpoint response: {r.text}")
            
            if r.ok:
                response_data = r.json()
                if (response_data.get("meta", {}).get("rc") == "ok" and 
                    "data" in response_data and 
                    len(response_data["data"]) > 0):
                    self.log(f"✓ WLAN created successfully using direct endpoint")
                    self.log(f"Created WLAN ID: {response_data['data'][0].get('_id', 'Unknown')}")
                    return True
                else:
                    self.log(f"✗ Unexpected response format: {response_data}")
            
            # If direct endpoint failed, try proxy endpoint
            self.log("Direct endpoint failed, trying proxy endpoint...")
            r = self.sess.post(self._u(endpoint, proxy_first=True), json=wlan_payload, timeout=30)
            self.log(f"Proxy endpoint response status: {r.status_code}")
            self.log(f"Proxy endpoint response: {r.text}")
            
            if r.ok:
                response_data = r.json()
                if (response_data.get("meta", {}).get("rc") == "ok" and 
                    "data" in response_data and 
                    len(response_data["data"]) > 0):
                    self.log(f"✓ WLAN created successfully using proxy endpoint")
                    self.log(f"Created WLAN ID: {response_data['data'][0].get('_id', 'Unknown')}")
                    return True
                else:
                    self.log(f"✗ Unexpected response format: {response_data}")
            
            self.log(f"✗ WLAN creation failed with both endpoints")
            return False
                
        except Exception as e:
            self.log(f"✗ Exception during API Browser WLAN creation: {e}")
            return False

    def create_wlan(self, site_key: str, ssid: str, password: str) -> bool:
        """Create WLAN using the corrected API Browser method"""
        # Handle None or missing site_key
        if not site_key:
            self.log("No site key provided, using default site")
            site_key = "default"
        
        # Use the corrected API Browser method that we know works
        self.log("Using corrected API Browser method for WLAN creation...")
        try:
            success = self.create_wlan_api_browser_method(site_key, ssid, password)
            if success:
                self.log("✓ WLAN created successfully using corrected API Browser method")
                return True
            else:
                self.log("✗ API Browser method failed, trying fallback...")
        except Exception as e:
            self.log(f"✗ API Browser method failed with exception: {e}")
        
        # Fallback to the old method if API Browser method fails
        self.log("Trying fallback WLAN creation method...")
        try:
            success = self._create_wlan_with_wlangroup_endpoint(site_key, ssid, password)
            if success:
                self.log("✓ WLAN created successfully using fallback method")
                return True
        except Exception as e:
            self.log(f"✗ Fallback method failed: {e}")
        
        # If all methods fail, raise exception
        raise Exception("All WLAN creation methods failed")

    def _add_ap_group_to_body(self, body: dict, site_key: str) -> dict:
        """Add AP group configuration to WLAN body"""
        try:
            body["ap_group_mode"] = "all"
            gid = self.get_all_aps_group_id(site_key)
            body["ap_group_ids"] = [gid]
            self.log(f"Added AP group {gid} to WLAN body")
        except Exception as e:
            self.log(f"Failed to add AP group: {e}")
            # Try alternative AP group methods
            try:
                # Try to get any existing AP group
                existing_groups = self._get_existing_ap_groups(site_key)
                if existing_groups:
                    group_id = existing_groups[0].get("_id") or existing_groups[0].get("id")
                    if group_id:
                        body["ap_group_ids"] = [group_id]
                        body["ap_group_mode"] = "all"
                        self.log(f"Using existing AP group: {group_id}")
                    else:
                        self.log("No valid AP group ID found")
                else:
                    self.log("No existing AP groups found")
            except Exception as e2:
                self.log(f"Failed to get existing AP groups: {e2}")
        return body

    def _create_minimal_wlan_body(self, ssid: str, password: str) -> dict:
        """Create minimal WLAN body for older UniFi versions"""
        return {
            "name": ssid,
            "x_passphrase": password,
            "enabled": True,
            "security": "wpapsk"
        }

    def _create_legacy_wlan_body(self, ssid: str, password: str) -> dict:
        """Create legacy WLAN body for very old UniFi versions"""
        return {
            "name": ssid,
            "x_passphrase": password,
            "enabled": True,
            "security": "wpapsk",
            "wpa_mode": "wpa2"
        }

    def _create_ultra_minimal_wlan_body(self, ssid: str, password: str) -> dict:
        """Create ultra-minimal WLAN body with only essential fields"""
        return {
            "name": ssid,
            "x_passphrase": password,
            "enabled": True
        }

    def _create_no_ap_group_mode_wlan_body(self, ssid: str, password: str) -> dict:
        """Create WLAN body without AP group mode (for controllers that don't support it)"""
        return {
            "name": ssid,
            "x_passphrase": password,
            "enabled": True,
            "security": "wpapsk",
            "wpa_mode": "wpa2",
            "is_2ghz": True,
            "is_5ghz": True
        }

    def _create_cmd_style_wlan_body(self, ssid: str, password: str) -> dict:
        """Create WLAN body in CMD format (for cmd endpoint)"""
        return {
            "cmd": "create-wlan",
            "name": ssid,
            "x_passphrase": password,
            "enabled": True,
            "security": "wpapsk"
        }

    def _create_all_aps_wlan_body(self, ssid: str, password: str) -> dict:
        """Create WLAN body with All APs broadcasting (official UniFi API format)"""
        return {
            "name": ssid,
            "passphrase": password,  # Use 'passphrase' instead of 'x_passphrase'
            "enabled": True,
            "security": "wpapsk",
            "apGroupIds": [],  # Empty array means all APs (official API format)
            "hideSsid": False,
            "isGuest": False,
            "wlanBand": "both"  # Both 2.4GHz and 5GHz
        }

    def _create_wlangroup_wlan_body(self, ssid: str, password: str, site_key: str) -> dict:
        """Create WLAN body using wlangroup_id method from the script"""
        try:
            wlangroup_id = self.get_all_aps_group_id(site_key)
            return {
                "name": ssid,
                "enabled": True,
                "wlangroup_id": wlangroup_id,
                "security": "wpapsk",
                "x_passphrase": password,
                "is_guest": False,
                "wpa_mode": "wpa2",
                "no2ghz_oui": False,
                "dtim_mode": "default",
            }
        except Exception as e:
            self.log(f"Failed to get wlangroup_id: {e}")
            # Fallback to basic structure
            return {
                "name": ssid,
                "enabled": True,
                "security": "wpapsk",
                "x_passphrase": password,
                "is_guest": False,
                "wpa_mode": "wpa2",
            }

    def _create_wlan_with_wlangroup_endpoint(self, site_key: str, ssid: str, password: str) -> bool:
        """Create WLAN using the correct API pattern from the methodology"""
        try:
            # Step 1: Get the wlangroup_id using the working approach
            self.log(f"Step 1: Getting wlangroup_id for site {site_key}")
            wlangroup_id = self.get_all_aps_group_id(site_key)
            self.log(f"Using wlangroup_id: {wlangroup_id}")
            
            # Step 2: Get the AP group ID using the new POST approach
            self.log(f"Step 2: Getting AP group ID for site {site_key}")
            ap_group_id = self.get_site_all_ap_group_id(site_key)
            self.log(f"Using ap_group_id: {ap_group_id}")
            
            # Step 3: Build payload using the working approach from user's code
            payload = {
                "name": ssid,
                "enabled": True,
                "wlangroup_id": wlangroup_id,
                "security": "wpapsk",
                "wpa_mode": "wpa2",
                "x_passphrase": password,
                # WiFi Performance Settings
                "fast_roaming_enabled": True,        # Fast Roaming On
                "bss_transition": True,              # BSS Transition On  
                "minrate_ng_enabled": True,          # Minimum Data Rate Control Auto
                "minrate_na_enabled": True,          # Minimum Data Rate Control Auto for 5GHz
                "minrate_setting_preference": "auto" # Auto minimum rate setting
            }
            
            # Add AP group fields if we found an AP group ID
            if ap_group_id:
                payload["ap_group_mode"] = "selected"
                payload["ap_group_ids"] = [ap_group_id]
                # Some builds accept (or prefer) singular too; harmless to include both:
                payload["ap_group_id"] = ap_group_id
                self.log(f"Added AP group fields: ap_group_mode=selected, ap_group_ids=[{ap_group_id}], ap_group_id={ap_group_id}")
            else:
                self.log("No AP group ID found, omitting AP group fields")
            
            # Try multiple endpoints for different controller types
            endpoints = [
                (f"/api/s/{site_key}/rest/wlanconf", False),  # Legacy (no proxy)
                (f"/api/s/{site_key}/rest/wlanconf", True),   # UniFi OS
                (f"/api/s/{site_key}/wlanconf", False),       # Alternative Legacy
                (f"/api/s/{site_key}/wlanconf", True),        # Alternative UniFi OS
                (f"/api/s/{site_key}/cmd/wlanconf", False),   # CMD endpoint Legacy
                (f"/api/s/{site_key}/cmd/wlanconf", True),    # CMD endpoint UniFi OS
            ]
            
            # Try each endpoint with the payload
            for endpoint, proxy_first in endpoints:
                self.log(f"Step 3: Trying WLAN creation with endpoint: {endpoint} (proxy_first={proxy_first})")
                self.log(f"Payload: {payload}")
                
                try:
                    r = self.sess.post(self._u(endpoint, proxy_first=proxy_first), json=payload, timeout=30)
                    self.log(f"Response status: {r.status_code}")
                    self.log(f"Response: {r.text}")
                    
                    # Check for successful response
                    if r.ok:
                        try:
                            response_data = r.json()
                            if (response_data.get("meta", {}).get("rc") == "ok" and 
                                "data" in response_data and 
                                len(response_data["data"]) > 0):
                                self.log(f"✓ WLAN created successfully using {endpoint}")
                                self.log(f"Created WLAN ID: {response_data['data'][0].get('_id', 'Unknown')}")
                                return True
                            else:
                                self.log(f"✗ Unexpected response format from {endpoint}: {response_data}")
                                continue
                        except Exception as parse_error:
                            self.log(f"✗ Failed to parse response from {endpoint}: {parse_error}")
                            continue
                    else:
                        self.log(f"✗ WLAN creation failed with {endpoint}: {r.status_code} - {r.text[:200]}...")
                        continue
                except Exception as e:
                    self.log(f"✗ Exception with {endpoint}: {e}")
                    continue
            
            self.log(f"✗ All WLAN creation methods failed")
            return False
                
        except Exception as e:
            self.log(f"Exception in wlangroup endpoint method: {e}")
            return False

    def _create_official_unifi_api_wlan_body(self, ssid: str, password: str) -> dict:
        """Create WLAN body using official UniFi Network Application API format"""
        return {
            "name": ssid,
            "passphrase": password,
            "enabled": True,
            "security": "wpapsk",
            "apGroupIds": [],  # Empty array = All APs (official API format)
            "hideSsid": False,
            "isGuest": False,
            "wlanBand": "both"  # Both 2.4GHz and 5GHz
        }

    def _create_all_aps_alt_wlan_body(self, ssid: str, password: str) -> dict:
        """Create WLAN body with All APs broadcasting (alternative approach)"""
        return {
            "name": ssid,
            "passphrase": password,
            "enabled": True,
            "security": "wpapsk",
            "apGroupIds": [],  # Empty array means all APs
            "hideSsid": False,
            "isGuest": False,
            "wlanBand": "both"
        }

    def _create_no_ap_group_fields_wlan_body(self, ssid: str, password: str) -> dict:
        """Create WLAN body without any AP group fields (let controller default to All)"""
        return {
            "name": ssid,
            "passphrase": password,
            "enabled": True,
            "security": "wpapsk",
            "hideSsid": False,
            "isGuest": False,
            "wlanBand": "both"
            # No AP group fields at all - let controller default to "All"
        }

    def _get_existing_wlans(self, site_key: str) -> list:
        """Get existing WLANs to understand the structure"""
        try:
            # Handle None or missing site_key
            if not site_key:
                site_key = "default"
            
            # Try different endpoints to get existing WLANs
            endpoints = [
                f"/api/s/{site_key}/rest/wlanconf",
                f"/api/s/{site_key}/list/wlanconf",
                f"/api/s/{site_key}/stat/wlanconf",
                f"/api/s/{site_key}/rest/wlan",
                f"/api/s/{site_key}/list/wlan",
                f"/api/s/{site_key}/stat/wlan"
            ]
            
            for endpoint in endpoints:
                try:
                    self.log(f"Trying to get WLANs from: {endpoint}")
                    r = self.sess.get(self._u(endpoint, proxy_first=True), timeout=15)
                    if r.ok:
                        data = self._j(r)
                        if isinstance(data, dict) and "data" in data:
                            wlans = data["data"]
                            self.log(f"Found {len(wlans)} WLANs via {endpoint}")
                            return wlans
                        elif isinstance(data, list):
                            self.log(f"Found {len(data)} WLANs via {endpoint}")
                            return data
                except Exception as e:
                    self.log(f"Failed to get WLANs from {endpoint}: {e}")
                    continue
            
            return []
        except Exception as e:
            self.log(f"Error getting existing WLANs: {e}")
            return []

    def _clone_existing_wlan(self, existing_wlan: dict, ssid: str, password: str) -> dict:
        """Clone an existing WLAN structure and modify for new SSID"""
        try:
            # Create a copy of the existing WLAN
            clone = existing_wlan.copy()
            
            # Remove fields that shouldn't be copied
            fields_to_remove = [
                "_id", "id", "site_id", "created_at", "updated_at", 
                "name", "x_passphrase", "enabled", "security"
            ]
            
            for field in fields_to_remove:
                clone.pop(field, None)
            
            # Set the new values
            clone["name"] = ssid
            clone["x_passphrase"] = password
            clone["enabled"] = True
            clone["security"] = "wpapsk"
            
            self.log(f"Cloned WLAN structure with fields: {list(clone.keys())}")
            return clone
            
        except Exception as e:
            self.log(f"Error cloning WLAN: {e}")
            # Fallback to minimal structure
            return self._create_minimal_wlan_body(ssid, password)

    def _clone_existing_wlan_no_ap_group(self, existing_wlan: dict, ssid: str, password: str) -> dict:
        """Clone an existing WLAN structure but remove AP group requirements"""
        try:
            # Create a copy of the existing WLAN
            clone = existing_wlan.copy()
            
            # Remove fields that shouldn't be copied
            fields_to_remove = [
                "_id", "id", "site_id", "created_at", "updated_at", 
                "name", "x_passphrase", "enabled", "security",
                "ap_group_ids", "ap_group_mode", "ap_group"
            ]
            
            for field in fields_to_remove:
                clone.pop(field, None)
            
            # Set the new values
            clone["name"] = ssid
            clone["x_passphrase"] = password
            clone["enabled"] = True
            clone["security"] = "wpapsk"
            
            # Ensure no AP group fields are present
            clone.pop("ap_group_ids", None)
            clone.pop("ap_group_mode", None)
            clone.pop("ap_group", None)
            
            self.log(f"Cloned WLAN structure (no AP group) with fields: {list(clone.keys())}")
            return clone
            
        except Exception as e:
            self.log(f"Error cloning WLAN (no AP group): {e}")
            # Fallback to minimal structure
            return self._create_minimal_wlan_body(ssid, password)

    def _get_existing_ap_groups(self, site_key: str) -> list:
        """Get existing AP groups from the controller"""
        try:
            # Handle None or missing site_key
            if not site_key:
                site_key = "default"
            
            # Try different endpoints to get AP groups
            endpoints = [
                f"/api/s/{site_key}/rest/apgroup",
                f"/api/s/{site_key}/list/apgroup",
                f"/api/s/{site_key}/stat/apgroup"
            ]
            
            for endpoint in endpoints:
                try:
                    self.log(f"Trying to get AP groups from: {endpoint}")
                    r = self.sess.get(self._u(endpoint, proxy_first=True), timeout=15)
                    if r.ok:
                        data = self._j(r)
                        if isinstance(data, dict) and "data" in data:
                            groups = data["data"]
                            self.log(f"Found {len(groups)} AP groups via {endpoint}")
                            return groups
                        elif isinstance(data, list):
                            self.log(f"Found {len(data)} AP groups via {endpoint}")
                            return data
                except Exception as e:
                    self.log(f"Failed to get AP groups from {endpoint}: {e}")
                    continue
            
            return []
        except Exception as e:
            self.log(f"Error getting existing AP groups: {e}")
            return []

    def _detect_wlan_endpoint(self, site_key: str) -> str:
        """Detect which WLAN endpoint is available on this controller"""
        # Handle None or missing site_key
        if not site_key:
            self.log("No site key provided, trying default site")
            site_key = "default"
        
        endpoints = [
            f"/api/s/{site_key}/rest/wlanconf",
            f"/api/s/{site_key}/cmd/wlanconf", 
            f"/api/s/{site_key}/add/wlanconf",
            f"/api/s/{site_key}/rest/wlan",
            f"/api/s/{site_key}/cmd/wlan",
            f"/api/s/{site_key}/add/wlan"
        ]
        
        self.log(f"Testing WLAN endpoints for site {site_key}...")
        for endpoint in endpoints:
            try:
                # Try a GET request to see if the endpoint exists
                self.log(f"Testing endpoint: {endpoint}")
                r = self.sess.get(self._u(endpoint, proxy_first=True), timeout=10)
                self.log(f"Response: {r.status_code} - {r.text[:200]}")
                if r.ok:
                    self.log(f"Found working WLAN endpoint: {endpoint}")
                    return endpoint
            except Exception as e:
                self.log(f"Endpoint {endpoint} failed: {e}")
                continue
        
        # Fallback to REST endpoint
        self.log("No working endpoints found, using fallback REST endpoint")
        return f"/api/s/{site_key}/rest/wlanconf"

    def _try_create_wlan(self, site_key: str, body: dict) -> bool:
        """Try to create a WLAN with the given configuration"""
        
        # Detect the correct endpoint first
        working_endpoint = self._detect_wlan_endpoint(site_key)

        def _try(rest_first=True):
            last = ""
            # Create endpoint list with detected working endpoint first
            all_endpoints = [
                ("REST", f"/api/s/{site_key}/rest/wlanconf"),
                ("CMD",  f"/api/s/{site_key}/cmd/wlanconf"),
                ("ADD",  f"/api/s/{site_key}/add/wlanconf")
            ]
            
            # Move working endpoint to front
            working_name = None
            for name, endpoint in all_endpoints:
                if endpoint == working_endpoint:
                    working_name = name
                    break
            
            if working_name:
                # Put working endpoint first
                endpoints = [(working_name, working_endpoint)]
                for name, endpoint in all_endpoints:
                    if endpoint != working_endpoint:
                        endpoints.append((name, endpoint))
            else:
                endpoints = all_endpoints
            for kind, path in endpoints:
                for proxy in (False, True):
                    try:
                        self.log(f"Trying {kind} endpoint: {path} (proxy={proxy})")
                        self.log(f"Payload: {body}")
                        r = self.sess.post(self._u(path, proxy_first=proxy), json=body, timeout=25)
                        self.log(f"Response: {r.status_code} - {r.text[:500]}")
                        if r.ok:
                            self.log(f"SUCCESS: WLAN created via {kind} endpoint")
                            return True, ""
                        last = f"{kind} {r.status_code}: {r.text[:400]}"
                    except Exception as ex:
                        self.log(f"Exception with {kind} endpoint: {ex}")
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
    def ssh_set_inform(self, ip: str, inform_url: Optional[str]=None, username: Optional[str]=None, password: Optional[str]=None, site_key: Optional[str]=None) -> bool:
        host = ip.strip()
        inform = (inform_url or self.inform_url).rstrip("/")
        
        # Try to get site-specific SSH credentials for adopted devices
        if site_key and not username and not password:
            site_creds = self.get_site_ssh_credentials(site_key)
            if site_creds:
                user = site_creds.get("username", self.ssh_user)
                pw = site_creds.get("password", self.ssh_pass)
                self.log(f"Using site-specific SSH credentials: {user}")
            else:
                user = self.ssh_user
                pw = self.ssh_pass
                self.log(f"Using default SSH credentials: {user}")
        else:
            user = username or self.ssh_user
            pw = password or self.ssh_pass
            self.log(f"Using provided SSH credentials: {user}")
        
        self.log(f"Attempting SSH set-inform to {host} with inform URL: {inform}")
        
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.log(f"Connecting to {host} as {user}...")
            cli.connect(host, username=user, password=pw, timeout=10)
            self.log(f"SSH connection successful to {host}")
            
            # Execute set-inform command using mca-cli-op (correct method for UniFi devices)
            cmd = f"mca-cli-op set-inform {inform}"
            self.log(f"Executing command: {cmd}")
            
            # Execute the command
            stdin, stdout, stderr = cli.exec_command(cmd, timeout=20)
            stdout_data = stdout.read().decode('utf-8', errors='ignore')
            stderr_data = stderr.read().decode('utf-8', errors='ignore')
            
            self.log(f"Command stdout: {stdout_data.strip()}")
            if stderr_data.strip():
                self.log(f"Command stderr: {stderr_data.strip()}")
            
            # Check if command was successful
            if "adoption request sent" in stdout_data.lower() or "adoption request" in stdout_data.lower():
                self.log(f"SUCCESS: Adoption request sent")
            elif "inform url set" in stdout_data.lower() or "inform set" in stdout_data.lower():
                self.log(f"SUCCESS: Inform URL set")
            elif "error" in stderr_data.lower() or "failed" in stderr_data.lower():
                self.log(f"ERROR: Command failed - {stderr_data.strip()}")
            else:
                self.log(f"INFO: Command completed - {stdout_data.strip()}")
            
            # Verify the inform URL was set by checking device status
            self.log("Verifying inform URL was set on device...")
            
            # Try multiple verification methods
            verification_success = False
            
            # Method 1: Check device info
            try:
                stdin, stdout, stderr = cli.exec_command("mca-cli-op info", timeout=15)
                info_output = stdout.read().decode('utf-8', errors='ignore')
                self.log(f"Device info output: {info_output}")
                
                if inform in info_output:
                    self.log(f"SUCCESS: Inform URL confirmed in device info: {inform}")
                    verification_success = True
            except Exception as e:
                self.log(f"Could not get device info: {e}")
            
            # Method 2: Check device status
            try:
                stdin, stdout, stderr = cli.exec_command("mca-cli-op status", timeout=15)
                status_output = stdout.read().decode('utf-8', errors='ignore')
                self.log(f"Device status output: {status_output}")
                
                if "adopted" in status_output.lower():
                    self.log("SUCCESS: Device shows as adopted")
                elif "adopting" in status_output.lower():
                    self.log("INFO: Device is in adopting state")
                elif "unadopted" in status_output.lower():
                    self.log("INFO: Device is unadopted")
                else:
                    self.log(f"INFO: Device status: {status_output.strip()}")
            except Exception as e:
                self.log(f"Could not get device status: {e}")
            
            # Method 3: Check device config file
            try:
                self.log("Checking device config file...")
                stdin, stdout, stderr = cli.exec_command("cat /etc/persistent/cfg/mgmt", timeout=15)
                config_output = stdout.read().decode('utf-8', errors='ignore')
                self.log(f"Device config output: {config_output}")
                
                if inform in config_output:
                    self.log(f"SUCCESS: Inform URL found in device config: {inform}")
                    verification_success = True
                else:
                    self.log(f"WARNING: Inform URL not found in device config. Expected: {inform}")
            except Exception as e:
                self.log(f"Could not check device config: {e}")
            
            if not verification_success:
                self.log(f"WARNING: Could not verify inform URL was set. Expected: {inform}")
            
            cli.close()
            self.log(f"SSH set-inform completed for {host}")
            
            # Wait a moment for the device to contact the controller
            import time
            self.log("Waiting for device to contact controller...")
            time.sleep(3)
            
            # Verify the device appears in the controller
            if site_key:
                self.log(f"Checking if device {host} appears in controller site {site_key}...")
                devices = self.get_devices(site_key)
                device_found = False
                for device in devices:
                    if device.get("ip") == host:
                        device_found = True
                        self.log(f"SUCCESS: Device {host} found in controller as {device.get('name', 'Unknown')}")
                        break
                
                if not device_found:
                    self.log(f"WARNING: Device {host} not yet visible in controller. It may take a few minutes to appear.")
            
            return True
            
        except Exception as e:
            self.log(f"SSH set-inform FAILED for {host}: {e}")
            return False

    def get_site_ssh_credentials(self, site_key: str) -> Optional[Dict]:
        """Get site-specific SSH credentials from the controller"""
        try:
            # Method 1: Try to get site settings
            r = self.sess.get(self._u(f"/api/s/{site_key}/get/setting", proxy_first=True), timeout=15)
            if r.ok:
                data = self._j(r)
                if isinstance(data, dict) and "data" in data:
                    settings = data["data"]
                    # Look for SSH settings in site configuration
                    ssh_settings = settings.get("ssh", {})
                    if ssh_settings:
                        self.log(f"Found SSH settings in site config: {ssh_settings}")
                        return {
                            "username": ssh_settings.get("username", self.ssh_user),
                            "password": ssh_settings.get("password", self.ssh_pass)
                        }
        except Exception as e:
            self.log(f"Failed to get site settings: {e}")
        
        # Method 2: Try to get from site-specific settings endpoint
        try:
            r = self.sess.get(self._u(f"/api/s/{site_key}/get/setting/device", proxy_first=True), timeout=15)
            if r.ok:
                data = self._j(r)
                if isinstance(data, dict) and "data" in data:
                    device_settings = data["data"]
                    # Look for SSH credentials in device settings
                    if "ssh" in device_settings:
                        ssh_creds = device_settings["ssh"]
                        self.log(f"Found SSH credentials in device settings: {ssh_creds}")
                        return {
                            "username": ssh_creds.get("username", self.ssh_user),
                            "password": ssh_creds.get("password", self.ssh_pass)
                        }
        except Exception as e:
            self.log(f"Failed to get device settings: {e}")
        
        # Method 3: Try to get from site info
        try:
            r = self.sess.get(self._u(f"/api/s/{site_key}/self", proxy_first=True), timeout=15)
            if r.ok:
                data = self._j(r)
                if isinstance(data, dict) and "data" in data:
                    site_info = data["data"]
                    # Look for SSH credentials in site info
                    if "ssh" in site_info:
                        ssh_creds = site_info["ssh"]
                        self.log(f"Found SSH credentials in site info: {ssh_creds}")
                        return {
                            "username": ssh_creds.get("username", self.ssh_user),
                            "password": ssh_creds.get("password", self.ssh_pass)
                        }
        except Exception as e:
            self.log(f"Failed to get site info: {e}")
        
        # Method 4: Try manual site SSH credentials from settings
        try:
            site_ssh_user = self.store.get_value("site_ssh_user", "")
            site_ssh_pass = self.store.get_value("site_ssh_pass", "")
            if site_ssh_user and site_ssh_pass:
                self.log(f"Trying manual site SSH credentials: {site_ssh_user}")
                test_result = self._test_ssh_credentials(site_ssh_user, site_ssh_pass, site_key)
                if test_result:
                    self.log(f"Found working manual SSH credentials: {site_ssh_user}")
                    return {
                        "username": site_ssh_user,
                        "password": site_ssh_pass
                    }
        except Exception as e:
            self.log(f"Failed to test manual SSH credentials: {e}")
        
        # Method 5: Try common UniFi SSH credential patterns
        try:
            # Common patterns for UniFi site-specific SSH credentials
            site_name = site_key.replace("-", "").lower()
            
            # Pattern 1: ubnt_sitename
            patterns = [
                f"ubnt_{site_name}",
                f"ubnt_{site_key}",
                f"admin_{site_name}",
                f"admin_{site_key}",
                site_name,
                site_key
            ]
            
            # Try each pattern with common passwords
            for username in patterns:
                if len(username) <= 20:  # UniFi username limit
                    # Common password patterns
                    passwords = [
                        username,  # Same as username
                        f"ubnt_{username}",
                        f"admin_{username}",
                        "ubnt",  # Default
                        "admin"  # Common
                    ]
                    
                    for password in passwords:
                        if len(password) <= 20:  # UniFi password limit
                            self.log(f"Trying SSH pattern: {username}/{password}")
                            # Test the credentials by trying to connect to a known device
                            test_result = self._test_ssh_credentials(username, password, site_key)
                            if test_result:
                                self.log(f"Found working SSH credentials: {username}/{password}")
                                return {
                                    "username": username,
                                    "password": password
                                }
        except Exception as e:
            self.log(f"Failed to test SSH patterns: {e}")
        
        self.log(f"No site-specific SSH credentials found for site: {site_key}")
        return None

    def _test_ssh_credentials(self, username: str, password: str, site_key: str) -> bool:
        """Test SSH credentials by trying to connect to a known device"""
        try:
            # Get a list of devices from the site to test credentials
            devices = self.get_devices(site_key)
            for device in devices:
                ip = device.get("ip")
                if ip and device.get("adopted"):
                    try:
                        cli = paramiko.SSHClient()
                        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        cli.connect(ip, username=username, password=password, timeout=5)
                        cli.close()
                        return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False

    def ssh_connect(self, ip: str, site_key: Optional[str]=None, username: Optional[str]=None, password: Optional[str]=None) -> Optional[paramiko.SSHClient]:
        """Connect to device via SSH and return client object"""
        host = ip.strip()
        
        # Try to get site-specific SSH credentials for adopted devices
        if site_key and not username and not password:
            site_creds = self.get_site_ssh_credentials(site_key)
            if site_creds:
                user = site_creds.get("username", self.ssh_user)
                pw = site_creds.get("password", self.ssh_pass)
            else:
                user = self.ssh_user
                pw = self.ssh_pass
        else:
            user = username or self.ssh_user
            pw = password or self.ssh_pass
        
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(host, username=user, password=pw, timeout=10)
            return cli
        except Exception as e:
            self.log(f"SSH connection failed to {host}: {e}")
            return None


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


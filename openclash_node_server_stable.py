#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClash 节点添加服务 - 稳定版
支持 URL 导入和手动输入，自动添加到所有策略组
使用备份文件方案：在备份文件上操作，验证通过后再原子性切换，只保留最新1个备份
支持协议含：SS / VMess / VLESS / Trojan / Hysteria(2) / TUIC / WireGuard / SOCKS5（socks5、socks5h、socks）
"""

import os
import sys
import json
import base64
import shutil
import time
import datetime
import subprocess
import urllib.parse
import urllib.request
import ssl
import shutil as _which_shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Tuple, Optional

# ========== 配置 ==========
DEFAULT_CONFIG_PATH = "/etc/openclash/config/config.yaml"  # 默认路径，会被自动检测覆盖
HOST = "0.0.0.0"
PORT = 8001  # 可被环境变量 OPENCLASH_NODE_SERVER_PORT 覆盖


class ReuseHTTPServer(HTTPServer):
    """允许快速重启时复用地址（无法解决「已另有进程在监听」）"""
    allow_reuse_address = True
DEDUP_STRATEGY = "rename"  # "skip" 或 "rename"
ALLOW_CHINESE_NAMES = True
LOG_FILE = "/tmp/openclash_node_server.log"
DEFAULT_SELF_UPDATE_URL = os.environ.get(
    "OPENCLASH_NODE_SERVER_SELF_UPDATE_URL",
    "https://raw.githubusercontent.com/kuku0799/zashboard-main/main/openclash_node_server_stable.py",
).strip()

# 全局变量
CONFIG_PATH = DEFAULT_CONFIG_PATH
USE_RUAMEL = False
yaml_loader = None
yaml_safe_load = None

# ========== 日志 ==========
def write_log(msg: str):
    """写入日志"""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"{ts} {msg}"
    print(log_msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except:
        pass

# ========== 动态检测配置文件路径 ==========
def find_active_config_path(use_log: bool = False) -> str:
    """动态检测 OpenClash 正在使用的配置文件路径"""
    try:
        # 方法1: 从 UCI 配置中读取（最可靠的方法）
        try:
            uci_result = subprocess.run(
                ["uci", "get", "openclash.@config[0].config_path"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if uci_result.returncode == 0:
                path = uci_result.stdout.strip()
                if path and os.path.exists(path):
                    if use_log:
                        write_log(f"从 UCI 配置找到配置文件: {path}")
                    return path
        except Exception as e:
            if use_log:
                write_log(f"从 UCI 读取配置失败: {e}")
        
        # 方法2: 从进程参数中查找
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "clash" in line.lower() and "-f" in line:
                        parts = line.split()
                        try:
                            idx = parts.index("-f")
                            if idx + 1 < len(parts):
                                path = parts[idx + 1]
                                if os.path.exists(path):
                                    if use_log:
                                        write_log(f"从进程参数找到配置文件: {path}")
                                    return path
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            if use_log:
                write_log(f"从进程查找配置失败: {e}")
        
        # 方法3: 从 /etc/config/openclash 文件中读取
        try:
            oc_config_file = "/etc/config/openclash"
            if os.path.exists(oc_config_file):
                with open(oc_config_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    import re
                    pattern = r"option config_path ['\"]([^'\"]+)['\"]"
                    match = re.search(pattern, content)
                    if match:
                        path = match.group(1)
                        if os.path.exists(path):
                            if use_log:
                                write_log(f"从配置文件找到: {path}")
                            return path
        except Exception as e:
            if use_log:
                write_log(f"从配置文件读取失败: {e}")
        
        # 方法4: 扫描 /etc/openclash/config/ 目录，找到最新的 .yaml 文件
        try:
            config_dir = "/etc/openclash/config"
            if os.path.exists(config_dir) and os.path.isdir(config_dir):
                yaml_files = []
                for filename in os.listdir(config_dir):
                    if filename.endswith((".yaml", ".yml")) and not filename.startswith("."):
                        filepath = os.path.join(config_dir, filename)
                        if os.path.isfile(filepath):
                            # 排除备份文件
                            if ".bak-" not in filename:
                                mtime = os.path.getmtime(filepath)
                                yaml_files.append((filepath, mtime))
                
                if yaml_files:
                    # 按修改时间排序，返回最新的
                    yaml_files.sort(key=lambda x: x[1], reverse=True)
                    path = yaml_files[0][0]
                    if use_log:
                        write_log(f"从目录扫描找到最新配置文件: {path}")
                    return path
        except Exception as e:
            if use_log:
                write_log(f"扫描配置目录失败: {e}")
        
        # 方法5: 检查常见路径（不包含硬编码文件名）
        common_paths = [
            "/etc/openclash/config.yaml",
            "/etc/openclash/config/config.yaml",
        ]
        for path in common_paths:
            if os.path.exists(path):
                if use_log:
                    write_log(f"从常见路径找到配置文件: {path}")
                return path
        
        # 方法6: 使用默认路径
        if use_log:
            write_log(f"使用默认配置文件路径: {DEFAULT_CONFIG_PATH}")
        return DEFAULT_CONFIG_PATH
    except Exception as e:
        if use_log:
            write_log(f"查找配置文件失败: {e}")
        return DEFAULT_CONFIG_PATH

# 初始化配置文件路径（不使用日志，因为 write_log 可能还未定义）
CONFIG_PATH = find_active_config_path(use_log=False)

# ========== YAML 库初始化 ==========
try:
    from ruamel.yaml import YAML
    USE_RUAMEL = True
    yaml_loader = YAML()
    yaml_loader.preserve_quotes = True
    yaml_loader.width = 4096
    yaml_safe_load = lambda f: yaml_loader.load(f)
    write_log("Using ruamel.yaml: True")
except ImportError:
    try:
        import yaml
        yaml_safe_load = yaml.safe_load
        write_log("Using ruamel.yaml: False (fallback to pyyaml)")
    except ImportError:
        write_log("ERROR: No YAML library found. Install: opkg install python3-yaml")
        sys.exit(1)

# ========== 工具函数 ==========
def decode_base64(s: str) -> str:
    """Base64 解码，自动补全 padding。
    先 URL 解码：订阅/分享里常见 method:pass 的 Base64 把尾部的 = 写成 %3D，urlparse 不会替 netloc 解码。"""
    s = urllib.parse.unquote(s.strip())
    s = s.replace("-", "+").replace("_", "/")
    while len(s) % 4:
        s += "="
    return base64.b64decode(s).decode("utf-8")

def is_valid_name(name: str) -> bool:
    """验证节点名称"""
    if not name or not name.strip():
        return False
    if not ALLOW_CHINESE_NAMES:
        try:
            name.encode("ascii")
        except UnicodeEncodeError:
            return False
    return True

def clean_name(name: str, existing: set) -> str:
    """清理并去重节点名称"""
    name = name.strip()
    if DEDUP_STRATEGY == "skip" and name in existing:
        return None
    if DEDUP_STRATEGY == "rename" and name in existing:
        count = 1
        while f"{name}_{count}" in existing:
            count += 1
        name = f"{name}_{count}"
    return name

def extract_custom_name(url: str) -> Optional[str]:
    """从 URL 中提取自定义名称（# 后面的部分）"""
    if "#" in url:
        return urllib.parse.unquote(url.split("#", 1)[1])
    return None

def display_name_from_url_optional(url_obj: urllib.parse.ParseResult) -> Optional[str]:
    """Shadowrocket 等：#fragment 或 ?remarks= / remark / name / note / ps"""
    if url_obj.fragment:
        return urllib.parse.unquote(url_obj.fragment)
    params = dict(urllib.parse.parse_qsl(url_obj.query, keep_blank_values=True))
    for key in ("remarks", "remark", "name", "note", "ps"):
        v = params.get(key)
        if v is not None and str(v).strip() != "":
            return urllib.parse.unquote(str(v))
    return None

def display_name_from_url(url_obj: urllib.parse.ParseResult, default: str) -> str:
    n = display_name_from_url_optional(url_obj)
    return n if n else default


def maybe_unwrap_shadowrocket_b64_outer(raw: str) -> str:
    """
    外层 scheme://Base64(内层标准内容)?remarks=... 且无 '@' 位于 netloc。
    内层格式随协议：SS 为 method:pass@h:p；vmess 为 JSON；其余多为 identity@h:p 或完整 scheme://...
    """
    u = raw.strip()
    if "://" not in u:
        return u
    try:
        scheme_part, _ = u.split("://", 1)
    except ValueError:
        return u
    scheme_low = scheme_part.lower()
    if scheme_low not in (
        "ss", "vmess", "vless", "trojan", "hysteria", "hysteria2", "tuic", "wireguard",
        "socks", "socks5", "socks5h", "socks4", "socks4a",
    ):
        return u
    url_obj = urllib.parse.urlparse(u)
    netloc = (url_obj.netloc or "").strip()
    path = (url_obj.path or "").strip()
    if path.startswith("/"):
        path = path[1:]
    blob = netloc + path
    if "@" in netloc or not blob:
        return u
    try:
        inner = decode_base64(blob.strip())
    except Exception:
        return u
    inner = inner.strip()
    tail_q = f"?{url_obj.query}" if url_obj.query else ""
    tail_f = f"#{url_obj.fragment}" if url_obj.fragment else ""

    if scheme_low in ("socks", "socks5", "socks5h", "socks4", "socks4a"):
        if "@" not in inner:
            return u
        return f"{scheme_part}://{inner}{tail_q}{tail_f}"

    if scheme_low == "ss":
        if "@" not in inner:
            return u
        return f"ss://{inner}{tail_q}{tail_f}"

    if scheme_low == "vmess":
        if not inner.startswith("{"):
            return u
        b = base64.b64encode(inner.encode("utf-8")).decode("ascii")
        return f"vmess://{b}{tail_q}{tail_f}"

    if scheme_low in ("vless", "trojan", "hysteria", "hysteria2", "tuic", "wireguard"):
        if inner.lower().startswith(scheme_low + "://"):
            base = inner
        elif "@" in inner:
            base = f"{scheme_low}://{inner}"
        else:
            return u
        return f"{base}{tail_q}{tail_f}"

    return u

# ========== URL 解析 ==========
def parse_ss_url(raw: str) -> Dict:
    """解析 SS URL（支持 ?remarks=；支持 method:密码@主机 明文内层）"""
    u = raw.strip()
    if u.startswith("SS://"):
        u = "ss://" + u[5:]
    if not u.startswith("ss://"):
        raise ValueError("not ss url")
    url_obj = urllib.parse.urlparse(u)
    name = display_name_from_url(url_obj, "ss-node")
    main_part = (url_obj.netloc or "").strip()
    pt = (url_obj.path or "").strip()
    if pt.startswith("/"):
        pt = pt[1:]
    main_part = main_part + pt
    
    # 检查是否有插件参数
    plugin_part = None
    if "/?" in main_part:
        main_part, plugin_part = main_part.split("/?", 1)
    
    if "@" in main_part:
        encoded, server_part = main_part.split("@", 1)
        try:
            decoded = decode_base64(encoded)
            method, password = decoded.split(":", 1)
        except Exception:
            method, password = encoded.split(":", 1)
        server, port = server_part.split(":", 1)
    else:
        decoded = decode_base64(main_part)
        at_idx = decoded.rindex("@")
        method_password = decoded[:at_idx]
        server_port = decoded[at_idx+1:]
        method, password = method_password.split(":", 1)
        server, port = server_port.split(":", 1)
    
    result = {
        "name": name,
        "type": "ss",
        "server": server,
        "port": int(port),
        "cipher": method,
        "password": password
    }
    
    # 解析插件参数
    if plugin_part:
        plugin_params = dict(urllib.parse.parse_qsl(plugin_part))
        plugin_name = plugin_params.get("plugin")
        if plugin_name:
            result["plugin"] = plugin_name
            plugin_opts = {}
            for key, value in plugin_params.items():
                if key != "plugin":
                    plugin_opts[key] = value
            if plugin_opts:
                result["plugin-opts"] = plugin_opts
    
    return result

def parse_vmess_url(raw: str) -> Dict:
    """解析 VMess URL（支持 path 承载 Base64；?remarks= 覆盖 JSON 内 ps）"""
    u = raw.strip()
    if u.upper().startswith("VMESS://"):
        u = "vmess://" + u[8:]
    url_obj = urllib.parse.urlparse(u)
    payload = (url_obj.netloc or "").strip()
    pt = (url_obj.path or "").strip().lstrip("/")
    if pt:
        payload = (payload + pt) if payload else pt
    if not payload:
        raise ValueError("VMess URL 无有效 payload")
    decoded = decode_base64(payload)
    data = json.loads(decoded)
    opt = display_name_from_url_optional(url_obj)
    name = opt if opt else data.get("ps", data.get("name", "vmess-node"))
    result = {
        "name": name,
        "type": "vmess",
        "server": data.get("add"),
        "port": int(data.get("port", 0)),
        "uuid": data.get("id"),
        "alterId": int(data.get("aid", 0)),
        "cipher": data.get("scy", data.get("cipher", "auto")),
        "network": data.get("net", data.get("network", "tcp")),
        "tls": data.get("tls") == "tls" or data.get("security") == "tls",
        "sni": data.get("sni"),
        "host": data.get("host"),
        "path": data.get("path"),
        "type_ws": data.get("type", ""),
        "udp": data.get("udp", True),  # 默认启用 UDP
    }
    
    # TLS 相关
    if data.get("skip-cert-verify"):
        result["skip-cert-verify"] = data.get("skip-cert-verify")
    # VMess 支持 alpn（可能是列表）
    if data.get("alpn"):
        alpn_value = data.get("alpn")
        if isinstance(alpn_value, list):
            result["alpn"] = alpn_value
        elif isinstance(alpn_value, str):
            result["alpn"] = [a.strip() for a in alpn_value.split(",") if a.strip()]
    if data.get("fingerprint"):
        result["fingerprint"] = data.get("fingerprint")
    
    # h2 网络类型的 host 字段（可能是列表）
    if result.get("network") == "h2" and data.get("host"):
        host_value = data.get("host")
        if isinstance(host_value, list):
            result["host"] = host_value
        elif isinstance(host_value, str):
            result["host"] = [h.strip() for h in host_value.split(",") if h.strip()]
    
    return result

def parse_vless_url(raw: str) -> Dict:
    """解析 VLESS URL"""
    url_obj = urllib.parse.urlparse(raw.strip())
    name = display_name_from_url(url_obj, "vless-node")
    params = dict(urllib.parse.parse_qsl(url_obj.query))
    
    # 检测 Reality 参数（优先判断，因为只要有 pbk 或 sid 就是 Reality）
    has_pbk = params.get("pbk") or params.get("publicKey")
    has_sid = params.get("sid") or params.get("shortId")
    is_reality = params.get("security", "").lower() == "reality" or params.get("reality") or has_pbk or has_sid
    
    # 记录解析日志
    write_log(f"解析 VLESS URL: {name}, security={params.get('security')}, has_pbk={bool(has_pbk)}, has_sid={bool(has_sid)}, is_reality={is_reality}")
    
    # 检测 TLS 类型
    security = params.get("security", "").lower()
    tls_type = None
    if is_reality:
        tls_type = "reality"
    elif security == "tls" or "tls" in params:
        tls_type = "tls"
    
    result = {
        "name": name,
        "type": "vless",
        "server": url_obj.hostname,
        "port": url_obj.port or 443,
        "uuid": url_obj.username,
        "tls": tls_type is not None,
        "tls_type": tls_type,
        "network": params.get("type", params.get("network", "tcp")),
        "sni": params.get("sni"),
        "host": params.get("host"),
        "path": params.get("path"),
        "flow": params.get("flow"),  # 流控：xtls-rprx-vision 等
        "encryption": params.get("encryption"),  # 加密方式，不设置默认值
        "udp": params.get("udp", "true").lower() != "false",  # 默认启用 UDP
    }
    
    # Reality 相关参数（优先处理）
    if is_reality:
        reality_opts = {}
        if has_pbk:
            reality_opts["public-key"] = params.get("pbk") or params.get("publicKey")
        if has_sid:
            reality_opts["short-id"] = params.get("sid") or params.get("shortId")
        # 注意：根据正确配置，servername 应该在顶层，不在 reality-opts 里
        # 这里先保存到 result，后面会在转换时移到顶层
        if params.get("sni"):
            result["sni"] = params.get("sni")  # 临时保存，后面会作为 servername
        if params.get("fp") or params.get("fingerprint"):
            reality_opts["fingerprint"] = params.get("fp") or params.get("fingerprint")
        if params.get("spx") or params.get("spiderX"):
            reality_opts["spider-x"] = params.get("spx") or params.get("spiderX")
        if reality_opts:
            result["reality-opts"] = reality_opts
            result["tls"] = True  # Reality 必须启用 TLS
            result["tls_type"] = "reality"
    
    # TLS 相关参数（非 Reality）
    elif tls_type == "tls":
        if params.get("allowInsecure") == "1" or params.get("allow-insecure") == "1":
            result["skip-cert-verify"] = True
        if params.get("alpn"):
            result["alpn"] = params.get("alpn")
        if params.get("fp") or params.get("fingerprint"):
            result["fingerprint"] = params.get("fp") or params.get("fingerprint")
    
    return result

def parse_trojan_url(raw: str) -> Dict:
    """解析 Trojan URL"""
    url_obj = urllib.parse.urlparse(raw.strip())
    name = display_name_from_url(url_obj, "trojan-node")
    params = dict(urllib.parse.parse_qsl(url_obj.query))
    
    result = {
        "name": name,
        "type": "trojan",
        "server": url_obj.hostname,
        "port": url_obj.port or 443,
        "password": url_obj.username,
        "sni": params.get("sni") or url_obj.hostname,
        "network": params.get("type", params.get("network", "tcp")),
        "host": params.get("host"),
        "path": params.get("path"),
        "udp": params.get("udp", "true").lower() != "false",  # 默认启用 UDP
    }
    
    # TLS 相关
    if params.get("allowInsecure") == "1" or params.get("allow-insecure") == "1":
        result["skip-cert-verify"] = True
    if params.get("alpn"):
        result["alpn"] = params.get("alpn")
    if params.get("fp") or params.get("fingerprint"):
        result["fingerprint"] = params.get("fp") or params.get("fingerprint")
    
    return result

def parse_hysteria_url(raw: str) -> Dict:
    """解析 Hysteria URL"""
    url_obj = urllib.parse.urlparse(raw.strip())
    name = display_name_from_url(url_obj, "hysteria-node")
    params = dict(urllib.parse.parse_qsl(url_obj.query))
    
    result = {
        "name": name,
        "type": "hysteria",
        "server": url_obj.hostname,
        "port": url_obj.port or 443,
        "auth": url_obj.username or params.get("auth"),
        "sni": params.get("peer") or params.get("sni") or url_obj.hostname,
        "protocol": params.get("protocol", "udp"),
    }
    
    # Hysteria 其他参数
    if params.get("obfs"):
        result["obfs"] = params.get("obfs")
    if params.get("obfsParam") or params.get("obfs-param"):
        result["obfs-password"] = params.get("obfsParam") or params.get("obfs-param")
    if params.get("up"):
        result["up"] = params.get("up")
    if params.get("down"):
        result["down"] = params.get("down")
    # Hysteria alpn 支持（列表格式）
    if params.get("alpn"):
        alpn_value = params.get("alpn")
        if isinstance(alpn_value, list):
            result["alpn"] = alpn_value
        elif isinstance(alpn_value, str):
            result["alpn"] = [a.strip() for a in alpn_value.split(",") if a.strip()]
    if params.get("insecure") == "1" or params.get("skip-cert-verify") == "1":
        result["skip-cert-verify"] = True
    if params.get("recvWindow") or params.get("recv-window"):
        result["recv-window"] = params.get("recvWindow") or params.get("recv-window")
    if params.get("recvWindowConn") or params.get("recv-window-conn"):
        result["recv-window-conn"] = params.get("recvWindowConn") or params.get("recv-window-conn")
    if params.get("disableMtuDiscovery") == "1" or params.get("disable-mtu-discovery") == "1":
        result["disable-mtu-discovery"] = True
    
    return result

def parse_hysteria2_url(raw: str) -> Dict:
    """解析 Hysteria2 URL"""
    url_obj = urllib.parse.urlparse(raw.strip())
    name = display_name_from_url(url_obj, "hysteria2-node")
    params = dict(urllib.parse.parse_qsl(url_obj.query))
    
    result = {
        "name": name,
        "type": "hysteria2",
        "server": url_obj.hostname,
        "port": url_obj.port or 443,
        "password": url_obj.username or params.get("password"),
        "sni": params.get("sni") or url_obj.hostname,
    }
    
    # Hysteria2 其他参数
    if params.get("obfs"):
        result["obfs"] = params.get("obfs")
    if params.get("obfs-password"):
        result["obfs-password"] = params.get("obfs-password")
    if params.get("up"):
        result["up"] = params.get("up")
    if params.get("down"):
        result["down"] = params.get("down")
    if params.get("alpn"):
        result["alpn"] = params.get("alpn")
    # Hysteria2 使用 insecure 字段（不是 skip-cert-verify）
    if params.get("insecure") == "1" or params.get("insecure") == "true":
        result["insecure"] = True
    elif params.get("insecure") == "0" or params.get("insecure") == "false":
        result["insecure"] = False
    if params.get("recv-window"):
        result["recv-window"] = params.get("recv-window")
    if params.get("recv-window-conn"):
        result["recv-window-conn"] = params.get("recv-window-conn")
    if params.get("disable-mtu-discovery") == "1":
        result["disable-mtu-discovery"] = True
    
    return result

def parse_tuic_url(raw: str) -> Dict:
    """解析 TUIC URL"""
    url_obj = urllib.parse.urlparse(raw.strip())
    name = display_name_from_url(url_obj, "tuic-node")
    params = dict(urllib.parse.parse_qsl(url_obj.query))
    
    result = {
        "name": name,
        "type": "tuic",
        "server": url_obj.hostname,
        "port": url_obj.port or 443,
        "uuid": url_obj.username,
        "password": params.get("password"),
        "sni": params.get("sni") or url_obj.hostname,
    }
    
    # TUIC 其他参数（根据模板）
    if params.get("congestion_controller") or params.get("congestion-controller"):
        result["congestion-controller"] = params.get("congestion_controller") or params.get("congestion-controller")
    if params.get("udp_relay_mode") or params.get("udp-relay-mode"):
        result["udp-relay-mode"] = params.get("udp_relay_mode") or params.get("udp-relay-mode")
    if params.get("udp_over_stream") == "1" or params.get("udp-over-stream") == "1":
        result["udp-over-stream"] = True
    if params.get("heartbeat"):
        result["heartbeat"] = params.get("heartbeat")
    if params.get("disable_sni") == "1" or params.get("disable-sni") == "1":
        result["disable-sni"] = True
    if params.get("reduce_rtt") == "1" or params.get("reduce-rtt") == "1":
        result["reduce-rtt"] = True
    if params.get("request_timeout") or params.get("request-timeout"):
        result["request-timeout"] = params.get("request_timeout") or params.get("request-timeout")
    if params.get("udp_relay_ipv6") == "1" or params.get("udp-relay-ipv6") == "1":
        result["udp-relay-ipv6"] = True
    if params.get("max_udp_relay_packet_size") or params.get("max-udp-relay-packet-size"):
        result["max-udp-relay-packet-size"] = params.get("max_udp_relay_packet_size") or params.get("max-udp-relay-packet-size")
    if params.get("fast_open") == "1" or params.get("fast-open") == "1":
        result["fast-open"] = True
    if params.get("skip_cert_verify") == "1" or params.get("skip-cert-verify") == "1":
        result["skip-cert-verify"] = True
    # TUIC 支持 alpn（列表格式）
    if params.get("alpn"):
        alpn_value = params.get("alpn")
        if isinstance(alpn_value, str):
            # 如果是字符串，尝试分割（支持逗号分隔）
            result["alpn"] = [a.strip() for a in alpn_value.split(",") if a.strip()]
        else:
            result["alpn"] = alpn_value
    
    return result

def parse_wireguard_url(raw: str) -> Dict:
    """解析 WireGuard URL"""
    url_obj = urllib.parse.urlparse(raw.strip())
    name = display_name_from_url(url_obj, "wireguard-node")
    params = dict(urllib.parse.parse_qsl(url_obj.query))
    
    result = {
        "name": name,
        "type": "wireguard",
        "server": url_obj.hostname,
        "port": int(params.get("port", 51820)),
        "public_key": url_obj.username,
        "private_key": params.get("private_key"),
        "dns": params.get("dns", "1.1.1.1"),
    }
    
    # WireGuard 其他参数
    if params.get("ip"):
        result["ip"] = params.get("ip")
    if params.get("allowed_ips") or params.get("allowed-ips"):
        result["allowed-ips"] = params.get("allowed_ips") or params.get("allowed-ips")
    if params.get("persistent_keepalive") or params.get("persistent-keepalive"):
        result["persistent-keepalive"] = params.get("persistent_keepalive") or params.get("persistent-keepalive")
    if params.get("reserved"):
        result["reserved"] = params.get("reserved")
    if params.get("mtu"):
        result["mtu"] = int(params.get("mtu"))
    if params.get("workers"):
        result["workers"] = int(params.get("workers"))
    if params.get("fwmark"):
        result["fwmark"] = params.get("fwmark")
    if params.get("preshared_key") or params.get("preshared-key"):
        result["pre-shared-key"] = params.get("preshared_key") or params.get("preshared-key")
    if params.get("local_addresses") or params.get("local-addresses"):
        result["local-addresses"] = params.get("local_addresses") or params.get("local-addresses")
    
    return result

def try_expand_socks_b64_userinfo(userinfo: str) -> Tuple[Optional[str], Optional[str]]:
    """
    兼容 Shadowrocket 等：userinfo 仅一段且为 Base64(username:password)，无 URL 标准第二段 password。
    若解码成功且含 ':'，返回 (用户名, 密码)；否则返回 (None, None) 表示不处理。
    """
    if not userinfo or not userinfo.strip():
        return None, None
    s = userinfo.strip()
    try:
        decoded = decode_base64(s)
        if ":" not in decoded:
            return None, None
        u, p = decoded.split(":", 1)
        return u, p
    except Exception:
        return None, None


def try_parse_socks_full_b64_blob(blob: str) -> Optional[Tuple[str, int, Optional[str], Optional[str]]]:
    """
    Shadowrocket 等：socks://Base64(username:password@host:port)?remarks=...
    netloc 中无 '@'，须整段 Base64 解码（须用原始 netloc，不可用 urlparse.hostname，否则大小写被破坏）。
    返回 (server, port, username, password)；失败返回 None。
    """
    if not blob or not blob.strip():
        return None
    try:
        inner = decode_base64(blob.strip())
    except Exception:
        return None
    inner = inner.strip()
    if "@" not in inner:
        return None
    userinfo, hostport = inner.rsplit("@", 1)
    userinfo, hostport = userinfo.strip(), hostport.strip()
    if ":" not in hostport:
        return None
    host, ps = hostport.rsplit(":", 1)
    host, ps = host.strip(), ps.strip()
    if not host or not ps.isdigit():
        return None
    port = int(ps)
    if ":" in userinfo:
        u, p = userinfo.split(":", 1)
    else:
        u, p = userinfo, ""
    u = u.strip()
    p = p.strip()
    return (host, port, u if u else None, p if p else None)

def parse_socks_url(raw: str) -> Dict:
    """
    解析 SOCKS URL（写入 Clash 的 type: socks5）。
    支持: socks5://、socks5h://、socks://、socks4://。
    - 标准: socks5://user:pass@host:port#name
    - user 单段 Base64(user:pass) @ host:port
    - 整段 netloc Base64(user:pass@host:port)，名称常在 ?remarks= / ?remark= / #fragment
    """
    url_obj = urllib.parse.urlparse(raw.strip())
    scheme = (url_obj.scheme or "").lower()
    params = dict(urllib.parse.parse_qsl(url_obj.query, keep_blank_values=True))
    name = display_name_from_url(url_obj, "socks-node")

    netloc = (url_obj.netloc or "").strip()
    path_tail = (url_obj.path or "").strip()
    if path_tail.startswith("/"):
        path_tail = path_tail[1:]
    blob = netloc + path_tail

    server: Optional[str] = None
    port: Optional[int] = None
    username = None
    password = None

    # 1) 整段 Base64(user:pass@host:port)，netloc 内通常没有 '@'
    if blob and "@" not in netloc:
        full = try_parse_socks_full_b64_blob(blob)
        if full:
            server, port, username, password = full
            write_log("SOCKS: 已解析为「整段 Base64(user:pass@host:port)」格式")

    # 2) 标准 user[:pass]@host:port（必须用 hostname，勿对整段 netloc 当域名解析）
    if server is None and "@" in netloc:
        server = url_obj.hostname
        if not server:
            raise ValueError("SOCKS URL 缺少主机名")
        port = url_obj.port if url_obj.port is not None else 1080
        username = urllib.parse.unquote(url_obj.username) if url_obj.username else None
        password = urllib.parse.unquote(url_obj.password) if url_obj.password else None

    # 3) 无 @：仅 host:port（必须从 netloc 拆，勿用 urlparse.hostname——会把 Base64 误当主机名并小写化）
    if server is None and netloc and "@" not in netloc:
        if netloc.startswith("["):
            br = netloc.find("]:")
            if br != -1:
                try:
                    server = netloc[1:br]
                    port = int(netloc[br + 2 :])
                except ValueError:
                    server = None
        if server is None:
            parts = netloc.rsplit(":", 1)
            if len(parts) == 2 and parts[1].isdigit():
                server, port = parts[0], int(parts[1])
        if server is None:
            raise ValueError(
                "SOCKS 链接无法解析：若为 Shadowrocket 导出的整段 Base64，请完整复制（字母大小写勿变）；"
                "否则请用 socks5://账号:密码@主机:端口 或 socks5://主机:端口"
            )

    if not server:
        raise ValueError("SOCKS URL 缺少主机名")

    # 4) 仅 user 为 Base64(user:pass)，password 为空
    if username and not password:
        u2, p2 = try_expand_socks_b64_userinfo(username)
        if p2 is not None:
            username, password = u2, p2
            write_log(f"SOCKS: userinfo 已按 Base64(username:password) 解码, 用户长度={len(username or '')}")

    if port is None:
        port = 1080
    if scheme in ("socks4", "socks4a"):
        write_log(f"提示: {scheme} 已按 socks5 写入配置；若服务端实为 SOCKS4，请在 Clash 中核对协议是否兼容")
    result: Dict = {
        "name": name,
        "type": "socks5",
        "server": server,
        "port": int(port),
    }
    if username:
        result["username"] = username
    if password:
        result["password"] = password
    udp_val = (params.get("udp") or "").lower()
    if udp_val in ("0", "false", "no"):
        result["udp"] = False
    else:
        result["udp"] = True
    if params.get("tls") in ("1", "true", "True", "yes"):
        result["tls"] = True
    if (
        params.get("allowInsecure") == "1"
        or params.get("allow-insecure") == "1"
        or params.get("insecure") == "1"
        or params.get("skip-cert-verify") == "1"
    ):
        result["skip-cert-verify"] = True
    if params.get("sni"):
        result["sni"] = params.get("sni")
    return result

def parse_urls_to_nodes(urls: List[str]) -> Tuple[List[Dict], List[str]]:
    """批量解析 URL 列表"""
    nodes = []
    errors = []

    def _parse_single_node_url(u: str):
        u = maybe_unwrap_shadowrocket_b64_outer(u)
        if u.startswith("ss://") or u.startswith("SS://"):
            return parse_ss_url(u)
        elif u.startswith("vmess://") or u.startswith("VMESS://"):
            return parse_vmess_url(u)
        elif u.startswith("vless://") or u.startswith("VLESS://"):
            return parse_vless_url(u)
        elif u.startswith("trojan://") or u.startswith("TROJAN://"):
            return parse_trojan_url(u)
        elif u.startswith("hysteria://") or u.startswith("HYSTERIA://"):
            return parse_hysteria_url(u)
        elif u.startswith("hysteria2://") or u.startswith("HYSTERIA2://"):
            return parse_hysteria2_url(u)
        elif u.startswith("tuic://") or u.startswith("TUIC://"):
            return parse_tuic_url(u)
        elif u.startswith("wireguard://") or u.startswith("WIREGUARD://"):
            return parse_wireguard_url(u)
        elif (
            u.lower().startswith("socks5://")
            or u.lower().startswith("socks5h://")
            or u.lower().startswith("socks://")
            or u.lower().startswith("socks4://")
            or u.lower().startswith("socks4a://")
        ):
            return parse_socks_url(u)
        raise ValueError(f"不支持的协议: {u[:50]}")

    def _fetch_subscription_payload(sub_url: str) -> Tuple[List[str], List[Dict]]:
        req = urllib.request.Request(
            sub_url,
            headers={"User-Agent": "Mozilla/5.0 openclash-node-server/1.0"},
            method="GET",
        )
        body = None
        last_err = None
        # 先走默认 SSL 校验；若路由器环境 TLS 兼容差导致 EOF，再降级为不校验证书
        for context in (None, ssl._create_unverified_context()):
            try:
                if context is None:
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        body = resp.read()
                else:
                    with urllib.request.urlopen(req, timeout=20, context=context) as resp:
                        body = resp.read()
                break
            except Exception as e:
                last_err = e
                body = None
        if body is None:
            # 回退方案：通过本机 Clash HTTP 代理抓取（适配路由器直连 TLS EOF 场景）
            # 可通过环境变量 OPENCLASH_SUB_FETCH_PROXY 覆盖，默认 http://127.0.0.1:7890
            proxy = os.environ.get("OPENCLASH_SUB_FETCH_PROXY", "http://127.0.0.1:7890").strip()
            wget_bin = _which_shutil.which("wget")
            if wget_bin:
                env = os.environ.copy()
                env["http_proxy"] = proxy
                env["https_proxy"] = proxy
                env["HTTP_PROXY"] = proxy
                env["HTTPS_PROXY"] = proxy
                env["all_proxy"] = proxy
                env["ALL_PROXY"] = proxy
                env["no_proxy"] = "127.0.0.1,localhost"
                env["NO_PROXY"] = "127.0.0.1,localhost"
                # BusyBox wget 通常支持环境变量代理，必要时可追加 -Y on
                res = subprocess.run(
                    [wget_bin, "-qO-", "--no-check-certificate", sub_url],
                    capture_output=True,
                    timeout=25,
                    env=env,
                )
                if res.returncode == 0 and res.stdout:
                    body = res.stdout
                    write_log(f"订阅抓取回退成功：通过代理 {proxy}")
            if body is None:
                raise last_err if last_err else RuntimeError("fetch subscription failed")
        text = body.decode("utf-8", errors="ignore").strip()
        if not text:
            return [], []

        # 1) 兼容 Clash YAML 订阅：直接读取 proxies 列表
        try:
            yaml_obj = yaml_safe_load(text)
            if isinstance(yaml_obj, dict) and isinstance(yaml_obj.get("proxies"), list):
                clash_nodes = []
                for p in yaml_obj.get("proxies") or []:
                    if isinstance(p, dict) and p.get("name") and p.get("type"):
                        clash_nodes.append(dict(p))
                if clash_nodes:
                    return [], clash_nodes
        except Exception:
            pass

        # 2) 纯文本/链接行订阅
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # 常见订阅是 base64(多行节点链接)；若原文中一条链接都没有，尝试整体解码
        if not any("://" in ln for ln in lines):
            compact = "".join(lines)
            try:
                decoded = decode_base64(compact)
                lines = [ln.strip() for ln in decoded.splitlines() if ln.strip()]
            except Exception:
                pass
        return [ln for ln in lines if "://" in ln], []
    
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            if url.lower().startswith("http://") or url.lower().startswith("https://"):
                sub_lines, clash_nodes = _fetch_subscription_payload(url)
                if clash_nodes:
                    nodes.extend(clash_nodes)
                    continue
                if not sub_lines:
                    errors.append(f"订阅内容为空或无可识别节点: {url[:80]}")
                    continue
                for line in sub_lines:
                    try:
                        nodes.append(_parse_single_node_url(line))
                    except Exception as e:
                        errors.append(f"订阅解析失败 {line[:50]}: {str(e)}")
            else:
                nodes.append(_parse_single_node_url(url))
        except Exception as e:
            errors.append(f"解析失败 {url[:50]}: {str(e)}")
    
    return nodes, errors

# ========== 节点格式转换 ==========
def to_clash_node(node: Dict) -> Dict:
    """将通用节点格式转换为 Clash 格式"""
    node_type = node.get("type", "").lower()
    # 按照标准格式顺序构建基础配置
    base = {
        "name": node.get("name", "").strip(),
        "type": node_type,
        "server": node.get("server", ""),
        "port": int(node.get("port", 0)),
    }
    
    if node_type == "ss":
        base["cipher"] = node.get("method") or node.get("cipher", "aes-256-gcm")
        base["password"] = node.get("password", "")
        if not base["password"]:
            raise ValueError("SS 节点缺少 password")
        
        # SS 插件
        if node.get("plugin"):
            base["plugin"] = node["plugin"]
        if node.get("plugin-opts"):
            base["plugin-opts"] = node["plugin-opts"]
        
        # UDP 支持
        if "udp" in node:
            base["udp"] = node["udp"]
    elif node_type == "vmess":
        base["uuid"] = node.get("uuid", "")
        base["alterId"] = int(node.get("alterId", 0))
        base["cipher"] = node.get("cipher", node.get("security", "auto"))
        if not base["uuid"]:
            raise ValueError("VMess 节点缺少 uuid")
        
        # UDP 支持
        if "udp" in node:
            base["udp"] = node["udp"]
    elif node_type == "vless":
        base["uuid"] = node.get("uuid", "")
        if not base["uuid"]:
            raise ValueError("VLESS 节点缺少 uuid")
        
        # 加密方式 (encryption) - 应该在 flow 之前处理
        if node.get("encryption"):
            base["encryption"] = node["encryption"]
        elif node.get("encryption") is None and node.get("flow"):
            # 如果有 flow 但没有 encryption，默认设置为 none
            base["encryption"] = "none"
        
        # 流控 (flow) - 注意：Reality 不使用 flow
        if node.get("flow"):
            base["flow"] = node["flow"]
        
        # UDP 支持 - Reality 节点建议显式设置
        if "udp" in node:
            base["udp"] = node["udp"]
        # 对于 Reality 节点，默认启用 UDP
        elif "reality-opts" in node or node.get("tls_type") == "reality":
            base["udp"] = True
        
        # Reality 配置 - 优先判断，因为 Reality 需要 tls: true
        # 方法1: 直接提供了 reality-opts
        if node.get("reality-opts"):
            base["tls"] = True
            base["reality-opts"] = node["reality-opts"]
            write_log(f"VLESS 节点 {base.get('name', '')} 使用直接提供的 reality-opts")
        else:
            # 方法2: 检查 tls_type
            tls_type = node.get("tls_type")
            # 方法3: 通过字段判断是否为 Reality（有 public-key 或 short-id 就是 Reality）
            has_public_key = node.get("public-key") or node.get("publicKey") or node.get("pbk")
            has_short_id = node.get("short-id") or node.get("shortId") or node.get("sid")
            
            # 方法4: 检查 extra 字段中是否有 Reality 参数（双重保险，因为 extra 可能还没被提取）
            if not has_public_key and not has_short_id and tls_type != "reality":
                extra = node.get("extra", {})
                if isinstance(extra, dict):
                    has_public_key = extra.get("public-key") or extra.get("publicKey") or extra.get("pbk")
                    has_short_id = extra.get("short-id") or extra.get("shortId") or extra.get("sid")
                    if extra.get("tls_type") == "reality":
                        tls_type = "reality"
                    # 如果从 extra 中找到了 Reality 字段，提取到 node 中
                    if has_public_key:
                        node["public-key"] = has_public_key
                    if has_short_id:
                        node["short-id"] = has_short_id
                    if tls_type == "reality":
                        node["tls_type"] = "reality"
            
            is_reality = (tls_type == "reality" or has_public_key or has_short_id)
            
            if is_reality:
                write_log(f"VLESS 节点 {base.get('name', '')} 检测到 Reality: tls_type={tls_type}, has_public_key={bool(has_public_key)}, has_short_id={bool(has_short_id)}")
            
            if is_reality:
                reality_opts = {}
                # 支持多种字段名
                if node.get("public-key"):
                    reality_opts["public-key"] = node["public-key"]
                elif node.get("publicKey"):
                    reality_opts["public-key"] = node["publicKey"]
                elif node.get("pbk"):
                    reality_opts["public-key"] = node["pbk"]
                
                if node.get("short-id"):
                    reality_opts["short-id"] = node["short-id"]
                elif node.get("shortId"):
                    reality_opts["short-id"] = node["shortId"]
                elif node.get("sid"):
                    reality_opts["short-id"] = node["sid"]
                
                # 注意：根据模板，servername 应该在顶层，不在 reality-opts 里
                # 先提取 servername 到顶层
                if node.get("sni"):
                    base["servername"] = node["sni"]
                elif node.get("server-name"):
                    base["servername"] = node["server-name"]
                elif node.get("servername"):
                    base["servername"] = node["servername"]
                
                if node.get("fingerprint") or node.get("fp"):
                    reality_opts["fingerprint"] = node.get("fingerprint") or node.get("fp")
                
                if node.get("spider-x") or node.get("spiderX") or node.get("spx"):
                    reality_opts["spider-x"] = node.get("spider-x") or node.get("spiderX") or node.get("spx")
                
                if reality_opts:
                    base["tls"] = True  # Reality 必须启用 TLS
                    base["reality-opts"] = reality_opts
                    write_log(f"VLESS 节点 {base.get('name', '')} 检测到 Reality 配置: {list(reality_opts.keys())}")
            else:
                # 普通 TLS 或非 TLS
                base["tls"] = node.get("tls", False)
    elif node_type == "trojan":
        base["password"] = node.get("password", "")
        base["sni"] = node.get("sni") or base["server"]
        if not base["password"]:
            raise ValueError("Trojan 节点缺少 password")
        
        # UDP 支持
        if "udp" in node:
            base["udp"] = node["udp"]
        
        # skip-cert-verify 应该在顶层（注意模板里有 typo: skip-cert-verfy，我们支持两种）
        if node.get("skip-cert-verify") or node.get("skip-cert-verfy"):
            base["skip-cert-verify"] = True
        
        # alpn 支持（可能是列表）
        if node.get("alpn"):
            alpn_value = node.get("alpn")
            if isinstance(alpn_value, list):
                base["alpn"] = alpn_value
            elif isinstance(alpn_value, str):
                # 如果是字符串，尝试分割
                base["alpn"] = [a.strip() for a in alpn_value.split(",") if a.strip()]
    elif node_type == "hysteria":
        # Hysteria 特殊字段
        if node.get("auth"):
            base["auth"] = node["auth"]
        if node.get("auth_str"):
            base["auth-str"] = node["auth_str"]
        if node.get("obfs"):
            base["obfs"] = node["obfs"]
        if node.get("obfs-password"):
            base["obfs-password"] = node["obfs-password"]
        if node.get("up"):
            base["up"] = node["up"]
        if node.get("down"):
            base["down"] = node["down"]
        # Hysteria alpn 支持（列表格式）
        if node.get("alpn"):
            alpn_value = node.get("alpn")
            if isinstance(alpn_value, list):
                base["alpn"] = alpn_value
            elif isinstance(alpn_value, str):
                base["alpn"] = [a.strip() for a in alpn_value.split(",") if a.strip()]
        if node.get("skip-cert-verify"):
            base["skip-cert-verify"] = node["skip-cert-verify"]
        if node.get("recv-window"):
            base["recv-window"] = node["recv-window"]
        if node.get("recv-window-conn"):
            base["recv-window-conn"] = node["recv-window-conn"]
        if node.get("disable-mtu-discovery"):
            base["disable-mtu-discovery"] = node["disable-mtu-discovery"]
        if node.get("sni"):
            base["sni"] = node["sni"]
        if node.get("protocol"):
            base["protocol"] = node["protocol"]
    
    elif node_type == "hysteria2":
        # Hysteria2 特殊字段（根据模板，使用 insecure 而不是 skip-cert-verify）
        if node.get("password"):
            base["password"] = node["password"]
        if node.get("obfs"):
            base["obfs"] = node["obfs"]
        if node.get("obfs-password"):
            base["obfs-password"] = node["obfs-password"]
        if node.get("up"):
            base["up"] = node["up"]
        if node.get("down"):
            base["down"] = node["down"]
        if node.get("alpn"):
            alpn_value = node.get("alpn")
            if isinstance(alpn_value, list):
                base["alpn"] = alpn_value
            elif isinstance(alpn_value, str):
                base["alpn"] = [a.strip() for a in alpn_value.split(",") if a.strip()]
        # Hysteria2 使用 insecure 字段（不是 skip-cert-verify）
        if "insecure" in node:
            base["insecure"] = node["insecure"]
        elif node.get("skip-cert-verify"):
            # 兼容旧字段名
            base["insecure"] = node["skip-cert-verify"]
        if node.get("recv-window"):
            base["recv-window"] = node["recv-window"]
        if node.get("recv-window-conn"):
            base["recv-window-conn"] = node["recv-window-conn"]
        if node.get("disable-mtu-discovery"):
            base["disable-mtu-discovery"] = node["disable-mtu-discovery"]
        if node.get("sni"):
            base["sni"] = node["sni"]
    
    elif node_type == "tuic":
        # TUIC 特殊字段
        if node.get("uuid"):
            base["uuid"] = node["uuid"]
        if node.get("password"):
            base["password"] = node["password"]
        if node.get("congestion-controller"):
            base["congestion-controller"] = node["congestion-controller"]
        if node.get("udp-relay-mode"):
            base["udp-relay-mode"] = node["udp-relay-mode"]
        if node.get("udp-over-stream"):
            base["udp-over-stream"] = node["udp-over-stream"]
        if node.get("heartbeat"):
            base["heartbeat"] = node["heartbeat"]
        if node.get("disable-sni"):
            base["disable-sni"] = node["disable-sni"]
        if node.get("reduce-rtt"):
            base["reduce-rtt"] = node["reduce-rtt"]
        if node.get("request-timeout"):
            base["request-timeout"] = node["request-timeout"]
        if node.get("udp-relay-ipv6"):
            base["udp-relay-ipv6"] = node["udp-relay-ipv6"]
        if node.get("max-udp-relay-packet-size"):
            base["max-udp-relay-packet-size"] = node["max-udp-relay-packet-size"]
        if node.get("fast-open"):
            base["fast-open"] = node["fast-open"]
        if node.get("skip-cert-verify"):
            base["skip-cert-verify"] = node["skip-cert-verify"]
        # TUIC alpn 支持（列表格式）
        if node.get("alpn"):
            alpn_value = node.get("alpn")
            if isinstance(alpn_value, list):
                base["alpn"] = alpn_value
            elif isinstance(alpn_value, str):
                base["alpn"] = [a.strip() for a in alpn_value.split(",") if a.strip()]
        if node.get("sni"):
            base["sni"] = node["sni"]
    
    elif node_type == "wireguard":
        # WireGuard 特殊字段
        if node.get("public_key"):
            base["public-key"] = node["public_key"]
        elif node.get("public-key"):
            base["public-key"] = node["public-key"]
        if node.get("private_key"):
            base["private-key"] = node["private_key"]
        elif node.get("private-key"):
            base["private-key"] = node["private-key"]
        if node.get("dns"):
            base["dns"] = node["dns"]
        if node.get("ip"):
            base["ip"] = node["ip"]
        if node.get("allowed-ips"):
            base["allowed-ips"] = node["allowed-ips"]
        if node.get("persistent-keepalive"):
            base["persistent-keepalive"] = node["persistent-keepalive"]
        if node.get("reserved"):
            base["reserved"] = node["reserved"]
        if node.get("mtu"):
            base["mtu"] = node["mtu"]
        if node.get("workers"):
            base["workers"] = node["workers"]
        if node.get("fwmark"):
            base["fwmark"] = node["fwmark"]
        if node.get("pre-shared-key"):
            base["pre-shared-key"] = node["pre-shared-key"]
        if node.get("local-addresses"):
            base["local-addresses"] = node["local-addresses"]
    
    elif node_type == "socks5":
        if node.get("username"):
            base["username"] = node["username"]
        if node.get("password"):
            base["password"] = node["password"]
        if "udp" in node:
            base["udp"] = bool(node["udp"])
        if node.get("tls"):
            base["tls"] = True
        if node.get("skip-cert-verify"):
            base["skip-cert-verify"] = bool(node["skip-cert-verify"])
        if node.get("sni"):
            base["servername"] = node["sni"]
    
    # 传输协议（SOCKS5 无 ws/grpc 等，跳过整段）
    if node_type != "socks5":
        network = node.get("network", "tcp")
        if network == "ws":
            ws_opts = {}
            # Host 在 headers 里（标准格式）
            if node.get("host"):
                ws_opts["headers"] = {"Host": node["host"]}
            elif node.get("type_ws") == "http":
                # VMess 的 type 字段
                if node.get("host"):
                    ws_opts["headers"] = {"Host": node["host"]}
            # path 在 ws-opts 顶层（标准格式）
            if node.get("path"):
                ws_opts["path"] = node["path"]
            # VMess 的 max-early-data（可选）
            if node.get("max-early-data"):
                ws_opts["max-early-data"] = int(node["max-early-data"])
            if node.get("early-data-header-name"):
                ws_opts["early-data-header-name"] = node["early-data-header-name"]
            if ws_opts:
                base["network"] = "ws"
                base["ws-opts"] = ws_opts
        elif network == "http":
            http_opts = {}
            if node.get("method"):
                http_opts["method"] = node["method"]
            if node.get("path"):
                http_opts["path"] = node["path"]
            if node.get("host"):
                http_opts["headers"] = {"Host": node["host"]}
            if http_opts:
                base["network"] = "http"
                base["http-opts"] = http_opts
        elif network == "h2":
            h2_opts = {}
            # h2-opts 的 host 应该是列表格式（根据模板）
            if node.get("host"):
                host_value = node["host"]
                if isinstance(host_value, list):
                    h2_opts["host"] = host_value
                elif isinstance(host_value, str):
                    # 如果是字符串，尝试分割（支持逗号分隔）
                    h2_opts["host"] = [h.strip() for h in host_value.split(",") if h.strip()]
            if node.get("path"):
                h2_opts["path"] = node["path"]
            if h2_opts:
                base["network"] = "h2"
                base["h2-opts"] = h2_opts
        elif network == "grpc":
            grpc_opts = {}
            if node.get("path"):
                grpc_opts["grpc-service-name"] = node["path"]
            if node.get("grpc-service-name"):
                grpc_opts["grpc-service-name"] = node["grpc-service-name"]
            if grpc_opts:
                base["network"] = "grpc"
                base["grpc-opts"] = grpc_opts
        else:
            # 默认 tcp，但如果有其他字段也要设置
            base["network"] = network
    
    # TLS (非 Reality 模式) - 只处理普通 TLS，Reality 已经在上面处理了（SOCKS5 over TLS 仅需顶层 tls/skip-cert-verify，避免塞入多余 tls-opts）
    if base.get("tls") and "reality-opts" not in base and node_type != "socks5":
        # servername 应该在顶层（标准格式，不是 tls-opts 里）
        if node.get("sni"):
            base["servername"] = node["sni"]
        elif node.get("servername"):
            base["servername"] = node["servername"]
        
        # client-fingerprint 应该在顶层（用于 TLS 指纹伪装）
        if node.get("client-fingerprint"):
            base["client-fingerprint"] = node["client-fingerprint"]
        
        # skip-cert-verify 应该在顶层（标准格式）
        if node.get("skip-cert-verify"):
            base["skip-cert-verify"] = node["skip-cert-verify"]
        
        # 其他 TLS 选项（fingerprint, alpn）放在 tls-opts 里（只有存在时才创建）
        tls_opts = {}
        if node.get("fingerprint") and not base.get("client-fingerprint"):
            # 如果已经有 client-fingerprint，就不需要 tls-opts 里的 fingerprint
            tls_opts["fingerprint"] = node["fingerprint"]
        if node.get("alpn"):
            tls_opts["alpn"] = node["alpn"] if isinstance(node["alpn"], list) else [node["alpn"]]
        # 只有当有 tls-opts 内容时才添加（标准格式中，简单的 TLS 不需要 tls-opts）
        if tls_opts:
            base["tls-opts"] = tls_opts
    
    # 确保 VLESS Reality 节点有必要的字段
    if node_type == "vless" and "reality-opts" in base:
        # Reality 节点必须启用 TLS
        base["tls"] = True
        
        # 注意：根据正确配置，flow 字段可以保留（不删除）
        # flow 字段保留，不删除
        
        # 确保有 public-key 和 short-id（至少这两个是必需的）
        reality_opts = base["reality-opts"]
        if not reality_opts.get("public-key"):
            write_log(f"警告: VLESS Reality 节点 {base.get('name', '')} 缺少 public-key")
        if not reality_opts.get("short-id"):
            write_log(f"警告: VLESS Reality 节点 {base.get('name', '')} 缺少 short-id")
        
        # 重要：servername 应该在顶层，不在 reality-opts 里！
        # 如果节点有 sni 或 server-name，应该作为顶层的 servername
        if node.get("sni"):
            base["servername"] = node["sni"]
        elif node.get("servername"):
            base["servername"] = node["servername"]
        elif node.get("server-name"):
            base["servername"] = node["server-name"]
        # 如果 reality-opts 里有临时保存的 _sni_temp，提取到顶层
        elif reality_opts.get("_sni_temp"):
            base["servername"] = reality_opts["_sni_temp"]
            del reality_opts["_sni_temp"]
            write_log(f"将 SNI 从 reality-opts 移到顶层 servername: {base['servername']}")
        # 如果 reality-opts 里有 server-name，也提取到顶层
        elif reality_opts.get("server-name"):
            base["servername"] = reality_opts["server-name"]
            del reality_opts["server-name"]
            write_log(f"将 server-name 从 reality-opts 移到顶层 servername: {base['servername']}")
        
        # reality-opts 中不应该有 server-name、dest 和 _sni_temp（根据正确配置，只有 public-key 和 short-id）
        if "server-name" in reality_opts:
            del reality_opts["server-name"]
        if "dest" in reality_opts:
            del reality_opts["dest"]
        if "_sni_temp" in reality_opts:
            del reality_opts["_sni_temp"]
        
        # Reality 节点必须添加 client-fingerprint（这是必需的！）
        # client-fingerprint 应该在顶层，不是 reality-opts 里
        if node.get("client-fingerprint"):
            base["client-fingerprint"] = node["client-fingerprint"]
        elif "client-fingerprint" not in base:
            # Reality 必须设置 client-fingerprint，如果没有提供，使用默认值 "chrome"
            base["client-fingerprint"] = "chrome"
            write_log(f"为 VLESS Reality 节点 {base.get('name', '')} 自动添加 client-fingerprint: chrome")
        
        # 确保 UDP 已设置（Reality 节点建议显式设置）
        if "udp" not in base:
            base["udp"] = True
        
        # skip-cert-verify 应该在顶层（如果提供了）
        if node.get("skip-cert-verify"):
            base["skip-cert-verify"] = node["skip-cert-verify"]
        
        # 记录完整的 Reality 配置用于调试
        write_log(f"VLESS Reality 节点 {base.get('name', '')} 最终配置: tls={base.get('tls')}, servername={base.get('servername')}, client-fingerprint={base.get('client-fingerprint')}, flow={base.get('flow')}, skip-cert-verify={base.get('skip-cert-verify')}, reality-opts={list(reality_opts.keys())}")
    
    # 确保所有节点都有 network 字段（SOCKS5 不要求、也不应带 network）
    if node_type == "socks5":
        base.pop("network", None)
    elif "network" not in base:
        base["network"] = node.get("network", "tcp")
    
    # 对于 VLESS Reality 节点，重新组织字段顺序以确保符合标准格式
    if node_type == "vless" and "reality-opts" in base:
        # 按照正确配置的顺序重新组织
        ordered_fields = ["name", "type", "server", "port", "uuid", "network", "servername", "flow", "udp", "tls", "reality-opts", "client-fingerprint", "skip-cert-verify"]
        ordered_base = {}
        # 先添加有序字段（按正确顺序）
        for field in ordered_fields:
            if field in base:
                ordered_base[field] = base[field]
        # 再添加其他字段（encryption 等）
        for key, value in base.items():
            if key not in ordered_base:
                ordered_base[key] = value
        base = ordered_base
        write_log(f"VLESS Reality 节点 {base.get('name', '')} 字段顺序已优化")
    
    return base

# ========== 配置备份和恢复 ==========
def backup_config() -> str:
    """备份当前 YAML 到 config 目录下"""
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    # 备份文件放在与配置文件相同的目录下
    config_dir = os.path.dirname(CONFIG_PATH)
    config_name = os.path.basename(CONFIG_PATH)
    backup_path = os.path.join(config_dir, f"{config_name}.bak-{ts}")
    shutil.copy2(CONFIG_PATH, backup_path)
    write_log(f"备份配置到: {backup_path}")
    return backup_path

def cleanup_old_backups(keep_latest: int = 1):
    """清理旧的备份文件，只保留最新的 N 个"""
    config_dir = os.path.dirname(CONFIG_PATH)
    config_name = os.path.basename(CONFIG_PATH)
    backup_pattern = f"{config_name}.bak-"
    
    # 查找所有备份文件
    backup_files = []
    try:
        for filename in os.listdir(config_dir):
            if filename.startswith(backup_pattern):
                filepath = os.path.join(config_dir, filename)
                if os.path.isfile(filepath):
                    backup_files.append((filepath, os.path.getmtime(filepath)))
    except Exception as e:
        write_log(f"查找备份文件失败: {e}")
        return
    
    # 按修改时间排序（最新的在前）
    backup_files.sort(key=lambda x: x[1], reverse=True)
    
    # 删除多余的备份文件（保留最新的 keep_latest 个）
    if len(backup_files) > keep_latest:
        for filepath, _ in backup_files[keep_latest:]:
            try:
                os.remove(filepath)
                write_log(f"已删除旧备份: {os.path.basename(filepath)}")
            except Exception as e:
                write_log(f"删除备份文件失败 {filepath}: {e}")

def restore_config(backup_path: str):
    """从备份恢复"""
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, CONFIG_PATH)
        write_log(f"从备份恢复: {backup_path}")

# ========== 配置加载和保存 ==========
def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            if USE_RUAMEL:
                return yaml_loader.load(f)
            else:
                return yaml_safe_load(f)
    except Exception as e:
        write_log(f"加载配置失败: {e}")
        raise

def verify_config(config_path: str) -> bool:
    """验证配置文件"""
    try:
        result = subprocess.run(
            ["/etc/init.d/openclash", "verify_config", config_path],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            return True
        # 如果命令失败，尝试基本 YAML 语法检查
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_safe_load(f)
        return True
    except Exception as e:
        write_log(f"YAML 语法检查失败: {e}")
        return False

# ========== 节点注入 ==========
def inject_proxies(config, nodes: List[Dict], add_to_groups: bool = True) -> Tuple[int, int, int]:
    """注入节点到配置，并添加到所有策略组"""
    if "proxies" not in config or not isinstance(config["proxies"], list):
        config["proxies"] = []
    
    existing_names = {proxy.get("name", "").strip() for proxy in config["proxies"]}
    new_nodes = []
    injected = 0
    skipped_invalid = 0
    skipped_duplicate = 0
    added_node_names = []
    
    # 添加节点到 proxies 列表
    for node in nodes:
        # 清理节点名称（去除首尾空格）
        name = node.get("name", "").strip()
        node["name"] = name  # 更新节点名称
        
        if not is_valid_name(name):
            skipped_invalid += 1
            continue
        
        if DEDUP_STRATEGY == "skip" and name in existing_names:
            skipped_duplicate += 1
            continue
        
        # rename 策略：自动重命名
        if DEDUP_STRATEGY == "rename" and name in existing_names:
            original = name
            count = 1
            while name in existing_names:
                name = f"{original}_{count}"
                count += 1
            node["name"] = name
        
        new_nodes.append(node)
        existing_names.add(name)
        added_node_names.append(name)
        injected += 1
    
    config["proxies"].extend(new_nodes)
    write_log(f"添加了 {injected} 个节点到 proxies 列表")
    
    # 添加到所有策略组
    if add_to_groups and added_node_names and "proxy-groups" in config:
        groups_updated = 0
        for group in config["proxy-groups"]:
            if not isinstance(group, dict):
                continue
            
            # 确保 proxies 字段存在且是列表
            if "proxies" not in group:
                group["proxies"] = []
            if not isinstance(group["proxies"], list):
                group["proxies"] = []
            
            # 清理策略组中已有节点名称的空格
            group_proxies = group.get("proxies", [])
            group_proxies_cleaned = [p.strip() if isinstance(p, str) else str(p).strip() for p in group_proxies]
            group["proxies"] = group_proxies_cleaned
            
            # 只保留 DIRECT 作为基础规则：移除 REJECT，确保 DIRECT 存在且靠前
            group["proxies"] = [p for p in group["proxies"] if p != "REJECT"]
            if "DIRECT" not in group["proxies"]:
                group["proxies"].insert(0, "DIRECT")
            
            # 为每个新节点添加到策略组
            for node_name in added_node_names:
                node_name_clean = node_name.strip()
                if node_name_clean not in group["proxies"]:
                    group["proxies"].append(node_name_clean)
                    groups_updated += 1
        
        write_log(f"更新了 {groups_updated} 个策略组，添加了 {len(added_node_names)} 个新节点")
    
    return injected, skipped_invalid, skipped_duplicate


def _proxy_names_in_config(config) -> set:
    """配置中 proxies 列表里出现的节点名（仅顶层手写节点）。"""
    out = set()
    for p in config.get("proxies") or []:
        if isinstance(p, dict) and p.get("name"):
            out.add(str(p["name"]).strip())
    return out


def ensure_unique_chain_group_name(config, base: str) -> str:
    """生成不与现有 proxy-groups 重名的组名。"""
    existing = set()
    for g in config.get("proxy-groups") or []:
        if isinstance(g, dict) and g.get("name"):
            existing.add(str(g["name"]).strip())
    name = (base or "chain-relay")[:120]
    if name not in existing:
        return name
    i = 2
    while i < 10000:
        cand = f"{base[:100]}_{i}"
        if cand not in existing:
            return cand
        i += 1
    return f"{base[:80]}_{int(time.time())}"


def inject_chain_group_into_select_groups(config, chain_group_name: str) -> None:
    """将链式组名加入各策略组候选（跳过 relay 链本身）。"""
    for group in config.get("proxy-groups") or []:
        if not isinstance(group, dict):
            continue
        if group.get("type") == "relay":
            continue
        gname = str(group.get("name", "")).strip()
        if gname == chain_group_name:
            continue
        if "proxies" not in group:
            group["proxies"] = []
        if not isinstance(group["proxies"], list):
            group["proxies"] = []
        if chain_group_name not in group["proxies"]:
            group["proxies"].append(chain_group_name)


def upsert_relay_group(config, transit: str, exit_: str, preferred_name: Optional[str]) -> str:
    """创建或更新 relay 组，返回最终组名。"""
    groups = config.setdefault("proxy-groups", [])
    default_base = f"链式-{transit}-{exit}"
    base = (preferred_name or "").strip() or default_base

    for g in groups:
        if isinstance(g, dict) and str(g.get("name", "")).strip() == base:
            if g.get("type") == "relay":
                g["proxies"] = [transit, exit_]
                write_log(f"已更新 relay 组: {base}")
                return base
            base = ensure_unique_chain_group_name(config, default_base)
            break

    final_name = ensure_unique_chain_group_name(config, base)
    for g in groups:
        if isinstance(g, dict) and str(g.get("name", "")).strip() == final_name and g.get("type") == "relay":
            g["proxies"] = [transit, exit_]
            write_log(f"已更新 relay 组: {final_name}")
            return final_name

    groups.append({"name": final_name, "type": "relay", "proxies": [transit, exit_]})
    write_log(f"已添加 relay 组: {final_name}")
    return final_name


def apply_chain_proxy(
    config,
    transit_name: str,
    exit_name: str,
    mode: str,
    chain_group_name: Optional[str] = None,
) -> Dict:
    """
    mode: relay | dialer | both
    返回: warnings, relay_group_name, dialer_applied, applied_mode
    """
    transit_name = transit_name.strip()
    exit_name = exit_name.strip()
    warnings: List[str] = []

    if not transit_name or not exit_name:
        raise ValueError("transit_name 与 exit_name 不能为空")
    if transit_name == exit_name:
        raise ValueError("中转与落地不能为同一节点")

    names = _proxy_names_in_config(config)
    if transit_name not in names:
        raise ValueError(f"中转节点不在配置 proxies 中: {transit_name}")
    if exit_name not in names:
        raise ValueError(f"落地节点不在配置 proxies 中: {exit_name}")

    mode_l = (mode or "both").lower()
    if mode_l not in ("relay", "dialer", "both"):
        raise ValueError("mode 必须是 relay、dialer 或 both")

    relay_group_name: Optional[str] = None
    dialer_applied = False

    if mode_l in ("relay", "both"):
        relay_group_name = upsert_relay_group(config, transit_name, exit_name, chain_group_name)
        inject_chain_group_into_select_groups(config, relay_group_name)

    if mode_l in ("dialer", "both"):
        exit_proxy = None
        for p in config.get("proxies") or []:
            if isinstance(p, dict) and str(p.get("name", "")).strip() == exit_name:
                exit_proxy = p
                break
        if exit_proxy is None:
            warnings.append("落地节点未在 proxies 中找到，dialer-proxy 未写入")
        else:
            exit_proxy["dialer-proxy"] = transit_name
            dialer_applied = True
            write_log(f"已为节点 {exit_name} 设置 dialer-proxy={transit_name}")

    return {
        "warnings": warnings,
        "relay_group_name": relay_group_name,
        "dialer_applied": dialer_applied,
        "applied_mode": mode_l,
    }


def promote_backup_to_live_and_restart(backup_path: str) -> None:
    """验证通过后：备份文件覆盖正式配置并尽量重启 OpenClash（与 delete-nodes 逻辑一致）。"""
    cleanup_old_backups(keep_latest=1)
    shutil.move(backup_path, CONFIG_PATH)
    new_backup = backup_config()
    write_log(f"已创建新备份: {os.path.basename(new_backup)}")
    try:
        os.sync()
    except Exception:
        pass

    write_log("切换 OpenClash 使用的配置文件...")
    try:
        status_result = subprocess.run(
            ["/etc/init.d/openclash", "status"],
            capture_output=True,
            timeout=5,
            text=True,
        )

        if status_result.returncode == 0:
            write_log("OpenClash 正在运行，切换配置文件...")
            try:
                uci_result = subprocess.run(
                    ["uci", "set", f"openclash.@config[0].config_path={CONFIG_PATH}"],
                    capture_output=True,
                    timeout=5,
                    text=True,
                )

                if uci_result.returncode == 0:
                    commit_result = subprocess.run(
                        ["uci", "commit", "openclash"],
                        capture_output=True,
                        timeout=5,
                        text=True,
                    )
                    if commit_result.returncode == 0:
                        write_log(f"✓ 已通过 UCI 切换配置文件: {CONFIG_PATH}")
                        write_log("重启 OpenClash 以应用新配置...")
                        restart_result = subprocess.run(
                            ["/etc/init.d/openclash", "restart"],
                            capture_output=True,
                            timeout=30,
                            text=True,
                        )
                        if restart_result.returncode == 0:
                            write_log("✓ OpenClash 已重启")
                            time.sleep(3)
                        else:
                            write_log(f"⚠️ 重启失败，返回码: {restart_result.returncode}")
                            if restart_result.stderr:
                                write_log(f"错误信息: {restart_result.stderr}")
                            if restart_result.stdout:
                                write_log(f"输出信息: {restart_result.stdout}")
                    else:
                        write_log(f"UCI commit 失败: {commit_result.stderr}")
                else:
                    write_log(f"UCI set 失败: {uci_result.stderr}")
                    write_log("尝试直接修改配置文件...")
                    oc_config_file = "/etc/config/openclash"
                    if os.path.exists(oc_config_file):
                        try:
                            import re
                            with open(oc_config_file, "r", encoding="utf-8") as f:
                                content = f.read()
                            pattern = r"option config_path ['\"]([^'\"]+)['\"]"
                            if re.search(pattern, content):
                                new_content = re.sub(pattern, f"option config_path '{CONFIG_PATH}'", content)
                                with open(oc_config_file, "w", encoding="utf-8") as f:
                                    f.write(new_content)
                                write_log(f"✓ 已修改 OpenClash 配置文件: {CONFIG_PATH}")
                                restart_result = subprocess.run(
                                    ["/etc/init.d/openclash", "restart"],
                                    capture_output=True,
                                    timeout=30,
                                    text=True,
                                )
                                if restart_result.returncode == 0:
                                    write_log("✓ OpenClash 已重启")
                                    time.sleep(3)
                                else:
                                    write_log(f"⚠️ 重启失败，返回码: {restart_result.returncode}")
                            else:
                                write_log("未找到 config_path 配置项")
                                write_log("尝试直接重启 OpenClash...")
                                restart_result = subprocess.run(
                                    ["/etc/init.d/openclash", "restart"],
                                    capture_output=True,
                                    timeout=30,
                                    text=True,
                                )
                                if restart_result.returncode == 0:
                                    write_log("✓ OpenClash 已重启")
                                    time.sleep(3)
                        except Exception as e:
                            write_log(f"修改配置文件失败: {e}")
            except Exception as e:
                write_log(f"切换配置文件失败: {e}")
                write_log("尝试直接重启 OpenClash...")
                try:
                    restart_result = subprocess.run(
                        ["/etc/init.d/openclash", "restart"],
                        capture_output=True,
                        timeout=30,
                        text=True,
                    )
                    if restart_result.returncode == 0:
                        write_log("✓ OpenClash 已重启")
                        time.sleep(3)
                except Exception as e2:
                    write_log(f"重启 OpenClash 失败: {e2}")
        else:
            write_log("OpenClash 未运行，配置文件已切换")
            write_log("提示：启动 OpenClash 时会使用新配置")
    except Exception as e:
        write_log(f"检查 OpenClash 状态时出错: {e}")
        write_log("尝试直接重启 OpenClash...")
        try:
            restart_result = subprocess.run(
                ["/etc/init.d/openclash", "restart"],
                capture_output=True,
                timeout=30,
                text=True,
            )
            if restart_result.returncode == 0:
                write_log("✓ OpenClash 已重启")
                time.sleep(3)
        except Exception as e2:
            write_log(f"重启 OpenClash 失败: {e2}")

# ========== HTTP 处理器 ==========
class Handler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        """设置 CORS 头"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
    
    def _send_json(self, status: int, data: dict):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    
    def do_GET(self):
        """处理 GET 请求"""
        if self.path == "/list-nodes":
            # 获取节点列表
            try:
                data = load_config()
                proxies = data.get("proxies", [])
                write_log(f"获取节点列表: 配置文件中有 {len(proxies)} 个节点")
                
                # 返回节点列表（只返回必要信息）
                nodes_list = []
                for proxy in proxies:
                    if not isinstance(proxy, dict):
                        write_log(f"警告: 节点不是字典类型: {type(proxy)}")
                        continue
                    node_info = {
                        "name": proxy.get("name", ""),
                        "type": proxy.get("type", ""),
                        "server": proxy.get("server", ""),
                        "port": proxy.get("port", 0),
                    }
                    # 只添加有效的节点（至少要有名称）
                    if node_info["name"]:
                        nodes_list.append(node_info)
                    else:
                        write_log(f"警告: 跳过无名称的节点: {proxy}")
                
                write_log(f"返回 {len(nodes_list)} 个有效节点")
                self._send_json(200, {
                    "ok": True,
                    "nodes": nodes_list,
                    "count": len(nodes_list)
                })
            except Exception as e:
                import traceback
                write_log(f"获取节点列表失败: {e}")
                write_log(f"错误详情: {traceback.format_exc()}")
                self._send_json(500, {"ok": False, "error": str(e)})
        else:
            self._send_json(404, {"ok": False, "error": "not found"})
    
    def do_POST(self):
        """处理 POST 请求"""
        if self.path == "/add-nodes":
            self._handle_add_nodes()
        elif self.path == "/delete-nodes":
            self._handle_delete_nodes()
        elif self.path == "/add-chain" or self.path == "/chain-proxy":
            self._handle_add_chain()
        elif self.path == "/update-self-script":
            self._handle_update_self_script()
        else:
            self._send_json(404, {"ok": False, "error": "not found"})

    def _handle_update_self_script(self):
        """更新当前运行的 openclash_node_server_stable.py 文件（更新后需重启进程生效）"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        try:
            payload = json.loads(body or "{}")
        except Exception as e:
            self._send_json(400, {"ok": False, "error": f"invalid json: {e}"})
            return

        script_url = str(payload.get("script_url") or DEFAULT_SELF_UPDATE_URL).strip()
        if not script_url:
            self._send_json(400, {"ok": False, "error": "script_url is required"})
            return

        script_path = os.path.abspath(__file__)
        temp_path = script_path + ".new"
        backup_path = script_path + ".bak"

        try:
            write_log(f"开始更新脚本: {script_url}")
            req = urllib.request.Request(
                script_url,
                headers={"User-Agent": "openclash-node-server-updater/1.0"},
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                code = resp.getcode()
                if code != 200:
                    raise RuntimeError(f"下载失败，HTTP {code}")
                raw = resp.read()

            content = raw.decode("utf-8")
            if "class Handler" not in content or "def run(" not in content:
                raise RuntimeError("下载内容校验失败：看起来不是有效脚本")

            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass

            # 先备份，再原子替换
            shutil.copy2(script_path, backup_path)
            os.replace(temp_path, script_path)
            write_log(f"脚本更新完成: {script_path}（已备份: {backup_path}）")

            self._send_json(
                200,
                {
                    "ok": True,
                    "updated": True,
                    "script_url": script_url,
                    "script_path": script_path,
                    "backup_path": backup_path,
                    "need_restart": True,
                    "message": "脚本已更新，需重启 openclash_node_server_stable.py 进程后生效",
                },
            )
        except Exception as e:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            write_log(f"更新脚本失败: {e}")
            self._send_json(500, {"ok": False, "error": str(e)})
    
    def _handle_add_nodes(self):
        """处理添加节点请求"""
        
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            payload = json.loads(body)
        except Exception as e:
            self._send_json(400, {"ok": False, "error": f"invalid json: {e}"})
            return
        
        nodes = payload.get("nodes")
        urls = payload.get("urls")
        
        if not nodes and not urls:
            self._send_json(400, {"ok": False, "error": "nodes or urls must be provided"})
            return
        
        backup_path = None
        try:
            # ========== 方案：在备份文件上操作，验证通过后再切换 ==========
            # 1. 备份当前配置文件（备份到 config 目录下）
            backup_path = backup_config()
            write_log(f"已备份配置文件到: {backup_path}")
            
            # 2. 在备份文件上操作（不创建临时文件，直接使用备份文件）
            with open(backup_path, "r", encoding="utf-8") as f:
                data = yaml_safe_load(f)
            if data is None:
                data = {}
            
            # 处理 URL 导入
            parse_errors = []
            if urls:
                write_log(f"开始解析 {len(urls)} 个 URL")
                parsed_nodes, parse_errors = parse_urls_to_nodes(urls)
                write_log(f"URL 解析完成: 成功 {len(parsed_nodes)} 个节点, 错误 {len(parse_errors)} 个")
                for i, node in enumerate(parsed_nodes):
                    write_log(f"解析的节点 {i+1}: {node.get('name', 'unknown')}, 类型: {node.get('type', 'unknown')}, 字段: {list(node.keys())}")
                    if node.get('type') == 'vless':
                        write_log(f"  - TLS: {node.get('tls', False)}, TLS类型: {node.get('tls_type')}, Flow: {node.get('flow')}, Encryption: {node.get('encryption')}")
                        write_log(f"  - Reality-opts: {node.get('reality-opts')}")
                        write_log(f"  - Public-key: {node.get('public-key') or node.get('publicKey') or node.get('pbk')}")
                        write_log(f"  - Short-id: {node.get('short-id') or node.get('shortId') or node.get('sid')}")
                nodes = parsed_nodes if not nodes else nodes + parsed_nodes
            
            # 处理手动输入的节点
            if nodes:
                # 转换前端传来的节点格式
                clash_nodes = []
                for n in nodes:
                    # 记录原始节点数据（用于调试）
                    write_log(f"处理节点: {n.get('name', 'unknown')}, 类型: {n.get('type', 'unknown')}, 字段: {list(n.keys())}")
                    # 检查 extra 字段，可能包含额外信息（前端可能把一些字段放在这里）
                    if 'extra' in n and isinstance(n['extra'], dict):
                        write_log(f"  发现 extra 字段: {list(n['extra'].keys())}")
                        # 将 extra 中的字段合并到主节点数据中（优先提取，避免覆盖已有字段）
                        for key, value in n['extra'].items():
                            if key not in n:  # 避免覆盖已有字段
                                n[key] = value
                                write_log(f"    从 extra 提取字段: {key} = {value}")
                        # 特别处理：如果 extra 中有 Reality 相关字段，确保 tls 被设置为 true
                        if n.get('type', '').lower() == 'vless':
                            has_reality_fields = (
                                n.get('tls_type') == 'reality' or
                                n.get('public-key') or n.get('publicKey') or n.get('pbk') or
                                n.get('short-id') or n.get('shortId') or n.get('sid') or
                                'reality-opts' in n
                            )
                            if has_reality_fields and not n.get('tls'):
                                n['tls'] = True
                                write_log(f"  检测到 Reality 字段，自动设置 tls=true")
                    clash_node = to_clash_node(n)
                    # 清理节点名称（去除首尾空格）
                    if 'name' in clash_node:
                        clash_node['name'] = clash_node['name'].strip()
                    # 记录转换后的节点数据（用于调试）
                    write_log(f"转换后节点: {clash_node.get('name', 'unknown')}, TLS: {clash_node.get('tls', False)}, Reality: {'reality-opts' in clash_node}")
                    if 'reality-opts' in clash_node:
                        write_log(f"  Reality-opts: {clash_node['reality-opts']}")
                    clash_nodes.append(clash_node)
                
                # 注入节点（自动添加到所有策略组）
                injected, skipped_invalid, skipped_duplicate = inject_proxies(data, clash_nodes, add_to_groups=True)
                write_log(f"已注入 {injected} 个节点到备份文件")
                
                # 3. 保存到备份文件
                with open(backup_path, "w", encoding="utf-8") as f:
                    if USE_RUAMEL:
                        yaml_loader.dump(data, f)
                    else:
                        import yaml
                        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                    f.flush()
                    try:
                        if hasattr(f, 'fileno'):
                            os.fsync(f.fileno())
                    except:
                        pass
                
                write_log("备份文件已保存（包含新节点）")
                
                # 4. 验证备份文件
                write_log("验证备份文件...")
                if not verify_config(backup_path):
                    raise RuntimeError("备份文件验证失败，YAML 格式可能有问题")
                
                # 5. 再次读取备份文件，确认节点确实存在并验证配置
                with open(backup_path, "r", encoding="utf-8") as f:
                    verify_data = yaml_safe_load(f)
                    if clash_nodes:
                        test_node_name = clash_nodes[0].get("name", "").strip()
                        proxy_names = [p.get("name", "").strip() for p in verify_data.get("proxies", [])]
                        if test_node_name not in proxy_names:
                            raise RuntimeError(f"验证失败：节点 '{test_node_name}' 不在备份文件中（当前 proxies: {proxy_names[:5]}...）")
                        
                        # 找到测试节点并验证其配置（特别是 Reality 节点）
                        test_node = None
                        for p in verify_data.get("proxies", []):
                            if p.get("name", "").strip() == test_node_name:
                                test_node = p
                                break
                        
                        if test_node:
                            write_log(f"验证节点配置: {test_node_name}")
                            write_log(f"  - type: {test_node.get('type')}")
                            write_log(f"  - server: {test_node.get('server')}")
                            write_log(f"  - port: {test_node.get('port')}")
                            write_log(f"  - tls: {test_node.get('tls')}")
                            write_log(f"  - network: {test_node.get('network')}")
                            if test_node.get('type') == 'vless':
                                write_log(f"  - uuid: {test_node.get('uuid', '')[:8]}...")
                                write_log(f"  - encryption: {test_node.get('encryption')}")
                                write_log(f"  - udp: {test_node.get('udp')}")
                                write_log(f"  - client-fingerprint: {test_node.get('client-fingerprint')}")
                                if 'reality-opts' in test_node:
                                    ro = test_node['reality-opts']
                                    write_log(f"  - reality-opts: public-key={bool(ro.get('public-key'))}, short-id={bool(ro.get('short-id'))}, server-name={ro.get('server-name')}, dest={ro.get('dest')}")
                                    # 验证必需字段
                                    if not ro.get('public-key'):
                                        write_log(f"  ⚠️ 警告: reality-opts 缺少 public-key")
                                    if not ro.get('short-id'):
                                        write_log(f"  ⚠️ 警告: reality-opts 缺少 short-id")
                                    if not ro.get('server-name') and not ro.get('dest'):
                                        write_log(f"  ⚠️ 警告: reality-opts 缺少 server-name 或 dest")
                                if not test_node.get('client-fingerprint'):
                                    write_log(f"  ⚠️ 警告: VLESS Reality 节点缺少 client-fingerprint（这是必需的！）")
                        
                        # 检查策略组（考虑名称可能有空格）
                        groups_with_node = 0
                        for g in verify_data.get("proxy-groups", []):
                            if isinstance(g, dict):
                                group_proxies = [p.strip() if isinstance(p, str) else str(p).strip() for p in g.get("proxies", [])]
                                if test_node_name in group_proxies:
                                    groups_with_node += 1
                        
                        if groups_with_node == 0:
                            # 列出第一个策略组的节点，用于调试
                            if len(verify_data.get("proxy-groups", [])) > 0:
                                first_group = verify_data["proxy-groups"][0]
                                first_proxies = first_group.get("proxies", [])
                                raise RuntimeError(f"验证失败：节点 '{test_node_name}' 不在任何策略组中（第一个策略组节点: {first_proxies[:5]}...）")
                        
                        write_log(f"验证通过：节点 '{test_node_name}' 在 {groups_with_node} 个策略组中")
                
                # 6. 原子性切换：备份文件 -> 正式文件
                write_log("验证通过，开始切换配置文件...")
                
                # 不停止 OpenClash，直接替换文件，然后通过 API 重载
                
                # 6.1. 清理旧备份文件（在切换前，只保留最新的 1 个）
                # 注意：此时备份文件还在，需要保留它，所以保留最新的 1 个（就是当前这个）
                cleanup_old_backups(keep_latest=1)
                
                # 6.2. 原子性替换：备份文件 -> 正式文件
                shutil.move(backup_path, CONFIG_PATH)
                backup_path = None  # 标记已成功切换，不需要清理
                write_log(f"配置文件切换成功: {CONFIG_PATH}")
                
                # 6.3. 切换后，从正式文件创建一个新的备份（确保有 2 个文件：正式文件 + 最新备份）
                new_backup = backup_config()
                write_log(f"已创建新备份: {os.path.basename(new_backup)}")
                
                # 强制刷新文件系统
                try:
                    os.sync()
                except:
                    pass
                
                # 6.4. 切换 OpenClash 使用的配置文件
                write_log("切换 OpenClash 使用的配置文件...")
                try:
                    # 检查 OpenClash 是否正在运行
                    status_result = subprocess.run(
                        ["/etc/init.d/openclash", "status"],
                        capture_output=True,
                        timeout=5,
                        text=True
                    )
                    
                    if status_result.returncode == 0:
                        write_log("OpenClash 正在运行，切换配置文件...")
                        
                        # 方法1: 通过 UCI 命令切换配置文件（这是 OpenClash 的标准方式）
                        try:
                            # 获取配置文件名（不含路径）
                            config_filename = os.path.basename(CONFIG_PATH)
                            write_log(f"切换配置文件到: {config_filename}")
                            
                            # 使用 UCI 命令切换配置文件
                            uci_result = subprocess.run(
                                ["uci", "set", f"openclash.@config[0].config_path={CONFIG_PATH}"],
                                capture_output=True,
                                timeout=5,
                                text=True
                            )
                            
                            if uci_result.returncode == 0:
                                # 提交 UCI 配置
                                commit_result = subprocess.run(
                                    ["uci", "commit", "openclash"],
                                    capture_output=True,
                                    timeout=5,
                                    text=True
                                )
                                if commit_result.returncode == 0:
                                    write_log(f"✓ 已通过 UCI 切换配置文件: {CONFIG_PATH}")
                                    
                                    # 重启 OpenClash（使用 restart 而不是 reload，确保完整重启）
                                    write_log("重启 OpenClash 以应用新配置...")
                                    restart_result = subprocess.run(
                                        ["/etc/init.d/openclash", "restart"],
                                        capture_output=True,
                                        timeout=30,
                                        text=True
                                    )
                                    if restart_result.returncode == 0:
                                        write_log("✓ OpenClash 已重启")
                                        # 等待 OpenClash 完全启动
                                        time.sleep(3)
                                    else:
                                        write_log(f"⚠️ 重启失败，返回码: {restart_result.returncode}")
                                        if restart_result.stderr:
                                            write_log(f"错误信息: {restart_result.stderr}")
                                        if restart_result.stdout:
                                            write_log(f"输出信息: {restart_result.stdout}")
                                else:
                                    write_log(f"UCI commit 失败: {commit_result.stderr}")
                            else:
                                write_log(f"UCI set 失败: {uci_result.stderr}")
                                write_log("尝试直接修改配置文件...")
                                
                                # 方法2: 直接修改 /etc/config/openclash 文件
                                oc_config_file = "/etc/config/openclash"
                                if os.path.exists(oc_config_file):
                                    try:
                                        with open(oc_config_file, "r", encoding="utf-8") as f:
                                            content = f.read()
                                        
                                        # 查找并替换 config_path
                                        import re
                                        pattern = r"option config_path ['\"]([^'\"]+)['\"]"
                                        if re.search(pattern, content):
                                            new_content = re.sub(pattern, f"option config_path '{CONFIG_PATH}'", content)
                                            with open(oc_config_file, "w", encoding="utf-8") as f:
                                                f.write(new_content)
                                            write_log(f"✓ 已修改 OpenClash 配置文件: {CONFIG_PATH}")
                                            
                                            # 重启 OpenClash
                                            restart_result = subprocess.run(
                                                ["/etc/init.d/openclash", "restart"],
                                                capture_output=True,
                                                timeout=30,
                                                text=True
                                            )
                                            if restart_result.returncode == 0:
                                                write_log("✓ OpenClash 已重启")
                                                time.sleep(3)
                                            else:
                                                write_log(f"⚠️ 重启失败，返回码: {restart_result.returncode}")
                                        else:
                                            write_log("未找到 config_path 配置项")
                                            # 如果找不到配置项，尝试直接重启，让 watchdog 检测文件变化
                                            write_log("尝试直接重启 OpenClash，让 watchdog 检测文件变化...")
                                            restart_result = subprocess.run(
                                                ["/etc/init.d/openclash", "restart"],
                                                capture_output=True,
                                                timeout=30,
                                                text=True
                                            )
                                            if restart_result.returncode == 0:
                                                write_log("✓ OpenClash 已重启")
                                                time.sleep(3)
                                    except Exception as e:
                                        write_log(f"修改配置文件失败: {e}")
                        except Exception as e:
                            write_log(f"切换配置文件失败: {e}")
                            # 如果切换失败，尝试直接重启，让 watchdog 检测文件变化
                            write_log("尝试直接重启 OpenClash，让 watchdog 检测文件变化...")
                            try:
                                restart_result = subprocess.run(
                                    ["/etc/init.d/openclash", "restart"],
                                    capture_output=True,
                                    timeout=30,
                                    text=True
                                )
                                if restart_result.returncode == 0:
                                    write_log("✓ OpenClash 已重启")
                                    time.sleep(3)
                            except Exception as e2:
                                write_log(f"重启 OpenClash 失败: {e2}")
                    else:
                        write_log("OpenClash 未运行，配置文件已切换")
                        write_log("提示：启动 OpenClash 时会使用新配置文件")
                            
                except Exception as e:
                    write_log(f"检查 OpenClash 状态时出错: {e}")
                    # 如果检查失败，尝试直接重启
                    write_log("尝试直接重启 OpenClash...")
                    try:
                        restart_result = subprocess.run(
                            ["/etc/init.d/openclash", "restart"],
                            capture_output=True,
                            timeout=30,
                            text=True
                        )
                        if restart_result.returncode == 0:
                            write_log("✓ OpenClash 已重启")
                            time.sleep(3)
                    except Exception as e2:
                        write_log(f"重启 OpenClash 失败: {e2}")
                
                # 9. 最终验证：检查切换后的文件
                time.sleep(1)  # 等待文件系统同步
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    final_data = yaml_safe_load(f)
                    if clash_nodes:
                        test_node_name = clash_nodes[0].get("name", "").strip()
                        final_proxy_names = [p.get("name", "").strip() for p in final_data.get("proxies", [])]
                        if test_node_name in final_proxy_names:
                            # 检查策略组（考虑名称可能有空格）
                            final_groups = 0
                            for g in final_data.get("proxy-groups", []):
                                if isinstance(g, dict):
                                    group_proxies = [p.strip() if isinstance(p, str) else str(p).strip() for p in g.get("proxies", [])]
                                    if test_node_name in group_proxies:
                                        final_groups += 1
                            write_log(f"最终确认：节点 '{test_node_name}' 已在 {final_groups} 个策略组中")
                        else:
                            write_log(f"警告：切换后检查发现节点 '{test_node_name}' 不在配置文件中")
                
                # 返回详细结果
                self._send_json(200, {
                    "ok": True,
                    "injected": injected,
                    "skipped_invalid": skipped_invalid,
                    "skipped_duplicate": skipped_duplicate,
                    "parse_errors": parse_errors
                })
            else:
                self._send_json(400, {
                    "ok": False,
                    "error": "no valid nodes to add",
                    "parse_errors": parse_errors,
                })
                
        except Exception as e:
            # 验证失败：删除本次备份文件，保留之前的备份
            if backup_path and os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                    write_log(f"验证失败，已删除本次备份文件: {os.path.basename(backup_path)}")
                except:
                    pass
            
            # 原文件保持不变
            write_log(f"错误: {e}")
            write_log("配置未切换，原文件保持不变")
            self._send_json(500, {"ok": False, "error": str(e)})
    
    def _handle_delete_nodes(self):
        """处理删除节点请求"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            payload = json.loads(body)
        except Exception as e:
            self._send_json(400, {"ok": False, "error": f"invalid json: {e}"})
            return
        
        node_names = payload.get("node_names", [])
        if not node_names:
            self._send_json(400, {"ok": False, "error": "node_names must be provided"})
            return
        
        backup_path = None
        try:
            # ========== 方案：在备份文件上操作，验证通过后再切换 ==========
            # 1. 备份当前配置文件（备份到 config 目录下）
            backup_path = backup_config()
            write_log(f"已备份配置文件到: {backup_path}")
            
            # 2. 在备份文件上操作
            with open(backup_path, "r", encoding="utf-8") as f:
                data = yaml_safe_load(f)
            if data is None:
                data = {}
            
            # 3. 删除节点
            deleted_count = 0
            not_found = []
            
            # 从 proxies 列表中删除
            if "proxies" in data and isinstance(data["proxies"], list):
                original_count = len(data["proxies"])
                data["proxies"] = [p for p in data["proxies"] 
                                  if p.get("name", "").strip() not in [n.strip() for n in node_names]]
                deleted_count = original_count - len(data["proxies"])
                
                # 检查哪些节点未找到
                found_names = {p.get("name", "").strip() for p in data["proxies"]}
                for name in node_names:
                    if name.strip() not in found_names:
                        not_found.append(name.strip())
            
            # 从所有策略组中删除节点
            groups_updated = 0
            if "proxy-groups" in data and isinstance(data["proxy-groups"], list):
                node_name_set = {n.strip() for n in node_names}
                for group in data["proxy-groups"]:
                    if isinstance(group, dict) and "proxies" in group:
                        original_proxies = group["proxies"]
                        # 清理策略组中已有节点名称的空格
                        group_proxies_cleaned = [p.strip() if isinstance(p, str) else str(p).strip() for p in original_proxies]
                        # 删除指定的节点
                        group["proxies"] = [p for p in group_proxies_cleaned if p not in node_name_set]
                        if len(group["proxies"]) != len(group_proxies_cleaned):
                            groups_updated += 1
            
            write_log(f"已删除 {deleted_count} 个节点，更新了 {groups_updated} 个策略组")
            
            if deleted_count == 0:
                raise RuntimeError(f"未找到要删除的节点: {node_names}")
            
            # 4. 保存到备份文件
            with open(backup_path, "w", encoding="utf-8") as f:
                if USE_RUAMEL:
                    yaml_loader.dump(data, f)
                else:
                    import yaml
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                f.flush()
                try:
                    if hasattr(f, 'fileno'):
                        os.fsync(f.fileno())
                except:
                    pass
            
            write_log("备份文件已保存（已删除节点）")
            
            # 5. 验证备份文件
            write_log("验证备份文件...")
            if not verify_config(backup_path):
                raise RuntimeError("备份文件验证失败，YAML 格式可能有问题")
            
            # 6. 原子性切换并重启
            write_log("验证通过，开始切换配置文件...")
            promote_backup_to_live_and_restart(backup_path)
            backup_path = None
            
            # 返回详细结果
            self._send_json(200, {
                "ok": True,
                "deleted": deleted_count,
                "not_found": not_found,
                "groups_updated": groups_updated
            })
            
        except Exception as e:
            # 验证失败：删除本次备份文件，保留之前的备份
            if backup_path and os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                    write_log(f"验证失败，已删除本次备份文件: {os.path.basename(backup_path)}")
                except:
                    pass
            
            # 原文件保持不变
            write_log(f"错误: {e}")
            write_log("配置未切换，原文件保持不变")
            self._send_json(500, {"ok": False, "error": str(e)})
    
    def _handle_add_chain(self):
        """链式代理：relay 组 + 可选 dialer-proxy（Meta）"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(body)
        except Exception as e:
            self._send_json(400, {"ok": False, "error": f"invalid json: {e}"})
            return

        transit_name = payload.get("transit_name") or payload.get("transit")
        exit_name = payload.get("exit_name") or payload.get("exit")
        mode = payload.get("mode", "both")
        raw_cgn = payload.get("chain_group_name")
        if raw_cgn is not None and str(raw_cgn).strip():
            chain_group_name = str(raw_cgn).strip()
        else:
            chain_group_name = None

        if not transit_name or not exit_name:
            self._send_json(400, {"ok": False, "error": "transit_name and exit_name are required"})
            return

        backup_path = None
        try:
            backup_path = backup_config()
            write_log(f"链式代理: 已备份到 {backup_path}")

            with open(backup_path, "r", encoding="utf-8") as f:
                data = yaml_safe_load(f)
            if data is None:
                data = {}

            result = apply_chain_proxy(
                data,
                str(transit_name).strip(),
                str(exit_name).strip(),
                str(mode),
                chain_group_name,
            )

            with open(backup_path, "w", encoding="utf-8") as f:
                if USE_RUAMEL:
                    yaml_loader.dump(data, f)
                else:
                    import yaml
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                f.flush()
                try:
                    if hasattr(f, "fileno"):
                        os.fsync(f.fileno())
                except Exception:
                    pass

            write_log("链式代理: 备份文件已写入")
            if not verify_config(backup_path):
                raise RuntimeError("备份文件验证失败")

            write_log("链式代理: 验证通过，切换配置...")
            promote_backup_to_live_and_restart(backup_path)
            backup_path = None

            self._send_json(
                200,
                {
                    "ok": True,
                    "applied_mode": result["applied_mode"],
                    "relay_group_name": result["relay_group_name"],
                    "dialer_applied": result["dialer_applied"],
                    "warnings": result["warnings"],
                },
            )
        except Exception as e:
            if backup_path and os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                    write_log(f"链式代理失败，已删除备份: {os.path.basename(backup_path)}")
                except Exception:
                    pass
            write_log(f"链式代理错误: {e}")
            self._send_json(500, {"ok": False, "error": str(e)})
    
    def log_message(self, format, *args):
        # 减少日志输出
        return

# ========== 主函数 ==========
def _listen_port() -> int:
    """监听端口：优先环境变量 OPENCLASH_NODE_SERVER_PORT"""
    raw = os.environ.get("OPENCLASH_NODE_SERVER_PORT", "").strip()
    if not raw:
        return PORT
    try:
        p = int(raw)
        if 1 <= p <= 65535:
            return p
    except ValueError:
        pass
    write_log(f"无效 OPENCLASH_NODE_SERVER_PORT={raw!r}，使用默认 {PORT}")
    return PORT


def run():
    """启动 HTTP 服务"""
    global CONFIG_PATH
    
    # 重新检测配置文件路径（使用日志）
    CONFIG_PATH = find_active_config_path(use_log=True)
    port = _listen_port()
    
    write_log(f"OpenClash node server 将监听 {HOST}:{port}")
    if port != PORT:
        write_log(f"(默认端口为 {PORT}，当前由环境变量 OPENCLASH_NODE_SERVER_PORT 指定)")
    write_log(f"配置文件路径: {CONFIG_PATH}")
    write_log(f"Dedup strategy: {DEDUP_STRATEGY}, Allow Chinese names: {ALLOW_CHINESE_NAMES}")
    
    # 检查配置文件
    if os.path.exists(CONFIG_PATH):
        size = os.path.getsize(CONFIG_PATH)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(CONFIG_PATH))
        write_log(f"配置文件大小: {size} 字节")
        write_log(f"配置文件最后修改: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        write_log(f"警告：配置文件不存在: {CONFIG_PATH}")
    
    try:
        server = ReuseHTTPServer((HOST, port), Handler)
    except OSError as e:
        if getattr(e, "errno", None) == 98 or "Address already in use" in str(e):
            write_log(
                f"错误: 端口 {port} 已被占用 (Errno 98)。同一台路由器上只能有一个实例监听该端口。"
            )
            write_log(
                "排查: netstat -lntp 2>/dev/null | grep " + str(port) + "   （无 netstat 可 opkg install net-tools）"
            )
            write_log(
                "若已由 procd/init 自动启动本脚本，请先停止该服务再手动运行，或直接沿用自动启动的那一个进程，不要重复启动。"
            )
            write_log(
                "临时换端口: OPENCLASH_NODE_SERVER_PORT=8002 python3 " + sys.argv[0]
            )
            sys.exit(1)
        raise
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        write_log("服务已停止")
        server.shutdown()

if __name__ == "__main__":
    run()

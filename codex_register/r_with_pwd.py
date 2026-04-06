"""
OpenAI 账号自动注册（密码注册 + OAuth 换 token）。

流程概要：Worker 临时邮箱 → OAuth 授权链 → 注册表单与密码 → 邮箱 OTP（若需要）
→ 创建账户；若进入手机号页或无 workspace，则另起独立 Session 用邮箱密码登录完成 OAuth。

依赖环境变量（可由 gui 写入进程环境）：MAIL_SERVICE_PROVIDER、WORKER_DOMAIN、
FREEMAIL_USERNAME、FREEMAIL_PASSWORD、GRAPH_*、GMAIL_*；
可选 TOKEN_OUTPUT_DIR、OPENAI_SSL_VERIFY、SKIP_NET_CHECK、MAILFREE_RANDOM_DOMAIN。
可选 MAILBOX_PREFIX、MAILBOX_RANDOM_LENGTH（控制邮箱本地名前缀与随机长度）。
可选 REGISTER_RANDOM_FINGERPRINT（1=随机指纹，0=固定）。
可选 MAIL_ALLOWED_DOMAINS（JSON 数组或逗号分隔域名）。
支持 --proxy 与命令行循环参数。
"""

import argparse
import base64
import hashlib
import json
import os
import random
import re
import secrets
import ssl
import string
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from curl_cffi import requests
from .mail_services import MailServiceError, build_mail_service, normalize_mail_provider


def _out(msg: str, end: str = "\n", flush: bool = False) -> None:
    """输出到 stdout，供 GUI 通过 StdoutCapture 收集。"""
    print(msg, end=end, flush=flush)


def _info(msg: str) -> None:
    _out(f"[*] {msg}")


def _warn(msg: str) -> None:
    _out(f"[Warn] {msg}")


def _err(msg: str) -> None:
    _out(f"[Error] {msg}")


_LOG_ONCE_LOCK = threading.Lock()
_LOG_ONCE_KEYS: set[str] = set()


def _log_once_mark(key: str) -> bool:
    k = str(key or "").strip()
    if not k:
        return True
    with _LOG_ONCE_LOCK:
        if k in _LOG_ONCE_KEYS:
            return False
        _LOG_ONCE_KEYS.add(k)
        return True


def _info_once(key: str, msg: str) -> None:
    if _log_once_mark(key):
        _info(msg)


def _warn_once(key: str, msg: str) -> None:
    if _log_once_mark(key):
        _warn(msg)


def _load_dotenv(path: str = ".env") -> None:
    """从 .env 加载键值到 os.environ（不覆盖已有环境变量）。"""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                os.environ[key] = value
    except Exception:
        pass


_load_dotenv()

# --- 邮箱服务与输出目录（可由 .env 或 GUI 注入）---
WORKER_DOMAIN = os.getenv("WORKER_DOMAIN", "").strip()
if WORKER_DOMAIN and not WORKER_DOMAIN.startswith("http"):
    WORKER_DOMAIN = f"https://{WORKER_DOMAIN}"
WORKER_DOMAIN = WORKER_DOMAIN.rstrip("/")
FREEMAIL_USERNAME = os.getenv("FREEMAIL_USERNAME", "").strip()
FREEMAIL_PASSWORD = os.getenv("FREEMAIL_PASSWORD", "").strip()
MAIL_SERVICE_PROVIDER = normalize_mail_provider(os.getenv("MAIL_SERVICE_PROVIDER", "mailfree"))
MAIL_ALLOWED_DOMAINS: List[str] = []
TOKEN_OUTPUT_DIR = os.getenv("TOKEN_OUTPUT_DIR", "").strip()

_mail_service_client: Any = None
_mail_service_sig: tuple[Any, ...] | None = None
STOP_EVENT: Any = None


class UserStoppedError(RuntimeError):
    """用户在 GUI 中点击停止时触发的中断异常。"""


class HeroSmsBalanceLowError(RuntimeError):
    """HeroSMS 余额低于阈值时触发的中断异常。"""


class HeroSmsCodeTimeoutError(RuntimeError):
    """HeroSMS 长时间未收到验证码时触发的中断异常。"""


class HeroSmsCountryBlockedError(RuntimeError):
    """HeroSMS 国家被策略过滤时触发的中断异常。"""


class RegionBlockedError(RuntimeError):
    """OpenAI 返回地区不可用时触发的中断异常。"""


def _stop_requested() -> bool:
    evt = STOP_EVENT
    if evt is None:
        return False
    try:
        return bool(evt.is_set())
    except Exception:
        return False


def _sleep_interruptible(seconds: float) -> bool:
    wait_sec = max(0.0, float(seconds or 0.0))
    if wait_sec <= 0:
        return _stop_requested()
    evt = STOP_EVENT
    if evt is not None:
        try:
            return bool(evt.wait(wait_sec))
        except Exception:
            pass
    time.sleep(wait_sec)
    return _stop_requested()


def _raise_if_stopped() -> None:
    if _stop_requested():
        raise UserStoppedError("stopped_by_user")


def _ssl_verify() -> bool:
    """是否校验 HTTPS 证书；OPENAI_SSL_VERIFY=0 时关闭（仅建议调试）。"""
    flag = os.getenv("OPENAI_SSL_VERIFY", "1").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def _skip_net_check() -> bool:
    """为真时跳过 Cloudflare trace 地区检测。"""
    flag = os.getenv("SKIP_NET_CHECK", "0").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        val = int(raw)
    except Exception:
        return default
    return max(lo, min(hi, val))


def _env_float(name: str, default: float, lo: float, hi: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        val = float(raw)
    except Exception:
        return default
    return max(lo, min(hi, val))


def _env_list(name: str) -> List[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, list):
        out = [str(x).strip() for x in parsed if str(x).strip()]
        return list(dict.fromkeys(out))
    out = [x.strip() for x in raw.split(",") if x.strip()]
    return list(dict.fromkeys(out))


MAIL_ALLOWED_DOMAINS = _env_list("MAIL_ALLOWED_DOMAINS")
_GRAPH_BAD_EMAILS: set[str] = set()
_MAILBOX_INIT_LAST_ERROR_CODE = ""
_MAILBOX_INIT_LAST_ERROR_MSG = ""


def _set_mailbox_init_error(code: str = "", message: str = "") -> None:
    global _MAILBOX_INIT_LAST_ERROR_CODE, _MAILBOX_INIT_LAST_ERROR_MSG
    _MAILBOX_INIT_LAST_ERROR_CODE = str(code or "").strip().lower()
    _MAILBOX_INIT_LAST_ERROR_MSG = str(message or "").strip()


def _consume_mailbox_init_error() -> tuple[str, str]:
    global _MAILBOX_INIT_LAST_ERROR_CODE, _MAILBOX_INIT_LAST_ERROR_MSG
    code = _MAILBOX_INIT_LAST_ERROR_CODE
    msg = _MAILBOX_INIT_LAST_ERROR_MSG
    _MAILBOX_INIT_LAST_ERROR_CODE = ""
    _MAILBOX_INIT_LAST_ERROR_MSG = ""
    return code, msg


def _graph_password_for_email(email: str) -> str:
    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        return ""
    path = str(os.getenv("GRAPH_ACCOUNTS_FILE", "") or "").strip() or "graph_accounts.txt"
    fp = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(fp):
        return ""
    try:
        with open(fp, "r", encoding="utf-8") as f:
            for raw in f:
                line = str(raw or "").strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("----", 3)
                if len(parts) < 2:
                    continue
                em = str(parts[0] or "").strip().lower()
                pwd = str(parts[1] or "").strip()
                if em == target:
                    return pwd
    except Exception:
        return ""
    return ""


def _mark_graph_bad_email(email: str, reason: str = "") -> None:
    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        return
    _GRAPH_BAD_EMAILS.add(target)
    removed = False
    try:
        client = _get_mail_service_client()
        remove_fn = getattr(client, "remove_account", None)
        if callable(remove_fn):
            removed = bool(remove_fn(target))
    except Exception:
        removed = False
    if reason:
        if removed:
            _warn(f"Graph 账号已删除: {target} ({reason})")
        else:
            _warn(f"Graph 账号已标记不可用: {target} ({reason})")
    else:
        if removed:
            _warn(f"Graph 账号已删除: {target}")
        else:
            _warn(f"Graph 账号已标记不可用: {target}")


def _mark_graph_registered_email(
    email: str,
    *,
    proxies: Any = None,
    remark: str = "已注册",
) -> bool:
    provider_now = normalize_mail_provider(
        os.getenv("MAIL_SERVICE_PROVIDER", MAIL_SERVICE_PROVIDER)
    )
    if provider_now != "graph":
        return False
    graph_mode = str(os.getenv("GRAPH_ACCOUNTS_MODE", "file") or "file").strip().lower()
    if graph_mode != "api":
        return False

    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        return False
    try:
        client = _get_mail_service_client()
        mark_fn = getattr(client, "mark_account_registered", None)
        if not callable(mark_fn):
            return False
        ok = bool(mark_fn(target, remark=remark, proxies=proxies))
        if ok:
            _info(f"Graph 账号备注已更新: {target} -> {remark}")
        return ok
    except Exception as e:
        _warn(f"Graph 账号备注更新失败: {target} -> {e}")
        return False


_HERO_SMS_SERVICE_CACHE: str = ""
_HERO_SMS_COUNTRY_CACHE: dict[str, int] = {}
_HERO_SMS_VERIFY_LOCK = threading.Lock()
_HERO_SMS_STATS_LOCK = threading.Lock()
_HERO_SMS_RUNTIME: dict[str, float] = {
    "spent_total_usd": 0.0,
    "balance_last_usd": -1.0,
    "balance_start_usd": -1.0,
    "updated_at": 0.0,
}
_HERO_SMS_REUSE_LOCK = threading.Lock()
_HERO_SMS_REUSE_STATE: dict[str, Any] = {
    "activation_id": "",
    "phone": "",
    "service": "",
    "country": -1,
    "uses": 0,
    "updated_at": 0.0,
}
_HERO_SMS_COUNTRY_LOCK = threading.Lock()
_HERO_SMS_COUNTRY_TIMEOUTS: dict[int, int] = {}
_HERO_SMS_COUNTRY_COOLDOWN_UNTIL: dict[int, float] = {}
_HERO_SMS_COUNTRY_METRICS: dict[int, dict[str, float]] = {}
_HERO_SMS_PRICE_CACHE_LOCK = threading.Lock()
_HERO_SMS_PRICE_CACHE: dict[str, Any] = {
    "service": "",
    "updated_at": 0.0,
    "items": [],
}

_OPENAI_SMS_BLOCKED_COUNTRY_IDS = {
    0,    # Russia
    3,    # China
    14,   # Hong Kong
    20,   # Macao
    51,   # Belarus
    57,   # Iran
    110,  # Syria
    113,  # Cuba
    191,  # North Korea
}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _hero_sms_min_balance_limit() -> float:
    raw_min = str(os.getenv("HERO_SMS_MIN_BALANCE", "") or "").strip()
    if raw_min:
        return _env_float("HERO_SMS_MIN_BALANCE", 2.0, 0.0, 100000.0)
    return _env_float("HERO_SMS_MAX_PRICE", 2.0, 0.0, 100000.0)


def _hero_sms_reuse_enabled() -> bool:
    return _env_bool("HERO_SMS_REUSE_PHONE", False)


def _hero_sms_reuse_ttl_sec() -> int:
    return _env_int("HERO_SMS_REUSE_TTL_SEC", 1200, 60, 86400)


def _hero_sms_reuse_max_uses() -> int:
    return _env_int("HERO_SMS_REUSE_MAX_USES", 2, 1, 100)


def _hero_sms_country_timeout_limit() -> int:
    return _env_int("HERO_SMS_COUNTRY_TIMEOUT_LIMIT", 2, 1, 20)


def _hero_sms_country_cooldown_sec() -> int:
    return _env_int("HERO_SMS_COUNTRY_COOLDOWN_SEC", 900, 60, 86400)


def _hero_sms_price_cache_ttl_sec() -> int:
    return _env_int("HERO_SMS_PRICE_CACHE_TTL_SEC", 90, 10, 1800)


def _hero_sms_reuse_get(service: str, country: int) -> tuple[str, str, int]:
    now = time.time()
    ttl = _hero_sms_reuse_ttl_sec()
    max_uses = _hero_sms_reuse_max_uses()
    svc = str(service or "").strip()
    ctry = int(country)
    with _HERO_SMS_REUSE_LOCK:
        aid = str(_HERO_SMS_REUSE_STATE.get("activation_id") or "").strip()
        phone = str(_HERO_SMS_REUSE_STATE.get("phone") or "").strip()
        state_svc = str(_HERO_SMS_REUSE_STATE.get("service") or "").strip()
        try:
            state_country = int(_HERO_SMS_REUSE_STATE.get("country") or -1)
        except Exception:
            state_country = -1
        uses = int(_HERO_SMS_REUSE_STATE.get("uses") or 0)
        updated = float(_HERO_SMS_REUSE_STATE.get("updated_at") or 0.0)

        valid = bool(aid and phone)
        valid = valid and (state_svc == svc)
        valid = valid and (state_country == ctry)
        valid = valid and (uses < max_uses)
        valid = valid and (updated > 0 and (now - updated) <= ttl)
        if not valid:
            return "", "", 0
        return aid, phone, uses


def _hero_sms_reuse_set(activation_id: str, phone: str, service: str, country: int) -> None:
    aid = str(activation_id or "").strip()
    ph = str(phone or "").strip()
    if not aid or not ph:
        return
    with _HERO_SMS_REUSE_LOCK:
        _HERO_SMS_REUSE_STATE["activation_id"] = aid
        _HERO_SMS_REUSE_STATE["phone"] = ph
        _HERO_SMS_REUSE_STATE["service"] = str(service or "").strip()
        _HERO_SMS_REUSE_STATE["country"] = int(country)
        _HERO_SMS_REUSE_STATE["uses"] = 0
        _HERO_SMS_REUSE_STATE["updated_at"] = time.time()


def _hero_sms_reuse_touch(increase: bool = False) -> None:
    with _HERO_SMS_REUSE_LOCK:
        if increase:
            _HERO_SMS_REUSE_STATE["uses"] = int(_HERO_SMS_REUSE_STATE.get("uses") or 0) + 1
        _HERO_SMS_REUSE_STATE["updated_at"] = time.time()


def _hero_sms_reuse_clear() -> None:
    with _HERO_SMS_REUSE_LOCK:
        _HERO_SMS_REUSE_STATE["activation_id"] = ""
        _HERO_SMS_REUSE_STATE["phone"] = ""
        _HERO_SMS_REUSE_STATE["service"] = ""
        _HERO_SMS_REUSE_STATE["country"] = -1
        _HERO_SMS_REUSE_STATE["uses"] = 0
        _HERO_SMS_REUSE_STATE["updated_at"] = 0.0


def _hero_sms_country_is_on_cooldown(country_id: int) -> bool:
    cid = int(country_id)
    now = time.time()
    with _HERO_SMS_COUNTRY_LOCK:
        until = float(_HERO_SMS_COUNTRY_COOLDOWN_UNTIL.get(cid) or 0.0)
        if until <= 0:
            return False
        if until <= now:
            _HERO_SMS_COUNTRY_COOLDOWN_UNTIL.pop(cid, None)
            _HERO_SMS_COUNTRY_TIMEOUTS.pop(cid, None)
            return False
        return True


def _hero_sms_country_mark_success(country_id: int) -> None:
    cid = int(country_id)
    with _HERO_SMS_COUNTRY_LOCK:
        _HERO_SMS_COUNTRY_TIMEOUTS.pop(cid, None)


def _hero_sms_country_mark_timeout(country_id: int) -> bool:
    cid = int(country_id)
    limit = _hero_sms_country_timeout_limit()
    cooldown_sec = _hero_sms_country_cooldown_sec()
    now = time.time()
    with _HERO_SMS_COUNTRY_LOCK:
        current = int(_HERO_SMS_COUNTRY_TIMEOUTS.get(cid) or 0) + 1
        _HERO_SMS_COUNTRY_TIMEOUTS[cid] = current
        if current < limit:
            return False
        _HERO_SMS_COUNTRY_TIMEOUTS[cid] = 0
        _HERO_SMS_COUNTRY_COOLDOWN_UNTIL[cid] = now + float(cooldown_sec)
        return True


def _hero_sms_country_record_result(country_id: int, success: bool, reason: str = "") -> None:
    cid = int(country_id)
    now = time.time()
    low = str(reason or "").strip().lower()
    with _HERO_SMS_COUNTRY_LOCK:
        row = _HERO_SMS_COUNTRY_METRICS.get(cid)
        if not isinstance(row, dict):
            row = {
                "attempts": 0.0,
                "success": 0.0,
                "timeout": 0.0,
                "send_fail": 0.0,
                "verify_fail": 0.0,
                "other_fail": 0.0,
                "last_used_at": 0.0,
                "last_success_at": 0.0,
            }
            _HERO_SMS_COUNTRY_METRICS[cid] = row

        row["attempts"] = float(row.get("attempts") or 0.0) + 1.0
        row["last_used_at"] = now

        if success:
            row["success"] = float(row.get("success") or 0.0) + 1.0
            row["last_success_at"] = now
            return

        if "接码超时" in low or "status_wait_code" in low or "timeout" in low:
            row["timeout"] = float(row.get("timeout") or 0.0) + 1.0
        elif "发送手机验证码失败" in low:
            row["send_fail"] = float(row.get("send_fail") or 0.0) + 1.0
        elif "手机验证码校验失败" in low:
            row["verify_fail"] = float(row.get("verify_fail") or 0.0) + 1.0
        else:
            row["other_fail"] = float(row.get("other_fail") or 0.0) + 1.0


def _hero_sms_country_score(
    country_id: int,
    *,
    cost: float,
    count: int,
    preferred_country: int,
) -> float:
    cid = int(country_id)
    preferred = int(preferred_country)
    if cid in _OPENAI_SMS_BLOCKED_COUNTRY_IDS:
        return -1e9
    if count <= 0:
        return -1e9
    if _hero_sms_country_is_on_cooldown(cid):
        return -1e9

    now = time.time()
    with _HERO_SMS_COUNTRY_LOCK:
        stats = dict(_HERO_SMS_COUNTRY_METRICS.get(cid) or {})
        timeout_streak = int(_HERO_SMS_COUNTRY_TIMEOUTS.get(cid) or 0)

    attempts = max(0.0, float(stats.get("attempts") or 0.0))
    success_num = max(0.0, float(stats.get("success") or 0.0))
    timeout_num = max(0.0, float(stats.get("timeout") or 0.0))
    send_fail_num = max(0.0, float(stats.get("send_fail") or 0.0))
    verify_fail_num = max(0.0, float(stats.get("verify_fail") or 0.0))
    other_fail_num = max(0.0, float(stats.get("other_fail") or 0.0))
    last_success_at = float(stats.get("last_success_at") or 0.0)

    if attempts <= 0:
        success_rate = 0.55
        timeout_rate = 0.0
        send_fail_rate = 0.0
        verify_fail_rate = 0.0
        other_fail_rate = 0.0
        explore_bonus = 9.0
    else:
        success_rate = success_num / attempts
        timeout_rate = timeout_num / attempts
        send_fail_rate = send_fail_num / attempts
        verify_fail_rate = verify_fail_num / attempts
        other_fail_rate = other_fail_num / attempts
        explore_bonus = max(0.0, 6.0 - min(6.0, attempts))

    score = 0.0
    score += success_rate * 80.0
    score -= timeout_rate * 70.0
    score -= send_fail_rate * 45.0
    score -= verify_fail_rate * 30.0
    score -= other_fail_rate * 20.0
    score -= float(timeout_streak) * 8.0
    score += explore_bonus

    if cost >= 0:
        score -= min(5.0, float(cost)) * 10.0
    score += min(20000, max(0, int(count))) / 2000.0

    if cid == preferred:
        score += 3.0

    if last_success_at > 0:
        age = max(0.0, now - last_success_at)
        if age < 900:
            score += 4.0
        elif age < 3600:
            score += 2.0

    return float(score)


def _hero_sms_prices_by_service(service_code: str, proxies: Any) -> list[dict[str, Any]]:
    svc = str(service_code or "").strip()
    if not svc:
        return []
    ttl = _hero_sms_price_cache_ttl_sec()
    now = time.time()
    with _HERO_SMS_PRICE_CACHE_LOCK:
        cache_svc = str(_HERO_SMS_PRICE_CACHE.get("service") or "")
        cache_at = float(_HERO_SMS_PRICE_CACHE.get("updated_at") or 0.0)
        cache_items = list(_HERO_SMS_PRICE_CACHE.get("items") or [])
        if cache_svc == svc and cache_items and (now - cache_at) <= float(ttl):
            return [dict(x) for x in cache_items if isinstance(x, dict)]

    ok, text, data = _hero_sms_request(
        "getPrices",
        proxies=proxies,
        params={"service": svc},
        timeout=25,
    )
    if not ok or not isinstance(data, dict):
        if text:
            _warn(f"HeroSMS 拉取国家价格失败: {text}")
        return []

    rows: list[dict[str, Any]] = []
    for country_key, entry in data.items():
        try:
            cid = int(country_key)
        except Exception:
            continue
        if cid in _OPENAI_SMS_BLOCKED_COUNTRY_IDS:
            continue
        if not isinstance(entry, dict):
            continue

        row = entry.get(svc) if isinstance(entry.get(svc), dict) else entry
        if not isinstance(row, dict):
            continue
        try:
            count = int(row.get("count") or 0)
        except Exception:
            count = 0
        if count <= 0:
            continue
        try:
            cost = float(row.get("cost") or -1.0)
        except Exception:
            cost = -1.0
        rows.append(
            {
                "country": cid,
                "cost": cost,
                "count": count,
            }
        )

    rows.sort(
        key=lambda x: (
            float(x.get("cost")) if float(x.get("cost") or -1.0) >= 0 else 999999.0,
            -int(x.get("count") or 0),
            int(x.get("country") or 0),
        )
    )

    with _HERO_SMS_PRICE_CACHE_LOCK:
        _HERO_SMS_PRICE_CACHE["service"] = svc
        _HERO_SMS_PRICE_CACHE["updated_at"] = now
        _HERO_SMS_PRICE_CACHE["items"] = [dict(x) for x in rows]
    return rows


def _hero_sms_auto_pick_country() -> bool:
    """为 True 时按库存/价格/历史评分自动选国；False 时严格使用配置里的国家（解析后的 ID）。"""
    return _env_bool("HERO_SMS_AUTO_PICK_COUNTRY", False)


def _hero_sms_pick_country_id(
    proxies: Any,
    *,
    service_code: str,
    preferred_country: int,
) -> int:
    preferred = int(preferred_country)
    if not _hero_sms_auto_pick_country():
        if preferred in _OPENAI_SMS_BLOCKED_COUNTRY_IDS:
            _warn(
                f"HeroSMS 已关闭自动选国：首选国家 ID {preferred} 在 OpenAI 短信黑名单内，仍将尝试使用该 ID"
            )
            return preferred
        if _hero_sms_country_is_on_cooldown(preferred):
            _warn(
                "HeroSMS 已关闭自动选国：首选国家仍在失败冷却中，仍按配置使用 "
                f"{preferred}（可设 HERO_SMS_AUTO_PICK_COUNTRY=1 恢复自动选国）"
            )
        return preferred

    rows = _hero_sms_prices_by_service(service_code, proxies)
    if not rows:
        if preferred not in _OPENAI_SMS_BLOCKED_COUNTRY_IDS and not _hero_sms_country_is_on_cooldown(preferred):
            return preferred
        return preferred

    scored: list[tuple[float, int, float, int]] = []
    for row in rows:
        cid = int(row.get("country") or -1)
        if cid < 0:
            continue
        try:
            cost = float(row.get("cost") or -1.0)
        except Exception:
            cost = -1.0
        try:
            count = int(row.get("count") or 0)
        except Exception:
            count = 0
        score = _hero_sms_country_score(
            cid,
            cost=cost,
            count=count,
            preferred_country=preferred,
        )
        if score <= -1e8:
            continue
        scored.append((score, cid, cost, count))

    if not scored:
        if preferred not in _OPENAI_SMS_BLOCKED_COUNTRY_IDS and not _hero_sms_country_is_on_cooldown(preferred):
            return preferred
        return preferred

    scored.sort(key=lambda x: (-float(x[0]), float(x[2]) if float(x[2]) >= 0 else 999999.0, -int(x[3]), int(x[1])))
    top_score, top_country, top_cost, top_count = scored[0]

    if top_country != preferred:
        _info(
            "HeroSMS 国家评分选优: "
            f"{preferred} -> {top_country} (score={top_score:.2f}, cost={top_cost:.3f}, stock={top_count})"
        )
    return int(top_country)


def _hero_sms_update_runtime(
    *,
    spent_delta: float = 0.0,
    balance: float | None = None,
    init_start: bool = False,
) -> None:
    delta = max(0.0, float(spent_delta or 0.0))
    bal = None
    if balance is not None:
        try:
            bal = float(balance)
        except Exception:
            bal = None

    with _HERO_SMS_STATS_LOCK:
        if delta > 0:
            _HERO_SMS_RUNTIME["spent_total_usd"] = round(
                max(0.0, float(_HERO_SMS_RUNTIME.get("spent_total_usd") or 0.0)) + delta,
                4,
            )
        if bal is not None and bal >= 0:
            _HERO_SMS_RUNTIME["balance_last_usd"] = round(bal, 4)
            current_start = float(_HERO_SMS_RUNTIME.get("balance_start_usd") or -1.0)
            if init_start and current_start < 0:
                _HERO_SMS_RUNTIME["balance_start_usd"] = round(bal, 4)
        _HERO_SMS_RUNTIME["updated_at"] = time.time()


def reset_hero_sms_runtime_stats() -> None:
    with _HERO_SMS_STATS_LOCK:
        _HERO_SMS_RUNTIME["spent_total_usd"] = 0.0
        _HERO_SMS_RUNTIME["balance_last_usd"] = -1.0
        _HERO_SMS_RUNTIME["balance_start_usd"] = -1.0
        _HERO_SMS_RUNTIME["updated_at"] = time.time()
    _hero_sms_reuse_clear()
    with _HERO_SMS_COUNTRY_LOCK:
        _HERO_SMS_COUNTRY_TIMEOUTS.clear()
        _HERO_SMS_COUNTRY_COOLDOWN_UNTIL.clear()
    with _HERO_SMS_PRICE_CACHE_LOCK:
        _HERO_SMS_PRICE_CACHE["service"] = ""
        _HERO_SMS_PRICE_CACHE["updated_at"] = 0.0
        _HERO_SMS_PRICE_CACHE["items"] = []


def get_hero_sms_runtime_stats() -> dict[str, float]:
    with _HERO_SMS_STATS_LOCK:
        return {
            "spent_total_usd": round(
                max(0.0, float(_HERO_SMS_RUNTIME.get("spent_total_usd") or 0.0)),
                4,
            ),
            "balance_last_usd": round(
                float(_HERO_SMS_RUNTIME.get("balance_last_usd") or -1.0),
                4,
            ),
            "balance_start_usd": round(
                float(_HERO_SMS_RUNTIME.get("balance_start_usd") or -1.0),
                4,
            ),
            "updated_at": float(_HERO_SMS_RUNTIME.get("updated_at") or 0.0),
        }


def _hero_sms_api_key() -> str:
    return str(os.getenv("HERO_SMS_API_KEY", "") or "").strip()


def _hero_sms_enabled() -> bool:
    if not _env_bool("HERO_SMS_ENABLED", False):
        return False
    return bool(_hero_sms_api_key())


def _hero_sms_base_url() -> str:
    raw = str(
        os.getenv("HERO_SMS_BASE_URL", "https://hero-sms.com/stubs/handler_api.php")
        or "https://hero-sms.com/stubs/handler_api.php"
    ).strip()
    return raw or "https://hero-sms.com/stubs/handler_api.php"


def _hero_sms_request(
    action: str,
    *,
    proxies: Any,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 25,
) -> tuple[bool, str, Any]:
    key = _hero_sms_api_key()
    if not key:
        return False, "NO_KEY", None

    query: Dict[str, Any] = {
        "action": str(action or "").strip(),
        "api_key": key,
    }
    if isinstance(params, dict):
        for k, v in params.items():
            if v is None:
                continue
            sv = str(v).strip() if isinstance(v, str) else v
            if sv == "":
                continue
            query[str(k)] = sv

    try:
        resp = requests.get(
            _hero_sms_base_url(),
            params=query,
            proxies=proxies,
            verify=_ssl_verify(),
            timeout=timeout,
            impersonate="chrome131",
        )
    except Exception as e:
        return False, f"REQUEST_ERROR:{e}", None

    code = int(getattr(resp, "status_code", 0) or 0)
    text = str(getattr(resp, "text", "") or "").strip()
    try:
        data = resp.json()
    except Exception:
        data = None
    if not (200 <= code < 300):
        if text:
            return False, text, data
        return False, f"HTTP {code}", data
    return True, text, data


def hero_sms_get_balance(proxies: Any = None) -> tuple[float, str]:
    ok, text, data = _hero_sms_request("getBalance", proxies=proxies, timeout=20)
    if not ok:
        return -1.0, str(text or "getBalance failed")

    line = str(text or "").strip()
    if line.upper().startswith("ACCESS_BALANCE:"):
        raw = line.split(":", 1)[1].strip()
        try:
            value = float(raw)
            _hero_sms_update_runtime(balance=value, init_start=True)
            return value, ""
        except Exception:
            pass

    if isinstance(data, dict):
        candidates = [
            data.get("balance"),
            data.get("amount"),
            data.get("data"),
        ]
        for val in candidates:
            try:
                if isinstance(val, dict):
                    num = float(val.get("balance") or val.get("amount") or -1)
                else:
                    num = float(val)
            except Exception:
                continue
            if num >= 0:
                _hero_sms_update_runtime(balance=num, init_start=True)
                return num, ""

    return -1.0, line or "无法解析余额"


def _hero_sms_resolve_service_code(proxies: Any) -> str:
    global _HERO_SMS_SERVICE_CACHE

    raw = str(os.getenv("HERO_SMS_SERVICE", "") or "").strip()
    if raw and raw.lower() not in {"auto", "openai", "chatgpt", "gpt", "codex"}:
        return raw
    if _HERO_SMS_SERVICE_CACHE:
        return _HERO_SMS_SERVICE_CACHE

    ok, _, data = _hero_sms_request(
        "getServicesList",
        proxies=proxies,
        params={"lang": "en"},
        timeout=30,
    )
    services: List[Dict[str, Any]] = []
    if ok and isinstance(data, dict):
        if isinstance(data.get("services"), list):
            services = [x for x in data.get("services") if isinstance(x, dict)]
        elif isinstance(data.get("data"), list):
            services = [x for x in data.get("data") if isinstance(x, dict)]

    selected = ""
    for item in services:
        code = str(item.get("code") or item.get("id") or "").strip()
        name = str(item.get("name") or item.get("title") or item.get("eng") or "").strip()
        low = f"{code} {name}".lower()
        if "openai" in low:
            selected = code
            break
    if not selected:
        for item in services:
            code = str(item.get("code") or item.get("id") or "").strip()
            name = str(item.get("name") or item.get("title") or item.get("eng") or "").strip()
            low = f"{code} {name}".lower()
            if any(k in low for k in ("chatgpt", "codex", "gpt")):
                selected = code
                break

    if not selected:
        selected = "dr"

    _HERO_SMS_SERVICE_CACHE = selected
    _info(f"HeroSMS 服务代码: {selected}")
    return selected


def _hero_sms_resolve_country_id(proxies: Any) -> int:
    raw = str(os.getenv("HERO_SMS_COUNTRY", "US") or "US").strip()
    if not raw:
        raw = "US"
    if raw.isdigit():
        return max(0, int(raw))

    key = raw.upper()
    if key in _HERO_SMS_COUNTRY_CACHE:
        return int(_HERO_SMS_COUNTRY_CACHE[key])

    wanted_tokens = {
        key,
        key.replace(" ", ""),
    }
    if key in {"US", "USA", "UNITEDSTATES", "UNITED STATES", "AMERICA"}:
        wanted_tokens.update({"US", "USA", "UNITEDSTATES", "UNITED STATES"})

    ok, _, data = _hero_sms_request("getCountries", proxies=proxies, timeout=30)
    countries: List[Dict[str, Any]] = []
    if ok and isinstance(data, list):
        countries = [x for x in data if isinstance(x, dict)]

    matched = -1
    for item in countries:
        cid = item.get("id")
        try:
            cid_i = int(cid)
        except Exception:
            continue
        names = [
            str(item.get("eng") or "").strip().upper(),
            str(item.get("rus") or "").strip().upper(),
            str(item.get("chn") or "").strip().upper(),
            str(item.get("iso") or "").strip().upper(),
            str(item.get("iso2") or "").strip().upper(),
        ]
        compact = {x.replace(" ", "") for x in names if x}
        exact = {x for x in names if x}
        if wanted_tokens & exact or wanted_tokens & compact:
            matched = cid_i
            break

    if matched < 0 and key in {"US", "USA", "UNITEDSTATES", "UNITED STATES", "AMERICA"}:
        matched = 187
    if matched < 0:
        matched = 0

    _HERO_SMS_COUNTRY_CACHE[key] = matched
    _info(f"HeroSMS 国家ID: {matched} ({raw})")
    return matched


def _hero_sms_set_status(activation_id: str, status: int, proxies: Any) -> str:
    if not activation_id:
        return ""
    _, text, _ = _hero_sms_request(
        "setStatus",
        proxies=proxies,
        params={"id": activation_id, "status": int(status)},
        timeout=20,
    )
    return str(text or "")


def _hero_sms_mark_ready_enabled() -> bool:
    """与 hero-sms 官方 SDK 一致：取号后 setStatus(1) 表示就绪、开始接收短信。"""
    return _env_bool("HERO_SMS_MARK_READY", True)


def _hero_sms_order_max_price() -> float:
    """getNumber 可选参数 maxPrice（美元）；0 表示不传，由平台按默认价格取号。"""
    return _env_float("HERO_SMS_ORDER_MAX_PRICE", 0.0, 0.0, 500.0)


def _hero_sms_mark_ready(activation_id: str, proxies: Any) -> None:
    if not activation_id or not _hero_sms_mark_ready_enabled():
        return
    resp = _hero_sms_set_status(activation_id, 1, proxies)
    if resp:
        low = str(resp).strip().upper()
        if low.startswith("ACCESS_") or "OK" in low:
            _info(f"HeroSMS 标记就绪 setStatus(1): {resp}")
        else:
            _warn(f"HeroSMS setStatus(1) 返回异常（仍将尝试发码）: {resp}")
    else:
        _info("HeroSMS setStatus(1) 已调用（无文本响应）")


def _is_hero_sms_balance_issue(reason: str) -> bool:
    low = str(reason or "").strip().lower()
    if not low:
        return False
    return "no_balance" in low or "余额不足" in low


def _is_hero_sms_timeout_issue(reason: str) -> bool:
    low = str(reason or "").strip().lower()
    if not low:
        return False
    return "接码超时" in low or "status_wait_code" in low or "timeout" in low


def _is_hero_sms_country_blocked_issue(reason: str) -> bool:
    low = str(reason or "").strip().lower()
    if not low:
        return False
    return (
        "country_blocked" in low
        or "国家受限" in low
        or "unsupported_country_region_territory" in low
        or "country, region, or territory" in low
        or "not supported in your country" in low
    )


def _is_region_blocked_issue(reason: str) -> bool:
    low = str(reason or "").strip().lower()
    if not low:
        return False
    return (
        "unsupported_country_region_territory" in low
        or "country, region, or territory not supported" in low
        or "country, region, or territory" in low
        or "request_forbidden" in low
    )


def _hero_sms_get_number(
    proxies: Any,
    *,
    service_code: str = "",
    country_id: int | None = None,
) -> tuple[str, str, str]:
    svc = str(service_code or "").strip() or _hero_sms_resolve_service_code(proxies)
    ctry = int(country_id) if country_id is not None else _hero_sms_resolve_country_id(proxies)
    if int(ctry) in _OPENAI_SMS_BLOCKED_COUNTRY_IDS:
        return "", "", f"COUNTRY_BLOCKED: 国家ID {ctry} 不支持 OpenAI 注册"
    min_balance = _hero_sms_min_balance_limit()
    _info(f"HeroSMS 取号参数: service={svc}, country={ctry}")

    balance_now, balance_err = hero_sms_get_balance(proxies)
    if balance_now >= 0:
        _info(
            "HeroSMS 当前余额: "
            f"${balance_now:.2f}（下限 ${min_balance:.2f}）"
        )
        if balance_now < min_balance:
            return "", "", f"NO_BALANCE: 当前余额 ${balance_now:.2f} < 下限 ${min_balance:.2f}"
    elif balance_err:
        _warn(f"HeroSMS 余额查询失败: {balance_err}")

    params: Dict[str, Any] = {
        "service": svc,
        "country": ctry,
    }
    max_px = _hero_sms_order_max_price()
    if max_px > 0:
        params["maxPrice"] = max_px
        _info(f"HeroSMS getNumber maxPrice={max_px}")

    ok, text, data = _hero_sms_request("getNumber", proxies=proxies, params=params, timeout=30)
    if not ok:
        return "", "", str(text or "getNumber failed")

    line = str(text or "").strip()
    if line.upper().startswith("ACCESS_NUMBER:"):
        parts = line.split(":", 2)
        if len(parts) >= 3:
            activation_id = str(parts[1] or "").strip()
            phone_raw = str(parts[2] or "").strip()
            if activation_id and phone_raw:
                phone = phone_raw if phone_raw.startswith("+") else f"+{phone_raw}"
                return activation_id, phone, ""

    if isinstance(data, dict):
        activation_id = str(
            data.get("activationId")
            or data.get("activation_id")
            or data.get("id")
            or ""
        ).strip()
        phone_raw = str(
            data.get("phoneNumber")
            or data.get("phone")
            or data.get("number")
            or ""
        ).strip()
        if activation_id and phone_raw:
            phone = phone_raw if phone_raw.startswith("+") else f"+{phone_raw}"
            return activation_id, phone, ""

    return "", "", line or "NO_NUMBERS"


def _hero_sms_poll_code(activation_id: str, proxies: Any) -> str:
    if not activation_id:
        return ""
    timeout_sec = _env_int("HERO_SMS_POLL_TIMEOUT_SEC", 120, 20, 900)
    interval_sec = _env_float("HERO_SMS_POLL_INTERVAL_SEC", 3.0, 1.0, 30.0)
    progress_sec = _env_int("HERO_SMS_POLL_PROGRESS_SEC", 8, 3, 120)
    resend_after_sec = _env_int("HERO_SMS_RESEND_AFTER_SEC", 24, 0, 300)

    started_at = time.time()
    next_progress_at = float(progress_sec)
    resent_once = False
    last_status = ""

    _info(
        "HeroSMS 等待短信验证码: "
        f"activation_id={activation_id}, timeout={timeout_sec}s"
    )

    def _try_resend(reason: str) -> None:
        nonlocal resent_once
        if resent_once:
            return
        if resend_after_sec <= 0:
            return
        resend_resp = _hero_sms_set_status(activation_id, 3, proxies)
        resent_once = True
        if resend_resp:
            _info(f"HeroSMS 请求重发验证码({reason}): {resend_resp}")
        else:
            _info(f"HeroSMS 请求重发验证码({reason})")

    while time.time() - started_at < timeout_sec:
        _raise_if_stopped()
        ok, text, data = _hero_sms_request(
            "getStatus",
            proxies=proxies,
            params={"id": activation_id},
            timeout=20,
        )
        line = str(text or "").strip()
        upper = line.upper()

        status_tag = ""
        if upper:
            if ":" in upper:
                status_tag = upper.split(":", 1)[0].strip()
            else:
                status_tag = upper
        if not status_tag and isinstance(data, dict):
            status_tag = str(
                data.get("status")
                or data.get("title")
                or data.get("message")
                or ""
            ).strip().upper()
        if status_tag and status_tag != last_status:
            last_status = status_tag
            _info(f"HeroSMS 状态: {status_tag}")

        if ok and upper.startswith("STATUS_OK"):
            if ":" in line:
                code = line.split(":", 1)[1].strip()
            else:
                code = ""
            if not code and isinstance(data, dict):
                sms_obj = data.get("sms") if isinstance(data.get("sms"), dict) else {}
                code = str(sms_obj.get("code") or data.get("code") or "").strip()
            if code:
                return code

        if status_tag in {"STATUS_WAIT_RETRY", "STATUS_WAIT_RESEND"}:
            _try_resend(status_tag)

        if status_tag in {"STATUS_CANCEL", "NO_ACTIVATION", "BAD_STATUS"}:
            return ""
        if isinstance(data, dict):
            title = str(data.get("title") or "").strip().upper()
            if title in {"STATUS_CANCEL", "NO_ACTIVATION", "BAD_STATUS"}:
                return ""

        elapsed = time.time() - started_at
        if (not resent_once) and resend_after_sec > 0 and elapsed >= float(resend_after_sec):
            _try_resend("timeout")

        if elapsed >= next_progress_at:
            left = max(0, int(timeout_sec - elapsed))
            _info(f"HeroSMS 等码中... 已等待 {int(elapsed)}s，剩余约 {left}s")
            next_progress_at += float(progress_sec)

        if _sleep_interruptible(interval_sec):
            raise UserStoppedError("stopped_by_user")
    _warn(f"HeroSMS 等码超时: {timeout_sec}s")
    return ""


def _try_verify_phone_via_hero_sms(
    session: requests.Session,
    *,
    proxies: Any,
    hint_url: str = "",
) -> tuple[bool, str]:
    if not _hero_sms_enabled():
        if not _env_bool("HERO_SMS_ENABLED", False):
            return False, "HeroSMS 未启用"
        return False, "HeroSMS API Key 未配置"

    max_tries = _env_int("HERO_SMS_MAX_TRIES", 3, 1, 6)
    last_reason = "HeroSMS 手机验证失败"
    lock_acquired = False
    serial_on = _env_bool("HERO_SMS_SERIAL_VERIFY", True)
    wait_sec = _env_int("HERO_SMS_SERIAL_WAIT_SEC", 180, 10, 3600)
    verify_balance_start = -1.0

    if serial_on:
        _info("等待 HeroSMS 手机验证锁...")
        started = time.time()
        while True:
            _raise_if_stopped()
            if _HERO_SMS_VERIFY_LOCK.acquire(timeout=0.5):
                lock_acquired = True
                break
            if time.time() - started >= wait_sec:
                return False, "HeroSMS 手机验证排队超时"

    def _verify_once(
        activation_id: str,
        phone_number: str,
        *,
        source: str,
        close_on_success: bool,
        cancel_on_fail: bool,
    ) -> tuple[bool, str, str]:
        finished = False
        fail_reason = ""
        try:
            send_headers: Dict[str, str] = {
                "referer": "https://auth.openai.com/add-phone",
                "accept": "application/json",
                "content-type": "application/json",
            }
            send_sentinel = _build_sentinel_for_session(session, "authorize_continue", proxies)
            if send_sentinel:
                send_headers["openai-sentinel-token"] = send_sentinel

            _hero_sms_mark_ready(activation_id, proxies)

            send_resp = _post_with_retry(
                session,
                "https://auth.openai.com/api/accounts/add-phone/send",
                headers=send_headers,
                json_body={"phone_number": phone_number},
                proxies=proxies,
                timeout=30,
                retries=1,
            )
            _info(f"{source} add-phone/send HTTP {send_resp.status_code}")
            if send_resp.status_code == 200:
                try:
                    sj = send_resp.json()
                except Exception:
                    sj = None
                if isinstance(sj, dict):
                    err_code = str(sj.get("error_code") or "").strip()
                    err_msg = str(sj.get("message") or "").strip()
                    err_v = sj.get("error")
                    if isinstance(err_v, dict):
                        err_code = str(err_v.get("code") or err_code).strip()
                        err_msg = str(err_v.get("message") or err_msg).strip()
                    elif isinstance(err_v, str) and not err_code:
                        err_code = str(err_v).strip()

                    if sj.get("success") is False:
                        reason_text = str(err_msg or err_code or sj)[:280]
                        if _is_hero_sms_country_blocked_issue(f"{err_code} {err_msg}"):
                            fail_reason = (
                                f"COUNTRY_BLOCKED: {err_code or 'unsupported_country_region_territory'}"
                                f" {err_msg}".strip()
                            )
                        else:
                            fail_reason = f"发送手机验证码失败: {reason_text}"
                        _warn(
                            f"{source} add-phone/send 业务失败: "
                            f"{reason_text}"
                        )
                        return False, "", fail_reason

                    if err_v and sj.get("success") is not False:
                        reason_text = str(err_msg or err_code or err_v)[:280]
                        if _is_hero_sms_country_blocked_issue(f"{err_code} {err_msg}"):
                            fail_reason = (
                                f"COUNTRY_BLOCKED: {err_code or 'unsupported_country_region_territory'}"
                                f" {err_msg}".strip()
                            )
                        else:
                            fail_reason = f"发送手机验证码失败: {reason_text}"
                        _warn(f"{source} add-phone/send 返回含 error 字段: {reason_text}")
                        return False, "", fail_reason
            if send_resp.status_code != 200:
                fail_body = str(send_resp.text or "")
                if _is_hero_sms_country_blocked_issue(fail_body):
                    fail_reason = f"COUNTRY_BLOCKED: {fail_body[:240]}"
                else:
                    fail_reason = f"发送手机验证码失败: HTTP {send_resp.status_code}"
                _warn(f"{source} {fail_reason} | {fail_body[:240]}")
                return False, "", fail_reason

            sms_code = _hero_sms_poll_code(activation_id, proxies)
            if not sms_code:
                fail_reason = "接码超时，未收到手机验证码"
                _warn(f"{source} {fail_reason}")
                return False, "", fail_reason
            _info(f"{source} HeroSMS 收到手机验证码: {sms_code}")

            verify_headers: Dict[str, str] = {
                "referer": "https://auth.openai.com/phone-verification",
                "accept": "application/json",
                "content-type": "application/json",
            }
            verify_sentinel = _build_sentinel_for_session(session, "authorize_continue", proxies)
            if verify_sentinel:
                verify_headers["openai-sentinel-token"] = verify_sentinel

            verify_resp = _post_with_retry(
                session,
                "https://auth.openai.com/api/accounts/phone-otp/validate",
                headers=verify_headers,
                json_body={"code": sms_code},
                proxies=proxies,
                timeout=30,
                retries=1,
            )
            _info(f"{source} phone-otp/validate HTTP {verify_resp.status_code}")
            if verify_resp.status_code != 200:
                verify_body = str(verify_resp.text or "")
                if _is_hero_sms_country_blocked_issue(verify_body):
                    fail_reason = f"COUNTRY_BLOCKED: {verify_body[:240]}"
                else:
                    fail_reason = f"手机验证码校验失败: HTTP {verify_resp.status_code}"
                _warn(f"{source} {fail_reason} | {verify_body[:240]}")
                return False, "", fail_reason

            if close_on_success:
                _hero_sms_set_status(activation_id, 6, proxies)
            else:
                keep_resp = _hero_sms_set_status(activation_id, 3, proxies)
                if keep_resp:
                    _info(f"{source} 复用保持激活: {keep_resp}")
            finished = True

            try:
                vj = verify_resp.json() or {}
            except Exception:
                vj = {}
            next_url = _extract_next_url(vj).strip() or str(vj.get("continue_url") or "").strip()
            if next_url and not next_url.startswith("http"):
                next_url = (
                    f"https://auth.openai.com{next_url}"
                    if next_url.startswith("/")
                    else next_url
                )
            if next_url:
                try:
                    _, follow_url = _follow_redirect_chain(session, next_url, proxies)
                    if follow_url:
                        next_url = follow_url
                except UserStoppedError:
                    raise
                except Exception:
                    pass
            if not next_url:
                next_url = str(hint_url or "").strip()
            return True, next_url, ""
        except UserStoppedError:
            raise
        except Exception as e:
            fail_reason = f"手机验证异常: {e}"
            _warn(f"{source} {fail_reason}")
            return False, "", fail_reason
        finally:
            if (not finished) and cancel_on_fail:
                _hero_sms_set_status(activation_id, 8, proxies)

    try:
        verify_balance_start, _ = hero_sms_get_balance(proxies)
        if verify_balance_start >= 0:
            _hero_sms_update_runtime(balance=verify_balance_start, init_start=True)

        service_code = _hero_sms_resolve_service_code(proxies)
        preferred_country_id = _hero_sms_resolve_country_id(proxies)
        _info(
            "HeroSMS 国家策略: "
            f"超时阈值={_hero_sms_country_timeout_limit()}次, "
            f"冷却={_hero_sms_country_cooldown_sec()}s"
        )
        country_id = _hero_sms_pick_country_id(
            proxies,
            service_code=service_code,
            preferred_country=preferred_country_id,
        )
        if country_id != preferred_country_id:
            _warn(
                f"HeroSMS 国家自动切换: {preferred_country_id} -> {country_id}"
            )
        reuse_on = _hero_sms_reuse_enabled()

        if reuse_on:
            reuse_id, reuse_phone, reuse_used = _hero_sms_reuse_get(service_code, country_id)
            if reuse_id and reuse_phone:
                _info(
                    "HeroSMS 尝试复用手机号: "
                    f"activation_id={reuse_id}, phone={reuse_phone}, used={reuse_used}"
                )
                ok_reuse, next_reuse, reason_reuse = _verify_once(
                    reuse_id,
                    reuse_phone,
                    source="复用号码",
                    close_on_success=False,
                    cancel_on_fail=False,
                )
                if ok_reuse:
                    _hero_sms_country_mark_success(country_id)
                    _hero_sms_country_record_result(country_id, True, "reuse_success")
                    _hero_sms_reuse_touch(increase=True)
                    return True, next_reuse
                last_reason = reason_reuse or "复用手机号失败"
                _hero_sms_country_record_result(country_id, False, last_reason)
                if _is_hero_sms_timeout_issue(last_reason):
                    switched = _hero_sms_country_mark_timeout(country_id)
                    if switched:
                        _hero_sms_set_status(reuse_id, 8, proxies)
                        _hero_sms_reuse_clear()
                        next_country = _hero_sms_pick_country_id(
                            proxies,
                            service_code=service_code,
                            preferred_country=preferred_country_id,
                        )
                        if next_country != country_id:
                            _warn(
                                "当前国家接码超时达到阈值，自动切换国家: "
                                f"{country_id} -> {next_country}"
                            )
                            country_id = next_country
                        else:
                            _hero_sms_reuse_touch(increase=True)
                            _hero_sms_set_status(reuse_id, 3, proxies)
                            _warn(f"复用手机号未收到短信，保留号码待下次继续: {last_reason}")
                            return False, "接码超时，已保留复用号码"
                    else:
                        _hero_sms_reuse_touch(increase=True)
                        _hero_sms_set_status(reuse_id, 3, proxies)
                        _warn(f"复用手机号未收到短信，保留号码待下次继续: {last_reason}")
                        return False, "接码超时，已保留复用号码"
                _warn(f"复用手机号失败，改为新购号码: {last_reason}")
                _hero_sms_set_status(reuse_id, 8, proxies)
                _hero_sms_reuse_clear()

        for attempt in range(1, max_tries + 1):
            _raise_if_stopped()
            activation_id, phone_number, get_err = _hero_sms_get_number(
                proxies,
                service_code=service_code,
                country_id=country_id,
            )
            if not activation_id or not phone_number:
                last_reason = f"取号失败: {get_err or 'NO_NUMBERS'}"
                _warn(f"HeroSMS 第 {attempt}/{max_tries} 次取号失败: {get_err or 'NO_NUMBERS'}")
                if _is_hero_sms_balance_issue(get_err):
                    break
                if _is_hero_sms_country_blocked_issue(get_err):
                    break
                if _sleep_interruptible(1.2):
                    raise UserStoppedError("stopped_by_user")
                continue

            _info(
                "HeroSMS 取号成功: "
                f"第 {attempt}/{max_tries} 次, activation_id={activation_id}, phone={phone_number}"
            )
            ok_new, next_new, reason_new = _verify_once(
                activation_id,
                phone_number,
                source=f"新购号码#{attempt}",
                close_on_success=(not reuse_on),
                cancel_on_fail=(not reuse_on),
            )
            if ok_new:
                _hero_sms_country_mark_success(country_id)
                _hero_sms_country_record_result(country_id, True, "new_success")
                if reuse_on:
                    _hero_sms_reuse_set(activation_id, phone_number, service_code, country_id)
                    _hero_sms_reuse_touch(increase=True)
                return True, next_new
            last_reason = reason_new or "手机验证失败"
            _hero_sms_country_record_result(country_id, False, last_reason)
            if reuse_on and _is_hero_sms_timeout_issue(last_reason):
                switched = _hero_sms_country_mark_timeout(country_id)
                if switched:
                    _hero_sms_set_status(activation_id, 8, proxies)
                    _hero_sms_reuse_clear()
                    next_country = _hero_sms_pick_country_id(
                        proxies,
                        service_code=service_code,
                        preferred_country=preferred_country_id,
                    )
                    if next_country != country_id:
                        _warn(
                            "当前国家接码超时达到阈值，自动切换国家: "
                            f"{country_id} -> {next_country}"
                        )
                        country_id = next_country
                        continue
                _hero_sms_reuse_set(activation_id, phone_number, service_code, country_id)
                _hero_sms_reuse_touch(increase=True)
                _hero_sms_set_status(activation_id, 3, proxies)
                _warn("新购号码接码超时，已保留号码供后续复用，停止继续购号")
                return False, "接码超时，已保留复用号码"
            if reuse_on:
                _hero_sms_set_status(activation_id, 8, proxies)

        return False, last_reason
    finally:
        try:
            verify_balance_end, _ = hero_sms_get_balance(proxies)
            if verify_balance_end >= 0:
                spent_delta = 0.0
                if verify_balance_start >= 0:
                    spent_delta = max(0.0, verify_balance_start - verify_balance_end)
                _hero_sms_update_runtime(
                    spent_delta=spent_delta,
                    balance=verify_balance_end,
                    init_start=True,
                )
        except Exception:
            pass
        if lock_acquired:
            try:
                _HERO_SMS_VERIFY_LOCK.release()
            except Exception:
                pass


_BROWSER_FINGERPRINT_POOL: List[Dict[str, str]] = [
    {
        "label": "chrome131_win",
        "impersonate": "chrome131",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": "Windows",
    },
    {
        "label": "chrome120_win",
        "impersonate": "chrome120",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="24"',
        "platform": "Windows",
    },
    {
        "label": "safari17_macos",
        "impersonate": "safari",
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "sec_ch_ua": '"Not_A Brand";v="99", "Safari";v="17"',
        "platform": "macOS",
    },
]

_ACCEPT_LANGUAGE_POOL = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "zh-CN,zh;q=0.9,en;q=0.8",
]


def _choose_browser_fingerprint() -> Dict[str, str]:
    random_on = os.getenv("REGISTER_RANDOM_FINGERPRINT", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    if not random_on:
        fp = dict(_BROWSER_FINGERPRINT_POOL[0])
    else:
        fp = dict(random.choice(_BROWSER_FINGERPRINT_POOL))
    fp["accept_language"] = random.choice(_ACCEPT_LANGUAGE_POOL)
    return fp


def _apply_session_fingerprint(session: requests.Session, fp: Dict[str, str]) -> None:
    setattr(session, "_fp_impersonate", str(fp.get("impersonate") or "safari"))
    session.headers.update(
        {
            "User-Agent": str(fp.get("ua") or ""),
            "Accept-Language": str(fp.get("accept_language") or "en-US,en;q=0.9"),
            "sec-ch-ua": str(fp.get("sec_ch_ua") or ""),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{str(fp.get("platform") or "Windows")}"',
        }
    )


def _email_domain(email: str) -> str:
    try:
        if "@" not in str(email or ""):
            return ""
        return str(email or "").split("@", 1)[1].strip().lower()
    except Exception:
        return ""


def _gmail_canonical_identity(email: str) -> str:
    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        return ""
    local, domain = target.split("@", 1)
    local = str(local or "").strip().lower()
    domain = str(domain or "").strip().lower()
    if not local or not domain:
        return ""
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}" if local and domain else ""


def _gmail_unique_master_count(values: list[str]) -> int:
    seen: set[str] = set()
    for raw in values or []:
        item = str(raw or "").strip().lower()
        if not item:
            continue
        if "----" in item:
            item = str(item.split("----", 1)[0] or "").strip().lower()
        cid = _gmail_canonical_identity(item)
        if cid:
            seen.add(cid)
    return len(seen)


def _mail_service_signature() -> tuple[Any, ...]:
    provider = normalize_mail_provider(MAIL_SERVICE_PROVIDER)
    mail_domains = str(os.getenv("MAIL_DOMAINS", "") or "").strip()
    cf_temp_admin_auth = str(
        os.getenv("CF_TEMP_ADMIN_AUTH", os.getenv("ADMIN_AUTH", ""))
        or ""
    )
    cloudmail_api_url = str(os.getenv("CLOUDMAIL_API_URL", "") or "").strip()
    cloudmail_admin_email = str(os.getenv("CLOUDMAIL_ADMIN_EMAIL", "") or "").strip()
    cloudmail_admin_password = str(os.getenv("CLOUDMAIL_ADMIN_PASSWORD", "") or "")
    mail_curl_api_base = str(os.getenv("MAIL_CURL_API_BASE", "") or "").strip()
    mail_curl_key = str(os.getenv("MAIL_CURL_KEY", "") or "")
    luckyous_api_base = str(os.getenv("LUCKYOUS_API_BASE", "https://mails.luckyous.com") or "").strip()
    luckyous_api_key = str(os.getenv("LUCKYOUS_API_KEY", "") or "")
    luckyous_project_code = str(os.getenv("LUCKYOUS_PROJECT_CODE", "") or "").strip()
    luckyous_email_type = str(os.getenv("LUCKYOUS_EMAIL_TYPE", "ms_graph") or "").strip().lower()
    luckyous_domain = str(os.getenv("LUCKYOUS_DOMAIN", "") or "").strip().lower()
    luckyous_variant_mode = str(os.getenv("LUCKYOUS_VARIANT_MODE", "") or "").strip().lower()
    luckyous_specified_email = str(os.getenv("LUCKYOUS_SPECIFIED_EMAIL", "") or "").strip().lower()
    graph_accounts_file = str(os.getenv("GRAPH_ACCOUNTS_FILE", "") or "").strip()
    graph_accounts_mode = str(os.getenv("GRAPH_ACCOUNTS_MODE", "file") or "file").strip().lower()
    if graph_accounts_mode not in {"file", "api"}:
        graph_accounts_mode = "file"
    graph_api_base_url = str(
        os.getenv("GRAPH_API_BASE_URL", os.getenv("GRAPH_API_URL", ""))
        or ""
    ).strip()
    graph_api_token = str(
        os.getenv("GRAPH_API_TOKEN", os.getenv("MAIL_API_TOKEN", ""))
        or ""
    ).strip()
    graph_tenant = str(os.getenv("GRAPH_TENANT", "common") or "common").strip()
    graph_fetch_mode = str(os.getenv("GRAPH_FETCH_MODE", "graph_api") or "graph_api").strip()
    gmail_imap_user = str(os.getenv("GMAIL_IMAP_USER", "") or "").strip()
    gmail_imap_pass = str(os.getenv("GMAIL_IMAP_PASS", "") or "")
    gmail_alias_emails = str(os.getenv("GMAIL_ALIAS_EMAILS", "") or "").strip()
    gmail_imap_server = str(os.getenv("GMAIL_IMAP_SERVER", "imap.gmail.com") or "imap.gmail.com").strip()
    try:
        gmail_imap_port = int(str(os.getenv("GMAIL_IMAP_PORT", "993") or "993").strip())
    except Exception:
        gmail_imap_port = 993
    try:
        gmail_alias_tag_len = int(str(os.getenv("GMAIL_ALIAS_TAG_LEN", "8") or "8").strip())
    except Exception:
        gmail_alias_tag_len = 8
    gmail_alias_mix_googlemail = str(
        os.getenv("GMAIL_ALIAS_MIX_GOOGLEMAIL", "1") or "1"
    ).strip().lower() in {"1", "true", "yes", "on"}
    cf_routing_api_token = str(os.getenv("CF_ROUTING_API_TOKEN", "") or "").strip()
    cf_routing_zone_id = str(os.getenv("CF_ROUTING_ZONE_ID", "") or "").strip()
    cf_routing_domain = str(os.getenv("CF_ROUTING_DOMAIN", "") or "").strip()
    cf_routing_cleanup = str(os.getenv("CF_ROUTING_CLEANUP", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
    gmail_api_client_id = str(os.getenv("GMAIL_API_CLIENT_ID", "") or "").strip()
    gmail_api_client_secret = str(os.getenv("GMAIL_API_CLIENT_SECRET", "") or "").strip()
    gmail_api_refresh_token = str(os.getenv("GMAIL_API_REFRESH_TOKEN", "") or "").strip()
    gmail_api_user = str(os.getenv("GMAIL_API_USER", "") or "").strip()
    return (
        provider,
        str(WORKER_DOMAIN or "").strip().rstrip("/"),
        str(FREEMAIL_USERNAME or "").strip(),
        str(FREEMAIL_PASSWORD or ""),
        _ssl_verify(),
        mail_domains,
        cf_temp_admin_auth,
        cloudmail_api_url,
        cloudmail_admin_email,
        cloudmail_admin_password,
        mail_curl_api_base,
        mail_curl_key,
        luckyous_api_base,
        luckyous_api_key,
        luckyous_project_code,
        luckyous_email_type,
        luckyous_domain,
        luckyous_variant_mode,
        luckyous_specified_email,
        graph_accounts_file,
        graph_accounts_mode,
        graph_api_base_url,
        graph_api_token,
        graph_tenant,
        graph_fetch_mode,
        gmail_imap_user,
        gmail_imap_pass,
        gmail_alias_emails,
        gmail_imap_server,
        gmail_imap_port,
        gmail_alias_tag_len,
        gmail_alias_mix_googlemail,
        cf_routing_api_token,
        cf_routing_zone_id,
        cf_routing_domain,
        cf_routing_cleanup,
        gmail_api_client_id,
        gmail_api_client_secret,
        gmail_api_refresh_token,
        gmail_api_user,
    )


def _mail_service_reset() -> None:
    global _mail_service_client, _mail_service_sig
    _mail_service_client = None
    _mail_service_sig = None


def _freemail_session_cookie_reset() -> None:
    """兼容旧调用：重置邮箱服务会话缓存。"""
    _mail_service_reset()


def _get_mail_service_client():
    global _mail_service_client, _mail_service_sig
    sig = _mail_service_signature()
    if _mail_service_client is not None and _mail_service_sig == sig:
        return _mail_service_client

    (
        provider,
        base_url,
        username,
        password,
        verify_ssl,
        mail_domains,
        cf_temp_admin_auth,
        cloudmail_api_url,
        cloudmail_admin_email,
        cloudmail_admin_password,
        mail_curl_api_base,
        mail_curl_key,
        luckyous_api_base,
        luckyous_api_key,
        luckyous_project_code,
        luckyous_email_type,
        luckyous_domain,
        luckyous_variant_mode,
        luckyous_specified_email,
        graph_accounts_file,
        graph_accounts_mode,
        graph_api_base_url,
        graph_api_token,
        graph_tenant,
        graph_fetch_mode,
        gmail_imap_user,
        gmail_imap_pass,
        gmail_alias_emails,
        gmail_imap_server,
        gmail_imap_port,
        gmail_alias_tag_len,
        gmail_alias_mix_googlemail,
        cf_routing_api_token,
        cf_routing_zone_id,
        cf_routing_domain,
        cf_routing_cleanup,
        gmail_api_client_id,
        gmail_api_client_secret,
        gmail_api_refresh_token,
        gmail_api_user,
    ) = sig
    os.environ["CF_ROUTING_API_TOKEN"] = cf_routing_api_token
    os.environ["CF_ROUTING_ZONE_ID"] = cf_routing_zone_id
    os.environ["CF_ROUTING_DOMAIN"] = cf_routing_domain
    os.environ["CF_ROUTING_CLEANUP"] = "1" if cf_routing_cleanup else "0"
    os.environ["GMAIL_API_CLIENT_ID"] = gmail_api_client_id
    os.environ["GMAIL_API_CLIENT_SECRET"] = gmail_api_client_secret
    os.environ["GMAIL_API_REFRESH_TOKEN"] = gmail_api_refresh_token
    os.environ["GMAIL_API_USER"] = gmail_api_user
    os.environ["MAIL_DOMAINS"] = mail_domains
    os.environ["CF_TEMP_ADMIN_AUTH"] = cf_temp_admin_auth
    os.environ["ADMIN_AUTH"] = cf_temp_admin_auth
    os.environ["CLOUDMAIL_API_URL"] = cloudmail_api_url
    os.environ["CLOUDMAIL_ADMIN_EMAIL"] = cloudmail_admin_email
    os.environ["CLOUDMAIL_ADMIN_PASSWORD"] = cloudmail_admin_password
    os.environ["MAIL_CURL_API_BASE"] = mail_curl_api_base
    os.environ["MAIL_CURL_KEY"] = mail_curl_key
    os.environ["LUCKYOUS_API_BASE"] = luckyous_api_base
    os.environ["LUCKYOUS_API_KEY"] = luckyous_api_key
    os.environ["LUCKYOUS_PROJECT_CODE"] = luckyous_project_code
    os.environ["LUCKYOUS_EMAIL_TYPE"] = luckyous_email_type
    os.environ["LUCKYOUS_DOMAIN"] = luckyous_domain
    os.environ["LUCKYOUS_VARIANT_MODE"] = luckyous_variant_mode
    os.environ["LUCKYOUS_SPECIFIED_EMAIL"] = luckyous_specified_email
    os.environ["GRAPH_ACCOUNTS_FILE"] = graph_accounts_file
    os.environ["GRAPH_ACCOUNTS_MODE"] = graph_accounts_mode
    os.environ["GRAPH_API_BASE_URL"] = graph_api_base_url
    os.environ["GRAPH_API_TOKEN"] = graph_api_token
    os.environ["GRAPH_API_URL"] = graph_api_base_url
    os.environ["MAIL_API_TOKEN"] = graph_api_token
    os.environ["GRAPH_TENANT"] = graph_tenant
    os.environ["GRAPH_FETCH_MODE"] = graph_fetch_mode
    os.environ["GMAIL_IMAP_USER"] = gmail_imap_user
    os.environ["GMAIL_IMAP_PASS"] = gmail_imap_pass
    os.environ["GMAIL_ALIAS_EMAILS"] = gmail_alias_emails
    os.environ["GMAIL_IMAP_SERVER"] = gmail_imap_server
    os.environ["GMAIL_IMAP_PORT"] = str(gmail_imap_port)
    os.environ["GMAIL_ALIAS_TAG_LEN"] = str(gmail_alias_tag_len)
    os.environ["GMAIL_ALIAS_MIX_GOOGLEMAIL"] = "1" if gmail_alias_mix_googlemail else "0"
    try:
        client = build_mail_service(
            provider,
            base_url=base_url,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
        )
    except MailServiceError as e:
        raise RuntimeError(str(e)) from e

    _mail_service_client = client
    _mail_service_sig = sig
    return client


def get_email_and_token(proxies: Any = None) -> tuple:
    """创建临时邮箱并获取 Token 以兼容原流程"""
    _set_mailbox_init_error()
    _raise_if_stopped()
    try:
        client = _get_mail_service_client()
        provider = normalize_mail_provider(MAIL_SERVICE_PROVIDER)
        graph_accounts_mode = str(os.getenv("GRAPH_ACCOUNTS_MODE", "file") or "file").strip().lower()
        graph_api_mode = provider == "graph" and graph_accounts_mode == "api"
        allow_domains: List[str] = []
        random_domain = True
        mailbox_prefix = ""
        mailbox_random_len = 0
        domain_capable = provider in {"mailfree", "cloudflare_temp_email", "cloudmail"}

        if domain_capable:
            allow_domains = [str(x).strip() for x in (MAIL_ALLOWED_DOMAINS or []) if str(x).strip()]
            allow_sig = ",".join(sorted({str(x).strip().lower() for x in allow_domains if str(x).strip()}))
            if allow_domains:
                _info_once(
                    f"mail_allow_domains:{provider}:{allow_sig}",
                    f"已指定注册域名 {len(allow_domains)} 个",
                )
            random_domain = os.getenv("MAILFREE_RANDOM_DOMAIN", "1").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }
            mailbox_custom_enabled = os.getenv("MAILBOX_CUSTOM_ENABLED", "0").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            mailbox_prefix = (
                str(os.getenv("MAILBOX_PREFIX", "") or "").strip()
                if mailbox_custom_enabled
                else ""
            )
            mailbox_random_len = (
                _env_int("MAILBOX_RANDOM_LENGTH", 0, 0, 32)
                if mailbox_custom_enabled
                else 0
            )
            if mailbox_prefix or mailbox_random_len > 0:
                _info_once(
                    (
                        f"mail_local_rule:{provider}:{mailbox_prefix or '-'}:{mailbox_random_len}"
                    ),
                    "邮箱本地名规则: "
                    f"prefix={mailbox_prefix or '-'}"
                    f", random_len={mailbox_random_len}"
                )

        if provider == "mailfree":
            try:
                domains = client.list_domains(proxies=proxies)
            except Exception:
                domains = []

            effective_domains: List[str] = []
            if domains:
                if allow_domains:
                    allow_set = {str(x).strip().lower() for x in allow_domains if str(x).strip()}
                    effective_domains = [
                        str(d).strip()
                        for d in domains
                        if str(d).strip() and str(d).strip().lower() in allow_set
                    ]
                    missing = [
                        str(x).strip()
                        for x in allow_domains
                        if str(x).strip()
                        and str(x).strip().lower() not in {str(d).strip().lower() for d in domains}
                    ]
                    if missing:
                        show = ", ".join(missing[:4])
                        suffix = "..." if len(missing) > 4 else ""
                        _warn_once(
                            f"mailfree_missing_domains:{','.join(sorted([m.lower() for m in missing]))}",
                            f"指定域名不可用 {len(missing)} 个: {show}{suffix}",
                        )
                else:
                    effective_domains = [str(d).strip() for d in domains if str(d).strip()]

            if effective_domains:
                if random_domain:
                    if allow_domains:
                        _info_once(
                            (
                                "mailfree_strategy:"
                                f"allow_random:{len(effective_domains)}:{','.join(sorted([str(d).lower() for d in effective_domains]))}"
                            ),
                            f"mailfree 将在已选域名 {len(effective_domains)} 个中随机切换",
                        )
                    else:
                        _info_once(
                            (
                                "mailfree_strategy:"
                                f"all_random:{len(effective_domains)}:{','.join(sorted([str(d).lower() for d in effective_domains]))}"
                            ),
                            f"mailfree 可用域名 {len(effective_domains)} 个，注册时随机切换",
                        )
                else:
                    fixed_domain = str(effective_domains[0]).strip()
                    if allow_domains:
                        _info_once(
                            (
                                "mailfree_strategy:"
                                f"allow_fixed:{fixed_domain.lower()}:{len(effective_domains)}"
                            ),
                            f"mailfree 已选域名 {len(effective_domains)} 个，"
                            f"当前固定使用 {fixed_domain}"
                        )
                    else:
                        _info_once(
                            (
                                "mailfree_strategy:"
                                f"all_fixed:{fixed_domain.lower()}:{len(effective_domains)}"
                            ),
                            f"mailfree 可用域名 {len(effective_domains)} 个，当前固定使用 {fixed_domain}",
                        )
            elif domains:
                _warn_once(
                    f"mailfree_strategy:fallback_allow_empty:{len(domains)}",
                    "指定域名均不可用，将由服务端默认域名策略兜底",
                )
            else:
                _warn_once(
                    "mailfree_strategy:fallback_no_domains",
                    "mailfree 未返回可用域名列表，将由服务端默认域名策略兜底",
                )
        elif provider == "cloudflare_temp_email":
            cfg_domains = [
                x
                for x in re.split(r"[\n\r,;\s]+", str(os.getenv("MAIL_DOMAINS", "") or ""))
                if str(x or "").strip()
            ]
            _info(
                "Cloudflare Temp Email 模式："
                f"可选域名 {len(cfg_domains)} 个，"
                f"随机域名={'开' if random_domain else '关'}"
            )
        elif provider == "cloudmail":
            cfg_domains = [
                x
                for x in re.split(r"[\n\r,;\s]+", str(os.getenv("MAIL_DOMAINS", "") or ""))
                if str(x or "").strip()
            ]
            _info(
                "CloudMail 模式："
                f"可选域名 {len(cfg_domains)} 个，"
                f"随机域名={'开' if random_domain else '关'}"
            )
        elif provider == "graph":
            if graph_api_mode:
                _info("Graph 接口模式：从接口账号池取邮箱（跳过 token 探活）")
            else:
                _info("Graph 模式：忽略 MailFree 域名/前缀规则，直接从账号池取邮箱")
        elif provider == "mail_curl":
            _info("Mail-Curl 模式：按邮箱 ID 轮询收件")
        elif provider == "cf_email_routing":
            cf_r_domain = str(os.getenv("CF_ROUTING_DOMAIN", "") or "").strip()
            cf_r_user = str(os.getenv("GMAIL_API_USER", "") or "").strip()
            _info(
                "CF Email Routing 模式："
                f"域名={cf_r_domain or '-'}，"
                f"转发至={cf_r_user or '-'}"
            )
        elif provider == "luckyous":
            lucky_project = str(os.getenv("LUCKYOUS_PROJECT_CODE", "") or "").strip()
            lucky_type = str(os.getenv("LUCKYOUS_EMAIL_TYPE", "ms_graph") or "").strip().lower()
            lucky_domain = str(os.getenv("LUCKYOUS_DOMAIN", "") or "").strip().lower()
            lucky_variant = str(os.getenv("LUCKYOUS_VARIANT_MODE", "") or "").strip().lower()
            _info(
                "Luckyous API 模式："
                f"project={lucky_project or '-'}，"
                f"email_type={lucky_type or '-'}，"
                f"domain={lucky_domain or '-'}，"
                f"variant={lucky_variant or '-'}"
            )
        else:
            _info("Gmail 模式：通过 IMAP 别名池接码，忽略 MailFree 域名规则")
            gmail_user = str(os.getenv("GMAIL_IMAP_USER", "") or "").strip().lower()
            alias_raw = str(os.getenv("GMAIL_ALIAS_EMAILS", "") or "").strip()
            alias_pool = (
                [str(x or "").strip().lower() for x in re.split(r"[\n\r,;\s]+", alias_raw) if str(x or "").strip()]
                if alias_raw
                else ([gmail_user] if gmail_user else [])
            )
            alias_unique_count = _gmail_unique_master_count(alias_pool)
            if alias_pool and alias_unique_count <= 1:
                _warn_once(
                    f"gmail_alias_single_master:{alias_unique_count}",
                    "Gmail 别名池仅识别到 1 个唯一主号（点号/+tag/googlemail 视为同源），"
                    "若该邮箱已注册过可能持续触发 user_already_exists",
                )

        pick_rounds = 5
        if provider == "graph":
            pick_rounds = 8 if graph_api_mode else 30
        for _ in range(pick_rounds):
            _raise_if_stopped()
            try:
                email = client.generate_mailbox(
                    random_domain=random_domain,
                    allowed_domains=allow_domains,
                    local_prefix=mailbox_prefix,
                    random_length=mailbox_random_len,
                    proxies=proxies,
                )
            except MailServiceError as e:
                err_text = str(e)
                _warn(f"临时邮箱生成失败，准备重试: {err_text}")
                if provider == "graph":
                    low = err_text.lower()
                    fatal = (
                        "graph 账号池为空" in low
                        or "graph 账号文件为空" in low
                        or "graph 账号文件不存在" in low
                        or "graph 接口模式无法获取账号列表" in low
                        or "graph 接口模式鉴权失败" in low
                        or "graph 接口账号池为空" in low
                    )
                    if fatal:
                        _set_mailbox_init_error("graph_pool_exhausted", err_text)
                        _err("Graph 账号池不可用，停止本轮注册")
                        return "", ""
                email = ""
            if email:
                _raise_if_stopped()
                if provider == "graph" and str(email).strip().lower() in _GRAPH_BAD_EMAILS:
                    _warn(f"跳过已标记不可用 Graph 邮箱: {email}")
                    continue
                if provider == "graph":
                    if graph_api_mode:
                        _info(f"Graph 接口邮箱已分配: {email}")
                    else:
                        try:
                            refresh_res = client.refresh_mailbox_token(email, proxies=proxies)
                            token_hint = str((refresh_res or {}).get("token_prefix") or "").strip()
                            if token_hint:
                                _info(f"Graph 邮箱令牌已刷新: {email} · {token_hint}")
                            else:
                                _info(f"Graph 邮箱令牌已刷新: {email}")
                        except Exception as e:
                            _warn(f"Graph 邮箱令牌刷新失败，剔除后重试: {email} -> {e}")
                            _mark_graph_bad_email(email, "token_refresh_failed")
                            continue
                return email, email

        _err("临时邮箱创建失败")
        if provider == "graph":
            _set_mailbox_init_error("graph_pool_exhausted", "Graph 账号池无可用邮箱")
        return "", ""
    except UserStoppedError:
        raise
    except Exception as e:
        _err(f"请求临时邮箱 API 出错: {e}")
        if normalize_mail_provider(MAIL_SERVICE_PROVIDER) == "graph":
            _set_mailbox_init_error("graph_pool_exhausted", str(e))
        return "", ""


def get_oai_code(
    token: str,
    email: str,
    proxies: Any = None,
    *,
    poll_rounds: int | None = None,
    poll_interval: float | None = None,
) -> str:
    """轮询 Worker 邮箱取 OpenAI 6 位码；邮件按 id 降序优先看较新。"""
    _ = token
    _raise_if_stopped()
    try:
        client = _get_mail_service_client()
    except Exception as e:
        _err(f"邮箱服务初始化失败: {e}")
        return ""

    _out(f"[*] 正在等待邮箱 {email} 的验证码...", end="", flush=True)
    if poll_rounds is None:
        poll_rounds = _env_int("OTP_POLL_MAX_ROUNDS", 40, 5, 300)
    else:
        poll_rounds = max(1, min(300, int(poll_rounds)))
    if poll_interval is None:
        poll_interval = _env_float("OTP_POLL_INTERVAL_SEC", 3.0, 0.2, 15.0)
    else:
        poll_interval = max(0.2, min(15.0, float(poll_interval)))

    def _progress_tick() -> None:
        _raise_if_stopped()
        _out(".", end="", flush=True)

    code = client.poll_otp_code(
        email,
        poll_rounds=poll_rounds,
        poll_interval=poll_interval,
        proxies=proxies,
        progress_cb=_progress_tick,
    )
    if code:
        _out(f"\n[*] 已收到验证码: {code}")
        return code

    _out("\n[*] 超时，未收到验证码")
    return ""


def get_oai_code_with_single_resend(
    token: str,
    email: str,
    proxies: Any = None,
    *,
    resend_once_cb: Any = None,
    scene: str = "OTP",
) -> str:
    """先短轮询；每 10 秒收不到就重发，达到上限后再常规轮询。"""
    first_wait_sec = _env_float("OTP_RESEND_WAIT_SEC", 10.0, 2.0, 60.0)
    first_interval = _env_float("OTP_RESEND_POLL_INTERVAL_SEC", 1.0, 0.2, 5.0)
    max_resend_times = _env_int("OTP_RESEND_MAX_TIMES", 3, 0, 10)
    resend_gap_sec = _env_float("OTP_RESEND_GAP_SEC", 0.8, 0.0, 10.0)
    quick_rounds = max(1, int((first_wait_sec / max(0.2, first_interval)) + 0.999))

    for resend_idx in range(max_resend_times + 1):
        code = get_oai_code(
            token,
            email,
            proxies,
            poll_rounds=quick_rounds,
            poll_interval=first_interval,
        )
        if code:
            return code

        if resend_idx >= max_resend_times:
            break

        _warn(
            f"{scene} {int(first_wait_sec)} 秒内未收到验证码，"
            f"尝试重发第 {resend_idx + 1}/{max_resend_times} 次"
        )
        if callable(resend_once_cb):
            try:
                resent_ok = bool(resend_once_cb())
                if resent_ok:
                    _info(f"{scene} 重发成功，继续等待验证码")
                else:
                    _warn(f"{scene} 重发返回异常，继续等待验证码")
            except Exception as e:
                _warn(f"{scene} 重发请求异常: {e}")

        if resend_gap_sec > 0 and _sleep_interruptible(resend_gap_sec):
            raise UserStoppedError("stopped_by_user")

    if max_resend_times > 0:
        _warn(f"{scene} 已达到最大重发次数({max_resend_times})，继续常规等待")

    return get_oai_code(token, email, proxies)


# --- OAuth2 / PKCE 与 token 交换 ---

AUTH_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"

DEFAULT_REDIRECT_URI = f"http://localhost:1455/auth/callback"
DEFAULT_SCOPE = "openid email profile offline_access"


def _b64url_no_pad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _sha256_b64url_no_pad(s: str) -> str:
    return _b64url_no_pad(hashlib.sha256(s.encode("ascii")).digest())


def _random_state(nbytes: int = 16) -> str:
    return secrets.token_urlsafe(nbytes)


def _pkce_verifier() -> str:
    return secrets.token_urlsafe(64)


def _parse_callback_url(callback_url: str) -> Dict[str, Any]:
    candidate = callback_url.strip()
    if not candidate:
        return {"code": "", "state": "", "error": "", "error_description": ""}

    if "://" not in candidate:
        if candidate.startswith("?"):
            candidate = f"http://localhost{candidate}"
        elif any(ch in candidate for ch in "/?#") or ":" in candidate:
            candidate = f"http://{candidate}"
        elif "=" in candidate:
            candidate = f"http://localhost/?{candidate}"

    parsed = urllib.parse.urlparse(candidate)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    fragment = urllib.parse.parse_qs(parsed.fragment, keep_blank_values=True)

    for key, values in fragment.items():
        if key not in query or not query[key] or not (query[key][0] or "").strip():
            query[key] = values

    def get1(k: str) -> str:
        v = query.get(k, [""])
        return (v[0] or "").strip()

    code = get1("code")
    state = get1("state")
    error = get1("error")
    error_description = get1("error_description")

    if code and not state and "#" in code:
        code, state = code.split("#", 1)

    if not error and error_description:
        error, error_description = error_description, ""

    return {
        "code": code,
        "state": state,
        "error": error,
        "error_description": error_description,
    }


def _jwt_claims_no_verify(id_token: str) -> Dict[str, Any]:
    if not id_token or id_token.count(".") < 2:
        return {}
    payload_b64 = id_token.split(".")[1]
    pad = "=" * ((4 - (len(payload_b64) % 4)) % 4)
    try:
        payload = base64.urlsafe_b64decode((payload_b64 + pad).encode("ascii"))
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return {}


def _decode_jwt_segment(seg: str) -> Dict[str, Any]:
    raw = (seg or "").strip()
    if not raw:
        return {}
    pad = "=" * ((4 - (len(raw) % 4)) % 4)
    try:
        decoded = base64.urlsafe_b64decode((raw + pad).encode("ascii"))
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return {}


def _oai_auth_session_claims(cookie_val: str) -> Dict[str, Any]:
    """解析 oai-client-auth-session：优先 payload（段 1）；若其中无 workspaces 再尝试段 0（兼容部分返回格式）。"""
    parts = (cookie_val or "").split(".")
    if len(parts) >= 3:
        payload = _decode_jwt_segment(parts[1])
        if payload.get("workspaces"):
            return payload
        alt = _decode_jwt_segment(parts[0])
        if alt.get("workspaces"):
            return alt
        return payload
    if len(parts) == 2:
        return _decode_jwt_segment(parts[0])
    return {}


def _extract_workspaces_from_claims(claims: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    raw = claims.get("workspaces")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            wid = str(item.get("id") or item.get("workspace_id") or "").strip()
            if not wid:
                continue
            normalized = dict(item)
            normalized["id"] = wid
            rows.append(normalized)
    if rows:
        return rows

    single = claims.get("workspace")
    if isinstance(single, dict):
        wid = str(single.get("id") or single.get("workspace_id") or "").strip()
        if wid:
            return [{"id": wid}]

    wid = str(claims.get("workspace_id") or claims.get("default_workspace_id") or "").strip()
    if wid:
        return [{"id": wid}]
    return []


def _session_workspaces(session: requests.Session) -> tuple[str, Dict[str, Any], List[Dict[str, Any]]]:
    auth_cookie = str(session.cookies.get("oai-client-auth-session") or "").strip()
    if not auth_cookie:
        return "", {}, []
    claims = _oai_auth_session_claims(auth_cookie)
    return auth_cookie, claims, _extract_workspaces_from_claims(claims)


def _extract_workspaces_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        rows = _extract_workspaces_from_claims(payload)
        if rows:
            return rows
        for key in ("data", "session", "account", "user", "result"):
            sub = payload.get(key)
            if isinstance(sub, dict):
                rows = _extract_workspaces_from_claims(sub)
                if rows:
                    return rows
    return []


def _fetch_workspaces_from_api(session: requests.Session, proxies: Any) -> tuple[List[Dict[str, Any]], str]:
    endpoints = (
        "https://auth.openai.com/api/accounts/me",
        "https://auth.openai.com/api/accounts/session",
        "https://auth.openai.com/api/accounts/workspaces",
    )
    for ep in endpoints:
        try:
            resp = _session_get_with_tls_retry(
                session,
                ep,
                proxies=proxies,
                allow_redirects=False,
                timeout=15,
                max_attempts=2,
            )
        except UserStoppedError:
            raise
        except Exception:
            continue

        code = int(getattr(resp, "status_code", 0) or 0)
        if code in {401, 403, 404}:
            continue
        try:
            data = resp.json() or {}
        except Exception:
            continue

        rows = _extract_workspaces_from_payload(data)
        if rows:
            return rows, ep
    return [], ""


def _refresh_workspace_candidates(
    session: requests.Session,
    proxies: Any,
    *,
    hint_url: str = "",
    base_referer: str = "https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
) -> tuple[List[Dict[str, Any]], str]:
    referer = str(base_referer or "https://auth.openai.com/sign-in-with-chatgpt/codex/consent")
    wait_workspace = _env_float("REGISTER_WORKSPACE_WAIT_SEC", 0.5, 0.0, 3.0)
    rounds = _env_int("REGISTER_WORKSPACE_REFRESH_ROUNDS", 3, 1, 8)

    urls: List[str] = ["https://auth.openai.com/workspace"]
    hint = str(hint_url or "").strip()
    if hint.startswith("http") and hint not in urls:
        urls.append(hint)

    for _ in range(rounds):
        for url in urls:
            _raise_if_stopped()
            try:
                resp = _session_get_with_tls_retry(
                    session,
                    url,
                    proxies=proxies,
                    allow_redirects=True,
                    timeout=20,
                    max_attempts=3,
                )
                final_url = str(getattr(resp, "url", "") or "").strip()
                if final_url:
                    referer = final_url
            except UserStoppedError:
                raise
            except Exception as e:
                _warn(f"刷新 workspace 会话失败({url}): {e}")
            if wait_workspace > 0 and _sleep_interruptible(wait_workspace):
                raise UserStoppedError("stopped_by_user")
            _, _, workspaces = _session_workspaces(session)
            if workspaces:
                return workspaces, referer
            api_workspaces, api_from = _fetch_workspaces_from_api(session, proxies)
            if api_workspaces:
                if api_from:
                    _info(f"通过 API 获取到 workspace: {api_from}")
                return api_workspaces, referer

    return [], referer


def _extract_next_url(data: Dict[str, Any]) -> str:
    """解析 JSON 响应中的下一跳 URL：优先 continue_url，否则按 page.type 映射。"""
    continue_url = str(data.get("continue_url") or "").strip()
    if continue_url:
        return continue_url
    page_type = str((data.get("page") or {}).get("type") or "").strip()
    mapping = {
        "email_otp_verification": "https://auth.openai.com/email-verification",
        "sign_in_with_chatgpt_codex_consent": "https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
        "workspace": "https://auth.openai.com/workspace",
        "add_phone": "https://auth.openai.com/add-phone",
        "phone_verification": "https://auth.openai.com/add-phone",
        "phone_otp_verification": "https://auth.openai.com/add-phone",
        "phone_number_verification": "https://auth.openai.com/add-phone",
    }
    return mapping.get(page_type, "")


def _is_add_phone_url(url: str) -> bool:
    u = str(url or "").strip().lower()
    if not u:
        return False
    return (
        ("/add-phone" in u)
        or ("add_phone" in u)
        or ("/phone-verification" in u)
        or ("phone_verification" in u)
    )


def _is_add_phone_page(page_type: str) -> bool:
    p = str(page_type or "").strip().lower().replace("-", "_")
    if not p:
        return False
    if p in {
        "add_phone",
        "phone_verification",
        "phone_otp_verification",
        "phone_number_verification",
    }:
        return True
    return "phone" in p and ("add" in p or "verification" in p)


def _handle_add_phone_challenge(
    session: requests.Session,
    *,
    current_url: str,
    proxies: Any,
    email: str,
    hint_url: str = "",
    scene: str = "",
    mark_bad_email_on_fail: bool = True,
) -> tuple[bool, str, str]:
    resolved_current = str(current_url or "").strip()
    resolved_hint = str(hint_url or "").strip()
    target = resolved_current or resolved_hint
    if not _is_add_phone_url(target):
        return True, resolved_current, ""

    label = str(scene or "").strip()
    if label:
        _info(f"{label}命中 add-phone，尝试 HeroSMS 手机验证")
    else:
        _info("命中 add-phone，尝试 HeroSMS 手机验证")

    phone_ok, phone_next = _try_verify_phone_via_hero_sms(
        session,
        proxies=proxies,
        hint_url=(resolved_hint or resolved_current),
    )
    if phone_ok:
        next_url = str(phone_next or resolved_current or resolved_hint).strip()
        return True, next_url, ""

    reason = str(phone_next or "add-phone 手机验证失败").strip()
    _warn(f"HeroSMS 手机验证失败: {reason}")
    if _is_hero_sms_balance_issue(reason):
        _warn("HeroSMS 余额不足，保留当前账号，等待充值后重试")
        raise HeroSmsBalanceLowError(reason)
    if _is_hero_sms_country_blocked_issue(reason):
        raise HeroSmsCountryBlockedError(reason)
    if _is_hero_sms_timeout_issue(reason):
        _warn("HeroSMS 接码超时，保留复用号码并结束当前尝试")
        raise HeroSmsCodeTimeoutError(reason)
    if mark_bad_email_on_fail:
        _mark_graph_bad_email(email, "add_phone_required")
    return False, (resolved_current or resolved_hint), reason


def _to_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _post_form(url: str, data: Dict[str, str], timeout: int = 30) -> Dict[str, Any]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        context = None
        if not _ssl_verify():
            context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            raw = resp.read()
            if resp.status != 200:
                raise RuntimeError(
                    f"token exchange failed: {resp.status}: {raw.decode('utf-8', 'replace')}"
                )
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        raise RuntimeError(
            f"token exchange failed: {exc.code}: {raw.decode('utf-8', 'replace')}"
        ) from exc


def _post_with_retry(
    session: requests.Session,
    url: str,
    *,
    headers: Dict[str, Any],
    data: Any = None,
    json_body: Any = None,
    proxies: Any = None,
    timeout: int = 30,
    retries: int = 2,
) -> Any:
    last_error: Optional[Exception] = None
    backoff_base = _env_float("HTTP_RETRY_BACKOFF_BASE_SEC", 2.0, 0.2, 10.0)
    for attempt in range(retries + 1):
        _raise_if_stopped()
        try:
            if json_body is not None:
                return session.post(
                    url,
                    headers=headers,
                    json=json_body,
                    proxies=proxies,
                    verify=_ssl_verify(),
                    timeout=timeout,
                )
            return session.post(
                url,
                headers=headers,
                data=data,
                proxies=proxies,
                verify=_ssl_verify(),
                timeout=timeout,
            )
        except Exception as e:
            last_error = e
            if attempt >= retries:
                break
            if _sleep_interruptible(backoff_base * (attempt + 1)):
                raise UserStoppedError("stopped_by_user")
    if last_error:
        raise last_error
    raise RuntimeError("Request failed without exception")


@dataclass(frozen=True)
class OAuthStart:
    auth_url: str
    state: str
    code_verifier: str
    redirect_uri: str


def generate_oauth_url(
    *, redirect_uri: str = DEFAULT_REDIRECT_URI, scope: str = DEFAULT_SCOPE
) -> OAuthStart:
    """构造带 PKCE 的 OAuth 授权 URL 与 code_verifier（供后续换 token）。"""
    state = _random_state()
    code_verifier = _pkce_verifier()
    code_challenge = _sha256_b64url_no_pad(code_verifier)

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "login",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    return OAuthStart(
        auth_url=auth_url,
        state=state,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
    )


def submit_callback_url(
    *,
    callback_url: str,
    expected_state: str,
    code_verifier: str,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
) -> Dict[str, Any]:
    """用授权码换 access/refresh token，并组装 GUI/工具可用的 account 字典。"""
    cb = _parse_callback_url(callback_url)
    if cb["error"]:
        desc = cb["error_description"]
        raise RuntimeError(f"oauth error: {cb['error']}: {desc}".strip())

    if not cb["code"]:
        raise ValueError("callback url missing ?code=")
    if not cb["state"]:
        raise ValueError("callback url missing ?state=")
    if cb["state"] != expected_state:
        raise ValueError("state mismatch")

    token_resp = _post_form(
        TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": cb["code"],
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )

    access_token = (token_resp.get("access_token") or "").strip()
    refresh_token = (token_resp.get("refresh_token") or "").strip()
    id_token_str = (token_resp.get("id_token") or "").strip()
    expires_in = _to_int(token_resp.get("expires_in"))

    id_claims = _jwt_claims_no_verify(id_token_str)
    at_claims = _jwt_claims_no_verify(access_token)

    email = str(id_claims.get("email") or "").strip()
    id_auth = id_claims.get("https://api.openai.com/auth") or {}
    at_auth = at_claims.get("https://api.openai.com/auth") or {}

    chatgpt_account_id = str(at_auth.get("chatgpt_account_id") or id_auth.get("chatgpt_account_id") or "")
    chatgpt_user_id = str(at_auth.get("chatgpt_user_id") or id_auth.get("chatgpt_user_id") or "")
    orgs = id_auth.get("organizations") or []
    organization_id = str(orgs[0].get("id", "")) if orgs else ""

    now = int(time.time())
    now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    local_offset = datetime.now(timezone.utc).astimezone().strftime("%z")
    local_offset_fmt = local_offset[:3] + ":" + local_offset[3:]
    expires_at_local = (datetime.now(timezone.utc) + timedelta(seconds=max(expires_in, 0))).astimezone().strftime(f"%Y-%m-%dT%H:%M:%S{local_offset_fmt}")

    return {
        "name": email,
        "platform": "openai",
        "type": "oauth",
        "credentials": {
            "access_token": access_token,
            "chatgpt_account_id": chatgpt_account_id,
            "chatgpt_user_id": chatgpt_user_id,
            "client_id": CLIENT_ID,
            "email": email,
            "expires_at": expires_at_local,
            "expires_in": expires_in,
            "id_token": id_token_str,
            "organization_id": organization_id,
            "refresh_token": refresh_token,
        },
        "extra": {
            "email": email,
        },
        "concurrency": 10,
        "priority": 1,
        "rate_multiplier": 1,
        "auto_pause_on_expired": True,
    }


_ACCOUNTS_FILE_PATH: Optional[str] = None


def _init_accounts_file(output_dir: str = "") -> str:
    """启动时创建 accounts JSON 文件，返回文件路径"""
    global _ACCOUNTS_FILE_PATH
    now_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data = {
        "exported_at": now_utc,
        "proxies": [],
        "accounts": [],
    }
    file_name = f"accounts_{int(time.time())}.json"
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        file_name = os.path.join(output_dir, file_name)
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _ACCOUNTS_FILE_PATH = file_name
    return file_name


def _append_account_to_file(account: Dict[str, Any]) -> bool:
    """将一个 account 追加写入 accounts JSON 文件，成功返回 True。"""
    if not _ACCOUNTS_FILE_PATH:
        return False
    try:
        with open(_ACCOUNTS_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["exported_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        data["accounts"].append(account)
        with open(_ACCOUNTS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        _warn(f"写入 accounts 文件失败: {e}")
        return False


# --- HTTP 会话、重定向与注册主流程 ---


def _session_get_with_tls_retry(
    session: requests.Session,
    url: str,
    *,
    proxies: Any,
    allow_redirects: bool = False,
    timeout: int = 25,
    max_attempts: int = 5,
) -> Any:
    """curl_cffi 在 Windows 上偶发 TLS(35)/OpenSSL 抖动，做有限次退避重试。"""
    last_err: Optional[Exception] = None
    delay_base = _env_float("TLS_RETRY_BASE_SEC", 1.0, 0.2, 5.0)
    delay_step = _env_float("TLS_RETRY_STEP_SEC", 0.85, 0.1, 3.0)
    for attempt in range(max_attempts):
        _raise_if_stopped()
        try:
            return session.get(
                url,
                allow_redirects=allow_redirects,
                proxies=proxies,
                verify=_ssl_verify(),
                timeout=timeout,
            )
        except Exception as e:
            last_err = e
            es = str(e).lower()
            transient = any(
                sub in es
                for sub in (
                    "curl:",
                    "tls",
                    "ssl",
                    "openssl",
                    "error:00000000",
                    "connection reset",
                    "timed out",
                    "timeout",
                    "eof",
                )
            )
            if not transient or attempt >= max_attempts - 1:
                raise
            delay = delay_base + attempt * delay_step
            reason_tag = "网络"
            if "timed out" in es or "timeout" in es:
                reason_tag = "超时"
            elif "connection reset" in es or "connection aborted" in es or "eof" in es:
                reason_tag = "连接中断"
            elif (
                "tls" in es
                or "ssl" in es
                or "openssl" in es
                or "error:00000000" in es
            ):
                reason_tag = "TLS/SSL"
            detail = " ".join(str(e).split())
            if len(detail) > 180:
                detail = detail[:180] + "..."
            _warn(
                f"{reason_tag}异常，{delay:.1f}s 后重试 ({attempt + 1}/{max_attempts})：{detail}"
            )
            if _sleep_interruptible(delay):
                raise UserStoppedError("stopped_by_user")
    raise last_err  # pragma: no cover


def _is_transient_net_error(exc: BaseException) -> bool:
    es = str(exc).lower()
    return any(
        sub in es
        for sub in (
            "curl:",
            "tls",
            "ssl",
            "openssl",
            "error:00000000",
            "connection reset",
            "timed out",
            "timeout",
            "eof",
            "connection aborted",
        )
    )


def _follow_redirect_chain(
    session: requests.Session,
    start_url: str,
    proxies: Any,
    max_redirects: int = 16,
) -> tuple[Any, str]:
    """跟随 3xx；若 Location 含 code 与 state 则返回 (None, 该 URL)。"""
    current_url = start_url
    response = None
    for _ in range(max_redirects):
        _raise_if_stopped()
        response = _session_get_with_tls_retry(
            session,
            current_url,
            proxies=proxies,
            allow_redirects=False,
            timeout=25,
        )
        if response.status_code not in (301, 302, 303, 307, 308):
            return response, current_url
        loc = (response.headers.get("Location") or "").strip()
        if not loc:
            return response, current_url
        nxt = urllib.parse.urljoin(current_url, loc)
        if "code=" in nxt and "state=" in nxt:
            return None, nxt
        current_url = nxt
    return response, current_url


def _build_sentinel_for_session(
    session: requests.Session, flow: str, proxies: Any
) -> Optional[str]:
    """向 Sentinel 换取 token；对 TLS/连接抖动做有限次重试（与 GET 重试策略一致）。"""
    if _stop_requested():
        return None
    did = session.cookies.get("oai-did")
    if not did:
        return None
    payload = json.dumps({"p": "", "id": did, "flow": flow}, separators=(",", ":"))
    imp = str(getattr(session, "_fp_impersonate", "safari") or "safari")
    ua = str(
        session.headers.get("User-Agent")
        or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    max_attempts = 5
    delay_base = _env_float("SENTINEL_RETRY_BASE_SEC", 1.0, 0.2, 5.0)
    delay_step = _env_float("SENTINEL_RETRY_STEP_SEC", 0.85, 0.1, 3.0)
    for attempt in range(max_attempts):
        if _stop_requested():
            return None
        try:
            sen_resp = requests.post(
                "https://sentinel.openai.com/backend-api/sentinel/req",
                headers={
                    "origin": "https://sentinel.openai.com",
                    "referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html?sv=20260219f9f6",
                    "content-type": "text/plain;charset=UTF-8",
                    "user-agent": ua,
                },
                data=payload,
                proxies=proxies,
                impersonate=imp,
                verify=_ssl_verify(),
                timeout=15,
            )
        except Exception as e:
            if not _is_transient_net_error(e) or attempt >= max_attempts - 1:
                _warn(f"Sentinel({flow}) 请求异常: {e}")
                return None
            delay = delay_base + attempt * delay_step
            _warn(
                f"Sentinel({flow}) 网络异常，{delay:.1f}s 后重试 ({attempt + 1}/{max_attempts})…"
            )
            if _sleep_interruptible(delay):
                return None
            continue
        if sen_resp.status_code != 200:
            if attempt >= max_attempts - 1:
                _warn(f"Sentinel({flow}) HTTP {sen_resp.status_code}")
                return None
            delay = delay_base + attempt * delay_step
            _warn(
                f"Sentinel({flow}) HTTP {sen_resp.status_code}，{delay:.1f}s 后重试…"
            )
            if _sleep_interruptible(delay):
                return None
            continue
        tok = str((sen_resp.json() or {}).get("token") or "").strip()
        if not tok:
            return None
        return json.dumps(
            {"p": "", "t": "", "c": tok, "id": did, "flow": flow},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return None


def _login_via_password_and_finish_oauth(
    email: str,
    password: str,
    dev_token: str,
    proxies: Any,
    *,
    mark_bad_email_on_invalid_pwd: bool = True,
    force_passwordless_otp: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    手机号页或无 OAuth 完成时的补救登录。

    须使用全新 Session 与全新 OAuth（PKCE/state），先跟随授权 URL，再 authorize/continue、
    password/verify；不可在注册未完成 OAuth 的旧 Session 里直接交密码（会 invalid_username_or_password）。
    """
    _raise_if_stopped()
    _info("补救登录：独立 Session + OAuth + password/verify")
    _info(f"邮箱: {email}")

    oauth = generate_oauth_url()
    fp = _choose_browser_fingerprint()
    s = requests.Session(proxies=proxies, impersonate=str(fp.get("impersonate") or "safari"))
    _apply_session_fingerprint(s, fp)
    _info(f"登录指纹: {fp.get('label', '-')}")

    def _submit_callback_or_none(callback_url: str, success_msg: str = "") -> Optional[Dict[str, Any]]:
        try:
            account_obj = submit_callback_url(
                callback_url=callback_url,
                code_verifier=oauth.code_verifier,
                redirect_uri=oauth.redirect_uri,
                expected_state=oauth.state,
            )
            if success_msg:
                _info(success_msg)
            return account_obj
        except Exception as e:
            msg = str(e)
            _err(f"交换 token 失败: {msg}")
            if _is_region_blocked_issue(msg):
                raise RegionBlockedError(msg)
            return None

    def _try_login_via_email_otp_api(
        referer_hint: str,
        *,
        prefer_passwordless: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if prefer_passwordless:
            _info("改走验证码登录接口(passwordless/send-otp)")
        else:
            _info("改走验证码登录接口(email-otp)")
        ref = str(referer_hint or "").strip()
        if not ref.startswith("http"):
            ref = "https://auth.openai.com/email-verification"
        ref_candidates = [
            ref,
            "https://auth.openai.com/email-verification",
            "https://auth.openai.com/log-in/password",
            "https://auth.openai.com/login/password",
        ]
        dedup_refs = [
            x for x in dict.fromkeys([str(v or "").strip() for v in ref_candidates]).keys() if x
        ]

        endpoint_candidates = [
            "https://auth.openai.com/api/accounts/passwordless/send-otp",
            "https://auth.openai.com/api/accounts/email-otp/send",
        ]
        if not prefer_passwordless:
            endpoint_candidates = [
                "https://auth.openai.com/api/accounts/email-otp/send",
                "https://auth.openai.com/api/accounts/passwordless/send-otp",
            ]

        def _send_login_otp_once() -> tuple[Any, str]:
            last_resp = None
            last_ep = ""
            endpoint_hint = ""
            for ref_item in dedup_refs:
                for endpoint in endpoint_candidates:
                    hdrs: Dict[str, str] = {
                        "referer": ref_item,
                        "accept": "application/json",
                        "content-type": "application/json",
                    }
                    st = _build_sentinel_for_session(s, "authorize_continue", proxies)
                    if st:
                        hdrs["openai-sentinel-token"] = st

                    if endpoint.endswith("/passwordless/send-otp"):
                        resp = _post_with_retry(
                            s,
                            endpoint,
                            headers=hdrs,
                            data="",
                            proxies=proxies,
                            timeout=30,
                            retries=1,
                        )
                    else:
                        resp = _post_with_retry(
                            s,
                            endpoint,
                            headers=hdrs,
                            json_body={},
                            proxies=proxies,
                            timeout=30,
                            retries=1,
                        )

                    last_resp = resp
                    last_ep = endpoint
                    endpoint_hint = endpoint.rsplit("/", 1)[-1]
                    if resp.status_code == 200:
                        return resp, endpoint_hint
            return last_resp, endpoint_hint or (last_ep.rsplit("/", 1)[-1] if last_ep else "send-otp")

        try:
            otp_send_resp, otp_endpoint = _send_login_otp_once()
        except UserStoppedError:
            raise
        except Exception as e:
            _warn(f"验证码登录 OTP 发送请求异常: {e}")
            return None
        _info(f"验证码登录 OTP 发送 HTTP {otp_send_resp.status_code} ({otp_endpoint})")
        if otp_send_resp.status_code != 200:
            _warn(f"验证码登录 OTP 发送失败: {otp_send_resp.text[:300]}")
            return None

        def _resend_login_otp_once() -> bool:
            resend_resp, resend_ep = _send_login_otp_once()
            _info(f"验证码登录 OTP 重发 HTTP {resend_resp.status_code} ({resend_ep})")
            if resend_resp.status_code != 200:
                _warn(f"验证码登录 OTP 重发异常: {resend_resp.text[:300]}")
            return resend_resp.status_code == 200

        code = get_oai_code_with_single_resend(
            dev_token,
            email,
            proxies,
            resend_once_cb=_resend_login_otp_once,
            scene="验证码登录 OTP",
        )
        if not code:
            _err("验证码登录流程未收到邮箱验证码")
            return None

        validate_headers: Dict[str, str] = {
            "referer": "https://auth.openai.com/email-verification",
            "accept": "application/json",
            "content-type": "application/json",
        }
        validate_sentinel = _build_sentinel_for_session(s, "authorize_continue", proxies)
        if validate_sentinel:
            validate_headers["openai-sentinel-token"] = validate_sentinel
        try:
            validate_resp = _post_with_retry(
                s,
                "https://auth.openai.com/api/accounts/email-otp/validate",
                headers=validate_headers,
                json_body={"code": code},
                proxies=proxies,
                timeout=30,
                retries=2,
            )
        except UserStoppedError:
            raise
        except Exception as e:
            _warn(f"验证码登录 OTP 校验请求异常: {e}")
            return None
        _info(f"验证码登录 OTP 校验 HTTP {validate_resp.status_code}")
        if validate_resp.status_code != 200:
            _warn(f"验证码登录 OTP 校验失败: {validate_resp.text[:400]}")
            return None

        try:
            vj = validate_resp.json() or {}
        except Exception:
            vj = {}
        otp_next = _extract_next_url(vj).strip() or str(vj.get("continue_url") or "").strip()
        otp_url = otp_next or ref
        if otp_url and not otp_url.startswith("http"):
            otp_url = f"https://auth.openai.com{otp_url}" if otp_url.startswith("/") else otp_url
        if otp_url:
            _, otp_url = _follow_redirect_chain(s, otp_url, proxies)

        solved, otp_url, _ = _handle_add_phone_challenge(
            s,
            current_url=otp_url,
            proxies=proxies,
            email=email,
            hint_url=otp_url,
            scene="验证码登录 OTP 后",
        )
        if not solved:
            return None
        if "code=" in otp_url and "state=" in otp_url:
            return _submit_callback_or_none(otp_url, success_msg="OAuth 换 token 成功（验证码登录）")
        return None

    _, current_url = _follow_redirect_chain(s, oauth.auth_url, proxies)
    if "code=" in current_url and "state=" in current_url:
        return _submit_callback_or_none(current_url)

    did = s.cookies.get("oai-did")
    _info(f"Device ID: {did}")

    st_user = _build_sentinel_for_session(s, "authorize_continue", proxies)
    uh: Dict[str, str] = {
        "referer": current_url,
        "accept": "application/json",
        "content-type": "application/json",
    }
    if st_user:
        uh["openai-sentinel-token"] = st_user

    username_body = json.dumps({"username": {"value": email, "kind": "email"}})
    username_resp = s.post(
        "https://auth.openai.com/api/accounts/authorize/continue",
        headers=uh,
        data=username_body,
        proxies=proxies,
        verify=_ssl_verify(),
        timeout=20,
    )
    _info(f"登录-用户名提交 HTTP {username_resp.status_code}")
    if username_resp.status_code != 200:
        _err(f"登录用户名步骤失败: {username_resp.text[:400]}")
        return None

    try:
        password_page_url = str(
            (username_resp.json() or {}).get("continue_url") or ""
        ).strip()
    except Exception:
        password_page_url = ""
    if not password_page_url:
        _err("登录：用户名响应缺少 continue_url")
        return None
    if not password_page_url.startswith("http"):
        password_page_url = (
            f"https://auth.openai.com{password_page_url}"
            if password_page_url.startswith("/")
            else password_page_url
        )

    _, current_url = _follow_redirect_chain(s, password_page_url, proxies)
    if "code=" in current_url and "state=" in current_url:
        return _submit_callback_or_none(current_url, success_msg="OAuth 换 token 成功（授权链已带 callback）")

    try:
        pre_pwd = _session_get_with_tls_retry(
            s,
            current_url,
            proxies=proxies,
            allow_redirects=True,
            timeout=25,
        )
        fu = (getattr(pre_pwd, "url", "") or "").strip()
        if fu:
            current_url = fu
    except UserStoppedError:
        raise
    except Exception as e:
        _warn(f"GET 密码页失败，仍尝试提交密码: {e}")

    if force_passwordless_otp:
        _info("测试模式：跳过 password/verify，直接使用一次性验证码登录")
        otp_login_account = _try_login_via_email_otp_api(
            current_url,
            prefer_passwordless=True,
        )
        if otp_login_account:
            return otp_login_account
        _err("测试模式一次性验证码登录失败")
        return None

    _PWD_REFERS = (
        current_url,
        "https://auth.openai.com/log-in/password",
        "https://auth.openai.com/login/password",
    )

    def _post_password_verify(referer: str, token: Optional[str]) -> Any:
        hdrs: Dict[str, str] = {
            "content-type": "application/json",
            "accept": "application/json",
            "referer": referer,
        }
        if token:
            hdrs["openai-sentinel-token"] = token
        return s.post(
            "https://auth.openai.com/api/accounts/password/verify",
            headers=hdrs,
            data=json.dumps({"password": password}),
            proxies=proxies,
            verify=_ssl_verify(),
            timeout=20,
        )

    password_resp: Any = None

    for ref in _PWD_REFERS:
        _raise_if_stopped()
        st_pwd = _build_sentinel_for_session(s, "password_verify", proxies)
        if not st_pwd:
            break
        password_resp = _post_password_verify(ref, st_pwd)
        _info(f"password/verify HTTP {password_resp.status_code} (Referer …{ref[-32:]})")
        if password_resp.status_code == 200:
            break

    if not password_resp or password_resp.status_code != 200:
        _warn("password/verify 未通过，尝试验证码登录接口")
        otp_login_account = _try_login_via_email_otp_api(current_url)
        if otp_login_account:
            return otp_login_account

        # 该登录链路下 authorize/continue 不接受 password 参数，继续重试只会产生 unknown_parameter 噪音。
        # 已尝试验证码接口后仍失败，按密码登录失败返回，由上层决定补位。
        snippet = (
            (password_resp.text[:500] if password_resp is not None else "")
            or "无响应"
        )
        if mark_bad_email_on_invalid_pwd and "invalid_username_or_password" in snippet.lower():
            _mark_graph_bad_email(email, "invalid_username_or_password")
        _err(f"登录密码步骤失败: {snippet}")
        return None

    try:
        pwd_json = password_resp.json() or {}
    except Exception:
        pwd_json = {}

    next_url = _extract_next_url(pwd_json).strip() or str(
        pwd_json.get("continue_url") or ""
    ).strip()
    if not next_url:
        _err("password/verify 后无下一跳 URL")
        return None
    if not next_url.startswith("http"):
        next_url = (
            f"https://auth.openai.com{next_url}"
            if next_url.startswith("/")
            else next_url
        )

    _, current_url = _follow_redirect_chain(s, next_url, proxies)
    solved, current_url, _ = _handle_add_phone_challenge(
        s,
        current_url=current_url,
        proxies=proxies,
        email=email,
        hint_url=current_url,
        scene="登录流程",
    )
    if not solved:
        return None
    if "code=" in current_url and "state=" in current_url:
        return _submit_callback_or_none(current_url, success_msg="OAuth 换 token 成功")

    if current_url.rstrip("/").endswith(
        "/email-verification"
    ) or "/email-verification" in current_url:
        _info("登录需邮箱 OTP，触发发送")
        otp_resp = _post_with_retry(
            s,
            "https://auth.openai.com/api/accounts/email-otp/send",
            headers={
                "referer": current_url,
                "accept": "application/json",
                "content-type": "application/json",
            },
            json_body={},
            proxies=proxies,
            timeout=30,
            retries=2,
        )
        _info(f"登录 OTP 发送 HTTP {otp_resp.status_code}")
        if otp_resp.status_code != 200:
            _err(f"登录 OTP 发送失败: {otp_resp.text[:300]}")
            return None

        def _resend_login_otp_once() -> bool:
            resend_resp = _post_with_retry(
                s,
                "https://auth.openai.com/api/accounts/email-otp/send",
                headers={
                    "referer": current_url,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                json_body={},
                proxies=proxies,
                timeout=30,
                retries=1,
            )
            _info(f"登录 OTP 重发 HTTP {resend_resp.status_code}")
            if resend_resp.status_code != 200:
                _warn(f"登录 OTP 重发异常: {resend_resp.text[:300]}")
            return resend_resp.status_code == 200

        code = get_oai_code_with_single_resend(
            dev_token,
            email,
            proxies,
            resend_once_cb=_resend_login_otp_once,
            scene="登录 OTP",
        )
        if not code:
            _err("登录流程未收到邮箱验证码")
            return None

        validate_resp = _post_with_retry(
            s,
            "https://auth.openai.com/api/accounts/email-otp/validate",
            headers={
                "referer": current_url,
                "accept": "application/json",
                "content-type": "application/json",
            },
            json_body={"code": code},
            proxies=proxies,
            timeout=30,
            retries=2,
        )
        _info(f"登录 OTP 校验 HTTP {validate_resp.status_code}")
        if validate_resp.status_code != 200:
            _err(f"登录 OTP 校验失败: {validate_resp.text[:400]}")
            return None

        try:
            vj = validate_resp.json() or {}
            otp_next = _extract_next_url(vj).strip() or str(
                vj.get("continue_url") or ""
            ).strip()
        except Exception:
            otp_next = ""
        if otp_next and not otp_next.startswith("http"):
            otp_next = (
                f"https://auth.openai.com{otp_next}"
                if otp_next.startswith("/")
                else otp_next
            )
        if otp_next:
            _info(f"OTP 后继续: {otp_next[:80]}…")
            _, current_url = _follow_redirect_chain(s, otp_next, proxies)
        solved, current_url, _ = _handle_add_phone_challenge(
            s,
            current_url=current_url,
            proxies=proxies,
            email=email,
            hint_url=current_url,
            scene="登录 OTP 后",
        )
        if not solved:
            return None
        if "code=" in current_url and "state=" in current_url:
            return _submit_callback_or_none(current_url, success_msg="OAuth 换 token 成功（登录 OTP 后）")

    solved, current_url, _ = _handle_add_phone_challenge(
        s,
        current_url=current_url,
        proxies=proxies,
        email=email,
        hint_url=current_url,
        scene="登录流程停留",
    )
    if not solved:
        return None

    _info("workspace 选择与最终换 token")
    auth_cookie, auth_claims, workspaces = _session_workspaces(s)
    if not auth_cookie:
        _err("登录后未获取 oai-client-auth-session")
        return None

    workspace_referer = "https://auth.openai.com/sign-in-with-chatgpt/codex/consent"
    if not workspaces:
        _info("会话无 workspace，尝试刷新会话")
        try:
            workspaces, workspace_referer = _refresh_workspace_candidates(
                s,
                proxies,
                hint_url=current_url,
                base_referer=workspace_referer,
            )
        except UserStoppedError:
            raise
        except Exception as e:
            _warn(f"刷新 workspace 会话失败: {e}")

    if not workspaces:
        _, auth_claims, _ = _session_workspaces(s)
        hint = str(current_url or "").strip()
        keys = sorted([str(k) for k in (auth_claims or {}).keys()])
        key_preview = ",".join(keys[:8])
        _warn(
            "workspace 仍为空："
            f"url={hint[:80]}，claims_keys=[{key_preview}]"
        )
        _err("登录流程仍无 workspace")
        return None

    workspace_id = str((workspaces[0] or {}).get("id") or "").strip()
    if not workspace_id:
        _err("无法解析 workspace_id")
        return None

    select_body = f'{{"workspace_id":"{workspace_id}"}}'
    _info("POST workspace/select")
    select_resp = _post_with_retry(
        s,
        "https://auth.openai.com/api/accounts/workspace/select",
        headers={
            "referer": workspace_referer,
            "accept": "application/json",
            "content-type": "application/json",
        },
        data=select_body,
        proxies=proxies,
        timeout=30,
        retries=2,
    )
    if select_resp.status_code != 200:
        _err(
            f"workspace/select 失败 HTTP {select_resp.status_code} — {select_resp.text[:400]}"
        )
        return None

    try:
        select_data = select_resp.json() or {}
    except Exception:
        select_data = {}
    continue_url = _extract_next_url(select_data).strip()
    if not continue_url:
        _err("workspace/select 后无 continue_url")
        return None

    current_url = continue_url
    for _ in range(8):
        _raise_if_stopped()
        final_resp = s.get(
            current_url,
            allow_redirects=False,
            proxies=proxies,
            verify=_ssl_verify(),
            timeout=15,
        )
        location = final_resp.headers.get("Location") or ""
        if final_resp.status_code not in [301, 302, 303, 307, 308]:
            break
        if not location:
            break
        next_url = urllib.parse.urljoin(current_url, location)
        if "code=" in next_url and "state=" in next_url:
            return _submit_callback_or_none(next_url, success_msg="OAuth 换 token 成功")
        current_url = next_url

    _err("登录重定向链未出现带 code 的 callback")
    return None


def _generate_password(length: int = 16) -> str:
    """生成符合 OpenAI 要求的随机强密码（大小写+数字+特殊字符）"""
    upper = random.choices(string.ascii_uppercase, k=2)
    lower = random.choices(string.ascii_lowercase, k=2)
    digits = random.choices(string.digits, k=2)
    specials = random.choices("!@#$%&*", k=2)
    rest_len = length - 8
    pool = string.ascii_letters + string.digits + "!@#$%&*"
    rest = random.choices(pool, k=rest_len)
    chars = upper + lower + digits + specials + rest
    random.shuffle(chars)
    return "".join(chars)


def run(proxy: Optional[str]):
    """
    单次完整注册。返回值：
    - 成功: (OAuth 账号字典, 明文密码)
    - 失败: (None, \"\") 或 (None, password)（已生成密码但后续失败时便于落盘）
    - 注册表单 403: (\"retry_403\", \"\") 由调用方冷却重试
    """
    proxies: Any = None
    if proxy:
        proxies = {"http": proxy, "https": proxy}
    _raise_if_stopped()

    fp = _choose_browser_fingerprint()
    s = requests.Session(proxies=proxies, impersonate=str(fp.get("impersonate") or "safari"))
    _apply_session_fingerprint(s, fp)
    _info(
        "浏览器指纹: "
        f"{fp.get('label', '-')}"
        f" · imp={fp.get('impersonate', '-')}"
        f" · lang={fp.get('accept_language', '-')}"
    )
    test_mode_passwordless = _env_bool("REGISTER_TEST_MODE_PASSWORDLESS", False) or _env_bool(
        "OPENAI_TEST_MODE",
        False,
    )
    if test_mode_passwordless:
        _info("测试模式已开启：注册成功后将执行一次性验证码登录链路")

    def _runtime_meta() -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        try:
            stats = get_hero_sms_runtime_stats()
            spent = float(stats.get("spent_total_usd") or 0.0)
            bal_last = float(stats.get("balance_last_usd") or -1.0)
            out["sms_spent_usd"] = round(max(0.0, spent), 4)
            if bal_last >= 0:
                out["sms_balance_usd"] = round(bal_last, 4)
            out["sms_min_balance_usd"] = round(_hero_sms_min_balance_limit(), 4)
        except Exception:
            pass
        return out

    def _ok(account_obj: Dict[str, Any], password: str = ""):
        meta = _runtime_meta()
        if meta:
            return account_obj, password, meta
        return account_obj, password

    def _fail(password: str = "", code: str = "", message: str = "", extra: Dict[str, Any] | None = None):
        meta: Dict[str, Any] = _runtime_meta()
        if code:
            meta["error_code"] = str(code).strip().lower()
        if message:
            meta["error_message"] = str(message).strip()[:220]
        if email_domain:
            meta["email_domain"] = email_domain
        if isinstance(extra, dict):
            for k, v in extra.items():
                if v is not None:
                    meta[str(k)] = v
        if meta:
            return None, password, meta
        return None, password

    email_domain = ""

    if not _skip_net_check():
        try:
            _raise_if_stopped()
            trace = _session_get_with_tls_retry(
                s,
                "https://cloudflare.com/cdn-cgi/trace",
                proxies=proxies,
                allow_redirects=True,
                timeout=15,
            ).text
            loc_re = re.search(r"^loc=(.+)$", trace, re.MULTILINE)
            loc = loc_re.group(1) if loc_re else None
            _info(f"当前 IP 地区: {loc}")
            oai_loc = None
            try:
                oai_trace = _session_get_with_tls_retry(
                    s,
                    "https://auth.openai.com/cdn-cgi/trace",
                    proxies=proxies,
                    allow_redirects=True,
                    timeout=15,
                ).text
                oai_loc_re = re.search(r"^loc=(.+)$", oai_trace, re.MULTILINE)
                oai_loc = oai_loc_re.group(1) if oai_loc_re else None
                if oai_loc:
                    _info(f"OpenAI 入口地区: {oai_loc}")
            except Exception:
                oai_loc = None

            if loc in ("CN", "HK") or oai_loc in ("CN", "HK"):
                raise RuntimeError("当前出口地区不可用，请更换代理")
            if loc and oai_loc and loc != oai_loc:
                _warn(
                    "地区检测存在差异："
                    f"cloudflare={loc}, openai={oai_loc}，"
                    "后续仍可能触发区域限制"
                )
        except UserStoppedError:
            raise
        except Exception as e:
            _err(f"网络/地区检测失败: {e}")
            return _fail("", "net_check_failed", str(e))

    email, dev_token = get_email_and_token(proxies)
    if not email or not dev_token:
        mb_code, mb_msg = _consume_mailbox_init_error()
        if mb_code:
            return _fail("", mb_code, mb_msg or "临时邮箱或会话获取失败")
        return _fail("", "mailbox_init_failed", "临时邮箱或会话获取失败")
    _raise_if_stopped()
    email_domain = _email_domain(email)
    _info(f"临时邮箱: {email}")
    masked = (dev_token[:8] + "…") if dev_token else ""
    _info(f"邮箱会话 JWT 前缀: {masked}")

    oauth = generate_oauth_url()
    url = oauth.auth_url

    try:
        signup_body = f'{{"username":{{"value":"{email}","kind":"email"}},"screen_hint":"signup"}}'

        def _signup_authorize_continue_once() -> tuple[Any, str, str]:
            seed_resp = _session_get_with_tls_retry(
                s,
                url,
                proxies=proxies,
                allow_redirects=True,
                timeout=25,
            )
            did = s.cookies.get("oai-did")
            _info(f"Device ID: {did}")
            sentinel = _build_sentinel_for_session(s, "authorize_continue", proxies)
            if not sentinel:
                raise RuntimeError("Sentinel token 获取失败")
            seed_url = str(getattr(seed_resp, "url", "") or "").strip()
            referer = (
                seed_url
                if seed_url.startswith("https://auth.openai.com")
                else "https://auth.openai.com/create-account"
            )
            signup_resp_local = s.post(
                "https://auth.openai.com/api/accounts/authorize/continue",
                headers={
                    "referer": referer,
                    "accept": "application/json",
                    "content-type": "application/json",
                    "openai-sentinel-token": sentinel,
                },
                data=signup_body,
                proxies=proxies,
                verify=_ssl_verify(),
                timeout=30,
            )
            return signup_resp_local, str(did or "").strip(), str(sentinel or "")

        signup_resp: Any = None
        signup_status = 0
        sentinel = ""
        for auth_try in range(2):
            signup_resp, _, sentinel = _signup_authorize_continue_once()
            signup_status = int(getattr(signup_resp, "status_code", 0) or 0)
            _info(f"注册表单 authorize/continue HTTP {signup_status}")
            low = str(getattr(signup_resp, "text", "") or "").lower()
            can_retry_invalid_step = (
                auth_try == 0
                and signup_status == 400
                and (
                    "invalid_auth_step" in low
                    or "invalid authorization step" in low
                )
            )
            if can_retry_invalid_step:
                _warn("注册前置步骤无效，重建授权链后重试一次")
                continue
            break

        if signup_status == 403:
            _err("注册表单 403，请稍后重试")
            return "retry_403", ""
        if signup_status != 200:
            _err(f"注册表单失败 HTTP {signup_status}: {signup_resp.text[:400]}")
            provider = normalize_mail_provider(MAIL_SERVICE_PROVIDER)
            low = str(signup_resp.text or "").lower()
            if provider == "graph" and (
                "invalid_auth_step" in low
                or "invalid authorization step" in low
            ):
                _warn("invalid_auth_step 可能为链路/风控抖动，当前账号暂不删除")
            return _fail("", "auth_continue_failed", f"HTTP {signup_status}")

        password = _generate_password()
        register_body = json.dumps({"password": password, "username": email})
        _info(f"已生成密码: {password[:4]}****")

        pwd_resp = s.post(
            "https://auth.openai.com/api/accounts/user/register",
            headers={
                "referer": "https://auth.openai.com/create-account/password",
                "accept": "application/json",
                "content-type": "application/json",
                "openai-sentinel-token": sentinel,
            },
            data=register_body,
            proxies=proxies,
            verify=_ssl_verify(),
        )
        _info(f"user/register HTTP {pwd_resp.status_code}")
        if pwd_resp.status_code != 200:
            _err(f"user/register 失败: {pwd_resp.text[:400]}")
            provider = normalize_mail_provider(MAIL_SERVICE_PROVIDER)
            fail_text = str(pwd_resp.text or "")
            fail_text_low = fail_text.lower()
            if (
                provider == "graph"
                and pwd_resp.status_code == 400
                and "failed to register username" in fail_text_low
            ):
                _mark_graph_registered_email(email, proxies=proxies, remark="已注册")
                _warn("检测到邮箱疑似已注册，尝试直接登录换取 token")
                login_pw_candidates: list[str] = []
                if password:
                    login_pw_candidates.append(password)
                graph_pwd = _graph_password_for_email(email)
                if graph_pwd and graph_pwd not in login_pw_candidates:
                    login_pw_candidates.append(graph_pwd)

                for idx, login_pwd in enumerate(login_pw_candidates, start=1):
                    if not login_pwd:
                        continue
                    if login_pwd != password:
                        _info(f"补救登录密码源 #{idx}: graph_accounts")
                    try:
                        account = _login_via_password_and_finish_oauth(
                            email,
                            login_pwd,
                            dev_token,
                            proxies,
                            mark_bad_email_on_invalid_pwd=False,
                        )
                    except HeroSmsBalanceLowError as e:
                        return _fail(
                            password,
                            "phone_balance_insufficient",
                            str(e or "HeroSMS 余额不足")[:220],
                        )
                    except RegionBlockedError as e:
                        return _fail(
                            password,
                            "region_blocked",
                            str(e or "区域不可用")[:220],
                        )
                    except HeroSmsCountryBlockedError as e:
                        return _fail(
                            password,
                            "phone_country_blocked",
                            str(e or "区域不可用")[:220],
                        )
                    except HeroSmsCodeTimeoutError as e:
                        return _fail(
                            password,
                            "phone_sms_timeout",
                            str(e or "接码超时")[:220],
                        )

                    if account:
                        _mark_graph_bad_email(email, "注册成功后已消费")
                        return _ok(account, login_pwd)

                _warn("该邮箱疑似已注册但登录换 token 失败：保留账号，不删除")
                return _fail(
                    password,
                    "register_password_failed",
                    f"HTTP {pwd_resp.status_code}; existing_account_login_failed",
                )
            return _fail(password, "register_password_failed", f"HTTP {pwd_resp.status_code}")

        try:
            register_json = pwd_resp.json()
            register_continue = register_json.get("continue_url", "")
            register_page = (register_json.get("page") or {}).get("type", "")
            _info(f"注册下一步 page={register_page} url={register_continue[:120]}")
        except Exception:
            register_continue = ""
            register_page = ""
            _warn(f"注册响应非 JSON，原文: {pwd_resp.text[:300]}")
        need_otp = (
            "email-verification" in register_continue
            or "verify" in register_continue
            or "email-otp" in register_continue
            or "otp" in register_continue
        )
        if not need_otp and register_page:
            need_otp = "verification" in register_page or "otp" in register_page

        if need_otp:
            send_otp_url = register_continue or "https://auth.openai.com/api/accounts/email-otp/send"
            _info(f"需要邮箱 OTP，发送接口: {send_otp_url}")
            try:
                send_resp = _post_with_retry(
                    s,
                    send_otp_url,
                    headers={
                        "referer": "https://auth.openai.com/create-account/password",
                        "accept": "application/json",
                        "content-type": "application/json",
                        "openai-sentinel-token": sentinel,
                    },
                    proxies=proxies,
                    timeout=30,
                    retries=2,
                )
                _info(f"OTP 发送 HTTP {send_resp.status_code}")
                if send_resp.status_code != 200:
                    _warn(f"OTP 发送异常: {send_resp.text[:300]}")
            except UserStoppedError:
                raise
            except Exception as e:
                _warn(f"OTP 发送请求异常: {e}")

            def _resend_register_otp_once() -> bool:
                resend_resp = _post_with_retry(
                    s,
                    send_otp_url,
                    headers={
                        "referer": "https://auth.openai.com/create-account/password",
                        "accept": "application/json",
                        "content-type": "application/json",
                        "openai-sentinel-token": sentinel,
                    },
                    proxies=proxies,
                    timeout=30,
                    retries=1,
                )
                _info(f"OTP 重发 HTTP {resend_resp.status_code}")
                if resend_resp.status_code != 200:
                    _warn(f"OTP 重发异常: {resend_resp.text[:300]}")
                return resend_resp.status_code == 200

            code = get_oai_code_with_single_resend(
                dev_token,
                email,
                proxies,
                resend_once_cb=_resend_register_otp_once,
                scene="注册 OTP",
            )
            if not code:
                return _fail(password, "otp_timeout", "未收到验证码")

            _info("校验注册邮箱 OTP")
            code_resp = _post_with_retry(
                s,
                "https://auth.openai.com/api/accounts/email-otp/validate",
                headers={
                    "referer": "https://auth.openai.com/email-verification",
                    "accept": "application/json",
                    "content-type": "application/json",
                    "openai-sentinel-token": sentinel,
                },
                json_body={"code": code},
                proxies=proxies,
                timeout=30,
                retries=2,
            )
            _info(f"OTP 校验 HTTP {code_resp.status_code}")
            if code_resp.status_code != 200:
                _err(f"OTP 校验失败: {code_resp.text[:400]}")
                return _fail(password, "otp_validate_failed", f"HTTP {code_resp.status_code}")
            else:
                try:
                    cu = (code_resp.json() or {}).get("continue_url") or ""
                    if cu:
                        register_continue = cu
                except Exception:
                    pass
        else:
            _info("无需邮箱 OTP，直接进入创建账户前步骤")

        post_wait = _env_float("REGISTER_POST_WAIT_SEC", 1.5, 0.0, 6.0)
        if post_wait > 0:
            if _sleep_interruptible(post_wait):
                raise UserStoppedError("stopped_by_user")
        if register_continue:
            state_url = (
                register_continue
                if register_continue.startswith("http")
                else f"https://auth.openai.com{register_continue}"
            )
            _info("GET continue_url，同步会话状态")
            try:
                _raise_if_stopped()
                s.get(
                    state_url,
                    proxies=proxies,
                    verify=_ssl_verify(),
                    timeout=15,
                )
                continue_wait = _env_float("REGISTER_CONTINUE_WAIT_SEC", 1.0, 0.0, 5.0)
                if continue_wait > 0:
                    if _sleep_interruptible(continue_wait):
                        raise UserStoppedError("stopped_by_user")
            except UserStoppedError:
                raise
            except Exception as e:
                _warn(f"访问 continue_url: {e}")

        create_account_body = '{"name":"Neo","birthdate":"2000-02-20"}'
        _info("POST create_account")
        create_account_resp = _post_with_retry(
            s,
            "https://auth.openai.com/api/accounts/create_account",
            headers={
                "referer": "https://auth.openai.com/about-you",
                "accept": "application/json",
                "content-type": "application/json",
            },
            data=create_account_body,
            proxies=proxies,
            timeout=30,
            retries=2,
        )
        create_account_status = create_account_resp.status_code
        _info(f"create_account HTTP {create_account_status}")

        if create_account_status != 200:
            fail_body = create_account_resp.text or ""
            fail_body_low = fail_body.lower()
            if "registration_disallowed" in fail_body:
                _warn(
                    "registration_disallowed（风控/频控）：建议拉长冷却、换 IP 或减少并发"
                )
            if _is_hero_sms_country_blocked_issue(fail_body_low):
                _warn("检测到地区/国家不受支持（unsupported_country_region_territory）")
                return _fail(
                    password,
                    "region_blocked",
                    str(fail_body or "Country/Region not supported")[:220],
                )
            _err(f"create_account 失败: {fail_body[:500]}")
            if "registration_disallowed" in fail_body and email_domain:
                return (
                    None,
                    password,
                    {
                        "email_domain": email_domain,
                        "error_code": "registration_disallowed",
                    },
                )
            return _fail(password, "create_account_failed", f"HTTP {create_account_status}")

        try:
            create_json = create_account_resp.json() or {}
            create_continue = str(create_json.get("continue_url") or "").strip()
            create_page = str((create_json.get("page") or {}).get("type") or "").strip()
            _info(f"创建账户后 page={create_page} url={create_continue[:120]}")
        except Exception:
            create_continue = ""
            create_page = ""

        if test_mode_passwordless:
            _info("测试模式：尝试一次性验证码登录并完成 OAuth")
            try:
                test_account = _login_via_password_and_finish_oauth(
                    email,
                    password,
                    dev_token,
                    proxies,
                    mark_bad_email_on_invalid_pwd=False,
                    force_passwordless_otp=True,
                )
            except HeroSmsBalanceLowError as e:
                return _fail(
                    password,
                    "phone_balance_insufficient",
                    str(e or "HeroSMS 余额不足")[:220],
                )
            except RegionBlockedError as e:
                return _fail(
                    password,
                    "region_blocked",
                    str(e or "区域不可用")[:220],
                )
            except HeroSmsCountryBlockedError as e:
                return _fail(
                    password,
                    "phone_country_blocked",
                    str(e or "国家受限")[:220],
                )
            except HeroSmsCodeTimeoutError as e:
                return _fail(
                    password,
                    "phone_sms_timeout",
                    str(e or "接码超时")[:220],
                )

            if test_account:
                _mark_graph_bad_email(email, "注册成功后已消费")
                return _ok(test_account, password)
            _err("测试模式一次性验证码链路未成功")
            return _fail(
                password,
                "test_mode_passwordless_failed",
                "测试模式一次性验证码登录失败",
            )

        if _is_add_phone_page(create_page) or _is_add_phone_url(create_continue):
            _info("进入手机号页：优先尝试 HeroSMS 手机验证")
            phone_entry_url = str(create_continue or "https://auth.openai.com/add-phone").strip()
            phone_ok, phone_next, phone_reason = _handle_add_phone_challenge(
                s,
                current_url=phone_entry_url,
                proxies=proxies,
                email=email,
                hint_url=phone_entry_url,
                scene="注册流程",
                mark_bad_email_on_fail=False,
            )
            if phone_ok:
                create_continue = str(phone_next or create_continue or "").strip()
                create_page = ""
                _info("HeroSMS 手机验证通过，继续当前会话")
            else:
                create_continue = str(phone_next or create_continue or phone_entry_url).strip()
                _info("改走邮箱密码登录完成 OAuth")
                try:
                    account = _login_via_password_and_finish_oauth(
                        email, password, dev_token, proxies
                    )
                except HeroSmsBalanceLowError as e:
                    return _fail(
                        password,
                        "phone_balance_insufficient",
                        str(e or "HeroSMS 余额不足")[:220],
                    )
                except RegionBlockedError as e:
                    return _fail(
                        password,
                        "region_blocked",
                        str(e or "区域不可用")[:220],
                    )
                except HeroSmsCountryBlockedError as e:
                    return _fail(
                        password,
                        "phone_country_blocked",
                        str(e or "国家受限")[:220],
                    )
                except HeroSmsCodeTimeoutError as e:
                    return _fail(
                        password,
                        "phone_sms_timeout",
                        str(e or "接码超时")[:220],
                    )
                if account:
                    _mark_graph_bad_email(email, "注册成功后已消费")
                    return _ok(account, password)
                _err("手机号分支下补救登录失败")
                if _is_add_phone_url(create_continue) or _is_add_phone_page(create_page):
                    _mark_graph_bad_email(email, "add_phone_required")
                    return _fail(
                        password,
                        "phone_gate",
                        str(phone_reason or "进入 add-phone，需手机号验证")[:220],
                    )
                return None, password

        workspace_hint_url = ""
        if create_continue:
            workspace_hint_url = (
                create_continue
                if create_continue.startswith("http")
                else f"https://auth.openai.com{create_continue}"
            )
            _info("GET create_account continue_url，同步会话状态")
            try:
                _, follow_url = _follow_redirect_chain(s, workspace_hint_url, proxies)
                if follow_url:
                    workspace_hint_url = follow_url
                if "code=" in follow_url and "state=" in follow_url:
                    try:
                        account = submit_callback_url(
                            callback_url=follow_url,
                            code_verifier=oauth.code_verifier,
                            redirect_uri=oauth.redirect_uri,
                            expected_state=oauth.state,
                        )
                    except Exception as e:
                        msg = str(e)
                        if _is_region_blocked_issue(msg):
                            raise RegionBlockedError(msg)
                        raise
                    _mark_graph_bad_email(email, "注册成功后已消费")
                    return _ok(account, password)
            except UserStoppedError:
                raise
            except RegionBlockedError as e:
                return _fail(password, "region_blocked", str(e)[:220])
            except Exception as e:
                _warn(f"访问 create_account continue_url: {e}")

        auth_cookie, auth_claims, workspaces = _session_workspaces(s)
        if not auth_cookie:
            _err("未获取 oai-client-auth-session")
            return None, password

        workspace_referer = "https://auth.openai.com/sign-in-with-chatgpt/codex/consent"
        if not workspaces:
            _info("Cookie 无 workspace，尝试刷新会话")
            try:
                workspaces, workspace_referer = _refresh_workspace_candidates(
                    s,
                    proxies,
                    hint_url=workspace_hint_url,
                    base_referer=workspace_referer,
                )
            except UserStoppedError:
                raise
            except Exception as e:
                _warn(f"刷新 workspace 会话失败: {e}")
        if not workspaces:
            _, auth_claims, _ = _session_workspaces(s)
            keys = sorted([str(k) for k in (auth_claims or {}).keys()])
            key_preview = ",".join(keys[:8])
            _warn(
                "注册流程 workspace 仍为空："
                f"url={str(workspace_hint_url or '').strip()[:80]}，"
                f"claims_keys=[{key_preview}]"
            )
            _info("仍无 workspace，补救登录")
            try:
                account = _login_via_password_and_finish_oauth(
                    email, password, dev_token, proxies
                )
            except HeroSmsBalanceLowError as e:
                return _fail(
                    password,
                    "phone_balance_insufficient",
                    str(e or "HeroSMS 余额不足")[:220],
                )
            except RegionBlockedError as e:
                return _fail(
                    password,
                    "region_blocked",
                    str(e or "区域不可用")[:220],
                )
            except HeroSmsCountryBlockedError as e:
                return _fail(
                    password,
                    "phone_country_blocked",
                    str(e or "国家受限")[:220],
                )
            except HeroSmsCodeTimeoutError as e:
                return _fail(
                    password,
                    "phone_sms_timeout",
                    str(e or "接码超时")[:220],
                )
            if account:
                _mark_graph_bad_email(email, "注册成功后已消费")
                return _ok(account, password)
            _err("无 workspace 且补救登录失败")
            return None, password
        workspace_id = str((workspaces[0] or {}).get("id") or "").strip()
        if not workspace_id:
            _err("无法解析 workspace_id")
            return None, password

        select_body = f'{{"workspace_id":"{workspace_id}"}}'
        _info("POST workspace/select")
        select_resp = _post_with_retry(
            s,
            "https://auth.openai.com/api/accounts/workspace/select",
            headers={
                "referer": workspace_referer,
                "accept": "application/json",
                "content-type": "application/json",
            },
            data=select_body,
            proxies=proxies,
            timeout=30,
            retries=2,
        )

        if select_resp.status_code != 200:
            _err(
                f"workspace/select 失败 HTTP {select_resp.status_code}: {select_resp.text[:400]}"
            )
            return None, password

        try:
            select_data = select_resp.json() or {}
        except Exception:
            select_data = {}
        continue_url = _extract_next_url(select_data).strip()
        if not continue_url:
            _err("workspace/select 后无 continue_url")
            return None, password

        current_url = continue_url
        for _ in range(6):
            _raise_if_stopped()
            final_resp = s.get(
                current_url,
                allow_redirects=False,
                proxies=proxies,
                verify=_ssl_verify(),
                timeout=15,
            )
            location = final_resp.headers.get("Location") or ""

            if final_resp.status_code not in [301, 302, 303, 307, 308]:
                break
            if not location:
                break

            next_url = urllib.parse.urljoin(current_url, location)
            if "code=" in next_url and "state=" in next_url:
                try:
                    account = submit_callback_url(
                        callback_url=next_url,
                        code_verifier=oauth.code_verifier,
                        redirect_uri=oauth.redirect_uri,
                        expected_state=oauth.state,
                    )
                except Exception as e:
                    msg = str(e)
                    if _is_region_blocked_issue(msg):
                        return _fail(password, "region_blocked", msg[:220])
                    raise
                _mark_graph_bad_email(email, "注册成功后已消费")
                return _ok(account, password)
            current_url = next_url

        _err("重定向链未出现 OAuth callback")
        return None, password

    except UserStoppedError:
        _warn("检测到停止指令，终止当前注册流程")
        return _fail("", "stopped_by_user", "用户停止任务")
    except RegionBlockedError as e:
        return _fail("", "region_blocked", str(e)[:220])
    except HeroSmsBalanceLowError as e:
        return _fail("", "phone_balance_insufficient", str(e)[:220])
    except HeroSmsCountryBlockedError as e:
        return _fail("", "phone_country_blocked", str(e)[:220])
    except HeroSmsCodeTimeoutError as e:
        return _fail("", "phone_sms_timeout", str(e)[:220])
    except Exception as e:
        _err(f"运行异常: {e}")
        emsg = str(e)
        low = emsg.lower()
        is_tls = (
            "ssl" in low
            or "tls" in low
            or "handshake" in low
            or "wrong version number" in low
            or "certificate" in low
        )
        return _fail("", "tls_error" if is_tls else "runtime_exception", emsg)


def main() -> None:
    """命令行入口：循环调用 run()，将成功账号写入 JSON 与 accounts.txt。"""
    parser = argparse.ArgumentParser(description="OpenAI 自动注册脚本")
    parser.add_argument(
        "--proxy", default=None, help="代理地址，如 http://127.0.0.1:7890"
    )
    parser.add_argument("--once", action="store_true", help="只运行一次")
    parser.add_argument("--sleep-min", type=int, default=5, help="循环模式最短等待秒数")
    parser.add_argument(
        "--sleep-max", type=int, default=30, help="循环模式最长等待秒数"
    )
    args = parser.parse_args()

    sleep_min = max(1, args.sleep_min)
    sleep_max = max(sleep_min, args.sleep_max)

    count = 0
    _info("命令行模式启动（Ctrl+C 退出）")

    accounts_file = _init_accounts_file(TOKEN_OUTPUT_DIR)
    _info(f"本轮导出 JSON: {accounts_file}")

    while True:
        count += 1
        _out(
            f"\n[{datetime.now().strftime('%H:%M:%S')}] 第 {count} 次注册",
            flush=True,
        )

        try:
            result = run(args.proxy)
            account_data = None
            password = ""
            meta: Dict[str, Any] = {}
            if isinstance(result, (tuple, list)):
                if len(result) > 0:
                    account_data = result[0]
                if len(result) > 1:
                    password = str(result[1] or "")
                if len(result) > 2 and isinstance(result[2], dict):
                    meta = dict(result[2])

            if account_data == "retry_403":
                _info("注册表单 403，10 秒后重试")
                time.sleep(10)
                continue

            if str(meta.get("error_code") or "").strip().lower() == "graph_pool_exhausted":
                _err("Graph 账号池已耗尽，停止后续注册")
                break
            if str(meta.get("error_code") or "").strip().lower() == "phone_balance_insufficient":
                _err("HeroSMS 余额低于下限，停止后续注册")
                break
            if str(meta.get("error_code") or "").strip().lower() == "phone_country_blocked":
                _err("HeroSMS 国家受限，停止后续注册")
                break
            if str(meta.get("error_code") or "").strip().lower() == "region_blocked":
                _err("OpenAI 区域不可用，停止后续注册")
                break

            if account_data and isinstance(account_data, dict):
                account_email = account_data.get("name", "")

                _append_account_to_file(account_data)
                _info(f"成功，已写入 JSON: {accounts_file}")

                if account_email and password:
                    pwd_file = (
                        os.path.join(TOKEN_OUTPUT_DIR, "accounts.txt")
                        if TOKEN_OUTPUT_DIR
                        else "accounts.txt"
                    )
                    with open(pwd_file, "a", encoding="utf-8") as af:
                        af.write(f"{account_email}----{password}\n")
                    _info(f"账号密码已追加: {pwd_file}")
            else:
                _warn("本次注册未成功")

        except Exception as e:
            _err(f"未捕获异常: {e}")

        if args.once:
            break

        wait_time = random.randint(sleep_min, sleep_max)
        _info(f"冷却 {wait_time}s")
        time.sleep(wait_time)


if __name__ == "__main__":
    main()

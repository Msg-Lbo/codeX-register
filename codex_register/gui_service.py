#!/usr/bin/env python3
"""
CodeX Register Web 控制台（Naive UI）。

职责：
- 提供本地 HTTP 服务，使用 Vue3 + Naive UI 构建 Web UI；
- 默认用 pywebview 打包为独立应用窗口显示（可切换浏览器模式）；
- 读写 gui_config.json，并将核心配置同步到环境变量；
- 在后台线程执行 r_with_pwd.run，实时采集日志；
- 管理 accounts_*.json、accounts.txt 与 local_accounts.db，本地同步与管理端拉取。
"""

from __future__ import annotations

import glob
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from queue import Empty, Queue
from typing import Any

from .gui_config_store import ACCOUNTS_TXT, DEFAULT_CONFIG, load_config, save_config
from .gui_http_utils import (
    _hint_connect_error,
    _http_delete,
    _http_get,
    _http_post_json,
    _merge_http_headers,
    _urlopen_request,
)
from .gui_service_data_ops import (
    accounts_txt_path as _data_accounts_txt_path,
    build_email_source_files_map as _data_build_email_source_files_map,
    build_local_account_index as _data_build_local_account_index,
    delete_local_accounts as _data_delete_local_accounts,
    delete_local_accounts_db_only as _data_delete_local_accounts_db_only,
    delete_json_files as _data_delete_json_files,
    export_codex_accounts as _data_export_codex_accounts,
    export_sub2api_accounts as _data_export_sub2api_accounts,
    email_from_account_entry as _data_email_from_account_entry,
    emails_from_accounts_json as _data_emails_from_accounts_json,
    list_accounts as _data_list_accounts,
    list_json_files as _data_list_json_files,
    save_json_file_note as _data_save_json_file_note,
    source_label as _data_source_label,
    sync_selected_accounts as _data_sync_selected_accounts,
    test_local_accounts_via_cpa as _data_test_local_accounts_via_cpa,
    upsert_local_account_record as _data_upsert_local_account_record,
)
from .gui_service_mail_ops import (
    get_mail_client as _mail_get_mail_client,
    mail_cf_dns_create_batch as _mail_mail_cf_dns_create_batch,
    mail_cf_dns_delete_batch as _mail_mail_cf_dns_delete_batch,
    mail_cf_dns_list as _mail_mail_cf_dns_list,
    mail_cf_dns_update as _mail_mail_cf_dns_update,
    mail_cf_worker_set_mail_domain as _mail_mail_cf_worker_set_mail_domain,
    mail_cf_zones as _mail_mail_cf_zones,
    mail_clear_emails as _mail_mail_clear_emails,
    mail_client_signature as _mail_mail_client_signature,
    mail_content_preview as _mail_mail_content_preview,
    mail_delete_email as _mail_mail_delete_email,
    mail_delete_emails as _mail_mail_delete_emails,
    mail_delete_mailbox as _mail_mail_delete_mailbox,
    mail_delete_mailboxes as _mail_mail_delete_mailboxes,
    mail_delete_graph_account_file as _mail_mail_delete_graph_account_file,
    mail_domain_stats as _mail_mail_domain_stats,
    mail_generate_mailbox as _mail_mail_generate_mailbox,
    mail_get_email_detail as _mail_mail_get_email_detail,
    mail_graph_account_files as _mail_mail_graph_account_files,
    mail_import_graph_account_file as _mail_mail_import_graph_account_file,
    mail_list_emails as _mail_mail_list_emails,
    mail_overview as _mail_mail_overview,
    mail_providers as _mail_mail_providers,
    mail_proxy as _mail_mail_proxy,
    mail_sender_text as _mail_mail_sender_text,
    record_mail_domain_error as _mail_record_mail_domain_error,
    record_mail_domain_registered as _mail_record_mail_domain_registered,
)
from .gui_service_remote_test import (
    batch_test_remote_accounts as _remote_batch_test_remote_accounts,
    consume_test_event_stream as _remote_consume_test_event_stream,
    is_account_deactivated_error as _remote_is_account_deactivated_error,
    is_rate_limited_error as _remote_is_rate_limited_error,
    is_ssl_retryable_error as _remote_is_ssl_retryable_error,
    is_token_invalidated_error as _remote_is_token_invalidated_error,
    refresh_remote_tokens as _remote_refresh_remote_tokens,
    refresh_api_success as _remote_refresh_api_success,
    revive_remote_tokens as _remote_revive_remote_tokens,
    set_remote_test_state as _remote_set_remote_test_state,
    try_refresh_remote_token as _remote_try_refresh_remote_token,
)
from .mail_services import (
    MailServiceError,
    available_mail_providers,
    build_mail_service,
    normalize_mail_provider,
)


_APP_NAME = "CodeX Register"
_APP_AUTHOR = "Msg-Lbo"
_APP_AUTHOR_URL = "https://github.com/Msg-Lbo"
_APP_LICENSE_NAME = "CodeX Register 使用协议（非开源许可）"
_APP_LICENSE_FILE = "LICENSE"
_APP_VERSION_FILE = "VERSION"
_APP_REPO_FILE = "REPOSITORY"
_APP_DEFAULT_REPO_SLUG = "Msg-Lbo/codeX-register"
_APP_REPO_ENV_KEYS = (
    "CODEX_UPDATE_REPO",
    "APP_UPDATE_REPO",
    "GITHUB_REPOSITORY",
)
_APP_INTRO = (
    "CodeX Register 是一套本地 Web 控制台，用于统一管理注册流程、邮箱服务、"
    "SMS 接码、代理切换与账号导入导出。"
)


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

_OPENAI_SMS_BLOCKED_COUNTRY_KEYWORDS = {
    "russia",
    "china",
    "hong kong",
    "macao",
    "macau",
    "belarus",
    "iran",
    "syria",
    "cuba",
    "north korea",
    "democratic people's republic of korea",
}

_COUNTRY_ZH_BY_ENG = {
    "united states": "美国",
    "usa": "美国",
    "usa (virtual)": "美国(虚拟)",
    "united kingdom": "英国",
    "germany": "德国",
    "france": "法国",
    "canada": "加拿大",
    "australia": "澳大利亚",
    "new zealand": "新西兰",
    "japan": "日本",
    "south korea": "韩国",
    "north korea": "朝鲜",
    "china": "中国",
    "hong kong": "中国香港",
    "macao": "中国澳门",
    "taiwan": "中国台湾",
    "singapore": "新加坡",
    "malaysia": "马来西亚",
    "thailand": "泰国",
    "vietnam": "越南",
    "indonesia": "印度尼西亚",
    "philippines": "菲律宾",
    "india": "印度",
    "pakistan": "巴基斯坦",
    "bangladesh": "孟加拉国",
    "sri lanka": "斯里兰卡",
    "nepal": "尼泊尔",
    "myanmar": "缅甸",
    "laos": "老挝",
    "cambodia": "柬埔寨",
    "brunei": "文莱",
    "russia": "俄罗斯",
    "ukraine": "乌克兰",
    "belarus": "白俄罗斯",
    "kazakhstan": "哈萨克斯坦",
    "uzbekistan": "乌兹别克斯坦",
    "kyrgyzstan": "吉尔吉斯斯坦",
    "tajikistan": "塔吉克斯坦",
    "turkmenistan": "土库曼斯坦",
    "mongolia": "蒙古",
    "turkey": "土耳其",
    "georgia": "格鲁吉亚",
    "armenia": "亚美尼亚",
    "azerbaijan": "阿塞拜疆",
    "israel": "以色列",
    "saudi arabia": "沙特阿拉伯",
    "united arab emirates": "阿联酋",
    "qatar": "卡塔尔",
    "kuwait": "科威特",
    "bahrain": "巴林",
    "oman": "阿曼",
    "jordan": "约旦",
    "lebanon": "黎巴嫩",
    "iraq": "伊拉克",
    "iran": "伊朗",
    "yemen": "也门",
    "syria": "叙利亚",
    "egypt": "埃及",
    "morocco": "摩洛哥",
    "algeria": "阿尔及利亚",
    "tunisia": "突尼斯",
    "libya": "利比亚",
    "sudan": "苏丹",
    "south sudan": "南苏丹",
    "ethiopia": "埃塞俄比亚",
    "kenya": "肯尼亚",
    "uganda": "乌干达",
    "tanzania": "坦桑尼亚",
    "nigeria": "尼日利亚",
    "ghana": "加纳",
    "south africa": "南非",
    "zambia": "赞比亚",
    "zimbabwe": "津巴布韦",
    "botswana": "博茨瓦纳",
    "namibia": "纳米比亚",
    "mozambique": "莫桑比克",
    "rwanda": "卢旺达",
    "mauritius": "毛里求斯",
    "mexico": "墨西哥",
    "brazil": "巴西",
    "argentina": "阿根廷",
    "chile": "智利",
    "peru": "秘鲁",
    "colombia": "哥伦比亚",
    "venezuela": "委内瑞拉",
    "ecuador": "厄瓜多尔",
    "bolivia": "玻利维亚",
    "paraguay": "巴拉圭",
    "uruguay": "乌拉圭",
    "panama": "巴拿马",
    "costa rica": "哥斯达黎加",
    "guatemala": "危地马拉",
    "honduras": "洪都拉斯",
    "el salvador": "萨尔瓦多",
    "nicaragua": "尼加拉瓜",
    "dominican republic": "多米尼加",
    "cuba": "古巴",
    "jamaica": "牙买加",
    "haiti": "海地",
    "trinidad and tobago": "特立尼达和多巴哥",
    "ireland": "爱尔兰",
    "netherlands": "荷兰",
    "belgium": "比利时",
    "luxembourg": "卢森堡",
    "switzerland": "瑞士",
    "austria": "奥地利",
    "italy": "意大利",
    "spain": "西班牙",
    "portugal": "葡萄牙",
    "greece": "希腊",
    "poland": "波兰",
    "czech republic": "捷克",
    "czechia": "捷克",
    "slovakia": "斯洛伐克",
    "hungary": "匈牙利",
    "romania": "罗马尼亚",
    "bulgaria": "保加利亚",
    "croatia": "克罗地亚",
    "slovenia": "斯洛文尼亚",
    "serbia": "塞尔维亚",
    "bosnia and herzegovina": "波黑",
    "montenegro": "黑山",
    "albania": "阿尔巴尼亚",
    "north macedonia": "北马其顿",
    "moldova": "摩尔多瓦",
    "lithuania": "立陶宛",
    "latvia": "拉脱维亚",
    "estonia": "爱沙尼亚",
    "denmark": "丹麦",
    "sweden": "瑞典",
    "norway": "挪威",
    "finland": "芬兰",
    "iceland": "冰岛",
    "malta": "马耳他",
    "cyprus": "塞浦路斯",
}


def _normalize_country_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().lower())


def _country_name_zh(eng: str, chn: str = "") -> str:
    raw_chn = str(chn or "").strip()
    if raw_chn and re.search(r"[\u4e00-\u9fff]", raw_chn):
        return raw_chn
    key = _normalize_country_name(eng)
    return str(_COUNTRY_ZH_BY_ENG.get(key) or str(eng or "").strip())


def _is_openai_sms_country_allowed(country_id: int, eng_name: str) -> bool:
    cid = int(country_id)
    if cid in _OPENAI_SMS_BLOCKED_COUNTRY_IDS:
        return False
    key = _normalize_country_name(eng_name)
    if not key:
        return True
    for kw in _OPENAI_SMS_BLOCKED_COUNTRY_KEYWORDS:
        if kw in key:
            return False
    return True

class StdoutCapture:
    """按行把 print 输出交给回调，供后台线程日志上屏。"""

    def __init__(self, cb):
        self._cb = cb
        self._buf = ""

    def write(self, text: str) -> None:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:
                self._cb(line)

    def flush(self) -> None:
        if self._buf:
            self._cb(self._buf)
            self._buf = ""


class RegisterService:
    """应用业务层：配置、运行控制、数据管理、日志缓存。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._log_ctx = threading.local()
        self.cfg: dict[str, Any] = load_config()
        self._running = False
        self._status_text = "就绪"
        self._progress = 0.0
        self._stop = threading.Event()
        self._worker_thread: threading.Thread | None = None

        self._logs: deque[dict[str, Any]] = deque(maxlen=5000)
        self._log_seq = 0

        self._sync_busy = False
        self._remote_busy = False
        self._remote_test_busy = False
        self._remote_rows: list[dict[str, Any]] = []
        self._remote_total = 0
        self._remote_pages = 1
        self._remote_email_counts: dict[str, int] = {}
        self._remote_sync_status_ready = False
        self._remote_test_state: dict[str, dict[str, str]] = {}
        self._local_cpa_test_state: dict[str, dict[str, str]] = self._normalize_local_cpa_test_state(
            self.cfg.get("local_cpa_test_state") or {}
        )
        self.cfg["local_cpa_test_state"] = dict(self._local_cpa_test_state)
        self._remote_test_stats: dict[str, int] = {
            "total": 0,
            "done": 0,
            "ok": 0,
            "fail": 0,
        }
        self._run_stats: dict[str, Any] = {
            "planned_total": 0,
            "success_count": 0,
            "retry_total": 0,
            "success_rate": 100.0,
            "last_retry_reason": "",
            "retry_reasons": {},
            "started_at": 0.0,
            "ended_at": 0.0,
            "elapsed_sec": 0.0,
            "success_cost_total_ms": 0,
            "success_cost_count": 0,
            "avg_success_sec": 0.0,
            "sms_spent_usd": 0.0,
            "sms_balance_usd": -1.0,
            "sms_min_balance_usd": 0.0,
        }
        self._mail_client: Any | None = None
        self._mail_client_sig: tuple[Any, ...] | None = None

        self._apply_to_env()
        self.log("Web 控制台已就绪")

    @staticmethod
    def _to_int(v: Any, default: int, lo: int = 1, hi: int | None = None) -> int:
        try:
            out = int(v)
        except (TypeError, ValueError):
            out = default
        out = max(lo, out)
        if hi is not None:
            out = min(hi, out)
        return out

    @staticmethod
    def _to_float(v: Any, default: float, lo: float = 0.0, hi: float | None = None) -> float:
        try:
            out = float(v)
        except (TypeError, ValueError):
            out = default
        out = max(lo, out)
        if hi is not None:
            out = min(hi, out)
        return out

    @staticmethod
    def _to_bool(v: Any, default: bool) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            sv = v.strip().lower()
            if sv in {"1", "true", "yes", "on"}:
                return True
            if sv in {"0", "false", "no", "off"}:
                return False
        return default

    @staticmethod
    def _normalize_domain_list(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for raw in values:
            d = str(raw or "").strip().lower()
            if not d or "@" in d:
                continue
            if d in seen:
                continue
            seen.add(d)
            out.append(d)
        return out

    @staticmethod
    def _normalize_domain_error_counts(values: Any) -> dict[str, int]:
        if not isinstance(values, dict):
            return {}
        out: dict[str, int] = {}
        for k, v in values.items():
            domain = str(k or "").strip().lower()
            if not domain or "@" in domain:
                continue
            try:
                count = int(v)
            except Exception:
                continue
            if count > 0:
                out[domain] = count
        return out

    @staticmethod
    def _normalize_domain_registered_counts(values: Any) -> dict[str, int]:
        if not isinstance(values, dict):
            return {}
        out: dict[str, int] = {}
        for k, v in values.items():
            domain = str(k or "").strip().lower()
            if not domain or "@" in domain:
                continue
            try:
                count = int(v)
            except Exception:
                continue
            if count > 0:
                out[domain] = count
        return out

    @staticmethod
    def _email_domain(value: str) -> str:
        email = str(value or "").strip().lower()
        if not email or "@" not in email:
            return ""
        return email.split("@", 1)[1].strip().lower()

    @staticmethod
    def _gmail_canonical_identity(value: str) -> str:
        email = str(value or "").strip().lower()
        if not email or "@" not in email:
            return ""
        local, domain = email.split("@", 1)
        local = str(local or "").strip().lower()
        domain = str(domain or "").strip().lower()
        if not local or not domain:
            return ""
        if domain in {"gmail.com", "googlemail.com"}:
            local = local.split("+", 1)[0].replace(".", "")
            domain = "gmail.com"
        return f"{local}@{domain}" if local and domain else ""

    @classmethod
    def _gmail_unique_master_count(cls, values: list[str]) -> int:
        seen: set[str] = set()
        for raw in values or []:
            email = str(raw or "").strip().lower()
            if not email:
                continue
            if "----" in email:
                email = str(email.split("----", 1)[0] or "").strip().lower()
            cid = cls._gmail_canonical_identity(email)
            if cid:
                seen.add(cid)
        return len(seen)

    @staticmethod
    def _normalize_json_file_notes(values: Any) -> dict[str, str]:
        if not isinstance(values, dict):
            return {}
        out: dict[str, str] = {}
        for k, v in values.items():
            name = os.path.basename(str(k or "").strip())
            if not name or not name.startswith("accounts_") or not name.endswith(".json"):
                continue
            note = str(v or "").strip()
            if len(note) > 120:
                note = note[:120]
            if note:
                out[name] = note
        return out

    @staticmethod
    def _normalize_local_cpa_test_state(values: Any) -> dict[str, dict[str, str]]:
        if not isinstance(values, dict):
            return {}
        out: dict[str, dict[str, str]] = {}
        for k, v in values.items():
            email = str(k or "").strip().lower()
            if not email or "@" not in email:
                continue
            if not isinstance(v, dict):
                continue
            status = str(v.get("status") or "未测").strip() or "未测"
            result = str(v.get("result") or "-").strip() or "-"
            at = str(v.get("at") or "-").strip() or "-"
            out[email] = {
                "status": status,
                "result": result,
                "at": at,
            }
        if len(out) > 3000:
            ordered = sorted(
                out.items(),
                key=lambda kv: str((kv[1] or {}).get("at") or ""),
                reverse=True,
            )
            out = dict(ordered[:3000])
        return out

    @staticmethod
    def _normalize_remote_account_provider(raw: Any) -> str:
        val = str(raw or "sub2api").strip().lower()
        if val in {"cliproxyapi", "cliproxy", "cli_proxy_api", "cpa"}:
            return "cliproxyapi"
        return "sub2api"

    @staticmethod
    def _normalize_graph_accounts_mode(raw: Any) -> str:
        val = str(raw or "file").strip().lower()
        if val in {"api", "http", "interface", "openapi", "open_api", "remote"}:
            return "api"
        return "file"

    @staticmethod
    def _extract_remote_item_access_token(item: Any) -> str:
        if not isinstance(item, dict):
            return ""

        containers: list[dict[str, Any]] = [item]
        for k in ("credentials", "auth", "tokens", "extra"):
            sub = item.get(k)
            if isinstance(sub, dict):
                containers.append(sub)

        for box in containers:
            for key in ("access_token", "accessToken"):
                val = str(box.get(key) or "").strip()
                if val:
                    return val

            token_obj = box.get("token")
            if isinstance(token_obj, dict):
                for key in ("access_token", "accessToken"):
                    val = str(token_obj.get(key) or "").strip()
                    if val:
                        return val

            token_text = str(token_obj or "").strip()
            if token_text.startswith("{") and token_text.endswith("}"):
                try:
                    payload = json.loads(token_text)
                except Exception:
                    payload = None
                if isinstance(payload, dict):
                    for key in ("access_token", "accessToken"):
                        val = str(payload.get(key) or "").strip()
                        if val:
                            return val

        return ""

    @staticmethod
    def _extract_email_like_text(raw: Any) -> str:
        text = str(raw or "").strip().lower()
        if not text:
            return ""
        m = re.search(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", text)
        return str(m.group(0)).strip() if m else ""

    @staticmethod
    def _normalize_repo_slug(raw: Any) -> str:
        text = str(raw or "").strip()
        if not text:
            return ""
        if text.startswith("https://github.com/"):
            text = text[len("https://github.com/") :]
        if text.startswith("http://github.com/"):
            text = text[len("http://github.com/") :]
        if text.startswith("git@github.com:"):
            text = text[len("git@github.com:") :]
        text = text.strip().rstrip("/")
        if text.endswith(".git"):
            text = text[:-4]
        parts = [p for p in text.split("/") if p]
        if len(parts) < 2:
            return ""
        return f"{parts[0]}/{parts[1]}"

    @classmethod
    def _detect_repo_slug(cls) -> str:
        for key in _APP_REPO_ENV_KEYS:
            env_val = os.getenv(key, "")
            slug = cls._normalize_repo_slug(env_val)
            if slug:
                return slug

        repo_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), _APP_REPO_FILE),
            os.path.join(os.getcwd(), _APP_REPO_FILE),
        ]
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            repo_candidates.append(os.path.join(exe_dir, _APP_REPO_FILE))
            if getattr(sys, "_MEIPASS", None):
                repo_candidates.append(os.path.join(str(sys._MEIPASS), _APP_REPO_FILE))  # type: ignore[attr-defined]
        except Exception:
            pass

        seen_paths: set[str] = set()
        for rp in repo_candidates:
            p = os.path.abspath(str(rp or ""))
            if not p or p in seen_paths:
                continue
            seen_paths.add(p)
            try:
                if not os.path.isfile(p):
                    continue
                with open(p, "r", encoding="utf-8") as f:
                    raw = str(f.read()).strip()
                slug = cls._normalize_repo_slug(raw)
                if slug:
                    return slug
            except Exception:
                continue

        try:
            raw = subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            raw = ""
        return cls._normalize_repo_slug(raw)

    @staticmethod
    def _read_app_version() -> str:
        env_ver = str(os.getenv("CODEX_REGISTER_VERSION", "") or "").strip()
        if env_ver:
            return env_ver.lstrip("vV")

        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), _APP_VERSION_FILE),
            os.path.join(os.getcwd(), _APP_VERSION_FILE),
        ]
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            candidates.append(os.path.join(exe_dir, _APP_VERSION_FILE))
            if getattr(sys, "_MEIPASS", None):
                candidates.append(os.path.join(str(sys._MEIPASS), _APP_VERSION_FILE))  # type: ignore[attr-defined]
        except Exception:
            pass

        seen_paths: set[str] = set()
        for ver_path in candidates:
            p = os.path.abspath(str(ver_path or ""))
            if not p or p in seen_paths:
                continue
            seen_paths.add(p)
            try:
                if os.path.isfile(p):
                    with open(p, "r", encoding="utf-8") as f:
                        text = str(f.read()).strip()
                    if text:
                        return text.lstrip("vV")
            except Exception:
                continue

        try:
            raw = subprocess.check_output(
                ["git", "describe", "--tags", "--always", "--dirty"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if raw:
                return raw.lstrip("vV")
        except Exception:
            pass
        return "0.0.0-dev"

    @staticmethod
    def _version_tuple(raw: Any) -> tuple[int, ...]:
        text = str(raw or "").strip().lstrip("vV")
        if not text:
            return (0,)
        nums = [
            int(x)
            for x in re.findall(r"\d+", text)
        ]
        if not nums:
            return (0,)
        return tuple(nums)

    @classmethod
    def _is_newer_version(cls, latest: Any, current: Any) -> bool:
        a = list(cls._version_tuple(latest))
        b = list(cls._version_tuple(current))
        n = max(len(a), len(b))
        a.extend([0] * (n - len(a)))
        b.extend([0] * (n - len(b)))
        return tuple(a) > tuple(b)

    @staticmethod
    def _normalize_cliproxy_management_base(raw: Any) -> str:
        base = str(raw or "").strip()
        if not base:
            return ""
        if not base.startswith("http://") and not base.startswith("https://"):
            base = f"http://{base}"
        base = base.rstrip("/")
        marker = "/v0/management"
        low = base.lower()
        idx = low.find(marker)
        if idx >= 0:
            return base[: idx + len(marker)]
        return f"{base}{marker}"

    def _cliproxy_management_context(self) -> tuple[str, str, bool, str | None]:
        raw_base = str(
            self.cfg.get("cliproxy_api_base")
            or self.cfg.get("accounts_list_api_base")
            or ""
        ).strip()
        if not raw_base:
            raise ValueError("请先填写 CLIProxyAPI 管理地址（cliproxy_api_base）")
        base = self._normalize_cliproxy_management_base(raw_base)

        raw_key = str(
            self.cfg.get("cliproxy_management_key")
            or self.cfg.get("accounts_sync_bearer_token")
            or ""
        ).strip()
        if not raw_key:
            raise ValueError("请先填写 CLIProxyAPI 管理密钥（cliproxy_management_key）")
        auth = raw_key if raw_key.lower().startswith("bearer ") else f"Bearer {raw_key}"

        verify_ssl = bool(self.cfg.get("openai_ssl_verify", True))
        proxy_arg = str(self.cfg.get("proxy") or "").strip() or None
        return base, auth, verify_ssl, proxy_arg

    @staticmethod
    def _file_color_index(file_name: str, palette_size: int = 12) -> int:
        name = str(file_name or "").strip().lower()
        if not name:
            return -1
        h = 0
        for ch in name:
            h = (h * 131 + ord(ch)) & 0x7FFFFFFF
        size = max(1, int(palette_size or 1))
        return int(h % size)

    def _calc_run_success_rate_locked(self) -> float:
        planned = max(0, int(self._run_stats.get("planned_total") or 0))
        retry_total = max(0, int(self._run_stats.get("retry_total") or 0))
        if planned <= 0:
            return 100.0
        return round((planned / (planned + retry_total)) * 100.0, 2)

    def _reset_run_stats(self, planned_total: int = 0) -> None:
        now = time.time()
        with self._lock:
            self._run_stats = {
                "planned_total": max(0, int(planned_total or 0)),
                "success_count": 0,
                "retry_total": 0,
                "success_rate": 100.0,
                "last_retry_reason": "",
                "retry_reasons": {},
                "started_at": now,
                "ended_at": 0.0,
                "elapsed_sec": 0.0,
                "success_cost_total_ms": 0,
                "success_cost_count": 0,
                "avg_success_sec": 0.0,
                "sms_spent_usd": 0.0,
                "sms_balance_usd": -1.0,
                "sms_min_balance_usd": 0.0,
            }
            self._run_stats["success_rate"] = self._calc_run_success_rate_locked()

    def _refresh_run_elapsed_locked(self) -> None:
        started = float(self._run_stats.get("started_at") or 0.0)
        ended = float(self._run_stats.get("ended_at") or 0.0)
        if started <= 0:
            self._run_stats["elapsed_sec"] = 0.0
            return
        tail = ended if ended > 0 else time.time()
        self._run_stats["elapsed_sec"] = round(max(0.0, tail - started), 2)

    def _mark_run_finished(self) -> None:
        with self._lock:
            self._run_stats["ended_at"] = time.time()
            self._refresh_run_elapsed_locked()

    def _record_run_success(self, delta: int = 1, duration_ms: int = 0) -> None:
        inc = max(0, int(delta or 0))
        dur = max(0, int(duration_ms or 0))
        if inc <= 0 and dur <= 0:
            return
        with self._lock:
            if inc > 0:
                self._run_stats["success_count"] = max(
                    0,
                    int(self._run_stats.get("success_count") or 0) + inc,
                )
            if dur > 0:
                total_ms = max(0, int(self._run_stats.get("success_cost_total_ms") or 0)) + dur
                cnt = max(0, int(self._run_stats.get("success_cost_count") or 0)) + 1
                self._run_stats["success_cost_total_ms"] = total_ms
                self._run_stats["success_cost_count"] = cnt
                self._run_stats["avg_success_sec"] = round((total_ms / cnt) / 1000.0, 2)

    def _record_run_retry(self, reason: str) -> tuple[int, float]:
        why = str(reason or "").strip() or "未知失败"
        with self._lock:
            retry_total = max(0, int(self._run_stats.get("retry_total") or 0)) + 1
            reasons = dict(self._run_stats.get("retry_reasons") or {})
            reasons[why] = max(0, int(reasons.get(why) or 0)) + 1

            self._run_stats["retry_total"] = retry_total
            self._run_stats["retry_reasons"] = reasons
            self._run_stats["last_retry_reason"] = why
            self._run_stats["success_rate"] = self._calc_run_success_rate_locked()
            rate = float(self._run_stats.get("success_rate") or 0.0)
        return retry_total, rate

    def _record_run_sms_stats_from_meta(self, meta: dict[str, Any]) -> None:
        if not isinstance(meta, dict) or not meta:
            return
        spent_raw = meta.get("sms_spent_usd")
        bal_raw = meta.get("sms_balance_usd")
        min_raw = meta.get("sms_min_balance_usd")

        spent: float | None = None
        bal: float | None = None
        min_bal: float | None = None
        try:
            if spent_raw is not None:
                spent = max(0.0, float(spent_raw))
        except Exception:
            spent = None
        try:
            if bal_raw is not None:
                bal = float(bal_raw)
        except Exception:
            bal = None
        try:
            if min_raw is not None:
                min_bal = max(0.0, float(min_raw))
        except Exception:
            min_bal = None

        if spent is None and bal is None and min_bal is None:
            return

        with self._lock:
            if spent is not None:
                self._run_stats["sms_spent_usd"] = round(
                    max(float(self._run_stats.get("sms_spent_usd") or 0.0), spent),
                    4,
                )
            if bal is not None and bal >= 0:
                self._run_stats["sms_balance_usd"] = round(bal, 4)
            if min_bal is not None:
                self._run_stats["sms_min_balance_usd"] = round(min_bal, 4)

    @staticmethod
    def _top_retry_reasons(reason_counts: dict[str, int], limit: int = 3) -> list[dict[str, Any]]:
        rows = [
            {"reason": str(k), "count": int(v)}
            for k, v in (reason_counts or {}).items()
            if int(v or 0) > 0
        ]
        rows.sort(key=lambda x: (-int(x.get("count") or 0), str(x.get("reason") or "")))
        return rows[: max(1, int(limit or 1))]

    @staticmethod
    def _retry_reason_from_meta(meta: dict[str, Any]) -> str:
        code = str(meta.get("error_code") or "").strip().lower()
        msg = str(meta.get("error_message") or "").strip()
        mapping = {
            "otp_timeout": "未收到验证码(OTP超时)",
            "otp_validate_failed": "验证码校验失败",
            "mailbox_init_failed": "临时邮箱初始化失败",
            "stopped_by_user": "用户手动停止",
            "net_check_failed": "网络地区检测失败",
            "auth_continue_failed": "注册前置接口失败(authorize/continue)",
            "register_password_failed": "密码提交失败(user/register)",
            "create_account_failed": "创建账号失败(create_account)",
            "phone_gate": "手机号验证风控(add-phone)",
            "phone_balance_insufficient": "手机号验证失败(HeroSMS余额不足)",
            "phone_country_blocked": "区域不可用(Country/Region not supported)",
            "region_blocked": "区域不可用(Country/Region not supported)",
            "phone_sms_timeout": "手机号验证码超时(HeroSMS)",
            "registration_disallowed": "registration_disallowed 风控",
            "graph_pool_exhausted": "Microsoft 邮箱账号池已耗尽",
            "test_mode_passwordless_failed": "测试模式一次性验证码链路失败",
            "tls_error": "SSL/TLS 异常",
            "runtime_exception": "运行异常",
        }
        base = mapping.get(code, "")
        if not base and code:
            base = f"接口错误: {code}"
        if base and msg:
            return f"{base}: {msg}"
        if base:
            return base
        if msg:
            return msg
        return ""

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        text = str(msg)
        prefix = str(getattr(self._log_ctx, "prefix", "") or "").strip()
        if prefix and not text.startswith(f"[{prefix}]"):
            text = f"[{prefix}] {text}"
        with self._lock:
            self._log_seq += 1
            line = f"[{ts}] {text}"
            self._logs.append(
                {
                    "id": self._log_seq,
                    "ts": ts,
                    "msg": text,
                    "line": line,
                }
            )

    def clear_logs(self) -> None:
        with self._lock:
            self._logs.clear()
            self._log_seq = 0

    def clear_run_stats(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                raise RuntimeError("任务运行中，无法清空统计")
            self._run_stats = {
                "planned_total": 0,
                "success_count": 0,
                "retry_total": 0,
                "success_rate": 100.0,
                "last_retry_reason": "",
                "retry_reasons": {},
                "started_at": 0.0,
                "ended_at": 0.0,
                "elapsed_sec": 0.0,
                "success_cost_total_ms": 0,
                "success_cost_count": 0,
                "avg_success_sec": 0.0,
                "sms_spent_usd": 0.0,
                "sms_balance_usd": -1.0,
                "sms_min_balance_usd": 0.0,
            }
        self.log("运行统计已清空")
        return self.status()
        self.log("日志已清空")

    def fetch_logs(self, since: int) -> dict[str, Any]:
        with self._lock:
            items = [x for x in self._logs if int(x.get("id", 0)) > since]
            last = self._log_seq
        return {"items": items, "last_id": last}

    def _config_health_locked(self) -> tuple[list[str], list[str]]:
        """返回 (blockers, warnings)。

        - blockers: 启动注册前必须补齐，否则直接拒绝启动
        - warnings: 建议完善项，不阻塞启动
        """
        cfg = dict(self.cfg)
        blockers: list[str] = []
        warnings: list[str] = []

        provider = normalize_mail_provider(cfg.get("mail_service_provider") or "mailfree")
        worker_domain = str(cfg.get("worker_domain") or "").strip()
        cf_temp_base_url = str(cfg.get("cf_temp_base_url") or "").strip()
        mail_domains_raw = str(cfg.get("mail_domains") or "").strip()
        cf_temp_mail_domains_raw = str(cfg.get("cf_temp_mail_domains") or "").strip()
        mail_domains = [
            x
            for x in re.split(r"[\n\r,;\s]+", mail_domains_raw)
            if str(x or "").strip()
        ]
        cf_temp_mail_domains = [
            x
            for x in re.split(r"[\n\r,;\s]+", cf_temp_mail_domains_raw)
            if str(x or "").strip()
        ]
        mail_allow_domains = self._normalize_domain_list(cfg.get("mail_domain_allowlist") or [])
        freemail_user = str(cfg.get("freemail_username") or "").strip()
        freemail_pass = str(cfg.get("freemail_password") or "").strip()
        cf_temp_admin_auth = str(cfg.get("cf_temp_admin_auth") or "").strip()
        cloudmail_api_url = str(cfg.get("cloudmail_api_url") or "").strip()
        cloudmail_admin_email = str(cfg.get("cloudmail_admin_email") or "").strip()
        cloudmail_admin_password = str(cfg.get("cloudmail_admin_password") or "").strip()
        mail_curl_api_base = str(cfg.get("mail_curl_api_base") or "").strip()
        mail_curl_key = str(cfg.get("mail_curl_key") or "").strip()
        luckyous_api_base = str(cfg.get("luckyous_api_base") or "").strip()
        luckyous_api_key = str(cfg.get("luckyous_api_key") or "").strip()
        luckyous_project_code = str(cfg.get("luckyous_project_code") or "").strip()
        graph_accounts_mode = self._normalize_graph_accounts_mode(cfg.get("graph_accounts_mode") or "file")
        graph_file = str(cfg.get("graph_accounts_file") or "").strip()
        graph_api_base_url = str(cfg.get("graph_api_base_url") or "").strip()
        graph_api_token = str(cfg.get("graph_api_token") or "").strip()
        gmail_user = str(cfg.get("gmail_imap_user") or "").strip()
        gmail_pass = str(cfg.get("gmail_imap_pass") or "").strip()
        gmail_aliases_raw = str(cfg.get("gmail_alias_emails") or "").strip()
        gmail_aliases = [
            x
            for x in re.split(r"[\n\r,;\s]+", gmail_aliases_raw)
            if str(x or "").strip()
        ]
        if provider == "cloudflare_temp_email":
            cf_temp_domain = str(cf_temp_base_url or worker_domain).strip()
            effective_cf_domains = cf_temp_mail_domains if cf_temp_mail_domains else mail_domains
            if not cf_temp_domain:
                blockers.append("Cloudflare Temp Email 服务地址未填写（cf_temp_base_url）")
            if not cf_temp_admin_auth:
                blockers.append("Cloudflare Temp Email 管理员口令未填写（cf_temp_admin_auth）")
            if not effective_cf_domains and not mail_allow_domains:
                blockers.append("Cloudflare Temp Email 域名池为空（cf_temp_mail_domains）")
        elif provider == "mailfree":
            if not worker_domain:
                blockers.append("邮箱服务地址未填写（worker_domain）")
            if not freemail_user:
                blockers.append("MailFree 用户名未填写（freemail_username）")
            if not freemail_pass:
                blockers.append("MailFree 密码未填写（freemail_password）")
        elif provider == "cloudmail":
            if not cloudmail_api_url:
                blockers.append("CloudMail API 地址未填写（cloudmail_api_url）")
            if not cloudmail_admin_email:
                blockers.append("CloudMail 管理员邮箱未填写（cloudmail_admin_email）")
            if not cloudmail_admin_password:
                blockers.append("CloudMail 管理员密码未填写（cloudmail_admin_password）")
            if not mail_domains and not mail_allow_domains:
                blockers.append("CloudMail 域名池为空（mail_domains）")
        elif provider == "mail_curl":
            if not mail_curl_api_base:
                blockers.append("Mail-Curl API 地址未填写（mail_curl_api_base）")
            if not mail_curl_key:
                blockers.append("Mail-Curl Key 未填写（mail_curl_key）")
        elif provider == "luckyous":
            if not luckyous_api_base:
                blockers.append("Luckyous API 地址未填写（luckyous_api_base）")
            if not luckyous_api_key:
                blockers.append("Luckyous API Key 未填写（luckyous_api_key）")
            if not luckyous_project_code:
                blockers.append("Luckyous 项目编码未填写（luckyous_project_code）")
        elif provider == "gmail":
            if not gmail_user:
                blockers.append("Gmail IMAP 账号未填写（gmail_imap_user）")
            if not gmail_pass:
                blockers.append("Gmail IMAP 应用专用密码未填写（gmail_imap_pass）")
            if not gmail_aliases:
                warnings.append("Gmail 别名池为空，将默认使用 IMAP 账号自身生成别名")
            else:
                unique_master_count = self._gmail_unique_master_count(gmail_aliases)
                if unique_master_count <= 1:
                    warnings.append(
                        "Gmail 别名池当前仅识别到 1 个唯一主号（点号/+tag/googlemail 视为同源），"
                        "可能持续触发 user_already_exists"
                    )
        elif provider == "graph":
            if graph_accounts_mode == "api":
                if not graph_api_base_url:
                    blockers.append("Graph 接口地址未填写（graph_api_base_url）")
                if not graph_api_token:
                    blockers.append("Graph 接口令牌未填写（graph_api_token）")
            else:
                if not graph_file:
                    blockers.append("Graph 账号文件未选择（graph_accounts_file）")
                else:
                    graph_path = os.path.abspath(os.path.expanduser(graph_file))
                    if not os.path.isfile(graph_path):
                        blockers.append(f"Graph 账号文件不存在：{graph_file}")

        if bool(cfg.get("hero_sms_enabled", False)):
            hero_key = str(cfg.get("hero_sms_api_key") or "").strip()
            hero_country = str(cfg.get("hero_sms_country") or "").strip()
            hero_min_balance = self._to_float(cfg.get("hero_sms_max_price"), 2.0, 0.0, 200.0)
            if not hero_key:
                warnings.append("SMS 已启用但 HeroSMS API Key 为空")
            if not hero_country:
                warnings.append("SMS 已启用但国家未设置（hero_sms_country）")
            if hero_min_balance <= 0:
                warnings.append("SMS 余额下限为 0，可能导致低余额下继续消耗")

        if bool(cfg.get("flclash_enable_switch", False)):
            flc_controller = str(cfg.get("flclash_controller") or "").strip()
            flc_group = str(cfg.get("flclash_group") or "").strip()
            if not flc_controller:
                blockers.append("FlClash 已启用但控制器地址为空（flclash_controller）")
            if not flc_group:
                blockers.append("FlClash 已启用但策略组为空（flclash_group）")

        remote_provider = self._normalize_remote_account_provider(
            cfg.get("remote_account_provider") or "sub2api"
        )
        if remote_provider == "sub2api":
            sync_url = str(cfg.get("accounts_sync_api_url") or "").strip()
            sync_token = str(cfg.get("accounts_sync_bearer_token") or "").strip()
            list_base = str(cfg.get("accounts_list_api_base") or "").strip()
            if not sync_url:
                warnings.append("Sub2API 同步接口为空（accounts_sync_api_url）")
            if not sync_token:
                warnings.append("Sub2API Bearer Token 为空（accounts_sync_bearer_token）")
            if not list_base:
                warnings.append("Sub2API 列表接口为空（accounts_list_api_base）")
        else:
            cliproxy_base = str(
                cfg.get("cliproxy_api_base")
                or cfg.get("accounts_list_api_base")
                or ""
            ).strip()
            cliproxy_key = str(
                cfg.get("cliproxy_management_key")
                or cfg.get("accounts_sync_bearer_token")
                or ""
            ).strip()
            if not cliproxy_base:
                warnings.append("CLIProxyAPI 管理地址为空（cliproxy_api_base）")
            if not cliproxy_key:
                warnings.append("CLIProxyAPI 管理密钥为空（cliproxy_management_key）")

        if self._to_int(cfg.get("concurrency"), 1, 1, 6) > 1 and not bool(
            cfg.get("register_random_fingerprint", True)
        ):
            warnings.append("多并发 + 固定指纹，可能提高 invalid_auth_step/400 概率")

        return blockers, warnings

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._refresh_run_elapsed_locked()
            reasons = dict(self._run_stats.get("retry_reasons") or {})
            sms_min_cfg = self._to_float(self.cfg.get("hero_sms_max_price"), 2.0, 0.0, 200.0)
            blockers, warnings = self._config_health_locked()
            return {
                "running": self._running,
                "status_text": self._status_text,
                "progress": self._progress,
                "sync_busy": self._sync_busy,
                "remote_busy": self._remote_busy,
                "remote_test_busy": self._remote_test_busy,
                "remote_test_total": int(self._remote_test_stats.get("total", 0)),
                "remote_test_done": int(self._remote_test_stats.get("done", 0)),
                "remote_test_ok": int(self._remote_test_stats.get("ok", 0)),
                "remote_test_fail": int(self._remote_test_stats.get("fail", 0)),
                "run_planned_total": int(self._run_stats.get("planned_total", 0)),
                "run_success_count": int(self._run_stats.get("success_count", 0)),
                "run_retry_total": int(self._run_stats.get("retry_total", 0)),
                "run_success_rate": float(self._run_stats.get("success_rate", 100.0)),
                "run_last_retry_reason": str(self._run_stats.get("last_retry_reason") or ""),
                "run_retry_reasons": reasons,
                "run_retry_reasons_top": self._top_retry_reasons(reasons, limit=3),
                "run_elapsed_sec": float(self._run_stats.get("elapsed_sec") or 0.0),
                "run_avg_success_sec": float(self._run_stats.get("avg_success_sec") or 0.0),
                "run_sms_spent_usd": float(self._run_stats.get("sms_spent_usd") or 0.0),
                "run_sms_balance_usd": float(self._run_stats.get("sms_balance_usd") or -1.0),
                "run_sms_min_balance_usd": float(
                    self._run_stats.get("sms_min_balance_usd") or sms_min_cfg
                ),
                "config_blockers": blockers,
                "config_warnings": warnings,
                "config_ready": len(blockers) == 0,
            }

    def get_config(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.cfg)

    def app_about_info(self) -> dict[str, Any]:
        slug = self._detect_repo_slug()
        if not slug:
            slug = _APP_DEFAULT_REPO_SLUG
        version = self._read_app_version()
        repo_url = f"https://github.com/{slug}" if slug else ""
        license_path = os.path.join(os.getcwd(), _APP_LICENSE_FILE)
        license_url = f"{repo_url}/blob/main/{_APP_LICENSE_FILE}" if repo_url else ""
        return {
            "name": _APP_NAME,
            "version": version,
            "author": _APP_AUTHOR,
            "author_url": _APP_AUTHOR_URL,
            "intro": _APP_INTRO,
            "license_name": _APP_LICENSE_NAME,
            "license_file": _APP_LICENSE_FILE,
            "license_exists": os.path.isfile(license_path),
            "license_url": license_url,
            "repo_slug": slug,
            "repo_url": repo_url,
            "platform": sys.platform,
            "python": sys.version.split()[0],
        }

    def app_check_update(self) -> dict[str, Any]:
        about = self.app_about_info()
        slug = str(about.get("repo_slug") or "").strip()
        if not slug:
            raise ValueError("未检测到 GitHub 仓库地址，无法检测更新")

        api_url = f"https://api.github.com/repos/{slug}/releases/latest"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "CodeX-Register-Update-Checker",
        }

        with self._lock:
            verify_ssl = bool(self.cfg.get("openai_ssl_verify", True))
            proxy_arg = str(self.cfg.get("proxy") or "").strip() or None

        code, text = _http_get(
            api_url,
            headers,
            verify_ssl=verify_ssl,
            timeout=30,
            proxy=proxy_arg,
        )
        if code == -1:
            raise RuntimeError(_hint_connect_error(str(text or "请求失败")))
        if not (200 <= code < 300):
            snippet = str(text or "").strip().replace("\n", " ")[:260]
            raise RuntimeError(f"检测更新失败 HTTP {code}: {snippet}")

        try:
            payload = json.loads(text) if str(text or "").strip() else {}
        except Exception as e:
            raise RuntimeError(f"更新接口返回非 JSON: {e}") from e
        if not isinstance(payload, dict):
            raise RuntimeError("更新接口返回结构异常")

        latest_tag = str(payload.get("tag_name") or "").strip()
        latest_name = str(payload.get("name") or latest_tag or "").strip()
        published_at = str(payload.get("published_at") or "").strip()
        html_url = str(payload.get("html_url") or "").strip()
        body = str(payload.get("body") or "").strip()
        if len(body) > 6000:
            body = body[:6000] + "\n..."

        assets: list[dict[str, Any]] = []
        for it in payload.get("assets") or []:
            if not isinstance(it, dict):
                continue
            assets.append(
                {
                    "name": str(it.get("name") or "").strip(),
                    "size": int(it.get("size") or 0),
                    "url": str(it.get("browser_download_url") or "").strip(),
                }
            )

        current_version = str(about.get("version") or "0.0.0-dev")
        has_update = bool(latest_tag) and self._is_newer_version(latest_tag, current_version)

        return {
            "repo_slug": slug,
            "current_version": current_version,
            "latest_tag": latest_tag,
            "latest_name": latest_name,
            "published_at": published_at,
            "release_url": html_url,
            "release_notes": body,
            "assets": assets,
            "has_update": has_update,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def update_config(self, data: dict[str, Any], emit_log: bool = True) -> dict[str, Any]:
        with self._lock:
            cfg = dict(self.cfg)
            old_remote_provider = self._normalize_remote_account_provider(
                self.cfg.get("remote_account_provider") or "sub2api"
            )

        if not isinstance(data, dict):
            data = {}

        if "num_accounts" in data:
            cfg["num_accounts"] = self._to_int(data.get("num_accounts"), cfg.get("num_accounts", 1), 1)
        if "num_files" in data:
            cfg["num_files"] = self._to_int(data.get("num_files"), cfg.get("num_files", 1), 1, 200)
        if "concurrency" in data:
            cfg["concurrency"] = self._to_int(data.get("concurrency"), cfg.get("concurrency", 1), 1, 6)
        if "sleep_min" in data:
            cfg["sleep_min"] = self._to_int(data.get("sleep_min"), cfg.get("sleep_min", 5), 1)
        if "sleep_max" in data:
            cfg["sleep_max"] = self._to_int(data.get("sleep_max"), cfg.get("sleep_max", 30), 1)
        if "retry_403_wait_sec" in data:
            cfg["retry_403_wait_sec"] = self._to_int(
                data.get("retry_403_wait_sec"),
                cfg.get("retry_403_wait_sec", 10),
                3,
                30,
            )
        if "remote_test_concurrency" in data:
            cfg["remote_test_concurrency"] = self._to_int(
                data.get("remote_test_concurrency"),
                cfg.get("remote_test_concurrency", 4),
                1,
                12,
            )
        if "remote_test_ssl_retry" in data:
            cfg["remote_test_ssl_retry"] = self._to_int(
                data.get("remote_test_ssl_retry"),
                cfg.get("remote_test_ssl_retry", 2),
                0,
                5,
            )
        if "remote_revive_concurrency" in data:
            cfg["remote_revive_concurrency"] = self._to_int(
                data.get("remote_revive_concurrency"),
                cfg.get("remote_revive_concurrency", 4),
                1,
                12,
            )
        if "remote_refresh_concurrency" in data:
            cfg["remote_refresh_concurrency"] = self._to_int(
                data.get("remote_refresh_concurrency"),
                cfg.get("remote_refresh_concurrency", 4),
                1,
                12,
            )
        if "mail_delete_concurrency" in data:
            cfg["mail_delete_concurrency"] = self._to_int(
                data.get("mail_delete_concurrency"),
                cfg.get("mail_delete_concurrency", 4),
                1,
                12,
            )
        if "mailbox_random_len" in data:
            cfg["mailbox_random_len"] = self._to_int(
                data.get("mailbox_random_len"),
                cfg.get("mailbox_random_len", 0),
                0,
                32,
            )
        if "gmail_imap_port" in data:
            cfg["gmail_imap_port"] = self._to_int(
                data.get("gmail_imap_port"),
                cfg.get("gmail_imap_port", 993),
                1,
                65535,
            )
        if "gmail_alias_tag_len" in data:
            cfg["gmail_alias_tag_len"] = self._to_int(
                data.get("gmail_alias_tag_len"),
                cfg.get("gmail_alias_tag_len", 8),
                1,
                64,
            )
        if "accounts_list_ssl_retry" in data:
            cfg["accounts_list_ssl_retry"] = self._to_int(
                data.get("accounts_list_ssl_retry"),
                cfg.get("accounts_list_ssl_retry", 3),
                0,
                8,
            )
        if "accounts_list_ssl_retry_wait_sec" in data:
            cfg["accounts_list_ssl_retry_wait_sec"] = self._to_float(
                data.get("accounts_list_ssl_retry_wait_sec"),
                float(cfg.get("accounts_list_ssl_retry_wait_sec", 0.8)),
                0.1,
                5.0,
            )
        if "flclash_delay_timeout_ms" in data:
            cfg["flclash_delay_timeout_ms"] = self._to_int(
                data.get("flclash_delay_timeout_ms"),
                cfg.get("flclash_delay_timeout_ms", 4000),
                500,
                20000,
            )
        if "flclash_delay_max_ms" in data:
            cfg["flclash_delay_max_ms"] = self._to_int(
                data.get("flclash_delay_max_ms"),
                cfg.get("flclash_delay_max_ms", 1800),
                100,
                30000,
            )
        if "flclash_delay_retry" in data:
            cfg["flclash_delay_retry"] = self._to_int(
                data.get("flclash_delay_retry"),
                cfg.get("flclash_delay_retry", 1),
                0,
                5,
            )
        if "flclash_rotate_every" in data:
            cfg["flclash_rotate_every"] = self._to_int(
                data.get("flclash_rotate_every"),
                cfg.get("flclash_rotate_every", 3),
                1,
                200,
            )
        if "hero_sms_max_price" in data:
            cfg["hero_sms_max_price"] = self._to_float(
                data.get("hero_sms_max_price"),
                float(cfg.get("hero_sms_max_price", 2.0)),
                0.0,
                200.0,
            )

        if cfg["sleep_max"] < cfg["sleep_min"]:
            cfg["sleep_max"] = cfg["sleep_min"]

        str_keys = [
            "proxy",
            "mail_service_provider",
            "flclash_controller",
            "flclash_secret",
            "flclash_group",
            "flclash_switch_policy",
            "flclash_delay_test_url",
            "worker_domain",
            "mail_domains",
            "cf_temp_base_url",
            "cf_temp_mail_domains",
            "freemail_username",
            "freemail_password",
            "cf_api_token",
            "cf_account_id",
            "cf_worker_script",
            "cf_worker_mail_domain_binding",
            "cf_dns_target_domain",
            "cf_temp_admin_auth",
            "cloudmail_api_url",
            "cloudmail_admin_email",
            "cloudmail_admin_password",
            "mail_curl_api_base",
            "mail_curl_key",
            "luckyous_api_base",
            "luckyous_api_key",
            "luckyous_project_code",
            "luckyous_email_type",
            "luckyous_domain",
            "luckyous_variant_mode",
            "luckyous_specified_email",
            "graph_accounts_mode",
            "graph_accounts_file",
            "graph_api_base_url",
            "graph_api_token",
            "graph_tenant",
            "graph_fetch_mode",
            "gmail_imap_user",
            "gmail_imap_pass",
            "gmail_alias_emails",
            "gmail_imap_server",
            "mailbox_prefix",
            "hero_sms_api_key",
            "hero_sms_service",
            "hero_sms_country",
            "hero_sms_reuse_phone",
            "hero_sms_auto_pick_country",
            "accounts_sync_api_url",
            "accounts_sync_bearer_token",
            "accounts_list_api_base",
            "remote_account_provider",
            "cliproxy_api_base",
            "cliproxy_management_key",
            "accounts_list_timezone",
            "codex_export_dir",
            "cf_routing_api_token",
            "cf_routing_zone_id",
            "cf_routing_domain",
            "gmail_api_client_id",
            "gmail_api_client_secret",
            "gmail_api_refresh_token",
            "gmail_api_user",
        ]
        for key in str_keys:
            if key in data:
                cfg[key] = str(data.get(key) or "").strip()

        if "openai_ssl_verify" in data:
            cfg["openai_ssl_verify"] = self._to_bool(
                data.get("openai_ssl_verify"),
                bool(cfg.get("openai_ssl_verify", True)),
            )
        if "skip_net_check" in data:
            cfg["skip_net_check"] = self._to_bool(
                data.get("skip_net_check"),
                bool(cfg.get("skip_net_check", False)),
            )
        if "graph_pre_refresh_before_run" in data:
            cfg["graph_pre_refresh_before_run"] = self._to_bool(
                data.get("graph_pre_refresh_before_run"),
                bool(cfg.get("graph_pre_refresh_before_run", True)),
            )
        if "hero_sms_enabled" in data:
            cfg["hero_sms_enabled"] = self._to_bool(
                data.get("hero_sms_enabled"),
                bool(cfg.get("hero_sms_enabled", False)),
            )
        if "hero_sms_reuse_phone" in data:
            cfg["hero_sms_reuse_phone"] = self._to_bool(
                data.get("hero_sms_reuse_phone"),
                bool(cfg.get("hero_sms_reuse_phone", False)),
            )
        if "hero_sms_auto_pick_country" in data:
            cfg["hero_sms_auto_pick_country"] = self._to_bool(
                data.get("hero_sms_auto_pick_country"),
                bool(cfg.get("hero_sms_auto_pick_country", False)),
            )
        if "cf_routing_cleanup" in data:
            cfg["cf_routing_cleanup"] = self._to_bool(
                data.get("cf_routing_cleanup"),
                bool(cfg.get("cf_routing_cleanup", True)),
            )
        if "mailfree_random_domain" in data:
            cfg["mailfree_random_domain"] = self._to_bool(
                data.get("mailfree_random_domain"),
                bool(cfg.get("mailfree_random_domain", True)),
            )
        if "gmail_alias_mix_googlemail" in data:
            cfg["gmail_alias_mix_googlemail"] = self._to_bool(
                data.get("gmail_alias_mix_googlemail"),
                bool(cfg.get("gmail_alias_mix_googlemail", True)),
            )
        if "mailbox_custom_enabled" in data:
            cfg["mailbox_custom_enabled"] = self._to_bool(
                data.get("mailbox_custom_enabled"),
                bool(cfg.get("mailbox_custom_enabled", False)),
            )
        if "register_random_fingerprint" in data:
            cfg["register_random_fingerprint"] = self._to_bool(
                data.get("register_random_fingerprint"),
                bool(cfg.get("register_random_fingerprint", True)),
            )
        if "register_test_mode_passwordless" in data:
            cfg["register_test_mode_passwordless"] = self._to_bool(
                data.get("register_test_mode_passwordless"),
                bool(cfg.get("register_test_mode_passwordless", False)),
            )
        if "mail_domain_allowlist" in data:
            cfg["mail_domain_allowlist"] = self._normalize_domain_list(
                data.get("mail_domain_allowlist")
            )
        if "mail_domain_error_counts" in data:
            cfg["mail_domain_error_counts"] = self._normalize_domain_error_counts(
                data.get("mail_domain_error_counts")
            )
        if "mail_domain_registered_counts" in data:
            cfg["mail_domain_registered_counts"] = self._normalize_domain_registered_counts(
                data.get("mail_domain_registered_counts")
            )
        if "fast_mode" in data:
            cfg["fast_mode"] = self._to_bool(
                data.get("fast_mode"),
                bool(cfg.get("fast_mode", False)),
            )
        if "flclash_enable_switch" in data:
            cfg["flclash_enable_switch"] = self._to_bool(
                data.get("flclash_enable_switch"),
                bool(cfg.get("flclash_enable_switch", False)),
            )
        if "flclash_switch_wait_sec" in data:
            cfg["flclash_switch_wait_sec"] = self._to_float(
                data.get("flclash_switch_wait_sec"),
                float(cfg.get("flclash_switch_wait_sec", 1.2)),
                0.0,
                10.0,
            )

        policy = str(cfg.get("flclash_switch_policy") or "round_robin").strip().lower()
        if policy not in {"round_robin", "random"}:
            policy = "round_robin"
        cfg["flclash_switch_policy"] = policy
        cfg["flclash_rotate_every"] = self._to_int(
            cfg.get("flclash_rotate_every"),
            3,
            1,
            200,
        )

        cfg["mail_service_provider"] = normalize_mail_provider(
            cfg.get("mail_service_provider") or "mailfree"
        )
        cfg["remote_account_provider"] = self._normalize_remote_account_provider(
            cfg.get("remote_account_provider") or "sub2api"
        )
        mail_domains_raw = str(cfg.get("mail_domains") or "").strip()
        if mail_domains_raw:
            cfg["mail_domains"] = ",".join(
                [
                    str(x or "").strip().lower()
                    for x in re.split(r"[\n\r,;\s]+", mail_domains_raw)
                    if str(x or "").strip()
                ]
            )
        else:
            cfg["mail_domains"] = ""
        cf_temp_mail_domains_raw = str(cfg.get("cf_temp_mail_domains") or "").strip()
        if cf_temp_mail_domains_raw:
            cfg["cf_temp_mail_domains"] = ",".join(
                [
                    str(x or "").strip().lower()
                    for x in re.split(r"[\n\r,;\s]+", cf_temp_mail_domains_raw)
                    if str(x or "").strip()
                ]
            )
        else:
            cfg["cf_temp_mail_domains"] = ""
        cfg["cf_worker_script"] = str(cfg.get("cf_worker_script") or "mailfree").strip() or "mailfree"
        cfg["cf_worker_mail_domain_binding"] = (
            str(cfg.get("cf_worker_mail_domain_binding") or "MAIL_DOMAIN").strip() or "MAIL_DOMAIN"
        )
        cfg["cf_dns_target_domain"] = str(cfg.get("cf_dns_target_domain") or "").strip().lower()
        cfg["luckyous_api_base"] = (
            str(cfg.get("luckyous_api_base") or "https://mails.luckyous.com").strip()
            or "https://mails.luckyous.com"
        )
        cfg["luckyous_api_key"] = str(cfg.get("luckyous_api_key") or "").strip()
        cfg["luckyous_project_code"] = str(cfg.get("luckyous_project_code") or "").strip()
        cfg["luckyous_email_type"] = str(cfg.get("luckyous_email_type") or "ms_graph").strip().lower()
        cfg["luckyous_domain"] = str(cfg.get("luckyous_domain") or "").strip().lower()
        cfg["luckyous_variant_mode"] = str(cfg.get("luckyous_variant_mode") or "").strip().lower()
        cfg["luckyous_specified_email"] = str(cfg.get("luckyous_specified_email") or "").strip().lower()
        cfg["graph_accounts_mode"] = self._normalize_graph_accounts_mode(
            cfg.get("graph_accounts_mode") or "file"
        )
        cfg["graph_api_base_url"] = str(cfg.get("graph_api_base_url") or "").strip()
        cfg["graph_api_token"] = str(cfg.get("graph_api_token") or "").strip()
        graph_mode = str(cfg.get("graph_fetch_mode") or "graph_api").strip().lower()
        if graph_mode not in {"graph_api", "imap_xoauth2"}:
            graph_mode = "graph_api"
        cfg["graph_fetch_mode"] = graph_mode
        cfg["gmail_imap_server"] = (
            str(cfg.get("gmail_imap_server") or "imap.gmail.com").strip() or "imap.gmail.com"
        )
        cfg["gmail_imap_port"] = self._to_int(cfg.get("gmail_imap_port"), 993, 1, 65535)
        cfg["gmail_alias_tag_len"] = self._to_int(cfg.get("gmail_alias_tag_len"), 8, 1, 64)
        cfg["gmail_alias_mix_googlemail"] = self._to_bool(
            cfg.get("gmail_alias_mix_googlemail"),
            bool(cfg.get("gmail_alias_mix_googlemail", True)),
        )
        cfg["hero_sms_country"] = str(cfg.get("hero_sms_country") or "US").strip() or "US"
        cfg["mail_domain_allowlist"] = self._normalize_domain_list(
            cfg.get("mail_domain_allowlist") or []
        )
        cfg["mail_domain_error_counts"] = self._normalize_domain_error_counts(
            cfg.get("mail_domain_error_counts") or {}
        )
        cfg["mail_domain_registered_counts"] = self._normalize_domain_registered_counts(
            cfg.get("mail_domain_registered_counts") or {}
        )
        cfg["json_file_notes"] = self._normalize_json_file_notes(
            cfg.get("json_file_notes") or {}
        )
        cfg["local_cpa_test_state"] = self._normalize_local_cpa_test_state(
            cfg.get("local_cpa_test_state") or {}
        )

        cfg["accounts_list_page_size"] = 10

        with self._lock:
            new_remote_provider = self._normalize_remote_account_provider(
                cfg.get("remote_account_provider") or "sub2api"
            )
            if new_remote_provider != old_remote_provider:
                self._remote_rows = []
                self._remote_total = 0
                self._remote_pages = 1
                self._remote_email_counts = {}
                self._remote_sync_status_ready = False
                self._remote_test_state = {}
            self._local_cpa_test_state = self._normalize_local_cpa_test_state(
                cfg.get("local_cpa_test_state") or {}
            )
            cfg["local_cpa_test_state"] = dict(self._local_cpa_test_state)
            self.cfg = cfg
            self._mail_client = None
            self._mail_client_sig = None
            save_config(self.cfg)
            self._apply_to_env()

        if emit_log:
            self.log("配置已保存到 gui_config.json")
        return self.get_config()

    def _set_status(self, text: str) -> None:
        with self._lock:
            self._status_text = text

    def _set_progress(self, val: float) -> None:
        with self._lock:
            self._progress = max(0.0, min(1.0, float(val)))

    def _set_running(self, running: bool) -> None:
        with self._lock:
            self._running = running

    def _wait_or_stop(self, seconds: float) -> bool:
        wait_sec = max(0.0, float(seconds or 0.0))
        if wait_sec <= 0:
            return self._stop.is_set()
        return self._stop.wait(wait_sec)

    def _apply_to_env(self) -> None:
        provider = normalize_mail_provider(self.cfg.get("mail_service_provider") or "mailfree")

        domain = str(self.cfg.get("worker_domain") or "").strip()
        mail_domains = str(self.cfg.get("mail_domains") or "").strip()
        cf_temp_base_url = str(self.cfg.get("cf_temp_base_url") or "").strip()
        cf_temp_mail_domains = str(self.cfg.get("cf_temp_mail_domains") or "").strip()

        if provider == "cloudflare_temp_email":
            if cf_temp_base_url:
                domain = cf_temp_base_url
            if cf_temp_mail_domains:
                mail_domains = cf_temp_mail_domains

        if domain and not domain.startswith("http"):
            domain = f"https://{domain}"
        os.environ["WORKER_DOMAIN"] = domain.rstrip("/")
        os.environ["MAIL_DOMAINS"] = mail_domains
        os.environ["CF_TEMP_BASE_URL"] = cf_temp_base_url
        os.environ["CF_TEMP_MAIL_DOMAINS"] = cf_temp_mail_domains
        os.environ["FREEMAIL_USERNAME"] = str(self.cfg.get("freemail_username") or "")
        os.environ["FREEMAIL_PASSWORD"] = str(self.cfg.get("freemail_password") or "")
        os.environ["CF_API_TOKEN"] = str(self.cfg.get("cf_api_token") or "").strip()
        os.environ["CF_ACCOUNT_ID"] = str(self.cfg.get("cf_account_id") or "").strip()
        os.environ["CF_WORKER_SCRIPT"] = str(self.cfg.get("cf_worker_script") or "mailfree").strip()
        os.environ["CF_WORKER_MAIL_DOMAIN_BINDING"] = (
            str(self.cfg.get("cf_worker_mail_domain_binding") or "MAIL_DOMAIN").strip()
        )
        os.environ["CF_DNS_TARGET_DOMAIN"] = str(self.cfg.get("cf_dns_target_domain") or "").strip()
        os.environ["CF_TEMP_ADMIN_AUTH"] = str(self.cfg.get("cf_temp_admin_auth") or "")
        os.environ["ADMIN_AUTH"] = str(self.cfg.get("cf_temp_admin_auth") or "")
        os.environ["CLOUDMAIL_API_URL"] = str(self.cfg.get("cloudmail_api_url") or "").strip()
        os.environ["CLOUDMAIL_ADMIN_EMAIL"] = str(self.cfg.get("cloudmail_admin_email") or "").strip()
        os.environ["CLOUDMAIL_ADMIN_PASSWORD"] = str(self.cfg.get("cloudmail_admin_password") or "")
        os.environ["MAIL_CURL_API_BASE"] = str(self.cfg.get("mail_curl_api_base") or "").strip()
        os.environ["MAIL_CURL_KEY"] = str(self.cfg.get("mail_curl_key") or "")
        os.environ["LUCKYOUS_API_BASE"] = str(
            self.cfg.get("luckyous_api_base") or "https://mails.luckyous.com"
        ).strip()
        os.environ["LUCKYOUS_API_KEY"] = str(self.cfg.get("luckyous_api_key") or "").strip()
        os.environ["LUCKYOUS_PROJECT_CODE"] = str(self.cfg.get("luckyous_project_code") or "").strip()
        os.environ["LUCKYOUS_EMAIL_TYPE"] = str(self.cfg.get("luckyous_email_type") or "ms_graph").strip().lower()
        os.environ["LUCKYOUS_DOMAIN"] = str(self.cfg.get("luckyous_domain") or "").strip().lower()
        os.environ["LUCKYOUS_VARIANT_MODE"] = str(self.cfg.get("luckyous_variant_mode") or "").strip().lower()
        os.environ["LUCKYOUS_SPECIFIED_EMAIL"] = str(
            self.cfg.get("luckyous_specified_email") or ""
        ).strip().lower()
        os.environ["CF_ROUTING_API_TOKEN"] = str(self.cfg.get("cf_routing_api_token") or "").strip()
        os.environ["CF_ROUTING_ZONE_ID"] = str(self.cfg.get("cf_routing_zone_id") or "").strip()
        os.environ["CF_ROUTING_DOMAIN"] = str(self.cfg.get("cf_routing_domain") or "").strip()
        os.environ["CF_ROUTING_CLEANUP"] = "1" if self.cfg.get("cf_routing_cleanup", True) else "0"
        os.environ["GMAIL_API_CLIENT_ID"] = str(self.cfg.get("gmail_api_client_id") or "").strip()
        os.environ["GMAIL_API_CLIENT_SECRET"] = str(self.cfg.get("gmail_api_client_secret") or "").strip()
        os.environ["GMAIL_API_REFRESH_TOKEN"] = str(self.cfg.get("gmail_api_refresh_token") or "").strip()
        os.environ["GMAIL_API_USER"] = str(self.cfg.get("gmail_api_user") or "").strip()
        os.environ["MAIL_SERVICE_PROVIDER"] = normalize_mail_provider(
            self.cfg.get("mail_service_provider") or "mailfree"
        )
        os.environ["REMOTE_ACCOUNT_PROVIDER"] = self._normalize_remote_account_provider(
            self.cfg.get("remote_account_provider") or "sub2api"
        )
        os.environ["CLIPROXY_API_BASE"] = self._normalize_cliproxy_management_base(
            self.cfg.get("cliproxy_api_base") or ""
        )
        os.environ["CLIPROXY_MANAGEMENT_KEY"] = str(self.cfg.get("cliproxy_management_key") or "")
        os.environ["GRAPH_ACCOUNTS_FILE"] = str(self.cfg.get("graph_accounts_file") or "").strip()
        os.environ["GRAPH_ACCOUNTS_MODE"] = self._normalize_graph_accounts_mode(
            self.cfg.get("graph_accounts_mode") or "file"
        )
        os.environ["GRAPH_API_BASE_URL"] = str(self.cfg.get("graph_api_base_url") or "").strip()
        os.environ["GRAPH_API_TOKEN"] = str(self.cfg.get("graph_api_token") or "").strip()
        os.environ["GRAPH_API_URL"] = os.environ["GRAPH_API_BASE_URL"]
        os.environ["MAIL_API_TOKEN"] = os.environ["GRAPH_API_TOKEN"]
        os.environ["GRAPH_TENANT"] = str(self.cfg.get("graph_tenant") or "common").strip()
        os.environ["GRAPH_FETCH_MODE"] = str(self.cfg.get("graph_fetch_mode") or "graph_api").strip()
        os.environ["GMAIL_IMAP_USER"] = str(self.cfg.get("gmail_imap_user") or "").strip()
        os.environ["GMAIL_IMAP_PASS"] = str(self.cfg.get("gmail_imap_pass") or "")
        os.environ["GMAIL_ALIAS_EMAILS"] = str(self.cfg.get("gmail_alias_emails") or "").strip()
        os.environ["GMAIL_IMAP_SERVER"] = (
            str(self.cfg.get("gmail_imap_server") or "imap.gmail.com").strip() or "imap.gmail.com"
        )
        os.environ["GMAIL_IMAP_PORT"] = str(
            self._to_int(self.cfg.get("gmail_imap_port"), 993, 1, 65535)
        )
        os.environ["GMAIL_ALIAS_TAG_LEN"] = str(
            self._to_int(self.cfg.get("gmail_alias_tag_len"), 8, 1, 64)
        )
        os.environ["GMAIL_ALIAS_MIX_GOOGLEMAIL"] = (
            "1" if bool(self.cfg.get("gmail_alias_mix_googlemail", True)) else "0"
        )
        os.environ["HERO_SMS_ENABLED"] = "1" if self.cfg.get("hero_sms_enabled") else "0"
        os.environ["HERO_SMS_REUSE_PHONE"] = "1" if self.cfg.get("hero_sms_reuse_phone") else "0"
        os.environ["HERO_SMS_API_KEY"] = str(self.cfg.get("hero_sms_api_key") or "").strip()
        os.environ["HERO_SMS_SERVICE"] = str(self.cfg.get("hero_sms_service") or "").strip()
        os.environ["HERO_SMS_COUNTRY"] = str(self.cfg.get("hero_sms_country") or "US").strip() or "US"
        os.environ["HERO_SMS_AUTO_PICK_COUNTRY"] = (
            "1" if self.cfg.get("hero_sms_auto_pick_country") else "0"
        )
        hero_sms_min_balance = self._to_float(self.cfg.get("hero_sms_max_price"), 2.0, 0.0, 200.0)
        os.environ["HERO_SMS_MIN_BALANCE"] = str(hero_sms_min_balance)
        # 兼容旧键名：仍保留 HERO_SMS_MAX_PRICE，实际语义为余额下限。
        os.environ["HERO_SMS_MAX_PRICE"] = str(hero_sms_min_balance)
        os.environ["OPENAI_SSL_VERIFY"] = "1" if self.cfg.get("openai_ssl_verify") else "0"
        os.environ["SKIP_NET_CHECK"] = "1" if self.cfg.get("skip_net_check") else "0"
        os.environ["MAILFREE_RANDOM_DOMAIN"] = "1" if self.cfg.get("mailfree_random_domain", True) else "0"
        os.environ["REGISTER_RANDOM_FINGERPRINT"] = "1" if self.cfg.get("register_random_fingerprint", True) else "0"
        os.environ["REGISTER_TEST_MODE_PASSWORDLESS"] = (
            "1" if self.cfg.get("register_test_mode_passwordless", False) else "0"
        )
        os.environ["OPENAI_TEST_MODE"] = os.environ["REGISTER_TEST_MODE_PASSWORDLESS"]
        mailbox_custom_enabled = bool(self.cfg.get("mailbox_custom_enabled", False))
        os.environ["MAILBOX_CUSTOM_ENABLED"] = "1" if mailbox_custom_enabled else "0"
        os.environ["MAILBOX_PREFIX"] = (
            str(self.cfg.get("mailbox_prefix") or "")
            if mailbox_custom_enabled
            else ""
        )
        os.environ["MAILBOX_RANDOM_LENGTH"] = str(
            self._to_int(self.cfg.get("mailbox_random_len"), 0, 0, 32)
            if mailbox_custom_enabled
            else 0
        )
        os.environ["MAIL_ALLOWED_DOMAINS"] = json.dumps(
            self._normalize_domain_list(self.cfg.get("mail_domain_allowlist") or []),
            ensure_ascii=False,
        )

        speed_env_keys = [
            "OTP_POLL_INTERVAL_SEC",
            "OTP_POLL_MAX_ROUNDS",
            "HTTP_RETRY_BACKOFF_BASE_SEC",
            "TLS_RETRY_BASE_SEC",
            "TLS_RETRY_STEP_SEC",
            "SENTINEL_RETRY_BASE_SEC",
            "SENTINEL_RETRY_STEP_SEC",
            "REGISTER_POST_WAIT_SEC",
            "REGISTER_CONTINUE_WAIT_SEC",
            "REGISTER_WORKSPACE_WAIT_SEC",
            "REGISTER_WORKSPACE_REFRESH_ROUNDS",
        ]
        if self.cfg.get("fast_mode"):
            os.environ["OTP_POLL_INTERVAL_SEC"] = "1"
            os.environ["OTP_POLL_MAX_ROUNDS"] = "70"
            os.environ["HTTP_RETRY_BACKOFF_BASE_SEC"] = "0.9"
            os.environ["TLS_RETRY_BASE_SEC"] = "0.6"
            os.environ["TLS_RETRY_STEP_SEC"] = "0.45"
            os.environ["SENTINEL_RETRY_BASE_SEC"] = "0.6"
            os.environ["SENTINEL_RETRY_STEP_SEC"] = "0.45"
            os.environ["REGISTER_POST_WAIT_SEC"] = "0.4"
            os.environ["REGISTER_CONTINUE_WAIT_SEC"] = "0.3"
            os.environ["REGISTER_WORKSPACE_WAIT_SEC"] = "0.6"
            os.environ["REGISTER_WORKSPACE_REFRESH_ROUNDS"] = "4"
        else:
            for key in speed_env_keys:
                os.environ.pop(key, None)

    @staticmethod
    def _normalize_flclash_controller(raw: str) -> str:
        url = str(raw or "").strip()
        if not url:
            return ""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"http://{url}"
        return url.rstrip("/")

    @staticmethod
    def _is_hk_node_name(name: str) -> bool:
        s = str(name or "").strip()
        if not s:
            return False

        if "🇭🇰" in s or "香港" in s or "港区" in s:
            return True

        low = s.lower()
        normalized = (
            low.replace("-", " ")
            .replace("_", " ")
            .replace("|", " ")
            .replace("/", " ")
            .replace("(", " ")
            .replace(")", " ")
        )
        compact = re.sub(r"[\s_\-|/()\[\]{}]+", "", low)

        if "hongkong" in compact or "hong kong" in normalized:
            return True
        if re.search(r"(^|[^a-z0-9])hkg([^a-z0-9]|$)", normalized):
            return True
        if re.search(r"(^|[^a-z0-9])hk\d*([^a-z0-9]|$)", normalized):
            return True
        # 兼容无分隔写法：hk01 / hk1 / hk02-us
        if re.search(r"(^|[^a-z0-9])hk\d+", low):
            return True
        return False

    @staticmethod
    def _flclash_request_json(
        controller: str,
        *,
        method: str,
        path: str,
        secret: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 15,
    ) -> dict[str, Any]:
        url = f"{controller}{path}"
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = int(resp.getcode() or 0)
                text = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"HTTP {e.code}: {(text or '')[:220]}") from e
        except Exception as e:
            raise RuntimeError(str(e)) from e
        if not (200 <= code < 300):
            raise RuntimeError(f"HTTP {code}: {(text or '')[:220]}")
        if not text.strip():
            return {}
        try:
            data = json.loads(text)
        except Exception:
            return {}
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def _parse_cf_trace(text: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for raw in str(text or "").splitlines():
            line = raw.strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = str(k or "").strip().lower()
            if not key:
                continue
            out[key] = str(v or "").strip()
        return out

    def probe_flclash_nodes(
        self,
        *,
        rounds: Any = 1,
        per_round_limit: Any = 0,
    ) -> dict[str, Any]:
        with self._lock:
            if self._running:
                raise RuntimeError("任务运行中，请先停止后再测试节点")

        controller = self._normalize_flclash_controller(
            str(self.cfg.get("flclash_controller") or "")
        )
        if not controller:
            raise ValueError("请先填写 FlClash 控制器")

        secret = str(self.cfg.get("flclash_secret") or "").strip()
        preferred_group = str(self.cfg.get("flclash_group") or "PROXY").strip()
        verify_ssl = bool(self.cfg.get("openai_ssl_verify", True))
        proxy_arg = str(self.cfg.get("proxy") or "").strip() or None
        switch_wait = self._to_float(self.cfg.get("flclash_switch_wait_sec"), 1.2, 0.0, 10.0)
        rounds_num = self._to_int(rounds, 1, 1, 5)
        per_round_limit_num = self._to_int(per_round_limit, 0, 0, 200)

        data = self._flclash_request_json(
            controller,
            method="GET",
            path="/proxies",
            secret=secret,
            timeout=20,
        )
        proxies = data.get("proxies") if isinstance(data, dict) else None
        if not isinstance(proxies, dict):
            raise RuntimeError("/proxies 返回格式异常")

        def _proxy_type(obj: Any) -> str:
            if isinstance(obj, dict):
                return str(obj.get("type") or "").strip().lower()
            return ""

        preferred = [preferred_group, "节点选择", "PROXY", "GLOBAL"]
        selector_candidates: list[tuple[str, dict[str, Any]]] = []
        for key, val in proxies.items():
            if not isinstance(val, dict):
                continue
            all_nodes = val.get("all")
            if not isinstance(all_nodes, list) or not all_nodes:
                continue
            if _proxy_type(val) in {"selector", "select"}:
                selector_candidates.append((str(key), val))

        group_key = ""
        group_obj: dict[str, Any] | None = None
        for name in preferred:
            if not name:
                continue
            obj = proxies.get(name)
            if (
                isinstance(obj, dict)
                and isinstance(obj.get("all"), list)
                and obj.get("all")
                and _proxy_type(obj) in {"selector", "select"}
            ):
                group_key = str(name)
                group_obj = obj
                break
        if group_obj is None and selector_candidates:
            group_key, group_obj = selector_candidates[0]
        if group_obj is None:
            raise RuntimeError("未找到可切换的 Selector 代理组，请在设置中指定节点组名")

        raw_nodes = [str(x).strip() for x in (group_obj.get("all") or []) if str(x).strip()]
        nodes: list[str] = []
        blocked_hk: list[str] = []
        strategy_skipped: list[str] = []
        for node in raw_nodes:
            low = node.lower()
            if low in {"direct", "reject", "pass"}:
                continue
            if self._is_hk_node_name(node):
                blocked_hk.append(node)
                continue
            node_obj = proxies.get(node)
            node_type = _proxy_type(node_obj)
            if node_type in {"urltest", "fallback", "loadbalance", "relay"}:
                strategy_skipped.append(node)
                continue
            if node not in nodes:
                nodes.append(node)

        if not nodes:
            if blocked_hk:
                raise RuntimeError("可用节点均为香港节点，已按规则跳过")
            if strategy_skipped:
                raise RuntimeError("候选均为自动策略组(URLTest/Fallback)，请改用具体节点组")
            raise RuntimeError("代理组没有可用节点")

        current = str(group_obj.get("now") or "").strip()
        group_path = urllib.parse.quote(group_key, safe="")

        def _build_round_order(now_node: str) -> list[str]:
            if not nodes:
                return []
            if now_node in nodes:
                idx = nodes.index(now_node)
                return [nodes[(idx + i + 1) % len(nodes)] for i in range(len(nodes))]
            return list(nodes)

        def _switch_to(node_name: str) -> str:
            self._flclash_request_json(
                controller,
                method="PUT",
                path=f"/proxies/{group_path}",
                secret=secret,
                payload={"name": node_name},
                timeout=20,
            )
            verify = self._flclash_request_json(
                controller,
                method="GET",
                path=f"/proxies/{group_path}",
                secret=secret,
                timeout=20,
            )
            now_name = str(verify.get("now") or "").strip()
            return now_name or node_name

        def _probe_cf_trace() -> dict[str, str]:
            code, text = _http_get(
                "https://cloudflare.com/cdn-cgi/trace",
                {"Accept": "text/plain"},
                verify_ssl=verify_ssl,
                timeout=25,
                proxy=proxy_arg,
            )
            if not (200 <= code < 300):
                snippet = (text or "")[:220].replace("\n", " ")
                raise RuntimeError(f"CF Trace HTTP {code}: {snippet}")
            trace = self._parse_cf_trace(text)
            if not trace.get("ip") and not trace.get("loc"):
                raise RuntimeError("CF Trace 响应缺少 ip/loc")
            return trace

        planned_per_round = len(nodes)
        if per_round_limit_num > 0:
            planned_per_round = min(planned_per_round, per_round_limit_num)

        items: list[dict[str, Any]] = []
        ok = 0
        fail = 0
        seq = 0
        current_now = current

        self.log(
            f"[FlClash 节点测试] 开始：group={group_key}，候选 {len(nodes)} 个，"
            f"轮数 {rounds_num}，每轮 {planned_per_round} 个"
        )
        if blocked_hk:
            self.log(
                f"[FlClash 节点测试] 已跳过香港节点 {len(blocked_hk)} 个"
            )

        for round_idx in range(1, rounds_num + 1):
            order = _build_round_order(current_now)
            if per_round_limit_num > 0:
                order = order[:per_round_limit_num]

            for node_name in order:
                seq += 1
                row = {
                    "key": f"{round_idx}-{seq}",
                    "round": round_idx,
                    "seq": seq,
                    "node": node_name,
                    "active": "",
                    "ip": "",
                    "loc": "",
                    "colo": "",
                    "warp": "",
                    "success": False,
                    "detail": "",
                    "tested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                try:
                    active_name = _switch_to(node_name)
                    row["active"] = active_name
                    if switch_wait > 0:
                        time.sleep(switch_wait)

                    trace = _probe_cf_trace()
                    row["ip"] = str(trace.get("ip") or "")
                    row["loc"] = str(trace.get("loc") or "")
                    row["colo"] = str(trace.get("colo") or "")
                    row["warp"] = str(trace.get("warp") or "")
                    if active_name and active_name != node_name:
                        row["detail"] = f"请求切换 {node_name}，实际 {active_name}"
                    else:
                        row["detail"] = "测试成功"
                    row["success"] = True
                    ok += 1
                    current_now = active_name or node_name
                    self.log(
                        f"[FlClash 节点测试] R{round_idx} #{seq} {node_name} -> "
                        f"{row['loc'] or '-'} {row['ip'] or '-'}"
                    )
                except Exception as e:
                    fail += 1
                    row["detail"] = str(e)
                    self.log(
                        f"[FlClash 节点测试] R{round_idx} #{seq} {node_name} 失败: {e}"
                    )

                items.append(row)

        restored = False
        restore_error = ""
        restore_target = current
        if restore_target:
            try:
                restored_now = _switch_to(restore_target)
                restored = True
                self.log(f"[FlClash 节点测试] 已恢复原节点: {restored_now or restore_target}")
            except Exception as e:
                restore_error = str(e)
                self.log(f"[FlClash 节点测试] 恢复原节点失败: {e}")

        self.log(f"[FlClash 节点测试] 完成：成功 {ok}，失败 {fail}")

        return {
            "controller": controller,
            "group": group_key,
            "rounds": rounds_num,
            "per_round_limit": per_round_limit_num,
            "candidate_total": len(nodes),
            "planned_per_round": planned_per_round,
            "attempts": len(items),
            "ok": ok,
            "fail": fail,
            "blocked_hk_count": len(blocked_hk),
            "blocked_hk_sample": blocked_hk[:8],
            "strategy_skipped_count": len(strategy_skipped),
            "restored": restored,
            "restore_target": restore_target,
            "restore_error": restore_error,
            "items": items,
        }

    def _mail_proxy(self) -> dict[str, str] | None:
        return _mail_mail_proxy(self)

    def _mail_client_signature(self) -> tuple[Any, ...]:
        return _mail_mail_client_signature(self)

    def _get_mail_client(self):
        return _mail_get_mail_client(self)

    @staticmethod
    def _mail_content_preview(text: str, limit: int = 200) -> str:
        return _mail_mail_content_preview(text, limit=limit)

    @staticmethod
    def _mail_sender_text(raw_sender: Any) -> str:
        return _mail_mail_sender_text(raw_sender)

    def _record_mail_domain_error(self, domain: str) -> int:
        return _mail_record_mail_domain_error(self, domain)

    def _record_mail_domain_registered(self, domain: str) -> int:
        return _mail_record_mail_domain_registered(self, domain)

    def mail_domain_stats(self) -> dict[str, Any]:
        return _mail_mail_domain_stats(self)

    def mail_cf_zones(self) -> dict[str, Any]:
        return _mail_mail_cf_zones(self)

    def mail_cf_dns_list(self, zone_id: str) -> dict[str, Any]:
        return _mail_mail_cf_dns_list(self, zone_id)

    def mail_cf_dns_create_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _mail_mail_cf_dns_create_batch(self, payload)

    def mail_cf_dns_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _mail_mail_cf_dns_update(self, payload)

    def mail_cf_dns_delete_batch(self, zone_id: str, record_ids: list[Any]) -> dict[str, Any]:
        return _mail_mail_cf_dns_delete_batch(self, zone_id, record_ids)

    def mail_cf_worker_set_mail_domain(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _mail_mail_cf_worker_set_mail_domain(self, payload)

    def mail_providers(self) -> dict[str, Any]:
        return _mail_mail_providers(self)

    def mail_overview(self, limit: Any = 120, offset: Any = 0) -> dict[str, Any]:
        return _mail_mail_overview(self, limit=limit, offset=offset)

    def mail_graph_account_files(self) -> dict[str, Any]:
        return _mail_mail_graph_account_files(self)

    def mail_import_graph_account_file(self, filename: str, content: str) -> dict[str, Any]:
        return _mail_mail_import_graph_account_file(self, filename, content)

    def mail_delete_graph_account_file(self, filename: str) -> dict[str, Any]:
        return _mail_mail_delete_graph_account_file(self, filename)

    def mail_generate_mailbox(self) -> dict[str, Any]:
        return _mail_mail_generate_mailbox(self)

    def mail_list_emails(self, mailbox: str) -> dict[str, Any]:
        return _mail_mail_list_emails(self, mailbox)

    def mail_get_email_detail(self, email_id: str) -> dict[str, Any]:
        return _mail_mail_get_email_detail(self, email_id)

    def mail_delete_email(self, email_id: str) -> dict[str, Any]:
        return _mail_mail_delete_email(self, email_id)

    def mail_delete_emails(self, ids: list[Any]) -> dict[str, Any]:
        return _mail_mail_delete_emails(self, ids)

    def mail_clear_emails(self, mailbox: str) -> dict[str, Any]:
        return _mail_mail_clear_emails(self, mailbox)

    def mail_delete_mailbox(self, address: str) -> dict[str, Any]:
        return _mail_mail_delete_mailbox(self, address)

    def mail_delete_mailboxes(self, addresses: list[Any]) -> dict[str, Any]:
        return _mail_mail_delete_mailboxes(self, addresses)

    def sms_overview(self, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            enabled = bool(self.cfg.get("hero_sms_enabled", False))
            reuse_phone = bool(self.cfg.get("hero_sms_reuse_phone", False))
            api_key = str(self.cfg.get("hero_sms_api_key") or "").strip()
            service_code = str(self.cfg.get("hero_sms_service") or "").strip()
            country = str(self.cfg.get("hero_sms_country") or "US").strip() or "US"
            min_balance = self._to_float(self.cfg.get("hero_sms_max_price"), 2.0, 0.0, 200.0)
            proxy = str(self.cfg.get("proxy") or "").strip() or ""

        data: dict[str, Any] = {
            "enabled": enabled,
            "reuse_phone": reuse_phone,
            "key_configured": bool(api_key),
            "service": service_code,
            "country": country,
            "min_balance_usd": round(float(min_balance), 4),
            "balance_usd": -1.0,
            "balance_error": "",
            "spent_usd": 0.0,
            "updated_at": "",
            "service_resolved": "",
            "country_resolved": -1,
        }

        try:
            from . import r_with_pwd  # type: ignore

            stats_fn = getattr(r_with_pwd, "get_hero_sms_runtime_stats", None)
            if callable(stats_fn):
                stats = stats_fn() or {}
                data["spent_usd"] = round(
                    max(0.0, float(stats.get("spent_total_usd") or 0.0)),
                    4,
                )
                bal_last = float(stats.get("balance_last_usd") or -1.0)
                if bal_last >= 0:
                    data["balance_usd"] = round(bal_last, 4)
                ts = float(stats.get("updated_at") or 0.0)
                if ts > 0:
                    data["updated_at"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

            if refresh and enabled and api_key:
                proxy_map = {"http": proxy, "https": proxy} if proxy else None
                bal_fn = getattr(r_with_pwd, "hero_sms_get_balance", None)
                if callable(bal_fn):
                    bal, err = bal_fn(proxy_map)
                    if float(bal) >= 0:
                        data["balance_usd"] = round(float(bal), 4)
                        data["balance_error"] = ""
                    else:
                        data["balance_error"] = str(err or "余额获取失败")[:220]

                svc_fn = getattr(r_with_pwd, "_hero_sms_resolve_service_code", None)
                ctry_fn = getattr(r_with_pwd, "_hero_sms_resolve_country_id", None)
                if callable(svc_fn):
                    try:
                        data["service_resolved"] = str(svc_fn(proxy_map) or "").strip()
                    except Exception:
                        pass
                if callable(ctry_fn):
                    try:
                        data["country_resolved"] = int(ctry_fn(proxy_map))
                    except Exception:
                        pass
        except Exception as e:
            data["balance_error"] = str(e)[:220]

        return data

    def sms_countries(self, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            enabled = bool(self.cfg.get("hero_sms_enabled", False))
            api_key = str(self.cfg.get("hero_sms_api_key") or "").strip()
            service_cfg = str(self.cfg.get("hero_sms_service") or "").strip()
            country_cfg = str(self.cfg.get("hero_sms_country") or "US").strip() or "US"
            proxy = str(self.cfg.get("proxy") or "").strip() or ""

        out: dict[str, Any] = {
            "enabled": enabled,
            "key_configured": bool(api_key),
            "service": service_cfg,
            "service_resolved": "",
            "country": country_cfg,
            "country_resolved": -1,
            "items": [],
            "total": 0,
            "filtered_out": 0,
            "updated_at": "",
            "error": "",
        }

        if not enabled:
            out["error"] = "HeroSMS 未启用"
            return out
        if not api_key:
            out["error"] = "HeroSMS API Key 未配置"
            return out

        try:
            from . import r_with_pwd  # type: ignore

            proxy_map = {"http": proxy, "https": proxy} if proxy else None
            req_fn = getattr(r_with_pwd, "_hero_sms_request", None)
            resolve_service_fn = getattr(r_with_pwd, "_hero_sms_resolve_service_code", None)
            resolve_country_fn = getattr(r_with_pwd, "_hero_sms_resolve_country_id", None)
            if not callable(req_fn):
                out["error"] = "HeroSMS 请求函数不可用"
                return out

            service_resolved = ""
            if callable(resolve_service_fn):
                try:
                    service_resolved = str(resolve_service_fn(proxy_map) or "").strip()
                except Exception:
                    service_resolved = str(service_cfg or "").strip()
            if not service_resolved:
                service_resolved = str(service_cfg or "").strip()
            out["service_resolved"] = service_resolved

            if callable(resolve_country_fn):
                try:
                    out["country_resolved"] = int(resolve_country_fn(proxy_map))
                except Exception:
                    pass

            ok_c, text_c, countries_data = req_fn(
                "getCountries",
                proxies=proxy_map,
                timeout=30,
            )
            if not ok_c:
                out["error"] = str(text_c or "getCountries failed")[:220]
                return out
            countries_rows = [x for x in (countries_data or []) if isinstance(x, dict)]

            prices_map: dict[str, dict[str, Any]] = {}
            params: dict[str, Any] = {}
            if service_resolved:
                params["service"] = service_resolved
            ok_p, text_p, prices_data = req_fn(
                "getPrices",
                proxies=proxy_map,
                params=params,
                timeout=30,
            )
            if ok_p and isinstance(prices_data, dict):
                for country_id, raw_entry in prices_data.items():
                    key = str(country_id or "").strip()
                    if not key:
                        continue
                    entry = raw_entry
                    if not isinstance(entry, dict):
                        continue

                    price_row: dict[str, Any] | None = None
                    if service_resolved and isinstance(entry.get(service_resolved), dict):
                        price_row = entry.get(service_resolved)
                    elif "cost" in entry or "count" in entry or "physicalCount" in entry:
                        price_row = entry
                    else:
                        for v in entry.values():
                            if isinstance(v, dict) and (
                                "cost" in v or "count" in v or "physicalCount" in v
                            ):
                                price_row = v
                                break

                    if not isinstance(price_row, dict):
                        continue
                    try:
                        cost = float(price_row.get("cost") or -1)
                    except Exception:
                        cost = -1.0
                    try:
                        count = int(price_row.get("count") or 0)
                    except Exception:
                        count = 0
                    try:
                        physical_count = int(price_row.get("physicalCount") or 0)
                    except Exception:
                        physical_count = 0
                    prices_map[key] = {
                        "cost": cost,
                        "count": max(0, count),
                        "physical_count": max(0, physical_count),
                    }
            elif refresh:
                out["error"] = str(text_p or "getPrices failed")[:220]

            items: list[dict[str, Any]] = []
            filtered_out = 0
            for row in countries_rows:
                try:
                    cid = int(row.get("id"))
                except Exception:
                    continue
                cid_s = str(cid)
                eng = str(row.get("eng") or "").strip() or cid_s
                chn = str(row.get("chn") or "").strip()
                if not _is_openai_sms_country_allowed(cid, eng):
                    filtered_out += 1
                    continue
                try:
                    visible = int(row.get("visible") or 0)
                except Exception:
                    visible = 0
                price_info = prices_map.get(cid_s, {})
                cost = float(price_info.get("cost") or -1.0)
                count = int(price_info.get("count") or 0)
                physical_count = int(price_info.get("physical_count") or 0)

                zh_name = _country_name_zh(eng, chn)
                title = zh_name if zh_name == eng else f"{zh_name} ({eng})"
                if cost >= 0:
                    label = f"{title} [{cid_s}] | ${cost:.3f} | 库存 {count}"
                else:
                    label = f"{title} [{cid_s}] | 无报价 | 库存 {count}"

                items.append(
                    {
                        "id": cid_s,
                        "eng": eng,
                        "chn": zh_name,
                        "visible": visible,
                        "cost": cost,
                        "count": count,
                        "physical_count": physical_count,
                        "label": label,
                    }
                )

            def _sort_key(x: dict[str, Any]) -> tuple[Any, ...]:
                c = int(x.get("count") or 0)
                v = int(x.get("visible") or 0)
                cost_v = float(x.get("cost") or -1.0)
                has_price = 0 if cost_v >= 0 else 1
                return (
                    0 if c > 0 else 1,
                    0 if v > 0 else 1,
                    has_price,
                    cost_v if cost_v >= 0 else 999999.0,
                    -c,
                    str(x.get("eng") or x.get("id") or ""),
                )

            items.sort(key=_sort_key)
            out["items"] = items
            out["total"] = len(items)
            out["filtered_out"] = int(filtered_out)
            out["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return out
        except Exception as e:
            out["error"] = str(e)[:220]
            return out

    def start(self, run_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if self._running:
                raise RuntimeError("任务正在运行中")
        if run_cfg:
            self.update_config(run_cfg, emit_log=False)

        with self._lock:
            blockers, _ = self._config_health_locked()
        if blockers:
            preview = "；".join(blockers[:3])
            if len(blockers) > 3:
                preview += f"；另有 {len(blockers) - 3} 项"
            raise RuntimeError(f"配置未完成，无法启动：{preview}")

        self._apply_to_env()
        self._stop.clear()
        self._set_running(True)
        self._set_status("运行中")
        self._set_progress(0)
        self._reset_run_stats(planned_total=0)
        self.log("开始注册任务")
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self._running:
                return self.status()
        self._stop.set()
        self._set_status("停止中")
        self.log("正在停止...")
        return self.status()

    def _worker(self) -> None:
        """后台注册循环：劫持 stdout 以收集 r_with_pwd 日志，结束后恢复。"""
        old_out, old_err = sys.stdout, sys.stderr
        cap = StdoutCapture(self.log)
        sys.stdout = cap
        sys.stderr = cap

        try:
            from . import r_with_pwd

            mail_provider = normalize_mail_provider(self.cfg.get("mail_service_provider") or "mailfree")
            domain = str(self.cfg.get("worker_domain") or "").strip()
            mail_domains_raw = str(self.cfg.get("mail_domains") or "").strip()
            if mail_provider == "cloudflare_temp_email":
                cf_domain = str(self.cfg.get("cf_temp_base_url") or "").strip()
                cf_domains_raw = str(self.cfg.get("cf_temp_mail_domains") or "").strip()
                if cf_domain:
                    domain = cf_domain
                if cf_domains_raw:
                    mail_domains_raw = cf_domains_raw
            elif mail_provider == "luckyous":
                lucky_base = str(
                    self.cfg.get("luckyous_api_base") or "https://mails.luckyous.com"
                ).strip()
                if lucky_base:
                    domain = lucky_base
            if domain and not domain.startswith("http"):
                domain = f"https://{domain}"

            r_with_pwd.STOP_EVENT = self._stop
            r_with_pwd.WORKER_DOMAIN = domain.rstrip("/")
            r_with_pwd.FREEMAIL_USERNAME = str(self.cfg.get("freemail_username") or "")
            r_with_pwd.FREEMAIL_PASSWORD = str(self.cfg.get("freemail_password") or "")
            r_with_pwd.MAIL_SERVICE_PROVIDER = mail_provider
            os.environ["WORKER_DOMAIN"] = r_with_pwd.WORKER_DOMAIN
            os.environ["MAIL_DOMAINS"] = mail_domains_raw
            r_with_pwd.MAIL_ALLOWED_DOMAINS = self._normalize_domain_list(
                self.cfg.get("mail_domain_allowlist") or []
            )
            r_with_pwd._freemail_session_cookie_reset()
            try:
                reset_sms_stats = getattr(r_with_pwd, "reset_hero_sms_runtime_stats", None)
                if callable(reset_sms_stats):
                    reset_sms_stats()
            except Exception:
                pass

            fp = str(self.cfg.get("freemail_password") or "")
            fp_mask = (fp[:3] + "***") if len(fp) >= 3 else ("***" if fp else "")
            random_domain_on = bool(self.cfg.get("mailfree_random_domain", True))
            mail_domains_list = [
                x for x in re.split(r"[\n\r,;\s]+", mail_domains_raw) if str(x or "").strip()
            ]
            allow_domains = list(r_with_pwd.MAIL_ALLOWED_DOMAINS or [])
            if mail_provider == "mailfree":
                self.log(
                    f"配置 -> mail={mail_provider}, domain={r_with_pwd.WORKER_DOMAIN}, "
                    f"user={r_with_pwd.FREEMAIL_USERNAME}, pass={fp_mask}, "
                    f"random_domain={'开启' if random_domain_on else '关闭'}"
                )
                if allow_domains:
                    self.log(f"配置 -> 指定注册域名 {len(allow_domains)} 个")
            else:
                graph_pre_refresh = bool(self.cfg.get("graph_pre_refresh_before_run", True))
                hero_sms_enabled = bool(self.cfg.get("hero_sms_enabled", False))
                hero_sms_reuse = bool(self.cfg.get("hero_sms_reuse_phone", False))
                hero_sms_service = str(self.cfg.get("hero_sms_service") or "").strip() or "(auto)"
                hero_sms_country = str(self.cfg.get("hero_sms_country") or "US").strip() or "US"
                hero_sms_auto_ctry = bool(self.cfg.get("hero_sms_auto_pick_country", False))
                hero_sms_price = self._to_float(
                    self.cfg.get("hero_sms_max_price"),
                    2.0,
                    0.0,
                    200.0,
                )
                if mail_provider == "graph":
                    graph_accounts_mode = self._normalize_graph_accounts_mode(
                        self.cfg.get("graph_accounts_mode") or "file"
                    )
                    graph_file = str(self.cfg.get("graph_accounts_file") or "graph_accounts.txt").strip()
                    graph_api_base = str(self.cfg.get("graph_api_base_url") or "").strip()
                    graph_api_token = str(self.cfg.get("graph_api_token") or "").strip()
                    token_mask = (
                        (graph_api_token[:4] + "***")
                        if len(graph_api_token) >= 4
                        else ("***" if graph_api_token else "-")
                    )
                    graph_tenant = str(self.cfg.get("graph_tenant") or "common").strip()
                    mode_text = "接口模式" if graph_accounts_mode == "api" else "文件模式"
                    pre_refresh_text = "接口模式固定关闭" if graph_accounts_mode == "api" else (
                        "开启" if graph_pre_refresh else "关闭"
                    )
                    if graph_accounts_mode == "api":
                        self.log(
                            "配置 -> "
                            f"mail={mail_provider}, mode={mode_text}, "
                            f"graph_api={graph_api_base or '-'}, token={token_mask}, "
                            f"pre_refresh={pre_refresh_text}"
                        )
                    else:
                        self.log(
                            "配置 -> "
                            f"mail={mail_provider}, mode={mode_text}, "
                            f"graph_file={graph_file or '-'}, tenant={graph_tenant}, "
                            f"pre_refresh={pre_refresh_text}"
                        )
                elif mail_provider == "cloudflare_temp_email":
                    cf_temp_auth = str(self.cfg.get("cf_temp_admin_auth") or "")
                    cf_mask = (cf_temp_auth[:3] + "***") if len(cf_temp_auth) >= 3 else ("***" if cf_temp_auth else "")
                    self.log(
                        "配置 -> "
                        f"mail={mail_provider}, api={r_with_pwd.WORKER_DOMAIN}, admin_auth={cf_mask}, "
                        f"domains={len(mail_domains_list)}, random_domain={'开' if random_domain_on else '关'}"
                    )
                elif mail_provider == "cloudmail":
                    cm_api = str(self.cfg.get("cloudmail_api_url") or "").strip()
                    cm_admin = str(self.cfg.get("cloudmail_admin_email") or "").strip()
                    self.log(
                        "配置 -> "
                        f"mail={mail_provider}, api={cm_api}, admin={cm_admin}, domains={len(mail_domains_list)}"
                    )
                elif mail_provider == "mail_curl":
                    mc_api = str(self.cfg.get("mail_curl_api_base") or "").strip()
                    mc_key = str(self.cfg.get("mail_curl_key") or "")
                    mc_mask = (mc_key[:4] + "***") if len(mc_key) >= 4 else ("***" if mc_key else "")
                    self.log(
                        "配置 -> "
                        f"mail={mail_provider}, api={mc_api}, key={mc_mask}"
                    )
                elif mail_provider == "luckyous":
                    lucky_api = str(
                        self.cfg.get("luckyous_api_base") or "https://mails.luckyous.com"
                    ).strip()
                    lucky_key = str(self.cfg.get("luckyous_api_key") or "")
                    lucky_key_mask = (
                        lucky_key[:4] + "***"
                        if len(lucky_key) >= 4
                        else ("***" if lucky_key else "")
                    )
                    lucky_project = str(self.cfg.get("luckyous_project_code") or "").strip()
                    lucky_type = str(self.cfg.get("luckyous_email_type") or "ms_graph").strip().lower()
                    lucky_domain = str(self.cfg.get("luckyous_domain") or "").strip().lower()
                    lucky_mode = str(self.cfg.get("luckyous_variant_mode") or "").strip().lower()
                    self.log(
                        "配置 -> "
                        f"mail={mail_provider}, api={lucky_api}, key={lucky_key_mask}, "
                        f"project={lucky_project or '-'}, type={lucky_type or '-'}, "
                        f"domain={lucky_domain or '-'}, variant={lucky_mode or '-'}"
                    )
                else:
                    gmail_user = str(self.cfg.get("gmail_imap_user") or "").strip().lower()
                    gmail_server = (
                        str(self.cfg.get("gmail_imap_server") or "imap.gmail.com").strip()
                        or "imap.gmail.com"
                    )
                    gmail_port = self._to_int(self.cfg.get("gmail_imap_port"), 993, 1, 65535)
                    gmail_tag_len = self._to_int(self.cfg.get("gmail_alias_tag_len"), 8, 1, 64)
                    gmail_mix = bool(self.cfg.get("gmail_alias_mix_googlemail", True))
                    alias_raw = str(self.cfg.get("gmail_alias_emails") or "").strip()
                    alias_rows = [
                        x
                        for x in re.split(r"[\n\r,;\s]+", alias_raw)
                        if str(x or "").strip()
                    ]
                    alias_count = len(alias_rows) if alias_rows else (1 if gmail_user else 0)
                    alias_unique_master_count = self._gmail_unique_master_count(alias_rows)
                    self.log(
                        "配置 -> "
                        f"mail={mail_provider}, imap_user={gmail_user}, "
                        f"imap_server={gmail_server}:{gmail_port}, alias_pool={alias_count}, "
                        f"tag_len={gmail_tag_len}, mix_googlemail={'开' if gmail_mix else '关'}"
                    )
                    if alias_rows and alias_unique_master_count <= 1:
                        self.log(
                            "[提示] Gmail 别名池仅识别到 1 个唯一主号（点号/+tag/googlemail 视为同源），"
                            "可能持续触发 user_already_exists"
                        )
                self.log(
                    "配置 -> "
                    f"hero_sms={'开启' if hero_sms_enabled else '关闭'}, "
                    f"service={hero_sms_service}, country={hero_sms_country}, "
                    f"auto_country={'开' if hero_sms_auto_ctry else '关'}, "
                    f"min_balance=${hero_sms_price:.2f}, "
                    f"reuse_phone={'开启' if hero_sms_reuse else '关闭'}"
                )
                if hero_sms_enabled and not str(self.cfg.get("hero_sms_api_key") or "").strip():
                    self.log("[提示] HeroSMS 已启用但 API Key 为空，add-phone 手机验证将无法执行")
                if hero_sms_enabled and str(self.cfg.get("hero_sms_api_key") or "").strip():
                    try:
                        sms_data = self.sms_overview(refresh=True)
                        bal_now = float(sms_data.get("balance_usd") or -1.0)
                        min_now = float(sms_data.get("min_balance_usd") or hero_sms_price)
                        if bal_now >= 0:
                            self.log(
                                f"HeroSMS 余额检查：当前 ${bal_now:.2f} · 下限 ${min_now:.2f}"
                            )
                        if bal_now >= 0 and bal_now < min_now:
                            self.log(
                                "HeroSMS 余额低于下限，停止注册："
                                f"当前 ${bal_now:.2f} < 下限 ${min_now:.2f}"
                            )
                            self._stop.set()
                            return
                    except Exception as e:
                        self.log(f"HeroSMS 余额预检查失败: {e}")

            per_file_num = self._to_int(self.cfg.get("num_accounts"), 1, 1)
            num_files = self._to_int(self.cfg.get("num_files"), 1, 1, 200)
            concurrency = self._to_int(self.cfg.get("concurrency"), 1, 1, 6)
            random_fp_on = bool(self.cfg.get("register_random_fingerprint", True))
            smin = self._to_int(self.cfg.get("sleep_min"), 5, 1)
            smax = self._to_int(self.cfg.get("sleep_max"), 30, smin)
            if smax < smin:
                smax = smin
            fast_mode = bool(self.cfg.get("fast_mode", False))
            retry_403_wait = self._to_int(self.cfg.get("retry_403_wait_sec"), 10, 3, 30)
            if fast_mode:
                retry_403_wait = min(retry_403_wait, 6)

            proxy_raw = str(self.cfg.get("proxy") or "").strip()
            proxy_items = [
                x
                for x in [str(v or "").strip() for v in re.split(r"[\n\r,;\s]+", proxy_raw)]
                if x
            ]
            if not proxy_items and proxy_raw:
                proxy_items = [proxy_raw]
            proxy = proxy_items[0] if proxy_items else None
            proxy_pick_lock = threading.Lock()
            proxy_pick_idx = 0

            def _mask_proxy_for_log(raw_proxy: str | None) -> str:
                text = str(raw_proxy or "").strip()
                if not text:
                    return "直连"
                try:
                    parsed = urllib.parse.urlsplit(text)
                    scheme = parsed.scheme or "http"
                    hostname = str(parsed.hostname or "").strip()
                    port = f":{parsed.port}" if parsed.port else ""
                    if hostname:
                        return f"{scheme}://{hostname}{port}"
                except Exception:
                    pass
                if "@" in text:
                    left, right = text.rsplit("@", 1)
                    if ":" in left:
                        user = left.split(":", 1)[0]
                        return f"{user}:***@{right}"
                return text

            def _pick_attempt_proxy() -> str | None:
                nonlocal proxy_pick_idx
                if not proxy_items:
                    return None
                if len(proxy_items) == 1:
                    return proxy_items[0]
                with proxy_pick_lock:
                    picked = proxy_items[proxy_pick_idx % len(proxy_items)]
                    proxy_pick_idx += 1
                return picked

            if len(proxy_items) > 1:
                self.log(
                    "代理轮换已启用："
                    f"共 {len(proxy_items)} 个入口，按顺序轮换"
                )
            elif proxy:
                self.log(f"代理入口：{_mask_proxy_for_log(proxy)}")
            else:
                self.log("代理入口：直连")

            outdir = os.getenv("TOKEN_OUTPUT_DIR", "").strip()
            graph_accounts_mode = self._normalize_graph_accounts_mode(
                self.cfg.get("graph_accounts_mode") or "file"
            )
            graph_pre_refresh_before_run = bool(
                self.cfg.get("graph_pre_refresh_before_run", True)
            )
            if mail_provider == "graph" and graph_accounts_mode == "api":
                graph_pre_refresh_before_run = False

            if concurrency > 1 and not random_fp_on:
                self.log(
                    "[提示] 当前为多并发 + 固定浏览器指纹，可能提高 invalid_auth_step/400 概率；"
                    "建议开启随机指纹或降低并发"
                )
            if mail_provider == "graph" and not graph_pre_refresh_before_run:
                if graph_accounts_mode == "api":
                    self.log("[提示] Graph 接口模式不执行注册前 token 预刷新")
                else:
                    self.log(
                        "[提示] 已关闭 Graph 注册前 token 预刷新：启动更快，但会更早命中坏号"
                    )

            if mail_provider == "graph":
                with self._lock:
                    self._mail_client = None
                    self._mail_client_sig = None
                if graph_pre_refresh_before_run:
                    proxy_map = {"http": proxy, "https": proxy} if proxy else None
                    client = self._get_mail_client()
                    refresh_fn = getattr(client, "refresh_mailbox_token", None)
                    remove_fn = getattr(client, "remove_account", None)
                    if not callable(refresh_fn):
                        raise RuntimeError("当前邮箱服务不支持刷新 Microsoft 邮箱 token")

                    account_rows = list(getattr(client, "_accounts", []) or [])
                    account_emails: list[str] = []
                    for acc in account_rows:
                        email = str((acc or {}).get("email") or "").strip().lower()
                        if email and "@" in email:
                            account_emails.append(email)
                    account_emails = list(dict.fromkeys(account_emails))

                    if not account_emails:
                        self.log("Microsoft 邮箱账号池为空，停止注册")
                        self._stop.set()
                        return

                    self.log(f"[Microsoft 邮箱] 注册前 token 预刷新开始：共 {len(account_emails)} 个账号")
                    pre_ok = 0
                    pre_fail = 0
                    for idx, email in enumerate(account_emails, start=1):
                        if self._stop.is_set():
                            break
                        try:
                            refresh_fn(email, proxies=proxy_map)
                            pre_ok += 1
                        except Exception as e:
                            pre_fail += 1
                            self.log(
                                f"[Microsoft 邮箱] token 预刷新失败 {idx}/{len(account_emails)}: {email} -> {e}"
                            )
                            if callable(remove_fn):
                                try:
                                    removed = bool(remove_fn(email))
                                except Exception:
                                    removed = False
                                if removed:
                                    self.log(f"[Microsoft 邮箱] 已移除失效账号: {email}")

                    remain_accounts = [
                        str((acc or {}).get("email") or "").strip().lower()
                        for acc in (getattr(client, "_accounts", []) or [])
                        if str((acc or {}).get("email") or "").strip()
                    ]
                    remain_count = len([x for x in remain_accounts if "@" in x])
                    self.log(
                        f"[Microsoft 邮箱] token 预刷新结束：成功 {pre_ok}，失败 {pre_fail}，剩余可用 {remain_count}"
                    )
                    if remain_count <= 0:
                        self.log("Microsoft 邮箱账号已耗尽，停止注册")
                        self._stop.set()
                        return
                else:
                    if graph_accounts_mode == "api":
                        self.log("[Microsoft 邮箱] 接口模式：已跳过注册前 token 预刷新")
                    else:
                        self.log("[Microsoft 邮箱] 已关闭注册前 token 预刷新")

            graph_accounts_file = str(
                self.cfg.get("graph_accounts_file") or "graph_accounts.txt"
            ).strip() or "graph_accounts.txt"
            graph_accounts_path = os.path.abspath(os.path.expanduser(graph_accounts_file))
            graph_accounts_mode = self._normalize_graph_accounts_mode(
                self.cfg.get("graph_accounts_mode") or "file"
            )

            def _graph_remaining_account_count() -> int:
                if mail_provider != "graph":
                    return -1
                if graph_accounts_mode == "api":
                    try:
                        gclient = self._get_mail_client()
                        rows = list(getattr(gclient, "_accounts", []) or [])
                    except Exception:
                        return 0
                    cnt = 0
                    for row in rows:
                        email_val = str((row or {}).get("email") or "").strip().lower()
                        if email_val and "@" in email_val:
                            cnt += 1
                    return cnt
                fp = str(graph_accounts_path or "").strip()
                if not fp or not os.path.isfile(fp):
                    return 0
                count = 0
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        for raw in f:
                            line = str(raw or "").strip().lstrip("\ufeff")
                            if not line or line.startswith("#"):
                                continue
                            parts = line.split("----", 3)
                            if len(parts) < 4:
                                continue
                            email = str(parts[0] or "").strip().lower()
                            client_id = str(parts[2] or "").strip()
                            token = str(parts[3] or "").strip()
                            if email and "@" in email and client_id and token:
                                count += 1
                except Exception:
                    return 0
                return count

            flclash_enable = bool(self.cfg.get("flclash_enable_switch", False))
            flclash_controller = self._normalize_flclash_controller(
                str(self.cfg.get("flclash_controller") or "")
            )
            flclash_secret = str(self.cfg.get("flclash_secret") or "").strip()
            flclash_group = str(self.cfg.get("flclash_group") or "PROXY").strip() or "PROXY"
            flclash_policy = str(self.cfg.get("flclash_switch_policy") or "round_robin").strip().lower()
            if flclash_policy not in {"round_robin", "random"}:
                flclash_policy = "round_robin"
            flclash_wait = self._to_float(self.cfg.get("flclash_switch_wait_sec"), 1.2, 0.0, 10.0)
            flclash_delay_url = str(
                self.cfg.get("flclash_delay_test_url") or "https://www.gstatic.com/generate_204"
            ).strip()
            flclash_delay_timeout_ms = self._to_int(
                self.cfg.get("flclash_delay_timeout_ms", 4000),
                4000,
                500,
                20000,
            )
            flclash_delay_max_ms = self._to_int(
                self.cfg.get("flclash_delay_max_ms", 1800),
                1800,
                100,
                30000,
            )
            flclash_delay_retry = self._to_int(
                self.cfg.get("flclash_delay_retry", 1),
                1,
                0,
                5,
            )
            flclash_rotate_every = self._to_int(
                self.cfg.get("flclash_rotate_every"),
                max(1, min(concurrency, per_file_num)),
                1,
                200,
            )

            total_target = per_file_num * num_files
            self._reset_run_stats(planned_total=total_target)
            if mail_provider == "graph" and bool(self.cfg.get("hero_sms_enabled", False)):
                with self._lock:
                    self._run_stats["sms_min_balance_usd"] = round(
                        self._to_float(self.cfg.get("hero_sms_max_price"), 2.0, 0.0, 200.0),
                        4,
                    )
            worker_count = min(concurrency, per_file_num)
            if flclash_enable and worker_count > 1:
                self.log(
                    "FlClash 动态换 IP + 多并发已启用：同一并发波次共享同一节点；"
                    f"每累计 {flclash_rotate_every} 次尝试后，等待当前波次结束再切到下一节点"
                )
            max_attempts = max(per_file_num * 50, per_file_num + 100)
            self.log(
                f"本轮参数：计划注册 {total_target}，"
                f"并发 {worker_count}，冷却 {smin}-{smax}s，"
                f"加速模式 {'开启' if fast_mode else '关闭'}，最大尝试 {max_attempts}"
            )

            flclash_lock = threading.Lock()
            flclash_state = {
                "enabled": False,
                "controller": flclash_controller,
                "secret": flclash_secret,
                "group": flclash_group,
                "policy": flclash_policy,
                "wait": flclash_wait,
                "delay_url": flclash_delay_url,
                "delay_timeout_ms": flclash_delay_timeout_ms,
                "delay_max_ms": flclash_delay_max_ms,
                "delay_retry": flclash_delay_retry,
                "nodes": [],
                "current": "",
                "next_idx": 0,
                "blocked_hk_count": 0,
                "blocked_hk_sample": [],
            }

            def _flclash_load_nodes() -> tuple[str, list[str], str]:
                data = self._flclash_request_json(
                    flclash_state["controller"],
                    method="GET",
                    path="/proxies",
                    secret=flclash_state["secret"],
                    timeout=20,
                )
                proxies = data.get("proxies") if isinstance(data, dict) else None
                if not isinstance(proxies, dict):
                    raise RuntimeError("/proxies 返回格式异常")

                def _proxy_type(obj: Any) -> str:
                    if isinstance(obj, dict):
                        return str(obj.get("type") or "").strip().lower()
                    return ""

                preferred = [
                    str(flclash_state["group"] or "").strip(),
                    "节点选择",
                    "PROXY",
                    "GLOBAL",
                ]
                selector_candidates: list[tuple[str, dict[str, Any]]] = []
                for key, val in proxies.items():
                    if not isinstance(val, dict):
                        continue
                    all_nodes = val.get("all")
                    if not isinstance(all_nodes, list) or not all_nodes:
                        continue
                    t = _proxy_type(val)
                    if t in {"selector", "select"}:
                        selector_candidates.append((str(key), val))

                target_key = ""
                target_obj: dict[str, Any] | None = None
                for name in preferred:
                    if not name:
                        continue
                    obj = proxies.get(name)
                    if (
                        isinstance(obj, dict)
                        and isinstance(obj.get("all"), list)
                        and obj.get("all")
                        and _proxy_type(obj) in {"selector", "select"}
                    ):
                        target_key = str(name)
                        target_obj = obj
                        break
                if target_obj is None and selector_candidates:
                    target_key, target_obj = selector_candidates[0]
                if target_obj is None:
                    raise RuntimeError("未找到可切换的 Selector 代理组，请在设置中指定节点组名")

                raw_nodes = [str(x).strip() for x in (target_obj.get("all") or []) if str(x).strip()]
                filtered: list[str] = []
                blocked: list[str] = []
                strategy_skipped: list[str] = []
                for node in raw_nodes:
                    low = node.lower()
                    if low in {"direct", "reject", "pass"}:
                        continue
                    if self._is_hk_node_name(node):
                        blocked.append(node)
                        continue

                    node_obj = proxies.get(node)
                    node_type = _proxy_type(node_obj)
                    if node_type in {"urltest", "fallback", "loadbalance", "relay"}:
                        strategy_skipped.append(node)
                        continue
                    if node not in filtered:
                        filtered.append(node)

                if not filtered:
                    flclash_state["blocked_hk_count"] = len(blocked)
                    flclash_state["blocked_hk_sample"] = blocked[:6]
                    if blocked:
                        raise RuntimeError("可用节点均为香港节点，已按规则跳过")
                    if strategy_skipped:
                        raise RuntimeError(
                            "节点组候选均为自动策略组(URLTest/Fallback)，"
                            "请改用包含具体节点的 Selector 组"
                        )
                    raise RuntimeError("代理组没有可用节点")

                flclash_state["blocked_hk_count"] = len(blocked)
                flclash_state["blocked_hk_sample"] = blocked[:6]

                current = str(target_obj.get("now") or "").strip()
                if current and self._is_hk_node_name(current):
                    current = ""

                return target_key, filtered, current

            def _flclash_candidate_order(force_diff: bool) -> list[str]:
                nodes: list[str] = list(flclash_state["nodes"])
                if not nodes:
                    return []
                current = str(flclash_state["current"] or "")
                if flclash_state["policy"] == "random":
                    order = list(nodes)
                    random.shuffle(order)
                    if force_diff and len(order) > 1 and current in order:
                        order = [n for n in order if n != current] + [current]
                    return order

                idx = int(flclash_state["next_idx"] or 0)
                if idx < 0 or idx >= len(nodes):
                    idx = 0
                order = [nodes[(idx + i) % len(nodes)] for i in range(len(nodes))]
                if force_diff and len(order) > 1 and current in order:
                    order = [n for n in order if n != current] + [current]
                return order

            def _flclash_probe_node_delay(node: str, tag: str) -> tuple[bool, int, str]:
                node_name = str(node or "").strip()
                if not node_name:
                    return False, -1, "节点名为空"
                url_arg = str(flclash_state["delay_url"] or "").strip()
                timeout_ms = int(flclash_state["delay_timeout_ms"] or 4000)
                max_ms = int(flclash_state["delay_max_ms"] or 1800)
                retry = int(flclash_state["delay_retry"] or 0)

                path_node = urllib.parse.quote(node_name, safe="")
                qs = urllib.parse.urlencode({"url": url_arg, "timeout": str(timeout_ms)})
                path = f"/proxies/{path_node}/delay?{qs}"

                last_msg = ""
                for i in range(retry + 1):
                    try:
                        data = self._flclash_request_json(
                            flclash_state["controller"],
                            method="GET",
                            path=path,
                            secret=str(flclash_state["secret"]),
                            timeout=max(5, int(timeout_ms / 1000) + 2),
                        )
                        delay = int(data.get("delay") or -1)
                        if delay > 0 and delay <= max_ms:
                            return True, delay, ""
                        if delay > 0:
                            last_msg = f"延迟 {delay}ms 超过阈值 {max_ms}ms"
                        else:
                            last_msg = str(data.get("error") or "延迟测试失败")
                    except Exception as e:
                        last_msg = str(e)

                    if i < retry:
                        wait = round(0.25 * (i + 1), 2)
                        self.log(
                            f"[{tag}] 节点 {node_name} 延迟测试失败，{wait}s 后重试 ({i + 1}/{retry})"
                        )
                        if self._wait_or_stop(wait):
                            return False, -1, "用户停止"

                return False, -1, last_msg or "延迟测试失败"

            def _flclash_pick_usable_node(tag: str, force_diff: bool) -> tuple[str, int]:
                order = _flclash_candidate_order(force_diff=force_diff)
                if not order:
                    raise RuntimeError("无可用节点")
                last_reason = ""
                for node in order:
                    ok_delay, delay_ms, reason = _flclash_probe_node_delay(node, tag)
                    if ok_delay:
                        return node, delay_ms
                    last_reason = reason or "延迟测试失败"
                    self.log(f"[{tag}] 节点不可用: {node} ({last_reason})")
                raise RuntimeError(f"未找到可用节点: {last_reason}")

            def _flclash_switch(tag: str, *, force_diff: bool) -> bool:
                if not flclash_state["enabled"]:
                    return False
                with flclash_lock:
                    try:
                        if not flclash_state["nodes"]:
                            g, nodes, current = _flclash_load_nodes()
                            flclash_state["group"] = g
                            flclash_state["nodes"] = nodes
                            flclash_state["current"] = current
                            if current in nodes:
                                flclash_state["next_idx"] = (nodes.index(current) + 1) % len(nodes)
                            else:
                                flclash_state["next_idx"] = 0

                        target, delay_ms = _flclash_pick_usable_node(tag, force_diff=force_diff)
                        current = str(flclash_state["current"] or "")

                        if target != current:
                            grp = urllib.parse.quote(str(flclash_state["group"]), safe="")
                            self._flclash_request_json(
                                flclash_state["controller"],
                                method="PUT",
                                path=f"/proxies/{grp}",
                                secret=str(flclash_state["secret"]),
                                payload={"name": target},
                                timeout=20,
                            )

                            verify = self._flclash_request_json(
                                flclash_state["controller"],
                                method="GET",
                                path=f"/proxies/{grp}",
                                secret=str(flclash_state["secret"]),
                                timeout=20,
                            )
                            actual_now = str(verify.get("now") or "").strip()
                            if actual_now:
                                flclash_state["current"] = actual_now
                            else:
                                flclash_state["current"] = target

                            if actual_now and actual_now != target:
                                self.log(
                                    f"[{tag}] FlClash 请求切到 {target}，"
                                    f"但当前为 {actual_now}（组不支持或被策略接管）"
                                )
                            else:
                                if target in flclash_state["nodes"]:
                                    flclash_state["next_idx"] = (
                                        flclash_state["nodes"].index(target) + 1
                                    ) % len(flclash_state["nodes"])
                                self.log(f"[{tag}] FlClash 已切换节点: {target} · 延迟 {delay_ms}ms")
                        else:
                            if len(flclash_state["nodes"]) <= 1:
                                self.log(
                                    f"[{tag}] 仅 1 个可用非香港节点，延迟 {delay_ms}ms: {target}"
                                )
                            else:
                                self.log(f"[{tag}] FlClash 维持节点: {target} · 延迟 {delay_ms}ms")

                        wait_sec = float(flclash_state["wait"] or 0)
                    except Exception as e:
                        self.log(f"[{tag}] FlClash 切换失败: {e}")
                        return False

                if wait_sec > 0:
                    if self._wait_or_stop(wait_sec):
                        return False
                return True

            if flclash_enable:
                if not flclash_state["controller"]:
                    self.log("FlClash 动态换 IP 已关闭：未填写控制器地址")
                else:
                    try:
                        g, nodes, current = _flclash_load_nodes()
                        flclash_state["enabled"] = True
                        flclash_state["group"] = g
                        flclash_state["nodes"] = nodes
                        flclash_state["current"] = current
                        if current in nodes:
                            flclash_state["next_idx"] = (nodes.index(current) + 1) % len(nodes)
                        else:
                            flclash_state["next_idx"] = 0
                        sample = ", ".join(nodes[:5])
                        self.log(
                            f"FlClash 动态换 IP 已启用: controller={flclash_state['controller']}, "
                            f"group={g}, nodes={len(nodes)}, 已排除香港节点"
                        )
                        blocked_cnt = int(flclash_state.get("blocked_hk_count") or 0)
                        blocked_sample = [
                            str(x).strip()
                            for x in (flclash_state.get("blocked_hk_sample") or [])
                            if str(x).strip()
                        ]
                        if blocked_cnt > 0:
                            show = ", ".join(blocked_sample[:5])
                            suffix = " ..." if blocked_cnt > len(blocked_sample[:5]) else ""
                            if show:
                                self.log(f"FlClash 已屏蔽香港节点 {blocked_cnt} 个: {show}{suffix}")
                            else:
                                self.log(f"FlClash 已屏蔽香港节点 {blocked_cnt} 个")
                        self.log(
                            f"FlClash 延迟测试: url={flclash_state['delay_url']}, "
                            f"timeout={flclash_state['delay_timeout_ms']}ms, "
                            f"阈值<={flclash_state['delay_max_ms']}ms, "
                            f"重试={flclash_state['delay_retry']}"
                        )
                        if sample:
                            self.log(f"FlClash 候选节点示例: {sample}")
                    except Exception as e:
                        self.log(f"FlClash 动态换 IP 初始化失败，已禁用: {e}")

            global_ok = 0
            completed_files = 0
            all_files_ok = True

            def _run_single_file(file_no: int) -> tuple[int, int, int, bool]:
                file_target = per_file_num
                progress_base = global_ok

                task_queue: Queue[int] = Queue()
                for idx in range(1, file_target + 1):
                    task_queue.put(idx)

                write_lock = threading.Lock()
                state_lock = threading.Lock()
                ok = 0
                attempts_started = file_target
                attempts_done = 0
                next_ticket = file_target
                extra_added = 0

                flc_batch_lock = threading.Condition()
                flc_active_runs = 0
                flc_switching = False
                flc_runs_on_node = 0
                flc_force_rollover = False
                flc_switch_every = max(1, int(flclash_rotate_every))

                def _flclash_mark_run_begin_locked() -> None:
                    nonlocal flc_active_runs, flc_runs_on_node, flc_force_rollover
                    flc_active_runs += 1
                    flc_runs_on_node += 1
                    if flc_runs_on_node >= flc_switch_every:
                        flc_force_rollover = True

                def _flclash_acquire_for_batch(tag: str) -> bool:
                    nonlocal flc_switching, flc_runs_on_node, flc_force_rollover
                    if not flclash_state["enabled"]:
                        return True

                    with flc_batch_lock:
                        while not self._stop.is_set():
                            if flc_switching:
                                flc_batch_lock.wait(timeout=0.2)
                                continue

                            # 达到轮换阈值后，阻塞新任务进入，等待当前在跑任务全部结束再切换。
                            if flc_force_rollover and flc_active_runs > 0:
                                flc_batch_lock.wait(timeout=0.2)
                                continue

                            if flc_active_runs == 0:
                                flc_switching = True
                                break

                            _flclash_mark_run_begin_locked()
                            return True

                        if self._stop.is_set():
                            return False

                    ok = _flclash_switch(tag, force_diff=True)

                    with flc_batch_lock:
                        flc_switching = False
                        if ok:
                            flc_runs_on_node = 0
                            flc_force_rollover = False
                            _flclash_mark_run_begin_locked()
                        flc_batch_lock.notify_all()
                    return ok

                def _flclash_release_for_batch() -> None:
                    nonlocal flc_active_runs
                    if not flclash_state["enabled"]:
                        return
                    with flc_batch_lock:
                        if flc_active_runs > 0:
                            flc_active_runs -= 1
                        if flc_active_runs == 0:
                            flc_batch_lock.notify_all()

                def _schedule_retry() -> int | None:
                    nonlocal attempts_started, next_ticket, extra_added
                    with state_lock:
                        if self._stop.is_set() or ok >= file_target:
                            return None
                        if attempts_started >= max_attempts:
                            return None
                        attempts_started += 1
                        extra_added += 1
                        next_ticket += 1
                        return next_ticket

                def _can_exit() -> bool:
                    with state_lock:
                        if ok >= file_target:
                            return True
                        if attempts_done >= attempts_started and task_queue.empty():
                            return True
                    return False

                def _one_worker(worker_no: int) -> None:
                    nonlocal ok, attempts_done
                    self._log_ctx.prefix = f"线程{worker_no}"
                    try:
                        while not self._stop.is_set():
                            with state_lock:
                                if ok >= file_target:
                                    return

                            try:
                                idx = task_queue.get(timeout=0.1)
                            except Empty:
                                if _can_exit():
                                    return
                                continue

                            if self._stop.is_set():
                                task_queue.task_done()
                                return

                            phase = (
                                f"{idx}/{file_target}"
                                if idx <= file_target
                                else f"补位#{idx - file_target}"
                            )
                            self.log(f"[F{file_no}W{worker_no}] >>> 尝试 {phase} <<<")

                            with state_lock:
                                ok_now = ok
                            self._set_status(
                                f"成功 {progress_base + ok_now}/{total_target} · "
                                f"当前批 {ok_now}/{file_target}"
                            )

                            need_retry = False
                            retry_reason = ""
                            flc_acquired = False
                            run_begin = time.time()

                            try:
                                if self._stop.is_set():
                                    continue

                                if flclash_state["enabled"]:
                                    flc_acquired = _flclash_acquire_for_batch(f"F{file_no}W{worker_no}")
                                    if not flc_acquired:
                                        if self._stop.is_set():
                                            need_retry = False
                                            retry_reason = ""
                                            continue
                                        self.log(
                                            f"[F{file_no}W{worker_no}] 节点切换/延迟测试失败，跳过本次并补位重试"
                                        )
                                        need_retry = True
                                        retry_reason = "节点切换/延迟测试失败"
                                        continue
                                attempt_proxy = _pick_attempt_proxy()
                                if len(proxy_items) > 1:
                                    self.log(
                                        f"[F{file_no}W{worker_no}] 代理轮换 -> "
                                        f"{_mask_proxy_for_log(attempt_proxy)}"
                                    )
                                result = r_with_pwd.run(attempt_proxy)
                                if not isinstance(result, (tuple, list)):
                                    self.log(f"[F{file_no}W{worker_no}] 返回异常，跳过")
                                    need_retry = True
                                    retry_reason = "返回结果异常"
                                else:
                                    acct = result[0]
                                    pwd = result[1] if len(result) > 1 else ""
                                    meta = result[2] if len(result) > 2 and isinstance(result[2], dict) else {}
                                    self._record_run_sms_stats_from_meta(meta)

                                    err_code = str(meta.get("error_code") or "").strip().lower()
                                    err_domain = str(meta.get("email_domain") or "").strip().lower()
                                    meta_reason = self._retry_reason_from_meta(meta)
                                    if err_code == "registration_disallowed" and err_domain:
                                        now = self._record_mail_domain_error(err_domain)
                                        self.log(
                                            f"[F{file_no}W{worker_no}] 域名风控计数: {err_domain} -> {now}"
                                        )
                                    if err_code == "graph_pool_exhausted":
                                        self.log(
                                            f"[F{file_no}W{worker_no}] Graph 账号池已耗尽，立即停止本轮注册"
                                        )
                                        self._stop.set()
                                        need_retry = False
                                        retry_reason = ""
                                        continue
                                    if err_code == "stopped_by_user":
                                        need_retry = False
                                        retry_reason = ""
                                        continue
                                    if err_code == "phone_balance_insufficient":
                                        self.log(
                                            f"[F{file_no}W{worker_no}] HeroSMS 余额低于下限，立即停止本轮注册"
                                        )
                                        self._stop.set()
                                        need_retry = False
                                        retry_reason = ""
                                        continue
                                    if err_code == "phone_country_blocked":
                                        self.log(
                                            f"[F{file_no}W{worker_no}] HeroSMS 国家受限，立即停止本轮注册"
                                        )
                                        self._stop.set()
                                        need_retry = False
                                        retry_reason = ""
                                        continue
                                    if err_code == "region_blocked":
                                        self.log(
                                            f"[F{file_no}W{worker_no}] OpenAI 区域不可用，立即停止本轮注册"
                                        )
                                        self._stop.set()
                                        need_retry = False
                                        retry_reason = ""
                                        continue

                                    if acct == "retry_403":
                                        self.log(
                                            f"[F{file_no}W{worker_no}] 403，{retry_403_wait} 秒后继续..."
                                        )
                                        stopped = self._wait_or_stop(float(retry_403_wait))
                                        if not stopped:
                                            need_retry = True
                                            retry_reason = "HTTP 403 限流"
                                    elif acct and isinstance(acct, dict):
                                        email = str(acct.get("name") or "")
                                        written = False
                                        with write_lock:
                                            with state_lock:
                                                can_write = ok < file_target
                                            if can_write:
                                                appended = bool(r_with_pwd._append_account_to_file(acct))
                                                if not appended:
                                                    self.log(
                                                        f"[F{file_no}W{worker_no}] "
                                                        "写入 JSON 失败，准备补位重试"
                                                    )
                                                    need_retry = True
                                                    retry_reason = "写入 JSON 失败"
                                                else:
                                                    with state_lock:
                                                        ok += 1
                                                        ok_now = ok
                                                    written = True
                                                    run_cost_ms = int((time.time() - run_begin) * 1000)
                                                    self._record_run_success(1, duration_ms=run_cost_ms)
                                                    if email and pwd:
                                                        try:
                                                            pf = (
                                                                os.path.join(outdir, ACCOUNTS_TXT)
                                                                if outdir
                                                                else ACCOUNTS_TXT
                                                            )
                                                            with open(pf, "a", encoding="utf-8") as af:
                                                                af.write(f"{email}----{pwd}\n")
                                                        except Exception as e:
                                                            self.log(
                                                                f"[F{file_no}W{worker_no}] "
                                                                f"写入 accounts.txt 失败: {e}"
                                                            )
                                                    if email:
                                                        try:
                                                            src_name = os.path.basename(
                                                                str(getattr(r_with_pwd, "_ACCOUNTS_FILE_PATH", "") or "")
                                                            )
                                                            self.upsert_local_account_record(
                                                                email,
                                                                pwd,
                                                                acct,
                                                                src_name,
                                                            )
                                                        except Exception as e:
                                                            self.log(
                                                                f"[F{file_no}W{worker_no}] "
                                                                f"写入 local_accounts.db 失败: {e}"
                                                            )
                                        if written:
                                            succ_domain = self._email_domain(email)
                                            if succ_domain:
                                                self._record_mail_domain_registered(succ_domain)
                                            self.log(
                                                f"[F{file_no}W{worker_no}] 成功 ({ok_now}/{file_target}): {email}"
                                            )
                                            if mail_provider == "graph":
                                                remain_now = _graph_remaining_account_count()
                                                if remain_now <= 0 and ok_now < file_target:
                                                    self.log(
                                                        f"[F{file_no}W{worker_no}] "
                                                        "Microsoft 邮箱账号已耗尽，立即停止本轮注册"
                                                    )
                                                    self._stop.set()
                                        else:
                                            self.log(
                                                f"[F{file_no}W{worker_no}] 已达目标，忽略额外成功: {email}"
                                            )
                                    else:
                                        self.log(f"[F{file_no}W{worker_no}] 本次失败")
                                        need_retry = True
                                        retry_reason = meta_reason or "注册流程失败"
                            except Exception as e:
                                self.log(f"[F{file_no}W{worker_no}] 异常: {e}")
                                need_retry = True
                                retry_reason = f"运行异常({type(e).__name__})"
                            finally:
                                if flc_acquired:
                                    _flclash_release_for_batch()
                                with state_lock:
                                    attempts_done += 1
                                    done_now = attempts_done
                                    ok_now = ok
                                    started_now = attempts_started
                                self._set_progress((progress_base + ok_now) / total_target)
                                self._set_status(
                                    f"成功 {progress_base + ok_now}/{total_target} · "
                                    f"当前批 {ok_now}/{file_target} · "
                                    f"尝试 {done_now}/{started_now}"
                                )
                                task_queue.task_done()

                            if need_retry and not self._stop.is_set():
                                retry_ticket = _schedule_retry()
                                if retry_ticket is not None:
                                    why = str(retry_reason or "").strip() or "未知失败"
                                    retry_total, success_rate = self._record_run_retry(why)
                                    task_queue.put(retry_ticket)
                                    self.log(
                                        f"[F{file_no}W{worker_no}] "
                                        f"失败补位：已追加第 {retry_ticket - file_target} 次补位，"
                                        f"原因={why}，当前成功率={success_rate:.2f}%（重试 {retry_total}）"
                                    )
                                else:
                                    with state_lock:
                                        ok_now = ok
                                        done_now = attempts_done
                                        started_now = attempts_started
                                    if ok_now < file_target and done_now >= started_now:
                                        why = str(retry_reason or "").strip() or "未知失败"
                                        self.log(
                                            f"[F{file_no}W{worker_no}] "
                                            f"已达最大尝试上限 {max_attempts}，当前成功 {ok_now}/{file_target}，"
                                            f"最近失败原因={why}"
                                        )

                            with state_lock:
                                finished = ok >= file_target
                            if finished or self._stop.is_set():
                                continue

                            w = random.randint(smin, smax)
                            if w > 0:
                                self.log(f"[F{file_no}W{worker_no}] 冷却 {w} 秒...")
                                self._wait_or_stop(float(w))
                    finally:
                        self._log_ctx.prefix = ""

                workers: list[threading.Thread] = []
                for worker_no in range(1, worker_count + 1):
                    t = threading.Thread(target=_one_worker, args=(worker_no,), daemon=True)
                    workers.append(t)
                    t.start()

                for t in workers:
                    t.join()

                with state_lock:
                    done_final = attempts_done
                    ok_final = ok
                    started_final = attempts_started
                    extra_final = extra_added

                file_ok = ok_final >= file_target
                if file_ok:
                    self.log(
                        f"[批次 {file_no}] 完成 "
                        f"(成功 {ok_final}/{file_target}，补位 {extra_final} 次)"
                    )
                else:
                    self.log(
                        f"[批次 {file_no}] 结束 "
                        f"(成功 {ok_final}/{file_target}，尝试 {done_final}/{started_final})"
                    )
                return ok_final, started_final, extra_final, file_ok

            for file_no in range(1, num_files + 1):
                if self._stop.is_set():
                    break
                acc_file = r_with_pwd._init_accounts_file(outdir)
                self.log(f"[批次 {file_no}] Accounts: {acc_file}")
                file_ok_count, _, _, file_ok = _run_single_file(file_no)
                global_ok += file_ok_count
                if file_ok:
                    completed_files += 1
                else:
                    all_files_ok = False
                    if not self._stop.is_set():
                        self.log(f"[批次 {file_no}] 未补齐，停止后续批次")
                    break

            with self._lock:
                retry_total = int(self._run_stats.get("retry_total") or 0)
                success_rate = float(self._run_stats.get("success_rate") or 100.0)
                top_reasons = self._top_retry_reasons(
                    dict(self._run_stats.get("retry_reasons") or {}),
                    limit=4,
                )
            if retry_total > 0:
                reason_text = "；".join(
                    [f"{str(x.get('reason') or '')} ×{int(x.get('count') or 0)}" for x in top_reasons]
                )
                self.log(
                    f"重试统计：{retry_total} 次 · 成功率 {success_rate:.2f}%"
                    + (f" · 原因：{reason_text}" if reason_text else "")
                )
            else:
                self.log(f"重试统计：0 次 · 成功率 {success_rate:.2f}%")

            with self._lock:
                self._refresh_run_elapsed_locked()
                elapsed_sec = float(self._run_stats.get("elapsed_sec") or 0.0)
                avg_sec = float(self._run_stats.get("avg_success_sec") or 0.0)
                sms_spent = float(self._run_stats.get("sms_spent_usd") or 0.0)
                sms_balance = float(self._run_stats.get("sms_balance_usd") or -1.0)
                sms_min = float(self._run_stats.get("sms_min_balance_usd") or 0.0)
            self.log(f"耗时统计：总耗时 {elapsed_sec:.2f}s · 平均耗时 {avg_sec:.2f}s/成功")
            if sms_spent > 0 or sms_balance >= 0:
                bal_text = f"${sms_balance:.2f}" if sms_balance >= 0 else "-"
                self.log(
                    "SMS统计："
                    f"累计消耗 ${sms_spent:.2f} · 当前余额 {bal_text} · 余额下限 ${sms_min:.2f}"
                )

            if self._stop.is_set() and global_ok < total_target:
                tag = (
                    f"已停止 (成功 {global_ok}/{total_target}，完成批次 {completed_files})"
                )
            elif all_files_ok and completed_files == num_files:
                tag = (
                    f"完成 (成功 {global_ok}/{total_target})"
                )
            else:
                tag = (
                    f"结束 (成功 {global_ok}/{total_target})，有批次未补齐"
                )
            self.log(tag)
        except Exception as e:
            self.log(f"运行异常: {e}")
        finally:
            try:
                if "r_with_pwd" in locals():
                    setattr(r_with_pwd, "STOP_EVENT", None)
            except Exception:
                pass
            self._mark_run_finished()
            cap.flush()
            sys.stdout = old_out
            sys.stderr = old_err
            self._set_running(False)
            self._set_status("就绪")
            self._set_progress(0)

    def _accounts_txt_path(self) -> str:
        return _data_accounts_txt_path(self)

    @staticmethod
    def _emails_from_accounts_json(fp: str) -> set[str]:
        return _data_emails_from_accounts_json(fp)

    @staticmethod
    def _email_from_account_entry(acc: dict[str, Any]) -> str:
        return _data_email_from_account_entry(acc)

    def _build_local_account_index(self) -> dict[str, dict[str, Any]]:
        return _data_build_local_account_index(self)

    def _build_email_source_files_map(self) -> dict[str, list[str]]:
        return _data_build_email_source_files_map(self)

    @staticmethod
    def _source_label(files: list[str]) -> str:
        return _data_source_label(files)

    def save_json_file_note(self, path: str, note: str) -> dict[str, Any]:
        return _data_save_json_file_note(self, path, note)

    def list_json_files(self) -> dict[str, Any]:
        return _data_list_json_files(self)

    def list_accounts(self) -> dict[str, Any]:
        return _data_list_accounts(self)

    def delete_json_files(self, paths: list[str]) -> dict[str, Any]:
        return _data_delete_json_files(self, paths)

    def delete_local_accounts(self, emails: list[str]) -> dict[str, Any]:
        return _data_delete_local_accounts(self, emails)

    def sync_selected_accounts(
        self,
        emails: list[str],
        provider_override: str = "",
    ) -> dict[str, Any]:
        return _data_sync_selected_accounts(self, emails, provider_override)

    def test_local_accounts_via_cpa(self, emails: list[str]) -> dict[str, Any]:
        return _data_test_local_accounts_via_cpa(self, emails)

    def export_sub2api_accounts(
        self,
        emails: list[str],
        file_count: int = 1,
        accounts_per_file: int = 0,
    ) -> dict[str, Any]:
        return _data_export_sub2api_accounts(self, emails, file_count, accounts_per_file)

    def export_codex_accounts(self, emails: list[str]) -> dict[str, Any]:
        return _data_export_codex_accounts(self, emails)

    def upsert_local_account_record(
        self,
        email: str,
        password: str,
        account: dict[str, Any] | None,
        source_primary: str = "",
    ) -> bool:
        return _data_upsert_local_account_record(self, email, password, account, source_primary)

    @staticmethod
    def _remote_item_groups_label(it: dict[str, Any]) -> str:
        gs = it.get("groups")
        if not isinstance(gs, list) or not gs:
            return "-"
        names: list[str] = []
        for g in gs[:4]:
            if isinstance(g, dict) and g.get("name"):
                names.append(str(g["name"]))
        s = ", ".join(names)
        if len(gs) > 4:
            s += "…"
        return s or "-"

    @staticmethod
    def _usage_to_percent(v: Any) -> str:
        try:
            return f"{float(v):.1f}%"
        except (TypeError, ValueError):
            return "--"

    @staticmethod
    def _remote_name_key(name: Any) -> str:
        return str(name or "").strip().lower()

    def _refresh_remote_rows_derived_locked(self) -> None:
        """在锁内重建远端缓存派生字段：重复标记、邮箱计数。"""
        counts: dict[str, int] = {}
        for row in self._remote_rows:
            k = self._remote_name_key(row.get("name"))
            if not k:
                continue
            counts[k] = counts.get(k, 0) + 1

        self._remote_email_counts = counts
        for row in self._remote_rows:
            k = self._remote_name_key(row.get("name"))
            row["is_dup"] = bool(k and counts.get(k, 0) > 1)

    def _fetch_remote_all_pages_cliproxy(self, search: str = "") -> dict[str, Any]:
        base, auth, verify_ssl, proxy_arg = self._cliproxy_management_context()
        headers = {
            "Accept": "application/json",
            "Authorization": auth,
        }
        url = f"{base.rstrip('/')}/auth-files"
        code, text = _http_get(
            url,
            headers,
            verify_ssl=verify_ssl,
            timeout=90,
            proxy=proxy_arg,
        )
        if not (200 <= code < 300):
            snippet = (text or "")[:400].replace("\n", " ")
            raise RuntimeError(f"HTTP {code}: {snippet}")

        try:
            payload = json.loads(text) if (text or "").strip() else {}
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON 解析失败: {e}") from e

        items = payload.get("files") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            items = []

        search_kw = str(search or "").strip().lower()
        with self._lock:
            test_state_snapshot = dict(self._remote_test_state)

        rows: list[dict[str, Any]] = []
        for idx, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            raw_name = str(it.get("name") or "").strip()
            aid = str(it.get("id") or raw_name or f"auth-{idx + 1}").strip()
            email = str(it.get("email") or "").strip()
            label = str(it.get("label") or "").strip()
            display_name = email or label or raw_name or aid
            provider = str(it.get("provider") or it.get("type") or "").strip()
            status = str(it.get("status") or "").strip()
            if bool(it.get("disabled")):
                status = "disabled"
            elif bool(it.get("unavailable")):
                status = "unavailable"

            if search_kw:
                haystack = " ".join(
                    [
                        display_name,
                        raw_name,
                        email,
                        label,
                        aid,
                        provider,
                    ]
                ).lower()
                if search_kw not in haystack:
                    continue

            access_token = self._extract_remote_item_access_token(it)

            rows.append(
                {
                    "key": f"{aid}-{idx}",
                    "id": aid,
                    "name": display_name,
                    "platform": provider,
                    "type": str(it.get("account_type") or it.get("type") or ""),
                    "status": status or "ready",
                    "groups": str(it.get("account") or "-"),
                    "u5h": "--",
                    "u7d": "--",
                    "test_status": str(
                        (test_state_snapshot.get(aid) or {}).get("status") or "未测试"
                    ),
                    "test_result": str(
                        (test_state_snapshot.get(aid) or {}).get("result") or "-"
                    ),
                    "test_at": str(
                        (test_state_snapshot.get(aid) or {}).get("at") or "-"
                    ),
                    "is_dup": False,
                    "auth_index": str(it.get("auth_index") or ""),
                    "file_name": raw_name or aid,
                    "runtime_only": bool(it.get("runtime_only")),
                    "disabled": bool(it.get("disabled")),
                    "unavailable": bool(it.get("unavailable")),
                    "status_message": str(it.get("status_message") or ""),
                    "access_token": access_token,
                    "provider_source": "cliproxyapi",
                }
            )

        with self._lock:
            self._remote_rows = rows
            self._remote_total = len(rows)
            self._remote_pages = 1
            self._refresh_remote_rows_derived_locked()
            self._remote_sync_status_ready = True

        self.log(f"CLIProxyAPI 列表拉取完成：{len(rows)} 条")
        return {
            "items": rows,
            "total": len(rows),
            "pages": 1,
            "loaded": len(rows),
        }

    def fetch_remote_all_pages(self, search: str = "") -> dict[str, Any]:
        with self._lock:
            if self._remote_busy:
                raise RuntimeError("服务端列表请求进行中")
            self._remote_busy = True
            self._remote_sync_status_ready = False
            self._remote_rows = []
            self._remote_total = 0
            self._remote_pages = 1
            self._remote_email_counts = {}

        page_rows: dict[int, list[dict[str, Any]]] = {}
        total = 0
        pages = 1
        with self._lock:
            test_state_snapshot = dict(self._remote_test_state)

        try:
            provider = self._normalize_remote_account_provider(
                self.cfg.get("remote_account_provider") or "sub2api"
            )
            if provider == "cliproxyapi":
                return self._fetch_remote_all_pages_cliproxy(search)

            tok = str(self.cfg.get("accounts_sync_bearer_token") or "").strip()
            base = str(self.cfg.get("accounts_list_api_base") or "").strip()
            if not tok:
                raise ValueError("请先填写 Bearer Token")
            if not base:
                raise ValueError("请先填写账号列表 API")

            psize = 10
            verify = bool(self.cfg.get("openai_ssl_verify", True))
            proxy_arg = str(self.cfg.get("proxy") or "").strip() or None
            fetch_workers = self._to_int(
                self.cfg.get("accounts_list_fetch_workers", 4),
                4,
                1,
                12,
            )
            ssl_retry_limit = self._to_int(
                self.cfg.get("accounts_list_ssl_retry", 3),
                3,
                0,
                8,
            )
            ssl_retry_wait = self._to_float(
                self.cfg.get("accounts_list_ssl_retry_wait_sec", 0.8),
                0.8,
                0.1,
                5.0,
            )
            tz = str(
                self.cfg.get(
                    "accounts_list_timezone",
                    DEFAULT_CONFIG["accounts_list_timezone"],
                )
            )
            auth = tok if tok.lower().startswith("bearer ") else f"Bearer {tok}"
            search_kw = str(search or "").strip()
            self.log("开始循环拉取列表与额度（每页 10 条）…")
            if ssl_retry_limit > 0:
                self.log(
                    f"列表拉取 SSL 重试已启用：最多 {ssl_retry_limit} 次，基准等待 {ssl_retry_wait:.1f}s"
                )

            def _http_get_retry(
                *,
                url: str,
                headers: dict[str, Any],
                timeout_sec: int,
                tag: str,
            ) -> tuple[int, str]:
                ssl_http_codes = {495, 496, 525, 526}
                for attempt in range(ssl_retry_limit + 1):
                    code, text = _http_get(
                        url,
                        headers,
                        verify_ssl=verify,
                        timeout=timeout_sec,
                        proxy=proxy_arg,
                    )
                    if 200 <= code < 300:
                        return code, text

                    msg = str(text or "")
                    is_ssl = self._is_ssl_retryable_error(msg) or code in ssl_http_codes
                    if not is_ssl or attempt >= ssl_retry_limit:
                        return code, text

                    wait = round(ssl_retry_wait * (attempt + 1), 2)
                    self.log(
                        f"[{tag}] SSL/TLS 异常，{wait}s 后重试 ({attempt + 1}/{ssl_retry_limit})"
                    )
                    time.sleep(wait)

                return -1, "SSL 重试失败"

            def _fetch_one_page(page_no: int) -> tuple[int, int, int, list[dict[str, Any]]]:
                qs = urllib.parse.urlencode(
                    {
                        "page": str(page_no),
                        "page_size": str(psize),
                        "platform": "",
                        "type": "",
                        "status": "",
                        "group": "",
                        "search": search_kw,
                        "timezone": tz,
                    }
                )
                url = f"{base.rstrip('/')}?{qs}"
                code, text = _http_get_retry(
                    url=url,
                    headers={"Accept": "application/json", "Authorization": auth},
                    timeout_sec=90,
                    tag=f"列表第 {page_no} 页",
                )
                if not (200 <= code < 300):
                    raise RuntimeError(f"HTTP {code}: {(text or '')[:400]}")

                try:
                    j = json.loads(text)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"JSON 解析失败: {e}") from e

                if j.get("code") != 0:
                    raise RuntimeError(str(j.get("message") or "接口返回非成功"))

                data = j.get("data") or {}
                items = data.get("items") or []
                if not isinstance(items, list):
                    items = []
                total_now = int(data.get("total") or 0)
                pages_now = max(1, int(data.get("pages") or 1))
                page_now = int(data.get("page") or page_no)

                rows_page: list[dict[str, Any]] = []

                for idx, it in enumerate(items):
                    if not isinstance(it, dict):
                        continue
                    aid = str(it.get("id") or "")
                    name = str(it.get("name") or "")
                    plat = str(it.get("platform") or "")
                    typ = str(it.get("type") or "")
                    st = str(it.get("status") or "")
                    gl = self._remote_item_groups_label(it)
                    access_token = self._extract_remote_item_access_token(it)

                    u5, u7 = "--", "--"
                    if aid.isdigit():
                        uurl = f"{base.rstrip('/')}/{aid}/usage?{urllib.parse.urlencode({'timezone': tz})}"
                        uc, ut = _http_get_retry(
                            url=uurl,
                            headers={"Accept": "application/json", "Authorization": auth},
                            timeout_sec=30,
                            tag=f"usage#{aid}",
                        )
                        if 200 <= uc < 300:
                            try:
                                uj = json.loads(ut)
                            except Exception:
                                uj = {}
                            if uj.get("code") == 0:
                                ud = uj.get("data") or {}
                                u5 = self._usage_to_percent(
                                    (ud.get("five_hour") or {}).get("utilization")
                                )
                                u7 = self._usage_to_percent(
                                    (ud.get("seven_day") or {}).get("utilization")
                                )

                    rows_page.append(
                        {
                            "key": f"{aid}-{page_now}-{idx}",
                            "id": aid,
                            "name": name,
                            "platform": plat,
                            "type": typ,
                            "status": st,
                            "groups": gl,
                            "u5h": u5,
                            "u7d": u7,
                            "test_status": str(
                                (test_state_snapshot.get(aid) or {}).get("status") or "未测试"
                            ),
                            "test_result": str(
                                (test_state_snapshot.get(aid) or {}).get("result") or "-"
                            ),
                            "test_at": str(
                                (test_state_snapshot.get(aid) or {}).get("at") or "-"
                            ),
                            "access_token": access_token,
                            "is_dup": False,
                        }
                    )

                return page_now, pages_now, total_now, rows_page

            def _flatten_rows() -> list[dict[str, Any]]:
                out: list[dict[str, Any]] = []
                for p in sorted(page_rows):
                    out.extend(page_rows[p])
                return out

            first_page, pages, total, first_rows = _fetch_one_page(1)
            page_rows[first_page] = first_rows
            self.log(f"列表第 {first_page}/{pages} 页：{len(first_rows)} 条")

            with self._lock:
                self._remote_rows = _flatten_rows()
                self._remote_total = total
                self._remote_pages = pages
                self._refresh_remote_rows_derived_locked()

            if pages > 1:
                worker_count = min(fetch_workers, pages - 1)
                self.log(f"并发拉取剩余页：{pages - 1} 页，线程 {worker_count}")
                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    future_to_page = {
                        executor.submit(_fetch_one_page, p): p for p in range(2, pages + 1)
                    }
                    for future in as_completed(future_to_page):
                        page_req = future_to_page[future]
                        try:
                            p_no, p_pages, p_total, p_rows = future.result()
                        except Exception as e:
                            for f in future_to_page:
                                if f is not future:
                                    f.cancel()
                            raise RuntimeError(f"第 {page_req} 页拉取失败: {e}") from e

                        page_rows[p_no] = p_rows
                        if p_total > total:
                            total = p_total
                        if p_pages > pages:
                            pages = p_pages

                        self.log(f"列表第 {p_no}/{pages} 页：{len(p_rows)} 条")
                        with self._lock:
                            self._remote_rows = _flatten_rows()
                            self._remote_total = total
                            self._remote_pages = pages
                            self._refresh_remote_rows_derived_locked()

            rows = _flatten_rows()

            with self._lock:
                self._remote_rows = rows
                self._remote_total = total
                self._remote_pages = pages
                self._refresh_remote_rows_derived_locked()
                self._remote_sync_status_ready = True

            self.log(f"循环拉取完成：{pages} 页，{total} 条，额度已同步")
            return {
                "items": rows,
                "total": total,
                "pages": pages,
                "loaded": len(rows),
            }
        except Exception as e:
            self.log(f"循环拉取失败: {e}")
            raise RuntimeError(_hint_connect_error(str(e))) from e
        finally:
            with self._lock:
                self._remote_busy = False

    def remote_cache(self) -> dict[str, Any]:
        with self._lock:
            rows: list[dict[str, Any]] = []
            for it in self._remote_rows:
                row = dict(it)
                row.setdefault("test_status", "未测试")
                row.setdefault("test_result", "-")
                row.setdefault("test_at", "-")
                row.setdefault("is_dup", False)
                rows.append(row)
            return {
                "items": rows,
                "total": self._remote_total,
                "pages": self._remote_pages,
                "loaded": len(rows),
                "provider": self._normalize_remote_account_provider(
                    self.cfg.get("remote_account_provider") or "sub2api"
                ),
                "ready": self._remote_sync_status_ready,
                "testing": self._remote_test_busy,
                "test_total": int(self._remote_test_stats.get("total", 0)),
                "test_done": int(self._remote_test_stats.get("done", 0)),
                "test_ok": int(self._remote_test_stats.get("ok", 0)),
                "test_fail": int(self._remote_test_stats.get("fail", 0)),
            }

    def remote_access_token(self, account_id: Any = "", file_name: Any = "") -> dict[str, Any]:
        """按账号获取 access_token（CLIProxyAPI 支持 download 接口兜底）。"""
        aid = str(account_id or "").strip()
        fname = str(file_name or "").strip()

        provider = self._normalize_remote_account_provider(
            self.cfg.get("remote_account_provider") or "sub2api"
        )

        with self._lock:
            rows = [dict(x) for x in self._remote_rows]

        target: dict[str, Any] | None = None
        if aid:
            for row in rows:
                if str(row.get("id") or "").strip() == aid:
                    target = row
                    break
        if target is None and fname:
            for row in rows:
                if str(row.get("file_name") or "").strip() == fname:
                    target = row
                    break

        if target is None and rows:
            # 未命中时保留空 target，不做猜测。
            target = None

        cached = str(((target or {}).get("access_token")) or "").strip()
        if cached:
            return {
                "id": str((target or {}).get("id") or aid),
                "file_name": str((target or {}).get("file_name") or fname),
                "access_token": cached,
                "source": "cache",
            }

        if provider != "cliproxyapi":
            raise ValueError("当前账号未提供可复制的 access_token")

        if not fname:
            fname = str((target or {}).get("file_name") or "").strip()
        if not fname:
            maybe_id = str((target or {}).get("id") or aid).strip()
            if maybe_id.endswith(".json"):
                fname = maybe_id
        if not fname:
            raise ValueError("缺少账号文件名，无法通过 CLIProxyAPI 下载 token")

        base, auth, verify_ssl, proxy_arg = self._cliproxy_management_context()
        headers = {
            "Accept": "application/json",
            "Authorization": auth,
        }
        name_candidates = [fname]
        try:
            alt = urllib.parse.unquote(fname)
            if alt and alt not in name_candidates:
                name_candidates.append(alt)
        except Exception:
            pass

        code = -1
        text = ""
        used_name = fname
        for name_try in name_candidates:
            qs = urllib.parse.urlencode({"name": name_try})
            url = f"{base.rstrip('/')}/auth-files/download?{qs}"
            c, t = _http_get(
                url,
                headers,
                verify_ssl=verify_ssl,
                timeout=90,
                proxy=proxy_arg,
            )
            code, text = c, t
            if 200 <= code < 300:
                used_name = name_try
                break

        if not (200 <= code < 300):
            snippet = str(text or "").replace("\n", " ")[:260]
            raise RuntimeError(f"下载账号文件失败 HTTP {code}: {snippet}")

        payload: Any = {}
        raw = str(text or "").strip()
        if raw:
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {}

        token = self._extract_remote_item_access_token(payload)
        if not token and isinstance(payload, dict):
            content = payload.get("content")
            if isinstance(content, str):
                c = content.strip()
                if c:
                    try:
                        content_obj = json.loads(c)
                    except Exception:
                        content_obj = {}
                    token = self._extract_remote_item_access_token(content_obj)

        if not token:
            raise RuntimeError("下载账号文件成功，但未解析到 access_token")

        with self._lock:
            for row in self._remote_rows:
                rid = str(row.get("id") or "").strip()
                rfile = str(row.get("file_name") or "").strip()
                if (aid and rid == aid) or (used_name and rfile == used_name) or (fname and rfile == fname):
                    row["access_token"] = token

        return {
            "id": str((target or {}).get("id") or aid),
            "file_name": used_name,
            "access_token": token,
            "source": "download",
        }

    @staticmethod
    def _consume_test_event_stream(resp) -> tuple[bool, str, str]:
        return _remote_consume_test_event_stream(resp)

    @staticmethod
    def _is_ssl_retryable_error(msg: str) -> bool:
        return _remote_is_ssl_retryable_error(msg)

    @staticmethod
    def _is_token_invalidated_error(msg: str) -> bool:
        return _remote_is_token_invalidated_error(msg)

    @staticmethod
    def _is_account_deactivated_error(msg: str) -> bool:
        return _remote_is_account_deactivated_error(msg)

    @staticmethod
    def _is_rate_limited_error(msg: str) -> bool:
        return _remote_is_rate_limited_error(msg)

    @staticmethod
    def _refresh_api_success(code: int, text: str) -> tuple[bool, str]:
        return _remote_refresh_api_success(code, text)

    def _try_refresh_remote_token(
        self,
        aid: str,
        *,
        base: str,
        auth: str,
        verify_ssl: bool,
        proxy_arg: str | None,
    ) -> tuple[bool, str, str]:
        return _remote_try_refresh_remote_token(
            self,
            aid,
            base=base,
            auth=auth,
            verify_ssl=verify_ssl,
            proxy_arg=proxy_arg,
        )

    def _set_remote_test_state(
        self,
        account_id: str,
        *,
        status_text: str,
        summary: str,
        duration_ms: int,
    ) -> None:
        _remote_set_remote_test_state(
            self,
            account_id,
            status_text=status_text,
            summary=summary,
            duration_ms=duration_ms,
        )

    def batch_test_remote_accounts(self, ids: list[Any]) -> dict[str, Any]:
        return _remote_batch_test_remote_accounts(self, ids)

    def refresh_remote_tokens(self, ids: list[Any]) -> dict[str, Any]:
        return _remote_refresh_remote_tokens(self, ids)

    def revive_remote_tokens(self, ids: list[Any]) -> dict[str, Any]:
        return _remote_revive_remote_tokens(self, ids)

    def _delete_remote_accounts_cliproxy(
        self,
        ordered_ids: list[str],
        delete_local: bool = False,
    ) -> dict[str, Any]:
        base, auth, verify_ssl, proxy_arg = self._cliproxy_management_context()
        headers = {
            "Accept": "application/json",
            "Authorization": auth,
        }

        with self._lock:
            row_by_id = {
                str(row.get("id") or "").strip(): dict(row)
                for row in self._remote_rows
            }

        ok = 0
        fail = 0
        deleted_ids: set[str] = set()
        deleted_emails: set[str] = set()
        results: list[dict[str, Any]] = []

        for i, aid in enumerate(ordered_ids, start=1):
            row = row_by_id.get(aid) or {}
            file_name = str(row.get("file_name") or row.get("name") or aid).strip()
            runtime_only = bool(row.get("runtime_only"))
            if runtime_only:
                fail += 1
                summary = "runtime_only 账号无法通过文件接口删除"
                results.append({"id": aid, "success": False, "summary": summary})
                self.log(f"[批量删除-CLIProxyAPI] id={aid} 失败: {summary}")
                continue

            self.log(f"[批量删除-CLIProxyAPI] 开始 {i}/{len(ordered_ids)}: id={aid} name={file_name}")
            q = urllib.parse.urlencode({"name": file_name})
            url = f"{base.rstrip('/')}/auth-files?{q}"
            code, text = _http_delete(
                url,
                headers,
                verify_ssl=verify_ssl,
                timeout=60,
                proxy=proxy_arg,
            )

            success = False
            summary = ""
            if 200 <= code < 300:
                if (text or "").strip():
                    try:
                        j = json.loads(text)
                    except Exception:
                        j = {}
                    if isinstance(j, dict) and str(j.get("status") or "").lower() in {"ok", "partial"}:
                        success = True
                        summary = "已删除"
                    elif isinstance(j, dict) and j.get("error"):
                        summary = str(j.get("error") or "删除失败")
                    else:
                        success = True
                        summary = "已删除"
                else:
                    success = True
                    summary = "已删除"
            else:
                snippet = (text or "")[:220].replace("\n", " ")
                summary = f"HTTP {code}: {snippet}"

            if success:
                ok += 1
                deleted_ids.add(aid)
                em = self._extract_email_like_text(
                    row.get("email") or row.get("name") or row.get("groups") or row.get("file_name")
                )
                if em:
                    deleted_emails.add(em)
                self.log(f"[批量删除-CLIProxyAPI] id={aid} 成功")
            else:
                fail += 1
                self.log(f"[批量删除-CLIProxyAPI] id={aid} 失败: {summary}")

            results.append(
                {
                    "id": aid,
                    "success": success,
                    "summary": summary,
                }
            )

        if deleted_ids:
            with self._lock:
                self._remote_rows = [
                    row
                    for row in self._remote_rows
                    if str(row.get("id") or "").strip() not in deleted_ids
                ]
                for aid in deleted_ids:
                    self._remote_test_state.pop(aid, None)
                self._refresh_remote_rows_derived_locked()
                self._remote_total = max(0, int(self._remote_total) - len(deleted_ids))

        self.log(f"[批量删除-CLIProxyAPI] 结束：成功 {ok}，失败 {fail}")
        local_deleted = 0
        if delete_local and deleted_emails:
            try:
                local_deleted = int(
                    (_data_delete_local_accounts_db_only(self, sorted(deleted_emails)) or {}).get("deleted") or 0
                )
            except Exception as e:
                self.log(f"[批量删除-CLIProxyAPI] 本地数据库删除失败: {e}")
        return {
            "ok": ok,
            "fail": fail,
            "total": len(ordered_ids),
            "deleted": sorted(deleted_ids),
            "local_deleted": int(local_deleted),
            "results": results,
        }

    def delete_remote_accounts(self, ids: list[Any], delete_local: bool = False) -> dict[str, Any]:
        """批量删除远端账号。"""
        ordered_ids: list[str] = []
        seen: set[str] = set()
        for raw in ids:
            aid = str(raw).strip()
            if not aid or aid in seen:
                continue
            seen.add(aid)
            ordered_ids.append(aid)
        if not ordered_ids:
            raise ValueError("请先选择要删除的账号")

        with self._lock:
            if self._remote_busy:
                raise RuntimeError("服务端列表拉取中，请稍后再删")
            if self._remote_test_busy:
                raise RuntimeError("批量测试进行中，请稍后再删")

        remote_provider = self._normalize_remote_account_provider(
            self.cfg.get("remote_account_provider") or "sub2api"
        )
        if remote_provider == "cliproxyapi":
            return self._delete_remote_accounts_cliproxy(ordered_ids, delete_local)

        tok = str(self.cfg.get("accounts_sync_bearer_token") or "").strip()
        base = str(self.cfg.get("accounts_list_api_base") or "").strip()
        if not tok:
            raise ValueError("请先填写 Bearer Token")
        if not base:
            raise ValueError("请先填写账号列表 API")

        verify_ssl = bool(self.cfg.get("openai_ssl_verify", True))
        proxy_arg = str(self.cfg.get("proxy") or "").strip() or None
        auth = tok if tok.lower().startswith("bearer ") else f"Bearer {tok}"

        ok = 0
        fail = 0
        deleted_ids: set[str] = set()
        deleted_emails: set[str] = set()
        results: list[dict[str, Any]] = []

        with self._lock:
            row_by_id = {
                str(row.get("id") or "").strip(): dict(row)
                for row in self._remote_rows
            }

        for i, aid in enumerate(ordered_ids, start=1):
            self.log(f"[批量删除] 开始 {i}/{len(ordered_ids)}: id={aid}")
            url = f"{base.rstrip('/')}/{urllib.parse.quote(aid)}"
            code, text = _http_delete(
                url,
                {
                    "Accept": "application/json",
                    "Authorization": auth,
                },
                verify_ssl=verify_ssl,
                timeout=60,
                proxy=proxy_arg,
            )

            success = False
            summary = ""
            if 200 <= code < 300:
                if (text or "").strip():
                    try:
                        j = json.loads(text)
                    except Exception:
                        j = {}
                    if isinstance(j, dict) and "code" in j:
                        try:
                            code_val = int(j.get("code") or 0)
                        except Exception:
                            code_val = -1
                        if code_val != 0:
                            success = False
                            summary = str(j.get("message") or "删除失败")
                        else:
                            success = True
                            summary = "已删除"
                    else:
                        success = True
                        summary = "已删除"
                else:
                    success = True
                    summary = "已删除"
            else:
                snippet = (text or "")[:220].replace("\n", " ")
                summary = f"HTTP {code}: {snippet}"

            if success:
                ok += 1
                deleted_ids.add(aid)
                row = row_by_id.get(aid) or {}
                em = self._extract_email_like_text(
                    row.get("email") or row.get("name") or row.get("groups") or row.get("file_name")
                )
                if em:
                    deleted_emails.add(em)
                self.log(f"[批量删除] id={aid} 成功")
            else:
                fail += 1
                self.log(f"[批量删除] id={aid} 失败: {summary}")

            results.append(
                {
                    "id": aid,
                    "success": success,
                    "summary": summary,
                }
            )

        if deleted_ids:
            with self._lock:
                self._remote_rows = [
                    row
                    for row in self._remote_rows
                    if str(row.get("id") or "").strip() not in deleted_ids
                ]
                for aid in deleted_ids:
                    self._remote_test_state.pop(aid, None)
                self._refresh_remote_rows_derived_locked()
                self._remote_total = max(0, int(self._remote_total) - len(deleted_ids))

        self.log(f"[批量删除] 结束：成功 {ok}，失败 {fail}")
        local_deleted = 0
        if delete_local and deleted_emails:
            try:
                local_deleted = int(
                    (_data_delete_local_accounts_db_only(self, sorted(deleted_emails)) or {}).get("deleted") or 0
                )
            except Exception as e:
                self.log(f"[批量删除] 本地数据库删除失败: {e}")
        return {
            "ok": ok,
            "fail": fail,
            "total": len(ordered_ids),
            "deleted": sorted(deleted_ids),
            "local_deleted": int(local_deleted),
            "results": results,
        }

    def remote_list_groups(self) -> dict[str, Any]:
        """获取管理端分组列表。"""
        remote_provider = self._normalize_remote_account_provider(
            self.cfg.get("remote_account_provider") or "sub2api"
        )
        if remote_provider == "cliproxyapi":
            return {"items": [], "total": 0}

        tok = str(self.cfg.get("accounts_sync_bearer_token") or "").strip()
        base = str(self.cfg.get("accounts_list_api_base") or "").strip()
        tz = str(
            self.cfg.get(
                "accounts_list_timezone",
                DEFAULT_CONFIG["accounts_list_timezone"],
            )
            or "Asia/Shanghai"
        ).strip() or "Asia/Shanghai"
        if not tok:
            raise ValueError("请先填写 Bearer Token")
        if not base:
            raise ValueError("请先填写账号列表 API")

        verify_ssl = bool(self.cfg.get("openai_ssl_verify", True))
        proxy_arg = str(self.cfg.get("proxy") or "").strip() or None
        auth = tok if tok.lower().startswith("bearer ") else f"Bearer {tok}"

        list_base = base.rstrip("/")
        if list_base.endswith("/accounts"):
            admin_base = list_base[: -len("/accounts")]
        elif "/accounts/" in list_base:
            admin_base = list_base.split("/accounts/", 1)[0]
        elif "/accounts" in list_base:
            admin_base = list_base.rsplit("/accounts", 1)[0]
        else:
            raise ValueError("账号列表 API 地址格式不正确，需包含 /accounts 路径")

        qs = urllib.parse.urlencode(
            {
                "page": "1",
                "page_size": "100",
                "status": "",
                "timezone": tz,
            }
        )
        url = f"{admin_base.rstrip('/')}/groups?{qs}"
        code, text = _http_get(
            url,
            {
                "Accept": "application/json",
                "Authorization": auth,
            },
            verify_ssl=verify_ssl,
            timeout=60,
            proxy=proxy_arg,
        )
        if not (200 <= code < 300):
            raise RuntimeError(f"获取分组失败 HTTP {code}: {(text or '')[:300]}")
        try:
            j = json.loads(text)
        except Exception as e:
            raise RuntimeError(f"获取分组失败：响应解析异常 {e}") from e
        if isinstance(j, dict) and ("code" in j):
            try:
                code_val = int(j.get("code") or 0)
            except Exception:
                code_val = -1
            if code_val != 0:
                raise RuntimeError(str(j.get("message") or "获取分组失败"))
        elif isinstance(j, dict) and ("success" in j):
            if not bool(j.get("success")):
                raise RuntimeError(str(j.get("message") or "获取分组失败"))
        data = j.get("data") if isinstance(j, dict) else {}
        items = data.get("items") if isinstance(data, dict) else []
        if not isinstance(items, list):
            items = []

        out: list[dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            gid = it.get("id")
            try:
                gid_int = int(gid)
            except Exception:
                continue
            name = str(it.get("name") or f"分组#{gid_int}").strip() or f"分组#{gid_int}"
            out.append(
                {
                    "id": gid_int,
                    "name": name,
                    "status": str(it.get("status") or ""),
                }
            )
        return {"items": out, "total": len(out)}

    def remote_bulk_update_groups(self, account_ids: list[Any], group_ids: list[Any]) -> dict[str, Any]:
        """批量给服务端账号分配分组。"""
        remote_provider = self._normalize_remote_account_provider(
            self.cfg.get("remote_account_provider") or "sub2api"
        )
        if remote_provider == "cliproxyapi":
            raise ValueError("CLIProxyAPI 不支持分组接口")

        ordered_account_ids: list[int] = []
        seen_accounts: set[int] = set()
        for raw in account_ids:
            try:
                aid = int(str(raw).strip())
            except Exception:
                continue
            if aid <= 0 or aid in seen_accounts:
                continue
            seen_accounts.add(aid)
            ordered_account_ids.append(aid)
        if not ordered_account_ids:
            raise ValueError("请先选择要操作的账号")

        ordered_group_ids: list[int] = []
        seen_groups: set[int] = set()
        for raw in group_ids:
            try:
                gid = int(str(raw).strip())
            except Exception:
                continue
            if gid <= 0 or gid in seen_groups:
                continue
            seen_groups.add(gid)
            ordered_group_ids.append(gid)
        if not ordered_group_ids:
            raise ValueError("请先选择至少一个分组")

        tok = str(self.cfg.get("accounts_sync_bearer_token") or "").strip()
        base = str(self.cfg.get("accounts_list_api_base") or "").strip()
        if not tok:
            raise ValueError("请先填写 Bearer Token")
        if not base:
            raise ValueError("请先填写账号列表 API")

        verify_ssl = bool(self.cfg.get("openai_ssl_verify", True))
        proxy_arg = str(self.cfg.get("proxy") or "").strip() or None
        auth = tok if tok.lower().startswith("bearer ") else f"Bearer {tok}"

        list_base = base.rstrip("/")
        if list_base.endswith("/accounts"):
            admin_base = list_base[: -len("/accounts")]
        elif "/accounts/" in list_base:
            admin_base = list_base.split("/accounts/", 1)[0]
        elif "/accounts" in list_base:
            admin_base = list_base.rsplit("/accounts", 1)[0]
        else:
            raise ValueError("账号列表 API 地址格式不正确，需包含 /accounts 路径")

        url = f"{admin_base.rstrip('/')}/accounts/bulk-update"
        body_obj = {
            "account_ids": ordered_account_ids,
            "group_ids": ordered_group_ids,
        }
        body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
        code, text = _http_post_json(
            url,
            body,
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": auth,
            },
            verify_ssl=verify_ssl,
            timeout=90,
            proxy=proxy_arg,
        )
        if not (200 <= code < 300):
            raise RuntimeError(f"批量分配分组失败 HTTP {code}: {(text or '')[:300]}")
        try:
            j = json.loads(text) if (text or "").strip() else {}
        except Exception as e:
            raise RuntimeError(f"批量分配分组失败：响应解析异常 {e}") from e
        if isinstance(j, dict) and ("code" in j):
            try:
                code_val = int(j.get("code") or 0)
            except Exception:
                code_val = -1
            if code_val != 0:
                raise RuntimeError(str(j.get("message") or "批量分配分组失败"))
        elif isinstance(j, dict) and ("success" in j):
            if not bool(j.get("success")):
                raise RuntimeError(str(j.get("message") or "批量分配分组失败"))
        return {
            "ok": len(ordered_account_ids),
            "account_ids": ordered_account_ids,
            "group_ids": ordered_group_ids,
            "raw": j,
        }

__all__ = ["StdoutCapture", "RegisterService"]

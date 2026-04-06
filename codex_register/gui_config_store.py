from __future__ import annotations

import json
import os
from typing import Any

CONFIG_FILE = "gui_config.json"
ACCOUNTS_TXT = "accounts.txt"
MAILFREE_DEFAULT_BASE_URL = "https://mailfree.example.workers.dev"

# 默认配置（缺省键在 load_config 时与文件/.env 合并）
DEFAULT_CONFIG = {
    "num_accounts": 1,
    "num_files": 1,
    "concurrency": 1,
    "sleep_min": 5,
    "sleep_max": 30,
    "fast_mode": False,
    "retry_403_wait_sec": 10,
    "proxy": "",
    "flclash_enable_switch": False,
    "flclash_controller": "127.0.0.1:9090",
    "flclash_secret": "",
    "flclash_group": "PROXY",
    "flclash_switch_policy": "round_robin",
    "flclash_switch_wait_sec": 1.2,
    "flclash_rotate_every": 3,
    "flclash_delay_test_url": "https://www.gstatic.com/generate_204",
    "flclash_delay_timeout_ms": 4000,
    "flclash_delay_max_ms": 1800,
    "flclash_delay_retry": 1,
    "remote_test_concurrency": 4,
    "remote_test_ssl_retry": 2,
    "remote_revive_concurrency": 4,
    "remote_refresh_concurrency": 4,
    "mail_delete_concurrency": 4,
    "worker_domain": "",
    "mail_domains": "",
    "freemail_username": "",
    "freemail_password": "",
    "cf_temp_base_url": "",
    "cf_temp_mail_domains": "",
    "cf_api_token": "",
    "cf_account_id": "",
    "cf_worker_script": "mailfree",
    "cf_worker_mail_domain_binding": "MAIL_DOMAIN",
    "cf_dns_target_domain": "",
    "cf_temp_admin_auth": "",
    "cloudmail_api_url": "",
    "cloudmail_admin_email": "",
    "cloudmail_admin_password": "",
    "mail_curl_api_base": "",
    "mail_curl_key": "",
    "luckyous_api_base": "https://mails.luckyous.com",
    "luckyous_api_key": "",
    "luckyous_project_code": "",
    "luckyous_email_type": "ms_graph",
    "luckyous_domain": "",
    "luckyous_variant_mode": "",
    "luckyous_specified_email": "",
    "mail_service_provider": "mailfree",
    "graph_accounts_mode": "file",
    "graph_accounts_file": "",
    "graph_api_base_url": "",
    "graph_api_token": "",
    "graph_tenant": "common",
    "graph_fetch_mode": "graph_api",
    "graph_pre_refresh_before_run": True,
    "gmail_imap_user": "",
    "gmail_imap_pass": "",
    "gmail_alias_emails": "",
    "gmail_imap_server": "imap.gmail.com",
    "gmail_imap_port": 993,
    "gmail_alias_tag_len": 8,
    "gmail_alias_mix_googlemail": True,
    "cf_routing_api_token": "",
    "cf_routing_zone_id": "",
    "cf_routing_domain": "",
    "cf_routing_cleanup": True,
    "gmail_api_client_id": "",
    "gmail_api_client_secret": "",
    "gmail_api_refresh_token": "",
    "gmail_api_user": "",
    "hero_sms_enabled": False,
    "hero_sms_api_key": "",
    "hero_sms_service": "",
    "hero_sms_country": "US",
    "hero_sms_max_price": 2.0,
    "hero_sms_reuse_phone": False,
    "hero_sms_auto_pick_country": False,
    "mail_domain_allowlist": [],
    "mailbox_custom_enabled": False,
    "mailbox_prefix": "",
    "mailbox_random_len": 0,
    "mail_domain_error_counts": {},
    "mail_domain_registered_counts": {},
    "json_file_notes": {},
    "local_cpa_test_state": {},
    "mailfree_random_domain": True,
    "register_random_fingerprint": True,
    "register_test_mode_passwordless": False,
    "openai_ssl_verify": True,
    "skip_net_check": False,
    "accounts_sync_api_url": "",
    "accounts_sync_bearer_token": "",
    "accounts_list_api_base": "",
    "remote_account_provider": "sub2api",
    "cliproxy_api_base": "",
    "cliproxy_management_key": "",
    "accounts_list_page_size": 10,
    "accounts_list_fetch_workers": 4,
    "accounts_list_ssl_retry": 3,
    "accounts_list_ssl_retry_wait_sec": 0.8,
    "accounts_list_timezone": "Asia/Shanghai",
    "codex_export_dir": "",
}


def _parse_env(path: str = ".env") -> dict[str, str]:
    """简易 .env 解析（仅用于首次补全 Worker 等配置）。"""
    kv: dict[str, str] = {}
    if not os.path.exists(path):
        return kv
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                    v = v[1:-1]
                if k:
                    kv[k] = v
    except Exception:
        pass
    return kv


def load_config() -> dict[str, Any]:
    """加载 gui_config.json，并可在 Worker 为空时用 .env 补全后回写。"""
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass

    if not cfg.get("worker_domain"):
        env = _parse_env()
        mode = str(
            env.get("MAIL_SERVICE_PROVIDER", env.get("EMAIL_API_MODE", "mailfree"))
            or "mailfree"
        ).strip()
        cfg["worker_domain"] = env.get("WORKER_DOMAIN", "") or MAILFREE_DEFAULT_BASE_URL
        cfg["mail_domains"] = env.get("MAIL_DOMAINS", "")
        cfg["freemail_username"] = env.get("FREEMAIL_USERNAME", "")
        cfg["freemail_password"] = env.get("FREEMAIL_PASSWORD", "")
        cfg["cf_temp_base_url"] = env.get(
            "CF_TEMP_BASE_URL",
            env.get("CF_TEMP_WORKER_DOMAIN", env.get("WORKER_DOMAIN", "")),
        )
        cfg["cf_temp_mail_domains"] = env.get(
            "CF_TEMP_MAIL_DOMAINS",
            env.get("MAIL_DOMAINS", ""),
        )
        cfg["cf_api_token"] = env.get("CF_API_TOKEN", env.get("CLOUDFLARE_API_TOKEN", ""))
        cfg["cf_account_id"] = env.get("CF_ACCOUNT_ID", env.get("CLOUDFLARE_ACCOUNT_ID", ""))
        cfg["cf_worker_script"] = env.get("CF_WORKER_SCRIPT", env.get("WORKER_SCRIPT_NAME", "mailfree"))
        cfg["cf_worker_mail_domain_binding"] = env.get("CF_WORKER_MAIL_DOMAIN_BINDING", "MAIL_DOMAIN")
        cfg["cf_dns_target_domain"] = env.get("CF_DNS_TARGET_DOMAIN", "")
        cfg["cf_temp_admin_auth"] = env.get("CF_TEMP_ADMIN_AUTH", env.get("ADMIN_AUTH", ""))
        cfg["cloudmail_api_url"] = env.get("CLOUDMAIL_API_URL", env.get("CM_API_URL", ""))
        cfg["cloudmail_admin_email"] = env.get("CLOUDMAIL_ADMIN_EMAIL", env.get("CM_ADMIN_EMAIL", ""))
        cfg["cloudmail_admin_password"] = env.get("CLOUDMAIL_ADMIN_PASSWORD", env.get("CM_ADMIN_PASS", ""))
        cfg["mail_curl_api_base"] = env.get("MAIL_CURL_API_BASE", env.get("MC_API_BASE", ""))
        cfg["mail_curl_key"] = env.get("MAIL_CURL_KEY", env.get("MC_KEY", ""))
        cfg["luckyous_api_base"] = env.get("LUCKYOUS_API_BASE", "https://mails.luckyous.com")
        cfg["luckyous_api_key"] = env.get("LUCKYOUS_API_KEY", "")
        cfg["luckyous_project_code"] = env.get("LUCKYOUS_PROJECT_CODE", "")
        cfg["luckyous_email_type"] = env.get("LUCKYOUS_EMAIL_TYPE", "ms_graph")
        cfg["luckyous_domain"] = env.get("LUCKYOUS_DOMAIN", "")
        cfg["luckyous_variant_mode"] = env.get("LUCKYOUS_VARIANT_MODE", "")
        cfg["luckyous_specified_email"] = env.get("LUCKYOUS_SPECIFIED_EMAIL", "")
        cfg["mail_service_provider"] = mode
        cfg["graph_accounts_mode"] = env.get("GRAPH_ACCOUNTS_MODE", "file")
        cfg["remote_account_provider"] = env.get("REMOTE_ACCOUNT_PROVIDER", cfg.get("remote_account_provider", "sub2api"))
        cfg["graph_api_base_url"] = env.get(
            "GRAPH_API_BASE_URL",
            env.get("GRAPH_API_URL", ""),
        )
        cfg["graph_api_token"] = env.get(
            "GRAPH_API_TOKEN",
            env.get("MAIL_API_TOKEN", ""),
        )
        cfg["cliproxy_api_base"] = env.get("CLIPROXY_API_BASE", env.get("CLIPROXY_MANAGEMENT_API", ""))
        cfg["cliproxy_management_key"] = env.get("CLIPROXY_MANAGEMENT_KEY", env.get("MANAGEMENT_KEY", ""))
        try:
            cfg["flclash_rotate_every"] = int(env.get("FLCLASH_ROTATE_EVERY", "3") or 3)
        except Exception:
            cfg["flclash_rotate_every"] = 3
        cfg["cf_routing_api_token"] = env.get("CF_ROUTING_API_TOKEN", env.get("CF_API_TOKEN", ""))
        cfg["cf_routing_zone_id"] = env.get("CF_ROUTING_ZONE_ID", env.get("CF_ZONE_ID", ""))
        cfg["cf_routing_domain"] = env.get("CF_ROUTING_DOMAIN", env.get("EMAIL_DOMAIN", ""))
        cleanup_v = env.get("CF_ROUTING_CLEANUP", "1").strip().lower()
        cfg["cf_routing_cleanup"] = cleanup_v not in ("0", "false", "no")
        cfg["gmail_api_client_id"] = env.get("GMAIL_API_CLIENT_ID", env.get("GMAIL_CLIENT_ID", ""))
        cfg["gmail_api_client_secret"] = env.get("GMAIL_API_CLIENT_SECRET", env.get("GMAIL_CLIENT_SECRET", ""))
        cfg["gmail_api_refresh_token"] = env.get("GMAIL_API_REFRESH_TOKEN", env.get("GMAIL_REFRESH_TOKEN", ""))
        cfg["gmail_api_user"] = env.get("GMAIL_API_USER", env.get("GMAIL_USER", ""))
        cfg["gmail_imap_user"] = env.get("GMAIL_IMAP_USER", env.get("IMAP_USER", ""))
        cfg["gmail_imap_pass"] = env.get("GMAIL_IMAP_PASS", env.get("IMAP_PASS", ""))
        cfg["gmail_alias_emails"] = env.get("GMAIL_ALIAS_EMAILS", env.get("EMAIL_LIST", ""))
        cfg["gmail_imap_server"] = (
            env.get("GMAIL_IMAP_SERVER", env.get("IMAP_SERVER", "imap.gmail.com"))
            or "imap.gmail.com"
        )
        try:
            cfg["gmail_imap_port"] = int(env.get("GMAIL_IMAP_PORT", "993") or 993)
        except Exception:
            cfg["gmail_imap_port"] = 993
        try:
            cfg["gmail_alias_tag_len"] = int(
                env.get("GMAIL_ALIAS_TAG_LEN", env.get("TAG_LENGTH", env.get("GMAIL_TAG_LEN", "8")))
                or 8
            )
        except Exception:
            cfg["gmail_alias_tag_len"] = 8
        mix_v = env.get("GMAIL_ALIAS_MIX_GOOGLEMAIL", "1").strip().lower()
        cfg["gmail_alias_mix_googlemail"] = mix_v not in ("0", "false", "no")
        ssl_v = env.get("OPENAI_SSL_VERIFY", "1").strip().lower()
        cfg["openai_ssl_verify"] = ssl_v not in ("0", "false", "no")
        skip_v = env.get("SKIP_NET_CHECK", "0").strip().lower()
        cfg["skip_net_check"] = skip_v in ("1", "true", "yes")
        fp_v = env.get("REGISTER_RANDOM_FINGERPRINT", "1").strip().lower()
        cfg["register_random_fingerprint"] = fp_v not in ("0", "false", "no")
        test_mode_v = env.get(
            "REGISTER_TEST_MODE_PASSWORDLESS",
            env.get("OPENAI_TEST_MODE", "0"),
        ).strip().lower()
        cfg["register_test_mode_passwordless"] = test_mode_v in ("1", "true", "yes", "on")
        save_config(cfg)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """保存完整配置到 gui_config.json。"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# CodeX Register

CodeX Register 是一个本地桌面化控制台，用于统一执行注册流程、邮箱池管理、SMS 接码、代理切换、本地账号库管理、以及云端账号运维。

本项目由 GPT-5.3-Codex 辅助完成。

- 前端：Vue 3 + Naive UI
- 后端：Python 本地 HTTP 服务
- 运行模式：`window`（pywebview）/ `browser`

## 0. 更新日志

### v1.0.8 (2026-04-06)

- Issue: #7 — Graph 接口模式账号列表拉取优化。
- 优先使用开放列表接口 `GET /api/open/accounts`，避免预探测 `/api/open/messages` 造成取件级慢请求。
- 当上游返回未登录/会话过期时快速失败并给出明确提示，不再继续慢速扫描。

### v1.0.7 (2026-04-06)

- Graph 接口模式账号备注更新切换为开放接口：`PATCH /api/open/accounts/:id/remark`。
- 备注更新请求体改为最小负载：`{"remark":"已注册"}`，不再依赖全量账号字段。
- 保持 token 鉴权与错误提示一致，注册链路中的“已注册账号”仍会自动回写备注。

### v1.0.6 (2026-04-06)

- Issue: #7 — Graph 接口模式注册链路异常（区域限制误归因、已注册账号处理、邮箱 OTP 重试策略）。
- 新增 Graph 双模式配置：`graph_accounts_mode=file/api`，接口模式支持仅 `graph_api_base_url + graph_api_token`。
- 修复 `Country, region, or territory not supported` 归因，统一标记为 `region_blocked` 并停止无效补位重试。
- 遇到 `Failed to register username` 时先尝试登录换 token，并将上游账号 `remark` 更新为 `已注册`。

## 1. 核心能力

- 工作台：启动/停止任务、实时日志、成功率、重试原因、SMS 消耗与余额统计。
- 邮箱体系：支持 `Cloudflare Temp Email`、[`MailFree`](https://github.com/Msg-Lbo/mailfree)、`CloudMail`、`Mail-Curl`、[`Luckyous API`](https://mails.luckyous.com/user/api-doc)、`Gmail IMAP`、`Microsoft Graph`。
- MailFree 域名配置：可在 UI 内读取 Cloudflare Zone、管理 CNAME、并将 DNS 子域名批量同步到 MailFree 域名池（`/api/domains`）。
- 代理能力：支持单代理或多代理轮换（逗号/空格/换行分隔）；支持 [`FlClash`](https://github.com/chen08209/FlClash) 动态切节点、延迟探测、自动跳过香港节点。
- 本地账号管理：SQLite（`local_accounts.db`）作为本地账号真源，支持导入、筛选、状态展示、导出与同步。
- 云端账号管理：支持 `Sub2API` 与 `CLIProxyAPI` 双模式，支持测活、刷新、删除、批量操作。
- 发布能力：推送 `v*` Tag 自动触发多平台 Release 打包。

## 2. 目录结构

```text
.
├─ gui.py
├─ VERSION
├─ REPOSITORY
├─ gui_config.example.json
├─ codex_register/
│  ├─ gui_service.py
│  ├─ gui_server_runtime.py
│  ├─ gui_frontend_app_template.html
│  ├─ gui_frontend_app_setup.js
│  ├─ r_with_pwd.py
│  ├─ mail_services.py
│  ├─ mail_providers/
│  └─ ...
├─ scripts/
└─ .github/workflows/release.yml
```

## 3. 环境要求

- Python `>= 3.10`
- 依赖安装：

```bash
pip install requests curl_cffi pywebview
```

说明：

- `window` 模式依赖 `pywebview`，Windows 需安装 WebView2 Runtime。
- 前端资源通过 CDN 加载（`unpkg.com`）。

## 4. 快速开始

1) 复制示例配置

```bash
cp gui_config.example.json gui_config.json
```

PowerShell：

```powershell
Copy-Item gui_config.example.json gui_config.json
```

2) 填写 `gui_config.json` 关键项（邮箱服务、代理、SMS、云端管理地址等）

3) 启动

```bash
python gui.py
```

说明：

- 大部分配置项可以在程序启动后直接在 GUI 中查看和修改，通常不需要手改 `gui_config.json`。

4) 可选参数

```bash
python gui.py --mode browser --host 127.0.0.1 --port 8765
python gui.py --mode browser --no-auto-open
```

## 5. 使用方法（推荐流程）

### 5.1 工作台

- 配置“计划注册数/并发/冷却/代理”后点击开始。
- 日志区会实时显示每个线程的尝试、成功、失败和重试补位。

### 5.2 邮箱设置

- 先选择 `mail_service_provider`。
- MailFree / Cloudflare Temp / CloudMail 可配置域名策略（随机域名、白名单、自定义 local-part）。
- Luckyous API 支持按项目编码自动下单邮箱并轮询验证码。
- Graph 支持文件模式与接口模式：文件模式使用账号文件；接口模式使用项目地址 + token。
- Graph 接口模式推荐对接 `microsoft-account-manager`：`https://github.com/Msg-Lbo/microsoft-account-manager`。
- Gmail 模式需使用应用专用密码（非登录密码）。

### 5.3 MailFree 域名配置（Cloudflare DNS）

在“邮箱设置 -> MailFree -> 域名配置”中：

1. 填 Cloudflare API Token，点击“刷新域名”。
2. 选择 Zone 与 CNAME 指向域名。
3. 可查看/新增/编辑/批量删除 CNAME。
4. 勾选记录后可“批量同步MailFree”，会把完整域名写入 MailFree 的 `/api/domains`。

注意：同步到 MailFree 需要该 MailFree 账号具备严格管理员权限。

Cloudflare Token 要求（用于域名配置页读取 Zone 和管理 CNAME）：

- 令牌类型：`API Token`（不是 Global API Key）。
- 推荐权限：
  - `Zone -> Zone -> Read`
  - `Zone -> DNS -> Read`
  - `Zone -> DNS -> Edit`
- 资源范围：建议仅授权需要管理的 Zone（最小权限原则）。

### 5.4 代理服务

- `proxy` 支持多条代理，格式可用逗号/空格/换行分隔，运行时按顺序轮换。
- 开启 FlClash 后，会在可用节点中切换（过滤香港节点，并做延迟检测）。
- 并发场景采用“波次切换”：每累计 `flclash_rotate_every` 次尝试后，等待当前波次结束再切下一节点。

### 5.5 账号管理

- 本地账号页：按邮箱/备注/状态搜索，支持批量选择、删除、导入到 Sub2API/CPA、导出文件。
- 云端账号页：支持分组、测活、刷新、复活（Sub2API）、删除。
- 云端删除支持附加操作：可选同时删除本地数据库中对应账号。

## 6. 配置说明（完整键）

以下与 `codex_register/gui_config_store.py` 的 `DEFAULT_CONFIG` 对应。

### 6.1 注册与运行节奏

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `num_accounts` | int | `1` | 每个批次目标成功数 |
| `num_files` | int | `1` | 批次数量 |
| `concurrency` | int | `1` | 并发线程数 |
| `sleep_min` | int | `5` | 每次尝试后最小冷却秒数 |
| `sleep_max` | int | `30` | 每次尝试后最大冷却秒数 |
| `fast_mode` | bool | `false` | 加速模式 |
| `retry_403_wait_sec` | int | `10` | 命中 403 的等待秒数 |
| `proxy` | string | `""` | 代理地址；支持多条轮换 |
| `register_random_fingerprint` | bool | `true` | 是否随机浏览器指纹 |
| `register_test_mode_passwordless` | bool | `false` | 测试模式：注册成功后走一次性验证码登录链路 |
| `openai_ssl_verify` | bool | `true` | HTTPS 证书校验 |
| `skip_net_check` | bool | `false` | 跳过出口地区检测 |

### 6.2 FlClash 动态换 IP

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `flclash_enable_switch` | bool | `false` | 是否启用 FlClash 动态切换 |
| `flclash_controller` | string | `127.0.0.1:9090` | 控制器地址 |
| `flclash_secret` | string | `""` | 控制器鉴权 secret |
| `flclash_group` | string | `PROXY` | Selector 组名 |
| `flclash_switch_policy` | string | `round_robin` | `round_robin` / `random` |
| `flclash_switch_wait_sec` | float | `1.2` | 切换后等待秒数 |
| `flclash_rotate_every` | int | `3` | 每波次尝试数（达到后切下一节点） |
| `flclash_delay_test_url` | string | `https://www.gstatic.com/generate_204` | 延迟探测 URL |
| `flclash_delay_timeout_ms` | int | `4000` | 延迟探测超时 |
| `flclash_delay_max_ms` | int | `1800` | 可用阈值 |
| `flclash_delay_retry` | int | `1` | 延迟探测重试次数 |

### 6.3 邮箱通用策略

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `mail_service_provider` | string | `mailfree` | `cloudflare_temp_email` / `mailfree` / `cloudmail` / `mail_curl` / `luckyous` / `gmail` / `graph` |
| `mail_domains` | string | `""` | 通用域名池（主要用于 Cloudflare Temp / CloudMail） |
| `mail_domain_allowlist` | array | `[]` | 注册域白名单 |
| `mailfree_random_domain` | bool | `true` | 是否随机域名 |
| `mailbox_custom_enabled` | bool | `false` | 自定义邮箱 local-part |
| `mailbox_prefix` | string | `""` | local-part 前缀 |
| `mailbox_random_len` | int | `0` | 前缀后追加随机长度 |

### 6.4 MailFree / Cloudflare Temp / Cloudflare DNS 配置

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `worker_domain` | string | `""` | MailFree 服务地址 |
| `freemail_username` | string | `""` | MailFree 用户名 |
| `freemail_password` | string | `""` | MailFree 密码 |
| `cf_temp_base_url` | string | `""` | Cloudflare Temp Email 服务地址（与 MailFree 独立） |
| `cf_temp_mail_domains` | string | `""` | Cloudflare Temp Email 域名池（与 MailFree 独立） |
| `cf_api_token` | string | `""` | Cloudflare API Token（权限建议：Zone Read + DNS Read/Edit） |
| `cf_account_id` | string | `""` | 兼容字段 |
| `cf_worker_script` | string | `mailfree` | 兼容字段 |
| `cf_worker_mail_domain_binding` | string | `MAIL_DOMAIN` | 兼容字段 |
| `cf_dns_target_domain` | string | `""` | CNAME 目标域名默认值 |
| `cf_temp_admin_auth` | string | `""` | Cloudflare Temp Email 管理员认证 |

### 6.5 CloudMail / Mail-Curl / Luckyous

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `cloudmail_api_url` | string | `""` | CloudMail API 地址 |
| `cloudmail_admin_email` | string | `""` | CloudMail 管理员邮箱 |
| `cloudmail_admin_password` | string | `""` | CloudMail 管理员密码 |
| `mail_curl_api_base` | string | `""` | Mail-Curl API 地址 |
| `mail_curl_key` | string | `""` | Mail-Curl Key |
| `luckyous_api_base` | string | `https://mails.luckyous.com` | Luckyous API 地址 |
| `luckyous_api_key` | string | `""` | Luckyous API Key（X-API-Key） |
| `luckyous_project_code` | string | `""` | Luckyous 项目编码（必填） |
| `luckyous_email_type` | string | `ms_graph` | Luckyous 邮箱类型（如 `ms_graph`） |
| `luckyous_domain` | string | `""` | Luckyous 指定域名（可选） |
| `luckyous_variant_mode` | string | `""` | Luckyous 变种模式（可选：`dot/plus/mixed/all`） |
| `luckyous_specified_email` | string | `""` | Luckyous 指定邮箱（可选，优先于 domain） |

### 6.6 Gmail / Graph

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `gmail_imap_user` | string | `""` | Gmail IMAP 账号 |
| `gmail_imap_pass` | string | `""` | Gmail 应用专用密码 |
| `gmail_alias_emails` | string | `""` | 别名邮箱池 |
| `gmail_imap_server` | string | `imap.gmail.com` | IMAP 服务器 |
| `gmail_imap_port` | int | `993` | IMAP 端口 |
| `gmail_alias_tag_len` | int | `8` | 别名 tag 长度 |
| `gmail_alias_mix_googlemail` | bool | `true` | 混用 gmail/googlemail 域名 |
| `graph_accounts_mode` | string | `file` | Graph 账号来源：`file` / `api` |
| `graph_accounts_file` | string | `""` | Graph 账号文件路径 |
| `graph_api_base_url` | string | `""` | Graph 接口模式地址（推荐 `microsoft-account-manager` 项目地址） |
| `graph_api_token` | string | `""` | Graph 接口模式 token |
| `graph_tenant` | string | `common` | Graph tenant |
| `graph_fetch_mode` | string | `graph_api` | `graph_api` / `imap_xoauth2` |
| `graph_pre_refresh_before_run` | bool | `true` | 启动前预刷新 token |

### 6.7 HeroSMS

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `hero_sms_enabled` | bool | `false` | 开启 HeroSMS |
| `hero_sms_api_key` | string | `""` | HeroSMS API Key |
| `hero_sms_service` | string | `""` | 服务代码（可自动识别） |
| `hero_sms_country` | string | `US` | 国家偏好 |
| `hero_sms_max_price` | float | `2.0` | 余额下限（美元） |
| `hero_sms_reuse_phone` | bool | `false` | 启用号码复用 |
| `hero_sms_auto_pick_country` | bool | `false` | 自动选国家 |

### 6.8 云端账号管理

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `remote_account_provider` | string | `sub2api` | 云端类型：`sub2api` / `cliproxyapi` |
| `accounts_sync_api_url` | string | `""` | 同步 API 地址 |
| `accounts_sync_bearer_token` | string | `""` | 同步 API Token |
| `accounts_list_api_base` | string | `""` | 列表 API 基地址 |
| `cliproxy_api_base` | string | `""` | CLIProxyAPI 管理地址 |
| `cliproxy_management_key` | string | `""` | CLIProxyAPI 管理密钥 |
| `accounts_list_page_size` | int | `10` | 列表每页数量 |
| `accounts_list_fetch_workers` | int | `4` | 拉取并发 |
| `accounts_list_ssl_retry` | int | `3` | SSL 重试次数 |
| `accounts_list_ssl_retry_wait_sec` | float | `0.8` | SSL 重试间隔 |
| `accounts_list_timezone` | string | `Asia/Shanghai` | 时区 |
| `remote_test_concurrency` | int | `4` | 测活并发 |
| `remote_test_ssl_retry` | int | `2` | 测活 SSL 重试 |
| `remote_refresh_concurrency` | int | `4` | 刷新并发 |
| `remote_revive_concurrency` | int | `4` | 复活并发（Sub2API） |

### 6.9 其他配置

| 键名 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `mail_delete_concurrency` | int | `4` | 邮件删除并发 |
| `codex_export_dir` | string | `""` | CPA 导出目录 |
| `mail_domain_error_counts` | object | `{}` | 域名失败计数（运行时维护） |
| `mail_domain_registered_counts` | object | `{}` | 域名成功计数（运行时维护） |
| `json_file_notes` | object | `{}` | JSON 文件备注 |
| `local_cpa_test_state` | object | `{}` | 本地账号测活状态缓存 |

## 7. Graph 账号文件格式

每行格式：

```text
email----password----client_id----refresh_token
```

示例：

```text
alice@outlook.com----pass123----xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx----0.AXEA...
bob@outlook.com----pass456----yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy----0.AXEA...
```

## 8. 常见问题

- IP 不切换：
  - 检查是否只配置了 1 条代理；
  - 多代理请使用逗号/空格/换行分隔；
  - FlClash 仅有 1 个可用非香港节点时无法切换。
- MailFree 域名同步失败：确认是严格管理员账号，且 MailFree 服务已升级到动态域名版本。
- Luckyous 下单失败：检查 API Key、项目编码与账户余额是否可用。
- `invalid_auth_step` 频繁：降低并发、提高代理质量、开启随机指纹。
- Gmail 登录失败：必须用应用专用密码。
- HeroSMS `NO_BALANCE`：充值或降低余额下限策略。

## 9. 使用协议

- 作者：`Msg-Lbo`（GitHub: `https://github.com/Msg-Lbo`）
- 协议文件：`LICENSE`
- 协议链接：`https://github.com/Msg-Lbo/codeX-register/blob/main/LICENSE`
- 允许学习研究与非商业自用；禁止商业售卖和二开后收费变现。

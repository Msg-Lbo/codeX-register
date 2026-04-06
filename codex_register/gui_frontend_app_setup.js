        const activeTab = Vue.ref("dash");
        const menuOptions = [
          { label: "工作台", key: "dash" },
          { label: "账号管理", key: "accounts" },
          { label: "邮箱设置", key: "mail" },
          { label: "SMS管理", key: "sms" },
          { label: "服务设置", key: "settings" },
          { label: "代理服务", key: "proxy" },
          { label: "运行日志", key: "logs" },
          { label: "关于", key: "about" }
        ];

        const themeOverrides = {
          common: {
            fontFamily: "Space Grotesk, PingFang SC, Microsoft YaHei, sans-serif",
            primaryColor: "#3ea6ff",
            primaryColorHover: "#74beff",
            primaryColorPressed: "#2f8bdb",
            infoColor: "#48b5ff",
            successColor: "#45d4af",
            warningColor: "#f7b267",
            errorColor: "#f46b78",
            bodyColor: "#0b1017",
            cardColor: "#111a29",
            modalColor: "#111a29",
            popoverColor: "#121d2d",
            borderColor: "#24344b",
            textColorBase: "#d9e3ef",
            textColor2: "#a9bdd2",
            textColor3: "#8ea3bb"
          },
          Layout: {
            color: "#0d1420",
            siderColor: "#0f1725",
            headerColor: "rgba(9, 15, 24, 0.85)",
            contentColor: "#0c131e",
            borderColor: "#24344b"
          },
          Card: {
            borderRadius: "14px",
            color: "rgba(16, 25, 38, 0.9)",
            titleFontSizeSmall: "15px",
            borderColor: "#2a3a51"
          },
          DataTable: {
            thColor: "#121d2d",
            tdColor: "rgba(16, 25, 38, 0.62)",
            borderColor: "#27384f",
            thTextColor: "#bfd1e4",
            tdTextColor: "#d5e2f0"
          },
          Input: {
            color: "rgba(13, 20, 32, 0.82)",
            colorFocus: "rgba(13, 20, 32, 0.92)",
            border: "1px solid #2a3a51",
            borderHover: "1px solid #3a516e",
            borderFocus: "1px solid #3ea6ff"
          },
          Alert: {
            borderRadius: "10px"
          }
        };

        const status = Vue.reactive({
          running: false,
          status_text: "就绪",
          progress: 0,
          sync_busy: false,
          remote_busy: false,
          remote_test_busy: false,
          config_ready: true,
          config_blockers: [],
          config_warnings: [],
          run_planned_total: 0,
          run_success_count: 0,
          run_retry_total: 0,
          run_success_rate: 100,
          run_last_retry_reason: "",
          run_retry_reasons_top: [],
          run_elapsed_sec: 0,
          run_avg_success_sec: 0,
          run_sms_spent_usd: 0,
          run_sms_balance_usd: -1,
          run_sms_min_balance_usd: 0
        });

        const dashForm = Vue.reactive({
          num_accounts: 1,
          concurrency: 1,
          sleep_min: 5,
          sleep_max: 30,
          fast_mode: false,
          proxy: ""
        });

        const settingsForm = Vue.reactive({
          mail_service_provider: "mailfree",
          mail_domain_allowlist: [],
          worker_domain: "",
          mail_domains: "",
          freemail_username: "",
          freemail_password: "",
          cf_temp_base_url: "",
          cf_temp_mail_domains: "",
          cf_api_token: "",
          cf_account_id: "",
          cf_worker_script: "mailfree",
          cf_worker_mail_domain_binding: "MAIL_DOMAIN",
          cf_dns_target_domain: "",
          cf_temp_admin_auth: "",
          cloudmail_api_url: "",
          cloudmail_admin_email: "",
          cloudmail_admin_password: "",
          mail_curl_api_base: "",
          mail_curl_key: "",
          luckyous_api_base: "https://mails.luckyous.com",
          luckyous_api_key: "",
          luckyous_project_code: "",
          luckyous_email_type: "ms_graph",
          luckyous_domain: "",
          luckyous_variant_mode: "",
          luckyous_specified_email: "",
          graph_accounts_mode: "file",
          graph_accounts_file: "",
          graph_api_base_url: "",
          graph_api_token: "",
          graph_tenant: "common",
          graph_fetch_mode: "graph_api",
          graph_pre_refresh_before_run: true,
          gmail_imap_user: "",
          gmail_imap_pass: "",
          gmail_alias_emails: "",
          gmail_imap_server: "imap.gmail.com",
          gmail_imap_port: 993,
          gmail_alias_tag_len: 8,
          gmail_alias_mix_googlemail: true,
          cf_routing_api_token: "",
          cf_routing_zone_id: "",
          cf_routing_domain: "",
          cf_routing_cleanup: true,
          gmail_api_client_id: "",
          gmail_api_client_secret: "",
          gmail_api_refresh_token: "",
          gmail_api_user: "",
          hero_sms_enabled: false,
          hero_sms_reuse_phone: false,
          hero_sms_api_key: "",
          hero_sms_service: "",
          hero_sms_country: "US",
          hero_sms_auto_pick_country: false,
          hero_sms_max_price: 2,
          mailfree_random_domain: true,
          mailbox_custom_enabled: false,
          mailbox_prefix: "",
          mailbox_random_len: 0,
          register_random_fingerprint: true,
          register_test_mode_passwordless: false,
          openai_ssl_verify: true,
          skip_net_check: false,
          flclash_enable_switch: false,
          flclash_controller: "127.0.0.1:9090",
          flclash_secret: "",
          flclash_group: "PROXY",
          flclash_switch_policy: "round_robin",
          flclash_switch_wait_sec: 1.2,
          flclash_rotate_every: 3,
          flclash_delay_test_url: "https://www.gstatic.com/generate_204",
          flclash_delay_timeout_ms: 4000,
          flclash_delay_max_ms: 1800,
          flclash_delay_retry: 1,
          remote_test_concurrency: 4,
          remote_test_ssl_retry: 2,
          remote_refresh_concurrency: 4,
          accounts_sync_api_url: "",
          accounts_sync_bearer_token: "",
          accounts_list_api_base: "",
          remote_account_provider: "sub2api",
          cliproxy_api_base: "",
          cliproxy_management_key: "",
          accounts_list_timezone: "Asia/Shanghai",
          codex_export_dir: ""
        });

        const loading = Vue.reactive({
          start: false,
          save: false,
          flclash_probe: false,
          json: false,
          accounts: false,
          local_delete: false,
          sync: false,
          sub2api_export: false,
          codex_export: false,
          remote: false,
          remote_groups: false,
          remote_group_update: false,
          remote_test: false,
          remote_refresh: false,
          remote_revive: false,
          remote_delete: false,
          update_check: false,
          run_stats_clear: false,
          logs: false,
          mail_overview: false,
          graph_files: false,
          mail_generate: false,
          mail_emails: false,
          mail_detail: false,
          mail_delete: false,
          mailbox_delete: false,
          mail_clear: false,
          mail_cf_zones: false,
          mail_cf_dns: false,
          mail_cf_dns_create: false,
          mail_cf_dns_update: false,
          mail_cf_dns_delete: false,
          mail_cf_worker_set: false,
          mail_cf_worker_batch: false,
          sms_overview: false,
          sms_countries: false
        });

        const jsonRows = Vue.ref([]);
        const jsonSelection = Vue.ref([]);
        const jsonNoteDraft = Vue.reactive({});
        const jsonNoteSaving = Vue.reactive({});
        const jsonInfo = Vue.reactive({ file_count: 0, account_total: 0 });

        const accountRows = Vue.ref([]);
        const accountSelection = Vue.ref([]);
        const accountSearch = Vue.ref("");
        const accountPickCount = Vue.ref(20);
        const accountInfo = Vue.reactive({ total: 0, path: "local_accounts.db", file_options: [] });
        const accountManageTab = Vue.ref("local");
        const showSub2ApiExportModal = Vue.ref(false);
        const sub2apiExportForm = Vue.reactive({
          file_count: 1,
          accounts_per_file: 50
        });

        const aboutInfo = Vue.reactive({
          name: "CodeX Register",
          version: "0.0.0-dev",
          author: "-",
          author_url: "",
          intro: "",
          license_name: "-",
          license_file: "LICENSE",
          license_exists: false,
          license_url: "",
          repo_slug: "",
          repo_url: "",
          platform: "",
          python: ""
        });
        const updateInfo = Vue.reactive({
          checked: false,
          checked_at: "",
          has_update: false,
          current_version: "",
          latest_tag: "",
          latest_name: "",
          published_at: "",
          release_url: "",
          release_notes: "",
          assets: [],
          error: ""
        });

        const remoteRows = Vue.ref([]);
        const remoteSelection = Vue.ref([]);
        const remoteSearch = Vue.ref("");
        const showRemoteDeleteModal = Vue.ref(false);
        const remoteDeleteAlsoLocal = Vue.ref(false);
        const remoteDeleteIds = Vue.ref([]);
        const remoteDeletePreview = Vue.ref("");
        const showRemoteGroupModal = Vue.ref(false);
        const remoteGroupOptions = Vue.ref([]);
        const remoteGroupSelection = Vue.ref([]);
        const remoteMeta = Vue.reactive({
          total: 0,
          pages: 1,
          loaded: 0,
          ready: false,
          testing: false,
          test_total: 0,
          test_done: 0,
          test_ok: 0,
          test_fail: 0
        });

        const mailProviders = Vue.ref([]);
        const mailProviderTab = Vue.ref("mailfree");
        const mailfreePanelTab = Vue.ref("basic");
        const graphAccountFileOptions = Vue.ref([]);
        const mailDomains = Vue.ref([]);
        const mailboxRows = Vue.ref([]);
        const mailboxSelection = Vue.ref([]);
        const mailboxSearch = Vue.ref("");
        const selectedMailbox = Vue.ref("");
        const mailRows = Vue.ref([]);
        const mailSelection = Vue.ref([]);
        const selectedMailId = Vue.ref("");
        const mailDetail = Vue.reactive({
          id: "",
          from: "",
          subject: "",
          date: "",
          content: ""
        });
        const mailState = Vue.reactive({
          provider: "mailfree",
          loaded: false,
          email_total: 0
        });
        const mailDomainErrors = Vue.reactive({});
        const mailDomainRegistered = Vue.reactive({});
        const cfZoneOptions = Vue.ref([]);
        const cfZoneId = Vue.ref("");
        const cfTargetDomain = Vue.ref("");
        const cfDnsRows = Vue.ref([]);
        const cfDnsSelection = Vue.ref([]);
        const showCfDnsAddModal = Vue.ref(false);
        const showCfDnsEditModal = Vue.ref(false);
        const cfDnsAddForm = Vue.reactive({
          count: 5,
          mode: "random",
          random_prefix: "",
          random_length: 8,
          manual_name: "",
          proxied: false,
          ttl: 1
        });
        const cfDnsEditForm = Vue.reactive({
          record_id: "",
          label: "",
          proxied: false,
          ttl: 1
        });
        const showMailModal = Vue.ref(false);
        const graphFileInputRef = Vue.ref(null);
        const mailViewCache = Vue.reactive({
          cloudflare_temp_email: {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          },
          mailfree: {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          },
          cloudmail: {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          },
          mail_curl: {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          },
          luckyous: {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          },
          graph: {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          },
          gmail: {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          },
          cf_email_routing: {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          }
        });

        const logLines = Vue.ref([]);
        const logSince = Vue.ref(0);
        const logScrollContainerRef = Vue.ref(null);
        const logAutoScrollThreshold = 48;
        const smsState = Vue.reactive({
          enabled: false,
          reuse_phone: false,
          key_configured: false,
          service: "",
          service_resolved: "",
          country: "US",
          country_resolved: -1,
          filtered_out: 0,
          min_balance_usd: 2,
          balance_usd: -1,
          balance_error: "",
          spent_usd: 0,
          updated_at: ""
        });
        const smsCountryOptions = Vue.ref([]);
        const flclashProbeForm = Vue.reactive({
          rounds: 1,
          per_round_limit: 0
        });
        const flclashProbeRows = Vue.ref([]);
        const flclashProbeMeta = Vue.reactive({
          group: "-",
          attempts: 0,
          ok: 0,
          fail: 0,
          candidate_total: 0,
          blocked_hk_count: 0,
          restored: false,
          restore_error: "",
          at: ""
        });

        let pollTimer = null;
        let pollTick = 0;
        let logUserHoldUntil = 0;

        function nextRenderFrame() {
          return new Promise((resolve) => {
            if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
              window.requestAnimationFrame(() => resolve());
              return;
            }
            setTimeout(() => resolve(), 0);
          });
        }

        function resolveLogContainer() {
          const direct = logScrollContainerRef.value;
          if (direct && typeof direct.scrollHeight === "number") {
            return direct;
          }
          if (typeof document === "undefined") return null;
          return document.querySelector(".log-scroll");
        }

        function ensureLogContainerScrollable() {
          const container = resolveLogContainer();
          if (!container) return;
          container.style.overflowY = "auto";
          container.style.overflowX = "hidden";
          container.style.touchAction = "pan-y";
        }

        function isLogNearBottom() {
          const container = resolveLogContainer();
          if (!container) return false;
          const gap = container.scrollHeight - container.scrollTop - container.clientHeight;
          return gap <= logAutoScrollThreshold;
        }

        function shouldAutoFollowLogs() {
          if (activeTab.value !== "logs") return true;
          const container = resolveLogContainer();
          if (!container) return true;
          if (Date.now() < logUserHoldUntil) return false;
          return isLogNearBottom();
        }

        function holdLogAutoFollow(ms = 6000) {
          const until = Date.now() + Math.max(800, Number(ms) || 0);
          if (until > logUserHoldUntil) {
            logUserHoldUntil = until;
          }
        }

        function onLogUserWheel(e) {
          if (activeTab.value !== "logs") return;
          const dy = Number((e && e.deltaY) || 0);
          if (dy < 0) {
            holdLogAutoFollow(10000);
            return;
          }
          if (dy > 0) {
            const container = resolveLogContainer();
            if (!container) {
              holdLogAutoFollow(4000);
              return;
            }
            const gap = container.scrollHeight - container.scrollTop - container.clientHeight;
            if (gap > logAutoScrollThreshold) {
              holdLogAutoFollow(5000);
              return;
            }
            logUserHoldUntil = 0;
          }
        }

        function onLogUserScroll() {
          if (activeTab.value !== "logs") return;
          const container = resolveLogContainer();
          if (!container) {
            holdLogAutoFollow(3000);
            return;
          }
          const gap = container.scrollHeight - container.scrollTop - container.clientHeight;
          if (gap > logAutoScrollThreshold) {
            holdLogAutoFollow(4000);
            return;
          }
          logUserHoldUntil = 0;
        }

        async function scrollLogsToBottom(force = false) {
          await Vue.nextTick();
          await nextRenderFrame();
          const container = resolveLogContainer();
          if (!container) return;
          container.scrollTop = container.scrollHeight;
          if (force) {
            await nextRenderFrame();
            container.scrollTop = container.scrollHeight;
          }
        }

        const progressPercent = Vue.computed(() => {
          const p = Number(status.progress || 0) * 100;
          return Math.max(0, Math.min(100, Math.round(p)));
        });

        const totalPlanCount = Vue.computed(() => {
          const perFile = Math.max(1, Number(dashForm.num_accounts || 1));
          return perFile;
        });

        const statusTagType = Vue.computed(() => {
          if (status.running) return "success";
          if ((status.status_text || "").includes("停止")) return "warning";
          return "default";
        });

        const runSuccessRateText = Vue.computed(() => {
          const rate = Number(status.run_success_rate || 100);
          const retry = Number(status.run_retry_total || 0);
          const success = Number(status.run_success_count || 0);
          const planned = Number(status.run_planned_total || 0);
          const elapsed = Number(status.run_elapsed_sec || 0);
          const avgSec = Number(status.run_avg_success_sec || 0);
          const plannedText = planned > 0 ? `${success}/${planned}` : `${success}`;
          return `成功率 ${rate.toFixed(2)}% · 成功 ${plannedText} · 重试 ${retry} 次 · 总耗时 ${elapsed.toFixed(1)}s · 平均 ${avgSec.toFixed(1)}s`;
        });

        const runRetryReasonText = Vue.computed(() => {
          function shortReasonLabel(raw) {
            const src = String(raw || "").trim();
            if (!src) return "未知";
            const s = src.toLowerCase();
            if (s.includes("otp") || s.includes("验证码") || s.includes("verification")) return "OTP 超时";
            if (s.includes("tls") || s.includes("ssl") || s.includes("openssl") || s.includes("curl")) return "SSL/TLS 异常";
            if (s.includes("429") || s.includes("rate limit")) return "429 限流";
            if (s.includes("no_balance") || s.includes("余额不足")) return "接码余额不足";
            if (s.includes("phone_country_blocked") || s.includes("country_blocked") || s.includes("国家受限")) return "手机号国家受限";
            if (s.includes("phone_sms_timeout") || s.includes("接码超时")) return "手机验证码超时";
            if (s.includes("add-phone") || s.includes("phone_gate") || s.includes("手机号")) return "手机号验证";
            if (s.includes("timeout") || s.includes("timed out") || s.includes("超时")) return "网络超时";
            if (s.includes("proxy") || s.includes("connection") || s.includes("refused") || s.includes("10061")) return "连接失败";
            if (src.length <= 20) return src;
            return `${src.slice(0, 20)}…`;
          }

          const retry = Number(status.run_retry_total || 0);
          if (retry <= 0) return "重试原因：无";
          const rows = Array.isArray(status.run_retry_reasons_top)
            ? status.run_retry_reasons_top
            : [];
          const txt = rows
            .slice(0, 3)
            .map((x) => `${shortReasonLabel((x && x.reason) || "")}×${Number((x && x.count) || 0)}`)
            .join("；");
          if (txt) return `重试原因：${txt}`;
          return `重试原因：${shortReasonLabel(status.run_last_retry_reason || "未知")}`;
        });

        const runSmsStatsText = Vue.computed(() => {
          const spent = Math.max(0, Number(status.run_sms_spent_usd || 0));
          const balance = Number(status.run_sms_balance_usd ?? -1);
          const minBalance = Math.max(0, Number(status.run_sms_min_balance_usd || 0));
          const balText = balance >= 0 ? `$${balance.toFixed(2)}` : "-";
          return `SMS 统计：消耗 $${spent.toFixed(2)} · 余额 ${balText} · 下限 $${minBalance.toFixed(2)}`;
        });

        const smsOverviewText = Vue.computed(() => {
          const bal = Number(smsState.balance_usd ?? -1);
          const spent = Math.max(0, Number(smsState.spent_usd || 0));
          const minBal = Math.max(0, Number(smsState.min_balance_usd || 0));
          const balText = bal >= 0 ? `$${bal.toFixed(2)}` : "-";
          const svc = String(smsState.service_resolved || smsState.service || "(auto)");
          const ctryResolved = Number(smsState.country_resolved || -1);
          const ctryCfg = String(smsState.country || "US");
          const ctryText = ctryResolved >= 0 ? `${ctryCfg} -> ${ctryResolved}` : ctryCfg;
          const reuseText = smsState.reuse_phone ? "复用手机号: 开" : "复用手机号: 关";
          const updated = String(smsState.updated_at || "-");
          return `服务 ${svc} · 国家 ${ctryText} · 余额 ${balText} · 下限 $${minBal.toFixed(2)} · 累计消耗 $${spent.toFixed(2)} · ${reuseText} · 更新时间 ${updated}`;
        });

        const remoteInfoText = Vue.computed(() => {
          const providerLabel = normalizeRemoteAccountProvider(settingsForm.remote_account_provider) === "cliproxyapi"
            ? "CLIProxyAPI"
            : "Sub2API";
          if (status.remote_test_busy || loading.remote_test) {
            const t = Number(remoteMeta.test_total || 0);
            const d = Number(remoteMeta.test_done || 0);
            const ok = Number(remoteMeta.test_ok || 0);
            const fail = Number(remoteMeta.test_fail || 0);
            return `${providerLabel} · 批量测试中 · 进度 ${d}/${t} · 成功 ${ok} · 失败 ${fail}`;
          }
          if (status.remote_busy || loading.remote) {
            if (!remoteMeta.loaded) return `${providerLabel} · 正在拉取第 1 页...`;
            return `${providerLabel} · 正在拉取中 · 已展示 ${remoteMeta.loaded} 条 · 预计 ${remoteMeta.pages} 页`;
          }
          if (!remoteMeta.loaded) {
            const t = Number(remoteMeta.test_total || 0);
            if (t > 0) {
              return `${providerLabel} · 未加载列表 · 最近测试 成功 ${remoteMeta.test_ok} · 失败 ${remoteMeta.test_fail}`;
            }
            return `${providerLabel} · 未加载`;
          }
          const base = `${providerLabel} · 已拉取 ${remoteMeta.pages} 页 · 共 ${remoteMeta.total} 条 · 已显示 ${remoteMeta.loaded} 条`;
          const t = Number(remoteMeta.test_total || 0);
          if (t > 0) {
            return `${base} · 最近测试 成功 ${remoteMeta.test_ok} · 失败 ${remoteMeta.test_fail}`;
          }
          return base;
        });

        const filteredMailboxRows = Vue.computed(() => {
          const kw = String(mailboxSearch.value || "").trim().toLowerCase();
          if (!kw) return mailboxRows.value;
          return mailboxRows.value.filter((row) => String(row.address || "").toLowerCase().includes(kw));
        });

        const mailInfoText = Vue.computed(() => {
          const dom = mailDomains.value.length;
          const box = mailboxRows.value.length;
          const em = Number(mailState.email_total || 0);
          const provider = String(mailState.provider || settingsForm.mail_service_provider || "mailfree");
          const selectedDomains = Array.isArray(settingsForm.mail_domain_allowlist)
            ? settingsForm.mail_domain_allowlist.length
            : 0;
          let regTotal = 0;
          for (const dm of mailDomains.value) {
            regTotal += Number(mailDomainRegistered[String(dm || "").toLowerCase()] || 0);
          }
          return `服务 ${provider} · 域名 ${dom} 个 · 已选域名 ${selectedDomains} 个 · 已注册 ${regTotal} 个 · 邮箱 ${box} 个 · 当前邮件 ${em} 封`;
        });

        function sanitizeMailboxPrefix(raw) {
          return String(raw || "")
            .trim()
            .replace(/[^a-zA-Z0-9._-]+/g, "")
            .slice(0, 40);
        }

        function previewRandomSuffix(len) {
          const n = Math.max(0, Math.min(32, Number(len) || 0));
          if (n <= 0) return "";
          if (n <= 12) return "x".repeat(n);
          return `${"x".repeat(12)}(+${n - 12})`;
        }

        const mailboxPatternPreviewText = Vue.computed(() => {
          if (!settingsForm.mailbox_custom_enabled) {
            return "已关闭自定义邮箱，生成时将使用接口默认规则";
          }
          const rawPrefix = String(settingsForm.mailbox_prefix || "").trim();
          const safePrefix = sanitizeMailboxPrefix(rawPrefix);
          const randomLen = Math.max(0, Math.min(32, Math.floor(Number(settingsForm.mailbox_random_len || 0))));
          const localPart = `${safePrefix}${previewRandomSuffix(randomLen)}` || "example";

          const allow = normalizeDomainList(settingsForm.mail_domain_allowlist || []);
          const cfgDomainsRaw = mailProviderTab.value === "cloudflare_temp_email"
            ? settingsForm.cf_temp_mail_domains
            : settingsForm.mail_domains;
          const cfgDomains = String(cfgDomainsRaw || "")
            .split(/[\n\r,;\s]+/)
            .map((x) => String(x || "").trim().toLowerCase())
            .filter((x) => !!x);
          const sourceDomains = allow.length
            ? allow
            : (mailDomains.value.length ? mailDomains.value : cfgDomains);
          const domain = sourceDomains.length ? String(sourceDomains[0] || "") : "domain.example";
          const domainMode = settingsForm.mailfree_random_domain
            ? `随机域名${sourceDomains.length > 1 ? `(${sourceDomains.length}个)` : ""}`
            : "固定域名";

          let tip = "";
          if (rawPrefix && !safePrefix) {
            tip = "；前缀包含非法字符，保存后会被清空";
          } else if (rawPrefix && rawPrefix !== safePrefix) {
            tip = `；已过滤为 ${safePrefix}`;
          }
          return `示例：${localPart}@${domain}（${domainMode}）${tip}`;
        });

        const gmailAliasPreviewText = Vue.computed(() => {
          const user = String(settingsForm.gmail_imap_user || "").trim().toLowerCase();
          const aliasRaw = String(settingsForm.gmail_alias_emails || "").trim();
          const aliases = aliasRaw
            ? aliasRaw
              .split(/[\n\r,;\s]+/)
              .map((x) => String(x || "").trim().toLowerCase())
              .filter((x) => x && x.includes("@"))
            : [];
          const base = String(aliases[0] || user || "name@gmail.com");
          const server = String(settingsForm.gmail_imap_server || "imap.gmail.com").trim() || "imap.gmail.com";
          const port = Math.max(1, Number(settingsForm.gmail_imap_port || 993));
          const tagLen = Math.max(1, Math.min(64, Math.floor(Number(settingsForm.gmail_alias_tag_len || 8))));
          const mixGooglemail = !!settingsForm.gmail_alias_mix_googlemail;
          const sampleTag = tagLen <= 12 ? "x".repeat(tagLen) : `${"x".repeat(12)}(+${tagLen - 12})`;

          if (!base.includes("@")) {
            return `示例：name+${sampleTag}@gmail.com · IMAP ${server}:${port}`;
          }
          const parts = base.split("@");
          const local = String(parts[0] || "name").split("+", 1)[0];
          const domain = String(parts[1] || "gmail.com").toLowerCase();
          const aliasDomain = mixGooglemail && (domain === "gmail.com" || domain === "googlemail.com")
            ? "gmail.com / googlemail.com"
            : domain;
          return `示例：${local}+${sampleTag}@${aliasDomain} · IMAP ${server}:${port}`;
        });

        const gmailAliasMasterWarningText = Vue.computed(() => {
          const user = String(settingsForm.gmail_imap_user || "").trim().toLowerCase();
          const aliasRaw = String(settingsForm.gmail_alias_emails || "").trim();
          const aliases = aliasRaw
            ? aliasRaw
              .split(/[\n\r,;\s]+/)
              .map((x) => String(x || "").trim().toLowerCase())
              .filter((x) => !!x)
            : [];
          const pool = aliases.length ? aliases : (user ? [user] : []);
          if (!pool.length) return "";

          const canonicalSet = new Set();
          let validCount = 0;
          for (const raw of pool) {
            const item = String(raw || "").split("----", 1)[0].trim().toLowerCase();
            if (!item || !item.includes("@")) continue;
            const parts = item.split("@");
            const local = String(parts[0] || "").trim().toLowerCase();
            const domain = String(parts[1] || "").trim().toLowerCase();
            if (!local || !domain) continue;
            validCount += 1;
            if (domain === "gmail.com" || domain === "googlemail.com") {
              const masterLocal = local.split("+", 1)[0].replace(/\./g, "");
              canonicalSet.add(`${masterLocal}@gmail.com`);
            } else {
              canonicalSet.add(`${local}@${domain}`);
            }
          }

          if (!validCount || canonicalSet.size > 1) return "";
          if (validCount <= 1) {
            return "当前仅配置 1 个 Gmail 主号；若该邮箱已注册过，会直接触发 user_already_exists。";
          }
          return "当前别名池看似多个，但本质是同一 Gmail 主号（点号/+tag/googlemail 视为同源），可能持续触发 user_already_exists。";
        });

        const selectedMailLabel = Vue.computed(() => {
          if (!selectedMailId.value) return "-";
          const row = mailRows.value.find((x) => String(x.id || "") === String(selectedMailId.value));
          if (!row) return String(selectedMailId.value);
          return `${row.id} · ${row.subject}`;
        });

        const mailDetailText = Vue.computed(() => {
          const text = String(mailDetail.content || "").trim();
          if (text) return text;
          return "请选择一封邮件查看内容";
        });

        const logText = Vue.computed(() => {
          return logLines.value.join("\n");
        });

        const flclashProbeSummary = Vue.computed(() => {
          if (loading.flclash_probe) {
            return "FlClash 节点测试进行中，请稍候...";
          }
          const attempts = Number(flclashProbeMeta.attempts || 0);
          if (attempts <= 0) {
            return "未执行节点出口测试";
          }
          const ok = Number(flclashProbeMeta.ok || 0);
          const fail = Number(flclashProbeMeta.fail || 0);
          const group = String(flclashProbeMeta.group || "-");
          const candidates = Number(flclashProbeMeta.candidate_total || 0);
          const blocked = Number(flclashProbeMeta.blocked_hk_count || 0);
          const restoreText = flclashProbeMeta.restore_error
            ? `恢复失败: ${String(flclashProbeMeta.restore_error || "")}`
            : (flclashProbeMeta.restored ? "已恢复原节点" : "未恢复原节点");
          return `组 ${group} · 候选 ${candidates} · 测试 ${attempts} · 成功 ${ok} · 失败 ${fail} · 跳过香港 ${blocked} · ${restoreText}`;
        });

        function rowKeyPath(row) {
          return row.path;
        }

        function rowKeyAccount(row) {
          return row.key;
        }

        function rowKeyRemote(row) {
          return row.key;
        }

        function rowKeyMailbox(row) {
          return row.key;
        }

        function rowKeyMail(row) {
          return row.key;
        }

        function rowKeyCfDns(row) {
          return row.key;
        }

        function fileToneClass(idx) {
          const n = Number(idx);
          if (!Number.isFinite(n) || n < 0) return "";
          return `row-file-tone-${Math.abs(Math.floor(n)) % 12}`;
        }

        function jsonRowClassName(row) {
          return fileToneClass(row && row.file_color_idx);
        }

        function accountRowClassName(row) {
          return "";
        }

        function setJsonNoteDraft(path, val) {
          const p = String(path || "");
          if (!p) return;
          jsonNoteDraft[p] = String(val || "");
        }

        async function saveJsonNote(path, showSuccess = true) {
          const p = String(path || "");
          if (!p) return;
          const note = String(jsonNoteDraft[p] || "").trim();
          jsonNoteSaving[p] = true;
          try {
            const data = await apiRequest("/api/data/json/note", {
              method: "POST",
              body: { path: p, note }
            });
            const row = jsonRows.value.find((x) => String(x.path || "") === p);
            if (row) row.note = String(data.note || "");
            jsonNoteDraft[p] = String(data.note || "");
            if (showSuccess) {
              const fileName = row ? String(row.name || "") : String(data.name || "");
              message.success(`备注已保存：${fileName || "JSON"}`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            jsonNoteSaving[p] = false;
          }
        }

        function normalizeDomainList(values) {
          if (!Array.isArray(values)) return [];
          const out = [];
          const seen = new Set();
          for (const raw of values) {
            const d = String(raw || "").trim().toLowerCase();
            if (!d || d.includes("@") || seen.has(d)) continue;
            seen.add(d);
            out.push(d);
          }
          return out;
        }

        function domainErrorCount(domain) {
          const d = String(domain || "").trim().toLowerCase();
          if (!d) return 0;
          const raw = mailDomainErrors[d];
          const n = Number(raw || 0);
          return Number.isFinite(n) && n > 0 ? n : 0;
        }

        function domainRegisteredCount(domain) {
          const d = String(domain || "").trim().toLowerCase();
          if (!d) return 0;
          const raw = mailDomainRegistered[d];
          const n = Number(raw || 0);
          return Number.isFinite(n) && n > 0 ? n : 0;
        }

        function isDomainSelected(domain) {
          const d = String(domain || "").trim().toLowerCase();
          if (!d) return false;
          const list = normalizeDomainList(settingsForm.mail_domain_allowlist);
          return list.includes(d);
        }

        function setDomainSelection(domains) {
          settingsForm.mail_domain_allowlist = normalizeDomainList(domains);
        }

        function toggleDomain(domain) {
          const d = String(domain || "").trim().toLowerCase();
          if (!d) return;
          const list = normalizeDomainList(settingsForm.mail_domain_allowlist);
          if (list.includes(d)) {
            if (list.length <= 1) {
              message.warning("至少保留 1 个可用域名");
              return;
            }
            setDomainSelection(list.filter((x) => x !== d));
            return;
          }
          list.push(d);
          setDomainSelection(list);
        }

        function applyDomainStats(data) {
          const counts = (data && data.error_counts) || {};
          const registered = (data && data.registered_counts) || {};
          const selected = normalizeDomainList((data && data.selected) || settingsForm.mail_domain_allowlist || []);
          for (const k of Object.keys(mailDomainErrors)) {
            delete mailDomainErrors[k];
          }
          for (const k of Object.keys(mailDomainRegistered)) {
            delete mailDomainRegistered[k];
          }
          if (counts && typeof counts === "object") {
            for (const [k, v] of Object.entries(counts)) {
              const d = String(k || "").trim().toLowerCase();
              if (!d) continue;
              const n = Number(v || 0);
              if (Number.isFinite(n) && n > 0) {
                mailDomainErrors[d] = n;
              }
            }
          }
          if (registered && typeof registered === "object") {
            for (const [k, v] of Object.entries(registered)) {
              const d = String(k || "").trim().toLowerCase();
              if (!d) continue;
              const n = Number(v || 0);
              if (Number.isFinite(n) && n > 0) {
                mailDomainRegistered[d] = n;
              }
            }
          }
          if (selected.length) {
            setDomainSelection(selected);
          }
        }

        function normalizeMailProvider(raw) {
          const val = String(raw || "mailfree").trim().toLowerCase();
          if (["cloudflare_temp_email", "cloudflare-temp-email", "cf_temp", "gptmail", "worker_api"].includes(val)) {
            return "cloudflare_temp_email";
          }
          if (["cloudmail", "cloud_mail"].includes(val)) return "cloudmail";
          if (["mail_curl", "mailcurl", "curl_mail"].includes(val)) return "mail_curl";
          if (["luckyous", "luckyous_api", "luckymail", "lucky_mail", "luckyous_openapi"].includes(val)) return "luckyous";
          if (val === "graph") return "graph";
          if (val === "gmail" || val === "imap") return "gmail";
          if (["cf_email_routing", "cf_routing", "cloudflare_email_routing", "cloudflare_routing"].includes(val)) return "cf_email_routing";
          return "mailfree";
        }

        function normalizeRemoteAccountProvider(raw) {
          const val = String(raw || "sub2api").trim().toLowerCase();
          if (["cliproxyapi", "cliproxy", "cli_proxy_api", "cpa"].includes(val)) {
            return "cliproxyapi";
          }
          return "sub2api";
        }

        function remoteRowClassName(row) {
          const classes = [];
          if (row && row.is_dup) classes.push("row-dup-strong");
          const s = String((row && row.test_status) || "").trim();
          if (s === "封禁") classes.push("row-test-ban");
          else if (s === "Token过期") classes.push("row-test-token");
          else if (s === "429限流") classes.push("row-test-429");
          else if (s === "已复活" || s === "已刷新") classes.push("row-test-revived");
          else if (s && s !== "成功" && s !== "未测试" && s !== "未测") classes.push("row-test-fail");
          return classes.join(" ");
        }

        const flclashPolicyOptions = [
          { label: "轮询切换", value: "round_robin" },
          { label: "随机切换", value: "random" }
        ];

        const graphFetchModeOptions = [
          { label: "Graph API 取件", value: "graph_api" },
          { label: "IMAP XOAUTH2 取件", value: "imap_xoauth2" }
        ];

        const graphAccountSourceOptions = [
          { label: "文件模式", value: "file" },
          { label: "接口模式", value: "api" }
        ];

        function normalizeGraphAccountsMode(raw) {
          const val = String(raw || "file").trim().toLowerCase();
          if (["api", "http", "interface", "openapi", "open_api", "remote"].includes(val)) {
            return "api";
          }
          return "file";
        }

        const remoteAccountProviderOptions = [
          { label: "Sub2API", value: "sub2api" },
          { label: "CLIProxyAPI", value: "cliproxyapi" }
        ];

        const flclashProbeColumns = [
          { title: "#", key: "seq", width: 56 },
          { title: "轮次", key: "round", width: 64 },
          { title: "节点", key: "node", minWidth: 220, ellipsis: { tooltip: true } },
          { title: "出口IP", key: "ip", width: 150, ellipsis: { tooltip: true } },
          { title: "地区", key: "loc", width: 72 },
          { title: "机房", key: "colo", width: 76 },
          {
            title: "状态",
            key: "success",
            width: 88,
            render(row) {
              if (row && row.success) {
                return Vue.h(
                  naive.NTag,
                  { type: "success", size: "small", bordered: false },
                  { default: () => "成功" }
                );
              }
              return Vue.h(
                naive.NTag,
                { type: "error", size: "small", bordered: false },
                { default: () => "失败" }
              );
            }
          },
          { title: "说明", key: "detail", minWidth: 240, ellipsis: { tooltip: true } }
        ];

        const jsonColumns = [
          { type: "selection", multiple: true },
          { title: "文件名", key: "name", minWidth: 180, ellipsis: { tooltip: true } },
          { title: "账号数", key: "count", width: 80 },
          { title: "创建时间", key: "created", width: 168 },
          {
            title: "备注",
            key: "note",
            minWidth: 280,
            render(row) {
              const path = String((row && row.path) || "");
              const value = Object.prototype.hasOwnProperty.call(jsonNoteDraft, path)
                ? String(jsonNoteDraft[path] || "")
                : String((row && row.note) || "");
              const saving = !!jsonNoteSaving[path];
              return Vue.h("div", { class: "json-note-cell" }, [
                Vue.h(naive.NInput, {
                  size: "small",
                  value,
                  clearable: true,
                  maxlength: 120,
                  placeholder: "输入备注",
                  onUpdateValue: (v) => setJsonNoteDraft(path, v)
                }),
                Vue.h(
                  naive.NButton,
                  {
                    size: "small",
                    type: "primary",
                    tertiary: true,
                    loading: saving,
                    onClick: () => saveJsonNote(path, true)
                  },
                  { default: () => "保存" }
                )
              ]);
            }
          }
        ];

        const accountColumns = [
          { type: "selection", multiple: true },
          { title: "#", key: "index", width: 56 },
          { title: "邮箱", key: "email", minWidth: 220, ellipsis: { tooltip: true } },
          { title: "密码", key: "password", width: 150, ellipsis: { tooltip: true } },
          {
            title: "状态",
            key: "cloud_test_status",
            width: 100,
            render(row) {
              const s = String(row.cloud_test_status || "未测").trim();
              const detail = String(row.cloud_test_result || "-").trim();
              if (s === "成功") {
                return Vue.h(
                  naive.NTag,
                  { type: "success", size: "small", bordered: false, title: detail },
                  { default: () => "成功" }
                );
              }
              if (s === "失败" || s === "刷新失败" || s === "封禁" || s === "Token过期" || s === "429限流") {
                return Vue.h(
                  naive.NTag,
                  { type: "error", size: "small", bordered: false, title: detail },
                  { default: () => "失败" }
                );
              }
              return Vue.h(
                naive.NTag,
                { type: "default", size: "small", bordered: false, title: detail },
                { default: () => "未测" }
              );
            }
          },
          { title: "备注", key: "note", minWidth: 300, ellipsis: { tooltip: true } },
          {
            title: "功能",
            key: "actions",
            width: 88,
            render(row) {
              const token = String((row && row.access_token) || "").trim();
              return Vue.h(
                naive.NButton,
                {
                  size: "small",
                  type: "primary",
                  tertiary: true,
                  disabled: !token,
                  title: "复制 access_token",
                  onClick: () => accountCopyToken(row)
                },
                { default: () => "复制AT" }
              );
            }
          }
        ];

        const accountFilteredRows = Vue.computed(() => {
          const kw = String(accountSearch.value || "").trim().toLowerCase();
          if (!kw) return accountRows.value;
          return accountRows.value.filter((row) => {
            const email = String((row && row.email) || "").toLowerCase();
            const note = String((row && row.note) || "").toLowerCase();
            const cloud = String((row && row.cloud_test_status) || "").toLowerCase();
            return email.includes(kw) || note.includes(kw) || cloud.includes(kw);
          });
        });

        function accountExportableRows() {
          return accountRows.value.filter((x) => !x.locked);
        }

        function accountSelectedEmails(includeLocked = false) {
          const keySet = new Set(accountSelection.value);
          return accountRows.value
            .filter((x) => keySet.has(x.key) && (includeLocked || !x.locked))
            .map((x) => String(x.email || "").trim())
            .filter((x) => !!x);
        }

        function openSub2ApiExportModal() {
          const emails = accountSelectedEmails();
          if (!emails.length) {
            message.warning("请先勾选可导出的账号");
            return;
          }
          const total = emails.length;
          const defaultPerFile = Math.min(100, Math.max(1, total));
          sub2apiExportForm.file_count = Math.max(1, Math.ceil(total / defaultPerFile));
          sub2apiExportForm.accounts_per_file = defaultPerFile;
          showSub2ApiExportModal.value = true;
        }

        async function confirmExportSub2Api() {
          const emails = accountSelectedEmails();
          if (!emails.length) {
            message.warning("请先勾选可导出的账号");
            return;
          }

          const fileCount = Math.max(1, Number(sub2apiExportForm.file_count || 1));
          const perFile = Math.max(1, Number(sub2apiExportForm.accounts_per_file || 1));
          if (fileCount * perFile < emails.length) {
            message.warning("文件数 × 每文件账号数 小于当前勾选账号数，请调整后重试");
            return;
          }

          loading.sub2api_export = true;
          try {
            await saveConfig(false);
            const data = await apiRequest("/api/data/sub2api/export", {
              method: "POST",
              body: {
                emails,
                file_count: fileCount,
                accounts_per_file: perFile
              }
            });

            await refreshAccounts(false);
            showSub2ApiExportModal.value = false;

            const exported = Number((data && data.exported) || 0);
            const missing = Array.isArray(data && data.missing) ? data.missing : [];
            const fileNum = Number((data && data.file_count) || 0);
            const dir = String((data && data.output_dir) || "");
            const opened = !!(data && data.opened_dir);
            const openSuffix = opened ? "，已打开目录" : "";
            if (missing.length) {
              message.warning(
                `导出完成：${exported} 个，文件 ${fileNum} 个，缺失 ${missing.length} 个${openSuffix}`
              );
            } else {
              message.success(`导出完成：${exported} 个，文件 ${fileNum} 个${openSuffix}`);
            }
            if (dir) {
              message.info(`导出目录：${dir}`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.sub2api_export = false;
          }
        }

        const remoteColumns = [
          { type: "selection", multiple: true },
          { title: "ID", key: "id", width: 92, ellipsis: { tooltip: true } },
          { title: "名称/邮箱", key: "name", minWidth: 280, ellipsis: { tooltip: true } },
          { title: "平台", key: "platform", width: 76 },
          { title: "分组", key: "groups", minWidth: 260, ellipsis: { tooltip: true } },
          { title: "5h", key: "u5h", width: 72 },
          { title: "7d", key: "u7d", width: 72 },
          {
            title: "测试",
            key: "test_status",
            width: 86,
            render(row) {
              const s = String(row.test_status || "未测试");
              if (s === "成功") {
                return Vue.h(
                  naive.NTag,
                  { type: "success", size: "small", bordered: false },
                  { default: () => "成功" }
                );
              }
              if (s === "封禁") {
                return Vue.h(
                  naive.NTag,
                  { type: "error", size: "small", bordered: false },
                  { default: () => "封禁" }
                );
              }
              if (s === "Token过期") {
                return Vue.h(
                  naive.NTag,
                  { type: "warning", size: "small", bordered: false },
                  { default: () => "Token过期" }
                );
              }
              if (s === "429限流") {
                return Vue.h(
                  naive.NTag,
                  { type: "info", size: "small", bordered: false },
                  { default: () => "429" }
                );
              }
              if (s === "已复活") {
                return Vue.h(
                  naive.NTag,
                  { type: "success", size: "small", bordered: false },
                  { default: () => "已复活" }
                );
              }
              if (s === "已刷新") {
                return Vue.h(
                  naive.NTag,
                  { type: "success", size: "small", bordered: false },
                  { default: () => "已刷新" }
                );
              }
              if (s === "刷新失败") {
                return Vue.h(
                  naive.NTag,
                  { type: "error", size: "small", bordered: false },
                  { default: () => "刷新失败" }
                );
              }
              if (s === "失败") {
                return Vue.h(
                  naive.NTag,
                  { type: "error", size: "small", bordered: false },
                  { default: () => "失败" }
                );
              }
              return Vue.h(
                naive.NTag,
                { type: "default", size: "small", bordered: false },
                { default: () => "未测" }
              );
            }
          },
          {
            title: "功能",
            key: "actions",
            width: 88,
            render(row) {
              const token = String((row && row.access_token) || "").trim();
              const provider = normalizeRemoteAccountProvider(settingsForm.remote_account_provider);
              const canDownload = (
                provider === "cliproxyapi"
                && !!String((row && row.file_name) || "").trim()
              );
              return Vue.h(
                naive.NButton,
                {
                  size: "small",
                  type: "primary",
                  tertiary: true,
                  disabled: !(token || canDownload),
                  title: "复制 access_token",
                  onClick: () => remoteCopyToken(row)
                },
                { default: () => "复制AT" }
              );
            }
          }
        ];

        const remoteTableColumns = Vue.computed(() => {
          const provider = normalizeRemoteAccountProvider(settingsForm.remote_account_provider);
          if (provider === "cliproxyapi") {
            return remoteColumns.filter((col) => col && col.key !== "groups");
          }
          return remoteColumns;
        });

        const mailboxColumns = [
          { type: "selection", multiple: true },
          { title: "邮箱地址", key: "address", minWidth: 280, ellipsis: { tooltip: true } },
          { title: "创建时间", key: "created_at", width: 168 },
          { title: "过期时间", key: "expires_at", width: 168 },
          { title: "邮件数", key: "count", width: 80 }
        ];

        const mailColumns = [
          { type: "selection", multiple: true },
          { title: "ID", key: "id", width: 140, ellipsis: { tooltip: true } },
          { title: "发件人", key: "from", minWidth: 180, ellipsis: { tooltip: true } },
          { title: "主题", key: "subject", minWidth: 220, ellipsis: { tooltip: true } },
          { title: "接收时间", key: "date", width: 170, ellipsis: { tooltip: true } }
        ];

        const cfDnsInfoText = Vue.computed(() => {
          const zone = cfZoneOptions.value.find((x) => String(x.value || "") === String(cfZoneId.value || ""));
          const zname = String((zone && zone.label) || "").trim() || "-";
          const target = String(cfTargetDomain.value || settingsForm.cf_dns_target_domain || "").trim() || "-";
          const total = Number(cfDnsRows.value.length || 0);
          const selected = Number(cfDnsSelection.value.length || 0);
          return `当前域名：${zname} · 指向：${target} · CNAME 记录 ${total} 条 · 已选 ${selected} 条`;
        });

        const cfDnsColumns = [
          { type: "selection", multiple: true },
          { title: "二级域名", key: "label", minWidth: 140, ellipsis: { tooltip: true } },
          { title: "完整域名", key: "name", minWidth: 240, ellipsis: { tooltip: true } },
          { title: "指向", key: "target", minWidth: 220, ellipsis: { tooltip: true } },
          {
            title: "代理",
            key: "proxied",
            width: 76,
            render(row) {
              const on = !!(row && row.proxied);
              return Vue.h(
                naive.NTag,
                { type: on ? "success" : "default", size: "small", bordered: false },
                { default: () => (on ? "开" : "关") }
              );
            }
          },
          { title: "TTL", key: "ttl", width: 76 },
          {
            title: "操作",
            key: "actions",
            width: 190,
            render(row) {
              return Vue.h("div", { class: "cf-dns-actions" }, [
                Vue.h(
                  naive.NButton,
                  {
                    size: "small",
                    tertiary: true,
                    onClick: () => openCfDnsEditModal(row)
                  },
                  { default: () => "编辑" }
                ),
                Vue.h(
                  naive.NButton,
                  {
                    size: "small",
                    type: "primary",
                    tertiary: true,
                    loading: loading.mail_cf_worker_set || loading.mail_cf_worker_batch,
                    onClick: () => setCfWorkerMailDomain(row)
                  },
                  { default: () => "同步到MailFree" }
                )
              ]);
            }
          }
        ];

        async function apiRequest(path, options = {}) {
          const opts = Object.assign({}, options);
          if (!opts.method) opts.method = "GET";
          if (opts.body && typeof opts.body !== "string") {
            opts.body = JSON.stringify(opts.body);
            opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
          }
          const resp = await fetch(path, opts);
          let payload = null;
          try {
            payload = await resp.json();
          } catch (_e) {
            payload = { ok: false, error: `HTTP ${resp.status}` };
          }
          if (!resp.ok || !payload.ok) {
            throw new Error(payload.error || `HTTP ${resp.status}`);
          }
          return payload.data;
        }

        async function copyText(text) {
          const raw = String(text || "");
          if (!raw) {
            throw new Error("空内容无法复制");
          }
          if (navigator && navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            await navigator.clipboard.writeText(raw);
            return;
          }
          const el = document.createElement("textarea");
          el.value = raw;
          el.setAttribute("readonly", "readonly");
          el.style.position = "fixed";
          el.style.left = "-9999px";
          document.body.appendChild(el);
          el.focus();
          el.select();
          try {
            const ok = document.execCommand("copy");
            if (!ok) throw new Error("浏览器不支持复制");
          } finally {
            document.body.removeChild(el);
          }
        }

        async function accountCopyToken(row) {
          const token = String((row && row.access_token) || "").trim();
          if (!token) {
            message.warning("该本地账号暂无可复制 access_token");
            return;
          }
          try {
            await copyText(token);
            message.success("已复制本地账号 access_token");
          } catch (e) {
            message.error(String(e.message || e));
          }
        }

        async function remoteCopyToken(row) {
          try {
            let token = String((row && row.access_token) || "").trim();
            if (!token) {
              const data = await apiRequest("/api/remote/access-token", {
                method: "POST",
                body: {
                  id: String((row && row.id) || "").trim(),
                  file_name: String((row && row.file_name) || "").trim()
                }
              });
              token = String((data && data.access_token) || "").trim();
              if (!token) {
                throw new Error("接口未返回 access_token");
              }
              if (row) row.access_token = token;
            }

            await copyText(token);
            message.success("已复制云端账号 access_token");
          } catch (e) {
            message.error(String(e.message || e));
          }
        }

        function assignConfig(cfg) {
          dashForm.num_accounts = Number(cfg.num_accounts || 1);
          dashForm.concurrency = Number(cfg.concurrency || 1);
          dashForm.sleep_min = Number(cfg.sleep_min || 5);
          dashForm.sleep_max = Number(cfg.sleep_max || 30);
          dashForm.fast_mode = !!cfg.fast_mode;
          dashForm.proxy = String(cfg.proxy || "");

          settingsForm.mail_service_provider = normalizeMailProvider(cfg.mail_service_provider || "mailfree");
          mailProviderTab.value = settingsForm.mail_service_provider;
          settingsForm.mail_domain_allowlist = normalizeDomainList(cfg.mail_domain_allowlist || []);
          settingsForm.worker_domain = String(cfg.worker_domain || "");
          settingsForm.mail_domains = String(cfg.mail_domains || "");
          settingsForm.freemail_username = String(cfg.freemail_username || "");
          settingsForm.freemail_password = String(cfg.freemail_password || "");
          settingsForm.cf_temp_base_url = String(cfg.cf_temp_base_url || cfg.worker_domain || "");
          settingsForm.cf_temp_mail_domains = String(cfg.cf_temp_mail_domains || cfg.mail_domains || "");
          settingsForm.cf_api_token = String(cfg.cf_api_token || "");
          settingsForm.cf_account_id = String(cfg.cf_account_id || "");
          settingsForm.cf_worker_script = String(cfg.cf_worker_script || "mailfree");
          settingsForm.cf_worker_mail_domain_binding = String(cfg.cf_worker_mail_domain_binding || "MAIL_DOMAIN");
          settingsForm.cf_dns_target_domain = String(cfg.cf_dns_target_domain || "").toLowerCase();
          if (!String(cfTargetDomain.value || "").trim()) {
            cfTargetDomain.value = String(settingsForm.cf_dns_target_domain || "").trim().toLowerCase();
          }
          settingsForm.cf_temp_admin_auth = String(cfg.cf_temp_admin_auth || "");
          settingsForm.cloudmail_api_url = String(cfg.cloudmail_api_url || "");
          settingsForm.cloudmail_admin_email = String(cfg.cloudmail_admin_email || "");
          settingsForm.cloudmail_admin_password = String(cfg.cloudmail_admin_password || "");
          settingsForm.mail_curl_api_base = String(cfg.mail_curl_api_base || "");
          settingsForm.mail_curl_key = String(cfg.mail_curl_key || "");
          settingsForm.luckyous_api_base = String(cfg.luckyous_api_base || "https://mails.luckyous.com");
          settingsForm.luckyous_api_key = String(cfg.luckyous_api_key || "");
          settingsForm.luckyous_project_code = String(cfg.luckyous_project_code || "");
          settingsForm.luckyous_email_type = String(cfg.luckyous_email_type || "ms_graph");
          settingsForm.luckyous_domain = String(cfg.luckyous_domain || "");
          settingsForm.luckyous_variant_mode = String(cfg.luckyous_variant_mode || "");
          settingsForm.luckyous_specified_email = String(cfg.luckyous_specified_email || "");
          settingsForm.graph_accounts_mode = normalizeGraphAccountsMode(cfg.graph_accounts_mode || "file");
          settingsForm.graph_accounts_file = String(cfg.graph_accounts_file || "");
          settingsForm.graph_api_base_url = String(cfg.graph_api_base_url || "");
          settingsForm.graph_api_token = String(cfg.graph_api_token || "");
          settingsForm.graph_tenant = String(cfg.graph_tenant || "common");
          settingsForm.graph_fetch_mode = String(cfg.graph_fetch_mode || "graph_api");
          settingsForm.graph_pre_refresh_before_run = cfg.graph_pre_refresh_before_run !== false;
          settingsForm.gmail_imap_user = String(cfg.gmail_imap_user || "");
          settingsForm.gmail_imap_pass = String(cfg.gmail_imap_pass || "");
          settingsForm.gmail_alias_emails = String(cfg.gmail_alias_emails || "");
          settingsForm.gmail_imap_server = String(cfg.gmail_imap_server || "imap.gmail.com");
          settingsForm.gmail_imap_port = Number(cfg.gmail_imap_port || 993);
          settingsForm.gmail_alias_tag_len = Number(cfg.gmail_alias_tag_len || 8);
          settingsForm.gmail_alias_mix_googlemail = cfg.gmail_alias_mix_googlemail !== false;
          settingsForm.cf_routing_api_token = String(cfg.cf_routing_api_token || "");
          settingsForm.cf_routing_zone_id = String(cfg.cf_routing_zone_id || "");
          settingsForm.cf_routing_domain = String(cfg.cf_routing_domain || "");
          settingsForm.cf_routing_cleanup = cfg.cf_routing_cleanup !== false;
          settingsForm.gmail_api_client_id = String(cfg.gmail_api_client_id || "");
          settingsForm.gmail_api_client_secret = String(cfg.gmail_api_client_secret || "");
          settingsForm.gmail_api_refresh_token = String(cfg.gmail_api_refresh_token || "");
          settingsForm.gmail_api_user = String(cfg.gmail_api_user || "");
          settingsForm.hero_sms_enabled = !!cfg.hero_sms_enabled;
          settingsForm.hero_sms_reuse_phone = !!cfg.hero_sms_reuse_phone;
          settingsForm.hero_sms_api_key = String(cfg.hero_sms_api_key || "");
          settingsForm.hero_sms_service = String(cfg.hero_sms_service || "");
          settingsForm.hero_sms_country = String(cfg.hero_sms_country || "US");
          settingsForm.hero_sms_auto_pick_country = !!cfg.hero_sms_auto_pick_country;
          settingsForm.hero_sms_max_price = Number(cfg.hero_sms_max_price ?? 2);
          smsState.enabled = !!settingsForm.hero_sms_enabled;
          smsState.reuse_phone = !!settingsForm.hero_sms_reuse_phone;
          smsState.key_configured = !!String(settingsForm.hero_sms_api_key || "").trim();
          smsState.service = String(settingsForm.hero_sms_service || "");
          smsState.country = String(settingsForm.hero_sms_country || "US");
          smsState.min_balance_usd = Math.max(0, Number(settingsForm.hero_sms_max_price || 0));
          settingsForm.mailfree_random_domain = cfg.mailfree_random_domain !== false;
          settingsForm.mailbox_custom_enabled = !!cfg.mailbox_custom_enabled;
          settingsForm.mailbox_prefix = String(cfg.mailbox_prefix || "");
          settingsForm.mailbox_random_len = Number(cfg.mailbox_random_len || 0);
          settingsForm.register_random_fingerprint = cfg.register_random_fingerprint !== false;
          settingsForm.register_test_mode_passwordless = !!cfg.register_test_mode_passwordless;
          settingsForm.openai_ssl_verify = !!cfg.openai_ssl_verify;
          settingsForm.skip_net_check = !!cfg.skip_net_check;
          settingsForm.flclash_enable_switch = !!cfg.flclash_enable_switch;
          settingsForm.flclash_controller = String(cfg.flclash_controller || "127.0.0.1:9090");
          settingsForm.flclash_secret = String(cfg.flclash_secret || "");
          settingsForm.flclash_group = String(cfg.flclash_group || "PROXY");
          settingsForm.flclash_switch_policy = String(cfg.flclash_switch_policy || "round_robin");
          settingsForm.flclash_switch_wait_sec = Number(cfg.flclash_switch_wait_sec || 1.2);
          settingsForm.flclash_rotate_every = Number(cfg.flclash_rotate_every || 3);
          settingsForm.flclash_delay_test_url = String(cfg.flclash_delay_test_url || "https://www.gstatic.com/generate_204");
          settingsForm.flclash_delay_timeout_ms = Number(cfg.flclash_delay_timeout_ms || 4000);
          settingsForm.flclash_delay_max_ms = Number(cfg.flclash_delay_max_ms || 1800);
          settingsForm.flclash_delay_retry = Number(cfg.flclash_delay_retry || 1);
          settingsForm.remote_test_concurrency = Number(cfg.remote_test_concurrency || 4);
          settingsForm.remote_test_ssl_retry = Number(cfg.remote_test_ssl_retry || 2);
          settingsForm.remote_refresh_concurrency = Number(cfg.remote_refresh_concurrency || 4);
          settingsForm.accounts_sync_api_url = String(cfg.accounts_sync_api_url || "");
          settingsForm.accounts_sync_bearer_token = String(cfg.accounts_sync_bearer_token || "");
          settingsForm.accounts_list_api_base = String(cfg.accounts_list_api_base || "");
          settingsForm.remote_account_provider = normalizeRemoteAccountProvider(cfg.remote_account_provider || "sub2api");
          settingsForm.cliproxy_api_base = String(cfg.cliproxy_api_base || "");
          settingsForm.cliproxy_management_key = String(cfg.cliproxy_management_key || "");
          settingsForm.accounts_list_timezone = String(cfg.accounts_list_timezone || "Asia/Shanghai");
          settingsForm.codex_export_dir = String(cfg.codex_export_dir || "");
        }

        function buildPayload() {
          return {
            num_accounts: Number(dashForm.num_accounts || 1),
            num_files: 1,
            concurrency: Number(dashForm.concurrency || 1),
            sleep_min: Number(dashForm.sleep_min || 5),
            sleep_max: Number(dashForm.sleep_max || 30),
            fast_mode: !!dashForm.fast_mode,
            proxy: String(dashForm.proxy || "").trim(),
            mail_service_provider: normalizeMailProvider(settingsForm.mail_service_provider || "mailfree"),
            mail_domain_allowlist: normalizeDomainList(settingsForm.mail_domain_allowlist || []),
            worker_domain: String(settingsForm.worker_domain || "").trim(),
            mail_domains: String(settingsForm.mail_domains || "").trim(),
            freemail_username: String(settingsForm.freemail_username || "").trim(),
            freemail_password: String(settingsForm.freemail_password || "").trim(),
            cf_temp_base_url: String(settingsForm.cf_temp_base_url || "").trim(),
            cf_temp_mail_domains: String(settingsForm.cf_temp_mail_domains || "").trim(),
            cf_api_token: String(settingsForm.cf_api_token || "").trim(),
            cf_account_id: String(settingsForm.cf_account_id || "").trim(),
            cf_worker_script: String(settingsForm.cf_worker_script || "mailfree").trim(),
            cf_worker_mail_domain_binding: String(settingsForm.cf_worker_mail_domain_binding || "MAIL_DOMAIN").trim(),
            cf_dns_target_domain: String(cfTargetDomain.value || settingsForm.cf_dns_target_domain || "").trim().toLowerCase(),
            cf_temp_admin_auth: String(settingsForm.cf_temp_admin_auth || "").trim(),
            cloudmail_api_url: String(settingsForm.cloudmail_api_url || "").trim(),
            cloudmail_admin_email: String(settingsForm.cloudmail_admin_email || "").trim(),
            cloudmail_admin_password: String(settingsForm.cloudmail_admin_password || "").trim(),
            mail_curl_api_base: String(settingsForm.mail_curl_api_base || "").trim(),
            mail_curl_key: String(settingsForm.mail_curl_key || "").trim(),
            luckyous_api_base: String(settingsForm.luckyous_api_base || "https://mails.luckyous.com").trim(),
            luckyous_api_key: String(settingsForm.luckyous_api_key || "").trim(),
            luckyous_project_code: String(settingsForm.luckyous_project_code || "").trim(),
            luckyous_email_type: String(settingsForm.luckyous_email_type || "ms_graph").trim(),
            luckyous_domain: String(settingsForm.luckyous_domain || "").trim(),
            luckyous_variant_mode: String(settingsForm.luckyous_variant_mode || "").trim(),
            luckyous_specified_email: String(settingsForm.luckyous_specified_email || "").trim(),
            graph_accounts_mode: normalizeGraphAccountsMode(settingsForm.graph_accounts_mode || "file"),
            graph_accounts_file: String(settingsForm.graph_accounts_file || "").trim(),
            graph_api_base_url: String(settingsForm.graph_api_base_url || "").trim(),
            graph_api_token: String(settingsForm.graph_api_token || "").trim(),
            graph_tenant: String(settingsForm.graph_tenant || "common").trim(),
            graph_fetch_mode: String(settingsForm.graph_fetch_mode || "graph_api").trim(),
            graph_pre_refresh_before_run: !!settingsForm.graph_pre_refresh_before_run,
            gmail_imap_user: String(settingsForm.gmail_imap_user || "").trim(),
            gmail_imap_pass: String(settingsForm.gmail_imap_pass || "").trim(),
            gmail_alias_emails: String(settingsForm.gmail_alias_emails || "").trim(),
            gmail_imap_server: String(settingsForm.gmail_imap_server || "imap.gmail.com").trim(),
            gmail_imap_port: Number(settingsForm.gmail_imap_port || 993),
            gmail_alias_tag_len: Number(settingsForm.gmail_alias_tag_len || 8),
            gmail_alias_mix_googlemail: !!settingsForm.gmail_alias_mix_googlemail,
            cf_routing_api_token: String(settingsForm.cf_routing_api_token || "").trim(),
            cf_routing_zone_id: String(settingsForm.cf_routing_zone_id || "").trim(),
            cf_routing_domain: String(settingsForm.cf_routing_domain || "").trim(),
            cf_routing_cleanup: !!settingsForm.cf_routing_cleanup,
            gmail_api_client_id: String(settingsForm.gmail_api_client_id || "").trim(),
            gmail_api_client_secret: String(settingsForm.gmail_api_client_secret || "").trim(),
            gmail_api_refresh_token: String(settingsForm.gmail_api_refresh_token || "").trim(),
            gmail_api_user: String(settingsForm.gmail_api_user || "").trim(),
            hero_sms_enabled: !!settingsForm.hero_sms_enabled,
            hero_sms_reuse_phone: !!settingsForm.hero_sms_reuse_phone,
            hero_sms_api_key: String(settingsForm.hero_sms_api_key || "").trim(),
            hero_sms_service: String(settingsForm.hero_sms_service || "").trim(),
            hero_sms_country: String(settingsForm.hero_sms_country || "US").trim(),
            hero_sms_auto_pick_country: !!settingsForm.hero_sms_auto_pick_country,
            hero_sms_max_price: Number(settingsForm.hero_sms_max_price || 0),
            mailfree_random_domain: !!settingsForm.mailfree_random_domain,
            mailbox_custom_enabled: !!settingsForm.mailbox_custom_enabled,
            mailbox_prefix: String(settingsForm.mailbox_prefix || "").trim(),
            mailbox_random_len: Number(settingsForm.mailbox_random_len || 0),
            register_random_fingerprint: !!settingsForm.register_random_fingerprint,
            register_test_mode_passwordless: !!settingsForm.register_test_mode_passwordless,
            openai_ssl_verify: !!settingsForm.openai_ssl_verify,
            skip_net_check: !!settingsForm.skip_net_check,
            flclash_enable_switch: !!settingsForm.flclash_enable_switch,
            flclash_controller: String(settingsForm.flclash_controller || "").trim(),
            flclash_secret: String(settingsForm.flclash_secret || "").trim(),
            flclash_group: String(settingsForm.flclash_group || "").trim(),
            flclash_switch_policy: String(settingsForm.flclash_switch_policy || "round_robin").trim(),
            flclash_switch_wait_sec: Number(settingsForm.flclash_switch_wait_sec || 1.2),
            flclash_rotate_every: Number(settingsForm.flclash_rotate_every || 3),
            flclash_delay_test_url: String(settingsForm.flclash_delay_test_url || "").trim(),
            flclash_delay_timeout_ms: Number(settingsForm.flclash_delay_timeout_ms || 4000),
            flclash_delay_max_ms: Number(settingsForm.flclash_delay_max_ms || 1800),
            flclash_delay_retry: Number(settingsForm.flclash_delay_retry || 1),
            remote_test_concurrency: Number(settingsForm.remote_test_concurrency || 4),
            remote_test_ssl_retry: Number(settingsForm.remote_test_ssl_retry || 2),
            remote_refresh_concurrency: Number(settingsForm.remote_refresh_concurrency || 4),
            accounts_sync_api_url: String(settingsForm.accounts_sync_api_url || "").trim(),
            accounts_sync_bearer_token: String(settingsForm.accounts_sync_bearer_token || "").trim(),
            accounts_list_api_base: String(settingsForm.accounts_list_api_base || "").trim(),
            remote_account_provider: normalizeRemoteAccountProvider(settingsForm.remote_account_provider || "sub2api"),
            cliproxy_api_base: String(settingsForm.cliproxy_api_base || "").trim(),
            cliproxy_management_key: String(settingsForm.cliproxy_management_key || "").trim(),
            accounts_list_timezone: String(settingsForm.accounts_list_timezone || "Asia/Shanghai").trim(),
            codex_export_dir: String(settingsForm.codex_export_dir || "").trim()
          };
        }

        function applySmsOverview(data) {
          const d = data || {};
          smsState.enabled = !!d.enabled;
          smsState.reuse_phone = !!d.reuse_phone;
          smsState.key_configured = !!d.key_configured;
          smsState.service = String(d.service || "");
          smsState.service_resolved = String(d.service_resolved || "");
          smsState.country = String(d.country || "US");
          smsState.country_resolved = Number(d.country_resolved ?? -1);
          smsState.min_balance_usd = Math.max(0, Number(d.min_balance_usd || settingsForm.hero_sms_max_price || 0));
          smsState.balance_usd = Number(d.balance_usd ?? -1);
          smsState.balance_error = String(d.balance_error || "");
          smsState.spent_usd = Math.max(0, Number(d.spent_usd || status.run_sms_spent_usd || 0));
          smsState.updated_at = String(d.updated_at || "");
        }

        async function refreshSmsOverview(showSuccess = false, forceRefresh = true) {
          loading.sms_overview = true;
          try {
            const q = forceRefresh ? "1" : "0";
            const data = await apiRequest(`/api/sms/overview?refresh=${q}`);
            applySmsOverview(data);
            if (showSuccess) {
              if (Number(smsState.balance_usd) >= 0) {
                message.success(`SMS 余额 $${Number(smsState.balance_usd).toFixed(2)}`);
              } else {
                message.warning(`SMS 余额获取失败：${smsState.balance_error || "未知错误"}`);
              }
            }
          } catch (e) {
            if (showSuccess) {
              message.error(String(e.message || e));
            }
          } finally {
            loading.sms_overview = false;
          }
        }

        function applySmsCountryOptions(data) {
          const rows = Array.isArray((data && data.items)) ? data.items : [];
          smsState.filtered_out = Number((data && data.filtered_out) || 0);
          smsCountryOptions.value = rows.map((x) => {
            const label = String((x && x.label) || "").trim();
            const id = String((x && x.id) || "").trim();
            const visible = Number((x && x.visible) || 0);
            const count = Number((x && x.count) || 0);
            return {
              label: label || id,
              value: id,
              disabled: visible <= 0 || count <= 0,
              eng: String((x && x.eng) || "").trim()
            };
          });

          const current = String(settingsForm.hero_sms_country || "").trim();
          const resolved = Number((data && data.country_resolved) || smsState.country_resolved || -1);

          if (!current) {
            if (resolved >= 0) {
              const rv = String(resolved);
              if (smsCountryOptions.value.some((x) => String(x.value || "") === rv)) {
                settingsForm.hero_sms_country = rv;
                return;
              }
            }
            const firstEnabled = smsCountryOptions.value.find((x) => !x.disabled);
            if (firstEnabled) {
              settingsForm.hero_sms_country = String(firstEnabled.value || "");
            } else if (smsCountryOptions.value.length > 0) {
              settingsForm.hero_sms_country = String(smsCountryOptions.value[0].value || "");
            }
            return;
          }

          if (smsCountryOptions.value.some((x) => String(x.value || "") === current)) {
            return;
          }

          if (resolved >= 0) {
            const rv = String(resolved);
            if (smsCountryOptions.value.some((x) => String(x.value || "") === rv)) {
              settingsForm.hero_sms_country = rv;
              return;
            }
          }

          const up = current.toUpperCase();
          if (up === "US" || up === "USA") {
            const hit = smsCountryOptions.value.find(
              (x) =>
                String(x.value) === "187"
                || /^UNITED STATES(?: OF AMERICA)?$/i.test(String(x.eng || ""))
                || String(x.eng || "").toUpperCase() === "USA"
            );
            if (hit) {
              settingsForm.hero_sms_country = String(hit.value);
            }
            return;
          }

          // 已填写国家偏好但与下拉 value 不一致时：不再用「第一个有库存」覆盖（避免误选成英国等）
        }

        async function refreshSmsCountryOptions(showSuccess = false, forceRefresh = true) {
          loading.sms_countries = true;
          try {
            const q = forceRefresh ? "1" : "0";
            const data = await apiRequest(`/api/sms/countries?refresh=${q}`);
            applySmsCountryOptions(data);
            if (showSuccess) {
              const total = Number((data && data.total) || 0);
              if (total > 0) {
                message.success(`已刷新国家与价格，共 ${total} 项`);
              } else {
                const err = String((data && data.error) || "无可用国家");
                message.warning(`国家列表为空：${err}`);
              }
            }
          } catch (e) {
            if (showSuccess) {
              message.error(String(e.message || e));
            }
          } finally {
            loading.sms_countries = false;
          }
        }

        async function loadConfig() {
          const data = await apiRequest("/api/config");
          assignConfig(data);
        }

        async function saveConfig(showSuccess = true) {
          loading.save = true;
          try {
            const data = await apiRequest("/api/config", {
              method: "POST",
              body: buildPayload()
            });
            assignConfig(data);
            if (activeTab.value === "sms") {
              await Promise.all([
                refreshSmsOverview(false, true),
                refreshSmsCountryOptions(false, true)
              ]);
            }
            if (showSuccess) message.success("配置已保存");
          } finally {
            loading.save = false;
          }
        }

        function resetFlclashProbeMeta() {
          flclashProbeMeta.group = "-";
          flclashProbeMeta.attempts = 0;
          flclashProbeMeta.ok = 0;
          flclashProbeMeta.fail = 0;
          flclashProbeMeta.candidate_total = 0;
          flclashProbeMeta.blocked_hk_count = 0;
          flclashProbeMeta.restored = false;
          flclashProbeMeta.restore_error = "";
          flclashProbeMeta.at = "";
        }

        function applyFlclashProbeResult(data) {
          const rows = Array.isArray((data && data.items))
            ? data.items.map((x, idx) => ({
              key: String((x && x.key) || `probe-${idx + 1}`),
              seq: Number((x && x.seq) || (idx + 1)),
              round: Number((x && x.round) || 1),
              node: String((x && x.node) || "-"),
              ip: String((x && x.ip) || "-"),
              loc: String((x && x.loc) || "-"),
              colo: String((x && x.colo) || "-"),
              success: !!(x && x.success),
              detail: String((x && x.detail) || ""),
              tested_at: String((x && x.tested_at) || "")
            }))
            : [];
          flclashProbeRows.value = rows;
          flclashProbeMeta.group = String((data && data.group) || "-");
          flclashProbeMeta.attempts = Number((data && data.attempts) || rows.length || 0);
          flclashProbeMeta.ok = Number((data && data.ok) || 0);
          flclashProbeMeta.fail = Number((data && data.fail) || 0);
          flclashProbeMeta.candidate_total = Number((data && data.candidate_total) || 0);
          flclashProbeMeta.blocked_hk_count = Number((data && data.blocked_hk_count) || 0);
          flclashProbeMeta.restored = !!(data && data.restored);
          flclashProbeMeta.restore_error = String((data && data.restore_error) || "");
          flclashProbeMeta.at = new Date().toLocaleString();
        }

        async function runFlclashProbe() {
          loading.flclash_probe = true;
          try {
            await saveConfig(false);
            const data = await apiRequest("/api/flclash/probe", {
              method: "POST",
              body: {
                rounds: Number(flclashProbeForm.rounds || 1),
                per_round_limit: Number(flclashProbeForm.per_round_limit || 0)
              }
            });
            applyFlclashProbeResult(data);
            const ok = Number((data && data.ok) || 0);
            const fail = Number((data && data.fail) || 0);
            if (fail > 0) {
              message.warning(`节点测试完成：成功 ${ok}，失败 ${fail}`);
            } else {
              message.success(`节点测试完成：成功 ${ok}`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.flclash_probe = false;
          }
        }

        function clearFlclashProbeRows() {
          flclashProbeRows.value = [];
          resetFlclashProbeMeta();
          message.success("已清空节点测试结果");
        }

        async function loadStatus() {
          const data = await apiRequest("/api/status");
          status.running = !!data.running;
          status.status_text = String(data.status_text || "就绪");
          status.progress = Number(data.progress || 0);
          status.sync_busy = !!data.sync_busy;
          status.remote_busy = !!data.remote_busy;
          status.remote_test_busy = !!data.remote_test_busy;
          status.config_ready = data.config_ready !== false;
          status.config_blockers = Array.isArray(data.config_blockers) ? data.config_blockers : [];
          status.config_warnings = Array.isArray(data.config_warnings) ? data.config_warnings : [];
          status.run_planned_total = Number(data.run_planned_total || 0);
          status.run_success_count = Number(data.run_success_count || 0);
          status.run_retry_total = Number(data.run_retry_total || 0);
          status.run_success_rate = Number(data.run_success_rate || 100);
          status.run_last_retry_reason = String(data.run_last_retry_reason || "");
          status.run_retry_reasons_top = Array.isArray(data.run_retry_reasons_top)
            ? data.run_retry_reasons_top
            : [];
          status.run_elapsed_sec = Number(data.run_elapsed_sec || 0);
          status.run_avg_success_sec = Number(data.run_avg_success_sec || 0);
          status.run_sms_spent_usd = Math.max(0, Number(data.run_sms_spent_usd || 0));
          status.run_sms_balance_usd = Number(data.run_sms_balance_usd ?? -1);
          status.run_sms_min_balance_usd = Math.max(0, Number(data.run_sms_min_balance_usd || 0));

          smsState.spent_usd = Math.max(smsState.spent_usd, status.run_sms_spent_usd);
          if (status.run_sms_balance_usd >= 0) {
            smsState.balance_usd = status.run_sms_balance_usd;
          }
          if (status.run_sms_min_balance_usd > 0) {
            smsState.min_balance_usd = status.run_sms_min_balance_usd;
          }
          remoteMeta.test_total = Number(data.remote_test_total || remoteMeta.test_total || 0);
          remoteMeta.test_done = Number(data.remote_test_done || remoteMeta.test_done || 0);
          remoteMeta.test_ok = Number(data.remote_test_ok || remoteMeta.test_ok || 0);
          remoteMeta.test_fail = Number(data.remote_test_fail || remoteMeta.test_fail || 0);
        }

        function applyAboutInfo(data) {
          aboutInfo.name = String((data && data.name) || "CodeX Register");
          aboutInfo.version = String((data && data.version) || "0.0.0-dev");
          aboutInfo.author = String((data && data.author) || "-");
          aboutInfo.author_url = String((data && data.author_url) || "");
          aboutInfo.intro = String((data && data.intro) || "");
          aboutInfo.license_name = String((data && data.license_name) || "-");
          aboutInfo.license_file = String((data && data.license_file) || "LICENSE");
          aboutInfo.license_exists = !!(data && data.license_exists);
          aboutInfo.license_url = String((data && data.license_url) || "");
          aboutInfo.repo_slug = String((data && data.repo_slug) || "");
          aboutInfo.repo_url = String((data && data.repo_url) || "");
          aboutInfo.platform = String((data && data.platform) || "");
          aboutInfo.python = String((data && data.python) || "");
        }

        async function refreshAboutInfo(showSuccess = false) {
          try {
            const data = await apiRequest("/api/app/about");
            applyAboutInfo(data);
            if (showSuccess) message.success("关于信息已刷新");
          } catch (e) {
            if (showSuccess) message.error(String(e.message || e));
          }
        }

        async function checkAppUpdate() {
          loading.update_check = true;
          try {
            const data = await apiRequest("/api/app/check-update");
            updateInfo.checked = true;
            updateInfo.checked_at = String(data.checked_at || "");
            updateInfo.has_update = !!data.has_update;
            updateInfo.current_version = String(data.current_version || "");
            updateInfo.latest_tag = String(data.latest_tag || "");
            updateInfo.latest_name = String(data.latest_name || "");
            updateInfo.published_at = String(data.published_at || "");
            updateInfo.release_url = String(data.release_url || "");
            updateInfo.release_notes = String(data.release_notes || "");
            updateInfo.assets = Array.isArray(data.assets) ? data.assets : [];
            updateInfo.error = "";
            if (updateInfo.has_update) {
              message.success(`发现新版本：${updateInfo.latest_tag || updateInfo.latest_name}`);
            } else {
              message.info("当前已是最新版本");
            }
          } catch (e) {
            const err = String(e.message || e);
            updateInfo.checked = true;
            updateInfo.has_update = false;
            updateInfo.error = err;
            message.error(err);
          } finally {
            loading.update_check = false;
          }
        }

        async function pullLogs() {
          if (loading.logs) return;
          loading.logs = true;
          try {
            ensureLogContainerScrollable();
            const data = await apiRequest(`/api/logs?since=${logSince.value}`);
            const items = Array.isArray(data.items) ? data.items : [];
            if (items.length) {
              const shouldFollow = shouldAutoFollowLogs();
              for (const it of items) {
                logLines.value.push(String(it.line || ""));
              }
              if (logLines.value.length > 1600) {
                logLines.value.splice(0, logLines.value.length - 1600);
              }
              if (shouldFollow) {
                await scrollLogsToBottom(true);
              }
            }
            logSince.value = Number(data.last_id || logSince.value);
          } finally {
            loading.logs = false;
          }
        }

        async function manualPoll() {
          await loadStatus();
          await pullLogs();
        }

        async function clearLogs() {
          await apiRequest("/api/logs/clear", { method: "POST" });
          logLines.value = [];
          logSince.value = 0;
          await pullLogs();
          message.success("日志已清空");
        }

        async function clearRunStats() {
          if (status.running) {
            message.warning("任务运行中，无法清空统计");
            return;
          }
          loading.run_stats_clear = true;
          try {
            const data = await apiRequest("/api/run-stats/clear", { method: "POST" });
            status.run_planned_total = Number(data.run_planned_total || 0);
            status.run_success_count = Number(data.run_success_count || 0);
            status.run_retry_total = Number(data.run_retry_total || 0);
            status.run_success_rate = Number(data.run_success_rate || 100);
            status.run_last_retry_reason = String(data.run_last_retry_reason || "");
            status.run_retry_reasons_top = Array.isArray(data.run_retry_reasons_top)
              ? data.run_retry_reasons_top
              : [];
            status.run_elapsed_sec = Number(data.run_elapsed_sec || 0);
            status.run_avg_success_sec = Number(data.run_avg_success_sec || 0);
            message.success("运行统计已恢复默认");
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.run_stats_clear = false;
          }
        }

        async function refreshJson(showSuccess = false) {
          loading.json = true;
          try {
            const data = await apiRequest("/api/data/json");
            jsonRows.value = Array.isArray(data.items)
              ? data.items.map((x) => ({
                path: String((x && x.path) || ""),
                name: String((x && x.name) || ""),
                count: Number((x && x.count) || 0),
                created: String((x && x.created) || "-"),
                note: String((x && x.note) || ""),
                file_color_idx: Number((x && x.file_color_idx) || 0)
              })).filter((x) => x.path)
              : [];

            const latestPathSet = new Set(jsonRows.value.map((x) => x.path));
            for (const row of jsonRows.value) {
              if (!Object.prototype.hasOwnProperty.call(jsonNoteDraft, row.path)) {
                jsonNoteDraft[row.path] = String(row.note || "");
              }
              if (!Object.prototype.hasOwnProperty.call(jsonNoteSaving, row.path)) {
                jsonNoteSaving[row.path] = false;
              }
            }
            for (const key of Object.keys(jsonNoteDraft)) {
              if (!latestPathSet.has(key)) {
                delete jsonNoteDraft[key];
                delete jsonNoteSaving[key];
              }
            }

            jsonInfo.file_count = Number(data.file_count || 0);
            jsonInfo.account_total = Number(data.account_total || 0);
            const allowed = new Set(jsonRows.value.map((x) => x.path));
            jsonSelection.value = jsonSelection.value.filter((k) => allowed.has(k));
            if (showSuccess) message.success("JSON 列表已刷新");
          } finally {
            loading.json = false;
          }
        }

        async function refreshAccounts(showSuccess = false) {
          loading.accounts = true;
          try {
            const data = await apiRequest("/api/data/accounts");
            accountRows.value = Array.isArray(data.items)
              ? data.items.map((x) => Object.assign({}, x, {
                source_color_idx: Number((x && x.source_color_idx) || -1)
              }))
              : [];
            accountInfo.total = Number(data.total || 0);
            accountInfo.path = String(data.path || "local_accounts.db");
            accountInfo.file_options = Array.isArray(data.file_options)
              ? data.file_options.map((name) => ({ label: String(name), value: String(name) }))
              : [];
            const allowed = new Map(accountRows.value.map((x) => [x.key, !!x.locked]));
            accountSelection.value = accountSelection.value.filter((k) => allowed.has(k) && !allowed.get(k));
            if (showSuccess) message.success("账号列表已刷新");
          } finally {
            loading.accounts = false;
          }
        }

        async function loadRemoteCache() {
          const data = await apiRequest("/api/remote/cache");
          if (data && data.provider) {
            settingsForm.remote_account_provider = normalizeRemoteAccountProvider(data.provider);
          }
          remoteRows.value = Array.isArray(data.items)
            ? data.items.map((x) => Object.assign({}, x, { is_dup: !!x.is_dup }))
            : [];
          remoteMeta.total = Number(data.total || 0);
          remoteMeta.pages = Number(data.pages || 1);
          remoteMeta.loaded = Number(data.loaded || 0);
          remoteMeta.ready = !!data.ready;
          remoteMeta.testing = !!data.testing;
          remoteMeta.test_total = Number(data.test_total || 0);
          remoteMeta.test_done = Number(data.test_done || 0);
          remoteMeta.test_ok = Number(data.test_ok || 0);
          remoteMeta.test_fail = Number(data.test_fail || 0);
          const allowed = new Set(remoteRows.value.map((x) => x.key));
          remoteSelection.value = remoteSelection.value.filter((k) => allowed.has(k));
          if (typeof data.testing !== "undefined") {
            status.remote_test_busy = !!data.testing;
          }
        }

        async function fetchRemoteAll() {
          loading.remote = true;
          try {
            await saveConfig(false);
            remoteRows.value = [];
            remoteSelection.value = [];
            remoteMeta.total = 0;
            remoteMeta.pages = 1;
            remoteMeta.loaded = 0;
            remoteMeta.ready = false;
            remoteMeta.testing = false;
            remoteMeta.test_total = 0;
            remoteMeta.test_done = 0;
            remoteMeta.test_ok = 0;
            remoteMeta.test_fail = 0;

            const data = await apiRequest("/api/remote/fetch-all", {
              method: "POST",
              body: { search: remoteSearch.value }
            });
            await loadRemoteCache();
            await refreshAccounts(false);
            message.success(`拉取完成：${Number(data.loaded || remoteMeta.loaded || 0)} 条`);
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.remote = false;
          }
        }

        function remoteSelectAll() {
          remoteSelection.value = remoteRows.value.map((x) => x.key);
        }

        function remoteSelectNone() {
          remoteSelection.value = [];
        }

        function remoteSelectFailed() {
          const keys = remoteRows.value
            .filter((row) => {
              const s = String(row.test_status || "").trim();
              return (
                s === "失败"
                || s === "刷新失败"
                || s === "封禁"
                || s === "Token过期"
                || s === "429限流"
              );
            })
            .map((row) => row.key);
          if (!keys.length) {
            message.warning("没有可选的测试失败账号");
            return;
          }
          remoteSelection.value = Array.from(new Set([...remoteSelection.value, ...keys]));
          message.success(`已勾选失败账号 ${keys.length} 个`);
        }

        function remoteSelectDuplicate() {
          const keys = remoteRows.value
            .filter((row) => !!row.is_dup)
            .map((row) => row.key);
          if (!keys.length) {
            message.warning("当前列表没有重复账号");
            return;
          }
          remoteSelection.value = Array.from(new Set([...remoteSelection.value, ...keys]));
          message.success(`已勾选重复账号 ${keys.length} 个`);
        }

        async function testSelectedRemoteAccounts() {
          if (!remoteSelection.value.length) {
            message.warning("请先勾选服务端账号");
            return;
          }
          loading.remote_test = true;
          try {
            await saveConfig(false);
            const keySet = new Set(remoteSelection.value);
            const ids = remoteRows.value
              .filter((x) => keySet.has(x.key))
              .map((x) => String(x.id || "").trim())
              .filter((x) => x);
            if (!ids.length) {
              message.warning("所选行缺少账号 ID");
              return;
            }
            const data = await apiRequest("/api/remote/test-batch", {
              method: "POST",
              body: { ids }
            });
            await loadRemoteCache();
            await refreshAccounts(false);
            const ok = Number(data.ok || 0);
            const fail = Number(data.fail || 0);
            if (fail === 0) {
              message.success(`批量测试完成：成功 ${ok}`);
            } else {
              message.warning(`批量测试完成：成功 ${ok}，失败 ${fail}`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.remote_test = false;
          }
        }

        async function refreshSelectedRemoteAccounts() {
          if (!remoteSelection.value.length) {
            message.warning("请先勾选服务端账号");
            return;
          }
          loading.remote_refresh = true;
          try {
            await saveConfig(false);
            const keySet = new Set(remoteSelection.value);
            const ids = remoteRows.value
              .filter((x) => keySet.has(x.key))
              .map((x) => String(x.id || "").trim())
              .filter((x) => x);
            if (!ids.length) {
              message.warning("所选行缺少账号 ID");
              return;
            }
            const data = await apiRequest("/api/remote/refresh-batch", {
              method: "POST",
              body: { ids }
            });
            await loadRemoteCache();
            await refreshAccounts(false);
            const ok = Number(data.ok || 0);
            const fail = Number(data.fail || 0);
            const apis = Array.isArray(data.api_summary)
              ? data.api_summary.slice(0, 2)
                .map((x) => `${String((x && x.api) || "-")}×${Number((x && x.count) || 0)}`)
                .join("；")
              : "";
            if (fail === 0) {
              message.success(
                `批量刷新完成：成功 ${ok}`
                + (apis ? `；接口：${apis}` : "")
                + `；并发 ${Number(data.concurrency || 1)}`
              );
            } else {
              const errs = Array.isArray(data.results)
                ? data.results.filter((x) => !x.success).slice(0, 3)
                : [];
              const detail = errs
                .map((x) => `${String((x && x.id) || "-")}: ${String((x && x.detail) || "未知错误")}`)
                .join("；");
              message.warning(
                `批量刷新完成：成功 ${ok}，失败 ${fail}`
                + (detail ? `；原因：${detail}` : "")
                + (apis ? `；接口：${apis}` : "")
                + `；并发 ${Number(data.concurrency || 1)}`
              );
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.remote_refresh = false;
          }
        }

        async function reviveSelectedRemoteAccounts() {
          if (!remoteSelection.value.length) {
            message.warning("请先勾选服务端账号");
            return;
          }
          loading.remote_revive = true;
          try {
            await saveConfig(false);
            const keySet = new Set(remoteSelection.value);
            const rows = remoteRows.value.filter((x) => keySet.has(x.key));
            const ids = rows
              .map((x) => String(x.id || "").trim())
              .filter((x) => x);
            if (!ids.length) {
              message.warning("所选行缺少账号 ID");
              return;
            }

            const isSub2Api = normalizeRemoteAccountProvider(settingsForm.remote_account_provider) === "sub2api";
            const tokenRows = isSub2Api
              ? rows.filter((x) => String(x.test_status || "").trim() === "Token过期")
              : rows;
            if (isSub2Api && !tokenRows.length) {
              message.warning("所选账号中没有“Token过期”状态");
              return;
            }

            const data = await apiRequest("/api/remote/revive-batch", {
              method: "POST",
              body: { ids: tokenRows.map((x) => String(x.id || "").trim()) }
            });
            await loadRemoteCache();
            await refreshAccounts(false);

            const ok = Number(data.ok || 0);
            const fail = Number(data.fail || 0);
            const apis = Array.isArray(data.api_summary)
              ? data.api_summary.slice(0, 2)
                .map((x) => `${String((x && x.api) || "-")}×${Number((x && x.count) || 0)}`)
                .join("；")
              : "";
            if (fail === 0) {
              message.success(
                `复活完成：成功 ${ok}`
                + (apis ? `；接口：${apis}` : "")
                + `；并发 ${Number(data.concurrency || 1)}`
              );
            } else {
              const errs = Array.isArray(data.results)
                ? data.results.filter((x) => !x.success).slice(0, 3)
                : [];
              const detail = errs
                .map((x) => `${String((x && x.id) || "-")}: ${String((x && x.detail) || "未知错误")}`)
                .join("；");
              message.warning(
                `复活完成：成功 ${ok}，失败 ${fail}`
                + (detail ? `；原因：${detail}` : "")
                + (apis ? `；接口：${apis}` : "")
                + `；并发 ${Number(data.concurrency || 1)}`
              );
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.remote_revive = false;
          }
        }

        async function deleteSelectedRemoteAccounts() {
          if (!remoteSelection.value.length) {
            message.warning("请先勾选要删除的账号");
            return;
          }

          const keySet = new Set(remoteSelection.value);
          const rows = remoteRows.value.filter((x) => keySet.has(x.key));
          const ids = rows.map((x) => String(x.id || "").trim()).filter((x) => x);
          if (!ids.length) {
            message.warning("所选行缺少账号 ID");
            return;
          }

          const names = rows
            .map((x) => String(x.name || x.id || ""))
            .slice(0, 10)
            .join("\n");
          remoteDeleteIds.value = ids;
          remoteDeleteAlsoLocal.value = false;
          remoteDeletePreview.value = names + (ids.length > 10 ? "\n…" : "");
          showRemoteDeleteModal.value = true;
        }

        async function confirmRemoteDeleteAccounts() {
          const ids = Array.isArray(remoteDeleteIds.value) ? remoteDeleteIds.value.slice() : [];
          if (!ids.length) {
            message.warning("请先勾选要删除的账号");
            return;
          }

          loading.remote_delete = true;
          try {
            await saveConfig(false);
            const data = await apiRequest("/api/remote/delete-batch", {
              method: "POST",
              body: {
                ids,
                delete_local: !!remoteDeleteAlsoLocal.value
              }
            });

            let refreshOk = true;
            try {
              await apiRequest("/api/remote/fetch-all", {
                method: "POST",
                body: { search: remoteSearch.value }
              });
              await loadRemoteCache();
            } catch (_refreshErr) {
              refreshOk = false;
            }
            await refreshAccounts(false);
            showRemoteDeleteModal.value = false;
            remoteDeleteIds.value = [];

            if (Number(data.fail || 0) === 0) {
              if (refreshOk) {
                message.success(
                  `删除完成：成功 ${data.ok}`
                  + (remoteDeleteAlsoLocal.value ? `，本地数据库删除 ${Number(data.local_deleted || 0)} 条` : "")
                  + "，列表已自动刷新"
                );
              } else {
                message.warning(`删除完成：成功 ${data.ok}，但自动刷新失败，请手动点“获取列表与额度”`);
              }
            } else {
              if (refreshOk) {
                message.warning(`删除完成：成功 ${data.ok}，失败 ${data.fail}，列表已自动刷新`);
              } else {
                message.warning(`删除完成：成功 ${data.ok}，失败 ${data.fail}；自动刷新失败，请手动点“获取列表与额度”`);
              }
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.remote_delete = false;
          }
        }

        async function openRemoteGroupModal() {
          if (normalizeRemoteAccountProvider(settingsForm.remote_account_provider) !== "sub2api") {
            message.warning("CLIProxyAPI 暂不支持分组功能");
            return;
          }
          if (!remoteSelection.value.length) {
            message.warning("请先勾选服务端账号");
            return;
          }
          loading.remote_groups = true;
          try {
            await saveConfig(false);
            const data = await apiRequest("/api/remote/groups", { method: "POST", body: {} });
            const items = Array.isArray(data.items) ? data.items : [];
            remoteGroupOptions.value = items.map((it) => ({
              label: String((it && it.name) || `分组#${String((it && it.id) || "")}`),
              value: Number((it && it.id) || 0)
            })).filter((x) => Number.isFinite(x.value) && x.value > 0);
            if (!remoteGroupOptions.value.length) {
              message.warning("未获取到可用分组");
              return;
            }
            remoteGroupSelection.value = [];
            showRemoteGroupModal.value = true;
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.remote_groups = false;
          }
        }

        async function confirmRemoteGroupBulkUpdate() {
          if (normalizeRemoteAccountProvider(settingsForm.remote_account_provider) !== "sub2api") {
            message.warning("CLIProxyAPI 暂不支持分组功能");
            return;
          }
          if (!remoteSelection.value.length) {
            message.warning("请先勾选服务端账号");
            return;
          }
          if (!remoteGroupSelection.value.length) {
            message.warning("请先选择分组");
            return;
          }
          loading.remote_group_update = true;
          try {
            await saveConfig(false);
            const keySet = new Set(remoteSelection.value);
            const accountIds = remoteRows.value
              .filter((x) => keySet.has(x.key))
              .map((x) => Number(x.id || 0))
              .filter((x) => Number.isFinite(x) && x > 0);
            if (!accountIds.length) {
              message.warning("所选行缺少账号 ID");
              return;
            }
            const groupIds = remoteGroupSelection.value
              .map((x) => Number(x || 0))
              .filter((x) => Number.isFinite(x) && x > 0);
            if (!groupIds.length) {
              message.warning("请先选择分组");
              return;
            }

            const data = await apiRequest("/api/remote/groups/bulk-update", {
              method: "POST",
              body: {
                account_ids: accountIds,
                group_ids: groupIds
              }
            });

            // 本地先行更新“分组”展示，避免必须重新整页拉取。
            const selectedNameMap = new Map(
              remoteGroupOptions.value.map((x) => [Number(x.value), String(x.label || "")])
            );
            const groupLabel = groupIds.map((id) => selectedNameMap.get(id) || `分组#${id}`).join(", ");
            const accountIdSet = new Set(accountIds.map((x) => String(x)));
            remoteRows.value = remoteRows.value.map((row) => {
              if (!accountIdSet.has(String(row.id || ""))) return row;
              return Object.assign({}, row, { groups: groupLabel || row.groups });
            });

            showRemoteGroupModal.value = false;
            message.success(`批量分组完成：账号 ${Number(data.ok || accountIds.length)} 个`);
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.remote_group_update = false;
          }
        }

        function jsonSelectAll() {
          jsonSelection.value = jsonRows.value.map((x) => x.path);
        }

        function jsonSelectNone() {
          jsonSelection.value = [];
        }

        async function deleteSelectedJson() {
          if (!jsonSelection.value.length) {
            message.warning("请先勾选要删除的 JSON");
            return;
          }
          const names = jsonRows.value
            .filter((x) => jsonSelection.value.includes(x.path))
            .map((x) => x.name)
            .slice(0, 12)
            .join("\n");
          const ok = window.confirm(`将永久删除以下 JSON：\n\n${names}${jsonSelection.value.length > 12 ? "\n…" : ""}\n\n此操作不可恢复。`);
          if (!ok) return;

          try {
            const data = await apiRequest("/api/data/json/delete", {
              method: "POST",
              body: { paths: jsonSelection.value }
            });
            jsonSelection.value = [];
            await Promise.all([refreshJson(false), refreshAccounts(false)]);
            message.success(`删除完成：JSON ${data.removed_files} 个，账号行 ${data.removed_lines} 条`);
          } catch (e) {
            message.error(String(e.message || e));
          }
        }

        function acctSelectAll() {
          accountSelection.value = accountRows.value
            .filter((x) => !x.locked)
            .map((x) => x.key);
        }

        function acctSelectNone() {
          accountSelection.value = [];
        }

        function acctSelectByCount() {
          const n = Math.max(0, Number(accountPickCount.value || 0));
          if (!n) {
            message.warning("请先输入勾选数量");
            return;
          }
          const candidates = accountExportableRows();
          const keys = candidates.slice(0, n).map((row) => row.key);
          if (!keys.length) {
            message.warning("没有可勾选账号（已导出/已导入账号不可勾选）");
            return;
          }
          accountSelection.value = keys;
          if (keys.length < n) {
            message.warning(`仅可勾选 ${keys.length} 个账号（其余已导出或已导入）`);
          } else {
            message.success(`已按数量勾选 ${keys.length} 个账号`);
          }
        }

        async function deleteSelectedLocalAccounts() {
          if (!accountSelection.value.length) {
            message.warning("请先勾选要删除的账号");
            return;
          }

          const emails = accountSelectedEmails(true);
          if (!emails.length) {
            message.warning("所选项未包含有效邮箱");
            return;
          }

          const preview = emails.slice(0, 12).join("\n");
          const ok = window.confirm(
            `将删除以下本地账号（共 ${emails.length} 个）：\n\n${preview}${emails.length > 12 ? "\n…" : ""}\n\n` +
            "会同时清理 local_accounts.db、accounts.txt 以及 accounts_*.json 中对应账号。此操作不可恢复。"
          );
          if (!ok) return;

          loading.local_delete = true;
          try {
            const data = await apiRequest("/api/data/accounts/delete", {
              method: "POST",
              body: { emails }
            });
            accountSelection.value = [];
            await refreshAccounts(false);
            message.success(
              `删除完成：账号 ${Number(data.deleted || 0)} 条，`
              + `accounts.txt ${Number(data.removed_txt_lines || 0)} 行，`
              + `JSON ${Number(data.removed_json_accounts || 0)} 条`
            );
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.local_delete = false;
          }
        }

        async function syncSelectedAccounts(targetProvider = "") {
          if (!accountSelection.value.length) {
            message.warning("请先勾选账号");
            return;
          }
          const provider = normalizeRemoteAccountProvider(targetProvider || settingsForm.remote_account_provider || "sub2api");
          const label = provider === "cliproxyapi" ? "CPA" : "Sub2API";
          const selectedKeySet = new Set(accountSelection.value);
          const selectedRows = accountRows.value
            .filter((x) => selectedKeySet.has(x.key) && !x.locked);
          const emailsPreview = selectedRows
            .map((x) => String(x.email || ""))
            .filter((x) => x)
            .slice(0, 12)
            .join("\n");
          const confirmText =
            `将导入到 ${label}（共 ${selectedRows.length} 个账号）：\n\n`
            + `${emailsPreview}${selectedRows.length > 12 ? "\n…" : ""}`
            + "\n\n确认继续吗？";
          if (!window.confirm(confirmText)) {
            return;
          }
          loading.sync = true;
          try {
            await saveConfig(false);
            const emails = accountSelectedEmails();
            const data = await apiRequest("/api/data/sync", {
              method: "POST",
              body: { emails, provider }
            });
            await refreshAccounts(false);
            const lowerLabel = provider === "cliproxyapi" ? "cpa" : "sub2api";
            message.success(`导入到${lowerLabel}结束：成功 ${data.ok}，失败 ${data.fail}`);
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.sync = false;
          }
        }

        async function exportSelectedCodeX() {
          if (!accountSelection.value.length) {
            message.warning("请先勾选账号");
            return;
          }
          loading.codex_export = true;
          try {
            await saveConfig(false);
            const emails = accountSelectedEmails();
            if (!emails.length) {
              message.warning("勾选项未包含有效邮箱");
              return;
            }

            const data = await apiRequest("/api/data/codex/export", {
              method: "POST",
              body: { emails }
            });

            const exported = Number((data && data.exported) || 0);
            const missing = Array.isArray(data && data.missing) ? data.missing : [];
            const fileName = String((data && data.filename) || "codex_export.bin");
            const dir = String((data && data.output_dir) || "");
            const opened = !!(data && data.opened_dir);
            const openSuffix = opened ? "，已打开目录" : "";
            if (missing.length) {
              message.warning(`导出完成：${exported} 个，缺失 ${missing.length} 个（${fileName}）${openSuffix}`);
            } else {
              message.success(`导出完成：${exported} 个（${fileName}）${openSuffix}`);
            }
            if (dir) {
              message.info(`导出目录：${dir}`);
            }
            await refreshAccounts(false);
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.codex_export = false;
          }
        }

        function resetMailDetail() {
          selectedMailId.value = "";
          mailDetail.id = "";
          mailDetail.from = "";
          mailDetail.subject = "";
          mailDetail.date = "";
          mailDetail.content = "";
          showMailModal.value = false;
        }

        function currentMailProviderKey() {
          return normalizeMailProvider(mailProviderTab.value || settingsForm.mail_service_provider || "mailfree");
        }

        function snapshotMailViewToCache() {
          const key = currentMailProviderKey();
          const target = mailViewCache[key] || {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          };
          if (!mailViewCache[key]) {
            mailViewCache[key] = target;
          }
          target.domains = Array.isArray(mailDomains.value) ? [...mailDomains.value] : [];
          target.mailboxRows = Array.isArray(mailboxRows.value)
            ? mailboxRows.value.map((x) => Object.assign({}, x))
            : [];
          target.selectedMailbox = String(selectedMailbox.value || "");
          target.mailRows = Array.isArray(mailRows.value)
            ? mailRows.value.map((x) => Object.assign({}, x))
            : [];
          target.mailTotal = Number(mailState.email_total || 0);
        }

        function restoreMailViewFromCache(provider) {
          const key = normalizeMailProvider(provider || "mailfree");
          const source = mailViewCache[key] || {
            domains: [],
            mailboxRows: [],
            selectedMailbox: "",
            mailRows: [],
            mailTotal: 0
          };
          if (!mailViewCache[key]) {
            mailViewCache[key] = source;
          }
          mailDomains.value = Array.isArray(source.domains) ? [...source.domains] : [];
          mailboxRows.value = Array.isArray(source.mailboxRows)
            ? source.mailboxRows.map((x) => Object.assign({}, x))
            : [];
          selectedMailbox.value = String(source.selectedMailbox || "");
          mailRows.value = Array.isArray(source.mailRows)
            ? source.mailRows.map((x) => Object.assign({}, x))
            : [];
          mailState.email_total = Number(source.mailTotal || 0);
          mailboxSelection.value = [];
          mailSelection.value = [];
          resetMailDetail();
        }

        function applyMailOverview(data) {
          const providers = Array.isArray(data.providers) ? data.providers : [];
          mailProviders.value = providers.map((it) => ({
            label: String((it && it.label) || ""),
            value: String((it && it.value) || "")
          })).filter((it) => it.label && it.value);

          const current = normalizeMailProvider(data.current || settingsForm.mail_service_provider || "mailfree");
          settingsForm.mail_service_provider = current;
          mailProviderTab.value = current;
          if (current !== "mailfree") {
            mailfreePanelTab.value = "basic";
          }
          mailState.provider = current;
          mailDomains.value = Array.isArray(data.domains)
            ? normalizeDomainList(data.domains)
            : [];

          const allowFromApi = normalizeDomainList(data.selected_domains || []);
          const allowFromForm = normalizeDomainList(settingsForm.mail_domain_allowlist || []);
          const domainSet = new Set(mailDomains.value);
          let allow = allowFromApi.length ? allowFromApi : allowFromForm;
          allow = allow.filter((d) => domainSet.has(d));
          if (!allow.length && mailDomains.value.length) {
            allow = [...mailDomains.value];
          }
          setDomainSelection(allow);

          const directCounts = (data && data.domain_error_counts) || {};
          const directRegistered = (data && data.domain_registered_counts) || {};
          const stats = (data && data.domain_stats) || {};
          const merged = {};
          const mergedRegistered = {};
          if (directCounts && typeof directCounts === "object") {
            for (const [k, v] of Object.entries(directCounts)) {
              const d = String(k || "").trim().toLowerCase();
              const n = Number(v || 0);
              if (d && Number.isFinite(n) && n > 0) merged[d] = n;
            }
          }
          if (directRegistered && typeof directRegistered === "object") {
            for (const [k, v] of Object.entries(directRegistered)) {
              const d = String(k || "").trim().toLowerCase();
              const n = Number(v || 0);
              if (d && Number.isFinite(n) && n > 0) mergedRegistered[d] = n;
            }
          }
          if (stats && typeof stats === "object") {
            for (const [k, v] of Object.entries(stats)) {
              const d = String(k || "").trim().toLowerCase();
              const n = Number((v && v.errors) || 0);
              if (d && Number.isFinite(n) && n > 0) merged[d] = n;
              const reg = Number((v && v.registered) || 0);
              if (d && Number.isFinite(reg) && reg > 0) mergedRegistered[d] = reg;
            }
          }
          applyDomainStats({
            error_counts: merged,
            registered_counts: mergedRegistered,
            selected: allow
          });

          mailboxRows.value = Array.isArray(data.mailboxes)
            ? data.mailboxes.map((x) => ({
              key: String((x && x.key) || ((x && x.address) || "")),
              address: String((x && x.address) || ""),
              created_at: String((x && x.created_at) || "-"),
              expires_at: String((x && x.expires_at) || "-"),
              count: Number((x && x.count) || 0)
            })).filter((x) => x.address)
            : [];

          const allowedMailboxKeys = new Set(mailboxRows.value.map((x) => x.key));
          mailboxSelection.value = mailboxSelection.value.filter((k) => allowedMailboxKeys.has(k));

          const addrSet = new Set(mailboxRows.value.map((x) => x.address));
          if (!selectedMailbox.value || !addrSet.has(selectedMailbox.value)) {
            selectedMailbox.value = "";
            mailRows.value = [];
            mailSelection.value = [];
            mailState.email_total = 0;
            resetMailDetail();
          }
          mailState.loaded = true;
          snapshotMailViewToCache();
        }

        async function loadMailProviders() {
          const data = await apiRequest("/api/mail/providers");
          applyMailOverview({
            providers: data.items || [],
            current: data.current || "mailfree",
            domains: mailDomains.value,
            selected_domains: settingsForm.mail_domain_allowlist,
            domain_error_counts: mailDomainErrors,
            domain_registered_counts: mailDomainRegistered,
            mailboxes: mailboxRows.value
          });
          mailState.loaded = false;
        }

        async function refreshGraphAccountFiles(showError = false) {
          if (normalizeGraphAccountsMode(settingsForm.graph_accounts_mode) !== "file") {
            graphAccountFileOptions.value = [];
            return;
          }
          loading.graph_files = true;
          try {
            const data = await apiRequest("/api/mail/graph-account-files");
            const items = Array.isArray(data.items) ? data.items : [];
            graphAccountFileOptions.value = items.map((x) => ({
              label: String((x && x.label) || (x && x.value) || ""),
              value: String((x && x.value) || "")
            })).filter((x) => x.label && x.value);
          } catch (e) {
            if (showError) {
              message.error(String(e.message || e));
            }
          } finally {
            loading.graph_files = false;
          }
        }

        function pickGraphAccountFile() {
          if (normalizeGraphAccountsMode(settingsForm.graph_accounts_mode) !== "file") {
            message.warning("接口模式无需选择账号文件");
            return;
          }
          const el = graphFileInputRef.value;
          if (!el) {
            message.error("文件选择器不可用");
            return;
          }
          el.value = "";
          el.click();
        }

        async function onGraphAccountFilePicked(e) {
          if (normalizeGraphAccountsMode(settingsForm.graph_accounts_mode) !== "file") {
            return;
          }
          const files = (e && e.target && e.target.files) ? e.target.files : null;
          if (!files || !files.length) return;
          const file = files[0];
          const name = String((file && file.name) || "").trim();
          if (!name.toLowerCase().endsWith(".txt")) {
            message.error("仅支持 .txt 文件");
            return;
          }
          loading.graph_files = true;
          try {
            const text = await file.text();
            const data = await apiRequest("/api/mail/graph-account-file/import", {
              method: "POST",
              body: { filename: name, content: text }
            });
            settingsForm.graph_accounts_file = String((data && data.filename) || name);
            await refreshGraphAccountFiles(false);
            message.success(`导入成功：${Number((data && data.count) || 0)} 条账号`);
          } catch (err) {
            message.error(String(err.message || err));
          } finally {
            loading.graph_files = false;
            if (graphFileInputRef.value) {
              graphFileInputRef.value.value = "";
            }
          }
        }

        async function deleteSelectedGraphAccountFile() {
          if (normalizeGraphAccountsMode(settingsForm.graph_accounts_mode) !== "file") {
            message.warning("接口模式没有本地账号文件可删除");
            return;
          }
          const target = String(settingsForm.graph_accounts_file || "").trim();
          if (!target) {
            message.warning("请先选择要删除的 Graph 账号文件");
            return;
          }
          const ok = window.confirm(`确认删除文件 ${target} ？此操作不可恢复。`);
          if (!ok) return;
          loading.graph_files = true;
          try {
            await apiRequest("/api/mail/graph-account-file/delete", {
              method: "POST",
              body: { filename: target }
            });
            settingsForm.graph_accounts_file = "";
            await refreshGraphAccountFiles(false);
            await saveConfig(false);
            message.success(`已删除：${target}`);
          } catch (err) {
            message.error(String(err.message || err));
          } finally {
            loading.graph_files = false;
          }
        }

        function updateMailProviderByTab(nextVal) {
          snapshotMailViewToCache();
          const val = normalizeMailProvider(nextVal || "mailfree");
          mailProviderTab.value = val;
          settingsForm.mail_service_provider = mailProviderTab.value;
          if (mailProviderTab.value !== "mailfree") {
            mailfreePanelTab.value = "basic";
          }
          restoreMailViewFromCache(mailProviderTab.value);
          if (mailProviderTab.value === "graph" && normalizeGraphAccountsMode(settingsForm.graph_accounts_mode) === "file") {
            refreshGraphAccountFiles(false);
          }
          if (mailProviderTab.value === "mailfree" && mailfreePanelTab.value === "domain") {
            refreshMailfreeCfZones(false)
              .then(() => refreshMailfreeCfDnsRecords(false))
              .catch(() => {});
          }
          refreshMailOverview(false);
        }

        async function updateRemoteAccountProvider(nextVal) {
          const val = normalizeRemoteAccountProvider(nextVal || "sub2api");
          settingsForm.remote_account_provider = val;
          try {
            await saveConfig(false);
          } catch (_e) {
            // 配置失败时保持现有视图，用户可重试。
          }
          remoteRows.value = [];
          remoteSelection.value = [];
          remoteMeta.total = 0;
          remoteMeta.pages = 1;
          remoteMeta.loaded = 0;
          remoteMeta.ready = false;
          remoteMeta.testing = false;
          remoteMeta.test_total = 0;
          remoteMeta.test_done = 0;
          remoteMeta.test_ok = 0;
          remoteMeta.test_fail = 0;
          await loadRemoteCache();
        }

        async function loadMailDomainStats() {
          try {
            const data = await apiRequest("/api/mail/domain-stats");
            applyDomainStats(data || {});
          } catch (_e) {
            // 统计接口失败不影响主流程。
          }
        }

        function normalizeCfDomainValue(raw) {
          let text = String(raw || "").trim().toLowerCase();
          if (!text) return "";
          text = text.replace(/^https?:\/\//, "");
          text = text.replace(/\/$/, "");
          text = text.replace(/^\.+|\.+$/g, "");
          if (text.includes("@")) {
            text = text.split("@").pop();
          }
          if (text.includes(":")) {
            text = text.split(":", 1)[0];
          }
          return String(text || "").trim().toLowerCase();
        }

        function selectedCfZoneName() {
          const hit = cfZoneOptions.value.find((x) => String(x.value || "") === String(cfZoneId.value || ""));
          return normalizeCfDomainValue((hit && hit.label) || "");
        }

        async function refreshMailfreeCfZones(showSuccess = false) {
          loading.mail_cf_zones = true;
          try {
            await saveConfig(false);
            const data = await apiRequest("/api/mail/cf/zones", { method: "POST", body: {} });
            const zones = Array.isArray(data.zones) ? data.zones : [];
            cfZoneOptions.value = zones
              .map((x) => ({
                label: String((x && x.name) || "").trim().toLowerCase(),
                value: String((x && x.id) || "").trim(),
                account_id: String((x && x.account_id) || "").trim(),
                account_name: String((x && x.account_name) || "").trim()
              }))
              .filter((x) => x.label && x.value);

            const zoneSet = new Set(cfZoneOptions.value.map((x) => x.value));
            const apiZone = String((data && data.selected_zone_id) || "").trim();
            if (apiZone && zoneSet.has(apiZone)) {
              cfZoneId.value = apiZone;
            } else if (!zoneSet.has(String(cfZoneId.value || ""))) {
              cfZoneId.value = cfZoneOptions.value.length ? String(cfZoneOptions.value[0].value || "") : "";
            }

            if (data && data.account_id) {
              settingsForm.cf_account_id = String(data.account_id || "").trim();
            }
            settingsForm.cf_worker_script = String((data && data.worker_script) || settingsForm.cf_worker_script || "mailfree").trim();
            settingsForm.cf_worker_mail_domain_binding = String(
              (data && data.worker_binding) || settingsForm.cf_worker_mail_domain_binding || "MAIL_DOMAIN"
            ).trim();

            const target = normalizeCfDomainValue((data && data.target_domain) || settingsForm.cf_dns_target_domain || "");
            cfTargetDomain.value = target || selectedCfZoneName();
            settingsForm.cf_dns_target_domain = String(cfTargetDomain.value || "");

            if (showSuccess) {
              message.success(`Cloudflare 域名已刷新：${cfZoneOptions.value.length} 个`);
            }
          } catch (e) {
            if (showSuccess) {
              message.error(String(e.message || e));
            }
          } finally {
            loading.mail_cf_zones = false;
          }
        }

        async function refreshMailfreeCfDnsRecords(showSuccess = false) {
          const zid = String(cfZoneId.value || "").trim();
          if (!zid) {
            cfDnsRows.value = [];
            cfDnsSelection.value = [];
            if (showSuccess) message.warning("请先选择域名");
            return;
          }
          loading.mail_cf_dns = true;
          try {
            await saveConfig(false);
            const data = await apiRequest("/api/mail/cf/dns/list", {
              method: "POST",
              body: { zone_id: zid }
            });
            cfDnsRows.value = Array.isArray(data.records)
              ? data.records.map((x, idx) => ({
                key: String((x && x.id) || `cf-dns-${idx + 1}`),
                id: String((x && x.id) || ""),
                label: String((x && x.label) || "").trim().toLowerCase(),
                name: String((x && x.name) || "").trim().toLowerCase(),
                target: String((x && x.target) || "").trim().toLowerCase(),
                zone_id: String((x && x.zone_id) || zid),
                zone_name: String((x && x.zone_name) || selectedCfZoneName()),
                ttl: Number((x && x.ttl) || 1),
                proxied: !!(x && x.proxied)
              })).filter((x) => x.id && x.name)
              : [];
            const keySet = new Set(cfDnsRows.value.map((x) => x.key));
            cfDnsSelection.value = cfDnsSelection.value.filter((k) => keySet.has(k));

            const targetNow = normalizeCfDomainValue(cfTargetDomain.value || settingsForm.cf_dns_target_domain || "");
            cfTargetDomain.value = targetNow || selectedCfZoneName();
            settingsForm.cf_dns_target_domain = String(cfTargetDomain.value || "");

            if (showSuccess) {
              message.success(`已加载 CNAME 记录：${cfDnsRows.value.length} 条`);
            }
          } catch (e) {
            if (showSuccess) {
              message.error(String(e.message || e));
            }
          } finally {
            loading.mail_cf_dns = false;
          }
        }

        function openCfDnsAddModal() {
          const zid = String(cfZoneId.value || "").trim();
          if (!zid) {
            message.warning("请先选择域名");
            return;
          }
          cfDnsAddForm.count = Math.max(1, Number(cfDnsAddForm.count || 5));
          cfDnsAddForm.mode = String(cfDnsAddForm.mode || "random").trim().toLowerCase() === "manual"
            ? "manual"
            : "random";
          cfDnsAddForm.random_length = Math.max(3, Number(cfDnsAddForm.random_length || 8));
          showCfDnsAddModal.value = true;
        }

        async function confirmCfDnsBatchCreate() {
          const zid = String(cfZoneId.value || "").trim();
          if (!zid) {
            message.warning("请先选择域名");
            return;
          }
          const target = normalizeCfDomainValue(cfTargetDomain.value || selectedCfZoneName());
          if (!target) {
            message.warning("请先选择 CNAME 指向域名");
            return;
          }
          if (String(cfDnsAddForm.mode || "") === "manual" && !String(cfDnsAddForm.manual_name || "").trim()) {
            message.warning("手动模式请填写二级域名前缀");
            return;
          }

          loading.mail_cf_dns_create = true;
          try {
            cfTargetDomain.value = target;
            settingsForm.cf_dns_target_domain = target;
            await saveConfig(false);
            const data = await apiRequest("/api/mail/cf/dns/create", {
              method: "POST",
              body: {
                zone_id: zid,
                target_domain: target,
                count: Number(cfDnsAddForm.count || 1),
                mode: String(cfDnsAddForm.mode || "random"),
                random_prefix: String(cfDnsAddForm.random_prefix || "").trim(),
                random_length: Number(cfDnsAddForm.random_length || 8),
                manual_name: String(cfDnsAddForm.manual_name || "").trim(),
                proxied: !!cfDnsAddForm.proxied,
                ttl: Number(cfDnsAddForm.ttl || 1)
              }
            });

            const ok = Number((data && data.ok) || 0);
            const fail = Number((data && data.fail) || 0);
            await refreshMailfreeCfDnsRecords(false);
            if (ok > 0) {
              showCfDnsAddModal.value = false;
            }
            if (fail > 0) {
              message.warning(`批量新增完成：成功 ${ok}，失败 ${fail}`);
            } else {
              message.success(`批量新增完成：成功 ${ok}`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_cf_dns_create = false;
          }
        }

        function openCfDnsEditModal(row) {
          if (!row) {
            message.warning("请先选择一条 DNS 记录");
            return;
          }
          cfDnsEditForm.record_id = String(row.id || "").trim();
          cfDnsEditForm.label = String(row.label || "").trim().toLowerCase();
          cfDnsEditForm.proxied = !!row.proxied;
          cfDnsEditForm.ttl = Number(row.ttl || 1);
          showCfDnsEditModal.value = true;
        }

        async function confirmCfDnsUpdate() {
          const zid = String(cfZoneId.value || "").trim();
          const rid = String(cfDnsEditForm.record_id || "").trim();
          const label = String(cfDnsEditForm.label || "").trim();
          const target = normalizeCfDomainValue(cfTargetDomain.value || selectedCfZoneName());
          if (!zid || !rid) {
            message.warning("记录信息不完整，请重试");
            return;
          }
          if (!label) {
            message.warning("请填写二级域名前缀");
            return;
          }
          if (!target) {
            message.warning("请先选择 CNAME 指向域名");
            return;
          }

          loading.mail_cf_dns_update = true;
          try {
            cfTargetDomain.value = target;
            settingsForm.cf_dns_target_domain = target;
            await saveConfig(false);
            await apiRequest("/api/mail/cf/dns/update", {
              method: "POST",
              body: {
                zone_id: zid,
                record_id: rid,
                label,
                target_domain: target,
                proxied: !!cfDnsEditForm.proxied,
                ttl: Number(cfDnsEditForm.ttl || 1)
              }
            });
            showCfDnsEditModal.value = false;
            await refreshMailfreeCfDnsRecords(false);
            message.success("DNS 记录已更新");
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_cf_dns_update = false;
          }
        }

        async function deleteSelectedCfDnsRecords() {
          const zid = String(cfZoneId.value || "").trim();
          if (!zid) {
            message.warning("请先选择域名");
            return;
          }
          const keySet = new Set(cfDnsSelection.value);
          const ids = cfDnsRows.value
            .filter((x) => keySet.has(x.key))
            .map((x) => String(x.id || "").trim())
            .filter((x) => !!x);
          if (!ids.length) {
            message.warning("请先勾选要删除的 DNS 记录");
            return;
          }
          const ok = window.confirm(`确认删除已选 ${ids.length} 条 DNS 记录？该操作不可恢复。`);
          if (!ok) return;

          loading.mail_cf_dns_delete = true;
          try {
            await saveConfig(false);
            const data = await apiRequest("/api/mail/cf/dns/delete", {
              method: "POST",
              body: { zone_id: zid, record_ids: ids }
            });
            const successCount = Number((data && data.ok) || 0);
            const failCount = Number((data && data.fail) || 0);
            cfDnsSelection.value = [];
            await refreshMailfreeCfDnsRecords(false);
            if (failCount > 0) {
              message.warning(`删除完成：成功 ${successCount}，失败 ${failCount}`);
            } else {
              message.success(`删除完成：成功 ${successCount}`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_cf_dns_delete = false;
          }
        }

        async function setCfWorkerMailDomain(row) {
          const domain = normalizeCfDomainValue((row && row.name) || "");
          if (!domain) {
            message.warning("该记录缺少完整域名");
            return;
          }
          loading.mail_cf_worker_set = true;
          try {
            settingsForm.cf_dns_target_domain = normalizeCfDomainValue(cfTargetDomain.value || settingsForm.cf_dns_target_domain || "");
            await saveConfig(false);
            const data = await apiRequest("/api/mail/cf/worker/set-mail-domain", {
              method: "POST",
              body: {
                mail_domain: domain
              }
            });
            await refreshMailOverview(false);
            const existed = !!(data && data.existed);
            if (existed) {
              message.success(`域名已存在于 MailFree：${domain}`);
            } else {
              message.success(`已同步到 MailFree 域名池：${domain}`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_cf_worker_set = false;
          }
        }

        async function syncSelectedCfDnsToMailfree() {
          const keySet = new Set(cfDnsSelection.value);
          const rows = cfDnsRows.value.filter((x) => keySet.has(x.key));
          if (!rows.length) {
            message.warning("请先勾选要同步的 DNS 记录");
            return;
          }

          const domains = [];
          const seen = new Set();
          for (const row of rows) {
            const dm = normalizeCfDomainValue((row && row.name) || "");
            if (!dm || seen.has(dm)) continue;
            seen.add(dm);
            domains.push(dm);
          }
          if (!domains.length) {
            message.warning("未找到可同步的完整域名");
            return;
          }

          const ok = window.confirm(`确认批量同步 ${domains.length} 个域名到 MailFree 域名池？`);
          if (!ok) return;

          loading.mail_cf_worker_batch = true;
          try {
            settingsForm.cf_dns_target_domain = normalizeCfDomainValue(cfTargetDomain.value || settingsForm.cf_dns_target_domain || "");
            await saveConfig(false);

            let success = 0;
            let existed = 0;
            let fail = 0;
            const errorSamples = [];

            for (const domain of domains) {
              try {
                const data = await apiRequest("/api/mail/cf/worker/set-mail-domain", {
                  method: "POST",
                  body: { mail_domain: domain }
                });
                success += 1;
                if (data && data.existed) {
                  existed += 1;
                }
              } catch (e) {
                fail += 1;
                if (errorSamples.length < 3) {
                  errorSamples.push(`${domain}: ${String(e.message || e)}`);
                }
              }
            }

            await refreshMailOverview(false);

            if (fail > 0) {
              const sampleText = errorSamples.length ? `；示例：${errorSamples.join(" | ")}` : "";
              message.warning(`批量同步完成：成功 ${success}（已存在 ${existed}），失败 ${fail}${sampleText}`);
            } else {
              message.success(`批量同步完成：成功 ${success}（已存在 ${existed}）`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_cf_worker_batch = false;
          }
        }

        async function refreshMailOverview(showSuccess = true) {
          loading.mail_overview = true;
          try {
            settingsForm.mail_service_provider = normalizeMailProvider(mailProviderTab.value || settingsForm.mail_service_provider);
            await saveConfig(false);
            const data = await apiRequest("/api/mail/overview", {
              method: "POST",
              body: { limit: 500, offset: 0 }
            });
            applyMailOverview(data || {});
            await loadMailDomainStats();
            if (selectedMailbox.value) {
              await loadMailboxEmails(selectedMailbox.value, false);
            }
            if (showSuccess) {
              message.success(`邮箱概览已刷新：${mailDomains.value.length} 个域名，${mailboxRows.value.length} 个邮箱`);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_overview = false;
          }
        }

        function mailboxSelectAll() {
          mailboxSelection.value = filteredMailboxRows.value.map((x) => x.key);
        }

        function mailboxSelectNone() {
          mailboxSelection.value = [];
        }

        async function loadMailboxEmails(mailbox, showError = true) {
          const target = String(mailbox || "").trim();
          if (!target) {
            mailRows.value = [];
            mailSelection.value = [];
            mailState.email_total = 0;
            resetMailDetail();
            return;
          }
          loading.mail_emails = true;
          try {
            const data = await apiRequest("/api/mail/emails", {
              method: "POST",
              body: { mailbox: target }
            });
            selectedMailbox.value = target;
            mailRows.value = Array.isArray(data.items)
              ? data.items.map((x) => ({
                key: String((x && x.key) || ((x && x.id) || "")),
                id: String((x && x.id) || ""),
                from: String((x && x.from) || "-"),
                subject: String((x && x.subject) || "(无主题)"),
                date: String((x && x.date) || "-"),
                preview: String((x && x.preview) || ""),
                mailbox: String((x && x.mailbox) || target)
              })).filter((x) => x.id)
              : [];
            mailState.email_total = Number(data.total || mailRows.value.length || 0);

            const allowed = new Set(mailRows.value.map((x) => x.key));
            mailSelection.value = mailSelection.value.filter((k) => allowed.has(k));
            const selectedRow = mailRows.value.find((x) => x.id === selectedMailId.value);
            if (!selectedRow) {
              resetMailDetail();
            }
            snapshotMailViewToCache();
          } catch (e) {
            if (showError) message.error(String(e.message || e));
          } finally {
            loading.mail_emails = false;
          }
        }

        async function refreshSelectedMailboxEmails() {
          if (!selectedMailbox.value) {
            message.warning("请先点击一个邮箱账号");
            return;
          }
          await loadMailboxEmails(selectedMailbox.value, true);
          message.success("邮件列表已刷新");
        }

        async function loadMailDetail(mailId, showError = true) {
          const target = String(mailId || "").trim();
          if (!target) {
            resetMailDetail();
            showMailModal.value = false;
            return false;
          }
          loading.mail_detail = true;
          try {
            const data = await apiRequest("/api/mail/email/detail", {
              method: "POST",
              body: { id: target }
            });
            selectedMailId.value = String(data.id || target);
            mailDetail.id = String(data.id || target);
            mailDetail.from = String(data.from || "-");
            mailDetail.subject = String(data.subject || "(无主题)");
            mailDetail.date = String(data.date || "-");
            mailDetail.content = String(data.content || data.text || "");
            return true;
          } catch (e) {
            if (showError) message.error(String(e.message || e));
            return false;
          } finally {
            loading.mail_detail = false;
          }
        }

        async function openMailboxRow(row) {
          if (!row || !row.address) return;
          await loadMailboxEmails(row.address, true);
        }

        function mailboxRowProps(row) {
          return {
            style: row && row.address === selectedMailbox.value
              ? "background: rgba(62,166,255,.12); box-shadow: inset 0 0 0 2px rgba(62,166,255,.55);"
              : "",
            onClick: () => {
              openMailboxRow(row);
            }
          };
        }

        async function openMailRow(row) {
          if (!row || !row.id) return;
          const ok = await loadMailDetail(row.id, true);
          if (ok) {
            showMailModal.value = true;
          }
        }

        function mailRowProps(row) {
          return {
            style: row && row.id === selectedMailId.value
              ? "background: rgba(69,212,175,.14); box-shadow: inset 0 0 0 2px rgba(69,212,175,.55);"
              : "",
            onClick: () => {
              openMailRow(row);
            }
          };
        }

        async function generateMailbox() {
          loading.mail_generate = true;
          try {
            await saveConfig(false);
            const data = await apiRequest("/api/mail/generate", { method: "POST", body: {} });
            const email = String(data.email || "");
            if (!email) throw new Error("生成邮箱失败：返回为空");
            await refreshMailOverview(false);
            selectedMailbox.value = email;
            await loadMailboxEmails(email, false);
            message.success(`已生成邮箱：${email}`);
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_generate = false;
          }
        }

        async function deleteSelectedMailboxes() {
          if (!mailboxSelection.value.length) {
            message.warning("请先勾选要删除的邮箱");
            return;
          }
          const keySet = new Set(mailboxSelection.value);
          const targets = mailboxRows.value.filter((x) => keySet.has(x.key)).map((x) => x.address);
          if (!targets.length) {
            message.warning("所选项不包含有效邮箱地址");
            return;
          }
          const names = targets.slice(0, 10).join("\n");
          const ok = window.confirm(
            `将删除以下邮箱（共 ${targets.length} 个）：\n\n${names}${targets.length > 10 ? "\n…" : ""}\n\n此操作不可恢复。`
          );
          if (!ok) return;

          loading.mailbox_delete = true;
          try {
            const data = await apiRequest("/api/mail/mailboxes/delete", {
              method: "POST",
              body: { addresses: targets }
            });
            mailboxSelection.value = [];
            await refreshMailOverview(false);
            if (selectedMailbox.value && !mailboxRows.value.some((x) => x.address === selectedMailbox.value)) {
              selectedMailbox.value = "";
              mailRows.value = [];
              mailSelection.value = [];
              mailState.email_total = 0;
              resetMailDetail();
            }
            const apis = Array.isArray(data.api_summary)
              ? data.api_summary.slice(0, 2)
                .map((x) => `${String((x && x.api) || "-")}×${Number((x && x.count) || 0)}`)
                .join("；")
              : "";
            if (Number(data.fail || 0) === 0) {
              const msg = `邮箱删除完成：成功 ${data.ok}`
                + (apis ? `；接口：${apis}` : "")
                + `；并发 ${Number(data.concurrency || 1)}`;
              message.success(msg);
            } else {
              const errs = Array.isArray(data.errors) ? data.errors : [];
              const detail = errs
                .slice(0, 3)
                .map((x) => `${String((x && x.address) || "-")}: ${String((x && x.error) || "未知错误")}`)
                .join("；");
              const suffix = errs.length > 3 ? "；..." : "";
              const msg = `邮箱删除完成：成功 ${data.ok}，失败 ${data.fail}`
                + (detail ? `；原因：${detail}${suffix}` : "")
                + (apis ? `；接口：${apis}` : "")
                + `；并发 ${Number(data.concurrency || 1)}`;
              message.warning(msg);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mailbox_delete = false;
          }
        }

        async function deleteSelectedEmails() {
          if (!mailSelection.value.length) {
            message.warning("请先勾选要删除的邮件");
            return;
          }
          const keySet = new Set(mailSelection.value);
          const ids = mailRows.value.filter((x) => keySet.has(x.key)).map((x) => x.id);
          if (!ids.length) {
            message.warning("所选项不包含有效邮件 ID");
            return;
          }
          const ok = window.confirm(`将删除已选邮件 ${ids.length} 封，确认继续？`);
          if (!ok) return;

          loading.mail_delete = true;
          try {
            const data = await apiRequest("/api/mail/emails/delete", {
              method: "POST",
              body: { ids }
            });
            mailSelection.value = [];
            if (ids.includes(String(selectedMailId.value || ""))) {
              resetMailDetail();
              showMailModal.value = false;
            }
            await loadMailboxEmails(selectedMailbox.value, false);
            if (Number(data.fail || 0) === 0) {
              message.success(`邮件删除完成：成功 ${data.ok}`);
            } else {
              const errs = Array.isArray(data.errors) ? data.errors : [];
              const detail = errs
                .slice(0, 3)
                .map((x) => `${String((x && x.id) || "-")}: ${String((x && x.error) || "未知错误")}`)
                .join("；");
              const suffix = errs.length > 3 ? "；..." : "";
              const msg = `邮件删除完成：成功 ${data.ok}，失败 ${data.fail}`
                + (detail ? `；原因：${detail}${suffix}` : "");
              message.warning(msg);
            }
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_delete = false;
          }
        }

        async function clearSelectedMailboxEmails() {
          const target = String(selectedMailbox.value || "").trim();
          if (!target) {
            message.warning("请先选择邮箱账号");
            return;
          }
          const ok = window.confirm(`将清空邮箱 ${target} 的全部邮件，确认继续？`);
          if (!ok) return;

          loading.mail_clear = true;
          try {
            const data = await apiRequest("/api/mail/emails/clear", {
              method: "POST",
              body: { mailbox: target }
            });
            await loadMailboxEmails(target, false);
            await refreshMailOverview(false);
            resetMailDetail();
            showMailModal.value = false;
            message.success(`清空完成：删除 ${Number(data.deleted || 0)} 封`);
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.mail_clear = false;
          }
        }

        async function startRun() {
          loading.start = true;
          try {
            await apiRequest("/api/start", {
              method: "POST",
              body: buildPayload()
            });
            await loadStatus();
            message.success("任务已启动");
          } catch (e) {
            message.error(String(e.message || e));
          } finally {
            loading.start = false;
          }
        }

        async function stopRun() {
          try {
            await apiRequest("/api/stop", { method: "POST" });
            await loadStatus();
            message.info("已发出停止指令");
          } catch (e) {
            message.error(String(e.message || e));
          }
        }

        async function initialLoad() {
          await loadConfig();
          await Promise.all([
            refreshAccounts(false),
            loadRemoteCache(),
            loadMailProviders(),
            loadMailDomainStats(),
            refreshSmsOverview(false, true),
            refreshSmsCountryOptions(false, true),
            refreshAboutInfo(false),
            loadStatus(),
            pullLogs()
          ]);
        }

        async function poll() {
          try {
            await loadStatus();
            await pullLogs();
            pollTick += 1;
            if (status.running && pollTick % 4 === 0) {
              await refreshAccounts(false);
            }
            if (
              activeTab.value === "accounts" &&
              (
                status.remote_busy ||
                loading.remote ||
                status.remote_test_busy ||
                loading.remote_test ||
                loading.remote_refresh ||
                pollTick % 6 === 0
              )
            ) {
              await loadRemoteCache();
            }
            if (
              activeTab.value === "mail"
              && ["mailfree", "cloudflare_temp_email", "cloudmail"].includes(normalizeMailProvider(mailProviderTab.value))
              && pollTick % 6 === 0
            ) {
              await loadMailDomainStats();
            }
            if (activeTab.value === "sms" && pollTick % 6 === 0) {
              await refreshSmsOverview(false, true);
            }
            if (activeTab.value === "sms" && pollTick % 20 === 0) {
              await refreshSmsCountryOptions(false, true);
            }
          } catch (_e) {
            // 轮询容错，下一轮重试。
          }
        }

        Vue.onMounted(async () => {
          try {
            await initialLoad();
            ensureLogContainerScrollable();
          } catch (e) {
            message.error(String(e.message || e));
          }
          pollTimer = window.setInterval(poll, 1500);
        });

        Vue.watch(activeTab, async (tab) => {
          if (tab === "logs") {
            logUserHoldUntil = 0;
            ensureLogContainerScrollable();
            await pullLogs();
            await scrollLogsToBottom(true);
            return;
          }
          if (tab === "proxy") return;
          if (tab === "sms") {
            await Promise.all([
              refreshSmsOverview(false, true),
              refreshSmsCountryOptions(false, true)
            ]);
            return;
          }
          if (tab === "accounts") {
            await Promise.all([
              refreshAccounts(false),
              loadRemoteCache()
            ]);
            return;
          }
          if (tab === "about") {
            await refreshAboutInfo(false);
            return;
          }
          if (tab === "mail") {
            if (
              normalizeMailProvider(mailProviderTab.value) === "graph"
              && normalizeGraphAccountsMode(settingsForm.graph_accounts_mode) === "file"
            ) {
              await refreshGraphAccountFiles(false);
            }
            await loadMailDomainStats();
            if (
              normalizeMailProvider(mailProviderTab.value) === "mailfree"
              && String(mailfreePanelTab.value || "basic") === "domain"
            ) {
              await refreshMailfreeCfZones(false);
              if (cfZoneId.value) {
                await refreshMailfreeCfDnsRecords(false);
              }
            }
            if (mailState.loaded) return;
            try {
              await refreshMailOverview(false);
            } catch (_e) {
              // 保持静默，用户可手动刷新。
            }
          }
        });

        Vue.watch(
          () => normalizeGraphAccountsMode(settingsForm.graph_accounts_mode || "file"),
          async (mode, oldMode) => {
            if (mode === oldMode) return;
            if (mode === "api") {
              settingsForm.graph_fetch_mode = "graph_api";
              settingsForm.graph_pre_refresh_before_run = false;
              graphAccountFileOptions.value = [];
              return;
            }
            if (mailProviderTab.value === "graph") {
              await refreshGraphAccountFiles(false);
            }
          }
        );

        Vue.watch(
          () => String(settingsForm.hero_sms_service || "").trim(),
          async (_val, _oldVal) => {
            if (activeTab.value !== "sms") return;
            try {
              await refreshSmsCountryOptions(false, true);
            } catch (_e) {
              // 忽略即时刷新失败。
            }
          }
        );

        Vue.watch(
          () => `${normalizeMailProvider(mailProviderTab.value)}:${String(mailfreePanelTab.value || "basic")}`,
          async (sig) => {
            if (activeTab.value !== "mail") return;
            if (!String(sig || "").startsWith("mailfree:domain")) return;
            try {
              await refreshMailfreeCfZones(false);
              if (cfZoneId.value) {
                await refreshMailfreeCfDnsRecords(false);
              }
            } catch (_e) {
              // 忽略自动刷新失败，允许用户手动重试。
            }
          }
        );

        Vue.watch(
          () => String(cfZoneId.value || ""),
          async (val, oldVal) => {
            if (val === oldVal) return;
            if (activeTab.value !== "mail") return;
            if (normalizeMailProvider(mailProviderTab.value) !== "mailfree") return;
            if (String(mailfreePanelTab.value || "basic") !== "domain") return;
            if (!String(val || "").trim()) {
              cfDnsRows.value = [];
              cfDnsSelection.value = [];
              return;
            }
            await refreshMailfreeCfDnsRecords(false);
          }
        );

        Vue.onBeforeUnmount(() => {
          if (pollTimer) {
            window.clearInterval(pollTimer);
            pollTimer = null;
          }
        });

        return {
          darkTheme,
          themeOverrides,
          activeTab,
          menuOptions,
          status,
          progressPercent,
          totalPlanCount,
          statusTagType,
          runSuccessRateText,
          runRetryReasonText,
          runSmsStatsText,
          dashForm,
          settingsForm,
          loading,
          jsonRows,
          jsonSelection,
          jsonInfo,
          accountRows,
          accountSelection,
          accountSearch,
          accountFilteredRows,
          accountPickCount,
          accountInfo,
          accountManageTab,
          showSub2ApiExportModal,
          sub2apiExportForm,
          aboutInfo,
          updateInfo,
          remoteRows,
          remoteSelection,
          remoteSearch,
          showRemoteDeleteModal,
          remoteDeleteAlsoLocal,
          remoteDeletePreview,
          showRemoteGroupModal,
          remoteGroupOptions,
          remoteGroupSelection,
          remoteMeta,
          remoteInfoText,
          mailProviders,
          mailProviderTab,
          mailfreePanelTab,
          graphAccountFileOptions,
          mailDomains,
          mailboxRows,
          mailboxSelection,
          mailboxSearch,
          selectedMailbox,
          filteredMailboxRows,
          mailRows,
          mailSelection,
          selectedMailId,
          selectedMailLabel,
          mailDetail,
          mailState,
          mailDomainErrors,
          mailDomainRegistered,
          cfZoneOptions,
          cfZoneId,
          cfTargetDomain,
          cfDnsRows,
          cfDnsSelection,
          cfDnsInfoText,
          showCfDnsAddModal,
          showCfDnsEditModal,
          cfDnsAddForm,
          cfDnsEditForm,
          showMailModal,
          graphFileInputRef,
          mailInfoText,
          mailboxPatternPreviewText,
          gmailAliasPreviewText,
          gmailAliasMasterWarningText,
          mailDetailText,
          logText,
          logScrollContainerRef,
          smsState,
          smsCountryOptions,
          smsOverviewText,
          flclashProbeForm,
          flclashProbeRows,
          flclashProbeSummary,
          flclashPolicyOptions,
          graphFetchModeOptions,
          graphAccountSourceOptions,
          remoteAccountProviderOptions,
          flclashProbeColumns,
          jsonColumns,
          accountColumns,
          remoteTableColumns,
          mailboxColumns,
          mailColumns,
          cfDnsColumns,
          rowKeyPath,
          rowKeyAccount,
          rowKeyRemote,
          rowKeyMailbox,
          rowKeyMail,
          rowKeyCfDns,
          jsonRowClassName,
          accountRowClassName,
          isDomainSelected,
          toggleDomain,
          domainErrorCount,
          domainRegisteredCount,
          mailboxRowProps,
          mailRowProps,
          remoteRowClassName,
          saveConfig,
          refreshJson,
          refreshAccounts,
          fetchRemoteAll,
          remoteSelectAll,
          remoteSelectNone,
          remoteSelectFailed,
          remoteSelectDuplicate,
          openRemoteGroupModal,
          confirmRemoteGroupBulkUpdate,
          testSelectedRemoteAccounts,
          refreshSelectedRemoteAccounts,
          reviveSelectedRemoteAccounts,
          deleteSelectedRemoteAccounts,
          confirmRemoteDeleteAccounts,
          jsonSelectAll,
          jsonSelectNone,
          deleteSelectedJson,
          acctSelectAll,
          acctSelectNone,
          acctSelectByCount,
          deleteSelectedLocalAccounts,
          syncSelectedAccounts,
          openSub2ApiExportModal,
          confirmExportSub2Api,
          exportSelectedCodeX,
          refreshMailOverview,
          refreshGraphAccountFiles,
          refreshMailfreeCfZones,
          refreshMailfreeCfDnsRecords,
          openCfDnsAddModal,
          confirmCfDnsBatchCreate,
          openCfDnsEditModal,
          confirmCfDnsUpdate,
          deleteSelectedCfDnsRecords,
          setCfWorkerMailDomain,
          syncSelectedCfDnsToMailfree,
          pickGraphAccountFile,
          onGraphAccountFilePicked,
          deleteSelectedGraphAccountFile,
          updateMailProviderByTab,
          updateRemoteAccountProvider,
          loadMailDomainStats,
          generateMailbox,
          mailboxSelectAll,
          mailboxSelectNone,
          deleteSelectedMailboxes,
          refreshSelectedMailboxEmails,
          deleteSelectedEmails,
          clearSelectedMailboxEmails,
          refreshSmsOverview,
          refreshSmsCountryOptions,
          runFlclashProbe,
          clearFlclashProbeRows,
          startRun,
          stopRun,
          clearLogs,
          clearRunStats,
          refreshAboutInfo,
          checkAppUpdate,
          onLogUserWheel,
          onLogUserScroll,
          manualPoll
        };

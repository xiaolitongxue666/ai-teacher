# ai-teacher 参考手册

[SKILL.md](SKILL.md) 的展开部分：字段字典、状态语义、完整踩坑清单。

## 一、`data/resources.json` 结构

顶层：

```json
{
  "schema_version": 1,
  "checked_at": "2026-11-09T13:21:31+08:00",
  "status_values": [...],
  "websites": [], "repos": [], "mcp_tools": [], "dify": [], "collections": []
}
```

当前条目数：websites 70 / repos 22 / mcp_tools 12 / dify 11 / collections 11。

### websites

| 字段 | 说明 |
| --- | --- |
| `id` | 小写短标识，文档锚点会用到 |
| `name` / `category` / `age` / `lang` | 展示与分龄检索 |
| `url` | 官方地址 |
| `verified` | 见下文六种取值 |
| `checked_at` | 最后一次探测时间，脚本写 |
| `note` | 人工描述，脚本不改 |
| `final_url` / `redirected_to` | 发生过跳转时由脚本记录 |

### repos

`id` / `name` / `stars` / `url` / `desc` / `subject` / `verified` / `checked_at`。

`stars` 是**快照**，不是实时值。用 `gh api repos/<slug> --jq .stargazers_count` 复核后再改，改完同步 `docs/07` 的表格数字。

### mcp_tools

`id` / `name` / `registry`（npm / PyPI / GitHub）/ `pkg` / `version` / `latest_version_checked` / `verified` / `checked_at`。

版本核对接口：

- npm：`registry.npmjs.org/<pkg>` 的 `dist-tags.latest`
- PyPI：`pypi.org/pypi/<pkg>/json` 的 `info.version`

### collections

| 字段 | 来源 | 说明 |
| --- | --- | --- |
| `id` / `name` / `subject` / `grade` / `media` | 人工 | 展示用 |
| `claimed` | 人工 | 原始文案的原话，用来对照实测 |
| `url_official` | 人工 | 官方分享页，正文只登这个 |
| `url_alias` | 人工 | 第三方中转，同时记进 `collections/网盘分享链接.md` |
| `entry_type` | 人工 | 「官方直链」或「第三方中转页 + 跳转方式」 |
| `password` | 人工 | 提取码，没有就不写 |
| `verified` | 脚本 | 入口可达性 |
| `actual` / `grade_actual` | 人工 | 实测结论，脚本不覆盖 |
| `needs_passcode` | 脚本 | 用**空码**单独试一次判定 |
| `share_total_files` | 脚本 | 截断时为下限 |
| `share_total_size_bytes` | 脚本 | 文件字节总和 |
| `share_suffix_counts` | 脚本 | 按扩展名分布 |
| `share_tree_truncated` | 脚本 | 请求预算用尽 |
| `share_tree_failed_pages` | 脚本 | 重试 3 次仍失败的页数 |
| `share_tree_incomplete` | 脚本 | 上面任一为真 |
| `share_tree_requests` | 脚本 | 实际请求次数 |
| `share_request_budget` | 人工 | 单条覆盖默认预算 |
| `tree_checked_at` | 脚本 | 本次统计时间 |

## 二、`verified` 六种取值

| 值 | 含义 | 使用者该怎么做 |
| --- | --- | --- |
| `ok` | HTTP 2xx | 直接用 |
| `blocked` | 403 / 429，反爬 | 浏览器打开通常正常 |
| `dead` | 域名不存在或站点关停 | 找替代入口 |
| `unreachable` | DNS 正常但本机连不上 | 需要代理或换网络 |
| `mismatch` | 可达但内容与描述不符 | **人工结论，脚本不覆盖** |
| `pending` | 未探测 | 跑脚本 |

## 三、已知的坑

### 环境类

1. **Windows 控制台默认 GBK**。跑带中文输出的脚本前设 `PYTHONIOENCODING=utf-8`；仓库脚本内部已 `reconfigure`，但外部调用仍需设。
2. **MSYS 的 `/tmp` 与 Windows Python 的 `/tmp` 不是同一路径**。前者在 MSYS 根，后者解析到 `C:\tmp`。跨 bash 与 python 传文件用项目内相对路径，用完即删。
3. **MSYS 的 `timeout` 会丢弃环境变量**。实测 `timeout 60 python -c "print(os.environ.get('LOCALAPPDATA'))"` 输出 `None`。依赖 `LOCALAPPDATA` / `USERPROFILE` 的脚本别套 `timeout`。
4. **`cmd //c` 在 MSYS 里报 command not found**。项目盘符写 `/e/...`。
5. **本仓 `core.autocrlf=true`**。手写记忆草稿等需要 `--validate` 的文件，写完先转 LF。

### 探针类

6. **请求超时 ≠ 目录到底**。早期 `quark_share_page` 异常返回空列表，上层当成「没有更多页」，导致同一分享两次统计差 40 个文件。现在失败重试 3 次（`QUARK_PAGE_RETRIES`），仍失败记 `share_tree_failed_pages`。
7. **`write_results_back` 的字段推断**。`field = row.get("field") or ("url" if section == websites else "url_official")`，多分区混跑时写错字段会回写 0 条且不报错。
8. **夸克单页硬限 100 条**。`_size=1000` 也只返回 100，必须翻页。大分享（`quark_misc` 21943 文件 / 1534 请求 / 约 11 分钟）需要把预算从默认 2000 往上调，或在数据里给单条设 `share_request_budget`。
9. **`nslookup` 返回 `Address: 223.5.5.5` 不代表域名可达**。那是 DNS 服务器地址。判断域名存在用 `socket.getaddrinfo` 或 DoH 的 `Status`（0 = 存在，3 = NXDOMAIN）。
10. **`ERRNO 2 No such file or directory` 在 Windows 上可能是 DNS 失败**。`URLError` 会把 `EAI_NONAME` 包成 `OSError(2)`。
11. **本地 DNS 与 DoH 结果可能不同**。VOA 本机解析 `174.36.196.242`，DoH 返回 Akamai `23.55.143.x`。记录两种结果，不要任选其一。

### 网盘类

12. **Chrome Cookie 在外部工具里读不到**。Chrome 运行时会独占锁 Cookie 库；即便用 VSS 卷影复制绕过文件锁，Chrome 127+ 的 Cookie 全部是 v20（App-Bound），密钥链需要 SYSTEM 层 DPAPI，用户态无解。`scripts/check_chrome_cookies.py` 可自检三层。
13. **`--cookies-from-browser chrome` 因此不可用**。要用登录态就导出 `cookies.txt`（用完即删），或改用 Firefox。
14. **`yt-dlp` 不支持任何国内网盘**。实测 1755 个提取器里夸克/百度/阿里/115/迅雷/天翼/彩云命中 0。
15. **`@ptbsare/netdisk-mcp-server` 的 `view` 只回 100 条**。它内部 `_size=1000` 但服务端硬限 100 且不翻页，`Total` 是单页条数不是总数。`list` / `transfer` 无 Cookie 直接 401。
16. **`wpss.best` 之类的聚合页是 Nuxt SPA**。SSR 载荷里没有真实分享链接，抓不到 share id。

### 工程类

17. **`data/resources.json` 改动密集，rebase 必冲突**。远端先行提交导致 push 被拒时：`git fetch` 比对范围 → 必要时 `reset --hard origin/main` → 重放改动。不要硬 rebase。
18. **星数会漂移**。一次比对 22 个项目有 14 个已偏。发布前用 API 复核，同步 `data` 与 `docs/07` 两处。
19. **两份工作副本会导致工作区分叉**。只保留 `E:\Code\my_code\Agents\ai-teacher`。

## 四、常用命令

```bash
# 链接核验
python scripts/check_links.py
python scripts/check_links.py --only websites,repos
python scripts/check_links.py --only quark_tree --write

# 视频
python scripts/download_video.py --check
python scripts/download_video.py "https://www.bilibili.com/video/BVxxxx" --audio-only

# Cookie 可读性
python scripts/check_chrome_cookies.py

# 中转页解析真实地址
python -c "import urllib.request;print(urllib.request.urlopen(urllib.request.Request('https://pan.quarkn.xyz/s/<id>',headers={'User-Agent':'Mozilla/5.0'})).geturl())"

# 星数复核
gh api repos/<owner>/<repo> --jq .stargazers_count

# 提交
git-smart-commit --yes
```

## 五、文档与数据的一致性

- 五列表：`| 名称 | 年龄 | \`status\` | 说明 | 链接 |`
- 四列表：首列链接、末列状态
- 计数类（70 / 22 / 12 / 11 / 11）散落在 `README.md`、`docs/00`、`docs/03`，改数据后必须逐处核对。

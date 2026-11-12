# ai-teacher 参考手册

[SKILL.md](SKILL.md) 的展开部分：字段字典、状态语义、完整踩坑清单。

## 一、`data/resources.json` 结构

顶层：

```json
{
  "schema_version": 1,
  "checked_at": "2026-11-09T13:21:31+08:00",
  "status_values": [...],
  "websites": [], "tutoring": [], "repos": [], "videos": [], "mcp_tools": [], "dify": [], "collections": []
}
```

当前条目数：websites 74 / tutoring 15 / repos 22 / videos 61 / mcp_tools 12 / dify 11 / collections 59。

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

### tutoring

| 字段 | 来源 | 说明 |
| --- | --- | --- |
| `id` / `name` / `url` | 人工 | 展示用 |
| `operator` | 人工 | 服务条款或联系页写明的主体；中文站不等于主体所在地 |
| `operator_evidence_url` | 人工 | 支撑主体判断的官方页面 |
| `teacher_origin` | 人工 | 师资国籍构成，写清是否含菲律宾 |
| `fixed_teacher` | 人工 | `支持` / `可预约` / `待确认`；`可预约` 指每次自己抢时段，无自动固定排课 |
| `fixed_teacher_note` | 人工 | 固定机制的具体限制（有效期、改期时限、每日上限） |
| `alipay` | 人工 | `official` 官网结账原生 / `official_manual` 官方渠道收款 / `none` 官方列全且不含 / `unverified` 只有间接证据 |
| `alipay_note` | 人工 | 结论与边界，写明「为什么不算」 |
| `alipay_evidence_url` | 人工 | 支撑支付结论的官方页面 |
| `verified` / `checked_at` / `redirected_to` | 脚本 | 只表示入口可达，与支付无关 |

**`alipay` 与 `fixed_teacher` 是人工结论，探针不覆盖。** 官网支付说明页返回 200 不等于支持支付宝；App 里打包支付宝 SDK 也不等于网页结账能选支付宝。拿脚本结果改写这两列，等于用「页面能打开」冒充「支持支付宝」。

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

#### 浅层口径（`share_probe_depth: "shallow"`）

教辅类成套资料（小学预习复习包、初中全科套件）结构是「1 个总目录 → 几十个教辅目录 → 再按年级/版本分册」。
全量遍历一条要几分钟，44 条要好几小时，实际也不需要——使用者关心「这一包收了哪些教辅」，不是总字节数。
这类条目加 `share_probe_depth: "shallow"`，走 `--only quark_shallow`：

| 字段 | 来源 | 说明 |
| --- | --- | --- |
| `share_probe_depth` | 人工 | 写 `"shallow"` 即走浅层分区，同时被全量 `quark_tree` 跳过 |
| `share_top_name` | 脚本 | 顶层目录名，用于核对分享标题与实际内容是否一致 |
| `share_l2_entries` | 脚本 | 第 2 层总项数 |
| `share_l2_dir_count` / `share_l2_file_count` | 脚本 | 第 2 层里目录与文件各多少 |
| `share_l2_dirs` | 脚本 | 第 2 层目录名（上限 80 个） |
| `share_l3_dir_names` | 脚本 | 第 3 层抽样，只用于说明「内容还在更下面」 |
| `share_probe_truncated` | 脚本 | 请求预算用尽 |
| `share_probe_requests` | 脚本 | 实际请求次数 |
| `share_probe_error` | 脚本 | 失败原因（如 `code 41010 文件涉及违规内容`） |
| `share_probe_checked_at` | 脚本 | 本次探测时间 |

**浅层条目绝不写 `share_total_files`。** 第 2 层的文件数是按层计的，不是资料规模。
反例实测：「初中电子课本」第 2 层只有 36 个文件，第 3 层却有 164 个目录，PDF 全在下面。

第 3 层是抽样（取前 8 个目录各翻 1 页），**抽样不置 `truncated`**——截断标记只表示第 2 层本身没读全。

#### 人工结论豁免：`status_manual`

| 字段 | 来源 | 说明 |
| --- | --- | --- |
| `status_manual` | 人工 | 置 `true` 后所有探测分区都跳过该条，不回写 `verified` |
| `replacement_id` | 人工 | 本条不可用时的替代条目 id，正文里链接过去 |

夸克分享被平台按违规下架时，**分享页仍返回 HTTP 200**（前端兜底页），只有接口业务码 `41010` 能看出来。
这种情况若让脚本重探，会把人工判定的 `dead` 冲成 `ok`。实测样本：`j_53_zhongkao`。

#### 腾讯文档索引：`sheet_embedded_quark_links`

走 `--only sheet_index`。表格数据在 percent-encoded 的 `flyweight.texts` 里，整体 unquote 后数 `pan.quark.cn/s/<id>`。
标题不在明文（明文的 `<title>` 是通用的「腾讯文档」），从 base64 的 `basicClientVars` 解 `padInfo.padTitle`，解不出留空不猜。

| 字段 | 说明 |
| --- | --- |
| `sheet_title` | 表格真实标题 |
| `sheet_embedded_quark_links` | 内嵌夸克链接条数 |
| `sheet_embedded_quark_links_unique` | 去重后条数 |

### videos

按国家审定教材矩阵登记的在线视频课程。

| 字段 | 来源 | 说明 |
| --- | --- | --- |
| `id` | 脚本 | `{出版社}_{学科}_g{年级}_{册别}`，如 `beishida_math_g2_up` |
| `platform` | 脚本 | 目前只有 `bilibili` |
| `bvid` | 脚本 | B站 视频号 |
| `publisher` / `subject` / `grade` / `volume` | 脚本 | 匹配键，与 `docs/11` 的矩阵一一对应 |
| `editor` | 脚本 | 平台登记的主编。英语按主编分版本，是区分键 |
| `pages` | 脚本 | **`view` 接口返回的真实分P数**，不是标题声称的集数 |
| `duration_seconds` / `play` / `publish` | 脚本 | `view` 接口实测值 |
| `uploader` / `uploader_mid` | 脚本 | UP 主名与 mid |
| `url` | 脚本 | 播放页 |
| `verified` | 探针 | 只表示播放页 HTTP 可达 |
| `checked_at` | 探针 | 最近一次可达性探测时间 |
| `note` | 脚本 | 标题集数与实际分P不符、上下册合并、分P过少、地方教材等需披露项 |

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

### 浅层与索引类

28. **教辅包不要跑全量**。44 条按 `quark_misc` 的量级（1534 请求 / 11 分钟）要好几小时。标 `share_probe_depth: "shallow"` 走 `--only quark_shallow`，实测 44 条 110 秒跑完。
29. **第 2 层文件数 ≠ 资料规模**。「初中电子课本」第 2 层 36 文件 / 164 目录，PDF 全在第 3 层。把这个数字写进 `share_total_files` 会让人误以为是全量。
30. **第 2 层的截断必须区分于第 3 层抽样**。第 3 层只取前 8 个目录各翻 1 页（`QUARK_SHALLOW_L3_SAMPLE_DIRS`），抽样不是遍历，不置 `truncated`。早期版本把第 3 层扫完，导致 `p_math`（8 项）都被标成「已截断」。
31. **分享页 200 掩盖平台下架**。违规内容时公开接口返回 HTTP 404 + `code 41010`，但 `pan.quark.cn/s/<id>` 前端兜底页仍是 200。只跑 `--only collections` 会把它标成 `ok`，必须靠 `quark_shallow` 的业务码。
32. **`mismatch` 之外还需要 `status_manual`**。空壳分享（如 53 知识清单）入口可达、内容为空，`verified` 会判 `ok`，需要人工置 `status_manual: true` 让它跳过回写。
33. **腾讯文档标题要从 base64 解**。明文 `<title>` 是通用的「腾讯文档」，真实标题在 `basicClientVars=JSON.parse(decodeURIComponent(escape(atob('...'))))` 的 `docInfo.padInfo.padTitle`。
34. **腾讯文档的表格数据在 percent-encoded 的 `flyweight.texts` 里**。不 unquote 直接搜 `pan.quark.cn` 会命中 0 次（页面上看似有 74 条）。
35. **`docs.qq.com/dop-api/get/sheet` 需要权限票**。无登录态返回 `retcode: 56030 ticket mismatch`，只能解析 HTML 里的 flyweight，别指望走 API。
36. **同一份资料可能在多个分享里重复**。逐文件比对文件名交集才能确认：大礼包的《课堂作业》44 文件与独立分享 44/44 完全相同，但《七彩课堂》大礼包 20 文件只与独立分享 284 文件交集 3——同名不同内容，不是重复。


### 工程类

17. **`data/resources.json` 改动密集，rebase 必冲突**。远端先行提交导致 push 被拒时：`git fetch` 比对范围 → 必要时 `reset --hard origin/main` → 重放改动。不要硬 rebase。
18. **星数会漂移**。一次比对 22 个项目有 14 个已偏。发布前用 API 复核，同步 `data` 与 `docs/07` 两处。
19. **两份工作副本会导致工作区分叉**。只保留 `E:\Code\my_code\Agents\study-map`。

### B站检索类

20. **wbi 搜索接口 5/8 不稳定，不可依赖**。失败时 `data` 里只有 `v_voucher`，没有 `result`。必须做「有 result 就用，空就回退 SSR」。
21. **SSR 才是可靠召回**（8/8），但只给 bvid + 标题，元数据必须再调 `view`。
22. **`view` 几乎必成**（31/32）。失败的那条是从 HTML 正则里误抓的无效串，返回 `-400`，不是限流。
23. **wbi 的 `title` 带 `<em class="keyword">` 高亮标签**，SSR 的 `title="..."` 是纯文本。两条通道都要先剥标签再打分，否则关键词匹配失效。
24. **标题匹配必须有三道硬门槛**：出版社必须出现、册别必须对、其它学科名不能出现。只靠扣分压不住，实测三条都出现过误命中。
25. **标题集数普遍虚标**。30 条带集数的标题只有 3 条对得上（`BV1NMaP6KEcQ` 称 152 实际 100、`BV1VoXEBrEYb` 称 180 实际 54）。
26. **`space/wbi/arc/search` 与 `yt-dlp bilisearch` 都是 412**，UP 主投稿列表枚举不了，别浪费时间。
27. **`data/resources.json` 可能被并行会话覆盖**。写入前重新读盘；用 `--json-out` 留备份，冲突时 `--from-json` 恢复，不必重新检索。

### 教材目录类

28. **小学语文只有统编版**。「人教版语文」「部编版语文」指的是同一套，2017 年起全国统一。
29. **小学英语从三年级起**，23 个国家审定版本没有任何一个覆盖二年级。二年级英语教材都是地方/校本教材。
30. **外研社版按主编分三个**（孙有中 / 刘兆义 / 张祖春），覆盖年级不同；刘兆义版缺四年级上册。B站标题一律不写主编，所以 `videos` 段按「外研三起点」统一登记 8 格、`editor` 留空，不要凭标题给视频安主编。

## 四、常用命令

```bash
# 链接核验
python scripts/check_links.py
python scripts/check_links.py --only websites,repos
python scripts/check_links.py --only quark_tree --write

# 教辅包浅层（只翻 2 层，44 条约 110 秒）
python scripts/check_links.py --only quark_shallow --write
# 腾讯文档索引内嵌的夸克链接计数
python scripts/check_links.py --only sheet_index --write

# 视频
python scripts/download_video.py --check
python scripts/download_video.py "https://www.bilibili.com/video/BVxxxx" --audio-only

# 按教材版本检索课程
python scripts/search_bilibili_courses.py --grid
python scripts/search_bilibili_courses.py --only 数学
python scripts/search_bilibili_courses.py --write --json-out data/videos_bilibili.json
python scripts/search_bilibili_courses.py --from-json data/videos_bilibili.json

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
- 计数类（74 / 15 / 22 / 60 / 12 / 11 / 59）散落在 `README.md`、`docs/00`、`docs/03`，改数据后必须逐处核对。
- `collections` 的 59 条分两张清单：11 条全量口径在 `docs/03b`，48 条浅层口径在 `docs/03c`。条数变了要同时改 `README.md` 索引四那张两行表、`docs/00` 的分区表、本文件第 18 行。
- 浅层条目的 `share_l2_entries` 与 note 里写的「第 2 层 N 个」必须一致。改 note 前用脚本核一遍：读 `share_l2_entries` 比对正文字面数字。

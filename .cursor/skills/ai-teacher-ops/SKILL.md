---
name: ai-teacher-ops
description: Maintain the ai-teacher learning-resource index repo — add or verify links, register a Quark share collection with measured file counts, run the link/Quark probes, and commit. Use when adding a resource to data/resources.json, editing docs/02 03 03b 07, running scripts/check_links.py or scripts/download_video.py, or when a link needs re-verification.
disable-model-invocation: true
---

# ai-teacher 运营流程

本仓是**链接索引**，不是课程、不托管文件。所有改动都要落到两条硬约束上：

1. `data/resources.json` 是唯一数据源，文档里的数字必须能从它推出来；
2. 每条链接同时有 `verified` 与 `checked_at`，二者都不能手填。

## 快速开始

```bash
python scripts/check_links.py                    # 全量报告，不改文件
python scripts/check_links.py --only websites    # 只看网站
python scripts/check_links.py --only quark_tree  # 全量翻完夸克分享目录，拿真实文件数
python scripts/check_links.py --only quark_shallow  # 只翻 2 层，大批量教辅包用这个
python scripts/check_links.py --only sheet_index    # 腾讯文档索引里内嵌的夸克链接计数
python scripts/check_links.py --write            # 回写 verified / checked_at / final_url
```

执行前先设 `PYTHONIOENCODING=utf-8`，否则中文输出在 Windows 控制台是乱码。

## 三个工作流

### 工作流 A：新增一条网站 / 仓库 / 平台链接

1. 追加到 `data/resources.json` 对应分区，`verified` 写 `pending`，`checked_at` 留空。
2. 跑 `check_links.py --only <分区> --write`，让脚本填值。
3. 把结果同步进 `docs/03-参考网站.md`（网站）、`docs/07-开源项目清单.md`（仓库）或 `docs/12-线上口语一对一.md`（平台）的表格。
4. 如果分区总数变了，同步 `docs/00-使用说明.md` 的分区计数表与 `README.md` 的索引表。

**不要**手写 `verified: ok`。仓库已有 14 条星数漂移是历史遗留，别再制造第二种漂移。

平台条目（`tutoring`）多一道工序：`alipay` / `operator` / `fixed_teacher` 三个字段脚本永远不填，必须打开官方支付说明页与条款页逐条核对，并把证据链接写进 `*_evidence_url`。**官网能打开 ≠ 支持支付宝**，别拿探针结果当支付结论。

### 工作流 B：登记一条网盘分享

先判断入口类型，再取实测数据。

```bash
# 1. 中转页解析出官方分享 id（跟 302 与 meta refresh）
python -c "import urllib.request;print(urllib.request.urlopen(urllib.request.Request('<中转链接>',headers={'User-Agent':'Mozilla/5.0'})).geturl())"

# 2. 读全目录，拿文件数、总大小、扩展名分布
python scripts/check_links.py --only quark_tree --write
```

写进 `collections` 的字段（详见 [reference.md](reference.md)）：

- `url_official` 官方直链；`url_alias` 第三方中转（正文只登官方页，别名只记在 `collections/`）
- `entry_type` 写清是「官方直链」还是「第三方中转页 + 跳转方式」
- `share_total_files` / `share_total_size_bytes` / `share_suffix_counts` 由脚本回写
- `share_tree_truncated` / `share_tree_incomplete` 为真时，`share_total_files` 是**下限**，文档必须写明「≥N」

然后改三处文档：`docs/03b-网盘资料清单.md` 加条目段落、`collections/网盘分享链接.md` 记原始链接、`docs/02-科目类别.md` 挂锚点入口。

### 工作流 B2：登记一批教辅分享（浅层口径）

教辅包结构是「1 个总目录 → 几十个教辅目录 → 再按年级/版本分册」。全量遍历一条要几分钟，几十条要好几小时，而使用者关心的是「这一包收了哪些教辅」，不是总字节数。这类条目走浅层：

1. 数据里加 `"share_probe_depth": "shallow"`。加了之后全量 `quark_tree` 会自动跳过它，两个分区互斥。
2. 跑 `python scripts/check_links.py --only quark_shallow --write`（44 条实测 110 秒）。
3. 只写 `share_l2_entries` / `share_l2_dir_count` / `share_l2_file_count` / `share_l2_dirs`，**不写 `share_total_files`**。
4. 正文进 `docs/03c-教辅成套清单.md`，不要塞进 03b——两页的统计口径不同，混在一起会被误读。

**报数规矩**：只能说「第 2 层 N 项」，不能说「共 N 个文件」。第 2 层的文件数按层计，反例实测某条第 2 层 36 文件、第 3 层 164 目录，PDF 全在下面。

### 工作流 B3：登记腾讯文档 / 公众号类索引

索引页不是资料本体，别当网盘分享登记。

- 腾讯文档：`entry_type` 写「腾讯文档总索引（页面内嵌夸克分享链接，不是资料本体）」，跑 `--only sheet_index` 拿 `sheet_embedded_quark_links`。
- 公众号文章：`entry_type` 写清「内链指向公众号历史文章，不是网盘直链」，并注明「无法用脚本核验到底层分享是否有效」。

### 工作流 B4：分享被平台下架 / 内容是空壳

两种都需要人工结论，脚本判不出来：

| 情况 | 现象 | 处理 |
| --- | --- | --- |
| 违规下架 | 接口 HTTP 404 + `code 41010`，但分享页仍 200 | `verified: "dead"` + `status_manual: true` + note 写清业务码 |
| 空壳 | 能打开，内容是「版权受限，暂不提供下载」之类 | `verified: "mismatch"`，有替代入口就写 `replacement_id` |

`status_manual: true` 会让所有探测分区跳过该条，防止脚本把 `dead` 冲成 `ok`。

### 工作流 C：视频下载

```bash
python scripts/download_video.py --check
python scripts/download_video.py <URL> [--audio-only] [--output DIR]
```

网盘分享链接会被脚本直接拒绝——`yt-dlp` 1755 个提取器里国内网盘命中 0。网盘里的 mp4 必须先用网盘客户端或 `BaiduPCS-Go` 落盘。

### 工作流 C2：三类资源批量下载（github / video / netdisk）

```bash
python scripts/fetch_resources.py plan                 # 只估算体积
python scripts/fetch_resources.py run --only github    # 浅克隆，按体积升序
python scripts/fetch_resources.py run --only video     # B站小学核心五组 2894 P
python scripts/fetch_resources.py run --only netdisk   # 夸克，需 NETDISK_QUARK_COOKIE
python scripts/fetch_resources.py status               # 合成三阶段进度
python scripts/fetch_resources.py report               # 写出 downloads/_state/REPORT.md
```

三个下载阶段均已完成（`github` 2026-11-09、`video` 11-11 08:20、`netdisk` 11-11 23:32），当前无活动下载任务。锁、进度文件、产物目录都按阶段分开，曾与 `video` 并行跑过，共用的是磁盘（底线 `MIN_FREE_BYTES` = 20 GB）。

阶段之间互不阻塞，但**同一阶段内部串行**：`netdisk` 里 9 条要一条条跑完，前一条没结束，后一条不会开始。

看进度别只信 `finished` 字段。当前代码会写 `current`；`finished: false` 配上一个已经退出的锁 pid，表示停了，不是还在跑。父进程退出后，BBDown 子进程可能还在下当前这一集，下完不会自己开下一集。重开视频前先确认没有残留的 BBDown。

| 想知道 | 看哪里 |
| --- | --- |
| 网盘在跑没跑 | `downloads/_state/RUNNING.netdisk.lock` 的 pid 是否存活，以及目标文件的 mtime 是否还在涨 |
| 网盘下到哪个文件 | `progress.netdisk.json` 的 `current` |
| 已完成多少项 | 递归计数：`find <目标目录> -type f \| wc -l`。只数顶层会少算子层，下载模式也不写 `_inventory.json` |
| 视频阶段 | `progress.video.json` 的 `current`。`per_collection` 只在 `watch_video.py` 覆盖过该文件时才有 |

`scripts/netdisk_progress.py` 需要条目目录下的 `_inventory.json`，而**下载模式不写这个文件**
（只有无登录态的清单模式才写）。在纯下载产物上它恒输出 `0 B / 0 B`，不要据它判断进度。

条目残缺时用三个补漏脚本按粒度回补（都复用 `quark.walk_share` + `download_entry`）：

```bash
python scripts/probe_remaining.py                       # 只读探测体积，不转存不占容量
python scripts/backfill_missing.py p_math --dry-run      # 先看清单
python scripts/backfill_missing.py p_math p_eng          # 批量补
python scripts/redownload_one.py p_math "子目录/a.pdf"   # 只补单个文件
```

`downloads/netdisk/_manifest.jsonl` 与 `REPORT.md` 都是**追加历史**，同一 item 会出现多行；
判读 `failed` 必须带上时间——DNS 断网那一轮的 8 条 `getaddrinfo failed` 与文件可下性无关，
重跑同一命令即可续。注意 `status: ok` 不代表完整：2026-11-11 之前的版本在 `failed > 0` 时
仍记 `ok`（`p_math` 缺 1882 个、`p_eng` 缺 615 个都因此被掩盖），现在改记 `incomplete`。

### 工作流 D：按教材版本找视频课

分类基准是**国家审定教材目录**，不是 B站 的标签。

```bash
python scripts/search_bilibili_courses.py --grid        # 看矩阵，不检索
python scripts/search_bilibili_courses.py --only 数学    # 只跑一科
python scripts/search_bilibili_courses.py --write       # 全量检索并回写 videos 分区
python scripts/search_bilibili_courses.py --write --json-out data/videos_bilibili.json  # 同时留备份
```

**三条通道的成功率决定了必须做双路**：

| 通道 | 实测成功率 | 拿到什么 |
| --- | --- | --- |
| `search.bilibili.com/all` SSR | 8/8 | bvid + 标题 |
| `x/web-interface/view?bvid=` | 31/32 | 分P数、时长、UP 主、播放量 |
| `x/web-interface/wbi/search/type` | 5/8 | 20 条完整元数据 |

`space/wbi/arc/search`（UP 主投稿列表）与 `yt-dlp bilisearch` 都是 `412`，别试。

**标题匹配必须有三道硬门槛**，缺一条就会错：

| 门槛 | 反例 |
| --- | --- |
| 出版社必须出现 | 「北师大版六年级英语」命中「湘少版六年级英语」`BV1uNgK68EBd` |
| 册别必须对 | 「四年级英语下册」命中「四年级英语上册」`BV1GmgQ6bEbz` |
| 其它学科名不能出现 | 「北师大版四年级英语下册」命中「北师大版四年级数学下册」`BV13p8S6iEx2` |

再加两条软约束：分P数 < 5 视为不是成套课程（单词朗读、单节精讲），带「单词朗读 / 课文朗读 / 听力磨耳朵」的降权。

## 不要做什么

| 禁止 | 原因 |
| --- | --- |
| 手填 `verified` / `checked_at` | 违反「先验证再呈现」。要么跑脚本，要么标 `pending` |
| 把请求超时当成「目录到底了」 | 会导致静默漏数，实测同一分享两次统计差 40 个文件 |
| 覆盖人工标记的 `mismatch` / `status_manual` | 前者是链接可达但内容不符，后者含违规下架；都是判断结论不是探测结果 |
| 在正文里写第三方中转域名 | 中转站会消失，正文只登官方分享页 |
| 给浅层条目写 `share_total_files` | 第 2 层文件数不是资料规模，实测某条 36 文件 / 164 目录，PDF 全在第 3 层 |
| 把第 3 层抽样算成「已截断」 | 截断标记只表示第 2 层没读全，抽样不是遍历 |
| 把教辅包塞进 `docs/03b` | 03b 是全量口径，03c 是浅层口径，混在一起会被误读成「这份才这么点文件」 |
| 转述原始文案里的数量（「900 节」「57 种工具」） | 要么实测过，要么在 `note` 里写明「原文案，未核对」 |
| 提交 Cookie / token / 可执行文件 | 凭据进 `.credentials/`（已忽略），二进制进 `.tools/`（已忽略） |
| 把 5 分钟没跑完的遍历结果当完整值 | 置 `share_tree_truncated`，文档写「≥N」 |
| 相信视频标题里的集数 | 实测 30 条带集数的标题只有 3 条对得上；判断覆盖度看 `view` 返回的分P数 |
| 假设语文有多个版本 | 小学语文在国家审定目录里只有统编版，「人教版语文」= 「部编版」= 统编版 |
| 假设小学英语有一二年级 | 国家审定的小学英语从三年级起，一二年级的英语教材都是地方/校本教材 |
| 用 `netdisk_progress.py` 判断下载进度 | 下载模式不写 `_inventory.json`，它恒输出 `0 B / 0 B`；改看目录计数与 `current` |
| 在当前管道还在写进度时再开 `watch_video.py` | 它按磁盘计数整文件覆盖 `progress.video.json`，把下载进程写下的 `current` 冲掉 |
| 拿 `_manifest.jsonl` 的 `failed` 当当前故障 | 那是追加历史，同一条会多行；`failed` 要连时间一起看（DNS 断网那轮是 `getaddrinfo failed`） |
| 用 `REPORT.md` 的条目数判断阶段完成 | 同样是历史累积，同一 item 重复出现；以 `progress.<stage>.json` 为准 |

## 环境约定

- 工作副本只有 `E:\Code\my_code\Agents\ai-teacher` 一份，别再开第二份。
- bash 里盘符写 `/e/...`，不要用 `cmd //c`。
- Python 输出中文一律 `PYTHONIOENCODING=utf-8`。
- 跨 bash 与 python 传文件用项目内相对路径，用完即删；`/tmp` 两边解析到不同位置。
- 提交前跑 `git-smart-commit --yes`，它会拦 `logs/`、`__pycache__/`、`.credentials/`、`.tools/` 等。
- 推送被拒时不要直接 rebase：`data/resources.json` 改动密集，必然冲突。先 `git fetch` 看范围，必要时 `reset --hard origin/main` 后重放。

## 更多

字段字典、`verified` 六种取值、完整踩坑清单见 [reference.md](reference.md)。

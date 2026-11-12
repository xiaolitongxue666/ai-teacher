# Project Memory (Compact)

1) 仓库唯一工作副本为 `E:\Code\my_code\Agents\study-map`，远端 `github.com/xiaolitongxue666/study-map`（PUBLIC）。原路径 `C:\Users\Administrator\Projects\ai-teacher` 已删除：双副本 HEAD 相同但工作区会分叉。GitHub 仓库曾用名 `ai-teacher`，现名 `study-map`。记忆 SSOT 是根目录 `PROJECT_MEMORY.md`，备份落 `.project-memory-backups/`（保留最近 2 份）。

2) `data/resources.json` 是链接索引，不是文件清单。2026-11-10 实测分区：websites 74 / tutoring 15 / repos 22 / videos 61 / mcp_tools 12 / dify 11 / collections 59。每条记录必须同时有 `verified` 与 `checked_at`。目录里的文件数只从磁盘扫描来。

3) `scripts/check_links.py` 分区：`websites` `tutoring` `repos` `videos` `collections` `markdown` `quark_tree`（全量翻目录）`quark_shallow`（只翻 2 层）`sheet_index`。默认不含后两个。`write_results_back` 按 section 推断字段：collections 用 `url_official`，其余用 `url`，写反会回写 0 条且不报错。

4) MSYS bash 的 `/tmp` 与 Windows Python 的 `/tmp`（解析为 `C:\tmp`）不是同一路径；跨 bash/python 传文件用项目内相对路径。Python 默认 stdout 为 GBK，中文输出必须 `PYTHONIOENCODING=utf-8`。MSYS 的 `timeout` 会丢弃 `LOCALAPPDATA`。项目盘符写 `/e/...`，不要用 `cmd //c`。MSYS 的 `find` 参数顺序严格：`-not -path` 必须写在 `-name` 之后，否则报 `paths must precede expression`。bash 里 `python -c` 不要写反斜杠转义，用 pathlib。

5) websites 分布 ok 61 / blocked 6 / dead 4 / unreachable 3（74 条）。NRICH 连续 3 次 403 判 `blocked`。本地 DNS 与 DoH 结果可能不同（VOA 本机 174.36.196.242，DoH 返回 Akamai 23.55.143.x），文档要注明差异。README 计数表必须与实测同步。

6) Dify 官方 `datasources` 共 17 项，无 webdav 条目；知识库接 WebDAV 只能用社区插件 `shaba/dify-datasource-webdav`。官方 `tools/nextcloud` 是 tool 插件不是 datasource。GitHub 星数持续漂移，发布前用 `gh api repos/<slug> --jq .stargazers_count` 复核；MCP 包版本查 npm `dist-tags.latest` / PyPI `info.version`。

7) 远端先行提交会使 push 被拒；`data/resources.json` 改动密集，rebase 必在它上面冲突。推送被拒时先 `git fetch` 看范围，必要时 `reset --hard origin/main` 后重放。

8) 范老师几何课实测 910 项（909 mp4 + 1 zip），678 个无年级标记，仅标 L6 的 111 条。内容是奥数专题，落在 `小学/数学/通用/思维专题/`。文件名里的 L 年级不是册次，不能当同步课。

9) 剑桥 A2 Key（KET）标准版纸笔最后一次场次 2026-12-03，之后仅机考；`A2 Key for Schools` 是另一条线。线上口语一对一平台条款差异大，`docs/12` 只收有官方页面佐证的条目。

10) 教辅类资料走浅层口径（`share_probe_depth: "shallow"`），只翻到第 2 层，只报 `share_l2_*`。`docs/03b` 是全量口径，`docs/03c` 是浅层口径，两者不可混写。夸克分享被违规下架时接口返回 HTTP 404 + `code 41010`，但分享页仍返回 200，只跑 `check_links` 看不出失效。腾讯文档总索引的表格数据在 percent-encoded 的 `flyweight.texts` 里，不 unquote 搜 `pan.quark` 会漏。判断「同一套资料」必须逐文件比对文件名交集，不能凭目录名。

11) `scripts/fetch_resources.py` 是三类资源统一下载入口，实现在 `scripts/downloads/`。进度按阶段分文件 `progress.<stage>.json`。早期 `sanitize_relative_path` 把整段路径当一个段；按 `_数字_` 切分修名的第一版把 `01_1、` 里的序号切掉，617 个文件被判缺号整批重下。`migrate_netdisk_layout.py` 只剥旧树 `<分享标题>_` 一层前缀。文件字节现在走 `library_layout`，不要再写回 `downloads/netdisk/quark/小学/`。`.gitignore` 必须写 `/downloads/`，不带斜杠会把 `scripts/downloads/` 一起忽略。

12) B站 720P 必须走 BBDown 的 TV 接口（`--use-tv-api -e avc -q 720P`，匿名即可）。`yt-dlp` 网页接口匿名最高 480P，且会静默回退。默认路径可用 `BBDOWN_PATH` 覆盖。`<pageNumberWithZero>` 补零位数按本次请求的 P 范围推断，不是合集总数。父进程退出后 BBDown 子进程还能下完当前合集，但不会自己开下一集。年级册取 `resources.json`，不从标题猜。

13) `CORE_PREFIXES` 是五组：`tongbian_chinese` / `renjiao_math` / `renjiao_english` / `beishida_math` / `waiyanshe_english`。必须写全 `beishida_math`（写 `beishida` 会带进北师英语），用 `waiyanshe_english` 而非 `waiyan`（排除 `waiyan_xinjiaoji_english_g2_up`）。两点各有测试。小学英语只做三起点，从三年级起。

14) 外研社版不能按主编登记。国家审定目录按刘兆义 / 孙有中 / 张祖春拆开，B站标题只写「外研版」。只有三上 `BV1GwgK6aEsi`、五上 `BV1qGxw6AE5w` 与平台刘兆义条目同 BVID，其余 `editor` 留空。外研「一起点」不在一二年级英语条目里，条目数为 0。新版教材「集数」普遍虚标：北师数学六上 `BV1Gqhn64ECB` 标题称 51 集实际仅 11 分P，外研六下 `BV1QpKA61Epi` 只有 6P。选课必须调 `view` 取 `videos` 与 `duration` 真值。外研一年级起点「情景动画」每册约 50P 但总时长仅 21-39 分钟，是课文动画不是课。

15) **三阶段全部完成（2026-11-11 23:32）**：`github` 22/22、12.05 GB；`video` 52/52 合集 2894 P、114.54 GB；`netdisk` 9/9 条 12738 个文件、119.42 GB。当时 `downloads/` 合计 246.03 GB，磁盘剩 99.2 GB。网盘九条逐条对齐 `share_total_size_bytes` 且全部 `failed=0`。`video` 与 `netdisk` 可安全并行：`SingleInstance` 按阶段分锁，判活只看各自 pid。**清理循环进程时不要用 `taskkill //T`**：实测误伤正在跑的 video 下载（pid 38636 静默消失、无 manifest 记录）。清理后必须检查 `RUNNING.*.lock` 是否残留陈旧 pid。

16) **本地资料库（2026-11-12）**：`downloads/library/小学/{学科}/{版本}/{年级}/{册}/{用途}/{系列}`。实测 2395 系列、15606 文件、250977666983 字节（约 233.74 GB）。搬迁、夸克、B站、`backfill_missing.py`、`redownload_one.py`、`netdisk_realign.py` 共用 `scripts/downloads/library_layout.py` 的 `destination_for` / `video_directory`。续传看新路径上「存在且字节数一致」，路径不一致会把已有文件判成缺失。用途从系列目录名判定，不看扩展名。语文、道法的「人教」记 `统编版`。年级正则必须写 `(?:年级)?`；`3-6上` 要先于紧凑 `6上`；`一下`/`一上`、`N数上`、`1A`/`3B` 是年级册，课次 `5.5` 不是。文件名没有单册的留在范围目录，不复制到六个年级。查询 `python scripts/library_query.py`；上册不覆盖下册，空年级和 `X至Y年级` 覆盖所问年级。索引 `data/library_catalog.json` 只由 `python scripts/catalog_library.py` 生成，禁止手改文件数。规则在 `docs/13-本地资料库.md`。6 个同字节重复（冀教《七彩练霸》下册）只留一份。旧 `downloads/videos/bilibili/小学` 与 `downloads/netdisk/quark/小学` 已删除。`_inventory.json` / `_missing.json` 仍写 `quark.target_dir_for` 的旧包目录；`netdisk_progress.py` 只扫那里，看不到资料库。

20) 夸克账号容量只有 10 GB，不是硬盘：必须「转存 → 取直链 → 下载 → 删除」逐文件闭环；漏删塞满后转存报 `41020`，容易被误判成登录态失效。实测下载中剩余容量常在 8.4 GB 徘徊，属正常。资料库搬迁是同盘 `os.rename`，不复制约 246 GB。

21) 新世纪小学数学微课 `weike.xsj21.com` 首页内嵌 12 个册次共 865 节，与北师大版同步，但课程页没有 mp4/m3u8，`/api/*` 全 404，只能在线看。智慧教育平台同步课堂是 SPA，HTML 里没有媒体地址。`k12.unischool.cn` DNS 是 NXDOMAIN。`zy.szedu.cn` 可解析但 HTTP/HTTPS 均连接失败。

22) 教材版本不要和网盘教辅混为一谈：`p_math` 的北师大是 PDF 教辅不是同步视频，`p_eng` 不按外研分册。想下北师数学或外研同步课只能走 B站，落地后在资料库的同步课槽。课标 PDF 在 `课标/{义务教育|普通高中}/{年}/`，是标准文本不是课时。

23) Windows 上 `write_json_atomic` 的 `os.replace` 会在目标文件被外部进程打开时抛 `PermissionError`（WinError 5），实测发生在外部脚本读 `progress.netdisk.json` 的瞬间。占用只持续毫秒级，现在是 10 次、0.1s 线性退避（约 4.5s）。早期版本不重试，一次采样就能把下载阶段打成崩溃——错误处理路径上的 flush 抛异常时外层没有兜底。

24) **转存封禁是最大的静默失败源**。实测 `sharepage/save` 间歇返回「当前用户封禁转存功能受限」，几十分钟后自行解除；业务码每次都不同，只能按文案判定（`QuarkError.is_save_banned`）。早期版本对单文件失败只记 `last_error` 继续下一个，跑完整条仍记 `ok`，导致 `p_math` 缺 1882 个、`p_eng` 缺 615 个都是事后才发现。现在：单文件按 120/600/1800 秒三级退避重试，全用完仍封禁则 `break` 停整条；`download_with_login` 返回 `missing` 列表，有失败就记 `incomplete` 并落 `_missing.json`。重跑验证三条均 `failed=0`。

25) **定时汇报与进度计数的陷阱**。30 分钟级汇报不要用单条 `sleep 1800`：实测在 Cursor shell 里只跑约 65 秒就返回，哨兵提前触发；用 `python -c "time.sleep(1800)"`（实测 `elapsed_ms=1801552`）或 `for i in $(seq 1 60); do sleep 30; done` 分段轮询。判断定时器是否存活不能靠 `Get-CimInstance` 匹配命令行关键词——检查命令自身含该关键词会自匹配；改查 `sleep.exe` 是否存在。进度计数一律递归（`ls *.mp4 | wc -l` 只数顶层，实测 202 vs 608）。`progress.<stage>.json` 的 `page_done` 只在条目完成时更新。断点续传与磁盘守卫的判据是「文件存在且字节数一致」；`assert_disk_headroom` 必须按**剩余待下体积**判断，按整条分享体积会让越接近完成的条目越容易被误判成 `skipped_disk`。转存轮询要先查一次再 sleep，无条件先等 0.5s 在几千个小文件时等于白费 33 分钟。校验脚本不能把文件名 `_` 前缀当元数据过滤：网盘里有 `_5 3全优卷….zip`、`_Recycle 2-学习任务单.docx` 这类真实文件，实测因此把 `p_eng` 虚报成缺 8 个。

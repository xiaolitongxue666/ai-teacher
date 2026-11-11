# Project Memory (Compact)

1) 仓库唯一工作副本为 `E:\Code\my_code\Agents\ai-teacher`，远端 `github.com/xiaolitongxue666/ai-teacher`（PUBLIC）。原路径 `C:\Users\Administrator\Projects\ai-teacher` 已删除：双副本 HEAD 相同但工作区会分叉。记忆 SSOT 是根目录 `PROJECT_MEMORY.md`，备份落 `.project-memory-backups/`（保留最近 2 份）。

2) `data/resources.json` 是单一数据源。2026-11-10 实测分区：websites 74 / tutoring 15 / repos 22 / videos 61 / mcp_tools 12 / dify 11 / collections 59。`videos` 从 60 变为 61，是因为补了外研三起点四年级上册。每条记录必须同时有 `verified` 与 `checked_at`。

3) `scripts/check_links.py` 分区：`websites` `tutoring` `repos` `videos` `collections` `markdown` `quark_tree`（全量翻目录）`quark_shallow`（只翻 2 层）`sheet_index`（腾讯文档内嵌链接计数）。默认不含后两个。`write_results_back` 按 section 推断字段：collections 用 `url_official`，其余用 `url`，写反会回写 0 条且不报错。

4) MSYS bash 的 `/tmp` 与 Windows Python 的 `/tmp`（解析为 `C:\tmp`）不是同一路径；跨 bash 与 python 传文件用项目内相对路径。Python 默认 stdout 为 GBK，输出中文必须 `PYTHONIOENCODING=utf-8`（脚本内部已 `reconfigure`，外部调用仍需设）。MSYS 的 `timeout` 会丢弃 `LOCALAPPDATA`。项目盘符写 `/e/...`，不要用 `cmd //c`。

5) websites 分布 ok 61 / blocked 6 / dead 4 / unreachable 3（74 条）。NRICH 连续 3 次 403 判 `blocked`。三个 `unreachable`：trtcocuk、bilimgenc（TÜBİTAK 自建 CA，本机信任链不含）、VOA。本地 DNS 与 DoH 结果可能不同（VOA 本机 174.36.196.242，DoH 返回 Akamai 23.55.143.x），文档要注明两者差异。README 计数表必须与实测同步。

6) Dify 官方 `datasources` 共 17 项，无 webdav 条目；知识库接 WebDAV 只能用社区插件 `shaba/dify-datasource-webdav`（1 star）。官方 `tools/nextcloud` 是 tool 插件不是 datasource。GitHub 星数持续漂移，发布前用 `gh api repos/<slug> --jq .stargazers_count` 复核并同步 `docs/07` 与 `data`；MCP 包版本查 npm `dist-tags.latest` / PyPI `info.version`。

7) 远端先行提交会使 push 被拒；`data/resources.json` 改动密集，rebase 必在它上面冲突。推送被拒时先 `git fetch` 看范围，必要时 `reset --hard origin/main` 后重放。

8) 范老师几何课实测 910 项（909 mp4 + 1 zip），678 个无年级标记，仅标 L6 的 111 条，内容是奥数专题不是课标几何，不能当同步课。

9) 剑桥 A2 Key（KET）标准版纸笔最后一次场次 2026-12-03，之后仅机考；`A2 Key for Schools` 是另一条线。线上口语一对一平台条款差异大，`docs/12` 只收有官方页面佐证的条目。

10) 教辅类资料走浅层口径（`share_probe_depth: "shallow"`），只翻到第 2 层，只报 `share_l2_*`。`docs/03b` 是全量口径，`docs/03c` 是浅层口径，两者不可混写，否则会被误读成「这份才这么点文件」。

11) 夸克分享被违规下架时接口返回 HTTP 404 + `code 41010`，但分享页仍返回 200，只跑 `check_links` 看不出失效。另：腾讯文档总索引：表格数据在 percent-encoded 的 `flyweight.texts` 里，不 unquote 搜 `pan.quark` 会漏。

12) 判断「同一套资料」必须逐文件比对文件名交集，不能凭目录名。

13) `scripts/fetch_resources.py` 是三类资源统一下载入口，实现在 `scripts/downloads/`。进度按阶段分文件 `progress.<stage>.json`。网盘路径：早期 `sanitize_relative_path` 把整段路径当一个段；按 `_数字_` 切分修名的第一版把 `01_1、` 里的序号切掉，617 个文件被判缺号整批重下。`migrate_netdisk_layout.py` 现在只剥 `<分享标题>_` 这一层前缀。`.gitignore` 必须写 `/downloads/`，不带斜杠会把 `scripts/downloads/` 一起忽略。

14) B站 720P 必须走 BBDown 的 TV 接口（`--use-tv-api -e avc -q 720P`，匿名即可）。`yt-dlp` 网页接口匿名最高 480P，且会静默回退。默认路径可用 `BBDOWN_PATH` 覆盖。`<pageNumberWithZero>` 补零位数按本次请求的 P 范围推断，不是合集总数。BBDown 会在 work-dir 建 `<cid>/` 放封面与 `.vclip`，只有纯图片目录才能删。父进程退出后 BBDown 子进程还能下完当前合集，但不会自己开下一集。

15) `CORE_PREFIXES` 是五组：`tongbian_chinese` / `renjiao_math` / `renjiao_english` / `beishida_math` / `waiyanshe_english`。必须写全 `beishida_math`，写 `beishida` 会把北师英语带进来；用 `waiyanshe_english` 而不是 `waiyan`，以排除地方教材 `waiyan_xinjiaoji_english_g2_up`。这两点各有测试。小学英语只做三起点，一起点不下载。

16) 外研社版不能按主编登记。国家审定目录里外研按刘兆义 / 孙有中 / 张祖春拆开，B站标题只写「外研版」或「2026新教材新课标」。只有三上 `BV1GwgK6aEsi`、五上 `BV1qGxw6AE5w` 与平台刘兆义条目同 BVID，其余无法核实，`editor` 留空。原先把 7 格都标成刘兆义是错的。外研「一起点」不在那 3000 条教材记录里，一二年级英语条目数为 0。

17) 新版教材的「集数」普遍虚标。实测北师数学六上原登记 `BV1Gqhn64ECB` 标题称 51 集、实际仅 11 个分P；外研六下 `BV1QpKA61Epi` 标题含上下册却只有 6P。选课时必须调 `view` 接口取 `videos` 与 `duration` 真值，不能信标题。另：外研一年级起点「情景动画」系列每册约 50P 但总时长仅 21-39 分钟（每 P 约 30 秒），是课文动画不是课，不能当同步课用。同类还有「电子教材点读」系列，分P多而单P极短。

18) 2026-11-11 08:20：`video` 阶段已完成 **52/52 合集、2894/2894 P、114.54 GB**，`finished: true`，锁与进程均已清理。五组实测：统编语文 945P/47.07GB、人教数学 716P/16.54GB、北师数学 651P/21.62GB、人教英语 333P/14.20GB、外研三起点英语 249P/15.12GB。校验方式是按 `plan_videos` 逐条比对分P数与零字节文件，900 个新文件全部通过。

19) `video` 与 `netdisk` 可安全并行：`SingleInstance` 按阶段分锁（`RUNNING.video.lock` / `RUNNING.netdisk.lock`），判活只看各自 pid，互不检查也不会杀对方进程；进度写各自的 `progress.<stage>.json`，产物目录也不同。共享的只有磁盘与带宽。**清理循环进程时不要用 `taskkill //T`**：实测它误伤了正在跑的 video 下载（pid 38636 静默消失、无 manifest 记录、日志无报错），只能靠锁 pid 是否存活 + 文件数是否停滞才能发现。清理后必须检查 `RUNNING.*.lock` 是否残留陈旧 pid，有则先删再重启。

20) 磁盘总账（两边全下完）：`netdisk` 11 条实测合计 119.42 GB（`p_math` 50.28、`p_chn` 28.18、`fan_geometry_900` 19.05 三项占 87 GB），`video` 第二轮约 47-65 GB。E 盘 255 GB 起算，全下完剩 82-100 GB，不会触及 20 GB 底线。真正的瓶颈是**夸克账号容量只有 10 GB**，不是硬盘：单条分享远超这个数，必须「转存 → 取直链 → 下载 → 删除」逐文件闭环；漏删塞满后转存报 `41020`，容易被误判成登录态失效。

21) 新世纪小学数学微课 `weike.xsj21.com` 首页内嵌 12 个册次共 865 节，与北师大版同步，但课程页没有 mp4/m3u8，`/api/*` 全 404，`osscdn.xsj21.com` 只开放 image 路径，只能在线看。智慧教育平台同步课堂是 SPA，HTML 里没有媒体地址。外研微课汇页面有 vip 与激活码。`k12.unischool.cn` 的 DNS 是 NXDOMAIN。`zy.szedu.cn` 域名可解析但 HTTP/HTTPS 均连接失败。

22) 用户口径下的教材版本不要和网盘教辅混为一谈：`p_math` 的北师大是 PDF 教辅不是同步视频，`p_eng` 不按外研分册，`xueersi_full` 小学子树按年级和年份季节组织、目录里没有「北师」「外研」「新标准」，`fan_geometry_900` 按解题模型编排、不能当北师同步课。想下北师数学或外研同步课只能走 B站。

23) Windows 上 `write_json_atomic` 的 `os.replace` 会在目标文件被外部进程打开时抛 `PermissionError`（WinError 5），实测发生在外部脚本读取 `progress.netdisk.json` 的瞬间。占用只持续毫秒级，重试即可：现在是 10 次、0.1s 线性退避（约 4.5s）。早期版本不重试，一次采样就能把下载阶段打成崩溃——错误处理路径上的 flush 一抛异常，外层没有兜底。

24) 30 分钟级定时汇报不要用单条 `sleep 1800`：实测在 Cursor 的 shell 里它只跑约 65 秒就返回（`elapsed_ms=64802`），导致哨兵提前触发。可靠做法是 `python -c "time.sleep(1800)"`，实测 `elapsed_ms=1801552`；或用一个短周期轮询 + 时间戳节流。`while true` 循环若 `sleep` 被打断会漂移，且 `wmic` 按关键词计数会把同一条进程链（bash → 子 bash → sleep）算成多份，判重复前必须按 ppid 求根。另：下载进度的正确计数方式：`ls *.mp4 | wc -l` 只数顶层，网盘目录有子层时会少算（实测顶层 202 vs 递归 608）。一律用 `find <dir> -name '*.mp4' | wc -l`。`progress.<stage>.json` 的 `page_done` 只在每个合集/条目完成时更新，集内进度只能数文件。

25) 视频每小时推进量实测（2026-11-10，11:26-15:34 共 4.13 小时）：平均 **125 P/小时、4 GB/小时**，逐小时 117-134 P 很稳定。分P速率会随年级升高而下降（一上 2.44 P/min → 五上 1.48 P/min），原因是单集体积从 19 MB/P 涨到 89 MB/P；所以「每小时多少 P」不能跨年级外推，按 GB/小时 反而更稳。

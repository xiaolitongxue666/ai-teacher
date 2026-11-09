# Project Memory (Compact)

1) 仓库唯一工作副本为 `E:\Code\my_code\Agents\ai-teacher`，远端 `github.com/xiaolitongxue666/ai-teacher`（PUBLIC）。原路径 `C:\Users\Administrator\Projects\ai-teacher` 已删除：双副本 HEAD 相同但工作区会分叉。
2) `data/resources.json` 是单一数据源，分区 websites 74 / tutoring 15 / repos 22 / videos 60 / mcp_tools 12 / dify 11 / collections 59；每条记录必须同时有 `verified` 与 `checked_at`。
3) `scripts/check_links.py` 分区：`websites` `tutoring` `repos` `videos` `collections` `markdown` `quark_tree`（全量翻目录）`quark_shallow`（只翻 2 层）`sheet_index`（腾讯文档内嵌链接计数）。默认不含后两个。`write_results_back` 按 section 推断字段：collections 用 `url_official`，其余用 `url`，写反会回写 0 条且不报错。
4) MSYS bash 的 `/tmp` 与 Windows Python 的 `/tmp`（解析为 `C:\tmp`）不是同一路径。跨 bash 与 python 传文件用项目内相对路径，用完即删。项目盘符写 `/e/...`，不要用 `cmd //c`（报 command not found）。
5) Python 默认 stdout 为 GBK，输出中文必须 `PYTHONIOENCODING=utf-8`；脚本内部已 `reconfigure`，外部调用仍需设。MSYS 的 `timeout` 会丢弃 `LOCALAPPDATA` 等环境变量，依赖它们的脚本别套 `timeout`。
6) websites 当前分布 ok 61 / blocked 6 / dead 4 / unreachable 3（74 条）。NRICH 连续 3 次 403 判 `blocked`。三个 `unreachable`：trtcocuk、bilimgenc（TÜBİTAK 自建 CA，证书 2026-04-30 至 2026-11-14，本机信任链不含该 CA）、VOA。README 计数表必须与实测同步。
7) 本地 DNS 与 DoH 结果可能不同（VOA 本机 174.36.196.242，DoH 返回 Akamai 23.55.143.x），文档记录要注明两者差异而不是任选其一。
8) Dify 官方 `datasources` 共 17 项，**无 webdav 条目**；知识库接 WebDAV 只能用社区插件 `shaba/dify-datasource-webdav`（1 star）。官方 `tools/nextcloud`（langgenius v0.1.7）虽走 WebDAV，但是 tool 插件不是 datasource，进不了知识库摄取列表。
9) GitHub 星数持续漂移，发布前用 `gh api repos/<slug> --jq .stargazers_count` 复核，同步 `docs/07` 与 `data` 两处（一次比对 22 个项目有 10 个已偏）。MCP 包版本核对：npm 用 `registry.npmjs.org/<pkg>` 的 `dist-tags.latest`，PyPI 用 `pypi.org/pypi/<pkg>/json` 的 `info.version`。
10) 远端先行提交会使 push 被拒；`data/resources.json` 改动密集，rebase 必在它上面冲突。正确顺序：`git fetch` 比对范围 → 必要时 `reset --hard origin/main` → 重放改动。
11) 范老师几何课实测 910 项（909 mp4 + 1 zip），678 个无年级标记，仅标 L6 的 111 条，定位是 4-6 年级奥数专题，1-3 年级用不上。
12) 第三方中转域名统一记在 `collections/`：pan.powersharex.com、pan.nameishare.com、pan.quarket.xyz、wpss.best、v.v8l.cn、pan.quarkn.xyz；正文只登真实分享页。
13) 提交统一用 `git-smart-commit --yes`；其 gitignore 门禁会拦 `logs/`、`graphify-out/`、`.claude-mem/`、`__pycache__/`、`*.pyc`、`temp_args.json`、`ERROR.md`、`%SystemDrive%/`、`%USERPROFILE%/`、`.DS_Store`、`Thumbs.db`。
14) 记忆 SSOT 是根目录 `PROJECT_MEMORY.md`，备份落 `.project-memory-backups/`（保留最近 2 份）。本仓 `core.autocrlf=true`，草稿写入后须转 LF，否则 `--validate` 因 CRLF 拒绝。
15) 剑桥 A2 Key（KET）：标准版**纸笔**最后一次场次 2026-12-03，之后仅机考；`A2 Key for Schools` 纸笔与机考均继续，证书不印 "for Schools"。官方累计学时 A2 为 180-200 小时（不是流传的 250）。
16) CET-4/6 **从未**与 CEFR 官方对接。只能走 CSE 间接链条（CSE 3≈A2、CSE 4≈B1、CSE 5≈B1-B2，学界把 CET-4 对到 CSE 5），因此 KET 明确低于 CET-4，文档不得写成「接近四级」。
17) 教辅类资料走**浅层口径**（`share_probe_depth: "shallow"`），只翻到第 2 层，只报 `share_l2_entries`（第 2 层项数），**绝不写 `share_total_files`**。反例实测：初中电子课本第 2 层 36 文件却有 164 个目录，PDF 全在第 3 层。44 条浅层探测约 110 秒；同批全量要数小时。
18) 第 3 层只抽样（`QUARK_SHALLOW_L3_SAMPLE_DIRS = 8`，每个子目录翻 1 页），**抽样不置 `truncated`**。截断标记只表示第 2 层没读全。早期版本扫完第 3 层，导致 `p_math`（仅 8 项）被误标「已截断」。
19) 夸克分享被平台按违规下架时，接口返回 HTTP 404 + `code 41010 文件涉及违规内容`，但 `pan.quark.cn/s/<id>` 分享页仍返回 HTTP 200。只跑 `--only collections` 会误判为 `ok`，必须靠 `quark_shallow` 的业务码。此类条目标 `verified: "dead"` + `status_manual: true`。
20) `status_manual: true` 让所有探测分区跳过该条回写，防止人工判定的 `dead` 被冲成 `ok`。`mismatch` 用于「入口可达但内容为空/不符」（如唯一目录名是「版权受限，暂不提供下载」），空壳有替代入口时写 `replacement_id`。
21) 腾讯文档总索引：表格数据在 percent-encoded 的 `flyweight.texts` 里，不 unquote 直接搜 `pan.quark.cn` 命中 0；真实标题在 base64 的 `basicClientVars` 的 `docInfo.padInfo.padTitle`（明文 `<title>` 只是通用的「腾讯文档」）。`docs.qq.com/dop-api/get/sheet` 需权限票，无登录态返回 `retcode: 56030`，只能解析 HTML。
22) 判断「同一套资料」必须逐文件比对文件名交集，不能凭目录名。实测：「复习资料大礼包」的《课堂作业》44/44、《解题技巧》9/9、《考点清单》50/50、《同步精练》19/19、《黄冈全优卷》22/22 与独立分享完全相同（是重复）；但《七彩课堂》大礼包 20 文件与独立分享 284 文件只交集 3（同名不同内容）。比对递归时 `fid` 传 `"0"` 会得到 0 文件，会误判为「空壳」。
23) 并行会话会用 `git add -A` 把别人正在改的文件一起提交。本仓已发生：`bab0542` 吞掉了当时的 `check_links.py` 与 `data/resources.json` 改动，导致后续 commit 只剩文档增量。多会话并行时提交前用 `git add <具体路径>` 而非 `-A`。
24) 文档计数散落多处，改数据后必须逐处核对：`README.md` 索引四、`docs/00` 分区表、`.cursor/skills/ai-teacher-ops/reference.md` 第 18 行、`docs/03b` 顶部指向 03c 的入口。曾出现 `03b` 写「初中套件 38 条」而实测 39 条的偏差。
25) `collections` 的 59 条分两张清单、两种口径：11 条全量口径在 `docs/03b`（报真实文件总数），48 条浅层口径在 `docs/03c`（只报第 2 层结构）。口径不能混在一页，会被误读成「这份才这么点文件」。

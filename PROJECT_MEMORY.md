# Project Memory (Compact)

1) 仓库唯一工作副本为 `E:\Code\my_code\Agents\ai-teacher`，远端 `github.com/xiaolitongxue666/ai-teacher`（PUBLIC）。原计划路径 `C:\Users\Administrator\Projects\ai-teacher` 已删除：双副本 HEAD 相同但工作区会分叉。
2) `data/resources.json` 是单一数据源，分区 websites / repos / mcp_tools / dify / collections；每条记录必须同时有 `verified` 与 `checked_at`。
3) `scripts/check_links.py` 默认 `--only=websites,repos,collections,markdown`；`write_results_back` 按 section 推断字段，collections 用 `url_official`、其余用 `url`，写反会导致回写 0 条。
4) MSYS bash 的 `/tmp` 与 Windows Python 的 `/tmp`（解析为 `C:\tmp`）不是同一路径。跨 bash 与 python 传文件一律用项目内相对路径，用完即删。
5) MSYS bash 下项目盘符写 `/e/...`；不要用 `cmd //c`（报 command not found）。
6) Python 默认 stdout 为 GBK，输出中文必须 `PYTHONIOENCODING=utf-8`；脚本内部已 `reconfigure`，外部调用仍需设。
7) NRICH 实测连续 3 次 403 判 `blocked`；websites 当前分布 ok 57 / blocked 6 / dead 4 / unreachable 3，README 的计数表必须与之同步。
8) 三个 `unreachable` 站点 trtcocuk / bilimgenc / VOA：DoH 均能解析，TCP 443 超时。bilimgenc 证书由 TÜBİTAK 自建 CA 签发，有效期 2026-04-30 至 2026-11-14，未过期，是本机信任链不含该 CA。
9) 本地 DNS 与 DoH 结果可能不同（VOA 本机 174.36.196.242，DoH 返回 Akamai 23.55.143.x），文档记录要注明两者差异而不是任选其一。
10) Dify 官方 `datasources` 共 17 项，**无 webdav 条目**；知识库接 WebDAV 只能用社区插件 `shaba/dify-datasource-webdav`（1 star）。
11) Dify 官方 `tools/nextcloud`（langgenius v0.1.7）走 WebDAV，但是 tool 插件不是 datasource，进不了知识库摄取列表，只能在工作流节点调用。
12) GitHub 星数持续漂移，发布前用 `gh api repos/<slug> --jq .stargazers_count` 复核，并同步 `docs/07` 与 `data` 两处（一次比对 22 个项目有 10 个已偏）。
13) MCP 包版本核对接口：npm 用 `registry.npmjs.org/<pkg>` 的 `dist-tags.latest`，PyPI 用 `pypi.org/pypi/<pkg>/json` 的 `info.version`；结果写入 `latest_version_checked`。
14) 远端先行提交会使 push 被拒；本仓 `data/resources.json` 改动密集，rebase 必在它上面冲突。正确顺序：`git fetch` 比对范围 → 必要时 `reset --hard origin/main` → 重放改动。
15) 范老师几何课实测 910 项（909 mp4 + 1 zip），678 个无年级标记，仅标 L6 的 111 条，定位是 4-6 年级奥数专题，1-3 年级用不上。
16) 第三方中转域名统一记在 `collections/`：pan.powersharex.com、pan.nameishare.com、pan.quarket.xyz、wpss.best、v.v8l.cn、pan.quarkn.xyz；正文只登真实分享页。
17) 提交统一用 `git-smart-commit --yes`；其 gitignore 门禁会拦 `logs/`、`graphify-out/`、`.claude-mem/`、`__pycache__/`、`*.pyc`、`temp_args.json`、`ERROR.md`、`%SystemDrive%/`、`%USERPROFILE%/`、`.DS_Store`、`Thumbs.db`。
18) 文档与 `data` 的一致性可脚本校验：五列表匹配 `| 名称 | 年龄 | \`status\` | 说明 | 链接 |`，四列表取首列链接与末列状态。
19) 记忆 SSOT 是根目录 `PROJECT_MEMORY.md`，备份落 `.project-memory-backups/`（保留最近 2 份）。本仓 `core.autocrlf=true`，草稿写入后须转 LF，否则 `--validate` 因 CRLF 拒绝。

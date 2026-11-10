# ai-teacher

面向孩子与青少年的学习资源导航。**这不是一套课程，是一张资源地图。**

这个仓库只做三件事：

1. 把散落在群聊、短视频、网盘里的学习资源，按 **适合人群** 和 **科目类别** 重新组织成可检索的清单；
2. 给每条链接标注 **核验状态** 和 **核验时间**，让你知道它到底还能不能打开；
3. 把「网盘下载」和「PDF OCR」这两件脏活，整理成可复用的工具选型（Cursor MCP / Dify 插件），并写明哪些说法经不起核实。

资源本身不托管在本仓库。所有教材、音视频、试题的版权归原权利人。

---

## 从这里开始

| 你想做什么 | 看这里 |
| --- | --- |
| 先搞清楚这个仓库怎么用 | [docs/00-使用说明.md](docs/00-使用说明.md) |
| 我家孩子 X 岁，该从哪下手 | [docs/01-适合人群.md](docs/01-适合人群.md) |
| 我要补某个科目 | [docs/02-科目类别.md](docs/02-科目类别.md) |
| 找免费学习网站 | [docs/03-参考网站.md](docs/03-参考网站.md) |
| 找成套的网盘资料 | [docs/03b-网盘资料清单.md](docs/03b-网盘资料清单.md)、[docs/03c-教辅成套清单.md](docs/03c-教辅成套清单.md) |
| 按教材版本找配套视频课 | [docs/11-在线视频课程.md](docs/11-在线视频课程.md) |
| 配置网盘 / OCR 工具 | [docs/04-工具推荐.md](docs/04-工具推荐.md)、[mcp/README.md](mcp/README.md)、[dify/README.md](dify/README.md) |
| 方法比资源更重要 | [docs/05-学习方法论.md](docs/05-学习方法论.md) |
| 按年龄排一个学习计划 | [docs/06-学习路线图.md](docs/06-学习路线图.md) |
| 想知道 KET / 剑桥五级是什么、要不要考 | [docs/10-剑桥英语KET.md](docs/10-剑桥英语KET.md) |
| 想找口语一对一的真人老师 | [docs/12-线上口语一对一.md](docs/12-线上口语一对一.md) |
| 想直接读代码 / 自建 | [docs/07-开源项目清单.md](docs/07-开源项目清单.md)、[docs/08-DeepTutor-拆解.md](docs/08-DeepTutor-拆解.md) |
| 想知道这仓库踩过哪些坑、为什么这么设计 | [docs/09-开发复盘.md](docs/09-开发复盘.md) |
| 用 agent 维护这个仓库 | [.cursor/skills/ai-teacher-ops/SKILL.md](.cursor/skills/ai-teacher-ops/SKILL.md) |

---

## 分龄速查

| 年龄段 | 主打方向 | 首选入口 | 建议投入 |
| --- | --- | --- | --- |
| 2-3 岁 | 声音与画面直连，建立「外语 = 好玩」 | Starfall、PBS Kids、Sesame Street | 每天 20-30 分钟动画，户外 2 小时 |
| 3-6 岁 | 自然拼读、听力量 | Reading Bear、Storyline Online、StoryWeaver | 每天 30 分钟，全程不翻译 |
| 小学 1-3 | 分级阅读、图形认知 | Oxford Owl、范老师几何思维课（1-3 年级段） | 每天 30-45 分钟 |
| 小学 4-6 | 章节书、几何推理、打字 | Free Kids Books、范老师几何思维课（挑专题）、TypingClub | 每天 45-60 分钟 |
| 初中 | 学科英语、科学实验 | BBC Bitesize、PhET、爆笑初中9科全套 | 每天 30 分钟英语 + 课内 |
| 高中 / 成人 | 雅思托福、四六级、原版阅读 | IELTS Atlas、Word Atlas、awesome-english-ebooks | 按考试节奏 |

更细的阶段目标见 [docs/06-学习路线图.md](docs/06-学习路线图.md)。

---

## 索引一：适合人群

| 人群 | 核心矛盾 | 对应文档 |
| --- | --- | --- |
| 学前（2-6 岁） | 母语尚未固化，需要声音 + 画面直连 | [docs/01](docs/01-适合人群.md) |
| 小学低年级（1-3） | 从「听懂」过渡到「读懂」 | [docs/01](docs/01-适合人群.md) |
| 小学高年级（4-6） | 阅读量爆发期，同时补数学思维 | [docs/01](docs/01-适合人群.md) |
| 初中 | 学科英语与理科实验 | [docs/01](docs/01-适合人群.md) |
| 高中 / 成人 | 应试 + 真实语境 | [docs/01](docs/01-适合人群.md) |

## 索引二：科目类别

| 科目 | 免费网站 | 成套资料 | 开源项目 |
| --- | --- | --- | --- |
| 英语 | Reading Bear、YouGlish、Tatoeba | 小学 1000 词、自然拼读 270 页、Wordly Wise 3000 | [Word Atlas](https://github.com/designfuchen/word-atlas)、[NCE](https://github.com/iChochy/NCE) |
| 数学（含几何） | NRICH、Math Playground、Bedtime Math | **范老师几何思维课（909 个视频，4-6 年级专题）** | [cn-math-taxonomy](https://github.com/xiaoyang111222/cn-math-taxonomy)、[FreePEP](https://github.com/siknet/FreePEP) |
| 科学 | PhET、NASA Space Place、Exploratorium | **爆笑初中9科全套**（物理 3 版、化学 3 版、生物 6 模块） | [BodyVista](https://github.com/FreedomIntelligence/BodyVista)、[atlas-of-physics](https://github.com/nathanliow/atlas-of-physics) |
| 编程与逻辑 | Scratch、Code.org、CodeCombat | Scratch 3.0 全套 174 节 | [algorithm-visualizer](https://github.com/algorithm-visualizer/algorithm-visualizer) |
| 艺术与音乐 | musictheory.net、Art for Kids Hub、Tate Kids | — | — |
| 通识百科 | Simple Wikipedia、BBC Bitesize、DK Learning | — | — |
| 教材 | basic.smartedu.cn | — | [tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser) |

## 索引三：参考网站（节选）

完整清单 74 条见 [docs/03-参考网站.md](docs/03-参考网站.md)，每条带核验状态。

| 状态 | 数量 | 含义 |
| --- | --- | --- |
| ok | 61 | 可直接访问 |
| blocked | 6 | 站点反爬，浏览器能打开，脚本探测被拦 |
| dead | 4 | 域名不存在或站点已关停 |
| unreachable | 3 | DNS 正常但本机连不上（境外站点直连） |

> 状态由 [scripts/check_links.py](scripts/check_links.py) 生成，最新核验时间见 `data/resources.json` 的 `checked_at`。

## 索引四：网盘成套资料

59 份资料，分两张清单：

| 清单 | 条数 | 口径 | 内容 |
| --- | --- | --- | --- |
| [docs/03b-网盘资料清单.md](docs/03b-网盘资料清单.md) | 11 | 全量翻完目录树，报真实文件数 | 视频课、单词书、教材工具、爆笑初中9科、学而思全套 |
| [docs/03c-教辅成套清单.md](docs/03c-教辅成套清单.md) | 48 | 只翻到第 2 层，**不报文件总数** | 小学预习复习包 5、初中全科套件 39、课件教案索引 4 |

03c 那份的浅层口径是刻意的：教辅包是「1 个总目录 → 几十个教辅目录 → 再按年级分册」，全量遍历一条要几分钟，44 条要好几小时。所以只报「第 2 层 66 项」这类结构量，不用它冒充规模。实测反例：某条初中电子课本第 2 层只有 36 个文件，第 3 层却有 164 个目录，PDF 全在下面。

03b 里数学方向的 **范老师·小学数学几何思维课**，我拉了完整目录核对：夸克分享里实际是 **910 个条目**（909 个 mp4 + 1 个 `电子档资料.zip`），「900 节」这个数量属实。但**「1-6 年级全覆盖」不成立**——910 个文件里 678 个没有年级标记，带标记的 232 个中只标 L6 的就有 111 条，真正覆盖到 1-2 年级的只有 4 条且都是全年级通用的速算技巧题；按主题看是奥数专题（巧求面积 150 条、鸡兔同笼 10、容斥 9、行程 8）。

三条实测与原始描述不符的，已在文档里标出：

| 条目 | 问题 |
| --- | --- |
| 智慧教育平台电子教材下载器 | 短链指向「网盘热门资源2000T」扫码页，已移除，替换为 [tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser) |
| Scratch 3.0 全套 | 聚合页标题写 214 节，资源描述写 174 节 |
| 范老师几何思维课 | 数量属实，但年级覆盖与描述不符，内容以 4-6 年级奥数为主 |

03c 里也有三条问题条目：

| 条目 | 问题 |
| --- | --- |
| 初中全科《53中考复习资料》 | **已被平台按违规下架**：接口返回 `code 41010 文件涉及违规内容`，但分享页仍返回 HTTP 200，只探链接会误判为正常 |
| 初中全科《53初中知识清单》 | 独立分享是空壳（唯一目录名「版权受限，暂不提供下载」），但复习资料大礼包里有一套完整 9 册 |
| 《优化设计》 | 原清单里同一条出现两次，指向同一 share id，已合并 |

另外 03c 做了逐文件比对：「初中全科《复习资料》打包合集」的 48 个目录里，绝大部分在其余 39 条里另有独立分享，而且不是新资料——《解题技巧》9/9、《考点手册》50/50、《同步精练》19/19、《课堂作业》44/44、《黄冈全优卷》22/22 全部逐文件相同。先用大礼包看全貌，不必逐条重复下载。

`pan.quark.cn/s/3d2dd7b91043` 已查实为 **「爆笑初中9科全套」**：初中物理/化学/数学/地理/历史/生物/语文/英语/政治九科动画课，外加乐乐课堂 18 项（含小学奥数与高中课程）。注意目录里有 `(1)` 重复副本：数学 13 组目录全部成对、乐乐课堂 9 组全部成对、地理只有 8 章成对，下载前按目录树挑，别整包拖。

## 索引五：工具推荐

| 需求 | 首选 | 安装 |
| --- | --- | --- |
| 接坚果云 / Nextcloud | `webdav-mcp-server` | `npx -y webdav-mcp-server` |
| 接百度 / 阿里 / 115 / 夸克 | `sync-vault-agent` | `npm i -g sync-vault-agent && mcp-agent init` |
| 下载视频（B站 / YouTube） | `yt-dlp` | `uvx yt-dlp <URL>` |
| 下载 B站 720P 以上 | `BBDown` | `BBDown --use-tv-api -q 720P <URL>` |
| 本地 PDF → Markdown | `pymupdf4llm-mcp` | `uvx pymupdf4llm-mcp` |
| 本地 PDF OCR（轻量） | `pdffr-mcp` | `npx -y pdffr-mcp` |
| Dify 知识库解析 | MinerU（官方插件） | Dify 插件市场直接装 |

视频下载有边界两层：

- `yt-dlp` **下不了任何国内网盘**（夸克、百度、阿里、115 全无提取器）。网盘里的 mp4 先用网盘客户端或 `BaiduPCS-Go` 落盘。
- `yt-dlp` 匿名态在 B站 **最高只有 480P**（`-F` 会写 `1080P 大会员, 720P 大会员 are missing`），
  且它静默回退不报错。要 720P 用 `BBDown --use-tv-api`；要 1080P 得给大会员 Cookie。

选型理由、被证伪的说法、Windows 上的坑，见 [docs/04-工具推荐.md](docs/04-工具推荐.md)。

---

## 目录结构

```
ai-teacher/
├── README.md
├── docs/                      # 全部正文
├── data/resources.json        # 单一数据源，脚本与文档都从这里取
├── mcp/                       # Cursor MCP 配置模板
├── dify/                      # Dify 插件方案
├── collections/               # 网盘链接原始清单（含提取码）
├── scripts/check_links.py     # 链接核验
├── scripts/fetch_resources.py # 三类资源统一下载入口
├── scripts/downloads/         # 下载管道实现（github / bilibili / quark）
├── downloads/                 # 下载产物（已 gitignore）
└── .cursor/skills/            # 维护本仓库的 agent skill
```

## 批量下载

`scripts/fetch_resources.py` 把 `data/resources.json` 里的 GitHub 仓库、B站课程、网盘分享
统一落到 `downloads/` 下，按学科 / 教材版本 / 年级分层命名。

```bash
python scripts/fetch_resources.py plan                 # 只估算体积，不下载
python scripts/fetch_resources.py run --only github    # 浅克隆 22 个仓库（按体积升序）
python scripts/fetch_resources.py run --only video     # B站小学核心三科，1994 P
python scripts/fetch_resources.py run --only netdisk   # 夸克小学条目（需 Cookie）
python scripts/fetch_resources.py status               # 轮询进度
python scripts/fetch_resources.py report               # 生成 REPORT.md
```

产物布局：

```
downloads/
├─ _state/                     # progress.<阶段>.json、REPORT.md、run.log
├─ github/<owner>__<repo>/     # 浅克隆，保留 .git
├─ videos/bilibili/小学/<学科>-<版本>/<年级>-<册>/[P001] 标题.mp4
└─ netdisk/quark/小学/<id>__<资料名>/
```

三条必须知道的边界：

- **720P 靠 BBDown 的 TV 接口**。`yt-dlp` 走网页接口匿名最高 480P，720P/1080P 被标成大会员专属，
  且它会静默回退而不报错。`BBDown --use-tv-api -q 720P` 匿名即可 720P，实测产出
  h264 / 1280x720 / 约 24 MB 每 15 分钟课时。用 `BBDOWN_PATH` 环境变量指定 exe 路径。
- **夸克匿名只能列举、不能下载**。`sharepage/token` 与 `sharepage/detail` 无需登录，
  能翻完整个目录（已实测 910 项）；但 `sharepage/save` 与 `file/download` 一律返回
  `401 code 31001 require login`。没有 Cookie 时该阶段自动降级为「只产清单」，
  把完整的 `_inventory.json`（fid / size / 相对路径）写进目录，填上
  `.credentials/netdisk.env` 的 `NETDISK_QUARK_COOKIE` 后重跑同一命令即可续传。
- **本机 Chrome 的 Cookie 读不出来**，别指望脚本自动取。Chrome 156 全库 3484 条都是
  `v20`（App-Bound Encryption），密钥链是 SYSTEM DPAPI → elevation_service.exe 内置密钥，
  外部进程走不通。把 profile 复制到 `--user-data-dir` 让 Chrome 自己解密也不行：实测
  启动瞬间把夸克登录态 6 条（`__pus`/`__puus`/`__kp`/`__kps`/`__uid`/`_UP_A4A_11_`）连同
  3482 行一起清成 0 行。Chrome 136+ 还禁止默认 user-data-dir 开 `--remote-debugging-port`，
  `RemoteDebuggingAllowed` 策略也绕不过。只能手工从 DevTools 的 `drive-h.quark.cn` 请求里
  复制整段 Cookie 头。
- **部分网盘分享需要提取码**，码在 `data/resources.json` 的 `note` 字段里。管道内写死了两条
  实测需要的：`primary_1000_words` = `YhRG`、`phonics_270` = `ab8M`。

长任务请后台跑再轮询，别占前台：

```bash
python scripts/fetch_resources.py run --only video > downloads/_state/run.log 2>&1 &
python scripts/fetch_resources.py status
```

如果视频阶段是由别的会话/旧版本代码启动的（不写 `progress.video.json`），
用旁观采集补上观测能力，它只数磁盘文件、不干预下载：

```bash
python scripts/watch_video.py &
```

### 下载进度（2026-11-10 快照）

| 阶段 | 状态 | 已落地 | 备注 |
| --- | --- | --- | --- |
| `github` | 完成 22/22 | 12.05 GB（磁盘实测）/ 11.64 GB（manifest 记录） | 实下 3 个，19 个按 `skipped` 跳过 |
| `video` | 完成 32/32 | 1994 P / 77.80 GB | 小学语文 12 + 数学 12 + 英语 8 个合集全部下满 |
| `netdisk` | 进行中 | 410 项 / 6.34 GB（`fan_geometry_900`） | 该条目标称 910 项 / 19.05 GB |

`downloads/` 合计约 96.2 GB，磁盘剩余约 261 GB。

网盘阶段是逐条串行的：`fan_geometry_900` 未跑完，后面 10 条（`primary_1000_words`、`phonics_270`、
`p_chn`、`p_math`、`p_eng`、`p_morality`、`p_sci`、`j_curriculum` 等，合计 119.42 GB）不会开始。
看进度用 `progress.netdisk.json` 的 `current` 字段，它写的是正在下的那个文件名。

两个只读观测脚本，都不干预下载进程：

```bash
python scripts/netdisk_progress.py    # 按 _inventory.json 比对「已落盘且体积一致」的完成度
python scripts/fetch_resources.py status
```

`netdisk_progress.py` 依赖各条目目录下的 `_inventory.json`，而**下载模式不写这个文件**
（只有无登录态的清单模式才写）。所以在纯下载产物目录上它只输出 `0 B / 0 B` ——
当前 `fan_geometry_900` 就是这种情况，实际进度只能靠 `ls` 计数或 `progress.netdisk.json` 的 `current`。

`progress.video.json` 的 `finished: true` 来自 `watch_video.py` 旁路采集，不是下载进程自报；
下载进程本身从不写进度文件，所以「有没有在跑」只能看目录 mtime 或进程列表。

### 实现中踩到的坑（改动这些代码前必读）

- **`git clone` 的完整性判据是 `.git/index`，不是 `.git/HEAD`**。clone 一开始就建好 HEAD
  再开始 fetch，中途被杀会留下「有 HEAD 但工作区空」的半成品，只看 HEAD 会误判为已完成。
- **不能用线程读 `git clone` 的 stderr**。git 派生的孙进程（`index-pack`、`git-remote-https`）
  会继承管道写端，父进程退出后 `for line in stderr` 仍不返回，主流程永久卡在 `join` 上。
  `github.py` 改为把 `--progress` 重定向到 `_state/git-progress.log`，主循环定时读文件新增部分。
- **停滞检测按「多久没有新输出」判断**，不按文件大小：LFS 拉取阶段 `.git` 不增长。
  默认连续 180 秒无输出即判定连接已死，`taskkill /T` 杀整棵进程树（只杀父进程会留下持锁子进程）。
- **`os.kill(pid, 0)` 在 Windows 上对已退出 pid 抛 `SystemError` 而不是 `OSError`**，
  只捕后者会让单实例锁直接崩在半路。
- **`.gitignore` 里的 `downloads/` 会连 `scripts/downloads/` 一起忽略**，必须写成 `/downloads/`。
- **并发阶段各写 `progress.<stage>.json`**，共用一个 `progress.json` 会互相覆盖；
  汇总视图由 `status` 合成写入 `progress.json`。
- **BBDown 会在 work-dir 下建 `<cid>/` 放封面与 `.vclip` 分片**，只有「纯图片」目录可删，
  否则会删掉正在下载的分片。
- **夸克登录态下载的 `stoken` 每取一次就换新值，且只有最新那个有效**。`walk_share` 拿目录时
  得到的 `share_fid_token` 与会话里的 `stoken` 绑定；若在转存前再调一次 `share_token`
  （哪怕传入完全相同的参数），旧 token 立刻失效，save 报 `41020 转存文件token校验异常`。
  实测两次调用返回的 stoken 不相等，且用新 stoken 立即转存同样失败。`walk_share` 现在把
  `stoken` 一起返回，`download_with_login` 必须复用它。
- **匿名拿到的 `share_fid_token` 不能用于登录态转存**：同一条目在匿名与登录两种 opener 下
  返回的 token 每条都不同，混用一律 `41020`。登录下载必须用同一个 opener 既走目录又转存。
- **`file/download` 用浏览器 UA 返回 `400 code 23018 download file size limit`**，
  非会员和 Svip 都会（官方限制 Web 端 >100 MB）。换夸克 PC 客户端 UA
  （`quark-cloud-drive/3.14.2 ...`）立刻放行，两种 UA 实测对照过。
- **直链本身也要带 Cookie**，否则 CDN 返回 `412 Precondition Failed`。
- **非会员是账号级限速，单连接固定约 100 KB/s**。与代理无关（直连与走 `127.0.0.1:7890`
  同为 101 KB/s），并发 1/4/8 也都不变。只有靠 Range 分片叠加并发：
  64 并发 613 KB/s、256 并发 2.15 MB/s、512 并发 2.90 MB/s，1024 并发退化到 0.8 MB/s
  且大量连接失败，所以并发封顶 512。
- **分片大小必须按并发数倒推，不能固定 1 MB**。吞吐只取决于并发连接数，而片数 = 体积/片大。
  固定 1 MB 时 20 MB 文件只切 21 片（21 并发）→ 202 KB/s；切 32 KB → 118 片 → 927 KB/s。
  同一个文件快 4.6 倍。`_download_ranged` 现在按 `size/workers` 算片大，并夹在 32 KB–4 MB 之间。
- **非会员账号总容量只有 10 GB**，而小学资料 119.42 GB。必须「转存 → 取直链 → 下载 → 删除」
  逐文件闭环，删除放在 `finally` 里：下载失败不清理，几次大文件失败就把容量塞满，
  后续所有文件都会卡在转存一步，且报错是误导性的 `41020` 而非容量不足。
- **转存返回的 fid 是新的**。`sharepage/save` 只回 `task_id`，要轮询 `/1/clouddrive/task`
  到 `status == 2`，再从 `save_as.save_as_top_fids` 取新 fid；用分享里的原 fid 去
  `file/download` 一定失败——那是别人的文件 id。
- **`<pageNumberWithZero>` 的补零位数由 BBDown 按本次请求的 P 范围推断**，不是按合集总数。
  100P 的合集全量下载得到 `[P001]`..`[P100]`，但 `-p 1,2` 只得到 `[P1]`、`[P2]`。
  用 `-p` 补下会产生同名重复，`normalize_page_numbers()` 在每轮下载后统一位数。


## 核验链接

```bash
python scripts/check_links.py            # 只报告
python scripts/check_links.py --write    # 回写 verified / checked_at
```

纯标准库，无需安装依赖，Python 3.10+ 即可。

## 测试

```bash
python -m unittest discover -s tests -v
```

覆盖下载管道的纯函数：文件名清洗（含 Windows 保留名与尾部点）、目录推导、
体积格式化、git 进度行解析、进度合并。涉及真实克隆与下载的部分靠人工冒烟，
不在单测里伪造。

## 免责声明

- 本仓库是**链接索引**，不托管、不转存任何教材、音视频、试题文件。
- 网盘资料的版权归原权利人，分享链接由第三方提供，本仓库不保证其合法性、完整性与长期有效性。
- 第三方短链域名（`pan.powersharex.com`、`pan.nameishare.com`、`pan.quarket.xyz`、`wpss.best`、`v.v8l.cn`、`pan.quarkn.xyz`）稳定性不可预期，失效属正常现象。
- 下载并运行第三方可执行文件（如各类下载器）存在安全风险，请自行查毒并评估。
- `downloads/` 下的产物仅供个人离线学习，**未纳入版本控制**，也不随仓库分发。

## License

文档内容采用 CC BY 4.0，脚本代码采用 MIT，见 [LICENSE](LICENSE)。

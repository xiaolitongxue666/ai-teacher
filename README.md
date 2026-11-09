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
| 本地 PDF → Markdown | `pymupdf4llm-mcp` | `uvx pymupdf4llm-mcp` |
| 本地 PDF OCR（轻量） | `pdffr-mcp` | `npx -y pdffr-mcp` |
| Dify 知识库解析 | MinerU（官方插件） | Dify 插件市场直接装 |

视频下载有边界：`yt-dlp` **下不了任何国内网盘**（夸克、百度、阿里、115 全无提取器）。网盘里的 mp4 先用网盘客户端或 `BaiduPCS-Go` 落盘。

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
└── .cursor/skills/            # 维护本仓库的 agent skill
```

## 核验链接

```bash
python scripts/check_links.py            # 只报告
python scripts/check_links.py --write    # 回写 verified / checked_at
```

纯标准库，无需安装依赖，Python 3.10+ 即可。

## 免责声明

- 本仓库是**链接索引**，不托管、不转存任何教材、音视频、试题文件。
- 网盘资料的版权归原权利人，分享链接由第三方提供，本仓库不保证其合法性、完整性与长期有效性。
- 第三方短链域名（`pan.powersharex.com`、`pan.nameishare.com`、`pan.quarket.xyz`、`wpss.best`、`v.v8l.cn`、`pan.quarkn.xyz`）稳定性不可预期，失效属正常现象。
- 下载并运行第三方可执行文件（如各类下载器）存在安全风险，请自行查毒并评估。

## License

文档内容采用 CC BY 4.0，脚本代码采用 MIT，见 [LICENSE](LICENSE)。

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
| 找成套的网盘资料 | [docs/03b-网盘资料清单.md](docs/03b-网盘资料清单.md) |
| 配置网盘 / OCR 工具 | [docs/04-工具推荐.md](docs/04-工具推荐.md)、[mcp/README.md](mcp/README.md)、[dify/README.md](dify/README.md) |
| 方法比资源更重要 | [docs/05-学习方法论.md](docs/05-学习方法论.md) |
| 按年龄排一个学习计划 | [docs/06-学习路线图.md](docs/06-学习路线图.md) |
| 想直接读代码 / 自建 | [docs/07-开源项目清单.md](docs/07-开源项目清单.md) |

---

## 分龄速查

| 年龄段 | 主打方向 | 首选入口 | 建议投入 |
| --- | --- | --- | --- |
| 2-3 岁 | 声音与画面直连，建立「外语 = 好玩」 | Starfall、PBS Kids、Sesame Street | 每天 20-30 分钟动画，户外 2 小时 |
| 3-6 岁 | 自然拼读、听力量 | Reading Bear、Storyline Online、StoryWeaver | 每天 30 分钟，全程不翻译 |
| 小学 1-3 | 分级阅读、图形认知 | Oxford Owl、范老师几何思维课（1-3 年级段） | 每天 30-45 分钟 |
| 小学 4-6 | 章节书、几何推理、打字 | Free Kids Books、范老师几何思维课（4-6 年级段）、TypingClub | 每天 45-60 分钟 |
| 初中 | 学科英语、科学实验 | BBC Bitesize、PhET、News in Levels | 每天 30 分钟英语 + 课内 |
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
| 数学（含几何） | NRICH、Math Playground、Bedtime Math | **范老师几何思维课 900 节** | [cn-math-taxonomy](https://github.com/xiaoyang111222/cn-math-taxonomy) |
| 科学 | PhET、NASA Space Place、Exploratorium | — | [BodyVista](https://github.com/FreedomIntelligence/BodyVista)、[atlas-of-physics](https://github.com/nathanliow/atlas-of-physics) |
| 编程与逻辑 | Scratch、Code.org、CodeCombat | Scratch 3.0 全套 174 节 | [algorithm-visualizer](https://github.com/algorithm-visualizer/algorithm-visualizer) |
| 艺术与音乐 | musictheory.net、Art for Kids Hub、Tate Kids | — | — |
| 通识百科 | Simple Wikipedia、BBC Bitesize、DK Learning | — | — |

## 索引三：参考网站（节选）

完整清单 70 条见 [docs/03-参考网站.md](docs/03-参考网站.md)，每条带核验状态。

| 状态 | 数量 | 含义 |
| --- | --- | --- |
| ok | 58 | 可直接访问 |
| blocked | 5 | 站点反爬，浏览器能打开，脚本探测被拦 |
| dead | 4 | 域名不存在或站点已关停 |
| unreachable | 3 | DNS 正常但本机连不上（境外站点直连） |

> 状态由 [scripts/check_links.py](scripts/check_links.py) 生成，最新核验时间见 `data/resources.json` 的 `checked_at`。

## 索引四：网盘成套资料

10 份成套资料，见 [docs/03b-网盘资料清单.md](docs/03b-网盘资料清单.md)。其中数学方向的主入口是 **范老师·小学数学几何思维课（900 节，1-6 年级）**。

其中两条实测与原始描述不符，已在文档里标出：

| 条目 | 问题 |
| --- | --- |
| 智慧教育平台电子教材下载器 | 短链实际指向「网盘热门资源2000T」扫码页，不是教材下载器 |
| Scratch 3.0 全套 | 聚合页标题写 214 节，资源描述写 174 节 |

## 索引五：工具推荐

| 需求 | 首选 | 安装 |
| --- | --- | --- |
| 接坚果云 / Nextcloud | `webdav-mcp-server` | `npx -y webdav-mcp-server` |
| 接百度 / 阿里 / 115 / 夸克 | `sync-vault-agent` | `npm i -g sync-vault-agent && mcp-agent init` |
| 本地 PDF → Markdown | `pymupdf4llm-mcp` | `uvx pymupdf4llm-mcp` |
| 本地 PDF OCR（轻量） | `pdffr-mcp` | `npx -y pdffr-mcp` |
| Dify 知识库解析 | MinerU（官方插件） | Dify 插件市场直接装 |

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
└── scripts/check_links.py     # 链接核验
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

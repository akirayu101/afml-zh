# AFML 中文翻译流程

## 专家角色

- 金融专家：校准金融、投资、市场微观结构、回测和风险管理术语。
- 量化程序专家：保护代码、包名、API、变量、路径、URL、命令和参数。
- 数学专家：保护 MathJax/TeX，检查公式周围中文是否改变数学语义。
- 中文排版专家：检查中英混排、中文标点、标题、caption、表格、代码框和移动端宽度。

## 不翻译内容

- `code`、`pre`、`.sourceCode`、`.math.inline`、`.math.display`、`script`、`style`、`svg`、`mjx-container`。
- Python 关键字、包名、函数名、变量名、文件名、URL、命令、参数名。
- 参考文献条目正文默认保留英文，翻译标题 `References` 为 `参考文献`。
- 人名、论文名、模型专名按术语表处理；缩写如 `CPCV`、`PBO`、`PSR`、`DSR`、`HRP` 保留。

## 输出结构

- 英文站点保留在 `book/`。
- 中文站点生成到 `zh/`。
- 人工重译和审查后的章节文本保存在 `translations/zh/chapters/*.json`。每条记录同时保存稳定键、英文源文和中文译文；生成时这些章节覆盖文件优先于旧版 `cache.json`，便于逐章对照审查，也避免重新生成时丢失人工修订。
- 根入口 `index.html` 可在发布中文 Pages 时跳转到 `zh/index.html`。
- 中文站点共享 `assets/`，并复制/复用正式图像资源。

## QA

- HTML 结构必须保留：章节数、figure/code/table 数量、MathJax 节点数量、锚点和链接。
- 中文页面不得出现未恢复的占位符，例如 `__AFML_KEEP_0__`。
- 代码块内容与英文源逐字一致。
- MathJax 节点文本与英文源逐字一致。
- 页面级横向溢出仍必须为 0；代码、表格、长公式只允许在自身容器内部滚动。
- 图像资源必须与英文源章节逐章一致，封面页按简化后的封面例外处理；中文站点复制出的图片文件应与 `book/media` 源文件字节一致。
- 图片、表格、代码说明文字使用独立 caption 样式，不混同正文；编号格式固定为 `图 1.1：`、`表 1.1：`、`代码清单 1.1：`。
- 脚注正文不直接插在正文流中；正文仅保留可点击角标，脚注内容统一移动到章末 `脚注` 区。
- 正文引用同样统一为 `图 1.1`、`表 1.1`、`代码清单 1.1`，不得残留 `代码片段`、`Snippet`、无空格的 `图1.1`。
- 公式周围必须人工或脚本复核，重点查找 `的均值，<公式>`、`……的`、`关于…`、`为…` 等机器翻译残片。
- 面向中国大陆读者采用中文全角标点；中文正文中不得残留 `U.S.` 这类未本地化片段，除参考文献正文按英文保留外。
- `multiprocessing` 作为 Python 模块名时保留英文；描述架构或技术概念时译为 `多进程`。

推荐每轮运行：

```bash
python3 scripts/audit_zh_chapter_overrides.py --chapter chapter-XX
python3 scripts/translate_book_zh.py --cache-path translations/zh/cache.json
python3 scripts/audit_zh_translation.py
python3 scripts/audit_zh_quality.py
```

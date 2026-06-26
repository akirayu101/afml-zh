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
- 根入口 `index.html` 可在发布中文 Pages 时跳转到 `zh/index.html`。
- 中文站点共享 `assets/`，并复制/复用正式图像资源。

## QA

- HTML 结构必须保留：章节数、figure/code/table 数量、MathJax 节点数量、锚点和链接。
- 中文页面不得出现未恢复的占位符，例如 `__AFML_KEEP_0__`。
- 代码块内容与英文源逐字一致。
- MathJax 节点文本与英文源逐字一致。
- 页面级横向溢出仍必须为 0；代码、表格、长公式只允许在自身容器内部滚动。

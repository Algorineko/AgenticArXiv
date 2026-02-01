# Agentic Arxiv
本项目实现了受Model Context Protocol（MCP）启发的工具系统，允许LLM Agent发现和使用外部工具，包括ArXiv论文检索等能力。

.env文件放置
```txt
LLM_BASE_URL=<base-url>
LLM_API_KEY=<token>
```

### PDFMathTranslate
```sh
export PDF_RAW_PATH=/home/dev/AgenticDemo/AgenticArxiv/output/pdf_raw 
wget -P $PDF_RAW_PATH https://arxiv.org/pdf/2601.22156v1.pdf
```
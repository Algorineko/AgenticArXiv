# Agentic Arxiv
本项目实现了受Model Context Protocol（MCP）启发的工具系统，允许LLM Agent发现和使用外部工具，包括ArXiv论文检索，PDF下载，PDF翻译等能力。

.env文件放置
```txt
LLM_BASE_URL=<base-url>
LLM_API_KEY=<token>
PDF_RAW_PATH=/home/dev/AgenticDemo/AgenticArxiv/output/pdf_raw
PDF_TRANSLATED_PATH=/home/dev/AgenticDemo/AgenticArxiv/output/pdf_translated
```

### PDFMathTranslate
```sh
# 下载 ArXiv 论文PDF
export PDF_RAW_PATH=/home/dev/AgenticDemo/AgenticArxiv/output/pdf_raw 
wget -P $PDF_RAW_PATH https://arxiv.org/pdf/2601.22156v1.pdf
```
```sh
# 进入GUI
pdf2zg -i
# 默认是英译中,-t为使用 CPU 核数
pdf2zh ./pdf-raw/3690624.3709231.pdf -s bing -o ./pdf-translated/ [-p 1] [--debug] [-t 4]
# case
pdf2zh /home/dev/AgenticDemo/AgenticArxiv/output/pdf_raw/2601.22156v1.pdf -s bing -o /home/dev/AgenticDemo/AgenticArxiv/output/pdf_translated -t 3
``` 

### FastAPI
```sh
# 启动FastAPI
cd /home/dev/AgenticDemo/AgenticArxiv
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
# 查看Swagger文档
http://127.0.0.1:8000/docs
```

### cURL测试
```sh
# 获取近期论文写入 session 短期记忆
curl -s -X POST "http://127.0.0.1:8000/arxiv/recent" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo1","aspect":"AI","days":7,"max_results":5}'
# 下载2号论文PDF
curl -s -X POST "http://127.0.0.1:8000/pdf/download" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo1","ref":2}'
# 翻译2号论文PDF
curl -s -X POST "http://127.0.0.1:8000/pdf/translate" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo1","ref":2,"force":false,"service":"bing","threads":4,"keep_dual":false}'
```


# AgenticArxiv/api/endpoints.py
from __future__ import annotations

import json
import queue
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from tools.tool_registry import registry
from models.schemas import Paper, TranslateTask
from models.store import store
from models.pdf_cache import PdfAsset
from models.translate_cache import TranslateAsset
from utils.logger import log

from services.runtime import event_bus, translate_runner


router = APIRouter()


class HealthResponse(BaseModel):
    status: str = "ok"


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


class ListToolsResponse(BaseModel):
    tools: List[ToolInfo]


class ExecuteToolRequest(BaseModel):
    name: str = Field(..., description="工具名称")
    args: Dict[str, Any] = Field(default_factory=dict, description="工具参数(JSON对象)")


class ExecuteToolResponse(BaseModel):
    name: str
    result: Any


class ArxivRecentRequest(BaseModel):
    session_id: str = Field(default="default", description="会话ID，用于短期记忆")
    max_results: int = Field(default=15, ge=1, le=100)
    aspect: str = Field(default="*", description="cs子领域，如 AI/LG/CL/... 或 *")
    days: int = Field(default=7, ge=1, le=30)
    output_path: Optional[str] = Field(
        default=None,
        description="可选：保存到指定文件路径；不传则用项目 output/recent_cs_papers.txt",
    )
    save_to_file: bool = Field(default=True, description="是否写入到文件")


class ArxivRecentResponse(BaseModel):
    session_id: str
    count: int
    papers: List[Paper]


class SessionPapersResponse(BaseModel):
    session_id: str
    papers: List[Paper]


class CreateTranslateTaskRequest(BaseModel):
    session_id: str = "default"
    ref: str | int | None = Field(
        default=None,
        description="论文引用: 1-based序号 或 arxiv id 或 title子串; 也支持 null 表示最近一次操作的论文",
    )
    force: bool = Field(default=False, description="是否强制重新翻译")
    service: str = Field(default="bing", description="翻译服务，如 bing/deepl/google")
    threads: int = Field(default=4, ge=1, le=32, description="线程数")
    keep_dual: bool = Field(
        default=False, description="是否保留双语 PDF（默认否，只保留中文）"
    )


class CreateTranslateTaskResponse(BaseModel):
    task: TranslateTask


class GetTaskResponse(BaseModel):
    task: TranslateTask


class AgentRunRequest(BaseModel):
    session_id: str = "default"
    task: str = Field(..., description="给Agent的任务描述")
    agent_model: Optional[str] = Field(default=None, description="可选：指定模型名")


class AgentRunResponse(BaseModel):
    task: str
    history: List[Dict[str, str]]
    final_observation: str


class DownloadPdfRequest(BaseModel):
    session_id: str = Field(default="default", description="会话ID，用于短期记忆")
    ref: str | int | None = Field(
        default=None,
        description="论文引用: 1-based序号 或 arxiv id 或 title子串; 也支持 null 表示最近一次操作的论文",
    )
    force: bool = Field(default=False, description="是否强制重新下载")


class DownloadPdfResponse(BaseModel):
    session_id: str
    paper_id: str
    pdf_url: str
    local_path: str
    status: str
    existed: bool
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None


class TranslatePdfRequest(BaseModel):
    session_id: str = Field(default="default", description="会话ID, 用于短期记忆")
    ref: str | int | None = Field(
        default=None,
        description="论文引用:1-based序号 或 arxiv id 或 title子串; 也支持 null 表示最近一次操作的论文",
    )
    force: bool = Field(default=False, description="是否强制重新翻译（覆盖本地 mono）")
    service: str = Field(default="bing", description="翻译服务，如 bing/deepl/google")
    threads: int = Field(
        default=4, ge=1, le=32, description="线程数（服务器 4 核可设 4）"
    )
    keep_dual: bool = Field(
        default=False, description="是否保留双语 PDF（默认否，只保留中文）"
    )


class TranslatePdfResponse(BaseModel):
    session_id: str
    paper_id: str
    input_pdf_path: str
    output_pdf_path: str
    status: str
    existed: bool
    service: str
    threads: int
    log_path: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str = Field(default="default")
    message: str = Field(..., description="用户对 Agent 的一句话/一个任务")
    agent_model: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    message: str
    reply: str
    history: List[Dict[str, str]]
    papers: List[Paper]
    pdf_assets: List[PdfAsset]
    translate_assets: List[TranslateAsset]
    tasks: List[TranslateTask] = Field(
        default_factory=list, description="该 session 的最近任务（可选）"
    )


class PdfAssetsResponse(BaseModel):
    assets: List[PdfAsset]


class TranslateAssetsResponse(BaseModel):
    assets: List[TranslateAsset]


# ---------------- SSE ----------------
def _sse_pack(event_json: str) -> str:
    """
    event_json 是 JSON 字符串，内部需含 type 字段：
      {"type":"task_succeeded", ...}
    """
    try:
        obj = json.loads(event_json)
        et = obj.get("type", "message")
    except Exception:
        et = "message"
    return f"event: {et}\ndata: {event_json}\n\n"


@router.get("/events")
def events(session_id: str = Query(default="default")):
    """
    SSE 订阅：用于推送翻译任务状态变化
    前端：EventSource(`/events?session_id=xxx`)
    """
    sid = session_id or "default"
    sub_id, q = event_bus.subscribe(sid)

    def gen():
        try:
            # 连接确认 + 可选：把当前任务快照发一份
            hello = json.dumps(
                {"type": "connected", "session_id": sid}, ensure_ascii=False
            )
            yield _sse_pack(hello)

            while True:
                try:
                    data = q.get(timeout=15)
                    yield _sse_pack(data)
                except queue.Empty:
                    # keep-alive（SSE comment 行）
                    yield ": ping\n\n"
        finally:
            event_bus.unsubscribe(sid, sub_id)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # Nginx 反代时建议关缓冲：X-Accel-Buffering: no
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


# ---------------- basic ----------------
@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/tools", response_model=ListToolsResponse)
def list_tools() -> ListToolsResponse:
    tools = registry.list_tools()
    return ListToolsResponse(tools=[ToolInfo(**t) for t in tools])


@router.post("/tools/execute", response_model=ExecuteToolResponse)
def execute_tool(req: ExecuteToolRequest) -> ExecuteToolResponse:
    try:
        result = registry.execute_tool(req.name, req.args)
        return ExecuteToolResponse(name=req.name, result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工具执行失败: {str(e)}")


@router.post("/arxiv/recent", response_model=ArxivRecentResponse)
def arxiv_recent(req: ArxivRecentRequest) -> ArxivRecentResponse:
    tool_name = "get_recently_submitted_cs_papers"

    args: Dict[str, Any] = {
        "max_results": req.max_results,
        "aspect": req.aspect,
        "days": req.days,
        "save_to_file": req.save_to_file,
    }
    if req.output_path is not None:
        args["output_path"] = req.output_path

    try:
        result = registry.execute_tool(tool_name, args)
        if not isinstance(result, list):
            raise RuntimeError(f"工具返回类型异常: {type(result)}")

        papers_obj = [Paper(**p) for p in result]
        store.set_last_papers(req.session_id, papers_obj)

        return ArxivRecentResponse(
            session_id=req.session_id,
            count=len(papers_obj),
            papers=papers_obj,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取论文失败: {str(e)}")


@router.get("/sessions/{session_id}/papers", response_model=SessionPapersResponse)
def get_session_papers(session_id: str) -> SessionPapersResponse:
    papers = store.get_last_papers(session_id)
    return SessionPapersResponse(session_id=session_id, papers=papers)


# ---------------- translate tasks (create -> auto-run) ----------------
@router.post("/translate/tasks", response_model=CreateTranslateTaskResponse)
def create_translate_task(
    req: CreateTranslateTaskRequest,
) -> CreateTranslateTaskResponse:
    try:
        # enqueue 会自行 resolve ref / last_active
        t = translate_runner.enqueue(
            session_id=req.session_id,
            ref=req.ref,
            force=req.force,
            service=req.service,
            threads=req.threads,
            keep_dual=req.keep_dual,
        )
        return CreateTranslateTaskResponse(task=t)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建翻译任务失败: {str(e)}")


@router.get("/translate/tasks/{task_id}", response_model=GetTaskResponse)
def get_translate_task(task_id: str) -> GetTaskResponse:
    t = store.get_task(task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return GetTaskResponse(task=t)


# ---------------- agent ----------------
@router.post("/agent/run", response_model=AgentRunResponse)
def run_agent(req: AgentRunRequest) -> AgentRunResponse:
    try:
        from utils.llm_client import get_env_llm_client
        from agents.agent_engine import ReActAgent

        llm_client = get_env_llm_client()
        agent = ReActAgent(llm_client)
        result = agent.run(
            task=req.task, agent_model=req.agent_model, session_id=req.session_id
        )
        return AgentRunResponse(**result)
    except Exception as e:
        log.error(f"Agent运行失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent运行失败: {str(e)}")


# ---------------- pdf download ----------------
@router.post("/pdf/download", response_model=DownloadPdfResponse)
def pdf_download(req: DownloadPdfRequest) -> DownloadPdfResponse:
    tool_name = "download_arxiv_pdf"
    try:
        result = registry.execute_tool(
            tool_name,
            {"session_id": req.session_id, "ref": req.ref, "force": req.force},
        )
        if not isinstance(result, dict):
            raise RuntimeError(f"工具返回类型异常: {type(result)}")
        return DownloadPdfResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载PDF失败: {str(e)}")


# ---------------- pdf translate (sync 保留) ----------------
@router.post("/pdf/translate", response_model=TranslatePdfResponse)
def pdf_translate(req: TranslatePdfRequest) -> TranslatePdfResponse:
    """
    保留原同步接口（可能耗时较长）。
    推荐前端改用 /pdf/translate/async + /events SSE
    """
    tool_name = "translate_arxiv_pdf"
    try:
        result = registry.execute_tool(
            tool_name,
            {
                "session_id": req.session_id,
                "ref": req.ref,
                "force": req.force,
                "service": req.service,
                "threads": req.threads,
                "keep_dual": req.keep_dual,
            },
        )
        if not isinstance(result, dict):
            raise RuntimeError(f"工具返回类型异常: {type(result)}")
        return TranslatePdfResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译PDF失败: {str(e)}")


@router.post("/pdf/translate/async", response_model=CreateTranslateTaskResponse)
def pdf_translate_async(req: TranslatePdfRequest) -> CreateTranslateTaskResponse:
    """
    新增：异步翻译接口
    - 立即返回 task
    - 任务进度/完成由 /events SSE 推送
    """
    try:
        t = translate_runner.enqueue(
            session_id=req.session_id,
            ref=req.ref,
            force=req.force,
            service=req.service,
            threads=req.threads,
            keep_dual=req.keep_dual,
        )
        return CreateTranslateTaskResponse(task=t)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建异步翻译任务失败: {str(e)}")


# ---------------- chat ----------------
@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        from utils.llm_client import get_env_llm_client
        from agents.agent_engine import ReActAgent

        llm_client = get_env_llm_client()
        agent = ReActAgent(llm_client)

        result = agent.run(
            task=req.message,
            agent_model=req.agent_model,
            session_id=req.session_id,
        )

        papers = store.get_last_papers(req.session_id)
        pdf_assets = sorted(
            store.pdf_cache.assets.values(), key=lambda x: x.updated_at, reverse=True
        )
        translate_assets = sorted(
            store.translate_cache.assets.values(),
            key=lambda x: x.updated_at,
            reverse=True,
        )
        tasks = store.list_tasks(session_id=req.session_id, limit=50)

        reply = ""
        for step in reversed(result.get("history", [])):
            if step.get("action") not in ("FINISH", "FORCE_STOP", "ERROR"):
                reply = step.get("observation", "")
                break
        reply = reply or result.get("final_observation", "")

        return ChatResponse(
            session_id=req.session_id,
            message=req.message,
            reply=reply,
            history=result.get("history", []),
            papers=papers,
            pdf_assets=list(pdf_assets),
            translate_assets=list(translate_assets),
            tasks=tasks,
        )

    except Exception as e:
        log.error(f"/chat 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"chat失败: {str(e)}")


@router.get("/pdf/assets", response_model=PdfAssetsResponse)
def list_pdf_assets() -> PdfAssetsResponse:
    assets = sorted(
        store.pdf_cache.assets.values(), key=lambda x: x.updated_at, reverse=True
    )
    return PdfAssetsResponse(assets=list(assets))


@router.get("/translate/assets", response_model=TranslateAssetsResponse)
def list_translate_assets() -> TranslateAssetsResponse:
    assets = sorted(
        store.translate_cache.assets.values(), key=lambda x: x.updated_at, reverse=True
    )
    return TranslateAssetsResponse(assets=list(assets))

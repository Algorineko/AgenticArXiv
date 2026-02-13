# AgenticArxiv/api/endpoints.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from tools.tool_registry import registry
from models.schemas import Paper, TranslateTask
from models.store import store
from models.pdf_cache import PdfAsset
from models.translate_cache import TranslateAsset
from utils.logger import log


router = APIRouter()


# -------------------------
# Pydantic 请求/响应模型
# -------------------------
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
    ref: str | int = Field(
        ..., description="论文引用：1-based序号 或 arxiv id 或 title子串"
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
    ref: str | int = Field(
        ..., description="论文引用：1-based序号 或 arxiv id 或 title子串"
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
    session_id: str = Field(default="default", description="会话ID，用于短期记忆")
    ref: str | int = Field(
        ..., description="论文引用:1-based序号 或 arxiv id 或 title子串"
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


class PdfAssetsResponse(BaseModel):
    assets: List[PdfAsset]


class TranslateAssetsResponse(BaseModel):
    assets: List[TranslateAsset]


# -------------------------
# 基础接口
# -------------------------
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


# -------------------------
# 针对 arxiv 工具的“更友好”接口
# -------------------------
@router.post("/arxiv/recent", response_model=ArxivRecentResponse)
def arxiv_recent(req: ArxivRecentRequest) -> ArxivRecentResponse:
    """
    获取最近days天内 cs.<aspect> 论文，并写入 session 的短期记忆（store.set_last_papers）
    """
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


# -------------------------
# 翻译任务：先把“创建任务/查任务”打通（翻译执行可后续接入 pdf2zh）
# -------------------------
@router.post("/translate/tasks", response_model=CreateTranslateTaskResponse)
def create_translate_task(
    req: CreateTranslateTaskRequest,
) -> CreateTranslateTaskResponse:
    paper = store.resolve_paper(req.session_id, req.ref)
    if paper is None:
        raise HTTPException(
            status_code=404,
            detail="未找到论文：请先调用 /arxiv/recent 写入 session 记忆，或检查 ref 是否正确",
        )

    t = store.create_translate_task(req.session_id, paper)
    return CreateTranslateTaskResponse(task=t)


@router.get("/translate/tasks/{task_id}", response_model=GetTaskResponse)
def get_translate_task(task_id: str) -> GetTaskResponse:
    t = store.get_task(task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return GetTaskResponse(task=t)


# -------------------------
# Agent 运行接口（可选）
# -------------------------
@router.post("/agent/run", response_model=AgentRunResponse)
def run_agent(req: AgentRunRequest) -> AgentRunResponse:
    """
    运行 ReActAgent（需要环境变量 LLM_API_KEY / LLM_BASE_URL）
    """
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


@router.post("/pdf/download", response_model=DownloadPdfResponse)
def pdf_download(req: DownloadPdfRequest) -> DownloadPdfResponse:
    """
    根据 session 的短期记忆 + ref 下载 PDF 到 output/pdf_raw，并维护 output/pdf_cache.json
    """
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


@router.post("/pdf/translate", response_model=TranslatePdfResponse)
def pdf_translate(req: TranslatePdfRequest) -> TranslatePdfResponse:
    """
    翻译 PDF 全文，默认只保留中文单语（mono）PDF：
      输出：output/pdf_translated/{paper_id}-mono.pdf
      同时维护：output/translate_cache.json
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

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    最小闭环对话接口：用户一句话 -> Agent 自己决定调用哪个 tool -> 返回回复 + 状态快照
    """
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

        # 状态快照：短期记忆 + 两份 cache
        papers = store.get_last_papers(req.session_id)
        pdf_assets = sorted(store.pdf_cache.assets.values(), key=lambda x: x.updated_at, reverse=True)
        translate_assets = sorted(store.translate_cache.assets.values(), key=lambda x: x.updated_at, reverse=True)

        # reply：用最后一步“有意义”的 observation（避免最后是“任务完成”）
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
        )

    except Exception as e:
        log.error(f"/chat 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"chat失败: {str(e)}")


@router.get("/pdf/assets", response_model=PdfAssetsResponse)
def list_pdf_assets() -> PdfAssetsResponse:
    assets = sorted(store.pdf_cache.assets.values(), key=lambda x: x.updated_at, reverse=True)
    return PdfAssetsResponse(assets=list(assets))


@router.get("/translate/assets", response_model=TranslateAssetsResponse)
def list_translate_assets() -> TranslateAssetsResponse:
    assets = sorted(store.translate_cache.assets.values(), key=lambda x: x.updated_at, reverse=True)
    return TranslateAssetsResponse(assets=list(assets))

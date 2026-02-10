# AgenticArxiv/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 确保工具被注册（side-effect import）
import tools.arxiv_tool  # noqa: F401
import tools.pdf_download_tool  # noqa: F401
import tools.pdf_translate_tool  # noqa: F401

from api.endpoints import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic Arxiv API",
        version="0.1.0",
        description="Expose ToolRegistry tools via FastAPI",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {"msg": "Agentic Arxiv API is running", "docs": "/docs"}

    app.include_router(api_router)
    return app


app = create_app()

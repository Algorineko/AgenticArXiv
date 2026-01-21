# AgenticArxiv/tools/arxiv_tool.py
import arxiv # type: ignore
from datetime import datetime, timezone, timedelta
from typing import List, Dict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.tool_registry import registry

cs_categories = {
    "*": "All Computer Science",  # 所有计算机科学领域
    "AI": "Artificial Intelligence",  # 人工智能
    "AR": "Hardware Architecture",  # 硬件架构
    "CC": "Computational Complexity",  # 计算复杂性
    "CE": "Computational Engineering, Finance, and Science",  # 计算工程、金融与科学
    "CG": "Computational Geometry",  # 计算几何
    "CL": "Computation and Language",  # 计算与语言
    "CR": "Cryptography and Security",  # 密码学与安全
    "CV": "Computer Vision and Pattern Recognition",  # 计算机视觉与模式识别
    "CY": "Computers and Society",  # 计算机与社会
    "DB": "Databases",  # 数据库
    "DC": "Distributed, Parallel, and Cluster Computing",  # 分布式、并行与集群计算
    "DL": "Digital Libraries",  # 数字图书馆
    "DM": "Discrete Mathematics",  # 离散数学
    "DS": "Data Structures and Algorithms",  # 数据结构与算法
    "ET": "Emerging Technologies",  # 新兴技术
    "FL": "Formal Languages and Automata Theory",  # 形式语言与自动机理论
    "GL": "General Literature",  # 一般文献
    "GR": "Graphics",  # 图形学
    "GT": "Computer Science and Game Theory",  # 计算机科学与博弈论
    "HC": "Human-Computer Interaction",  # 人机交互
    "IR": "Information Retrieval",  # 信息检索
    "IT": "Information Theory",  # 信息论
    "LG": "Machine Learning",  # 机器学习
    "LO": "Logic in Computer Science",  # 计算机科学中的逻辑
    "MA": "Multiagent Systems",  # 多智能体系统
    "MM": "Multimedia",  # 多媒体
    "MS": "Mathematical Software",  # 数学软件
    "NA": "Numerical Analysis",  # 数值分析
    "NE": "Neural and Evolutionary Computing",  # 神经与进化计算
    "NI": "Networking and Internet Architecture",  # 网络与互联网架构
    "OH": "Other Computer Science",  # 其他计算机科学
    "OS": "Operating Systems",  # 操作系统
    "PF": "Performance",  # 性能
    "PL": "Programming Languages",  # 编程语言
    "RO": "Robotics",  # 机器人学
    "SC": "Symbolic Computation",  # 符号计算
    "SD": "Sound",  # 音频处理
    "SE": "Software Engineering",  # 软件工程
    "SI": "Social and Information Networks",  # 社会与信息网络
    "SY": "Systems and Control",  # 系统与控制
}


def get_recently_submitted_cs_papers(
    max_results: int = 50, aspect: str = "*", days: int = 7
) -> List[Dict]:
    """
    获取最近 days 天内提交的 cs.<aspect> 论文列表

    Args:
        max_results: 最大返回结果数,默认50
        aspect: cs子领域, "*" 表示全部子领域，否则如 "LO" / "AI" 等
        days: 查询最近多少天的论文, 默认7天

    Returns:
        论文信息列表，每个论文包含标题、作者、摘要等信息
    """
    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=days)).strftime("%Y%m%d")
    end_date = now_utc.strftime("%Y%m%d")

    if aspect == "*":
        query = f"cat:cs.* AND submittedDate:[{start_date} TO {end_date}]"
    else:
        query = f"cat:cs.{aspect} AND submittedDate:[{start_date} TO {end_date}]"

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers: List[Dict] = []
    for result in client.results(search):
        paper_info = {
            "id": result.get_short_id(),
            "title": result.title,
            "authors": [author.name for author in result.authors],
            "summary": (result.summary[:200] + "...")
            if len(result.summary) > 200
            else result.summary,
            "published": result.published.strftime("%Y-%m-%d %H:%M:%S"),
            "updated": result.updated.strftime("%Y-%m-%d %H:%M:%S")
            if result.updated
            else None,
            "pdf_url": result.pdf_url,
            "primary_category": result.primary_category,
            "categories": result.categories,
            "comment": result.comment,
            "links": [link.href for link in result.links],
        }
        papers.append(paper_info)

    return papers


def format_papers_console(papers: List[Dict], top_authors: int = 3) -> str:
    if not papers:
        return "未获取到最近提交的论文\n"
    lines = []
    for i, paper in enumerate(papers, 1):
        lines.append(f"{i}. {paper['title']}")
        lines.append(f"   作者: {', '.join(paper['authors'][:top_authors])}")
        lines.append(f"   发布时间: {paper['published']}")
        lines.append(f"   PDF链接: {paper['pdf_url']}")
        lines.append(f"   注释: {paper.get('comment')}")
        lines.append(f"   摘要: {paper['summary']}")
        lines.append(f"   全部链接: {paper['links']}")
        lines.append("-" * 80)
    return "\n".join(lines)


# 定义参数模式 (JSON Schema)
ARXIV_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "max_results": {
            "type": "integer",
            "description": "最大返回结果数",
            "minimum": 1,
            "maximum": 100,
            "default": 50,
        },
        "aspect": {
            "type": "string",
            "description": "计算机科学子领域代码",
            "enum": list(cs_categories.keys()),
            "default": "*",
        },
        "days": {
            "type": "integer",
            "description": "查询最近多少天的论文",
            "minimum": 1,
            "maximum": 30,
            "default": 7,
        },
    },
    "required": [],
}

# 注册工具到全局注册表
registry.register_tool(
    name="get_recently_submitted_cs_papers",
    description="获取最近提交的计算机科学领域论文列表，支持按子领域筛选",
    parameter_schema=ARXIV_TOOL_SCHEMA,
    func=get_recently_submitted_cs_papers,
)

# 注册格式化工具
FORMAT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "papers": {
            "type": "array",
            "description": "论文信息列表",
            "items": {"type": "object"},
        },
        "top_authors": {
            "type": "integer",
            "description": "显示前几位作者",
            "minimum": 1,
            "default": 3,
        },
    },
    "required": ["papers"],
}

registry.register_tool(
    name="format_papers_console",
    description="格式化论文列表为控制台可读的文本格式",
    parameter_schema=FORMAT_TOOL_SCHEMA,
    func=format_papers_console,
)


if __name__ == "__main__":
    # 测试工具注册
    ASPECT = "CL"
    papers = get_recently_submitted_cs_papers(max_results=20, aspect=ASPECT)
    print(format_papers_console(papers))

    # 测试通过注册表调用
    print("\n=== 通过工具注册表调用 ===")
    result = registry.execute_tool(
        "get_recently_submitted_cs_papers",
        {"max_results": 5, "aspect": "AI", "days": 7},
    )
    print(f"获取到 {len(result)} 篇论文")

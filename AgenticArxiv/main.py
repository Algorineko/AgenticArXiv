# AgenticArxiv/main.py
import argparse

from tools.arxiv_tool import get_recently_submitted_cs_papers, format_papers_console
from utils.llm_client import get_env_llm_client
from config import settings


def test_arxiv(aspect: str, max_results: int) -> None:
    papers = get_recently_submitted_cs_papers(max_results=max_results, aspect=aspect)
    print(format_papers_console(papers))


def test_llm(prompt: str) -> None:
    client = get_env_llm_client()
    resp = client.chat_completions(
        model=settings.models.agent_model,  
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1000,
        stream=False,
    )
    # OpenAI-compatible 的常规字段：choices[0].message.content
    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    print(content or resp)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("arxiv", help="测试 ArXiv 检索")
    p1.add_argument("--aspect", default="LO", help='cs 子领域，如 LO/AI/LG，或 "*"')
    p1.add_argument("--max", type=int, default=20, help="最大结果数")

    p2 = sub.add_parser("llm", help="测试 LLM chat/completions")
    p2.add_argument("--prompt", default="你好，请介绍一下你自己。")

    args = parser.parse_args()

    if args.cmd == "arxiv":
        test_arxiv(aspect=args.aspect, max_results=args.max)
    elif args.cmd == "llm":
        test_llm(prompt=args.prompt)


if __name__ == "__main__":
    main()

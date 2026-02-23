# AgenticArxiv/agents/agent_engine.py
import json
import re
from typing import Dict, Any, Optional, Tuple
import sys
import os
from models.schemas import Paper
from models.store import store

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.llm_client import LLMClient
from tools.tool_registry import registry
from agents.context_manager import ContextManager
from agents.prompt_templates import get_react_prompt, format_tool_description
from utils.logger import log
from config import settings

from services.runtime import translate_runner


class ReActAgent:
    """基于ReAct模式的Agent引擎"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.context = ContextManager()
        self.max_iterations = 5
        self.session_id = "default"

        try:
            import tools.arxiv_tool  # noqa: F401
            import tools.pdf_download_tool  # noqa: F401
            import tools.pdf_translate_tool  # noqa: F401
            import tools.cache_status_tool  # noqa: F401

            log.info(f"已导入工具模块，注册了 {len(registry.list_tools())} 个工具")
        except ImportError as e:
            log.warning(f"导入工具模块失败: {e}")

    def parse_llm_response(self, response: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        log.debug(f"解析LLM响应: {response[:200]}...")

        thought_match = re.search(
            r"Thought:\s*(.*?)(?=\nAction:|$)", response, re.DOTALL
        )
        thought = thought_match.group(1).strip() if thought_match else "未提供思考过程"

        action_match = re.search(
            r"Action:\s*(.*?)(?=\nObservation:|$)", response, re.DOTALL
        )
        action_text = action_match.group(1).strip() if action_match else ""

        log.info(f"提取到的Action文本: {action_text}")

        if action_text.upper() == "FINISH":
            log.info("Agent决定结束任务")
            return thought, None

        try:
            json_match = re.search(r"({.*})", action_text, re.DOTALL)
            if json_match:
                action_json = json.loads(json_match.group(1))

                if isinstance(action_json, dict):
                    if "name" in action_json and "args" in action_json:
                        action_dict = {
                            "name": action_json["name"],
                            "args": action_json["args"],
                        }
                    else:
                        tool_names = [tool["name"] for tool in registry.list_tools()]
                        if tool_names:
                            action_dict = {"name": tool_names[0], "args": action_json}
                        else:
                            raise ValueError("没有可用的工具")

                    log.info(
                        f"解析成功: 工具={action_dict['name']}, 参数={action_dict['args']}"
                    )
                    return thought, action_dict
        except json.JSONDecodeError as e:
            log.error(f"JSON解析失败: {e}, Action文本: {action_text}")

        log.warning("尝试从文本中提取工具调用信息")

        tool_names = [tool["name"] for tool in registry.list_tools()]
        for tool_name in tool_names:
            if tool_name in action_text:
                args = {}
                if "max_results" in action_text:
                    max_match = re.search(r"max_results[=\s:]+(\d+)", action_text)
                    if max_match:
                        args["max_results"] = int(max_match.group(1))

                if "aspect" in action_text:
                    aspect_match = re.search(
                        r'aspect[=\s:]+["\']?([A-Z*]+)["\']?', action_text
                    )
                    if aspect_match:
                        args["aspect"] = aspect_match.group(1)

                if "days" in action_text:
                    days_match = re.search(r"days[=\s:]+(\d+)", action_text)
                    if days_match:
                        args["days"] = int(days_match.group(1))

                log.info(f"从文本提取: 工具={tool_name}, 参数={args}")
                return thought, {"name": tool_name, "args": args}

        log.error(f"无法解析Action: {action_text}")
        return thought, None

    def execute_action(self, action_dict: Dict[str, Any]) -> str:
        """执行动作并返回观察结果"""
        try:
            tool_name = action_dict["name"]
            args = action_dict.get("args", {}) or {}

            log.info(f"执行工具: {tool_name}, 参数: {args}")

            # 强制覆盖 session_id：只要工具参数里支持 session_id，就用当前会话 self.session_id
            try:
                tool = registry.get_tool(tool_name)
                props = (tool or {}).get("parameters", {}).get("properties", {})
                if isinstance(args, dict) and ("session_id" in props):
                    args["session_id"] = self.session_id
            except Exception:
                pass

            available_tools = [tool["name"] for tool in registry.list_tools()]
            if tool_name not in available_tools:
                available_tools_str = ", ".join(available_tools)
                return f"错误: 工具 '{tool_name}' 不存在。可用工具包括: {available_tools_str}"

            # --- 关键：翻译工具改为异步 enqueue（不阻塞 /chat） ---
            if tool_name == "translate_arxiv_pdf":
                # 兼容工具参数（ref/paper_id/pdf_url/input_pdf_path）
                t = translate_runner.enqueue(
                    session_id=self.session_id,
                    ref=args.get("ref", None),
                    force=bool(args.get("force", False)),
                    service=args.get("service") or settings.pdf2zh_service,
                    threads=int(args.get("threads") or settings.pdf2zh_threads),
                    keep_dual=bool(args.get("keep_dual", False)),
                    paper_id=args.get("paper_id"),
                    pdf_url=args.get("pdf_url"),
                    input_pdf_path=args.get("input_pdf_path"),
                )
                return (
                    f"已创建翻译任务 task_id={t.task_id}, paper_id={t.paper_id}，状态={t.status}。"
                    f"前端可订阅 SSE: /events?session_id={self.session_id}，"
                    f"任务完成后刷新 /translate/assets 或 /pdf/assets。"
                )

            # 其它工具仍同步执行
            result = registry.execute_tool(tool_name, args)

            # 加固：如果工具返回 paper_id，则同步写入 last_active_paper_id
            try:
                if isinstance(result, dict):
                    pid = result.get("paper_id")
                    if isinstance(pid, str) and pid.strip():
                        store.set_last_active_paper_id(self.session_id, pid.strip())
            except Exception:
                pass

            if tool_name == "get_recently_submitted_cs_papers":
                if isinstance(result, list):
                    if result:
                        papers_obj = [Paper(**p) for p in result]
                        store.set_last_papers(self.session_id, papers_obj)

                        papers_count = len(result)
                        paper_titles = [
                            paper.get("title", "无标题") for paper in result[:3]
                        ]
                        titles_str = "\n".join(
                            [f"  - {title}" for title in paper_titles]
                        )

                        if papers_count > 3:
                            return f"成功获取 {papers_count} 篇论文。示例论文:\n{titles_str}\n  ... 还有 {papers_count - 3} 篇论文"
                        else:
                            return f"成功获取 {papers_count} 篇论文:\n{titles_str}"
                    else:
                        return (
                            "未获取到任何论文记录，请尝试调整搜索参数（如增加天数范围）"
                        )
                else:
                    return f"工具返回结果格式异常: {type(result)}"

            elif tool_name == "format_papers_console":
                return "FINISH"

            if isinstance(result, list):
                return f"成功获取 {len(result)} 条记录"
            elif isinstance(result, str):
                return result[:1000] if len(result) > 1000 else result
            else:
                return str(result)[:1000]

        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            log.error(error_msg, exc_info=True)
            return error_msg

    def run(
        self, task: str, agent_model: str = None, session_id: str = "default"
    ) -> Dict[str, Any]:
        log.info(f"开始执行任务: {task}")
        self.session_id = session_id

        if agent_model is None:
            agent_model = settings.models.agent_model

        tools = registry.list_tools()
        tools_description = format_tool_description(tools)

        self.context.clear()

        for iteration in range(self.max_iterations):
            log.info(f"第 {iteration + 1} 次迭代")

            prompt = get_react_prompt(
                task=task,
                tools_description=tools_description,
                history=self.context.get_history_text(),
            )

            log.debug(f"发送给LLM的提示词:\n{prompt}")

            try:
                response = self.llm_client.chat_completions(
                    model=agent_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=1000,
                    stream=False,
                )

                content = (
                    response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                log.debug(f"LLM响应: {content}")

                thought, action_dict = self.parse_llm_response(content)

                log.info(f"Thought: {thought}")

                if action_dict is None:
                    log.info("任务完成")
                    self.context.add_step(thought, "FINISH", "任务完成")
                    break

                observation = self.execute_action(action_dict)
                log.info(f"Observation: {observation[:200]}...")

                self.context.add_step(
                    thought,
                    json.dumps(action_dict, ensure_ascii=False),
                    observation,
                )

                if iteration == self.max_iterations - 1:
                    log.warning("达到最大迭代次数，强制结束")
                    self.context.add_step("达到最大迭代次数", "FORCE_STOP", "迭代限制")
                    break

            except Exception as e:
                error_msg = f"LLM调用失败: {str(e)}"
                log.error(error_msg)
                self.context.add_step("LLM调用失败", "ERROR", error_msg)
                break

        result = {
            "task": task,
            "history": self.context.get_full_history(),
            "final_observation": self.context.history[-1].observation
            if self.context.history
            else "无执行结果",
        }

        log.info(f"任务执行完成，共 {len(self.context.history)} 步")
        log.info("-" * 80)
        return result

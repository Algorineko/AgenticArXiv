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


class ReActAgent:
    """基于ReAct模式的Agent引擎"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.context = ContextManager()
        self.max_iterations = 5  # 最大迭代次数
        self.session_id = "default"

        # 确保工具被注册 - 导入工具模块
        try:
            import tools.arxiv_tool  # noqa: F401
            import tools.pdf_download_tool  # noqa: F401
            import tools.pdf_translate_tool  # noqa: F401

            log.info(f"已导入工具模块，注册了 {len(registry.list_tools())} 个工具")
        except ImportError as e:
            log.warning(f"导入工具模块失败: {e}")

    def parse_llm_response(self, response: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        解析LLM的响应,提取Thought和Action

        Returns:
            Tuple[thought, action_dict]
            action_dict为None表示FINISH
        """
        log.debug(f"解析LLM响应: {response[:200]}...")

        # 提取Thought部分
        thought_match = re.search(
            r"Thought:\s*(.*?)(?=\nAction:|$)", response, re.DOTALL
        )
        thought = thought_match.group(1).strip() if thought_match else "未提供思考过程"

        # 提取Action部分
        action_match = re.search(
            r"Action:\s*(.*?)(?=\nObservation:|$)", response, re.DOTALL
        )
        action_text = action_match.group(1).strip() if action_match else ""

        log.info(f"提取到的Action文本: {action_text}")

        # 检查是否是FINISH
        if action_text.upper() == "FINISH":
            log.info("Agent决定结束任务")
            return thought, None

        # 尝试解析JSON格式的Action
        try:
            # 提取JSON部分
            json_match = re.search(r"({.*})", action_text, re.DOTALL)
            if json_match:
                action_json = json.loads(json_match.group(1))

                if isinstance(action_json, dict):
                    # 兼容两种格式：{"name": "...", "args": {...}} 或 直接是参数对象
                    if "name" in action_json and "args" in action_json:
                        action_dict = {
                            "name": action_json["name"],
                            "args": action_json["args"],
                        }
                    else:
                        # 假设这是args对象，需要指定工具名
                        # 这里简化处理，使用默认工具名
                        tool_names = [tool["name"] for tool in registry.list_tools()]
                        # 查找合适的工具（这里简化：使用第一个工具）
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
            # 尝试其他解析方式
            pass

        # 如果以上方法都失败，尝试从文本中提取
        log.warning("尝试从文本中提取工具调用信息")

        # 查找工具名
        tool_names = [tool["name"] for tool in registry.list_tools()]
        for tool_name in tool_names:
            if tool_name in action_text:
                # 尝试提取参数
                args = {}
                # 这里简化参数提取，实际项目中需要更复杂的解析
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

        # 如果无法解析，返回错误
        log.error(f"无法解析Action: {action_text}")
        return thought, None  # FINISH

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
                    args["session_id"] = (
                        self.session_id
                    )  # 覆盖 LLM 传的 default / 其它值
            except Exception:
                pass

            # 检查工具是否存在
            available_tools = [tool["name"] for tool in registry.list_tools()]
            if tool_name not in available_tools:
                # 提供更友好的错误信息，列出可用工具
                available_tools_str = ", ".join(available_tools)
                return f"错误: 工具 '{tool_name}' 不存在。可用工具包括: {available_tools_str}"

            # 执行工具
            result = registry.execute_tool(tool_name, args)

            # 根据不同的工具类型返回不同的结果
            if tool_name == "get_recently_submitted_cs_papers":
                if isinstance(result, list):
                    if result:
                        # 短期记忆
                        papers_obj = [Paper(**p) for p in result]
                        store.set_last_papers(self.session_id, papers_obj)
                        # 获取论文详细信息
                        papers_count = len(result)
                        paper_titles = [
                            paper.get("title", "无标题") for paper in result[:3]
                        ]  # 只显示前3篇
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
                # # 格式化工具返回字符串
                # if isinstance(result, str):
                #     # 如果结果太长，截断但保持完整性
                #     if len(result) > 2000:
                #         return result[:2000] + "\n...(结果过长，已截断)"
                #     return result
                # else:
                #     return f"格式化结果: {str(result)[:500]}"
                # 这是历史测试工具：不在前端展示长文本，直接返回 FINISH
                return "FINISH"

            # 默认处理
            if isinstance(result, list):
                return f"成功获取 {len(result)} 条记录"
            elif isinstance(result, str):
                return result[:1000] if len(result) > 1000 else result
            else:
                return str(result)[:1000]

        except Exception as e:
            error_msg = f"工具执行失败: {str(e)}"
            log.error(error_msg, exc_info=True)  # 记录完整异常信息
            return error_msg

    def run(
        self, task: str, agent_model: str = None, session_id: str = "default"
    ) -> Dict[str, Any]:
        """
        运行ReAct Agent

        Args:
            task: 任务描述
            agent_model: 使用的模型名称

        Returns:
            Dict包含执行结果和历史记录
        """
        log.info(f"开始执行任务: {task}")
        self.session_id = session_id

        if agent_model is None:
            agent_model = settings.models.agent_model

        # 获取可用工具
        tools = registry.list_tools()
        tools_description = format_tool_description(tools)

        # 清空历史
        self.context.clear()

        # ReAct循环
        for iteration in range(self.max_iterations):
            log.info(f"第 {iteration + 1} 次迭代")

            # 生成提示词
            prompt = get_react_prompt(
                task=task,
                tools_description=tools_description,
                history=self.context.get_history_text(),
            )

            log.debug(f"发送给LLM的提示词:\n{prompt}")

            # 调用LLM
            try:
                response = self.llm_client.chat_completions(
                    model=agent_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,  # 低温度以获得更确定的输出
                    max_tokens=1000,
                    stream=False,
                )

                # 提取响应内容
                content = (
                    response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                log.debug(f"LLM响应: {content}")

                # 解析响应
                thought, action_dict = self.parse_llm_response(content)

                # 记录Thought
                log.info(f"Thought: {thought}")

                # 检查是否结束
                if action_dict is None:
                    log.info("任务完成")
                    self.context.add_step(thought, "FINISH", "任务完成")
                    break

                # 执行Action
                observation = self.execute_action(action_dict)
                log.info(f"Observation: {observation[:100]}...")

                # 保存到上下文
                self.context.add_step(thought, json.dumps(action_dict), observation)

                # 检查是否达到最大迭代次数
                if iteration == self.max_iterations - 1:
                    log.warning("达到最大迭代次数，强制结束")
                    self.context.add_step("达到最大迭代次数", "FORCE_STOP", "迭代限制")
                    break

            except Exception as e:
                error_msg = f"LLM调用失败: {str(e)}"
                log.error(error_msg)
                self.context.add_step("LLM调用失败", "ERROR", error_msg)
                break

        # 返回结果
        result = {
            "task": task,
            "history": self.context.get_full_history(),
            "final_observation": self.context.history[-1].observation
            if self.context.history
            else "无执行结果",
        }

        log.info(f"任务执行完成，共 {len(self.context.history)} 步")
        log.info("-" * 50)
        return result

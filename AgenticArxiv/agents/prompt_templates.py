# AgenticArxiv/agents/prompt_templates.py

REACT_PROMPT_TEMPLATE = """你是一个AI研究助手,可以获取最新的arXiv计算机科学论文。你有以下工具可以使用：

{tools_description}

当前任务：{task}
请按照ReAct框架的格式思考和行动:
Thought: 分析当前情况和下一步需要做什么
Action: {{"name": "工具名称", "args": {{参数对象}}}}
Observation: 工具执行的结果
当你认为任务已经完成时，使用以下格式结束：
Thought: 任务已完成
Action: FINISH
注意：只能使用上面列出的工具。每次只能执行一个动作。
现在开始执行任务：
{history}
"""

def get_react_prompt(task: str, tools_description: str, history: str = "") -> str:
    """生成ReAct提示词"""
    return REACT_PROMPT_TEMPLATE.format(
        task=task,
        tools_description=tools_description,
        history=history
    )

def format_tool_description(tools) -> str:
    """格式化工具描述 - 更详细的版本"""
    if not tools:
        return "当前没有可用工具"
    
    descriptions = []
    for tool in tools:
        # 提取工具基本信息
        name = tool.get('name', '未知工具')
        desc = tool.get('description', '无描述')
        
        # 格式化参数信息
        params_info = ""
        if 'parameters' in tool and 'properties' in tool['parameters']:
            params = []
            for param_name, param_spec in tool['parameters']['properties'].items():
                param_type = param_spec.get('type', 'unknown')
                param_desc = param_spec.get('description', '')
                default_val = param_spec.get('default', '无默认值')
                
                # 如果有枚举值，显示可选值
                if 'enum' in param_spec:
                    enum_vals = param_spec['enum']
                    if len(enum_vals) > 5:
                        param_info = f"{param_name} ({param_type}): {param_desc}, 可选值: {enum_vals[:3]}...等{len(enum_vals)}个值"
                    else:
                        param_info = f"{param_name} ({param_type}): {param_desc}, 可选值: {enum_vals}"
                else:
                    param_info = f"{param_name} ({param_type}): {param_desc}, 默认: {default_val}"
                
                params.append(f"    {param_info}")
            
            if params:
                params_info = "\n" + "\n".join(params)
        
        # 构建完整描述
        tool_desc = f"- {name}: {desc}"
        if params_info:
            tool_desc += "\n  参数:"
            tool_desc += params_info
        
        descriptions.append(tool_desc)
    
    return "\n\n".join(descriptions)
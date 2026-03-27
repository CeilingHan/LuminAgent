from dataclasses import dataclass
from typing import List

@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    tags: List[str]

def get_all_skills():
    return [
        AgentSkill(
            id="BrowserUse",
            name="浏览器使用",
            description="使用浏览器访问网页、抓取内容",
            tags=["browser", "web", "tools"]
        ),
        AgentSkill(
            id="PythonExecute",
            name="Python代码执行",
            description="执行Python代码",
            tags=["python", "code", "execute"]
        ),
        AgentSkill(
            id="AskHuman",
            name="询问人类",
            description="向用户提问获取信息",
            tags=["human", "interaction"]
        ),
        AgentSkill(
            id="Planning",
            name="任务规划",
            description="生成任务执行计划",
            tags=["plan", "task"]
        )
    ]
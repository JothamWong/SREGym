import logging

from langgraph.constants import END
from langgraph.graph import START

from clients.stratus.configs import BaseAgentCfg
from clients.stratus.stratus_agent.base_agent import BaseAgent
from clients.stratus.tools.stratus_tool_node import StratusToolNode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RollbackAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tool_node = None
        self.thinking_prompt_inject_node = "pre_thinking_step"
        self.thinking_node = "thinking_step"
        self.tool_calling_prompt_inject_node = "pre_tool_calling_step"
        self.tool_calling_node = "tool_calling_step"

    def build_agent(self):
        self.tool_node = StratusToolNode(
            async_tools=self.async_tools,
            sync_tools=self.sync_tools,
        )

        # we add the node to the graph
        self.graph_builder.add_node("tool_agent", self.llm_tool_call_step)
        self.graph_builder.add_node("tool_node", self.tool_node)
        self.graph_builder.add_node("post_tool_hook", self.post_tool_hook)

        self.graph_builder.add_edge(START, "tool_agent")
        self.graph_builder.add_edge("tool_agent", "tool_node")
        self.graph_builder.add_edge("tool_node", "post_tool_hook")
        self.graph_builder.add_conditional_edges(
            "post_tool_hook",
            self.post_tool_route,
            {"next_round": "tool_agent", END: END},
        )

        self.graph = self.graph_builder.compile()

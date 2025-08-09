import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class LanggraphToolConfig(BaseModel):
    mcp_prometheus: str = Field(
        description="url for prometheus mcp server", default=f"{os.environ['MCP_SERVER_URL']}/prometheus/sse"
    )
    mcp_observability: str = Field(
        description="url for observability mcp server", default=f"{os.environ['MCP_SERVER_URL']}/jaeger/sse"
    )
    mcp_kubectl: str = Field(
        description="url for kubectl mcp server", default=f"{os.environ['MCP_SERVER_URL']}/kubectl_mcp_tools/sse"
    )
    mcp_submit: str = Field(
        description="url for submit mcp server", default=f"{os.environ['MCP_SERVER_URL']}/submit/sse"
    )

    min_len_to_sum: int = Field(
        description="Minimum length of text that will be summarized " "first before being input to the main agent.",
        default=200,
        ge=50,
    )

    use_summaries: bool = Field(description="Whether or not using summaries for too long texts.", default=True)

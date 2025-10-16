import asyncio
import subprocess
from typing import Annotated

from langchain_core.tools import InjectedToolCallId, tool

localization_tool_docstring = """
Use this tool to retrieve the UID of a specified resource.

    Args:
        resource_type (str): The type of the resource (e.g., 'pod', 'service', 'deployment').
        resource_name (str): The name of the resource.
    Returns:
        str: The UID of the specified resource.
"""


@tool(description=localization_tool_docstring)
async def get_resource_uid(
    resource_type: str,
    resource_name: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> str:
    cmd = [
        "kubectl",
        "get",
        resource_type,
        resource_name,
        "-o",
        "jsonpath={.metadata.uid}",
    ]
    proc = await asyncio.create_subprocess_exec(
        " ".join(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise Exception(f"Error retrieving UID: {stderr.decode().strip()}")
    uid = stdout.decode().strip()
    return uid if uid else "UID not found"

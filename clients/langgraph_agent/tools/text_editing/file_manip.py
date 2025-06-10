import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from clients.langgraph_agent.k8s_agent import State
from clients.langgraph_agent.state import State
from clients.langgraph_agent.tools.text_editing.windowed_file import WindowedFile

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@tool("open_file", description="open a file")
def open_file(
    state: Annotated[dict, InjectedState] = None, path: Optional[str] = None, line_number: Optional[str] = None
) -> str:
    # This tool should get both path and line number from the state
    # if the state does not have them, then it means no file has been opened yet.
    if path is None:
        print('Usage: open "<file>"')
        sys.exit(1)

    wf = WindowedFile(path=Path(path), exit_on_exception=False)

    if line_number is not None:
        try:
            line_num = int(line_number)
        except ValueError:
            print('Usage: open "<file>" [<line_number>]')
            print("Error: <line_number> must be a number")
            sys.exit(1)
        if line_num > wf.n_lines:
            print(f"Warning: <line_number> ({line_num}) is greater than the number of lines in the file ({wf.n_lines})")
            print(f"Warning: Setting <line_number> to {wf.n_lines}")
            line_num = wf.n_lines
        elif line_num < 1:
            print(f"Warning: <line_number> ({line_num}) is less than 1")
            print("Warning: Setting <line_number> to 1")
            line_num = 1
    else:
        # Default to middle of window if no line number provided
        line_num = wf.first_line

    wf.goto(line_num - 1, mode="top")
    wf.print_window()
    return wf.get_window_text(line_numbers=True, status_line=True, pre_post_line=True)


def update_file_vars_in_state(state: State, message: ToolMessage | AIMessage | HumanMessage):
    match message:
        case ToolMessage():
            if message.tool_call.function.name == "open_file":
                return State(
                    messages=state["messages"] + [message],
                    curr_file=message.tool_call.arguments["file"],
                    curr_line=state["curr_line"],
                )
            elif message.tool_call.function.name == "goto_line":
                return State(
                    messages=state["messages"] + [message],
                    curr_file=state["curr_file"],
                    curr_line=message.tool_call.arguments["line"],
                )
        case _:
            logger.info("Not found open_file or goto_line in message: %s", message)

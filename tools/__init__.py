from tools.registry import ToolRegistry
from tools.file_io import READ_FILE, WRITE_FILE, LIST_FILES, set_workspace
from tools.shell import RUN_SHELL
from tools.messaging import SEND_MESSAGE, READ_MESSAGES
from tools.task_management import CREATE_TASK, UPDATE_TASK, LIST_TASKS
from tools.feedback import SUBMIT_FEEDBACK, LIST_FEEDBACK, UPDATE_FEEDBACK_STATUS
from workspace.shared import SharedWorkspace


def create_tool_registry(workspace: SharedWorkspace) -> ToolRegistry:
    set_workspace(workspace)

    registry = ToolRegistry()
    for tool_def in [
        READ_FILE,
        WRITE_FILE,
        LIST_FILES,
        RUN_SHELL,
        SEND_MESSAGE,
        READ_MESSAGES,
        CREATE_TASK,
        UPDATE_TASK,
        LIST_TASKS,
        SUBMIT_FEEDBACK,
        LIST_FEEDBACK,
        UPDATE_FEEDBACK_STATUS,
    ]:
        registry.register(tool_def)
    return registry

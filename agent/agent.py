import json
import platform
import re

import psutil

import agent.actions
from agent import tools
from agent.actions import ACTIONS_PROMPT, EXECUTE_ACTION, Actions
from agent.consent import ask_data_send_consent
from agent.prompts import SYSTEM_PROMPT

from llm_api import LlmApi, types_request, types_tools
import settings
from text import print_in_color, Color, truncate_string


class Agent:
    def __init__(
        self, name: str, system_prompt: str = SYSTEM_PROMPT, is_planner: bool = False
    ):
        self.api: LlmApi = settings.LLM_API
        self.chat_history: list[types_request.Message] = []
        self.name = name

        self.is_planner = is_planner
        initial_prompts = [
            system_prompt,
            ACTIONS_PROMPT,
        ]
        if is_planner:
            initial_prompts.append(EXECUTE_ACTION)
        self.add_initial_prompts(initial_prompts)

        self.start_greeting = "Hello! How can I help you today?"
        self.add_action_to_chat_history(
            action={"action": "COMMUNICATE", "content": self.start_greeting},
            role="assistant",
            name=self.name,
        )

        self.tools = tools.tools
        self.tools_string = (
            f"Functions available to you:\n{json.dumps(self.tools, indent=2)}"
        )
        self.tools_message = self._create_message(self.tools_string, role="system")

    def get_response(
        self,
        content: str,
        role: types_request.MessageRole = "user",
        asker_name: str = "User",
        allow_tools: bool = True,
        tag: str | None = "AGENT",
    ) -> str:
        self.add_to_chat_history(content=content, role=role, name=asker_name)

        while True:
            # Include tool descriptions if allowed
            _api_messages = (
                self.chat_history + [self.tools_message]
                if allow_tools
                else self.chat_history
            )

            response: str = self.api.response_from_messages(_api_messages, tag=tag)

            response_stripped = self.strip_text_outside_curly_braces(response)
            if response != response_stripped:
                print_in_color("Had to strip extra content outside {}", Color.YELLOW)
                self.add_to_chat_history(
                    "Your response contained text that wasn't valid JSON. I stripped the extra text for now."
                    " In the future, please respond ONLY JSON.",
                    role="user",
                    name="Response parser",
                )

            try:
                response_parsed = json.loads(response_stripped, strict=False)
            except json.decoder.JSONDecodeError as e:
                print_in_color(f"Error parsing response: {response}\n{e}", Color.RED)
                self.add_to_chat_history(
                    content="Your response threw a JSONDecodeError - please try again",
                    role="user",
                    name="Response parser",
                )
                continue

            self.add_to_chat_history(content=response, role="assistant", name=self.name)

            response_action = response_parsed.get("action")
            if response_action not in Actions.__members__:
                print_in_color(f"INVALID ACTION: {response_action}", Color.RED)
                self.add_to_chat_history(
                    content=f"INVALID ACTION: {response_action}",
                    role="user",
                    name="Response parser",
                )
                continue

            if response_action == Actions.PLAN.name:
                print(f"PLAN")
                print(f"Main goal: {response_parsed.get('main_goal')}")
                print(f"Steps:\n{response_parsed.get('steps')}")
                self.delete_old_plans()
                self.add_to_chat_history(
                    content="You've updated your plan, good! What's next?",
                    role="user",
                    name="Response parser",
                )
                continue

            if response_action == Actions.RUN_FUNCTION.name:
                print(f"RUN_FUNCTION")
                self.handle_tool_call(types_tools.ToolCall(**response_parsed))
                self.add_to_chat_history(
                    content="You've ran a function. You should PLAN next.",
                    role="user",
                    name="Response parser",
                )
                continue

            if response_action == Actions.EXECUTE.name:
                print(response_action)
                self.spawn_agent_and_execute(
                    name=response_parsed["name"],
                    instructions=response_parsed["instructions"],
                )
                continue

            if response_action == Actions.COMMUNICATE.name:
                print(f"COMMUNICATE")
                return response_parsed.get("content", "(NO CONTENT)")

        return self.handle_string_response(response)

    def strip_text_outside_curly_braces(self, text: str) -> str:
        # Matches everything from the first { to the last } including nested ones
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)
        return ""  # Return an empty string if no outermost braces are found

    def add_action_to_chat_history(
        self,
        action: dict[agent.actions.Actions.__members__, str | dict],
        role: types_request.MessageRole,
        name: str | None = None,
    ):
        content = json.dumps(action, indent=2)
        self.add_to_chat_history(content=content, role=role, name=name)

    def add_to_chat_history(
        self,
        content: str | None = None,
        name: str | None = None,
        role: types_request.MessageRole | None = None,
        message: types_request.Message | None = None,
    ):
        if (content is None or role is None) and message is None:
            raise ValueError("Either content and role or message must be provided")

        if message is None:
            message = self._create_message(content=content, role=role, name=name)

        self._add_or_merge_message(message)

    def delete_old_plans(self):
        first = True
        for message in reversed(self.chat_history):
            content = message["content"]
            try:
                content_parsed = json.loads(content, strict=False)
            except json.JSONDecodeError:
                # Not an action - maybe just a string
                continue

            if first and content_parsed.get("action") == Actions.PLAN.name:
                first = False
                continue

            if content_parsed.get("action") == Actions.PLAN.name:
                self.chat_history.remove(message)

    def _add_or_merge_message(self, message: types_request.Message):
        content_truncated = truncate_string(
            message.get("content").replace("\n", " "), 100
        )
        print_in_color(
            f"{message.get('name', '')} ({message.get('role')}): {content_truncated}",
            Color.LIGHTBLACK_EX,
        )

        if len(self.chat_history) == 0:
            self.chat_history.append(message)
            return

        roles_to_merge = ("user",)
        latest_message = self.chat_history[-1]
        if (
            message["role"] in roles_to_merge
            and message["role"] == latest_message["role"]
        ):
            print_in_color(f"[Merging disabled for now]", Color.LIGHTBLACK_EX)
            self.chat_history.append(message)
            return

            print(
                f"Duplicate roles \"{message['role']}\" detected, merging messages..."
            )
            latest_message["content"] = (
                f"{latest_message['content']}\n{message['content']}"
            )
            return
        self.chat_history.append(message)

    def handle_tool_call(self, tool_call: types_tools.ToolCall):
        tool_result = (
            f"FUNCTION CALLER: Output and exit code for your function call:\n"
            f"---\n"
            f"{self.run_tool(tool_call)}\n"
            f"---"
        )
        self.add_to_chat_history(
            content=tool_result, role="user", name="Function caller"
        )

    def handle_string_response(self, response: str) -> str:
        self.add_to_chat_history(content=response, role="assistant", name=self.name)
        return response

    def run_tool(self, tool_call: types_tools.ToolCall) -> str:
        try:
            tool_function = tools.TOOL_FUNCTIONS[tool_call["function"]]
            return tool_function(**tool_call["parameters"])
        except KeyError:
            message = f"Function {tool_call['function']} not found"
            print_in_color(message, color=Color.YELLOW)
            return message
        except Exception as e:
            message = f"Error running function {tool_call['function']}: {e}"
            print_in_color(message, color=Color.RED)
            return message

    @ask_data_send_consent
    def gather_system_info(self) -> dict:
        system_info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "ram": str(round(psutil.virtual_memory().total / (1024.0**3))) + " GB",
        }
        return system_info

    def _create_message(
        self, content: str, role: types_request.MessageRole, name: str | None = None
    ) -> types_request.Message:
        message = types_request.Message(content=content, role=role)
        if name is not None:
            message["name"] = name
        return message

    def add_initial_prompts(self, prompts: list[str]):
        for prompt in prompts:
            self.add_to_chat_history(content=prompt, role="system")

    def spawn_agent_and_execute(self, name: str, instructions: str):
        """Spawn an agent to fulfill a task. Exits this function when the task is complete."""
        child = Agent(name=name, system_prompt=instructions, is_planner=False)
        self.add_to_chat_history(
            f"Spawned an agent named {name}", role="user", name="Response parser"
        )
        self.add_to_chat_history(
            f"CHILD AGENT COMMUNICATION SESSION ACTIVE. DURING THIS SESSION, ALL [COMMUNICATE] CALLS WILL BE DIRECTED TO THE CHILD AGENT.",
            role="system",
        )
        parent_communication = "Please execute your task. Tell me when you are done."
        while True:
            child_communication = child.get_response(
                parent_communication, asker_name=self.name, tag="CHILD"
            )
            print(f"{name}: {child_communication}")
            task_done = child.get_response(
                "Is your task done? Answer with COMMUNICATE, yes/no only.",
                asker_name=self.name,
                tag="CHILD",
            )
            if "yes" in task_done.lower():
                self.add_to_chat_history(child_communication, role="user", name=name)
                self.add_to_chat_history("My task is done.", role="user", name=name)
                break
            parent_communication = self.get_response(
                child_communication, asker_name=name
            )
            print(f"{self.name}: {parent_communication}")
            input("Press ENTER to continue")

        self.add_to_chat_history(
            f"CHILD AGENT COMMUNICATION SESSION ENDED. [COMMUNICATE] CALLS ARE ONCE MORE DIRECTED TO THE USER.",
            role="system",
        )

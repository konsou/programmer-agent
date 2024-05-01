from typing import Callable, Any

from agent.actions.types import Actions, ActionResponse
from text import print_in_color, Color

ActionHandler = Callable[[Any], str]
ActionHandlers = dict[Actions.__members__, ActionHandler]


def handle_action(
    action: Actions.__members__,
    data: Any,
    handlers: ActionHandlers,
) -> str:
    return handlers[action](data)


def handle_action_from_response(
    response: ActionResponse, handlers: ActionHandlers
) -> str:
    response_action = response.get("action")
    if response_action not in Actions.__members__:
        print_in_color(
            f"handle_action_from_response: {response_action} is not valid", Color.YELLOW
        )
        response_action = Actions.INVALID.name
    return handle_action(response_action, response, handlers)

# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
from pathlib import Path

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.app_utils.services import get_memory_service


def _resolve_reasoning_engine_resource() -> str:
    if resource := os.environ.get("REASONING_ENGINE_RESOURCE"):
        return resource
    meta = Path(__file__).parent.parent / "deployment_metadata.json"
    try:
        return json.loads(meta.read_text()).get("remote_agent_runtime_id", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


REASONING_ENGINE_RESOURCE = _resolve_reasoning_engine_resource()


MODEL = "gemini-3.7-flash"


async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


from app.app_utils.topic_guard import topic_guard_callback
from app.app_utils.firestore_tools import (
    add_or_update_motorcycle_rental,
    get_motorcycle_rental,
    list_motorcycle_rentals,
)
from app.app_utils.image_tools import generate_domain_item_image
from app.app_utils.rag_tools import consult_travel_instructions
from app.app_utils.travel_tools import (
    calculate_trip_budget,
    generate_destination_image,
    get_scenic_route_highlights,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a travel planning AI assistant for US road trips and motorcycle routes "
        "(Utah Scenic Byway 12, Zion, Bryce Canyon, Grand Canyon). "
        "Standard trip duration is 7 days unless specified otherwise. "
        "\n\n"
        "IMPORTANT: You must ONLY answer from the data your tools return. "
        "Do not use your training knowledge to answer any question. "
        "If none of your tools can supply the answer, respond: "
        "'I don't have that information in this system.' "
        "\n\n"
        "Your tools and when to use them:\n"
        "- consult_travel_instructions: speed limits, travel hours, rules, guidelines — call this FIRST for any factual travel question\n"
        "- list_motorcycle_rentals / get_motorcycle_rental / add_or_update_motorcycle_rental: rental inventory and updates\n"
        "- calculate_trip_budget: itemized cost breakdowns (call with days, daily_rental_rate, total_miles)\n"
        "- get_scenic_route_highlights: route mileage, waypoints, difficulty for known routes\n"
        "- generate_destination_image: generate a scenic postcard image for an itinerary stop\n"
        "- generate_domain_item_image: photo-realistic image of a motorcycle, landmark, or travel item\n"
        "- PreloadMemoryTool: call this at the start of every session to recall the user's stated preferences, "
        "budget, and riding experience from past conversations.\n"
    ),
    code_executor=AgentEngineSandboxCodeExecutor(
        agent_engine_resource_name=REASONING_ENGINE_RESOURCE
    ) if REASONING_ENGINE_RESOURCE else None,
    tools=[
        generate_domain_item_image,
        consult_travel_instructions,
        list_motorcycle_rentals,
        get_motorcycle_rental,
        add_or_update_motorcycle_rental,
        calculate_trip_budget,
        get_scenic_route_highlights,
        generate_destination_image,
        PreloadMemoryTool(),
    ],
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
    memory_service=get_memory_service(),
)

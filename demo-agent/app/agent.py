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

import datetime
import json
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

import google.auth
from google import genai
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory.vertex_ai_memory_bank_service import (
    VertexAiMemoryBankService,
)
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.load_memory_tool import LoadMemoryTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from .a2ui_utils import a2ui_callback






from google.cloud import firestore, storage
from google.genai import types

# HARDCODED project ID and bucket name for Agent Platform compatibility
FIRESTORE_PROJECT = "qwiklabs-gcp-01-ffa5389289dd"
GCS_BUCKET_NAME = "smart-pantry-assets-ffa538"



def get_firestore_client():
    """Returns a Firestore client configured with hardcoded project ID and datastore scope."""
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/datastore"]
    )
    return firestore.Client(project=FIRESTORE_PROJECT, credentials=creds)


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


def get_pantry_items(category: str = "") -> str:
    """Reads pantry items from the Firestore collection.

    Args:
        category: Optional category filter (e.g., 'Grains', 'Canned Goods', 'Produce', 'Dairy').

    Returns:
        A formatted list of pantry items with quantity, unit, and expiration date.
    """
    try:
        db = get_firestore_client()
        collection_ref = db.collection("pantry_items")
        if category:
            docs = collection_ref.where("category", "==", category).stream()
        else:
            docs = collection_ref.stream()

        items = []
        for doc in docs:
            data = doc.to_dict()
            items.append(
                f"- {data.get('name')} ({data.get('category')}): {data.get('quantity')} {data.get('unit')} [Expires: {data.get('expiration_date', 'N/A')}]"
            )

        if not items:
            return "No pantry items found matching criteria."
        return "Pantry Items:\n" + "\n".join(items)
    except Exception as e:
        return f"Error fetching pantry items: {str(e)}"


def add_pantry_item(
    item_id: str,
    name: str,
    category: str,
    quantity: float,
    unit: str,
    expiration_date: str = "",
) -> str:
    """Adds or updates a pantry item in the Firestore collection.

    Args:
        item_id: Unique identifier for the item (e.g., 'pasta-spaghetti', 'milk-whole').
        name: Display name of the pantry item (e.g., 'Spaghetti', 'Whole Milk').
        category: Category (e.g., 'Grains', 'Dairy', 'Produce', 'Canned Goods').
        quantity: Numerical quantity available.
        unit: Unit of measurement (e.g., 'grams', 'liters', 'cans', 'heads').
        expiration_date: Optional expiration date string (YYYY-MM-DD).

    Returns:
        Confirmation message.
    """
    try:
        db = get_firestore_client()
        item_data = {
            "id": item_id,
            "name": name,
            "category": category,
            "quantity": quantity,
            "unit": unit,
            "expiration_date": expiration_date,
        }
        db.collection("pantry_items").document(item_id).set(item_data)
        return f"Successfully added/updated pantry item '{name}' ({item_id}) in Firestore."
    except Exception as e:
        return f"Error adding pantry item: {str(e)}"


def check_expiring_items(days_threshold: int = 30) -> str:
    """Checks Firestore for pantry items expiring within the specified number of days.

    Args:
        days_threshold: Number of days ahead to check for expiring items (default 30).

    Returns:
        A list of items that will expire within the given timeframe.
    """
    try:
        db = get_firestore_client()
        docs = db.collection("pantry_items").stream()
        now = datetime.date.today()
        cutoff = now + datetime.timedelta(days=days_threshold)

        expiring = []
        for doc in docs:
            data = doc.to_dict()
            exp_str = data.get("expiration_date")
            if exp_str:
                try:
                    exp_date = datetime.datetime.strptime(
                        exp_str, "%Y-%m-%d"
                    ).date()
                    if now <= exp_date <= cutoff:
                        expiring.append(
                            f"- {data.get('name')} ({data.get('quantity')} {data.get('unit')}): Expires on {exp_str}"
                        )
                except ValueError:
                    continue

        if not expiring:
            return f"No items found expiring within the next {days_threshold} days."
        return f"Items expiring within the next {days_threshold} days:\n" + "\n".join(
            expiring
        )
    except Exception as e:
        return f"Error checking expiring items: {str(e)}"


def search_recipes(query: str) -> str:
    """Searches for real online recipes matching a keyword or ingredient via TheMealDB API.

    Args:
        query: Recipe title or primary ingredient (e.g., 'spaghetti', 'chicken', 'pasta').

    Returns:
        A list of matching recipe titles, categories, cuisines, and instructions.
    """
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={encoded_query}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        meals = data.get("meals")
        if not meals:
            return f"No recipes found for '{query}'."

        results = []
        for meal in meals[:3]:  # Top 3 matching recipes
            name = meal.get("strMeal")
            category = meal.get("strCategory")
            area = meal.get("strArea")
            instructions = (meal.get("strInstructions") or "")[:200] + "..."
            thumb = meal.get("strMealThumb", "")
            results.append(
                f"- **{name}** ({category} | {area} cuisine)\n  Preview: {instructions}\n  Image: {thumb}"
            )

        return "\n\n".join(results)
    except Exception as e:
        return f"Error fetching recipes: {str(e)}"


def geocode_address(address: str) -> str:
    """Converts a street address into geographic coordinates (latitude and longitude) using Google Geocoding API.

    Args:
        address: The location or address string (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        Formatted location details with address and lat/lng coordinates.
    """
    try:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

        encoded = urllib.parse.quote(address)
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded}&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = data.get("results", [])
        if not results:
            return f"No geocoding results found for address: '{address}'."

        first = results[0]
        formatted_address = first.get("formatted_address")
        location = first.get("geometry", {}).get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        return f"Address: {formatted_address}\nLocation: ({lat}, {lng})"
    except Exception as e:
        return f"Error geocoding address: {str(e)}"


def find_nearby_places(address: str, place_type: str = "grocery_store") -> str:
    """Finds nearby places (e.g. grocery stores, supermarkets) near a given address using Google Places API (New).

    Args:
        address: The center address or city to search near (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA').
        place_type: Type of place to search for (e.g., 'grocery_store', 'supermarket', 'bakery').

    Returns:
        A list of nearby places with name, address, and location coordinates.
    """
    try:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."

        # Step 1: Geocode address to get center coordinates
        encoded_addr = urllib.parse.quote(address)
        geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_addr}&key={api_key}"
        with urllib.request.urlopen(geo_url, timeout=5) as response:
            geo_data = json.loads(response.read().decode("utf-8"))

        geo_results = geo_data.get("results", [])
        if not geo_results:
            return f"Could not geocode address: '{address}'."

        loc = geo_results[0]["geometry"]["location"]
        lat, lng = loc["lat"], loc["lng"]

        # Step 2: Query Places API (New) searchNearby REST endpoint
        places_url = "https://places.googleapis.com/v1/places:searchNearby"
        body = json.dumps(
            {
                "includedTypes": [place_type],
                "maxResultCount": 5,
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": 5000.0,
                    }
                },
            }
        ).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        }

        req = urllib.request.Request(
            places_url, data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            places_data = json.loads(response.read().decode("utf-8"))

        places = places_data.get("places", [])
        if not places:
            return f"No nearby {place_type} found near '{address}'."

        formatted_places = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "Unknown")
            addr = p.get("formattedAddress", "N/A")
            ploc = p.get("location", {})
            plat, plng = ploc.get("latitude"), ploc.get("longitude")
            formatted_places.append(
                f"- **{display_name}**\n  Address: {addr}\n  Location: ({plat}, {plng})"
            )

        return f"Nearby {place_type} places near '{address}':\n\n" + "\n\n".join(
            formatted_places
        )
    except Exception as e:
        return f"Error finding nearby places: {str(e)}"


def generate_recipe_image(prompt: str, tool_context: ToolContext) -> str:
    """Generates an image for a dish/recipe using gemini-3.1-flash-lite-image in the global region.
    Saves the image as a Playground artifact and uploads bytes directly to Cloud Storage.

    Args:
        prompt: Description of the food or dish image to generate (e.g., 'Spaghetti Bolognese with fresh basil').

    Returns:
        Public HTTPS URL of the uploaded image in Cloud Storage.
    """
    try:
        # 1. Generate image using gemini-3.1-flash-lite-image model in global region
        client = genai.Client(
            vertexai=True, project=FIRESTORE_PROJECT, location="global"
        )
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"High quality food photography of: {prompt}",
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            return "Error: Image generation returned no content."

        part = response.candidates[0].content.parts[0]
        if not part.inline_data or not part.inline_data.data:
            return "Error: Image response missing inline data."

        image_bytes = part.inline_data.data
        mime_type = part.inline_data.mime_type or "image/jpeg"

        # Unique filename
        safe_name = "".join(
            c if c.isalnum() else "_" for c in prompt[:25]
        ).strip("_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recipe_{safe_name}_{timestamp}.jpg"

        # 2. Save artifact for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(
            data=image_bytes, mime_type=mime_type
        )
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 3. Upload image bytes to public Cloud Storage bucket
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/devstorage.full_control"]
        )
        storage_client = storage.Client(
            project=FIRESTORE_PROJECT, credentials=creds
        )
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = (
            f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        )
        return f"Successfully generated image!\nPublic GCS URL: {public_url}"
    except Exception as e:
        return f"Error generating image: {str(e)}"


def generate_recipe_video(prompt: str, tool_context: ToolContext) -> str:
    """Generates a short video for a dish or recipe using gemini-omni-flash-preview in the global region.
    Saves the video as a Playground artifact and uploads video bytes directly to Cloud Storage.

    Args:
        prompt: Description of the food preparation or dish video to generate (e.g., 'Preparing a fresh garden salad').

    Returns:
        Public HTTPS URL of the uploaded video in Cloud Storage.
    """
    try:
        # 1. Generate video using gemini-omni-flash-preview model via Interactions API in global region
        client = genai.Client(
            vertexai=True, project=FIRESTORE_PROJECT, location="global"
        )
        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=f"Short video showing food preparation: {prompt}",
        )

        video_bytes = None
        mime_type = "video/mp4"

        if hasattr(interaction, "steps") and interaction.steps:
            for step in interaction.steps:
                if hasattr(step, "content") and step.content:
                    for item in step.content:
                        data = getattr(item, "data", None)
                        if data:
                            if isinstance(data, str):
                                import base64

                                try:
                                    video_bytes = base64.b64decode(data)
                                except Exception:
                                    video_bytes = data.encode("utf-8")
                            else:
                                video_bytes = data
                            if hasattr(item, "mime_type") and item.mime_type:
                                mime_type = item.mime_type
                            break

        if not video_bytes:
            return "Error: Video generation returned no video content."

        # Unique filename
        safe_name = "".join(
            c if c.isalnum() else "_" for c in prompt[:25]
        ).strip("_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recipe_{safe_name}_{timestamp}.mp4"

        # 2. Save artifact for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(
            data=video_bytes, mime_type=mime_type
        )
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 3. Upload video bytes to public Cloud Storage bucket
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/devstorage.full_control"]
        )
        storage_client = storage.Client(
            project=FIRESTORE_PROJECT, credentials=creds
        )
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = (
            f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        )
        return f"Successfully generated video!\nPublic GCS URL: {public_url}"
    except Exception as e:
        return f"Error generating video: {str(e)}"


# Configure AgentEngineSandboxCodeExecutor reading from deployment_metadata.json if present
metadata_path = os.path.join(
    os.path.dirname(__file__), "..", "deployment_metadata.json"
)
agent_engine_res = None
if os.path.exists(metadata_path):
    try:
        with open(metadata_path, "r") as f:
            meta = json.load(f)
            val = meta.get("remote_agent_runtime_id")
            if val and val != "None":
                agent_engine_res = val
    except Exception:
        pass

if agent_engine_res:
    code_executor = AgentEngineSandboxCodeExecutor(
        agent_engine_resource_name=agent_engine_res
    )
else:
    code_executor = AgentEngineSandboxCodeExecutor()

# Extract Agent Engine ID for Memory Bank service
MEMORY_ENGINE_ID = "7830277060567236608"
if agent_engine_res:
    MEMORY_ENGINE_ID = agent_engine_res.split("/")[-1]

memory_service = VertexAiMemoryBankService(
    project=FIRESTORE_PROJECT,
    location="us-central1",
    agent_engine_id=MEMORY_ENGINE_ID,
)


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description="You are a Smart Pantry & Recipe Concierge. You help users manage their pantry inventory, track expiration dates, search real online recipes, geocode locations, find nearby grocery stores, generate visual food preview images, safely execute Python code, and remember user preferences over time.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects.\n\n"
        "MEMORY & ALLERGY MANAGEMENT:\n"
        "1. All user food allergies, intolerances, and dietary restrictions (e.g., peanuts, tree nuts, shellfish, gluten, dairy, eggs, soy) MUST be remembered in memory across sessions.\n"
        "2. Whenever a user states or mentions a food allergy or dietary restriction, record and save it in memory immediately.\n"
        "3. Before suggesting recipes, planning meals, or recommending pantry items, use memory tools to recall all stored user allergies.\n"
        "4. STRICT SAFETY RULE: Filter out and NEVER recommend any recipe or ingredient containing items that trigger any of the user's remembered allergies."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=code_executor,
    tools=[
        get_weather,
        get_current_time,
        get_pantry_items,
        add_pantry_item,
        check_expiring_items,
        search_recipes,
        geocode_address,
        find_nearby_places,
        generate_recipe_image,
        generate_recipe_video,
        LoadMemoryTool(),
        PreloadMemoryTool(),
    ],
    after_model_callback=a2ui_callback,
)


app = App(
    root_agent=root_agent,
    name="app",
)









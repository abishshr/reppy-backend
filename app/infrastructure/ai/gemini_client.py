"""Gemini API client for AI interactions."""

import base64
from typing import Any

import google.generativeai as genai
import httpx
from google.generativeai.types import FunctionDeclaration, Tool

from app.config import settings


class GeminiClient:
    """Client for interacting with Google's Gemini API."""

    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    async def chat_with_tools(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        image_url: str | None = None,
        image_base64: str | None = None,
        image_mime_type: str = "image/jpeg",
    ) -> dict[str, Any]:
        """
        Send a chat message with tool calling support and optional image.

        Args:
            system_prompt: The system instruction for the model
            messages: List of conversation messages
            tools: List of tool schemas
            image_url: Optional URL of an image to analyze
            image_base64: Optional base64-encoded image data
            image_mime_type: MIME type of the image

        Returns:
            dict with 'text' and 'tool_calls'
        """
        # Convert tool schemas to Gemini format
        gemini_tools = self._convert_tools(tools)

        # Build conversation content
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [msg["content"]]})

        # Add image to the last message if provided
        if contents and (image_url or image_base64):
            print(f"[GeminiClient] Processing image - URL: {bool(image_url)}, Base64: {bool(image_base64)}")
            image_part = await self._create_image_part(
                image_url, image_base64, image_mime_type
            )
            if image_part:
                # Add image to the last user message
                contents[-1]["parts"].append(image_part)
                print(f"[GeminiClient] Image added to message, total parts: {len(contents[-1]['parts'])}")
            else:
                print("[GeminiClient] Failed to create image part")

        # Create model with system instruction
        model_with_system = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=system_prompt,
        )
        chat = model_with_system.start_chat(history=contents[:-1] if len(contents) > 1 else [])

        # Get all parts from the last message (text + image if present)
        last_message_parts = contents[-1]["parts"] if contents else [""]

        # Generate response
        response = chat.send_message(
            last_message_parts,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=8192,  # Increased for large tool outputs like workout plans
            ),
            tools=gemini_tools if gemini_tools else None,
        )

        # Parse response
        result: dict[str, Any] = {
            "text": "",
            "tool_calls": [],
        }

        for part in response.parts:
            if hasattr(part, "text") and part.text:
                result["text"] = part.text
            elif hasattr(part, "function_call"):
                fc = part.function_call
                # Deep convert protobuf to Python primitives
                args = self._proto_to_dict(fc.args) if fc.args else {}
                print(f"[GeminiClient] Tool call: {fc.name}, args keys: {list(args.keys()) if args else 'none'}")
                # Log plan parameter if present (preview only)
                if "plan" in args:
                    plan_preview = str(args["plan"])[:200]
                    print(f"[GeminiClient] Plan preview: {plan_preview}...")
                result["tool_calls"].append({
                    "name": fc.name,
                    "arguments": args,
                })

        return result

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Simple text generation without tools."""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        response = self.model.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=1024,
            ),
        )

        return response.text

    async def _create_image_part(
        self,
        image_url: str | None,
        image_base64: str | None,
        mime_type: str,
    ) -> dict | None:
        """
        Create an image part for Gemini from URL or base64 data.

        Args:
            image_url: URL of the image to fetch
            image_base64: Base64-encoded image data
            mime_type: MIME type of the image

        Returns:
            Image part dict for Gemini, or None if failed
        """
        try:
            if image_base64:
                # Remove data URI prefix if present
                if "," in image_base64:
                    image_base64 = image_base64.split(",")[1]

                return {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_base64,
                    }
                }

            elif image_url:
                # Fetch image from URL
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_url, timeout=30.0)
                    response.raise_for_status()

                    # Detect mime type from response or URL
                    content_type = response.headers.get("content-type", mime_type)
                    if ";" in content_type:
                        content_type = content_type.split(";")[0]

                    # Encode to base64
                    image_data = base64.b64encode(response.content).decode("utf-8")

                    return {
                        "inline_data": {
                            "mime_type": content_type,
                            "data": image_data,
                        }
                    }

        except Exception as e:
            print(f"[GeminiClient] Failed to process image: {e}")
            return None

        return None

    def _proto_to_dict(self, proto_obj: Any) -> Any:
        """Recursively convert protobuf objects to Python primitives."""
        from google.protobuf.struct_pb2 import Struct, ListValue, Value

        if isinstance(proto_obj, dict):
            return {k: self._proto_to_dict(v) for k, v in proto_obj.items()}
        elif hasattr(proto_obj, 'items'):  # MapComposite
            return {k: self._proto_to_dict(v) for k, v in proto_obj.items()}
        elif hasattr(proto_obj, '__iter__') and not isinstance(proto_obj, (str, bytes)):
            # RepeatedComposite or list-like
            return [self._proto_to_dict(item) for item in proto_obj]
        elif hasattr(proto_obj, 'DESCRIPTOR'):  # Protobuf message
            from google.protobuf.json_format import MessageToDict
            return MessageToDict(proto_obj)
        else:
            return proto_obj

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[Tool] | None:
        """Convert our tool schema format to Gemini's format."""
        if not tools:
            return None

        function_declarations = []

        for tool in tools:
            # Convert parameters to Gemini format
            properties = {}
            required = []

            params = tool.get("parameters", {})
            for prop_name, prop_schema in params.get("properties", {}).items():
                prop_type = prop_schema.get("type", "string")

                # Map types
                type_mapping = {
                    "string": "STRING",
                    "integer": "INTEGER",
                    "number": "NUMBER",
                    "boolean": "BOOLEAN",
                    "array": "ARRAY",
                    "object": "OBJECT",
                }

                gemini_type = type_mapping.get(prop_type, "STRING")

                properties[prop_name] = {
                    "type": gemini_type,
                    "description": prop_schema.get("description", ""),
                }

                # Handle array items
                if prop_type == "array" and "items" in prop_schema:
                    properties[prop_name]["items"] = prop_schema["items"]

            # Build required list
            required = params.get("required", [])

            fd = FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters={
                    "type": "OBJECT",
                    "properties": properties,
                    "required": required,
                } if properties else None,
            )
            function_declarations.append(fd)

        return [Tool(function_declarations=function_declarations)]

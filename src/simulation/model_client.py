"""Configurable model interface with no implicit network calls."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import AgentModelReply, ModelOutput, ModelRequest, PublicMessageDraft


class ModelClientError(RuntimeError):
    """Base class for explicit, safe model-client failures."""

    def __init__(self, message: str, *, failure_category: str = "model_client") -> None:
        super().__init__(message)
        self.failure_category = failure_category


class ModelConfigurationError(ModelClientError):
    pass


class ModelTransportError(ModelClientError):
    pass


class ModelResponseError(ModelClientError):
    pass


class ModelClient(Protocol):
    def generate(self, request: ModelRequest) -> ModelOutput: ...


class OpenAICompatibleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = "https://api.openai.com/v1"
    model: str = Field(min_length=1)
    api_key_env: str = Field(default="OPENAI_API_KEY", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=512, ge=1)
    max_retries: int = Field(default=0, ge=0, le=5)
    seed: int | None = None
    timeout_seconds: float = Field(default=30.0, gt=0.0)
    response_format: Literal["json_schema", "json_object"] = "json_schema"

    @model_validator(mode="after")
    def validate_base_url(self) -> "OpenAICompatibleConfig":
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        return self

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/chat/completions"


TransportResponse = (
    tuple[int, bytes] | tuple[int, bytes, Mapping[str, str]]
)
Transport = Callable[[str, Mapping[str, str], bytes, float], TransportResponse]


def _urllib_transport(
    url: str, headers: Mapping[str, str], body: bytes, timeout: float
) -> tuple[int, bytes, Mapping[str, str]]:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is explicit config
            return response.status, response.read(), dict(response.headers.items())
    except HTTPError as exc:
        response_headers = dict(exc.headers.items()) if exc.headers is not None else {}
        return exc.code, exc.read(), response_headers
    except (URLError, TimeoutError, OSError) as exc:
        raise ModelTransportError(
            "model endpoint could not be reached (category=transport_unreachable)",
            failure_category="transport_unreachable",
        ) from exc


def _safe_provider_field(value: object, *, secret: str, limit: int) -> str | None:
    if not isinstance(value, (str, int, float)):
        return None
    sanitized = " ".join(str(value).split())
    if secret:
        sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized[:limit] or None


def _provider_failure_category(status: int, code: str | None, message: str | None) -> str:
    normalized_code = (code or "").lower()
    normalized_message = (message or "").lower()
    if normalized_code == "json_validate_failed":
        return "provider_json_validation"
    if status == 400 and "schema" in normalized_message:
        return "provider_schema_rejected"
    if status in {401, 403}:
        return "provider_auth_or_permission"
    if status == 429:
        return "provider_rate_limit"
    if status >= 500:
        return "provider_server_error"
    return "provider_request_rejected"


def _provider_error_message(
    status: int,
    body: bytes,
    response_headers: Mapping[str, str],
    *,
    api_key: str,
) -> tuple[str, str]:
    """Extract only documented diagnostic fields; never echo bodies or headers."""

    error_code: object = None
    error_message: object = None
    body_request_id: object = None
    try:
        payload = json.loads(body)
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                error_code = error.get("code") or error.get("type")
                error_message = error.get("message")
            body_request_id = payload.get("request_id")
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    normalized_headers = {str(key).lower(): value for key, value in response_headers.items()}
    header_request_id = next(
        (
            normalized_headers[name]
            for name in ("x-request-id", "x-groq-request-id", "request-id")
            if name in normalized_headers
        ),
        None,
    )
    safe_code = _safe_provider_field(error_code, secret=api_key, limit=100)
    safe_message = _safe_provider_field(error_message, secret=api_key, limit=500)
    safe_request_id = _safe_provider_field(
        header_request_id or body_request_id,
        secret=api_key,
        limit=200,
    )
    category = _provider_failure_category(status, safe_code, safe_message)
    details = [f"category={category}"]
    if safe_code:
        details.append(f"code={safe_code}")
    if safe_message:
        details.append(f"message={safe_message}")
    if safe_request_id:
        details.append(f"request_id={safe_request_id}")
    suffix = f" ({'; '.join(details)})" if details else ""
    return f"model endpoint returned HTTP {status}{suffix}", category


def _strict_response_schema() -> dict[str, object]:
    """Derive Groq's strict structural subset from the Pydantic contract."""

    pydantic_schema = AgentModelReply.model_json_schema()

    def structural_subset(node: object) -> object:
        if isinstance(node, dict):
            result: dict[str, object] = {}
            for key in ("type", "enum", "$ref"):
                if key in node:
                    result[key] = node[key]
            if "items" in node:
                result["items"] = structural_subset(node["items"])
            if "anyOf" in node:
                result["anyOf"] = structural_subset(node["anyOf"])
            definitions = node.get("$defs")
            if isinstance(definitions, dict):
                result["$defs"] = {
                    name: structural_subset(definition)
                    for name, definition in definitions.items()
                }
            properties = node.get("properties")
            if isinstance(properties, dict):
                result["properties"] = {
                    name: structural_subset(property_schema)
                    for name, property_schema in properties.items()
                }
                # Groq strict mode requires every represented field to be present.
                # Application-optional values retain []/null semantics, and the
                # Pydantic model itself remains unchanged.
                result["required"] = list(properties)
                result["additionalProperties"] = False
            return result
        if isinstance(node, list):
            return [structural_subset(value) for value in node]
        return node

    schema = structural_subset(pydantic_schema)
    if not isinstance(schema, dict):
        raise ModelConfigurationError(
            "agent response schema is not an object "
            "(category=provider_schema_configuration)",
            failure_category="provider_schema_configuration",
        )
    _validate_strict_response_schema(schema)
    return schema


def _validate_strict_response_schema(schema: Mapping[str, object]) -> None:
    """Fail locally if a generated strict schema violates Groq requirements."""

    def validate(node: object, path: str) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                required = node.get("required")
                if required != list(properties):
                    raise ModelConfigurationError(
                        f"strict response schema has non-required fields at {path} "
                        "(category=provider_schema_configuration)",
                        failure_category="provider_schema_configuration",
                    )
                if node.get("additionalProperties") is not False:
                    raise ModelConfigurationError(
                        f"strict response schema is not closed at {path} "
                        "(category=provider_schema_configuration)",
                        failure_category="provider_schema_configuration",
                    )
            for key, value in node.items():
                validate(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                validate(value, f"{path}[{index}]")

    validate(schema, "$")


class OpenAICompatibleClient:
    """Small Chat Completions adapter with strict local response validation."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        transport: Transport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport or _urllib_transport

    def generate(self, request: ModelRequest) -> ModelOutput:
        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise ModelConfigurationError(
                f"missing API credential in environment variable {self.config.api_key_env} "
                "(category=configuration)",
                failure_category="configuration",
            )
        response_format: dict[str, object]
        if self.config.response_format == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "cascade_agent_reply",
                    "strict": True,
                    "schema": _strict_response_schema(),
                },
            }
        else:
            response_format = {"type": "json_object"}
        payload: dict[str, object] = {
            "model": self.config.model,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "temperature": self.config.temperature,
            "response_format": response_format,
        }
        token_parameter = (
            "max_completion_tokens"
            if urlparse(self.config.base_url).hostname == "api.groq.com"
            else "max_tokens"
        )
        payload[token_parameter] = self.config.max_output_tokens
        if self.config.seed is not None:
            payload["seed"] = self.config.seed
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "cascade-research/0.1",
        }
        encoded = json.dumps(payload).encode("utf-8")
        status = 0
        body = b""
        response_headers: Mapping[str, str] = {}
        for attempt in range(self.config.max_retries + 1):
            try:
                transport_response = self._transport(
                    self.config.endpoint,
                    headers,
                    encoded,
                    self.config.timeout_seconds,
                )
                if len(transport_response) == 2:
                    status, body = transport_response
                    response_headers = {}
                else:
                    status, body, response_headers = transport_response
            except ModelTransportError:
                if attempt >= self.config.max_retries:
                    raise
                continue
            if status not in {408, 409, 429} and status < 500:
                break
            if attempt >= self.config.max_retries:
                break
        if status < 200 or status >= 300:
            error_message, failure_category = _provider_error_message(
                status,
                body,
                response_headers,
                api_key=api_key,
            )
            raise ModelTransportError(
                error_message,
                failure_category=failure_category,
            )
        try:
            response = json.loads(body)
            choice = response["choices"][0]
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("message content is not a string")
            reply = AgentModelReply.model_validate_json(content)
            usage = response.get("usage") or {}
            return ModelOutput(
                reply=reply,
                model_name=str(response.get("model") or self.config.model),
                response_id=response.get("id"),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ModelResponseError(
                "model returned a malformed structured response "
                "(category=application_response_validation)",
                failure_category="application_response_validation",
            ) from exc


class DeterministicMockClient:
    """Request-keyed mock whose output is independent of call order."""

    def __init__(
        self,
        responses: Mapping[str, AgentModelReply] | None = None,
        *,
        default_reply: AgentModelReply | None = None,
        model_name: str = "deterministic-mock-v1",
    ) -> None:
        self._responses = dict(responses or {})
        self._default = default_reply or AgentModelReply(
            private_belief="UNKNOWN",
            confidence=0.0,
            uncertainty="The mock has no configured response for this request.",
            public_recommendation="UNKNOWN",
        )
        self._model_name = model_name
        self._requests: list[ModelRequest] = []

    @property
    def requests(self) -> tuple[ModelRequest, ...]:
        return tuple(self._requests)

    def generate(self, request: ModelRequest) -> ModelOutput:
        self._requests.append(request)
        reply = self._responses.get(request.request_id, self._default)
        return ModelOutput(reply=reply, model_name=self._model_name)


class EvidenceEchoMockClient:
    """Deterministic CLI mock that shares one authorized evidence sentence."""

    model_name = "evidence-echo-mock-v1"

    def generate(self, request: ModelRequest) -> ModelOutput:
        user_messages = [item for item in request.messages if item.role == "user"]
        if len(user_messages) != 1:
            raise ModelResponseError("mock request must contain one user payload")
        try:
            payload = json.loads(user_messages[0].content)
            evidence = payload["authorized_evidence"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ModelResponseError("mock request contains malformed agent context") from exc
        first = evidence[0] if evidence else None
        supporting = (first["fact_id"],) if first else ()
        outgoing = None
        if request.purpose == "message" and first is not None:
            outgoing = PublicMessageDraft(
                text=f"My evidence says: {first['text']}",
                source_fact_ids=supporting,
                public_recommendation="UNKNOWN",
            )
        reply = AgentModelReply(
            private_belief="UNKNOWN",
            confidence=0.25,
            supporting_fact_ids=supporting,
            uncertainty="The available evidence does not establish every requirement.",
            public_recommendation="UNKNOWN",
            outgoing_message=outgoing,
        )
        return ModelOutput(reply=reply, model_name=self.model_name)

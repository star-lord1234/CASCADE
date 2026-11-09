import json

import pytest
from pydantic import ValidationError

from src.simulation.agent import AgentResponseValidationError, IsolatedAgent
from src.simulation.cli import _live_api_key_env, build_parser
from src.simulation.loader import load_benchmark
from src.simulation.model_client import (
    DeterministicMockClient,
    ModelConfigurationError,
    ModelResponseError,
    ModelTransportError,
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
    _validate_strict_response_schema,
)
from src.simulation.schemas import (
    AgentModelReply,
    BeliefSnapshot,
    DeliveredMessage,
    ModelRequest,
    PublicMessageDraft,
)


def _request() -> ModelRequest:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    context = catalog.agent_context(catalog.task_ids()[0], "agent_1")
    return IsolatedAgent(context, DeterministicMockClient()).build_request(
        request_id="REQ_1", round_index=0
    )


def test_reply_schema_rejects_bad_answer_confidence_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AgentModelReply.model_validate(
            {
                "private_belief": "MAYBE",
                "confidence": 2.0,
                "public_recommendation": "YES",
                "secret": "not allowed",
            }
        )


def test_deterministic_mock_is_request_keyed_not_call_order() -> None:
    configured = AgentModelReply(
        private_belief="YES",
        confidence=0.7,
        supporting_fact_ids=(),
        public_recommendation="YES",
    )
    mock = DeterministicMockClient({"REQ_1": configured})
    request = _request()
    assert mock.generate(request) == mock.generate(request)
    assert mock.generate(request).reply == configured
    other = request.model_copy(update={"request_id": "REQ_OTHER"})
    assert mock.generate(other).reply.private_belief == "UNKNOWN"


def test_openai_compatible_client_parses_schema_checked_reply(monkeypatch) -> None:
    monkeypatch.setenv("CASCADE_TEST_API_KEY", "not-a-real-key")
    captured = {}

    def transport(url, headers, body, timeout):
        captured.update(
            url=url,
            authorization=headers["Authorization"],
            payload=json.loads(body),
            timeout=timeout,
        )
        content = json.dumps(
            {
                "private_belief": "UNKNOWN",
                "confidence": 0.25,
                "supporting_fact_ids": [],
                "uncertainty": "More evidence is needed.",
                "public_recommendation": "UNKNOWN",
                "outgoing_message": None,
            }
        )
        response = {
            "id": "response_1",
            "model": "test-model-version",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        }
        return 200, json.dumps(response).encode()

    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            base_url="https://example.invalid/v1",
            model="test-model",
            api_key_env="CASCADE_TEST_API_KEY",
        ),
        transport=transport,
    )
    output = client.generate(_request())
    assert output.reply.private_belief == "UNKNOWN"
    assert output.model_name == "test-model-version"
    assert output.input_tokens == 11
    assert captured["url"] == "https://example.invalid/v1/chat/completions"
    assert captured["authorization"] == "Bearer not-a-real-key"
    assert captured["payload"]["response_format"]["type"] == "json_schema"
    structured = captured["payload"]["response_format"]["json_schema"]
    assert structured["strict"] is True
    schema = structured["schema"]
    assert schema["required"] == list(schema["properties"])
    nested = schema["$defs"]["PublicMessageDraft"]
    assert nested["required"] == list(nested["properties"])
    assert schema["additionalProperties"] is False
    assert nested["additionalProperties"] is False
    assert set(schema["properties"]) == set(AgentModelReply.model_fields)
    assert set(nested["properties"]) == set(PublicMessageDraft.model_fields)
    assert "default" not in json.dumps(schema)
    assert "pattern" not in json.dumps(schema)
    assert "title" not in json.dumps(schema)
    assert schema["properties"]["private_belief"]["enum"] == [
        "YES",
        "NO",
        "UNKNOWN",
    ]
    uncertainty_types = {
        item.get("type")
        for item in schema["properties"]["uncertainty"]["anyOf"]
    }
    assert uncertainty_types == {
        "string",
        "null",
    }


def test_groq_cli_propagates_request_settings_and_infers_groq_key_env() -> None:
    args = build_parser().parse_args(
        [
            "live-smoke",
            "--model",
            "openai/gpt-oss-120b",
            "--base-url",
            "https://api.groq.com/openai/v1",
        ]
    )
    assert args.model == "openai/gpt-oss-120b"
    assert args.base_url == "https://api.groq.com/openai/v1"
    assert args.api_key_env is None
    assert args.max_output_tokens == 1024
    assert _live_api_key_env(args.base_url, args.api_key_env) == "GROQ_API_KEY"
    assert _live_api_key_env(args.base_url, "CUSTOM_GROQ_KEY") == "CUSTOM_GROQ_KEY"


def test_groq_compatible_request_matches_documented_chat_shape(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-secret")
    captured = {}

    def transport(url, headers, body, timeout):
        captured.update(url=url, headers=headers, payload=json.loads(body), timeout=timeout)
        content = json.dumps(
            {
                "private_belief": "UNKNOWN",
                "confidence": 0.2,
                "public_recommendation": "UNKNOWN",
            }
        )
        return 200, json.dumps(
            {"choices": [{"message": {"content": content}}]}
        ).encode(), {"x-request-id": "req_success"}

    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
            api_key_env="GROQ_API_KEY",
        ),
        transport=transport,
    )
    client.generate(_request())
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["headers"] == {
        "Authorization": "Bearer test-groq-secret",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "cascade-research/0.1",
    }
    assert captured["payload"]["model"] == "openai/gpt-oss-120b"
    assert [message["role"] for message in captured["payload"]["messages"]] == [
        "system",
        "user",
    ]
    assert captured["payload"]["max_completion_tokens"] == 512
    assert "max_tokens" not in captured["payload"]
    assert captured["payload"]["response_format"]["json_schema"]["strict"] is True
    assert captured["payload"]["model"] == "openai/gpt-oss-120b"


def test_provider_error_is_diagnostic_and_never_echoes_key_or_headers(monkeypatch) -> None:
    secret = "test-groq-secret"
    monkeypatch.setenv("GROQ_API_KEY", secret)
    response = {
        "error": {
            "message": f"Access denied for credential {secret}",
            "type": "permission_denied",
        },
        "headers": {"Authorization": f"Bearer {secret}"},
    }
    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
            api_key_env="GROQ_API_KEY",
        ),
        transport=lambda *_: (
            403,
            json.dumps(response).encode(),
            {
                "x-request-id": "req_403_test",
                "Authorization": f"Bearer {secret}",
            },
        ),
    )
    with pytest.raises(ModelTransportError) as raised:
        client.generate(_request())
    diagnostic = str(raised.value)
    assert diagnostic == (
        "model endpoint returned HTTP 403 "
        "(category=provider_auth_or_permission; code=permission_denied; "
        "message=Access denied for credential [REDACTED]; "
        "request_id=req_403_test)"
    )
    assert raised.value.failure_category == "provider_auth_or_permission"
    assert secret not in diagnostic
    assert "Authorization" not in diagnostic
    assert "Bearer" not in diagnostic


def test_invalid_strict_schema_is_rejected_locally() -> None:
    with pytest.raises(ModelConfigurationError) as raised:
        _validate_strict_response_schema(
            {
                "type": "object",
                "properties": {"private_belief": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            }
        )
    assert raised.value.failure_category == "provider_schema_configuration"
    assert "category=provider_schema_configuration" in str(raised.value)


def test_provider_json_validation_failure_is_sanitized_and_categorized(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-secret")
    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
            api_key_env="GROQ_API_KEY",
        ),
        transport=lambda *_: (
            400,
            json.dumps(
                {
                    "error": {
                        "code": "json_validate_failed",
                        "message": "Failed to generate JSON. Please adjust your prompt.",
                    }
                }
            ).encode(),
            {"x-request-id": "req_json_failure"},
        ),
    )
    with pytest.raises(ModelTransportError) as raised:
        client.generate(_request())
    assert raised.value.failure_category == "provider_json_validation"
    assert str(raised.value) == (
        "model endpoint returned HTTP 400 "
        "(category=provider_json_validation; code=json_validate_failed; "
        "message=Failed to generate JSON. Please adjust your prompt.; "
        "request_id=req_json_failure)"
    )


def test_provider_invalid_schema_rejection_is_categorized(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-secret")
    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
            api_key_env="GROQ_API_KEY",
        ),
        transport=lambda *_: (
            400,
            json.dumps(
                {
                    "error": {
                        "code": "invalid_request_error",
                        "message": "Invalid schema for response_format.",
                    }
                }
            ).encode(),
            {"x-request-id": "req_schema_failure"},
        ),
    )
    with pytest.raises(ModelTransportError) as raised:
        client.generate(_request())
    assert raised.value.failure_category == "provider_schema_rejected"
    assert "category=provider_schema_rejected" in str(raised.value)
    assert "request_id=req_schema_failure" in str(raised.value)


def test_application_validation_rejects_duplicate_evidence_ids(monkeypatch) -> None:
    monkeypatch.setenv("CASCADE_TEST_API_KEY", "placeholder")
    content = json.dumps(
        {
            "private_belief": "UNKNOWN",
            "confidence": 0.2,
            "supporting_fact_ids": ["F005", "F005"],
            "uncertainty": None,
            "public_recommendation": "UNKNOWN",
            "outgoing_message": None,
        }
    )
    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            model="test-model",
            api_key_env="CASCADE_TEST_API_KEY",
        ),
        transport=lambda *_: (
            200,
            json.dumps({"choices": [{"message": {"content": content}}]}).encode(),
        ),
    )
    with pytest.raises(ModelResponseError) as raised:
        client.generate(_request())
    assert raised.value.failure_category == "application_response_validation"
    assert "category=application_response_validation" in str(raised.value)


def test_agent_prompt_requests_only_the_complete_json_object() -> None:
    system_prompt = _request().messages[0].content
    assert "exactly one JSON object with no prose or Markdown fences" in system_prompt
    for field_name in AgentModelReply.model_fields:
        assert field_name in system_prompt


def test_openai_client_fails_safely_on_missing_key_and_malformed_reply(monkeypatch) -> None:
    config = OpenAICompatibleConfig(
        model="test-model", api_key_env="CASCADE_MISSING_TEST_KEY"
    )
    monkeypatch.delenv("CASCADE_MISSING_TEST_KEY", raising=False)
    with pytest.raises(ModelConfigurationError, match="CASCADE_MISSING_TEST_KEY"):
        OpenAICompatibleClient(config, transport=lambda *_: (200, b"{}")).generate(
            _request()
        )
    monkeypatch.setenv("CASCADE_MISSING_TEST_KEY", "placeholder")
    client = OpenAICompatibleClient(
        config,
        transport=lambda *_: (
            200,
            json.dumps({"choices": [{"message": {"content": "not-json"}}]}).encode(),
        ),
    )
    with pytest.raises(ModelResponseError, match="malformed structured response"):
        client.generate(_request())


def test_openai_client_retries_only_configured_transient_failures(monkeypatch) -> None:
    monkeypatch.setenv("CASCADE_RETRY_TEST_KEY", "placeholder")
    attempts = []

    def transport(*_):
        attempts.append(1)
        if len(attempts) == 1:
            return 429, b"{}"
        content = json.dumps(
            {
                "private_belief": "UNKNOWN",
                "confidence": 0.1,
                "public_recommendation": "UNKNOWN",
            }
        )
        return 200, json.dumps(
            {"choices": [{"message": {"content": content}}]}
        ).encode()

    client = OpenAICompatibleClient(
        OpenAICompatibleConfig(
            model="test-model",
            api_key_env="CASCADE_RETRY_TEST_KEY",
            max_retries=1,
            seed=42,
        ),
        transport=transport,
    )
    assert client.generate(_request()).reply.private_belief == "UNKNOWN"
    assert len(attempts) == 2


def test_agent_rejects_unauthorized_model_evidence_reference() -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    context = catalog.agent_context(catalog.task_ids()[0], "agent_1")
    reply = AgentModelReply(
        private_belief="YES",
        confidence=0.9,
        supporting_fact_ids=("F_UNAUTHORIZED",),
        public_recommendation="YES",
    )
    agent = IsolatedAgent(
        context, DeterministicMockClient({"REQ_1": reply})
    )
    with pytest.raises(AgentResponseValidationError, match="unauthorized"):
        agent.probe(
            request_id="REQ_1",
            snapshot_id="B_1",
            episode_id="EP_1",
            round_index=0,
        )


def test_delivery_is_recipient_checked_and_snapshot_serializes() -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    context = catalog.agent_context(task_id, "agent_1")
    fact_id = context.authorized_evidence[0].fact_id
    reply = AgentModelReply(
        private_belief="UNKNOWN",
        confidence=0.4,
        supporting_fact_ids=(fact_id,),
        uncertainty="The remaining requirements are unknown.",
        public_recommendation="UNKNOWN",
        outgoing_message=PublicMessageDraft(
            text="I need more evidence.",
            source_fact_ids=(fact_id,),
            parent_message_ids=("M_1",),
            public_recommendation="UNKNOWN",
        ),
    )
    agent = IsolatedAgent(context, DeterministicMockClient({"REQ_1": reply}))
    message = DeliveredMessage(
        message_id="M_1",
        task_id=task_id,
        sender_id="agent_2",
        recipient_id="agent_1",
        round_index=0,
        text="I found one relevant record.",
        public_recommendation="UNKNOWN",
    )
    agent.deliver(message)
    result = agent.probe(
        request_id="REQ_1",
        snapshot_id="B_1",
        episode_id="EP_1",
        round_index=1,
    )
    restored = BeliefSnapshot.model_validate_json(result.snapshot.model_dump_json())
    assert restored == result.snapshot
    assert restored.received_message_ids == ("M_1",)
    wrong_recipient = message.model_copy(update={"message_id": "M_2", "recipient_id": "agent_3"})
    with pytest.raises(ValidationError, match="another recipient"):
        agent.deliver(wrong_recipient)

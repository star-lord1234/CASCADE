import json

import pytest
from pydantic import ValidationError

from src.simulation.loader import load_benchmark
from src.simulation.model_client import DeterministicMockClient
from src.simulation.network import build_adjacency
from src.simulation.orchestrator import aggregate_group, run_episode
from src.simulation.schemas import (
    AgentModelReply,
    BeliefSnapshot,
    EpisodeConfig,
    PublicMessageDraft,
)


def _reply(
    belief: str,
    *,
    fact_id: str | None = None,
    outgoing_text: str | None = None,
) -> AgentModelReply:
    outgoing = None
    if outgoing_text is not None:
        outgoing = PublicMessageDraft(
            text=outgoing_text,
            source_fact_ids=((fact_id,) if fact_id else ()),
            public_recommendation=belief,
        )
    return AgentModelReply(
        private_belief=belief,
        confidence=0.7 if belief != "UNKNOWN" else 0.2,
        supporting_fact_ids=((fact_id,) if fact_id else ()),
        uncertainty=None if belief != "UNKNOWN" else "More evidence is needed.",
        public_recommendation=belief,
        outgoing_message=outgoing,
    )


def _clients(catalog, task_id: str, episode_id: str, *, agents: int = 3):
    clients = {}
    for agent_id in catalog.agent_ids(task_id)[:agents]:
        context = catalog.agent_context(task_id, agent_id)
        fact_id = context.authorized_evidence[0].fact_id
        responses = {
            f"{episode_id}.R0.{agent_id}.belief": _reply("UNKNOWN"),
            f"{episode_id}.R1.{agent_id}.message": _reply(
                "UNKNOWN",
                fact_id=fact_id,
                outgoing_text=f"{agent_id} shares authorized evidence {fact_id}.",
            ),
            f"{episode_id}.R1.{agent_id}.belief": _reply("YES", fact_id=fact_id),
        }
        clients[agent_id] = DeterministicMockClient(responses)
    return clients


def _prompt_for(client: DeterministicMockClient, purpose: str, round_index: int) -> str:
    request = next(
        item
        for item in client.requests
        if item.purpose == purpose and item.round_index == round_index
    )
    return "\n".join(message.content for message in request.messages)


def test_network_topologies_are_deterministic_and_role_neutral() -> None:
    agents = ("agent_1", "agent_2", "agent_3", "agent_4", "agent_5")
    fully = build_adjacency(agents, "fully_connected")
    assert fully["agent_1"] == ("agent_2", "agent_3", "agent_4", "agent_5")
    ring = build_adjacency(agents, "ring")
    assert ring["agent_1"] == ("agent_5", "agent_2")
    assert ring["agent_3"] == ("agent_2", "agent_4")
    star = build_adjacency(agents, "star", star_center_id="agent_3")
    assert star["agent_3"] == ("agent_1", "agent_2", "agent_4", "agent_5")
    assert star["agent_1"] == ("agent_3",)


@pytest.mark.parametrize("condition", ["clear", "ambiguous", "omission"])
def test_full_mock_episode_runs_in_each_controlled_condition(condition: str) -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    episode_id = f"EP_{condition}"
    clients = _clients(catalog, task_id, episode_id)
    result = run_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id=episode_id,
        config=EpisodeConfig(
            condition=condition,
            topology="fully_connected",
            communication_rounds=1,
            agent_count=3,
            injection_round=1,
            stimulus_sender_id="agent_1",
        ),
        model_clients=clients,
    )
    controlled = [item for item in result.routed_messages if item.origin == "controlled"]
    assert len(controlled) == 1
    assert controlled[0].condition_tag == condition
    assert controlled[0].variant_id is not None
    assert controlled[0].sender_id == "agent_1"
    assert controlled[0].recipient_ids == ("agent_2", "agent_3")
    assert len(result.belief_snapshots) == 6
    assert result.final_group_decision.answer == "YES"


def test_conditions_select_distinct_matched_stimuli() -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    stimuli = {
        condition: catalog.controlled_stimulus(task_id, condition)
        for condition in ("clear", "ambiguous", "omission")
    }
    assert len({item.variant_id for item in stimuli.values()}) == 3
    assert len({item.text for item in stimuli.values()}) == 3
    assert {item.condition for item in stimuli.values()} == {
        "clear",
        "ambiguous",
        "omission",
    }


def test_round_zero_is_independent_and_organic_delivery_is_synchronous() -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    episode_id = "EP_SYNC"
    clients = _clients(catalog, task_id, episode_id)
    result = run_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id=episode_id,
        config=EpisodeConfig(
            condition="ambiguous",
            topology="fully_connected",
            communication_rounds=1,
            agent_count=3,
            injection_round=1,
            stimulus_sender_id="agent_1",
        ),
        model_clients=clients,
    )

    for agent_id, client in clients.items():
        round_zero = _prompt_for(client, "belief", 0)
        assert '"delivered_messages":[]' in round_zero
        message_phase = _prompt_for(client, "message", 1)
        assert ".organic." not in message_phase
        assert "condition_tag" not in message_phase
        assert "variant_id" not in message_phase
        assert "ambiguity_category" not in message_phase
        assert "ground_truth" not in message_phase
        belief_phase = _prompt_for(client, "belief", 1)
        expected_organic = 2
        payload = json.loads(next(
            message.content
            for request in client.requests
            if request.purpose == "belief" and request.round_index == 1
            for message in request.messages
            if message.role == "user"
        ))
        organic_received = [
            item
            for item in payload["delivered_messages"]
            if ".organic." in item["message_id"]
        ]
        assert len(organic_received) == expected_organic
        assert "leader" not in belief_phase.lower()

    organic = [item for item in result.routed_messages if item.origin == "organic"]
    assert [item.sender_id for item in organic] == ["agent_1", "agent_2", "agent_3"]
    assert all(len(item.recipient_ids) == 2 for item in organic)


@pytest.mark.parametrize(
    ("topology", "center", "expected_counts"),
    [
        ("fully_connected", None, {"agent_1": 4, "agent_2": 4}),
        ("ring", None, {"agent_1": 2, "agent_2": 2}),
        ("star", "agent_3", {"agent_1": 1, "agent_3": 4}),
    ],
)
def test_episode_routing_respects_topology(topology, center, expected_counts) -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    episode_id = f"EP_{topology}"
    clients = _clients(catalog, task_id, episode_id, agents=5)
    result = run_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id=episode_id,
        config=EpisodeConfig(
            condition="clear",
            topology=topology,
            communication_rounds=1,
            agent_count=5,
            injection_round=1,
            stimulus_sender_id="agent_1",
            star_center_id=center,
        ),
        model_clients=clients,
    )
    organic = {
        item.sender_id: item
        for item in result.routed_messages
        if item.origin == "organic"
    }
    for sender, count in expected_counts.items():
        assert len(organic[sender].recipient_ids) == count
    if topology == "star":
        assert result.config.stimulus_sender_id != result.config.star_center_id


def test_beliefs_update_after_delivery_and_group_aggregation_is_prespecified() -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    clients = _clients(catalog, task_id, "EP_UPDATE")
    result = run_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id="EP_UPDATE",
        config=EpisodeConfig(
            condition="omission",
            communication_rounds=1,
            agent_count=3,
            injection_round=1,
            stimulus_sender_id="agent_1",
        ),
        model_clients=clients,
    )
    round_zero = [item.private_belief for item in result.belief_snapshots if item.round_index == 0]
    round_one = [item.private_belief for item in result.belief_snapshots if item.round_index == 1]
    assert round_zero == ["UNKNOWN", "UNKNOWN", "UNKNOWN"]
    assert round_one == ["YES", "YES", "YES"]
    assert result.final_group_decision.answer == "YES"

    def snapshot(index, belief):
        return BeliefSnapshot(
            snapshot_id=f"B_{index}",
            episode_id="EP_AGG",
            task_id="TASK_1",
            agent_id=f"agent_{index}",
            round_index=1,
            private_belief=belief,
            confidence=0.5,
            public_recommendation=belief,
        )

    assert aggregate_group(
        tuple(snapshot(index, belief) for index, belief in enumerate(("YES", "YES", "NO"), 1))
    ).answer == "YES"
    assert aggregate_group(
        tuple(snapshot(index, belief) for index, belief in enumerate(("YES", "NO", "UNKNOWN"), 1))
    ).answer == "ABSTAIN"
    assert aggregate_group(
        tuple(snapshot(index, belief) for index, belief in enumerate(("YES", "YES", "UNKNOWN", "UNKNOWN", "UNKNOWN"), 1))
    ).answer == "ABSTAIN"


def test_independent_condition_runs_only_round_zero() -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    episode_id = "EP_INDEPENDENT"
    clients = {}
    for agent_id in catalog.agent_ids(task_id)[:3]:
        clients[agent_id] = DeterministicMockClient(
            {f"{episode_id}.R0.{agent_id}.belief": _reply("UNKNOWN")}
        )
    result = run_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id=episode_id,
        config=EpisodeConfig(
            condition="independent",
            communication_rounds=0,
            agent_count=3,
            injection_round=None,
            stimulus_sender_id=None,
        ),
        model_clients=clients,
    )
    assert len(result.belief_snapshots) == 3
    assert result.routed_messages == ()
    assert result.rounds == ()
    assert result.final_group_decision.answer == "ABSTAIN"


def test_injection_round_is_configurable() -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    episode_id = "EP_DELAYED_INJECTION"
    clients = _clients(catalog, task_id, episode_id)
    result = run_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id=episode_id,
        config=EpisodeConfig(
            condition="clear",
            communication_rounds=2,
            agent_count=3,
            injection_round=2,
            stimulus_sender_id="agent_2",
        ),
        model_clients=clients,
    )
    assert result.rounds[0].controlled_message_ids == ()
    assert len(result.rounds[1].controlled_message_ids) == 1
    controlled = next(item for item in result.routed_messages if item.origin == "controlled")
    assert controlled.round_index == 2
    assert controlled.sender_id == "agent_2"


def test_mock_episode_is_deterministically_reproducible() -> None:
    catalog = load_benchmark("data/benchmark/canonical_tasks.jsonl")
    task_id = catalog.task_ids()[0]
    episode_id = "EP_REPRODUCIBLE"
    config = EpisodeConfig(
        condition="ambiguous",
        topology="ring",
        communication_rounds=1,
        agent_count=3,
        injection_round=1,
        stimulus_sender_id="agent_1",
    )
    first = run_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id=episode_id,
        config=config,
        model_clients=_clients(catalog, task_id, episode_id),
    )
    second = run_episode(
        catalog=catalog,
        task_id=task_id,
        episode_id=episode_id,
        config=config,
        model_clients=_clients(catalog, task_id, episode_id),
    )
    assert first == second


def test_invalid_episode_configurations_fail_explicitly() -> None:
    with pytest.raises(ValidationError, match="explicit stimulus sender"):
        EpisodeConfig(condition="clear", communication_rounds=1)
    with pytest.raises(ValidationError, match="zero communication rounds"):
        EpisodeConfig(
            condition="independent",
            communication_rounds=1,
            injection_round=None,
        )
    with pytest.raises(ValidationError, match="explicit center"):
        EpisodeConfig(
            condition="clear",
            topology="star",
            communication_rounds=1,
            injection_round=1,
            stimulus_sender_id="agent_1",
        )

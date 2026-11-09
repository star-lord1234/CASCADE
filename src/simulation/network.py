"""Deterministic communication topologies without role or authority labels."""

from __future__ import annotations

from .schemas import TopologyName


class NetworkConfigurationError(ValueError):
    pass


def build_adjacency(
    agent_ids: tuple[str, ...],
    topology: TopologyName,
    *,
    star_center_id: str | None = None,
) -> dict[str, tuple[str, ...]]:
    if len(agent_ids) < 2:
        raise NetworkConfigurationError("a communication network needs at least two agents")
    if len(agent_ids) != len(set(agent_ids)):
        raise NetworkConfigurationError("agent IDs must be unique")
    if topology == "fully_connected":
        if star_center_id is not None:
            raise NetworkConfigurationError("fully connected topology has no star center")
        return {
            sender: tuple(recipient for recipient in agent_ids if recipient != sender)
            for sender in agent_ids
        }
    if topology == "ring":
        if star_center_id is not None:
            raise NetworkConfigurationError("ring topology has no star center")
        if len(agent_ids) == 2:
            return {agent_ids[0]: (agent_ids[1],), agent_ids[1]: (agent_ids[0],)}
        adjacency: dict[str, tuple[str, ...]] = {}
        for index, sender in enumerate(agent_ids):
            previous = agent_ids[index - 1]
            following = agent_ids[(index + 1) % len(agent_ids)]
            adjacency[sender] = (previous, following)
        return adjacency
    if topology == "star":
        if star_center_id is None:
            raise NetworkConfigurationError("star topology requires an explicit center")
        if star_center_id not in agent_ids:
            raise NetworkConfigurationError("star center must be a selected agent")
        return {
            sender: (
                tuple(agent for agent in agent_ids if agent != sender)
                if sender == star_center_id
                else (star_center_id,)
            )
            for sender in agent_ids
        }
    raise NetworkConfigurationError(f"unsupported topology: {topology!r}")

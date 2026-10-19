"""Typed messages exchanged between Sentinel, agents, and Kafka.

Every payload that crosses a process boundary (workflow requests, agent commands and results, Kafka records)
is one of these models, validated on the way in and serialized with ``model_dump(mode="json")``.
"""

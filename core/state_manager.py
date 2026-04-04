"""Shared state manager for inter-agent communication."""
from datetime import datetime


class StateManager:
    """Pub/sub state manager for passing data between agents."""

    def __init__(self):
        self._channels = {}
        self._history = []

    def publish(self, channel, data, agent_name="system"):
        self._channels[channel] = {
            "data": data,
            "published_by": agent_name,
            "timestamp": datetime.now().isoformat(),
        }
        self._history.append({
            "action": "publish",
            "channel": channel,
            "agent": agent_name,
            "timestamp": datetime.now().isoformat(),
        })

    def subscribe(self, channel):
        entry = self._channels.get(channel)
        if entry:
            return entry["data"]
        return None

    def get_all_channels(self):
        return {
            ch: {
                "published_by": info["published_by"],
                "timestamp": info["timestamp"],
                "has_data": info["data"] is not None,
            }
            for ch, info in self._channels.items()
        }

    def clear(self):
        self._channels.clear()
        self._history.clear()


# Singleton
state_manager = StateManager()

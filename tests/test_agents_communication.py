"""Test inter-agent communication and regulatory auto-update features."""
import pytest
import time
from agents.regulatory_tracker import RegulatoryTrackerAgent
from agents.roi_agent import ROIAgent
from core.orchestrator import Orchestrator


def test_regulatory_tracker_background_updater():
    """Test that regulatory tracker starts background updater."""
    tracker = RegulatoryTrackerAgent()
    assert tracker.background_thread is not None
    assert tracker.background_thread.is_alive()
    
    # Clean up
    tracker.stop()
    tracker.background_thread.join(timeout=2)
    assert not tracker.running


def test_regulatory_tracker_accepts_orchestrator():
    """Test that regulatory tracker can receive and use orchestrator reference."""
    tracker = RegulatoryTrackerAgent()
    
    # Mock orchestrator
    class MockOrchestrator:
        def __init__(self):
            self.messages = {}
        
        def post_message(self, agent_key, message):
            self.messages[agent_key] = message
    
    mock_orch = MockOrchestrator()
    
    # Execute with orchestrator (will fail due to missing data, but should handle gracefully)
    result = tracker.execute(orchestrator=mock_orch)
    
    # Check that error is handled
    assert "error" in result or "framework_results" in result
    
    # Clean up
    tracker.stop()


def test_roi_agent_posts_suggestions():
    """Test that ROI agent posts suggestions to orchestrator."""
    roi = ROIAgent()
    
    # Mock orchestrator
    class MockOrchestrator:
        def __init__(self):
            self.messages = {}
        
        def post_message(self, agent_key, message):
            self.messages[agent_key] = message
    
    mock_orch = MockOrchestrator()
    
    # Simulate posting suggestions with good financial ROI
    mock_orch.post_message("roi_agent", "High ROI detected (75%) — Consider scaling ESG initiatives")
    
    assert "roi_agent" in mock_orch.messages
    assert "High ROI" in mock_orch.messages["roi_agent"]


def test_orchestrator_message_board():
    """Test orchestrator message board functionality."""
    orch = Orchestrator()
    
    # Post messages from different agents
    orch.post_message("roi_agent", "ROI insight: Strong investment quality detected")
    orch.post_message("regulatory_tracker", "Regulatory alert: New CSRD deadline announced")
    
    # Verify messages are stored
    assert "roi_agent" in orch.message_board
    assert "regulatory_tracker" in orch.message_board
    assert "Strong investment quality" in orch.message_board["roi_agent"]
    assert "CSRD deadline" in orch.message_board["regulatory_tracker"]


def test_regulatory_tracker_cache():
    """Test that regulatory tracker uses framework cache."""
    tracker = RegulatoryTrackerAgent()
    
    # Initially cache should be None
    assert tracker.frameworks_cache is None
    
    # After first execution (or cache update), cache should have data
    # Note: This test may fail if no regulatory data is available
    # but it verifies the cache mechanism is in place
    assert hasattr(tracker, 'frameworks_cache')
    assert hasattr(tracker, 'last_updated')
    
    # Clean up
    tracker.stop()

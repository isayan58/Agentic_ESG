"""Channel enum guarantees: str-compatibility and stable values.

These tests pin two properties we rely on:
1. Channel members are interchangeable with their string values, so adopting
   the enum is non-breaking for any caller still passing raw strings.
2. The string values are stable — changing any of them is a public-API
   break that requires migrating on-disk state and downstream consumers.
"""
from core.channels import Channel, dataset_channel, validated_channel


class TestStrCompat:
    def test_member_equals_value(self):
        assert Channel.CARBON == "carbon_results"
        assert "carbon_results" == Channel.CARBON

    def test_member_hashes_like_value(self):
        assert hash(Channel.CARBON) == hash("carbon_results")

    def test_dict_lookup_works_either_way(self):
        d = {}
        d[Channel.RISK] = 42
        assert d["risk_results"] == 42

        d2 = {"audit_results": "x"}
        assert d2[Channel.AUDIT] == "x"

    def test_str_repr_is_value(self):
        # Logs/JSON shouldn't show "Channel.CARBON" — just the channel name.
        assert str(Channel.CARBON) == "carbon_results"


class TestStableValues:
    """If any of these assertions fails the change is a breaking API."""

    def test_all_channel_values(self):
        assert Channel.DATA_COLLECTION.value == "data_collection_results"
        assert Channel.REGULATORY.value == "regulatory_results"
        assert Channel.CARBON.value == "carbon_results"
        assert Channel.RISK.value == "risk_results"
        assert Channel.AUDIT.value == "audit_results"
        assert Channel.ROI.value == "roi_results"
        assert Channel.REPORT.value == "report_results"
        assert Channel.ACTION.value == "action_results"
        assert Channel.STAKEHOLDER.value == "stakeholder_results"


class TestDynamicChannels:
    def test_validated_channel_format(self):
        assert validated_channel("emissions") == "validated_emissions"

    def test_dataset_channel_format(self):
        assert dataset_channel("supply_chain") == "dataset_supply_chain"

"""Labelling policy: turns household facts into an eligibility outcome with a reason.

Pure and reusable: imports only ``social_support.domain`` (feature 005 trains on these labels).
"""

from social_support.labelling.facts import HouseholdFacts
from social_support.labelling.policy import LabellingPolicy, LabelResult, PolicyError, load_policy

__all__ = ["HouseholdFacts", "LabelResult", "LabellingPolicy", "PolicyError", "load_policy"]

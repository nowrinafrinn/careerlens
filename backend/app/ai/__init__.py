"""Optional AI assistance.

The core app never needs it. A provider only turns a prompt into text; what
that text may claim is decided by the validators here, and anything that
fails them is replaced by the rule engine's result.
"""

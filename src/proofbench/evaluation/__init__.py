"""Evaluation: scoring closed decisions against the evaluator-only oracle.

This is the only package permitted to load oracle material, and it may do so
only after a review subprocess has exited with its decision written. A test walks
the import graph to enforce that (tests/security/test_oracle_boundary.py).
"""

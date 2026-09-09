"""Pydantic request/response models.

These - not the ORM classes - define the API contract. Keeping them separate
means a column rename never silently changes the wire format, and a password
hash can never leak by being on the model.
"""

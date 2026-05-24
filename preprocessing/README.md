# Preprocessing

This package contains the minimal deterministic data-preparation helpers needed
for the research extension layer of the repository.

## Scope

It is responsible for:

- discovering committed raw datasets,
- validating and normalizing schema,
- building deterministic data manifests with checksums,
- computing global train/validation/test split boundaries.

## Current Design Rules

- committed local data only,
- relative paths only,
- deterministic outputs,
- no live downloads,
- no notebook dependency,
- no QuantConnect dependency.

## Intended Output Locations

- `data/processed/manifests/`
- `data/processed/splits/`

The current canonical execution path remains
`python -m strategy_development.local_implementation.reproduce`.

"""
Recommendation engine. Layout:

  scoring.py     pure maths + ranking rules shared by the offline job and the API
                 (no numpy/scipy, so the API process stays slim)
  builder.py     OFFLINE: load orders -> item-item similarity -> write a run -> promote
  evaluation.py  OFFLINE: leave-last-out hit-rate vs a popularity baseline (promote gate)
  serving.py     ONLINE: request-time lookups, eligibility, fallbacks, diversity

builder.py and evaluation.py need numpy/scipy (requirements-reco.txt) and are
imported only by scripts/ and tests — never by the API. See
backend/docs/recommendations.md.
"""

"""Player Modelling Engine — PGN ingestion pipeline.

A self-contained subsystem that ingests multi-game PGN files, runs Stockfish
analysis on each relevant position, and stores the *raw* per-position results
for later feature extraction. Kept isolated from the main review app (which uses
Postgres); this package uses its own SQLite database, Celery worker and Redis
queue.
"""

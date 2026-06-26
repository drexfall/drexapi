"""Wires the write app + projection into a runnable System.

SingleThreadedRunner processes followers synchronously in-process: a write
through the runner's Projects instance updates the read model before the call
returns. Correct + simple for one process.

Scaling note: multiple FastAPI workers / a separate Celery process each get
their own in-process runner and only project their own writes. For multi-process
fan-out, switch to a pull-based projection (Celery beat draining the leader's
notification log, mirroring the legacy projects.drain_outbox task) or a
multi-process runner. Deferred until horizontal scale is needed.
"""
from functools import lru_cache

from eventsourcing.system import SingleThreadedRunner, System

from .application import Projects
from .config import get_settings
from .projections import ProjectReadModel


@lru_cache
def get_runner() -> SingleThreadedRunner:
	system = System(pipes=[[Projects, ProjectReadModel]])
	runner = SingleThreadedRunner(system, env=get_settings().es_env())
	runner.start()
	return runner


def get_projects_app() -> Projects:
	return get_runner().get(Projects)

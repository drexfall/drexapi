"""System wiring for carousels: write app + projection.

Same in-process SingleThreadedRunner story as es/system.py. The render worker
(pipeline.run_render) is invoked out-of-band (Celery in prod, inline in tests)
and issues commands through this same Carousels instance, so its result events
flow through the projection too.
"""
from functools import lru_cache

from eventsourcing.system import SingleThreadedRunner, System

from es.config import get_settings

from .application import Carousels
from .projections import CarouselReadModel


@lru_cache
def get_runner() -> SingleThreadedRunner:
	system = System(pipes=[[Carousels, CarouselReadModel]])
	runner = SingleThreadedRunner(system, env=get_settings().es_env())
	runner.start()
	return runner


def get_carousels_app() -> Carousels:
	return get_runner().get(Carousels)

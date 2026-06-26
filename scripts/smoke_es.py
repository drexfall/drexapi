"""Smoke test for the event-sourced Project slice. No Django, no DB server.

Run: .venv/bin/python scripts/smoke_es.py
"""
from es.application import ProjectNotFound, Projects
from es.readmodel import InMemoryReadModelStore, set_read_store


def main() -> None:
	set_read_store(InMemoryReadModelStore())  # never touch a live cluster
	app = Projects(env={"PERSISTENCE_MODULE": "eventsourcing.sqlite", "SQLITE_DBNAME": ":memory:"})

	pid = app.create(owner_id="auth0|abc", name="My First Project", description="hi", metadata={"k": 1})
	p = app.get(pid)
	assert p.slug == "my-first-project", p.slug
	assert p.status == "provisioning", p.status
	assert p.owner_id == "auth0|abc"

	app.mark_ready(pid)
	assert app.get(pid).status == "ready"

	app.update(pid, {"name": "Renamed", "description": None})
	p = app.get(pid)
	assert p.name == "Renamed", p.name
	assert p.description == "hi", "None change must be ignored"

	app.delete(pid)
	assert app.get(pid).status == "deleting"

	# event history proves it is truly event-sourced (rebuilt from the log)
	stored = list(app.repository.event_store.get(pid))
	names = [type(e).__name__ for e in stored]
	assert names == ["Created", "Provisioned", "Updated", "Deleted"], names

	try:
		app.get("not-a-real-id")
	except ProjectNotFound:
		pass
	else:  # pragma: no cover
		raise AssertionError("expected ProjectNotFound")

	print("OK — events:", names)


if __name__ == "__main__":
	main()

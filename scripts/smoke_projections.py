"""Smoke test for slice 2 — projections + read model + list + slug uniqueness.

Runs the full System (write app + projection follower) on in-memory sqlite with
an in-memory read store. No Mongo, no live cluster.

Run: PYTHONPATH=. .venv/bin/python scripts/smoke_projections.py
"""
import os

# Force in-memory event store before the runner is built.
os.environ["PERSISTENCE_MODULE"] = "eventsourcing.sqlite"
os.environ["SQLITE_DBNAME"] = ":memory:"

from es.application import Projects  # noqa: E402
from es.readmodel import InMemoryReadModelStore, get_read_store, set_read_store  # noqa: E402
from es.system import get_runner  # noqa: E402


def main() -> None:
	set_read_store(InMemoryReadModelStore())
	app: Projects = get_runner().get(Projects)
	store = get_read_store()

	# create -> projection writes read doc synchronously
	pid = app.create(owner_id="auth0|alice", name="Launch Plan", description="d", metadata={"a": 1})
	doc = store.get(str(pid))
	assert doc is not None, "projection did not write read model"
	assert doc["slug"] == "launch-plan", doc["slug"]
	assert doc["status"] == "provisioning", doc["status"]
	assert doc["owner_id"] == "auth0|alice"
	# owner auto-admin
	assert doc["members"] == [{"user_id": "auth0|alice", "role": "admin"}], doc["members"]
	assert store.get_role(str(pid), "auth0|alice") == "admin"

	# provision -> status flips in read model
	app.mark_ready(pid)
	assert store.get(str(pid))["status"] == "ready"

	# update -> read model patched, None ignored
	app.update(pid, {"name": "Launch Plan v2", "description": None})
	doc = store.get(str(pid))
	assert doc["name"] == "Launch Plan v2", doc["name"]
	assert doc["description"] == "d"

	# slug uniqueness via read model
	pid2 = app.create(owner_id="auth0|alice", name="Launch Plan")
	assert store.get(str(pid2))["slug"] == "launch-plan-2", store.get(str(pid2))["slug"]

	# another owner's project not visible to alice
	bob_pid = app.create(owner_id="auth0|bob", name="Bob Thing")

	rows = store.list_for_member("auth0|alice", limit=50, skip=0)
	assert {r["slug"] for r in rows} == {"launch-plan", "launch-plan-2"}, [r["slug"] for r in rows]
	assert rows[0]["created_at"] >= rows[-1]["created_at"]  # newest first

	# --- membership ---
	# bob added as editor on alice's project -> appears in bob's list, role projected
	app.add_member(pid, "auth0|bob", "editor")
	assert store.get_role(str(pid), "auth0|bob") == "editor"
	assert {r["slug"] for r in store.list_for_member("auth0|bob", 50, 0)} == {"launch-plan", "bob-thing"}

	# role change is an upsert (no duplicate member rows)
	app.add_member(pid, "auth0|bob", "admin")
	bob_rows = [m for m in store.get(str(pid))["members"] if m["user_id"] == "auth0|bob"]
	assert bob_rows == [{"user_id": "auth0|bob", "role": "admin"}], bob_rows

	# removing the owner is rejected
	try:
		app.remove_member(pid, "auth0|alice")
	except Exception as exc:
		assert "owner" in str(exc), exc
	else:  # pragma: no cover
		raise AssertionError("expected owner-removal to fail")

	# remove bob -> drops from his list
	app.remove_member(pid, "auth0|bob")
	assert store.get_role(str(pid), "auth0|bob") is None
	assert {r["slug"] for r in store.list_for_member("auth0|bob", 50, 0)} == {"bob-thing"}

	# delete -> read doc removed
	app.delete(pid)
	assert store.get(str(pid)) is None, "deleted project still in read model"
	assert {r["slug"] for r in store.list_for_member("auth0|alice", 50, 0)} == {"launch-plan-2"}

	print("OK — projection + list + slug-uniqueness + membership/roles verified")


if __name__ == "__main__":
	main()

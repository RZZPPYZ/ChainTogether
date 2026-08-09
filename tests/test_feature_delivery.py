from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from server.database import Database


class FeatureDeliverySchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.temp.name) / "feature-delivery.db"))
        await self.db.initialize()
        self.now = "2026-08-02T00:00:00+00:00"
        await self.db.save_agent(
            agent_id="agent-owner",
            name="Owner",
            created_at=self.now,
            updated_at=self.now,
        )
        await self.db.save_session(
            "group-session",
            "Feature group",
            self.temp.name,
            self.now,
            origin="group",
        )
        await self.db.create_group(
            "group-1",
            "Feature group",
            "group-session",
            self.now,
            ["agent-owner"],
            default_agent_id="agent-owner",
            working_dir=self.temp.name,
        )
        await self.db.create_feature_run(
            run_id="run-1",
            feature_id="F001",
            group_id="group-1",
            working_dir=self.temp.name,
            feature_doc_path="docs/features/F001/feature.md",
            title="Feature delivery schema",
            stage="discovery",
            state="active",
            priority="P1",
            owner_agent_id="agent-owner",
            current_gate=None,
            operator_quote="ship it",
            origin_message_seq=None,
            artifact_refs=[],
            created_at=self.now,
        )

    async def asyncTearDown(self) -> None:
        await self.db.close()
        self.temp.cleanup()

    async def _columns(self, table: str) -> set[str]:
        cursor = await self.db._conn.execute(f"PRAGMA table_info({table})")
        return {str(row[1]) for row in await cursor.fetchall()}

    async def _insert_dispatch(
        self,
        dispatch_id: str,
        state: str,
        generation: int,
        *,
        purpose: str = "stage",
        predecessor_id: str | None = None,
    ) -> None:
        await self.db._conn.execute(
            "INSERT INTO feature_dispatches "
            "(id, feature_run_id, observed_stage, observed_revision, purpose, "
            " generation, target_role, target_agent_id, predecessor_dispatch_id, "
            " state, capability_hash, attempt_count, created_at, updated_at) "
            "VALUES (?, 'run-1', 'discovery', 'revision-1', ?, ?, 'owner', "
            " 'agent-owner', ?, ?, ?, 0, ?, ?)",
            (
                dispatch_id,
                purpose,
                generation,
                predecessor_id,
                state,
                f"hash-{dispatch_id}",
                self.now,
                self.now,
            ),
        )
        await self.db._conn.commit()

    async def test_i2_i3_start_checkpoint_schema_and_request_key_are_durable(
        self,
    ) -> None:
        columns = await self._columns("feature_start_requests")
        self.assertEqual(
            {
                "request_key",
                "group_id",
                "feature_run_id",
                "requirement",
                "requirement_hash",
                "authorization",
                "state",
                "error",
                "created_at",
                "updated_at",
            },
            columns,
        )
        await self.db._conn.execute(
            "INSERT INTO feature_start_requests "
            "(request_key, group_id, feature_run_id, requirement, "
            " requirement_hash, authorization, state, created_at, updated_at) "
            "VALUES ('request-1', 'group-1', 'run-1', 'ship it', 'hash', "
            " '{}', 'running', ?, ?)",
            (self.now, self.now),
        )
        await self.db._conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db._conn.execute(
                "INSERT INTO feature_start_requests "
                "(request_key, group_id, feature_run_id, requirement, "
                " requirement_hash, authorization, state, created_at, updated_at) "
                "VALUES ('request-1', 'group-1', 'run-1', 'duplicate', 'hash', "
                " '{}', 'running', ?, ?)",
                (self.now, self.now),
            )
        await self.db._conn.rollback()

    async def test_i6_i7_dispatch_schema_and_partial_indexes_enforce_pair(self) -> None:
        columns = await self._columns("feature_dispatches")
        required = {
            "id",
            "feature_run_id",
            "observed_stage",
            "observed_revision",
            "purpose",
            "generation",
            "target_role",
            "target_agent_id",
            "predecessor_dispatch_id",
            "state",
            "lease_owner",
            "lease_token_hash",
            "lease_expires_at",
            "capability_hash",
            "invocation_id",
            "attempt_count",
            "error",
            "created_at",
            "updated_at",
        }
        self.assertTrue(required.issubset(columns))

        await self._insert_dispatch("dispatch-pending", "pending", 1)
        with self.assertRaises(sqlite3.IntegrityError):
            await self._insert_dispatch("dispatch-waiting", "waiting", 2)
        await self.db._conn.rollback()

        await self.db._conn.execute(
            "UPDATE feature_dispatches SET state = 'completed' WHERE id = ?",
            ("dispatch-pending",),
        )
        await self.db._conn.commit()
        await self._insert_dispatch("dispatch-active", "active", 2)
        with self.assertRaises(sqlite3.IntegrityError):
            await self._insert_dispatch("dispatch-leased", "leased", 3)
        await self.db._conn.rollback()

        with self.assertRaises(sqlite3.IntegrityError):
            await self._insert_dispatch("dispatch-invalid", "unknown", 4)
        await self.db._conn.rollback()

    async def test_i7_invocation_link_is_bound_to_one_dispatch_generation(self) -> None:
        columns = await self._columns("feature_invocation_links")
        self.assertIn("dispatch_id", columns)
        for invocation_id in ("invocation-1", "invocation-2"):
            await self.db._conn.execute(
                "INSERT INTO group_invocations "
                "(id, group_id, root_content, status, custody_state, depth, "
                " created_at, updated_at) "
                "VALUES (?, 'group-1', 'feature turn', 'running', 'new', 0, ?, ?)",
                (invocation_id, self.now, self.now),
            )
        await self._insert_dispatch("dispatch-linked", "active", 1)
        await self.db._conn.execute(
            "INSERT INTO feature_invocation_links "
            "(invocation_id, feature_run_id, dispatch_id) "
            "VALUES ('invocation-1', 'run-1', 'dispatch-linked')"
        )
        await self.db._conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.db._conn.execute(
                "INSERT INTO feature_invocation_links "
                "(invocation_id, feature_run_id, dispatch_id) "
                "VALUES ('invocation-2', 'run-1', 'dispatch-linked')"
            )
        await self.db._conn.rollback()


class FeatureDeliveryMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_doc_outbox_migrates_to_update_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "legacy.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "CREATE TABLE feature_doc_syncs ("
                "feature_run_id TEXT PRIMARY KEY, feature_doc_path TEXT NOT NULL, "
                "content TEXT NOT NULL, base_hash TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO feature_doc_syncs VALUES "
                "('legacy-run', 'feature.md', 'content', 'hash', 'now')"
            )
            connection.commit()
            connection.close()

            db = Database(str(db_path))
            await db.initialize()
            try:
                cursor = await db._conn.execute(
                    "SELECT sync_mode FROM feature_doc_syncs "
                    "WHERE feature_run_id = 'legacy-run'"
                )
                self.assertEqual(("update",), await cursor.fetchone())
            finally:
                await db.close()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest import mock

from fastapi import HTTPException

from server.models import (
    FeatureDeliveryRolesRequest,
    FeatureDeliveryStartRequest,
    FeatureReviewRequest,
    FeatureTransitionRequest,
)
from server.routers import features as feature_routes


class FeatureDeliveryRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.lifecycle = mock.AsyncMock()
        self.delivery = mock.AsyncMock()
        feature_routes.set_feature_manager(self.lifecycle)
        feature_routes.set_feature_delivery_manager(self.delivery)

    async def test_operator_start_resume_and_roles_routes_delegate(self) -> None:
        self.delivery.start.return_value = {"run": {"id": "run-1"}}
        started = await feature_routes.start_feature_delivery(
            "group-1",
            FeatureDeliveryStartRequest(
                request_key="request-1", requirement="Build the feature"
            ),
            _="bearer",
        )
        self.assertEqual("run-1", started["run"]["id"])
        self.delivery.start.assert_awaited_once_with(
            "group-1",
            request_key="request-1",
            requirement="Build the feature",
            priority="P1",
            origin_message_seq=None,
        )

        self.delivery.resume.return_value = {"run": {"id": "run-1"}}
        await feature_routes.resume_feature_delivery(
            "group-1", _="bearer"
        )
        self.delivery.resume_for_group.assert_awaited_once_with("group-1")

        request = FeatureDeliveryRolesRequest(
            owner_agent_id="owner",
            reviewer_agent_id="reviewer",
            vision_guardian_agent_id="guardian",
        )
        self.delivery.update_roles_for_group.return_value = {
            "run": {"id": "run-1"}
        }
        await feature_routes.update_feature_delivery_roles(
            "group-1", request, _="bearer"
        )
        self.delivery.update_roles_for_group.assert_awaited_once()

    async def test_session_status_requires_capability(self) -> None:
        with mock.patch.object(
            feature_routes.session_manager,
            "verify_session_capability",
            return_value=False,
        ):
            with self.assertRaises(HTTPException) as caught:
                await feature_routes.get_feature_delivery_status_for_session(
                    "session-1",
                    "run-1",
                    session_capability="wrong",
                    _="bearer",
                )
        self.assertEqual(403, caught.exception.status_code)

        self.delivery.status.return_value = {"feature_id": "F002"}
        with mock.patch.object(
            feature_routes.session_manager,
            "verify_session_capability",
            return_value=True,
        ):
            result = await feature_routes.get_feature_delivery_status_for_session(
                "session-1",
                "run-1",
                session_capability="valid",
                _="bearer",
            )
        self.assertEqual("F002", result["feature_id"])
        self.delivery.status.assert_awaited_with(
            "run-1", actor_session_id="session-1"
        )

    async def test_dispatch_transition_binds_both_capabilities(self) -> None:
        self.lifecycle.transition_for_dispatch.return_value = {
            "id": "run-1",
            "stage": "design",
        }
        self.delivery.status.return_value = {
            "feature_id": "F002",
            "stage": "design",
        }
        with mock.patch.object(
            feature_routes.session_manager,
            "verify_session_capability",
            return_value=True,
        ):
            result = await feature_routes.transition_feature_dispatch(
                "session-1",
                "run-1",
                FeatureTransitionRequest(to_stage="design"),
                session_capability="session-secret",
                dispatch_id="dispatch-1",
                dispatch_capability="dispatch-secret",
                _="bearer",
            )
        self.assertEqual("design", result["stage"])
        self.lifecycle.transition_for_dispatch.assert_awaited_once_with(
            "run-1",
            "session-1",
            dispatch_id="dispatch-1",
            dispatch_capability="dispatch-secret",
            to_stage="design",
            result="",
            reason="",
            evidence_refs=[],
            revision="",
        )

    async def test_request_review_is_owner_to_reviewer_handoff(self) -> None:
        self.lifecycle.request_review_for_dispatch.return_value = {
            "id": "run-1",
            "stage": "review",
        }
        self.delivery.status.return_value = {
            "feature_id": "F002",
            "stage": "review",
        }
        with mock.patch.object(
            feature_routes.session_manager,
            "verify_session_capability",
            return_value=True,
        ):
            await feature_routes.request_feature_review(
                "session-1",
                "run-1",
                FeatureReviewRequest(
                    evidence_refs=["evidence/quality.md"], revision="abc1234"
                ),
                session_capability="session-secret",
                dispatch_id="dispatch-1",
                dispatch_capability="dispatch-secret",
                _="bearer",
            )
        self.lifecycle.request_review_for_dispatch.assert_awaited_once_with(
            "run-1",
            "session-1",
            dispatch_id="dispatch-1",
            dispatch_capability="dispatch-secret",
            reason="SHA-bound review packet is ready for independent review",
            evidence_refs=["evidence/quality.md"],
            revision="abc1234",
        )


if __name__ == "__main__":
    unittest.main()

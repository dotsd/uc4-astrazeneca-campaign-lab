# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Integration tests for AstraZenecaCampaignLabADKAgent session state, V4 signed URLs, and ADK Reasoning Engine."""
from __future__ import annotations

import unittest
from agents.adk_conversational_agent import (
    AstraZenecaCampaignLabADKAgent,
    create_campaign_lab_adk_agent,
    preserve_verified_signed_urls_callback,
    verify_signed_url_preflight,
)
from config.settings import settings
from scripts.deploy_reasoning_engine import AstraZenecaCampaignLabReasoningEngine


class TestAdkAgentIntegration(unittest.TestCase):
    """Verify ADK agent initialization, Gemini 3.1 models, generic campaign state overrides, and preflight helpers."""

    def test_agent_session_initialization_and_state_override(self) -> None:
        agent = AstraZenecaCampaignLabADKAgent(
            session_id="test_uc4_session_01",
            initial_state={
                "campaign_name": "AZD9550",
                "theme_prompt": "astrazeneca_dark",
                "master_strapline": "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
            },
        )
        self.assertEqual(agent.state["campaign_name"], "AZD9550")
        self.assertEqual(agent.state["theme_prompt"], "astrazeneca_dark")
        self.assertEqual(
            agent.state["master_strapline"],
            "TWO DISTINCT PATHWAYS. ONE BALANCED FORCE.",
        )

    def test_gemini_3_models_and_google_adk_framework(self) -> None:
        self.assertEqual(settings.MODEL_TIER, "gemini-3.1-pro-preview")
        self.assertIn("gemini-3.1-pro-preview", settings.llm_model_candidates)
        self.assertEqual(settings.IMAGEN_MODEL, "gemini-3-pro-image")
        self.assertEqual(
            settings.GCS_EXPORT_BUCKET, "astrazeneca-ge-pilot-usecase"
        )
        self.assertEqual(
            settings.STAGING_BUCKET, "gs://astrazeneca-ge-pilot-usecase"
        )
        self.assertEqual(settings.GCS_FOLDER_PREFIX, "UC4")
        self.assertEqual(
            settings.SIGNING_SERVICE_ACCOUNT,
            "project-service-account@gcp-ai-intelligence-dev-0a06.iam.gserviceaccount.com",
        )
        for m in settings.llm_model_candidates + settings.image_model_candidates:
            self.assertNotIn("2.5", m)

        engine = AstraZenecaCampaignLabReasoningEngine()
        self.assertEqual(engine.agent_framework, "google-adk")

        adk_agent = create_campaign_lab_adk_agent()
        self.assertEqual(adk_agent.name, "astrazeneca_campaign_lab")
        self.assertGreaterEqual(len(adk_agent.tools), 10)

    def test_signed_url_preflight_and_callback(self) -> None:
        self.assertFalse(verify_signed_url_preflight(""))
        self.assertFalse(verify_signed_url_preflight("https://example.com/unsigned.png"))
        sample_resp = "Here is your verified deliverable link."
        self.assertEqual(
            preserve_verified_signed_urls_callback(llm_response=sample_resp),
            sample_resp,
        )


if __name__ == "__main__":
    unittest.main()

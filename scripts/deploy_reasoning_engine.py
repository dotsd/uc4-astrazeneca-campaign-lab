#!/usr/bin/env python3
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

"""Deploy & Update AstraZeneca Campaign Lab in Vertex AI Agent Engine (`google-adk`).

Uses `BaseAgent` with `_run_async_impl` (identical to `UC1` `Calquence Campaign Lab`)
so that Gemini 3.1 Pro Preview (`gemini-3.1-pro-preview`) and `gemini-3-pro-image`
are invoked via the `global` Vertex AI endpoint while the Reasoning Engine runs in
`europe-west1`, with native ADK artifact attachment and 7-day V4 Signed URLs.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import vertexai
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from PIL import Image
from vertexai import agent_engines
from vertexai.agent_engines import AdkApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("astrazeneca_campaign_lab.deploy")

CLEAN_AGENT_DESCRIPTION = (
    "Executive Campaign Partner & autonomous pharmaceutical marketing multi-agent system "
    "for AstraZeneca. Powered by Gemini 3.1 Pro and Nano Banana Pro (gemini-3-pro-image) "
    "to generate live 4K campaign visuals, slide decks, agency briefing forms, "
    "vector clinical charts, information pamphlets, and campaign videos."
)


def _ensure_sys_path() -> None:
    """Ensure the root application directory is in sys.path inside the Agent Runtime container."""
    for search_dir in [
        Path("."),
        Path("/code"),
        Path("/code/app"),
        Path("/app"),
    ]:
        if (search_dir / "config" / "settings.py").exists():
            resolved = str(search_dir.resolve())
            if resolved not in sys.path:
                sys.path.insert(0, resolved)
            break
    else:
        for base_root in ("/code", "/app"):
            if not os.path.exists(base_root):
                continue
            for root, _, _ in os.walk(base_root):
                if os.path.exists(os.path.join(root, "config", "settings.py")):
                    if root not in sys.path:
                        sys.path.insert(0, root)
                    break


def _build_gcs_artifact_service():
    """Build the ADK GcsArtifactService backed by `gs://astrazeneca-ge-pilot-usecase`."""
    from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService

    artifact_uri = os.environ.get(
        "ARTIFACT_SERVICE_URI", "gs://astrazeneca-ge-pilot-usecase"
    )
    bucket_name = artifact_uri.replace("gs://", "").strip("/").split("/")[0]
    try:
        return GcsArtifactService(bucket_name=bucket_name)
    except Exception as exc:
        logger.warning(
            "GcsArtifactService fallback to InMemoryArtifactService (%s)", exc
        )
        return InMemoryArtifactService()


def preserve_verified_signed_urls_callback(
    callback_context: Optional[Any] = None,
    llm_response: Optional[Any] = None,
    **kwargs: Any,
) -> Optional[Any]:
    """Post-model callback that delegates to `agents.adk_conversational_agent.preserve_verified_signed_urls_callback`."""
    _ensure_sys_path()
    from agents.adk_conversational_agent import (
        preserve_verified_signed_urls_callback as _impl,
    )

    return _impl(
        callback_context=callback_context,
        llm_response=llm_response,
        **kwargs,
    )


class AstraZenecaCampaignLabBaseAgent(BaseAgent):
    """Google ADK BaseAgent for AstraZeneca Campaign Lab.

    Uses Gemini 3.1 Pro Preview (`gemini-3.1-pro-preview`) on the `global` endpoint,
    Google Search Grounding, and `gemini-3-pro-image` to generate 4K visuals,
    widescreen slide decks, extended A4 pamphlets, vector SVG charts, and HD videos.
    """

    name: str = "astrazeneca_campaign_lab"
    description: str = CLEAN_AGENT_DESCRIPTION
    after_model_callback: Any = preserve_verified_signed_urls_callback

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        _ensure_sys_path()
        user_text = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                if getattr(part, "text", None):
                    user_text += part.text + " "
                elif getattr(part, "inline_data", None) and part.inline_data.data:
                    mime = (part.inline_data.mime_type or "").lower()
                    if "pdf" in mime:
                        try:
                            from pypdf import PdfReader

                            reader = PdfReader(io.BytesIO(part.inline_data.data))
                            pdf_text = "\n".join(
                                page.extract_text() or "" for page in reader.pages[:20]
                            )
                            user_text += (
                                f"\n[Uploaded PDF Document Content]:\n{pdf_text[:10000]}\n"
                            )
                        except Exception as exc:
                            logger.warning("PDF inline extraction warning: %s", exc)
        user_text = user_text.strip() or "Hello"

        session_id = getattr(ctx.session, "id", "default") or "default"
        user_id = (
            getattr(ctx, "user_id", None)
            or getattr(ctx.session, "user_id", "default_user")
            or "default_user"
        )
        app_name = getattr(ctx, "app_name", "app") or "app"
        initial_state = dict(getattr(ctx.session, "state", {}) or {})

        from agents.adk_conversational_agent import (
            AstraZenecaCampaignLabADKAgent,
            _infer_mime_type,
            backfill_gcs_native_artifact,
            prepare_inline_preview_bytes,
        )
        from config.settings import get_settings

        runtime_settings = get_settings()
        runtime_settings.output_dir.mkdir(parents=True, exist_ok=True)
        runtime_settings.uploads_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "ADK invocation started | session_id=%s | user_id=%s | user_text_len=%d",
            session_id,
            user_id,
            len(user_text),
        )
        event_actions = EventActions(state_delta={}, artifact_delta={})
        cb_ctx = CallbackContext(ctx, event_actions=event_actions)

        agent = AstraZenecaCampaignLabADKAgent(
            session_id=session_id,
            initial_state=initial_state,
            tool_context=cb_ctx,
        )
        result = agent.interact(user_text, tool_context=cb_ctx)
        response_text = result.get("response", "")

        updated_state = result.get("state", {})
        state_delta = {
            "campaign_name": updated_state.get("campaign_name"),
            "theme_prompt": updated_state.get("theme_prompt"),
            "master_strapline": updated_state.get("master_strapline"),
            "video_length_mode": updated_state.get("video_length_mode"),
            "last_deliverables": updated_state.get("last_deliverables", {}),
            "verified_signed_urls": updated_state.get("verified_signed_urls", {}),
            "history": updated_state.get("history", [])[-10:],
        }
        event_actions.state_delta.update(state_delta)

        # Attach every generated deliverable as a native ADK artifact + zero-byte GCS backfill
        turn_artifacts = result.get("turn_artifacts", {}) or {}
        for _, local_path_str in turn_artifacts.items():
            file_path = Path(local_path_str)
            if not file_path.exists():
                continue
            filename = file_path.name
            content_type = _infer_mime_type(file_path)
            payload_bytes = prepare_inline_preview_bytes(file_path)
            part = types.Part.from_bytes(
                data=payload_bytes, mime_type=content_type
            )
            version = event_actions.artifact_delta.get(filename, 0)
            if filename not in event_actions.artifact_delta:
                try:
                    version = await cb_ctx.save_artifact(filename, part)
                except Exception as art_err:
                    logger.debug(
                        "ADK save_artifact fallback for %s: %s", filename, art_err
                    )
                    version = 0
                    event_actions.artifact_delta[filename] = version

            backfill_gcs_native_artifact(
                payload_bytes=payload_bytes,
                content_type=content_type,
                filename=filename,
                version=version,
                session_id=session_id,
                user_id=user_id,
                app_name=app_name,
            )

        if self.after_model_callback:
            response_text = self.after_model_callback(
                callback_context=cb_ctx,
                llm_response=response_text,
            )

        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(
                role="model",
                parts=[types.Part(text=response_text)],
            ),
            actions=event_actions,
        )


root_agent = AstraZenecaCampaignLabBaseAgent(
    after_model_callback=preserve_verified_signed_urls_callback
)


class AstraZenecaCampaignLabReasoningEngine(AdkApp):
    """Vertex AI Agent Engine (`google-adk`) with OpenTelemetry, Cloud Logging & GcsArtifactService."""

    agent_framework: str = "google-adk"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "agent" not in kwargs and "app" not in kwargs and not args:
            kwargs["agent"] = AstraZenecaCampaignLabBaseAgent(
                after_model_callback=preserve_verified_signed_urls_callback
            )
        kwargs.setdefault("app_name", "app")
        kwargs.setdefault("enable_tracing", True)
        kwargs.setdefault(
            "artifact_service_builder", _build_gcs_artifact_service
        )
        super().__init__(*args, **kwargs)
        self.agent_framework = "google-adk"

    def set_up(self) -> None:
        """Initialize runtime directories, Cloud Logging, OpenTelemetry, and GcsArtifactService."""
        _ensure_sys_path()
        os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true")
        os.environ.setdefault(
            "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED", "true"
        )
        os.environ.setdefault(
            "ARTIFACT_SERVICE_URI", "gs://astrazeneca-ge-pilot-usecase"
        )
        try:
            import google.cloud.logging as gcp_logging

            client = gcp_logging.Client()
            client.setup_logging()
        except Exception as log_exc:
            logger.debug("Cloud Logging client fallback to standard stdout: %s", log_exc)

        super().set_up()
        from config.settings import get_settings

        runtime_settings = get_settings()
        runtime_settings.output_dir.mkdir(parents=True, exist_ok=True)
        runtime_settings.uploads_dir.mkdir(parents=True, exist_ok=True)

    def register_operations(self) -> Dict[str, List[str]]:
        """Register both ADK streaming operations and standard synchronous query."""
        ops = super().register_operations()
        if "" not in ops:
            ops[""] = []
        if "query" not in ops[""]:
            ops[""].append("query")
        return ops

    def query(
        self,
        prompt: Optional[str] = "Hello",
        campaign_name: str = "AZD9550 Dual Agonist",
        theme_prompt: str = "astrazeneca_light",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute synchronous query for direct Python SDK callers."""
        _ensure_sys_path()
        from agents.adk_conversational_agent import AstraZenecaCampaignLabADKAgent

        agent = AstraZenecaCampaignLabADKAgent(
            initial_state={
                "campaign_name": campaign_name,
                "theme_prompt": theme_prompt,
            }
        )
        result = agent.chat(prompt or "Hello")
        return {
            "status": "success",
            "agent_name": "astrazeneca_campaign_lab",
            "agent_framework": "google-adk",
            "service_name": "AstraZeneca Campaign Lab",
            "response": result.get("response", ""),
            "deliverables": result.get("deliverables", {}),
        }


def patch_reasoning_engine_framework_and_telemetry(
    resource_name: str,
    env_vars: Dict[str, str],
) -> None:
    """Explicitly patch `spec.agent_framework = 'google-adk'` and telemetry env vars."""
    from config.settings import get_settings
    from google.cloud.aiplatform_v1beta1 import (
        ReasoningEngine as GapicReasoningEngine,
        ReasoningEngineServiceClient,
        ReasoningEngineSpec,
        UpdateReasoningEngineRequest,
    )
    from google.protobuf import field_mask_pb2

    settings = get_settings()
    location = settings.google_cloud_location
    client = ReasoningEngineServiceClient(
        client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"}
    )
    env_entries = [{"name": k, "value": str(v)} for k, v in env_vars.items()]
    re_proto = GapicReasoningEngine(
        name=resource_name,
        spec=ReasoningEngineSpec(
            agent_framework="google-adk",
            deployment_spec=ReasoningEngineSpec.DeploymentSpec(env=env_entries),
        ),
    )
    update_mask = field_mask_pb2.FieldMask(
        paths=["spec.agent_framework", "spec.deployment_spec.env"]
    )
    logger.info(
        "Patching ReasoningEngine metadata (%s) -> spec.agent_framework='google-adk' & telemetry=true",
        resource_name,
    )
    operation = client.update_reasoning_engine(
        request=UpdateReasoningEngineRequest(
            reasoning_engine=re_proto,
            update_mask=update_mask,
        )
    )
    operation.result(timeout=600)
    logger.info(
        "Verified GCP Agent Runtime metadata patch: framework='google-adk', telemetry='true'"
    )


def register_agent_in_gemini_enterprise(
    reasoning_engine_resource_name: str,
    display_name: str = "AstraZeneca Campaign Lab",
    description: str = CLEAN_AGENT_DESCRIPTION,
) -> None:
    """Register or update `AstraZeneca Campaign Lab` in Gemini Enterprise with the AstraZeneca Symbol icon."""
    import google.auth
    from google.auth.transport.requests import Request
    from agents.adk_conversational_agent import upload_to_gcs
    from config.settings import get_settings
    from tools.logo_tools import ensure_astrazeneca_logo_assets, render_svg_to_png

    settings = get_settings()
    project_number = settings.google_cloud_project_number
    app_id = settings.gemini_enterprise_engine_id

    logger.info(
        "Registering / updating '%s' in Gemini Enterprise App (%s)...",
        display_name,
        app_id,
    )

    icon_b64 = ""
    svg_b64 = ""
    svg_data_uri = ""
    png_data_uri = ""
    bucket_clean = (
        settings.gcs_assets_bucket.replace("gs://", "").strip("/").split("/")[0]
    )
    uc4_prefix = (settings.gcs_folder_prefix or "UC4").strip("/")
    symbol_gcs_url = (
        f"https://storage.googleapis.com/{bucket_clean}/{uc4_prefix}/"
        "astrazeneca_campaign_lab/brand_icons/astrazeneca_symbol_gold.png"
    )

    try:
        svg_symbol_path = settings.logos_dir / "AstraZeneca symbol.svg"
        png_symbol_path = settings.logos_dir / "astrazeneca_symbol_gold.png"
        if svg_symbol_path.exists():
            svg_raw = svg_symbol_path.read_bytes()
            svg_b64 = base64.b64encode(svg_raw).decode("ascii")
            svg_data_uri = f"data:image/svg+xml;base64,{svg_b64}"
            render_svg_to_png(
                svg_symbol_path,
                png_symbol_path,
                dpi=600,
                color_overrides=["#f0ab00"],
            )
        logos = ensure_astrazeneca_logo_assets()
        sym_path = (
            png_symbol_path
            if png_symbol_path.exists()
            else logos.get("png_symbol_gold")
        )
        if sym_path and sym_path.exists():
            with Image.open(sym_path) as im:
                im = im.convert("RGBA")
                sq = Image.new("RGBA", (128, 128), (255, 255, 255, 0))
                im.thumbnail((112, 112), Image.Resampling.LANCZOS)
                sq.paste(
                    im,
                    ((128 - im.width) // 2, (128 - im.height) // 2),
                    im,
                )
                buf = io.BytesIO()
                sq.save(buf, format="PNG", optimize=True)
                icon_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                png_data_uri = f"data:image/png;base64,{icon_b64}"
    except Exception as icon_exc:
        logger.warning("Local agent icon preparation note: %s", icon_exc)

    try:
        logos = ensure_astrazeneca_logo_assets()
        for p in logos.values():
            if p and p.exists():
                upload_to_gcs(p, session_id="global", folder_prefix="brand_icons")
        sym_path = logos.get("png_symbol_gold")
        if sym_path and sym_path.exists():
            symbol_gcs_url = upload_to_gcs(
                sym_path, session_id="global", folder_prefix="brand_icons"
            )
    except Exception as gcs_exc:
        logger.debug("GCS brand icon upload note: %s", gcs_exc)

    token = ""
    try:
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(Request())
        token = creds.token or ""
    except Exception:
        for cmd in [
            ["gcloud", "auth", "application-default", "print-access-token"],
            ["gcloud", "auth", "print-access-token"],
        ]:
            try:
                out = (
                    subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                    .decode("utf-8")
                    .strip()
                )
                if out:
                    token = out
                    break
            except Exception:
                continue

    if not token:
        logger.warning("Could not load token for Gemini Enterprise registration.")
        return

    icon_candidates = []
    if png_data_uri:
        icon_candidates.append(
            ("icon (content='data:image/png;base64,...')", {"content": png_data_uri})
        )
    if svg_data_uri:
        icon_candidates.append(
            (
                "icon (content='data:image/svg+xml;base64,...')",
                {"content": svg_data_uri},
            )
        )
    if png_data_uri:
        icon_candidates.append(("icon (PNG data URI)", {"uri": png_data_uri}))
    icon_candidates.append(("icon (V4 Signed GCS HTTPS URI)", {"uri": symbol_gcs_url}))

    for loc in ["eu", "global"]:
        base_prefix = f"{loc}-" if loc != "global" else ""
        agents_url = (
            f"https://{base_prefix}discoveryengine.googleapis.com/v1alpha/"
            f"projects/{project_number}/locations/{loc}/collections/default_collection/"
            f"engines/{app_id}/assistants/default_assistant/agents"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": project_number,
        }
        try:
            req = urllib.request.Request(agents_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                agents_list = data.get("agents", [])
                updated_existing = False
                for ag in agents_list:
                    ag_name = ag.get("name", "")
                    re_cfg = (
                        ag.get("adkAgentDefinition", {})
                        .get("provisionedReasoningEngine", {})
                        .get("reasoningEngine", "")
                    )
                    if (
                        (reasoning_engine_resource_name and reasoning_engine_resource_name in re_cfg)
                        or ag.get("displayName") == display_name
                        or "84099737022232589" in ag_name
                    ):
                        primary_icon = (
                            icon_candidates[0][1]
                            if icon_candidates
                            else {"uri": symbol_gcs_url}
                        )
                        for mask in [
                            "displayName,description,icon,adkAgentDefinition.toolSettings.toolDescription",
                            "displayName,description,adkAgentDefinition.toolSettings.toolDescription",
                            "displayName,description",
                        ]:
                            try:
                                patch_url = (
                                    f"https://{base_prefix}discoveryengine.googleapis.com/v1alpha/"
                                    f"{ag_name}?updateMask={mask}"
                                )
                                patch_body: Dict[str, Any] = {
                                    "displayName": display_name,
                                    "description": description,
                                    "icon": primary_icon,
                                    "adkAgentDefinition": {
                                        "toolSettings": {
                                            "toolDescription": description
                                        },
                                        "provisionedReasoningEngine": {
                                            "reasoningEngine": reasoning_engine_resource_name
                                        },
                                    },
                                }
                                patch_req = urllib.request.Request(
                                    patch_url,
                                    data=json.dumps(patch_body).encode("utf-8"),
                                    headers=headers,
                                    method="PATCH",
                                )
                                with urllib.request.urlopen(
                                    patch_req, timeout=15
                                ) as presp:
                                    presp_data = json.loads(
                                        presp.read().decode("utf-8")
                                    )
                                    logger.info(
                                        "Updated existing Gemini Enterprise Agent in (%s): %s -> '%s' (mask=%s, returned_icon_keys=%s)",
                                        loc,
                                        ag_name,
                                        display_name,
                                        mask,
                                        list((presp_data.get("icon") or {}).keys()),
                                    )
                                    updated_existing = True
                                    break
                            except Exception as mask_err:
                                logger.warning(
                                    "PATCH mask=%s on %s note: %s",
                                    mask,
                                    ag_name,
                                    mask_err,
                                )

                        for label, icon_payload in icon_candidates:
                            try:
                                icon_patch_url = (
                                    f"https://{base_prefix}discoveryengine.googleapis.com/v1alpha/"
                                    f"{ag_name}?updateMask=icon"
                                )
                                icon_patch_req = urllib.request.Request(
                                    icon_patch_url,
                                    data=json.dumps(
                                        {
                                            "name": ag_name,
                                            "displayName": display_name,
                                            "icon": icon_payload,
                                        }
                                    ).encode("utf-8"),
                                    headers=headers,
                                    method="PATCH",
                                )
                                with urllib.request.urlopen(
                                    icon_patch_req, timeout=15
                                ) as iresp:
                                    iresp_data = json.loads(
                                        iresp.read().decode("utf-8")
                                    )
                                    saved_icon = iresp_data.get("icon") or {}
                                    if saved_icon.get("uri") or saved_icon.get(
                                        "content"
                                    ):
                                        logger.info(
                                            "Verified Gemini Enterprise Agent Icon persisted via %s",
                                            label,
                                        )
                                        break
                            except Exception:
                                continue

                if not updated_existing:
                    post_body: Dict[str, Any] = {
                        "displayName": display_name,
                        "description": description,
                        "state": "ENABLED",
                        "sharingConfig": {"scope": "ALL_USERS"},
                        "adkAgentDefinition": {
                            "toolSettings": {"toolDescription": description},
                            "provisionedReasoningEngine": {
                                "reasoningEngine": reasoning_engine_resource_name
                            },
                        },
                    }
                    if icon_candidates:
                        post_body["icon"] = icon_candidates[0][1]
                    post_req = urllib.request.Request(
                        agents_url,
                        data=json.dumps(post_body).encode("utf-8"),
                        headers=headers,
                        method="POST",
                    )
                    with urllib.request.urlopen(post_req, timeout=15) as cresp:
                        created = json.loads(cresp.read().decode("utf-8"))
                        logger.info(
                            "Registered new Gemini Enterprise Agent in (%s): %s ('%s')",
                            loc,
                            created.get("name"),
                            display_name,
                        )
        except Exception as ge_err:
            logger.info("Gemini Enterprise endpoint (%s) status: %s", loc, ge_err)


def deploy(
    project_id: Optional[str] = None,
    icon_only: bool = False,
    artifact_service_uri: Optional[str] = None,
):
    """Deploy or update the AstraZeneca Campaign Lab ADK Agent Engine in-place."""
    from config.settings import get_settings

    settings = get_settings()
    display_name = "AstraZeneca Campaign Lab"
    description = CLEAN_AGENT_DESCRIPTION

    existing_re = (
        settings.existing_reasoning_engine_id
        or "projects/726684663091/locations/europe-west1/reasoningEngines/5973077126683820032"
    )
    project_id = project_id or settings.google_cloud_project
    location = settings.google_cloud_location or "europe-west1"
    artifact_uri = (
        artifact_service_uri
        or settings.artifact_service_uri
        or "gs://astrazeneca-ge-pilot-usecase"
    )
    staging_bucket = settings.gcs_staging_bucket or artifact_uri
    os.environ["ARTIFACT_SERVICE_URI"] = artifact_uri

    logger.info(
        "Initializing Vertex AI: project=%s, location=%s, staging_bucket=%s, artifact_service_uri=%s",
        project_id,
        location,
        staging_bucket,
        artifact_uri,
    )
    vertexai.init(
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
    )

    register_agent_in_gemini_enterprise(existing_re, display_name, description)
    if icon_only:
        logger.info("Completed --icon-only Gemini Enterprise Agent update.")
        return None

    engine_instance = AstraZenecaCampaignLabReasoningEngine()

    requirements = [
        "google-cloud-aiplatform[adk,agent_engines]>=1.88.0",
        "google-adk>=1.5.0",
        "google-cloud-storage>=2.14.0",
        "google-cloud-logging>=3.10.0",
        "google-cloud-texttospeech>=2.21.0",
        "google-genai>=2.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.1",
        "reportlab>=4.0.0",
        "python-docx>=1.1.0",
        "pillow>=10.0.0",
        "matplotlib>=3.8.0",
        "numpy>=2.0.0",
        "pypdf>=4.0.0",
        "httpx>=0.27.0",
        "cloudpickle>=3.0.0",
        "opentelemetry-sdk>=1.25.0",
        "opentelemetry-exporter-gcp-trace>=1.6.0",
        "opentelemetry-exporter-gcp-monitoring>=1.6.0",
        "opentelemetry-exporter-gcp-logging>=1.0.0",
        "opentelemetry-exporter-otlp-proto-http>=1.0.0",
    ]

    extra_packages = [
        "agents",
        "config",
        "tools",
        "assets",
    ]

    env_vars = {
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED": "true",
        "STAGING_BUCKET": staging_bucket,
        "GCS_STAGING_BUCKET": staging_bucket,
        "GCS_EXPORT_BUCKET": settings.gcs_assets_bucket,
        "GCS_ASSETS_BUCKET": settings.gcs_assets_bucket,
        "ARTIFACT_SERVICE_URI": artifact_uri,
        "GCS_FOLDER_PREFIX": settings.gcs_folder_prefix,
        "SIGNING_SERVICE_ACCOUNT": settings.signing_service_account,
        "MODEL_TIER": settings.MODEL_TIER,
        "FALLBACK_MODEL_TIER": settings.FALLBACK_MODEL_TIER,
        "IMAGEN_MODEL": settings.IMAGEN_MODEL,
        "ENABLE_GOOGLE_GROUNDING": "true",
        "ENABLE_DATASTORE": "false",
        "SERVICE_NAME": display_name,
    }

    logger.info(
        "Updating existing Agent Engine IN-PLACE via vertexai.agent_engines: %s",
        existing_re,
    )
    remote_engine = agent_engines.update(
        resource_name=existing_re,
        agent_engine=engine_instance,
        requirements=requirements,
        extra_packages=extra_packages,
        display_name=display_name,
        description=description,
        env_vars=env_vars,
    )
    patch_reasoning_engine_framework_and_telemetry(
        remote_engine.resource_name, env_vars
    )
    logger.info(
        "Successfully UPDATED Agent Engine in-place with Framework='google-adk' & Telemetry=Enabled: %s",
        remote_engine.resource_name,
    )
    register_agent_in_gemini_enterprise(
        remote_engine.resource_name, display_name, description
    )
    return remote_engine


if __name__ == "__main__":
    cli_artifact_uri = None
    for arg in sys.argv[1:]:
        if arg.startswith("--artifact_service_uri="):
            cli_artifact_uri = arg.split("=", 1)[1].strip("\"'")
    deploy(
        icon_only="--icon-only" in sys.argv,
        artifact_service_uri=cli_artifact_uri,
    )

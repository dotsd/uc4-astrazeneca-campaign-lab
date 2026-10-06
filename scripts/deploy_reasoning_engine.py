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

"""Deploy & Update AstraZeneca Campaign Lab (UC4) in Vertex AI Agent Engine (`google-adk`).

Unified Storage (`gs://astrazeneca-ge-pilot-usecase/UC4/`), Native In-Chat Artifact
Attachment with GCS Zero-Byte Backfill (`gs://astrazeneca-ge-pilot-usecase/app/`),
Google Search Grounding, Dynamic Brand Theme Engine, and Verified 7-Day V4 Signed URLs.
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
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import vertexai
from PIL import Image
from vertexai import agent_engines
from vertexai.agent_engines import AdkApp

from agents.adk_conversational_agent import (
    AstraZenecaCampaignLabADKAgent,
    create_campaign_lab_adk_agent,
    upload_to_gcs,
)
from config.settings import get_settings
from tools.logo_tools import ensure_astrazeneca_logo_assets, render_svg_to_png

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("astrazeneca_campaign_lab.deploy")


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


class AstraZenecaCampaignLabReasoningEngine(AdkApp):
    """Vertex AI Agent Engine (`google-adk`) for AstraZeneca Campaign Lab (UC4)."""

    agent_framework: str = "google-adk"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "agent" not in kwargs and "app" not in kwargs and not args:
            kwargs["agent"] = create_campaign_lab_adk_agent()
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
        prompt: Optional[str] = "Generate a campaign slide deck and look and feel",
        campaign_name: str = "Strategic Campaign",
        theme_prompt: str = "astrazeneca_light",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute synchronous query for direct Python SDK callers."""
        _ensure_sys_path()
        agent = AstraZenecaCampaignLabADKAgent(
            initial_state={
                "campaign_name": campaign_name,
                "theme_prompt": theme_prompt,
            }
        )
        result = agent.chat(prompt or "Generate a campaign slide deck and look and feel")
        return {
            "status": "success",
            "agent_name": "astrazeneca_campaign_lab",
            "agent_framework": "google-adk",
            "service_name": "AstraZeneca Campaign Lab",
            "response": result.get("response", ""),
            "deliverables": result.get("deliverables", {}),
            "gcs_uploads": result.get("gcs_uploads", {}),
        }


def patch_reasoning_engine_framework_and_telemetry(
    resource_name: str,
    env_vars: Dict[str, str],
) -> None:
    """Explicitly patch `spec.agent_framework = 'google-adk'` and telemetry env vars."""
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


def _find_existing_uc4_reasoning_engine(display_name: str) -> str:
    """Discover if `AstraZeneca Campaign Lab` already has a Reasoning Engine in Vertex AI."""
    settings = get_settings()
    if settings.existing_reasoning_engine_id:
        if settings.existing_reasoning_engine_id.startswith("projects/"):
            return settings.existing_reasoning_engine_id
        return (
            f"projects/{settings.google_cloud_project_number}/locations/"
            f"{settings.google_cloud_location}/reasoningEngines/"
            f"{settings.existing_reasoning_engine_id}"
        )

    meta_file = PROJECT_ROOT / "deployment_metadata.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if meta.get("reasoning_engine_resource_name"):
                return meta["reasoning_engine_resource_name"]
        except Exception:
            pass

    try:
        for eng in agent_engines.list():
            if getattr(eng, "display_name", "") == display_name:
                return eng.resource_name
    except Exception as exc:
        logger.debug("ReasoningEngine list lookup note: %s", exc)
    return ""


def _persist_reasoning_engine_id(resource_name: str) -> None:
    """Save the provisioned Reasoning Engine resource name to `deployment_metadata.json` and `.env`."""
    meta_file = PROJECT_ROOT / "deployment_metadata.json"
    meta_file.write_text(
        json.dumps(
            {
                "service_name": "AstraZeneca Campaign Lab",
                "gcs_folder_prefix": "UC4",
                "reasoning_engine_resource_name": resource_name,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        if 'EXISTING_REASONING_ENGINE_ID=""' in content:
            content = content.replace(
                'EXISTING_REASONING_ENGINE_ID=""',
                f'EXISTING_REASONING_ENGINE_ID="{resource_name}"',
            )
            env_file.write_text(content, encoding="utf-8")


def register_agent_in_gemini_enterprise(
    reasoning_engine_resource_name: str,
    display_name: str = "AstraZeneca Campaign Lab",
    description: str = "",
) -> None:
    """Register or update `AstraZeneca Campaign Lab` in Gemini Enterprise with the AstraZeneca Symbol icon."""
    import google.auth
    from google.auth.transport.requests import Request

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

    # 1. Render and encode directly from assets/astrazeneca_logos_svg/AstraZeneca symbol.svg
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

    # 2. Upload brand icons to unified GCS bucket under UC4/ and generate 7-day V4 Signed URL
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

    # 3. Acquire bearer token (ADC first, fallback to gcloud CLI)
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
                    # Strictly match ONLY AstraZeneca Campaign Lab (never touch UC1 Calquence Campaign Lab)
                    if (
                        (reasoning_engine_resource_name and reasoning_engine_resource_name in re_cfg)
                        or ag.get("displayName") == display_name
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
    """Deploy or update the AstraZeneca Campaign Lab (UC4) ADK Agent Engine & register in Gemini Enterprise."""
    settings = get_settings()
    display_name = settings.service_name
    description = (
        "AstraZeneca Campaign Lab (UC4) — Generic multimodal campaign, brand look-and-feel, "
        "and scientific communications studio with Google Search Grounding, custom brand palette "
        "engine (Google 4-color, AstraZeneca Light/Dark, or custom Hex/RGB), 4K slide decks, "
        "extended A4 PDF pamphlets, SVG charts/logos, and short/long 1080p HD videos."
    )

    existing_re = _find_existing_uc4_reasoning_engine(display_name)
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

    if icon_only and existing_re:
        register_agent_in_gemini_enterprise(existing_re, display_name, description)
        logger.info("Completed --icon-only Gemini Enterprise Agent update.")
        return None

    engine_instance = AstraZenecaCampaignLabReasoningEngine()

    requirements = [
        "google-cloud-aiplatform[adk,agent_engines]>=1.88.0",
        "google-adk>=1.0.0",
        "google-cloud-storage>=2.14.0",
        "google-cloud-logging>=3.10.0",
        "google-cloud-texttospeech>=2.21.0",
        "google-genai>=1.10.0",
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
        "GOOGLE_CLOUD_PROJECT": settings.google_cloud_project,
        "GOOGLE_CLOUD_LOCATION": location,
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        "GCS_STAGING_BUCKET": staging_bucket,
        "GCS_ASSETS_BUCKET": settings.gcs_assets_bucket,
        "ARTIFACT_SERVICE_URI": artifact_uri,
        "GCS_FOLDER_PREFIX": settings.gcs_folder_prefix,
        "SIGNING_SERVICE_ACCOUNT": settings.signing_service_account,
        "ENABLE_GOOGLE_GROUNDING": "true",
        "ENABLE_DATASTORE": "false",
        "SERVICE_NAME": display_name,
    }

    if existing_re:
        logger.info(
            "Updating existing UC4 Agent Engine IN-PLACE via vertexai.agent_engines: %s",
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
    else:
        logger.info(
            "Creating NEW Vertex AI Agent Engine for '%s' (UC4)...",
            display_name,
        )
        remote_engine = agent_engines.create(
            agent_engine=engine_instance,
            requirements=requirements,
            extra_packages=extra_packages,
            display_name=display_name,
            description=description,
            env_vars=env_vars,
        )

    _persist_reasoning_engine_id(remote_engine.resource_name)
    patch_reasoning_engine_framework_and_telemetry(
        remote_engine.resource_name, env_vars
    )
    logger.info(
        "Successfully deployed '%s' (UC4) with Framework='google-adk' & Telemetry=Enabled: %s",
        display_name,
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

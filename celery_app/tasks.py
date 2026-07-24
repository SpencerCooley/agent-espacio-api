import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from uuid import UUID

from celery_app.celery_app import celery_app
from sqlalchemy.orm.attributes import flag_modified

STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
REPOS_DIR = os.path.join(STORAGE_PATH, "repos")
PUBLISHED_DIR = os.path.join(STORAGE_PATH, "published")
MAX_DEPLOY_HISTORY = 20


def _publish_deploy_event(
    event_type: str,
    artifact_id: UUID,
    folder_id,
    payload: dict,
) -> None:
    try:
        from services.events import publish_event

        publish_event(
            event_type=event_type,
            folder_id=str(folder_id) if folder_id else "",
            resource_id=str(artifact_id),
            payload=payload,
        )
    except Exception as e:
        print(f"[DEPLOY] Failed to publish event {event_type}: {e}", flush=True)


def _append_deploy_history(pub: dict, entry: dict) -> None:
    history = list(pub.get("deploy_history") or [])
    history.insert(0, entry)
    pub["deploy_history"] = history[:MAX_DEPLOY_HISTORY]


@celery_app.task(bind=True)
def hello_world_task(self):
    """
    A simple hello world Celery task.

    Returns:
        dict: A greeting message with task ID.
    """
    return {
        "message": "Hello from Agent Espacio Celery!",
        "task_id": self.request.id,
        "status": "success"
    }


@celery_app.task(bind=True, max_retries=0)
def deploy_repo_task(self, artifact_id_str: str, ref: str = ""):
    """
    Deploy a static site from a repo artifact.

    1. Clone the repo to a temp directory
    2. If build_command is set, run it
    3. Copy output to PUBLISHED_DIR/{artifact_id}/
    4. Update artifact meta with deploy status + history
    5. Publish WebSocket events for real-time UI updates
    """
    artifact_id = UUID(artifact_id_str)
    repo_path = os.path.join(REPOS_DIR, f"{artifact_id}.git")
    published_path = os.path.join(PUBLISHED_DIR, str(artifact_id))
    started_at = datetime.now(timezone.utc).isoformat()

    os.environ.setdefault("PYTHONPATH", "/app")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models.artifact import Artifact

    db_url = os.environ.get("DATABASE_URL", "postgresql://agentespacio:agentespacio@db:5432/agentespacio_db")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    artifact = None
    folder_id = None

    try:
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if not artifact:
            return {"status": "error", "detail": "Artifact not found"}

        folder_id = artifact.folder_id
        meta = dict(artifact.meta or {})
        pub = dict(meta.get("publish") or {})
        build_command = pub.get("build_command", "")
        output_dir = pub.get("output_dir", "dist")

        # Mark as building
        pub["status"] = "building"
        meta["publish"] = pub
        artifact.meta = meta
        flag_modified(artifact, "meta")
        db.commit()

        _publish_deploy_event(
            "artifact.deploy_started",
            artifact_id,
            folder_id,
            {"status": "building", "started_at": started_at, "ref": ref or ""},
        )

        log_lines = []
        deployed_commit = "unknown"

        with tempfile.TemporaryDirectory(prefix=f"deploy-{artifact_id}-") as tmp_dir:
            clone_dir = os.path.join(tmp_dir, "src")

            try:
                result = subprocess.run(
                    ["git", "clone", "--depth=1", repo_path, clone_dir],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"Clone failed: {result.stderr}")
                log_lines.append(f"Cloned repo to {clone_dir}")
            except subprocess.TimeoutExpired:
                raise RuntimeError("Clone timed out after 120s")

            commit_result = subprocess.run(
                ["git", "-C", clone_dir, "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True,
            )
            deployed_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown"

            if build_command:
                log_lines.append(f"Running build: {build_command}")
                try:
                    if any(cmd in build_command for cmd in ["npm", "yarn", "pnpm"]):
                        pkg = "npm" if "npm" in build_command else ("pnpm" if "pnpm" in build_command else "yarn")
                        install_cmd = f"{pkg} install"
                        install_result = subprocess.run(
                            install_cmd,
                            shell=True, cwd=clone_dir, capture_output=True, text=True, timeout=300,
                        )
                        if install_result.returncode != 0:
                            log_lines.append(f"Install warning: {install_result.stderr[:500]}")

                    build_result = subprocess.run(
                        build_command, shell=True, cwd=clone_dir,
                        capture_output=True, text=True, timeout=300,
                    )
                    log_lines.append(f"Build stdout: {build_result.stdout[:1000]}")
                    if build_result.returncode != 0:
                        log_lines.append(f"Build stderr: {build_result.stderr[:1000]}")
                        raise RuntimeError(f"Build failed with code {build_result.returncode}")
                    log_lines.append("Build completed successfully")
                except subprocess.TimeoutExpired:
                    raise RuntimeError("Build timed out after 300s")

            if build_command:
                source_dir = os.path.join(clone_dir, output_dir)
                if not os.path.isdir(source_dir):
                    raise RuntimeError(f"Output directory '{output_dir}' not found after build")
            else:
                source_dir = clone_dir
                log_lines.append("No build command configured — serving files as-is")

            if os.path.exists(published_path):
                shutil.rmtree(published_path)
            shutil.copytree(source_dir, published_path)

            log_lines.append(f"Deployed to {published_path}")

        finished_at = datetime.now(timezone.utc).isoformat()
        log_text = "\n".join(log_lines[-50:])

        # Refresh artifact after long-running work
        db.refresh(artifact)
        meta = dict(artifact.meta or {})
        pub = dict(meta.get("publish") or {})
        pub["status"] = "deployed"
        pub["last_deploy_at"] = finished_at
        pub["last_deploy_commit"] = deployed_commit
        pub["last_deploy_log"] = log_text
        _append_deploy_history(pub, {
            "status": "deployed",
            "commit": deployed_commit,
            "started_at": started_at,
            "finished_at": finished_at,
            "log": log_text,
            "ref": ref or "",
        })
        meta["publish"] = pub
        artifact.meta = meta
        flag_modified(artifact, "meta")
        db.commit()

        _publish_deploy_event(
            "artifact.deployed",
            artifact_id,
            folder_id,
            {
                "status": "deployed",
                "commit": deployed_commit,
                "started_at": started_at,
                "finished_at": finished_at,
                "log": log_text,
            },
        )

        return {"status": "deployed", "commit": deployed_commit}

    except Exception as e:
        finished_at = datetime.now(timezone.utc).isoformat()
        log_text = f"Deploy failed: {str(e)[:2000]}"
        try:
            if artifact is not None:
                db.refresh(artifact)
                meta = dict(artifact.meta or {})
                pub = dict(meta.get("publish") or {})
                pub["status"] = "failed"
                pub["last_deploy_log"] = log_text
                pub["last_deploy_at"] = finished_at
                _append_deploy_history(pub, {
                    "status": "failed",
                    "commit": "",
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "log": log_text,
                    "ref": ref or "",
                })
                meta["publish"] = pub
                artifact.meta = meta
                flag_modified(artifact, "meta")
                db.commit()
                _publish_deploy_event(
                    "artifact.deploy_failed",
                    artifact_id,
                    folder_id or artifact.folder_id,
                    {
                        "status": "failed",
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "log": log_text,
                    },
                )
        except Exception:
            pass
        return {"status": "error", "detail": str(e)}

    finally:
        db.close()
        engine.dispose()

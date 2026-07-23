import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from uuid import UUID

from celery_app.celery_app import celery_app

STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
REPOS_DIR = os.path.join(STORAGE_PATH, "repos")
PUBLISHED_DIR = os.path.join(STORAGE_PATH, "published")


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
    4. Update artifact meta with deploy status
    """
    artifact_id = UUID(artifact_id_str)
    repo_path = os.path.join(REPOS_DIR, f"{artifact_id}.git")
    published_path = os.path.join(PUBLISHED_DIR, str(artifact_id))

    # We need DB access to read/update the artifact
    # Import here to avoid circular imports
    os.environ.setdefault("PYTHONPATH", "/app")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models.artifact import Artifact

    db_url = os.environ.get("DATABASE_URL", "postgresql://agentespacio:agentespacio@db:5432/agentespacio_db")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if not artifact:
            return {"status": "error", "detail": "Artifact not found"}

        meta = artifact.meta or {}
        pub = meta.get("publish", {})
        build_command = pub.get("build_command", "")
        output_dir = pub.get("output_dir", "dist")

        # Mark as building
        pub["status"] = "building"
        meta["publish"] = pub
        artifact.meta = meta
        db.commit()

        log_lines = []

        with tempfile.TemporaryDirectory(prefix=f"deploy-{artifact_id}-") as tmp_dir:
            clone_dir = os.path.join(tmp_dir, "src")

            # Clone the repo
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

            # Determine deployed commit
            commit_result = subprocess.run(
                ["git", "-C", clone_dir, "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True,
            )
            deployed_commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown"

            # Run build if configured
            if build_command:
                log_lines.append(f"Running build: {build_command}")
                try:
                    # Try npm install first if build_command contains npm/yarn/pnpm
                    if any(cmd in build_command for cmd in ["npm", "yarn", "pnpm"]):
                        install_result = subprocess.run(
                            build_command.split()[0] + " install" if "npm" in build_command else "yarn install",
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

            # Determine source directory
            if build_command:
                source_dir = os.path.join(clone_dir, output_dir)
                if not os.path.isdir(source_dir):
                    raise RuntimeError(f"Output directory '{output_dir}' not found after build")
            else:
                # No build step — serve files directly from the repo root
                source_dir = clone_dir
                log_lines.append("No build command configured — serving files as-is")

            # Deploy: remove old files, copy new ones
            if os.path.exists(published_path):
                shutil.rmtree(published_path)
            shutil.copytree(source_dir, published_path)

            log_lines.append(f"Deployed to {published_path}")

        # Update artifact meta
        pub["status"] = "deployed"
        pub["last_deploy_at"] = datetime.now(timezone.utc).isoformat()
        pub["last_deploy_commit"] = deployed_commit
        pub["last_deploy_log"] = "\n".join(log_lines[-50:])  # Keep last 50 lines
        meta["publish"] = pub
        artifact.meta = meta
        db.commit()

        return {"status": "deployed", "commit": deployed_commit}

    except Exception as e:
        # Mark as failed
        try:
            meta = artifact.meta or {}
            pub = meta.get("publish", {})
            pub["status"] = "failed"
            pub["last_deploy_log"] = f"Deploy failed: {str(e)[:2000]}"
            meta["publish"] = pub
            artifact.meta = meta
            db.commit()
        except Exception:
            pass
        return {"status": "error", "detail": str(e)}

    finally:
        db.close()
        engine.dispose()

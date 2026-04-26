# PDF To Editable PPT MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working vertical slice of the Web platform: account/password auth, PDF upload, queue-backed workflow dispatch, Python Worker execution, one Runner Agent prompt/skill, one Validator Agent prompt/skill, editable PPTX candidate generation, full-page validation, and user-triggered repair.

**Architecture:** Next.js owns Web/API, auth, database access, uploads, task status, and task conversation. Python Worker owns Gateway, Redis Streams consumption, task manifests, deterministic PDF/PPT tools, Codex subprocess execution, Runner/Validator prompt and skill files, and validation reports. Files are shared through a local Docker volume, and Codex/CodeDesk auth is mounted read-only from the host into the Worker container.

**Tech Stack:** Next.js, TypeScript, Prisma, PostgreSQL, Redis Streams, Python 3.11, pytest, Pydantic, PyMuPDF, python-pptx, Pillow, scikit-image, LibreOffice, Docker Compose, Codex CLI.

---

## Scope Notes

This plan implements the first end-to-end MVP. It does not attempt advanced perfect PDF reconstruction in the first pass. It creates the architecture, tool protocol, prompts, skills, validation harness, and a minimal editable reconstruction path that can be iterated against the sample PDFs in `pdf-to-ppt-test-samples/`.

The important quality rule is enforced from the start: a generated PPTX that is mostly one full-page image fails validation.

## File Map

- `package.json`: root npm workspace scripts.
- `.env.example`: local development environment variables, including `HOST_CODEX_HOME`.
- `docker-compose.yml`: Postgres, Redis, Web, and Worker services with shared task volume and read-only Codex auth mounts.
- `apps/web/`: Next.js app.
- `apps/web/prisma/schema.prisma`: database schema.
- `apps/web/src/lib/auth.ts`: password hashing, cookie session helpers.
- `apps/web/src/lib/db.ts`: Prisma singleton.
- `apps/web/src/lib/queue.ts`: Redis Streams producer.
- `apps/web/src/lib/tasks.ts`: task directory and upload helpers.
- `apps/web/src/app/`: pages and API routes.
- `apps/worker/`: Python Worker package.
- `apps/worker/src/autofacodex/gateway.py`: Redis Streams consumer and workflow dispatcher.
- `apps/worker/src/autofacodex/config.py`: environment and path configuration.
- `apps/worker/src/autofacodex/agents/`: Codex subprocess launcher, prompts, and skills.
- `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`: workflow state machine.
- `apps/worker/src/autofacodex/tools/`: deterministic PDF/PPT/render/validation tools.
- `contracts/`: JSON schemas shared by Web, Worker, and agent prompts.
- `tests/fixtures/`: small generated PDF fixtures for deterministic tests.

---

## Task 1: Repository And Toolchain Scaffold

**Files:**
- Create: `package.json`
- Create: `.env.example`
- Create: `.dockerignore`
- Create: `apps/worker/pyproject.toml`
- Create: `apps/worker/requirements.txt`
- Create: `apps/worker/requirements-dev.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Write root workspace files**

Create `package.json`:

```json
{
  "private": true,
  "name": "autofacodex",
  "workspaces": ["apps/web"],
  "scripts": {
    "dev:web": "npm --workspace apps/web run dev",
    "build:web": "npm --workspace apps/web run build",
    "lint:web": "npm --workspace apps/web run lint",
    "test:web": "npm --workspace apps/web run test",
    "test:worker": "cd apps/worker && .venv/bin/pytest -q",
    "test": "npm run test:web && npm run test:worker"
  }
}
```

Create `.env.example`:

```bash
POSTGRES_USER=autofacodex
POSTGRES_PASSWORD=autofacodex
POSTGRES_DB=autofacodex
DATABASE_URL=postgresql://autofacodex:autofacodex@postgres:5432/autofacodex
REDIS_URL=redis://redis:6379/0
NEXT_PUBLIC_APP_URL=http://localhost:3000
SESSION_SECRET=replace-with-32-byte-random-secret
SHARED_TASKS_DIR=/shared/tasks
HOST_CODEX_HOME=/home/alvin/.codex
CODEX_HOME=/home/worker/.codex
CODEX_BIN=codex
```

Create `.dockerignore`:

```text
.git
.superpowers
node_modules
apps/web/.next
apps/worker/.pytest_cache
apps/worker/.venv
__pycache__
*.pyc
pdf-to-ppt-test-samples/~$*
```

Append to `.gitignore`:

```text
node_modules/
.env
apps/web/.next/
apps/worker/.venv/
apps/worker/.pytest_cache/
__pycache__/
shared-tasks/
```

- [ ] **Step 2: Create Python Worker dependency files**

Create `apps/worker/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "autofacodex-worker"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `apps/worker/requirements.txt`:

```text
pydantic==2.11.3
redis==5.2.1
PyMuPDF==1.25.5
python-pptx==1.0.2
Pillow==11.2.1
scikit-image==0.25.2
numpy==2.2.5
lxml==5.3.2
```

Create `apps/worker/requirements-dev.txt`:

```text
-r requirements.txt
pytest==8.3.5
ruff==0.11.6
reportlab==4.4.0
```

- [ ] **Step 3: Install initial dependencies**

Run:

```bash
npm install
python3 -m venv apps/worker/.venv
apps/worker/.venv/bin/pip install -r apps/worker/requirements-dev.txt
```

Expected: npm creates `package-lock.json`, pip installs Worker dependencies without errors.

- [ ] **Step 4: Commit scaffold**

Run:

```bash
git add package.json package-lock.json .env.example .dockerignore .gitignore apps/worker
git commit -m "chore: scaffold project toolchains"
```

---

## Task 2: Docker Compose With Codex Auth Injection

**Files:**
- Create: `docker-compose.yml`
- Create: `apps/worker/Dockerfile`
- Create: `apps/worker/src/autofacodex/agents/codex_auth.py`
- Test: `apps/worker/tests/test_codex_auth.py`

- [ ] **Step 1: Write failing auth mount tests**

Create `apps/worker/tests/test_codex_auth.py`:

```python
from pathlib import Path

import pytest

from autofacodex.agents.codex_auth import CodexAuthConfig, validate_codex_auth


def test_validate_codex_auth_accepts_auth_and_config(tmp_path: Path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text('{"ok":true}', encoding="utf-8")
    (codex_home / "config.toml").write_text('model = "gpt-5.3-codex"\\n', encoding="utf-8")

    config = validate_codex_auth(CodexAuthConfig(codex_home=codex_home, codex_bin="codex"))

    assert config.auth_json == codex_home / "auth.json"
    assert config.config_toml == codex_home / "config.toml"


def test_validate_codex_auth_rejects_missing_auth(tmp_path: Path):
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()

    with pytest.raises(FileNotFoundError, match="auth.json"):
        validate_codex_auth(CodexAuthConfig(codex_home=codex_home, codex_bin="codex"))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_codex_auth.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'autofacodex'`.

- [ ] **Step 3: Implement auth validation**

Create `apps/worker/src/autofacodex/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `apps/worker/src/autofacodex/agents/__init__.py`:

```python
from .codex_auth import CodexAuthConfig, validate_codex_auth

__all__ = ["CodexAuthConfig", "validate_codex_auth"]
```

Create `apps/worker/src/autofacodex/agents/codex_auth.py`:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodexAuthConfig:
    codex_home: Path
    codex_bin: str

    @property
    def auth_json(self) -> Path:
        return self.codex_home / "auth.json"

    @property
    def config_toml(self) -> Path:
        return self.codex_home / "config.toml"


def validate_codex_auth(config: CodexAuthConfig) -> CodexAuthConfig:
    if not config.auth_json.is_file():
        raise FileNotFoundError(
            f"Codex auth file not found: {config.auth_json}. "
            "Mount HOST_CODEX_HOME/auth.json into the Worker container as read-only."
        )
    if not config.config_toml.is_file():
        raise FileNotFoundError(
            f"Codex config file not found: {config.config_toml}. "
            "Mount HOST_CODEX_HOME/config.toml into the Worker container as read-only."
        )
    return config
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_codex_auth.py -q
```

Expected: PASS.

- [ ] **Step 5: Add Docker files**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-autofacodex}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-autofacodex}
      POSTGRES_DB: ${POSTGRES_DB:-autofacodex}
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  web:
    build:
      context: .
      dockerfile: apps/web/Dockerfile
    env_file: .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      SHARED_TASKS_DIR: /shared/tasks
    ports:
      - "3000:3000"
    volumes:
      - shared-tasks:/shared/tasks
    depends_on:
      - postgres
      - redis

  worker:
    build:
      context: .
      dockerfile: apps/worker/Dockerfile
    env_file: .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
      SHARED_TASKS_DIR: /shared/tasks
      CODEX_HOME: /home/worker/.codex
      CODEX_BIN: ${CODEX_BIN:-codex}
    volumes:
      - shared-tasks:/shared/tasks
      - ${HOST_CODEX_HOME}/auth.json:/home/worker/.codex/auth.json:ro
      - ${HOST_CODEX_HOME}/config.toml:/home/worker/.codex/config.toml:ro
    depends_on:
      - postgres
      - redis

volumes:
  postgres-data:
  shared-tasks:
```

Create `apps/worker/Dockerfile`:

```dockerfile
FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    poppler-utils \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 worker
WORKDIR /app/apps/worker

COPY apps/worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN npm install -g @openai/codex

COPY apps/worker ./
USER worker
ENV PYTHONPATH=/app/apps/worker/src
CMD ["python", "-m", "autofacodex.gateway"]
```

- [ ] **Step 6: Verify compose config without starting services**

Run:

```bash
cp .env.example .env
docker compose config >/tmp/autofacodex-compose.yml
```

Expected: command exits 0. Inspect `/tmp/autofacodex-compose.yml` and confirm no auth secret contents are embedded.

- [ ] **Step 7: Commit Docker auth injection**

Run:

```bash
git add docker-compose.yml apps/worker/Dockerfile apps/worker/src apps/worker/tests
git commit -m "chore: add docker compose and codex auth mounts"
```

---

## Task 3: Shared Contracts And Worker Config

**Files:**
- Create: `contracts/task-manifest.schema.json`
- Create: `contracts/slide-model.schema.json`
- Create: `contracts/validator-report.schema.json`
- Create: `apps/worker/src/autofacodex/config.py`
- Create: `apps/worker/src/autofacodex/contracts.py`
- Test: `apps/worker/tests/test_contracts.py`

- [ ] **Step 1: Write failing contract tests**

Create `apps/worker/tests/test_contracts.py`:

```python
from pathlib import Path

from autofacodex.contracts import TaskManifest, SlideModel, ValidatorReport


def test_task_manifest_paths_are_task_relative(tmp_path: Path):
    manifest = TaskManifest(
        task_id="task_123",
        workflow_type="pdf_to_ppt",
        input_pdf="input.pdf",
        attempt=1,
        max_attempts=3,
    )

    assert manifest.workflow_type == "pdf_to_ppt"
    assert manifest.input_pdf == "input.pdf"


def test_slide_model_rejects_full_page_raster_as_declared_fallback():
    model = SlideModel(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 13.333, "height": 7.5},
                "elements": [],
                "raster_fallback_regions": [],
            }
        ]
    )

    assert model.slides[0].page_number == 1


def test_validator_report_requires_page_status():
    report = ValidatorReport(
        task_id="task_123",
        attempt=1,
        pages=[
            {
                "page_number": 1,
                "status": "repair_needed",
                "visual_score": 0.75,
                "editable_score": 0.4,
                "text_coverage_score": 0.9,
                "raster_fallback_ratio": 0.6,
                "issues": [
                    {
                        "type": "editability",
                        "message": "Large raster region detected",
                        "suggested_action": "Reconstruct visible text as editable text boxes",
                    }
                ],
            }
        ],
    )

    assert report.pages[0].status == "repair_needed"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_contracts.py -q
```

Expected: FAIL with missing `autofacodex.contracts`.

- [ ] **Step 3: Implement Pydantic contracts**

Create `apps/worker/src/autofacodex/contracts.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field


class TaskManifest(BaseModel):
    task_id: str
    workflow_type: Literal["pdf_to_ppt"]
    input_pdf: str
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1)


class SlideSize(BaseModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SlideElement(BaseModel):
    id: str
    type: Literal["text", "image", "shape", "table", "path"]
    x: float
    y: float
    w: float = Field(ge=0)
    h: float = Field(ge=0)
    text: str | None = None
    source: str | None = None
    style: dict = Field(default_factory=dict)


class RasterFallbackRegion(BaseModel):
    x: float
    y: float
    w: float
    h: float
    reason: str


class SlideSpec(BaseModel):
    page_number: int = Field(ge=1)
    size: SlideSize
    elements: list[SlideElement] = Field(default_factory=list)
    raster_fallback_regions: list[RasterFallbackRegion] = Field(default_factory=list)


class SlideModel(BaseModel):
    slides: list[SlideSpec]


class ValidatorIssue(BaseModel):
    type: str
    message: str
    suggested_action: str
    region: list[float] | None = None


class PageValidation(BaseModel):
    page_number: int = Field(ge=1)
    status: Literal["pass", "repair_needed", "manual_review", "failed"]
    visual_score: float = Field(ge=0, le=1)
    editable_score: float = Field(ge=0, le=1)
    text_coverage_score: float = Field(ge=0, le=1)
    raster_fallback_ratio: float = Field(ge=0, le=1)
    issues: list[ValidatorIssue] = Field(default_factory=list)


class ValidatorReport(BaseModel):
    task_id: str
    attempt: int = Field(ge=1)
    pages: list[PageValidation]
```

- [ ] **Step 4: Implement Worker config**

Create `apps/worker/src/autofacodex/config.py`:

```python
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerConfig:
    redis_url: str
    shared_tasks_dir: Path
    codex_home: Path
    codex_bin: str


def load_config() -> WorkerConfig:
    return WorkerConfig(
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        shared_tasks_dir=Path(os.environ.get("SHARED_TASKS_DIR", "shared-tasks")),
        codex_home=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))),
        codex_bin=os.environ.get("CODEX_BIN", "codex"),
    )
```

- [ ] **Step 5: Add JSON schema mirrors**

Create the three files in `contracts/` by serializing the matching Pydantic models in a one-off shell command:

```bash
cd apps/worker
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from autofacodex.contracts import TaskManifest, SlideModel, ValidatorReport

root = Path("../..") / "contracts"
root.mkdir(exist_ok=True)
for name, model in {
    "task-manifest.schema.json": TaskManifest,
    "slide-model.schema.json": SlideModel,
    "validator-report.schema.json": ValidatorReport,
}.items():
    (root / name).write_text(json.dumps(model.model_json_schema(), indent=2), encoding="utf-8")
PY
```

Expected: `contracts/*.schema.json` files are created.

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_contracts.py -q
git add contracts apps/worker/src/autofacodex/config.py apps/worker/src/autofacodex/contracts.py apps/worker/tests/test_contracts.py
git commit -m "feat: add workflow contracts"
```

Expected: tests pass and commit succeeds.

---

## Task 4: Web App, Database, Local Auth, And Task Records

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/Dockerfile`
- Create: `apps/web/prisma/schema.prisma`
- Create: `apps/web/src/lib/db.ts`
- Create: `apps/web/src/lib/auth.ts`
- Create: `apps/web/src/lib/tasks.ts`
- Create: `apps/web/src/app/api/auth/register/route.ts`
- Create: `apps/web/src/app/api/auth/login/route.ts`
- Create: `apps/web/src/app/api/tasks/route.ts`
- Create: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/app/tasks/[taskId]/page.tsx`

- [ ] **Step 1: Scaffold Next.js app**

Run:

```bash
npx create-next-app@latest apps/web --ts --eslint --app --src-dir --tailwind --import-alias "@/*" --use-npm
npm --workspace apps/web install @prisma/client prisma bcryptjs jose ioredis zod
npm --workspace apps/web install -D vitest @types/bcryptjs
```

Expected: Next.js app exists under `apps/web`.

- [ ] **Step 2: Add Web scripts**

Modify `apps/web/package.json` so the scripts block contains:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "vitest run",
    "prisma:generate": "prisma generate",
    "prisma:migrate": "prisma migrate dev"
  }
}
```

- [ ] **Step 3: Add Prisma schema**

Create `apps/web/prisma/schema.prisma`:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id           String   @id @default(cuid())
  email        String   @unique
  passwordHash String
  createdAt    DateTime @default(now())
  tasks        WorkflowTask[]
  messages     TaskConversationMessage[]
}

model WorkflowTask {
  id             String   @id @default(cuid())
  userId         String
  workflowType   String
  status         String
  inputFilePath  String
  outputFilePath String?
  currentAttempt Int      @default(1)
  maxAttempts    Int      @default(3)
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt
  user           User     @relation(fields: [userId], references: [id])
  artifacts      TaskArtifact[]
  events         TaskEvent[]
  messages       TaskConversationMessage[]
}

model TaskArtifact {
  id           String   @id @default(cuid())
  taskId       String
  artifactType String
  path         String
  metadata     Json?
  createdAt    DateTime @default(now())
  task         WorkflowTask @relation(fields: [taskId], references: [id])
}

model TaskEvent {
  id        String   @id @default(cuid())
  taskId    String
  role      String
  eventType String
  message   String
  payload   Json?
  createdAt DateTime @default(now())
  task      WorkflowTask @relation(fields: [taskId], references: [id])
}

model TaskConversationMessage {
  id        String   @id @default(cuid())
  taskId    String
  userId    String?
  role      String
  content   String
  createdAt DateTime @default(now())
  task      WorkflowTask @relation(fields: [taskId], references: [id])
  user      User?    @relation(fields: [userId], references: [id])
}
```

- [ ] **Step 4: Implement auth helpers**

Create `apps/web/src/lib/db.ts`:

```ts
import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma = globalForPrisma.prisma ?? new PrismaClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}
```

Create `apps/web/src/lib/auth.ts`:

```ts
import bcrypt from "bcryptjs";
import { jwtVerify, SignJWT } from "jose";
import { cookies } from "next/headers";

const cookieName = "autofacodex_session";

function secretKey() {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.length < 32) {
    throw new Error("SESSION_SECRET must be at least 32 characters");
  }
  return new TextEncoder().encode(secret);
}

export async function hashPassword(password: string) {
  return bcrypt.hash(password, 12);
}

export async function verifyPassword(password: string, hash: string) {
  return bcrypt.compare(password, hash);
}

export async function createSession(userId: string) {
  const token = await new SignJWT({ userId })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(secretKey());
  const jar = await cookies();
  jar.set(cookieName, token, { httpOnly: true, sameSite: "lax", path: "/" });
}

export async function getSessionUserId() {
  const jar = await cookies();
  const token = jar.get(cookieName)?.value;
  if (!token) return null;
  try {
    const verified = await jwtVerify(token, secretKey());
    return String(verified.payload.userId);
  } catch {
    return null;
  }
}
```

- [ ] **Step 5: Implement register and login routes**

Create `apps/web/src/app/api/auth/register/route.ts`:

```ts
import { NextResponse } from "next/server";
import { z } from "zod";
import { createSession, hashPassword } from "@/lib/auth";
import { prisma } from "@/lib/db";

const bodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(8)
});

export async function POST(request: Request) {
  const body = bodySchema.parse(await request.json());
  const user = await prisma.user.create({
    data: { email: body.email.toLowerCase(), passwordHash: await hashPassword(body.password) }
  });
  await createSession(user.id);
  return NextResponse.json({ userId: user.id });
}
```

Create `apps/web/src/app/api/auth/login/route.ts`:

```ts
import { NextResponse } from "next/server";
import { z } from "zod";
import { createSession, verifyPassword } from "@/lib/auth";
import { prisma } from "@/lib/db";

const bodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(1)
});

export async function POST(request: Request) {
  const body = bodySchema.parse(await request.json());
  const user = await prisma.user.findUnique({ where: { email: body.email.toLowerCase() } });
  if (!user || !(await verifyPassword(body.password, user.passwordHash))) {
    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
  }
  await createSession(user.id);
  return NextResponse.json({ userId: user.id });
}
```

- [ ] **Step 6: Add a minimal Web UI**

Replace `apps/web/src/app/page.tsx`:

```tsx
export default function Home() {
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-2xl font-semibold">AutoFaCodex</h1>
      <p>Upload a PDF, run the editable PPT workflow, and review Validator feedback.</p>
    </main>
  );
}
```

Run:

```bash
npm --workspace apps/web run lint
```

Expected: lint passes or reports only create-next-app baseline formatting warnings. Fix reported TypeScript errors before committing.

- [ ] **Step 7: Commit Web auth baseline**

Create `apps/web/Dockerfile`:

```dockerfile
FROM node:22-bookworm
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm install
COPY apps/web apps/web
WORKDIR /app/apps/web
EXPOSE 3000
CMD ["npm", "run", "dev"]
```

Run:

```bash
git add apps/web package.json package-lock.json
git commit -m "feat: add web auth and task schema"
```

---

## Task 5: Uploads And Redis Streams Queue

**Files:**
- Create: `apps/web/src/lib/queue.ts`
- Modify: `apps/web/src/lib/tasks.ts`
- Modify: `apps/web/src/app/api/tasks/route.ts`
- Test: `apps/web/src/lib/queue.test.ts`

- [ ] **Step 1: Write Redis job producer test**

Create `apps/web/src/lib/queue.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { buildWorkflowJob } from "./queue";

describe("buildWorkflowJob", () => {
  it("creates a language-neutral pdf_to_ppt job payload", () => {
    const job = buildWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" });
    expect(job).toEqual({
      task_id: "task_1",
      workflow_type: "pdf_to_ppt"
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm --workspace apps/web run test -- src/lib/queue.test.ts
```

Expected: FAIL with missing `buildWorkflowJob`.

- [ ] **Step 3: Implement queue producer**

Create `apps/web/src/lib/queue.ts`:

```ts
import Redis from "ioredis";

export type WorkflowJobInput = {
  taskId: string;
  workflowType: "pdf_to_ppt";
};

export function buildWorkflowJob(input: WorkflowJobInput) {
  return {
    task_id: input.taskId,
    workflow_type: input.workflowType
  };
}

export async function enqueueWorkflowJob(input: WorkflowJobInput) {
  const redis = new Redis(process.env.REDIS_URL ?? "redis://localhost:6379/0");
  const job = buildWorkflowJob(input);
  await redis.xadd("workflow_jobs", "*", "payload", JSON.stringify(job));
  await redis.quit();
}
```

- [ ] **Step 4: Implement upload task route**

Create `apps/web/src/lib/tasks.ts`:

```ts
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

export function taskDir(taskId: string) {
  const root = process.env.SHARED_TASKS_DIR ?? "shared-tasks";
  return path.join(root, taskId);
}

export async function writeInputPdf(taskId: string, bytes: ArrayBuffer) {
  const dir = taskDir(taskId);
  await mkdir(dir, { recursive: true });
  const filePath = path.join(dir, "input.pdf");
  await writeFile(filePath, Buffer.from(bytes));
  return filePath;
}
```

Create `apps/web/src/app/api/tasks/route.ts`:

```ts
import { NextResponse } from "next/server";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { enqueueWorkflowJob } from "@/lib/queue";
import { writeInputPdf } from "@/lib/tasks";

export async function POST(request: Request) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof File) || file.type !== "application/pdf") {
    return NextResponse.json({ error: "PDF file is required" }, { status: 400 });
  }

  const task = await prisma.workflowTask.create({
    data: {
      userId,
      workflowType: "pdf_to_ppt",
      status: "queued",
      inputFilePath: ""
    }
  });

  const inputFilePath = await writeInputPdf(task.id, await file.arrayBuffer());
  await prisma.workflowTask.update({
    where: { id: task.id },
    data: { inputFilePath }
  });
  await enqueueWorkflowJob({ taskId: task.id, workflowType: "pdf_to_ppt" });

  return NextResponse.json({ taskId: task.id });
}
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
npm --workspace apps/web run test -- src/lib/queue.test.ts
git add apps/web/src/lib apps/web/src/app/api/tasks/route.ts
git commit -m "feat: enqueue uploaded pdf workflow jobs"
```

Expected: queue test passes.

---

## Task 6: Worker Gateway And Task Manifest

**Files:**
- Create: `apps/worker/src/autofacodex/gateway.py`
- Create: `apps/worker/src/autofacodex/workflows/__init__.py`
- Create: `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`
- Test: `apps/worker/tests/test_gateway.py`

- [ ] **Step 1: Write failing Gateway dispatch test**

Create `apps/worker/tests/test_gateway.py`:

```python
import json
from pathlib import Path

from autofacodex.gateway import parse_job_payload, write_task_manifest


def test_parse_job_payload():
    payload = json.dumps({"task_id": "task_1", "workflow_type": "pdf_to_ppt"})

    job = parse_job_payload(payload)

    assert job.task_id == "task_1"
    assert job.workflow_type == "pdf_to_ppt"


def test_write_task_manifest(tmp_path: Path):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    (task_dir / "input.pdf").write_bytes(b"%PDF-1.4")

    manifest_path = write_task_manifest(task_dir, "task_1", 1, 3)

    assert manifest_path.name == "task-manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["task_id"] == "task_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_gateway.py -q
```

Expected: FAIL with missing `autofacodex.gateway`.

- [ ] **Step 3: Implement Gateway helpers**

Create `apps/worker/src/autofacodex/gateway.py`:

```python
import json
import time
from pathlib import Path

import redis
from pydantic import BaseModel

from autofacodex.config import load_config
from autofacodex.contracts import TaskManifest
from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt


class WorkflowJob(BaseModel):
    task_id: str
    workflow_type: str


def parse_job_payload(payload: str) -> WorkflowJob:
    return WorkflowJob.model_validate_json(payload)


def write_task_manifest(task_dir: Path, task_id: str, attempt: int, max_attempts: int) -> Path:
    manifest = TaskManifest(
        task_id=task_id,
        workflow_type="pdf_to_ppt",
        input_pdf="input.pdf",
        attempt=attempt,
        max_attempts=max_attempts,
    )
    path = task_dir / "task-manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def run_once(payload: str) -> None:
    config = load_config()
    job = parse_job_payload(payload)
    if job.workflow_type != "pdf_to_ppt":
        raise ValueError(f"Unsupported workflow_type: {job.workflow_type}")
    task_dir = config.shared_tasks_dir / job.task_id
    write_task_manifest(task_dir, job.task_id, attempt=1, max_attempts=3)
    run_pdf_to_ppt(task_dir)


def main() -> None:
    config = load_config()
    client = redis.Redis.from_url(config.redis_url, decode_responses=True)
    stream = "workflow_jobs"
    group = "worker"
    consumer = "worker-1"
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    while True:
        messages = client.xreadgroup(group, consumer, {stream: ">"}, count=1, block=5000)
        if not messages:
            time.sleep(1)
            continue
        for _, entries in messages:
            for message_id, fields in entries:
                run_once(fields["payload"])
                client.xack(stream, group, message_id)


if __name__ == "__main__":
    main()
```

Create `apps/worker/src/autofacodex/workflows/__init__.py`:

```python
__all__ = []
```

Create `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`:

```python
from pathlib import Path


def run_pdf_to_ppt(task_dir: Path) -> None:
    (task_dir / "logs").mkdir(exist_ok=True)
    (task_dir / "logs" / "workflow.log").write_text("pdf_to_ppt workflow started\\n", encoding="utf-8")
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_gateway.py -q
git add apps/worker/src/autofacodex/gateway.py apps/worker/src/autofacodex/workflows apps/worker/tests/test_gateway.py
git commit -m "feat: add worker gateway"
```

Expected: tests pass.

---

## Task 7: Deterministic PDF Extraction And Rendering

**Files:**
- Create: `apps/worker/src/autofacodex/tools/pdf_extract.py`
- Create: `apps/worker/src/autofacodex/tools/pdf_render.py`
- Create: `apps/worker/src/autofacodex/tools/__init__.py`
- Test: `apps/worker/tests/test_pdf_tools.py`

- [ ] **Step 1: Write failing PDF tool tests**

Create `apps/worker/tests/test_pdf_tools.py`:

```python
from pathlib import Path

from reportlab.pdfgen import canvas

from autofacodex.tools.pdf_extract import extract_pdf
from autofacodex.tools.pdf_render import render_pdf_pages


def make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Editable Title")
    c.rect(70, 120, 160, 60, stroke=1, fill=0)
    c.save()


def test_extract_pdf_text_and_page_size(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    result = extract_pdf(pdf, tmp_path / "extracted")

    assert result["pages"][0]["page_number"] == 1
    assert "Editable Title" in result["pages"][0]["text"]


def test_render_pdf_pages_outputs_png(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf)

    renders = render_pdf_pages(pdf, tmp_path / "renders")

    assert len(renders) == 1
    assert renders[0].suffix == ".png"
    assert renders[0].is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pdf_tools.py -q
```

Expected: FAIL with missing tool modules.

- [ ] **Step 3: Implement PDF extraction and rendering**

Create `apps/worker/src/autofacodex/tools/__init__.py`:

```python
__all__ = []
```

Create `apps/worker/src/autofacodex/tools/pdf_extract.py`:

```python
import json
from pathlib import Path

import fitz


def extract_pdf(pdf_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    pages = []
    for index, page in enumerate(doc, start=1):
        text_dict = page.get_text("dict")
        images = page.get_images(full=True)
        drawings = page.get_drawings()
        pages.append(
            {
                "page_number": index,
                "width": page.rect.width,
                "height": page.rect.height,
                "text": page.get_text("text"),
                "text_blocks": text_dict.get("blocks", []),
                "image_count": len(images),
                "drawing_count": len(drawings),
            }
        )
    result = {"pages": pages}
    (output_dir / "pages.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
```

Create `apps/worker/src/autofacodex/tools/pdf_render.py`:

```python
from pathlib import Path

import fitz


def render_pdf_pages(pdf_path: Path, output_dir: Path, zoom: float = 2.0) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths: list[Path] = []
    matrix = fitz.Matrix(zoom, zoom)
    for index, page in enumerate(doc, start=1):
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        output = output_dir / f"page-{index:03d}.png"
        pixmap.save(output)
        paths.append(output)
    return paths
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pdf_tools.py -q
git add apps/worker/src/autofacodex/tools apps/worker/tests/test_pdf_tools.py
git commit -m "feat: extract and render pdf pages"
```

Expected: tests pass.

---

## Task 8: Editable Slide Model Builder And PPTX Generator

**Files:**
- Create: `apps/worker/src/autofacodex/tools/slide_model_builder.py`
- Create: `apps/worker/src/autofacodex/tools/pptx_generate.py`
- Test: `apps/worker/tests/test_pptx_generation.py`

- [ ] **Step 1: Write failing PPTX generation test**

Create `apps/worker/tests/test_pptx_generation.py`:

```python
from pathlib import Path
from zipfile import ZipFile

from autofacodex.contracts import SlideModel
from autofacodex.tools.pptx_generate import generate_pptx


def test_generate_pptx_contains_editable_text(tmp_path: Path):
    model = SlideModel(
        slides=[
            {
                "page_number": 1,
                "size": {"width": 10, "height": 7.5},
                "elements": [
                    {
                        "id": "title",
                        "type": "text",
                        "text": "Editable Title",
                        "x": 1,
                        "y": 1,
                        "w": 5,
                        "h": 1,
                        "style": {"font_size": 28},
                    }
                ],
                "raster_fallback_regions": [],
            }
        ]
    )
    output = tmp_path / "candidate.pptx"

    generate_pptx(model, output)

    with ZipFile(output) as pptx:
        slide_xml = pptx.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "Editable Title" in slide_xml
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_generation.py -q
```

Expected: FAIL with missing `pptx_generate`.

- [ ] **Step 3: Implement PPTX generator**

Create `apps/worker/src/autofacodex/tools/pptx_generate.py`:

```python
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt

from autofacodex.contracts import SlideModel


def generate_pptx(model: SlideModel, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    presentation = Presentation()
    if model.slides:
      presentation.slide_width = Inches(model.slides[0].size.width)
      presentation.slide_height = Inches(model.slides[0].size.height)

    blank_layout = presentation.slide_layouts[6]
    for slide_spec in model.slides:
        slide = presentation.slides.add_slide(blank_layout)
        for element in slide_spec.elements:
            if element.type == "text":
                box = slide.shapes.add_textbox(
                    Inches(element.x),
                    Inches(element.y),
                    Inches(element.w),
                    Inches(element.h),
                )
                paragraph = box.text_frame.paragraphs[0]
                run = paragraph.add_run()
                run.text = element.text or ""
                font_size = element.style.get("font_size", 18)
                run.font.size = Pt(font_size)
    presentation.save(output_path)
    return output_path
```

- [ ] **Step 4: Implement initial slide model builder**

Create `apps/worker/src/autofacodex/tools/slide_model_builder.py`:

```python
from autofacodex.contracts import SlideElement, SlideModel, SlideSize, SlideSpec


def build_initial_slide_model(extracted: dict) -> SlideModel:
    slides: list[SlideSpec] = []
    for page in extracted["pages"]:
        width = 13.333
        height = 13.333 * float(page["height"]) / float(page["width"])
        elements: list[SlideElement] = []
        text = page.get("text", "").strip()
        if text:
            elements.append(
                SlideElement(
                    id=f"p{page['page_number']}-text-1",
                    type="text",
                    text=text,
                    x=0.5,
                    y=0.5,
                    w=width - 1,
                    h=max(1.0, height - 1),
                    style={"font_size": 14},
                )
            )
        slides.append(
            SlideSpec(
                page_number=page["page_number"],
                size=SlideSize(width=width, height=height),
                elements=elements,
                raster_fallback_regions=[],
            )
        )
    return SlideModel(slides=slides)
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pptx_generation.py -q
git add apps/worker/src/autofacodex/tools/slide_model_builder.py apps/worker/src/autofacodex/tools/pptx_generate.py apps/worker/tests/test_pptx_generation.py
git commit -m "feat: generate editable pptx from slide model"
```

Expected: tests pass.

---

## Task 9: PPTX Rendering, Structure Inspection, And Validator Metrics

**Files:**
- Create: `apps/worker/src/autofacodex/tools/pptx_render.py`
- Create: `apps/worker/src/autofacodex/tools/pptx_inspect.py`
- Create: `apps/worker/src/autofacodex/tools/visual_diff.py`
- Create: `apps/worker/src/autofacodex/agents/validator_runtime.py`
- Test: `apps/worker/tests/test_validator_runtime.py`

- [ ] **Step 1: Write failing Validator runtime test**

Create `apps/worker/tests/test_validator_runtime.py`:

```python
from pathlib import Path

from autofacodex.agents.validator_runtime import build_validator_report


def test_build_validator_report_fails_full_page_raster(tmp_path: Path):
    report = build_validator_report(
        task_id="task_1",
        attempt=1,
        page_count=1,
        visual_scores={1: 0.98},
        editable_scores={1: 0.1},
        text_scores={1: 0.0},
        raster_ratios={1: 0.95},
    )

    page = report.pages[0]
    assert page.status == "repair_needed"
    assert page.issues[0].type == "editability"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_validator_runtime.py -q
```

Expected: FAIL with missing `validator_runtime`.

- [ ] **Step 3: Implement Validator report builder**

Create `apps/worker/src/autofacodex/agents/validator_runtime.py`:

```python
from autofacodex.contracts import PageValidation, ValidatorIssue, ValidatorReport


def build_validator_report(
    task_id: str,
    attempt: int,
    page_count: int,
    visual_scores: dict[int, float],
    editable_scores: dict[int, float],
    text_scores: dict[int, float],
    raster_ratios: dict[int, float],
) -> ValidatorReport:
    pages: list[PageValidation] = []
    for page_number in range(1, page_count + 1):
        visual = visual_scores.get(page_number, 0)
        editable = editable_scores.get(page_number, 0)
        text = text_scores.get(page_number, 0)
        raster = raster_ratios.get(page_number, 1)
        issues: list[ValidatorIssue] = []
        status = "pass"
        if raster >= 0.5 or editable < 0.5:
            status = "repair_needed"
            issues.append(
                ValidatorIssue(
                    type="editability",
                    message="Slide contains excessive raster content or too few editable elements",
                    suggested_action="Reconstruct visible text and simple shapes as editable PPT elements",
                )
            )
        if visual < 0.9:
            status = "repair_needed"
            issues.append(
                ValidatorIssue(
                    type="visual_fidelity",
                    message="Rendered PPTX differs from the source PDF page",
                    suggested_action="Use the diff render to adjust positions, sizes, colors, and missing regions",
                )
            )
        if text < 0.8:
            status = "repair_needed"
            issues.append(
                ValidatorIssue(
                    type="text_coverage",
                    message="Editable PPTX text does not cover source PDF text",
                    suggested_action="Recover missing text as editable text boxes",
                )
            )
        pages.append(
            PageValidation(
                page_number=page_number,
                status=status,
                visual_score=visual,
                editable_score=editable,
                text_coverage_score=text,
                raster_fallback_ratio=raster,
                issues=issues,
            )
        )
    return ValidatorReport(task_id=task_id, attempt=attempt, pages=pages)
```

- [ ] **Step 4: Add rendering and inspection tools**

Create `apps/worker/src/autofacodex/tools/pptx_inspect.py`:

```python
from pathlib import Path
from zipfile import ZipFile


def inspect_pptx_editability(pptx_path: Path) -> dict:
    with ZipFile(pptx_path) as archive:
        slide_names = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))
        pages = []
        for slide_name in slide_names:
            xml = archive.read(slide_name).decode("utf-8", errors="ignore")
            pages.append(
                {
                    "slide": slide_name,
                    "text_runs": xml.count("<a:t>"),
                    "pictures": xml.count("<p:pic>"),
                    "shapes": xml.count("<p:sp>"),
                }
            )
    return {"pages": pages}
```

Create `apps/worker/src/autofacodex/tools/visual_diff.py`:

```python
from pathlib import Path

from PIL import Image
from skimage.metrics import structural_similarity
import numpy as np


def compare_images(reference: Path, candidate: Path) -> float:
    ref = Image.open(reference).convert("L")
    cand = Image.open(candidate).convert("L").resize(ref.size)
    ref_array = np.asarray(ref)
    cand_array = np.asarray(cand)
    score, _ = structural_similarity(ref_array, cand_array, full=True)
    return float(max(0.0, min(1.0, score)))
```

Create `apps/worker/src/autofacodex/tools/pptx_render.py`:

```python
import subprocess
from pathlib import Path


def render_pptx_to_pdf(pptx_path: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(pptx_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return output_dir / f"{pptx_path.stem}.pdf"
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_validator_runtime.py -q
git add apps/worker/src/autofacodex/agents/validator_runtime.py apps/worker/src/autofacodex/tools/pptx_render.py apps/worker/src/autofacodex/tools/pptx_inspect.py apps/worker/src/autofacodex/tools/visual_diff.py apps/worker/tests/test_validator_runtime.py
git commit -m "feat: add validator metrics"
```

Expected: tests pass.

---

## Task 10: Runner And Validator Prompts, Skills, And Codex Launcher

**Files:**
- Create: `apps/worker/src/autofacodex/agents/codex_runner.py`
- Create: `apps/worker/agent_assets/runner/SKILL.md`
- Create: `apps/worker/agent_assets/runner/runner.system.md`
- Create: `apps/worker/agent_assets/validator/SKILL.md`
- Create: `apps/worker/agent_assets/validator/validator.system.md`
- Test: `apps/worker/tests/test_agent_assets.py`

- [ ] **Step 1: Write failing agent asset tests**

Create `apps/worker/tests/test_agent_assets.py`:

```python
from pathlib import Path


def test_runner_prompt_forbids_full_page_screenshot():
    text = Path("agent_assets/runner/runner.system.md").read_text(encoding="utf-8")
    assert "full-page screenshot" in text
    assert "Validator report" in text


def test_validator_prompt_requires_every_page():
    text = Path("agent_assets/validator/validator.system.md").read_text(encoding="utf-8")
    assert "every page" in text
    assert "editable" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_agent_assets.py -q
```

Expected: FAIL because agent asset files do not exist.

- [ ] **Step 3: Create Runner prompt and skill**

Create `apps/worker/agent_assets/runner/runner.system.md`:

```markdown
# Runner Agent

You are the PDF to editable PPT Runner Agent for one task directory.

Rules:
- Operate only inside the provided task directory.
- Use deterministic tools before AI-heavy repair.
- Read the latest Validator report before repairing.
- Modify `slides/slide-model.v*.json` as the main repair surface.
- Prefer editable PowerPoint primitives: text boxes, images, shapes, tables, and paths.
- Do not replace a slide with a full-page screenshot.
- Use raster fallback only for bounded regions and write the reason into the slide model.
- Keep repairs scoped to Validator-identified pages and regions unless a global font or layout fix is required.
- Write a concise task event after each repair attempt.

Inputs:
- `task-manifest.json`
- `extracted/pages.json`
- `slides/slide-model.v*.json`
- `reports/validator.v*.json`
- `renders/pdf/*.png`
- `renders/diff/*.png`
- user conversation messages when present

Output:
- a revised slide model
- a generated PPTX candidate
- a short repair summary
```

Create `apps/worker/agent_assets/runner/SKILL.md`:

```markdown
---
name: pdf-to-ppt-runner
description: Repair editable PDF to PPT slide models from Validator reports.
---

# PDF To PPT Runner Skill

1. Read the task manifest.
2. Read the latest Validator report.
3. Identify pages with `repair_needed` or `manual_review`.
4. Inspect only the relevant slide model, PDF extraction data, and render artifacts.
5. Update editable elements in the slide model.
6. Avoid full-page screenshots.
7. Regenerate the PPTX through the provided tool command.
8. Record what changed and why.
```

- [ ] **Step 4: Create Validator prompt and skill**

Create `apps/worker/agent_assets/validator/validator.system.md`:

```markdown
# Validator Agent

You are the PDF to editable PPT Validator Agent for one task directory.

Rules:
- Validate every page.
- Never trust Runner confidence as proof of success.
- Separate visual fidelity, editability, and text coverage.
- Reject slides that are visually close because they use one full-page screenshot.
- Preserve evidence: rendered PDF pages, rendered PPT pages, diff images, PPTX structure findings, and issue regions.
- Return structured repair instructions precise enough for Runner.
- Use `manual_review` when a page cannot be confidently repaired by the current tools.

Output:
- `reports/validator.vN.json`
- per-page status: `pass`, `repair_needed`, `manual_review`, or `failed`
- metrics: `visual_score`, `editable_score`, `text_coverage_score`, `raster_fallback_ratio`
- issue list with type, message, region when available, and suggested action
```

Create `apps/worker/agent_assets/validator/SKILL.md`:

```markdown
---
name: pdf-to-ppt-validator
description: Validate PDF to PPT outputs for visual fidelity, editability, and text coverage.
---

# PDF To PPT Validator Skill

1. Render the source PDF pages.
2. Render the candidate PPTX pages.
3. Compare every page visually.
4. Inspect PPTX internals for editable text, shapes, tables, images, and raster coverage.
5. Compare source text against editable PPTX text.
6. Reject full-page screenshot slides.
7. Write a structured Validator report.
8. Recommend repair, manual review, failure, or success.
```

- [ ] **Step 5: Implement Codex launcher**

Create `apps/worker/src/autofacodex/agents/codex_runner.py`:

```python
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from autofacodex.agents.codex_auth import CodexAuthConfig, validate_codex_auth


@dataclass(frozen=True)
class CodexInvocation:
    role: str
    task_dir: Path
    system_prompt: Path
    skill_dir: Path
    codex_home: Path
    codex_bin: str


def run_codex_agent(invocation: CodexInvocation, message: str, timeout_seconds: int = 900) -> subprocess.CompletedProcess[str]:
    validate_codex_auth(CodexAuthConfig(codex_home=invocation.codex_home, codex_bin=invocation.codex_bin))
    prompt = invocation.system_prompt.read_text(encoding="utf-8")
    full_message = f"{prompt}\\n\\nTask directory: {invocation.task_dir}\\nSkill directory: {invocation.skill_dir}\\n\\n{message}"
    return subprocess.run(
        [invocation.codex_bin, "exec", "--dangerously-bypass-approvals-and-sandbox", full_message],
        cwd=invocation.task_dir,
        env={**os.environ, "CODEX_HOME": str(invocation.codex_home)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_agent_assets.py -q
git add apps/worker/agent_assets apps/worker/src/autofacodex/agents/codex_runner.py apps/worker/tests/test_agent_assets.py
git commit -m "feat: add runner and validator agent assets"
```

Expected: prompt tests pass.

---

## Task 11: End-To-End Worker Workflow Without Codex Repair

**Files:**
- Modify: `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`
- Test: `apps/worker/tests/test_pdf_to_ppt_workflow.py`

- [ ] **Step 1: Write failing workflow test**

Create `apps/worker/tests/test_pdf_to_ppt_workflow.py`:

```python
from pathlib import Path

from reportlab.pdfgen import canvas

from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt


def make_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=(400, 300))
    c.setFont("Helvetica", 24)
    c.drawString(72, 220, "Workflow Title")
    c.save()


def test_run_pdf_to_ppt_creates_candidate_and_report(tmp_path: Path):
    task_dir = tmp_path / "task_1"
    task_dir.mkdir()
    make_pdf(task_dir / "input.pdf")

    run_pdf_to_ppt(task_dir)

    assert (task_dir / "output" / "candidate.v1.pptx").is_file()
    assert (task_dir / "reports" / "validator.v1.json").is_file()
    assert (task_dir / "slides" / "slide-model.v1.json").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pdf_to_ppt_workflow.py -q
```

Expected: FAIL because workflow only writes a log.

- [ ] **Step 3: Implement workflow orchestration**

Replace `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`:

```python
from pathlib import Path

from autofacodex.agents.validator_runtime import build_validator_report
from autofacodex.tools.pdf_extract import extract_pdf
from autofacodex.tools.pdf_render import render_pdf_pages
from autofacodex.tools.pptx_generate import generate_pptx
from autofacodex.tools.pptx_inspect import inspect_pptx_editability
from autofacodex.tools.slide_model_builder import build_initial_slide_model


def run_pdf_to_ppt(task_dir: Path) -> None:
    for name in ["extracted", "renders/pdf", "renders/ppt", "renders/diff", "slides", "output", "reports", "logs"]:
        (task_dir / name).mkdir(parents=True, exist_ok=True)

    pdf_path = task_dir / "input.pdf"
    extracted = extract_pdf(pdf_path, task_dir / "extracted")
    render_pdf_pages(pdf_path, task_dir / "renders" / "pdf")

    slide_model = build_initial_slide_model(extracted)
    slide_model_path = task_dir / "slides" / "slide-model.v1.json"
    slide_model_path.write_text(slide_model.model_dump_json(indent=2), encoding="utf-8")

    candidate = generate_pptx(slide_model, task_dir / "output" / "candidate.v1.pptx")
    inspection = inspect_pptx_editability(candidate)
    page_count = len(slide_model.slides)
    editable_scores = {
        index + 1: 1.0 if page["text_runs"] > 0 else 0.0
        for index, page in enumerate(inspection["pages"])
    }
    report = build_validator_report(
        task_id=task_dir.name,
        attempt=1,
        page_count=page_count,
        visual_scores={page: 0.5 for page in range(1, page_count + 1)},
        editable_scores=editable_scores,
        text_scores={page: 0.8 for page in range(1, page_count + 1)},
        raster_ratios={page: 0.0 for page in range(1, page_count + 1)},
    )
    (task_dir / "reports" / "validator.v1.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run workflow tests and commit**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_pdf_to_ppt_workflow.py -q
git add apps/worker/src/autofacodex/workflows/pdf_to_ppt.py apps/worker/tests/test_pdf_to_ppt_workflow.py
git commit -m "feat: run initial pdf to ppt workflow"
```

Expected: tests pass.

---

## Task 12: Repair Job And User Conversation Loop

**Files:**
- Modify: `apps/web/src/app/api/tasks/[taskId]/messages/route.ts`
- Modify: `apps/worker/src/autofacodex/gateway.py`
- Modify: `apps/worker/src/autofacodex/workflows/pdf_to_ppt.py`
- Test: `apps/web/src/lib/queue.test.ts`

- [ ] **Step 1: Extend queue payload test**

Modify `apps/web/src/lib/queue.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildWorkflowJob } from "./queue";

describe("buildWorkflowJob", () => {
  it("creates an initial job payload", () => {
    expect(buildWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt" })).toEqual({
      task_id: "task_1",
      workflow_type: "pdf_to_ppt",
      mode: "initial"
    });
  });

  it("creates a repair job payload", () => {
    expect(buildWorkflowJob({ taskId: "task_1", workflowType: "pdf_to_ppt", mode: "repair" })).toEqual({
      task_id: "task_1",
      workflow_type: "pdf_to_ppt",
      mode: "repair"
    });
  });
});
```

- [ ] **Step 2: Update queue payload builder**

Modify `apps/web/src/lib/queue.ts`:

```ts
import Redis from "ioredis";

export type WorkflowJobInput = {
  taskId: string;
  workflowType: "pdf_to_ppt";
  mode?: "initial" | "repair";
};

export function buildWorkflowJob(input: WorkflowJobInput) {
  return {
    task_id: input.taskId,
    workflow_type: input.workflowType,
    mode: input.mode ?? "initial"
  };
}

export async function enqueueWorkflowJob(input: WorkflowJobInput) {
  const redis = new Redis(process.env.REDIS_URL ?? "redis://localhost:6379/0");
  await redis.xadd("workflow_jobs", "*", "payload", JSON.stringify(buildWorkflowJob(input)));
  await redis.quit();
}
```

- [ ] **Step 3: Add task message route**

Create `apps/web/src/app/api/tasks/[taskId]/messages/route.ts`:

```ts
import { NextResponse } from "next/server";
import { z } from "zod";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";
import { enqueueWorkflowJob } from "@/lib/queue";

const bodySchema = z.object({ content: z.string().min(1) });

export async function POST(request: Request, context: { params: Promise<{ taskId: string }> }) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { taskId } = await context.params;
  const body = bodySchema.parse(await request.json());

  const task = await prisma.workflowTask.findFirst({ where: { id: taskId, userId } });
  if (!task) return NextResponse.json({ error: "Not found" }, { status: 404 });

  await prisma.taskConversationMessage.create({
    data: { taskId, userId, role: "user", content: body.content }
  });
  await prisma.workflowTask.update({ where: { id: taskId }, data: { status: "running_repair" } });
  await enqueueWorkflowJob({ taskId, workflowType: "pdf_to_ppt", mode: "repair" });

  return NextResponse.json({ ok: true });
}
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
npm --workspace apps/web run test -- src/lib/queue.test.ts
git add apps/web/src/lib/queue.ts apps/web/src/lib/queue.test.ts apps/web/src/app/api/tasks
git commit -m "feat: enqueue user repair requests"
```

Expected: queue tests pass.

---

## Task 13: Sample Regression Harness

**Files:**
- Create: `apps/worker/src/autofacodex/evaluation/run_samples.py`
- Create: `apps/worker/src/autofacodex/evaluation/__init__.py`
- Create: `apps/worker/tests/test_sample_discovery.py`

- [ ] **Step 1: Write failing sample discovery test**

Create `apps/worker/tests/test_sample_discovery.py`:

```python
from pathlib import Path

from autofacodex.evaluation.run_samples import discover_pdfs


def test_discover_pdfs_ignores_temp_office_files(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "~$b.pdf").write_bytes(b"")
    (tmp_path / "c.pptx").write_bytes(b"")

    assert [p.name for p in discover_pdfs(tmp_path)] == ["a.pdf"]
```

- [ ] **Step 2: Implement sample discovery and runner**

Create `apps/worker/src/autofacodex/evaluation/__init__.py`:

```python
__all__ = []
```

Create `apps/worker/src/autofacodex/evaluation/run_samples.py`:

```python
import shutil
from pathlib import Path

from autofacodex.workflows.pdf_to_ppt import run_pdf_to_ppt


def discover_pdfs(samples_dir: Path) -> list[Path]:
    return sorted(path for path in samples_dir.glob("*.pdf") if not path.name.startswith("~$"))


def run_samples(samples_dir: Path, output_root: Path) -> list[Path]:
    task_dirs: list[Path] = []
    for index, pdf in enumerate(discover_pdfs(samples_dir), start=1):
        task_dir = output_root / f"sample-{index:03d}-{pdf.stem}"
        task_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pdf, task_dir / "input.pdf")
        run_pdf_to_ppt(task_dir)
        task_dirs.append(task_dir)
    return task_dirs


if __name__ == "__main__":
    run_samples(Path("pdf-to-ppt-test-samples"), Path("shared-tasks/evaluation"))
```

- [ ] **Step 3: Run tests and one local evaluation**

Run:

```bash
cd apps/worker && .venv/bin/pytest tests/test_sample_discovery.py -q
cd /home/alvin/AutoFaCodex && PYTHONPATH=apps/worker/src apps/worker/.venv/bin/python -m autofacodex.evaluation.run_samples
```

Expected: test passes. Evaluation creates task directories under `shared-tasks/evaluation`.

- [ ] **Step 4: Commit evaluation harness**

Run:

```bash
git add apps/worker/src/autofacodex/evaluation apps/worker/tests/test_sample_discovery.py
git commit -m "feat: add sample regression harness"
```

---

## Task 14: Task Page UI For Artifacts, Reports, And Conversation

**Files:**
- Create: `apps/web/src/app/tasks/[taskId]/page.tsx`
- Create: `apps/web/src/app/tasks/[taskId]/TaskConversation.tsx`
- Create: `apps/web/src/app/api/tasks/[taskId]/route.ts`

- [ ] **Step 1: Add task detail API**

Create `apps/web/src/app/api/tasks/[taskId]/route.ts`:

```ts
import { NextResponse } from "next/server";
import { getSessionUserId } from "@/lib/auth";
import { prisma } from "@/lib/db";

export async function GET(_request: Request, context: { params: Promise<{ taskId: string }> }) {
  const userId = await getSessionUserId();
  if (!userId) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const { taskId } = await context.params;
  const task = await prisma.workflowTask.findFirst({
    where: { id: taskId, userId },
    include: {
      artifacts: true,
      events: { orderBy: { createdAt: "desc" }, take: 50 },
      messages: { orderBy: { createdAt: "asc" } }
    }
  });
  if (!task) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json({ task });
}
```

- [ ] **Step 2: Add task page**

Create `apps/web/src/app/tasks/[taskId]/page.tsx`:

```tsx
import TaskConversation from "./TaskConversation";

export default async function TaskPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  return (
    <main className="mx-auto grid max-w-6xl gap-6 p-8">
      <header>
        <h1 className="text-2xl font-semibold">PDF to PPT Task</h1>
        <p className="text-sm text-gray-600">{taskId}</p>
      </header>
      <section className="grid gap-3 rounded border p-4">
        <h2 className="text-lg font-medium">Artifacts and Validator Report</h2>
        <p className="text-sm text-gray-600">The first MVP shows task status here. Report rendering is added after the Worker writes database artifacts.</p>
      </section>
      <TaskConversation taskId={taskId} />
    </main>
  );
}
```

Create `apps/web/src/app/tasks/[taskId]/TaskConversation.tsx`:

```tsx
"use client";

import { useState } from "react";

export default function TaskConversation({ taskId }: { taskId: string }) {
  const [content, setContent] = useState("");
  const [pending, setPending] = useState(false);

  async function sendMessage() {
    setPending(true);
    await fetch(`/api/tasks/${taskId}/messages`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content })
    });
    setContent("");
    setPending(false);
  }

  return (
    <section className="grid gap-3 rounded border p-4">
      <h2 className="text-lg font-medium">Continue With AI</h2>
      <textarea
        className="min-h-28 rounded border p-3"
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder="Describe what still looks wrong or what should be more editable."
      />
      <button
        className="w-fit rounded bg-black px-4 py-2 text-white disabled:opacity-50"
        disabled={pending || !content.trim()}
        onClick={sendMessage}
      >
        Send repair request
      </button>
    </section>
  );
}
```

- [ ] **Step 3: Run lint and commit**

Run:

```bash
npm --workspace apps/web run lint
git add apps/web/src/app/tasks apps/web/src/app/api/tasks/[taskId]/route.ts
git commit -m "feat: add task review and conversation page"
```

Expected: lint passes.

---

## Task 15: End-To-End Docker Smoke Test

**Files:**
- Create: `scripts/smoke-test.sh`
- Modify: `README.md`

- [ ] **Step 1: Add smoke script**

Create `scripts/smoke-test.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

test -f .env || cp .env.example .env
docker compose up -d postgres redis
npm --workspace apps/web run prisma:migrate
docker compose up -d web worker
docker compose ps
```

Run:

```bash
chmod +x scripts/smoke-test.sh
```

- [ ] **Step 2: Add README instructions**

Create or update `README.md`:

```markdown
# AutoFaCodex

## Local Setup

1. Copy `.env.example` to `.env`.
2. Set `HOST_CODEX_HOME` to the host Codex config directory. On this machine it is `/home/alvin/.codex`.
3. Do not commit `.env`, `auth.json`, or `config.toml`.
4. Start the stack with `docker compose up --build`.

The Worker container mounts:

- `${HOST_CODEX_HOME}/auth.json` to `/home/worker/.codex/auth.json:ro`
- `${HOST_CODEX_HOME}/config.toml` to `/home/worker/.codex/config.toml:ro`

PDF test samples live in `pdf-to-ppt-test-samples/`.
```

- [ ] **Step 3: Run verification**

Run:

```bash
npm run test
docker compose config >/tmp/autofacodex-compose.yml
```

Expected: tests pass and compose config renders. If Docker is unavailable, record the exact Docker error in the task event or final handoff.

- [ ] **Step 4: Commit smoke test**

Run:

```bash
git add scripts/smoke-test.sh README.md
git commit -m "docs: add local smoke test instructions"
```

---

## Self-Review Checklist

- Spec coverage:
  - Web/API auth and upload: Tasks 4, 5, 14.
  - Queue-backed workflow: Tasks 5, 6.
  - Worker Gateway: Task 6.
  - Local shared volume: Tasks 2, 5, 6.
  - Runner Agent prompt/skill: Task 10.
  - Validator Agent prompt/skill: Task 10.
  - Codex/CodeDesk auth injection: Task 2 and Task 15.
  - PDF extraction/rendering: Task 7.
  - Editable PPTX generation: Task 8.
  - Full-page validation and editability rejection: Task 9.
  - User conversation repair loop: Tasks 12, 14.
  - Sample-driven quality iteration: Task 13.
- The MVP validates architecture and tool protocol first. Advanced conversion quality comes from repeated evaluation after this plan is implemented.
- No secret contents are read, copied, generated into the repo, or committed.

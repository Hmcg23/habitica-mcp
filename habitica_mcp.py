#!/usr/bin/env python3
"""
MCP Server for Habitica.

Provides tools to interact with the Habitica API, including reading tasks,
scoring habits, managing todos and dailies, and viewing user stats.

Authentication:
    Set the following environment variables before running:
        HABITICA_USER_ID  — your Habitica User ID (Settings → API)
        HABITICA_API_KEY  — your Habitica API Token (Settings → API)
"""

import json
import os
from enum import Enum
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Server init
# ---------------------------------------------------------------------------

mcp = FastMCP("habitica_mcp")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE = "https://habitica.com/api/v3"
CLIENT_HEADER = "habitica-mcp/1.0"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _auth_headers() -> dict:
    user_id = os.environ.get("HABITICA_USER_ID", "")
    api_key = os.environ.get("HABITICA_API_KEY", "")
    if not user_id or not api_key:
        raise RuntimeError(
            "Missing credentials. Set HABITICA_USER_ID and HABITICA_API_KEY "
            "environment variables (find them in Habitica → Settings → API)."
        )
    return {
        "x-api-user": user_id,
        "x-api-key": api_key,
        "x-client": CLIENT_HEADER,
        "Content-Type": "application/json",
    }


async def _request(method: str, path: str, **kwargs) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method,
            f"{API_BASE}{path}",
            headers=_auth_headers(),
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json()


def _handle_error(e: Exception) -> str:
    if isinstance(e, RuntimeError):
        return f"Error: {e}"
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 401:
            return "Error: Invalid credentials. Check your HABITICA_USER_ID and HABITICA_API_KEY."
        if code == 404:
            return "Error: Not found. Check that the task ID is correct."
        if code == 429:
            return "Error: Rate limit hit. Wait a moment before retrying."
        try:
            msg = e.response.json().get("message", str(e))
        except Exception:
            msg = str(e)
        return f"Error {code}: {msg}"
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Try again."
    return f"Error: {type(e).__name__}: {e}"


def _fmt_task(t: dict) -> dict:
    """Normalize a raw Habitica task dict into a clean summary."""
    out: dict = {
        "id": t.get("id", ""),
        "type": t.get("type", ""),
        "text": t.get("text", ""),
        "notes": t.get("notes", ""),
    }
    if t.get("type") == "todo":
        out["completed"] = t.get("completed", False)
        out["due"] = t.get("date") or None
    if t.get("type") == "daily":
        out["completed"] = t.get("completed", False)
        out["streak"] = t.get("streak", 0)
        out["isDue"] = t.get("isDue", False)
    if t.get("type") == "habit":
        out["up"] = t.get("up", True)
        out["down"] = t.get("down", False)
        out["counterUp"] = t.get("counterUp", 0)
        out["counterDown"] = t.get("counterDown", 0)
    priority_map = {0.1: "trivial", 1: "easy", 1.5: "medium", 2: "hard"}
    out["priority"] = priority_map.get(t.get("priority", 1), "easy")
    if t.get("checklist"):
        out["checklist"] = [
            {"id": c["id"], "text": c["text"], "completed": c["completed"]}
            for c in t["checklist"]
        ]
    return out


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class TaskType(str, Enum):
    HABITS = "habits"
    DAILYS = "dailys"
    TODOS = "todos"
    REWARDS = "rewards"
    COMPLETED_TODOS = "completedTodos"


class ScoreDirection(str, Enum):
    UP = "up"
    DOWN = "down"


class GetTasksInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    type: Optional[TaskType] = Field(
        default=None,
        description=(
            "Filter by task type: 'habits', 'dailys', 'todos', 'rewards', "
            "or 'completedTodos'. Omit to return all active task types."
        ),
    )


class GetTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task_id: str = Field(
        ..., description="The Habitica task ID (UUID). Get it from habitica_get_tasks."
    )


class ScoreTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task_id: str = Field(..., description="The Habitica task ID to score.")
    direction: ScoreDirection = Field(
        ...,
        description=(
            "'up' to score positively (check off a daily/todo, click + on a habit); "
            "'down' to score negatively (click - on a habit, uncheck a todo/daily)."
        ),
    )


class CreateTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    text: str = Field(..., description="Task title.", min_length=1, max_length=500)
    type: TaskType = Field(
        ...,
        description="Task type: 'habits', 'dailys', 'todos', or 'rewards'.",
    )
    notes: Optional[str] = Field(default=None, description="Optional notes / description.")
    priority: Optional[str] = Field(
        default=None,
        description="Difficulty: 'trivial', 'easy', 'medium', or 'hard'. Defaults to 'easy'.",
    )
    due_date: Optional[str] = Field(
        default=None,
        description="Due date for todos, ISO 8601 format (e.g. '2026-06-15').",
    )


class UpdateTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task_id: str = Field(..., description="The Habitica task ID to update.")
    text: Optional[str] = Field(default=None, description="New title.", max_length=500)
    notes: Optional[str] = Field(default=None, description="New notes.")
    priority: Optional[str] = Field(
        default=None,
        description="New difficulty: 'trivial', 'easy', 'medium', or 'hard'.",
    )
    due_date: Optional[str] = Field(
        default=None, description="New due date (ISO 8601). Todos only."
    )


class DeleteTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task_id: str = Field(..., description="The Habitica task ID to delete.")


class AddChecklistItemInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task_id: str = Field(..., description="Task ID to add checklist item to.")
    text: str = Field(..., description="Text for the checklist item.", min_length=1)


class ScoreChecklistItemInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task_id: str = Field(..., description="Task ID containing the checklist item.")
    item_id: str = Field(..., description="Checklist item ID to toggle.")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(
    name="habitica_get_tasks",
    annotations={
        "title": "Get Habitica Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def habitica_get_tasks(params: GetTasksInput) -> str:
    """Get tasks from the authenticated Habitica user's task list.

    Returns habits, dailies, todos, or rewards depending on the type filter.
    For todos, only incomplete items are returned unless type='completedTodos'.

    Args:
        params (GetTasksInput):
            - type (Optional[TaskType]): Filter by task type. Omit for all types.

    Returns:
        str: JSON array of task objects, each with:
            - id (str): UUID, needed for scoring/updating/deleting
            - type (str): 'habit', 'daily', 'todo', or 'reward'
            - text (str): Task title
            - notes (str): Task notes
            - priority (str): 'trivial', 'easy', 'medium', or 'hard'
            - completed (bool): For dailies/todos
            - isDue (bool): For dailies — whether due today
            - streak (int): For dailies — current streak
            - checklist (list): Sub-items, if any
    """
    try:
        params_dict = {}
        if params.type:
            params_dict["type"] = params.type.value
        data = await _request("GET", "/tasks/user", params=params_dict)
        tasks = [_fmt_task(t) for t in data.get("data", [])]
        return json.dumps(tasks, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="habitica_get_task",
    annotations={
        "title": "Get Single Habitica Task",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def habitica_get_task(params: GetTaskInput) -> str:
    """Get full details for a single Habitica task by ID.

    Args:
        params (GetTaskInput):
            - task_id (str): The task UUID from habitica_get_tasks.

    Returns:
        str: JSON object with full task details including checklist items.
    """
    try:
        data = await _request("GET", f"/tasks/{params.task_id}")
        return json.dumps(_fmt_task(data.get("data", {})), indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="habitica_get_user_stats",
    annotations={
        "title": "Get Habitica User Stats",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def habitica_get_user_stats() -> str:
    """Get the authenticated user's Habitica profile, stats, and streaks.

    Returns:
        str: JSON object with:
            - username (str)
            - level (int)
            - class (str): warrior, healer, rogue, or wizard
            - hp, mp, exp, gp, gems (numbers)
            - streak (int): daily login streak
    """
    try:
        data = await _request("GET", "/user")
        u = data.get("data", {})
        stats = u.get("stats", {})
        result = {
            "username": u.get("profile", {}).get("name", ""),
            "level": stats.get("lvl", 0),
            "class": stats.get("class", ""),
            "hp": round(stats.get("hp", 0), 1),
            "hp_max": stats.get("maxHealth", 50),
            "mp": round(stats.get("mp", 0), 1),
            "mp_max": stats.get("maxMP", 0),
            "exp": round(stats.get("exp", 0), 1),
            "exp_to_next": stats.get("toNextLevel", 0),
            "gp": round(stats.get("gp", 0), 2),
            "gems": u.get("balance", 0) * 4,
            "login_streak": u.get("streak", 0),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="habitica_score_task",
    annotations={
        "title": "Score a Habitica Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def habitica_score_task(params: ScoreTaskInput) -> str:
    """Score a Habitica task up or down.

    - For todos/dailies: 'up' marks complete, 'down' marks incomplete.
    - For habits: 'up' clicks the + button, 'down' clicks the - button.

    Args:
        params (ScoreTaskInput):
            - task_id (str): UUID of the task to score.
            - direction (str): 'up' or 'down'.

    Returns:
        str: JSON with XP gained, gold gained, HP change, and level-up info.
    """
    try:
        data = await _request("POST", f"/tasks/{params.task_id}/score/{params.direction.value}")
        d = data.get("data", {})
        result = {
            "xp_gained": round(d.get("_tmp", {}).get("exp", 0), 2),
            "gold_gained": round(d.get("_tmp", {}).get("gp", 0), 2),
            "hp_change": round(d.get("_tmp", {}).get("hp", 0), 2),
            "leveled_up": d.get("_tmp", {}).get("lvl") is not None,
            "level": d.get("lvl", 0),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="habitica_create_task",
    annotations={
        "title": "Create a Habitica Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def habitica_create_task(params: CreateTaskInput) -> str:
    """Create a new task in Habitica.

    Args:
        params (CreateTaskInput):
            - text (str): Task title.
            - type (str): 'habits', 'dailys', 'todos', or 'rewards'.
            - notes (Optional[str]): Description/notes.
            - priority (Optional[str]): 'trivial', 'easy', 'medium', or 'hard'.
            - due_date (Optional[str]): ISO 8601 date for todos (e.g. '2026-06-15').

    Returns:
        str: JSON with the created task's id and details.
    """
    priority_map = {"trivial": 0.1, "easy": 1, "medium": 1.5, "hard": 2}
    type_map = {"habits": "habit", "dailys": "daily", "todos": "todo", "rewards": "reward"}
    body: dict = {
        "text": params.text,
        "type": type_map.get(params.type.value, params.type.value),
    }
    if params.notes:
        body["notes"] = params.notes
    if params.priority:
        body["priority"] = priority_map.get(params.priority, 1)
    if params.due_date and params.type == TaskType.TODOS:
        body["date"] = params.due_date
    try:
        data = await _request("POST", "/tasks/user", json=body)
        return json.dumps(_fmt_task(data.get("data", {})), indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="habitica_update_task",
    annotations={
        "title": "Update a Habitica Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def habitica_update_task(params: UpdateTaskInput) -> str:
    """Update an existing Habitica task's title, notes, priority, or due date.

    Args:
        params (UpdateTaskInput):
            - task_id (str): UUID of the task to update.
            - text (Optional[str]): New title.
            - notes (Optional[str]): New notes.
            - priority (Optional[str]): New difficulty level.
            - due_date (Optional[str]): New due date (todos only).

    Returns:
        str: JSON with the updated task details.
    """
    priority_map = {"trivial": 0.1, "easy": 1, "medium": 1.5, "hard": 2}
    body: dict = {}
    if params.text is not None:
        body["text"] = params.text
    if params.notes is not None:
        body["notes"] = params.notes
    if params.priority is not None:
        body["priority"] = priority_map.get(params.priority, 1)
    if params.due_date is not None:
        body["date"] = params.due_date
    if not body:
        return "Error: No fields to update. Provide at least one of: text, notes, priority, due_date."
    try:
        data = await _request("PUT", f"/tasks/{params.task_id}", json=body)
        return json.dumps(_fmt_task(data.get("data", {})), indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="habitica_delete_task",
    annotations={
        "title": "Delete a Habitica Task",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def habitica_delete_task(params: DeleteTaskInput) -> str:
    """Permanently delete a Habitica task. This cannot be undone.

    Args:
        params (DeleteTaskInput):
            - task_id (str): UUID of the task to delete.

    Returns:
        str: Confirmation message or error.
    """
    try:
        await _request("DELETE", f"/tasks/{params.task_id}")
        return json.dumps({"deleted": True, "task_id": params.task_id})
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="habitica_add_checklist_item",
    annotations={
        "title": "Add Checklist Item to Habitica Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def habitica_add_checklist_item(params: AddChecklistItemInput) -> str:
    """Add a checklist item to an existing Habitica daily or todo.

    Args:
        params (AddChecklistItemInput):
            - task_id (str): UUID of the parent task.
            - text (str): Text for the new checklist item.

    Returns:
        str: JSON with the updated task including the new checklist item.
    """
    try:
        data = await _request(
            "POST",
            f"/tasks/{params.task_id}/checklist",
            json={"text": params.text},
        )
        return json.dumps(_fmt_task(data.get("data", {})), indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="habitica_score_checklist_item",
    annotations={
        "title": "Toggle Habitica Checklist Item",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def habitica_score_checklist_item(params: ScoreChecklistItemInput) -> str:
    """Toggle a checklist item on a Habitica daily or todo (mark complete/incomplete).

    Args:
        params (ScoreChecklistItemInput):
            - task_id (str): UUID of the parent task.
            - item_id (str): UUID of the checklist item to toggle.

    Returns:
        str: JSON with the updated task.
    """
    try:
        data = await _request(
            "POST",
            f"/tasks/{params.task_id}/checklist/{params.item_id}/score",
        )
        return json.dumps(_fmt_task(data.get("data", {})), indent=2)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

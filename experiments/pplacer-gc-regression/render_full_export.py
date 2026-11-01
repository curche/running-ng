#!/usr/bin/env python3
"""Render a Claude Code session JSONL transcript into a full, untruncated
markdown log: every user message, assistant message, tool call, and complete
tool output.

The built-in `/export` command collapses tool calls to one-line summaries
("ran 1 shell command") and drops their output. This reads the raw session
transcript (~/.claude/projects/<project>/<session-id>.jsonl) instead, which
retains full tool_use inputs and tool_result content.

Usage:
    python3 render_full_export.py <session-id-or-path-to-jsonl> <output.md>

If the first argument doesn't look like a path, it's treated as a session ID
and resolved under the current project's transcript directory
(~/.claude/projects/<slug of $PWD>/<session-id>.jsonl).
"""
import json
import os
import sys


def resolve_src(arg: str) -> str:
    if os.path.exists(arg):
        return arg
    # Treat as a bare session ID; resolve against this project's transcript dir.
    slug = os.getcwd().replace("/", "-")
    candidate = os.path.expanduser(
        f"~/.claude/projects/{slug}/{arg}.jsonl"
    )
    if os.path.exists(candidate):
        return candidate
    raise FileNotFoundError(
        f"Could not find transcript for {arg!r} (tried {arg!r} and {candidate!r})"
    )


def fmt_tool_result_content(content):
    # content can be str, or list of {type: text/image, ...}
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    out.append(item.get("text", ""))
                elif item.get("type") == "image":
                    out.append("[image content omitted]")
                else:
                    out.append(json.dumps(item, indent=2))
            else:
                out.append(str(item))
        return "\n".join(out)
    return json.dumps(content, indent=2)


def render(src_path: str, out_path: str, include_thinking: bool = False):
    entries = []
    with open(src_path) as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            entries.append(json.loads(raw))

    session_id = None
    for e in entries:
        if e.get("sessionId"):
            session_id = e["sessionId"]
            break

    out = []
    out.append("# Full Session Export")
    out.append("")
    out.append(f"Session ID: {session_id}")
    out.append(f"Project cwd: {os.getcwd()}")
    out.append("")
    out.append(
        "Complete raw transcript (every user message, assistant message, "
        "tool call, and full tool output)."
    )
    out.append("")
    out.append("---")
    out.append("")

    # tool_use_id -> (tool name, input), so tool_result blocks can be labeled
    tool_use_index = {}
    turn_num = 0

    for entry in entries:
        etype = entry.get("type")

        if etype == "user":
            msg = entry.get("message", {})
            content = msg.get("content")
            if isinstance(content, str):
                turn_num += 1
                out.append(f"## USER (turn {turn_num})")
                out.append("")
                out.append(content)
                out.append("")
            elif isinstance(content, list):
                has_tool_result = any(
                    isinstance(c, dict) and c.get("type") == "tool_result"
                    for c in content
                )
                has_text = any(
                    isinstance(c, dict) and c.get("type") == "text" for c in content
                )
                if has_tool_result:
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "tool_result":
                            tu_id = c.get("tool_use_id")
                            name, _ = tool_use_index.get(tu_id, ("unknown_tool", {}))
                            out.append(f"### TOOL RESULT  (`{name}`)")
                            out.append("")
                            out.append("```")
                            out.append(fmt_tool_result_content(c.get("content")))
                            out.append("```")
                            out.append("")
                if has_text:
                    turn_num += 1
                    out.append(f"## USER (turn {turn_num})")
                    out.append("")
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            out.append(c.get("text", ""))
                    out.append("")

        elif etype == "assistant":
            msg = entry.get("message", {})
            content = msg.get("content")
            if isinstance(content, list):
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    ctype = c.get("type")
                    if ctype == "text":
                        txt = c.get("text", "")
                        if txt.strip():
                            out.append("## ASSISTANT")
                            out.append("")
                            out.append(txt)
                            out.append("")
                    elif ctype == "thinking":
                        if include_thinking:
                            txt = c.get("thinking", "")
                            if txt.strip():
                                out.append("<details><summary>thinking</summary>")
                                out.append("")
                                out.append(txt)
                                out.append("")
                                out.append("</details>")
                                out.append("")
                    elif ctype == "tool_use":
                        tool_use_index[c.get("id")] = (c.get("name"), c.get("input"))
                        out.append(f"### TOOL CALL: `{c.get('name')}`")
                        out.append("")
                        out.append("```json")
                        out.append(json.dumps(c.get("input", {}), indent=2))
                        out.append("```")
                        out.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(out))

    print(f"wrote {out_path} ({len(out)} lines)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src = resolve_src(sys.argv[1])
    render(src, sys.argv[2])

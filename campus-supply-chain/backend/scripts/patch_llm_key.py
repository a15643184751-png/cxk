"""将 LLM_API_KEY 写入 backend/.env（存在则替换该行，不存在则追加）。"""
from __future__ import annotations

import pathlib
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python patch_llm_key.py <API_KEY>")
        return 1
    key = (sys.argv[1] or "").strip()
    if not key:
        print("Key 为空，已跳过写入。")
        return 0
    root = pathlib.Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = text.splitlines()
    out: list[str] = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("LLM_API_KEY=") or stripped.startswith("LLM_API_KEY ="):
            out.append(f"LLM_API_KEY={key}")
            found = True
        else:
            out.append(line)
    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(f"LLM_API_KEY={key}")
    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(f"已更新 {env_path} 中的 LLM_API_KEY。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

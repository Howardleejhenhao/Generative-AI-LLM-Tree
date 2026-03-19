def build_demo_workspace_payload() -> dict:
    return {
        "workspace": {
            "id": "demo-workspace",
            "name": "Launch Review",
            "slug": "launch-review",
            "description": (
                "Demo workspace shown before the first real conversation tree is created."
            ),
        },
        "nodes": [
            {
                "id": "demo-root",
                "parent_id": None,
                "edited_from_id": None,
                "title": "Root Brief",
                "summary": "Define the rollout theme and constraints.",
                "provider": "openai",
                "model_name": "gpt-4.1-mini",
                "position": {"x": 80, "y": 120},
                "messages": [
                    {
                        "id": "m1",
                        "role": "system",
                        "content": "You are coordinating a branching conversation workspace.",
                        "order_index": 0,
                    },
                    {
                        "id": "m2",
                        "role": "user",
                        "content": "Outline a product launch plan for an experimental DAG chat UI.",
                        "order_index": 1,
                    },
                    {
                        "id": "m3",
                        "role": "assistant",
                        "content": (
                            "Start with graph navigation, branch-aware context, and model"
                            " comparison hooks."
                        ),
                        "order_index": 2,
                    },
                ],
            },
            {
                "id": "demo-openai-branch",
                "parent_id": "demo-root",
                "edited_from_id": None,
                "title": "OpenAI Angle",
                "summary": "Focus on fast iteration and structured streaming UI.",
                "provider": "openai",
                "model_name": "gpt-4.1",
                "position": {"x": 420, "y": 70},
                "messages": [
                    {
                        "id": "m4",
                        "role": "user",
                        "content": "Continue from the root and suggest a first milestone.",
                        "order_index": 0,
                    },
                    {
                        "id": "m5",
                        "role": "assistant",
                        "content": (
                            "Milestone one should ship the node canvas, side panel, and"
                            " parent-child lineage rules."
                        ),
                        "order_index": 1,
                    },
                ],
            },
            {
                "id": "demo-gemini-branch",
                "parent_id": "demo-root",
                "edited_from_id": None,
                "title": "Gemini Angle",
                "summary": "Explore alternate phrasing and comparative branch outcomes.",
                "provider": "gemini",
                "model_name": "gemini-2.0-flash",
                "position": {"x": 420, "y": 310},
                "messages": [
                    {
                        "id": "m6",
                        "role": "user",
                        "content": "Branch from the same root but optimize for experimentation.",
                        "order_index": 0,
                    },
                    {
                        "id": "m7",
                        "role": "assistant",
                        "content": (
                            "Track each branch independently so prompt edits never pollute"
                            " sibling context."
                        ),
                        "order_index": 1,
                    },
                ],
            },
            {
                "id": "demo-edit-branch",
                "parent_id": "demo-openai-branch",
                "edited_from_id": "demo-openai-branch",
                "title": "Edited Re-branch",
                "summary": "Version-safe branch created from an older node revision.",
                "provider": "gemini",
                "model_name": "gemini-2.0-pro-exp",
                "position": {"x": 760, "y": 150},
                "messages": [
                    {
                        "id": "m8",
                        "role": "user",
                        "content": "Revise the milestone to add editable history handling.",
                        "order_index": 0,
                    },
                    {
                        "id": "m9",
                        "role": "assistant",
                        "content": (
                            "Preserve the original node, fork an edited variant, and render"
                            " both as separate children."
                        ),
                        "order_index": 1,
                    },
                ],
            },
        ],
    }

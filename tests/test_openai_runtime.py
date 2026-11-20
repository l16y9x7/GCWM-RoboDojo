from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from roboskylar.arms import ArmResult, ArmToolkit
from roboskylar.openai_runtime import _Transcript, run_openai_agent


def test_transcript_keeps_image_parts_and_records_archive_refs(tmp_path):
    transcript = _Transcript(tmp_path)
    transcript.add(
        {"role": "user", "content": "checkpoint"},
        [("cam_head.png", b"head"), ("cam_right_wrist.png", b"wrist")],
    )

    assert [part["type"] for part in transcript.messages[0]["content"]] == [
        "text", "image_url", "image_url"
    ]
    assert transcript.recorded[0]["content"][-1] == {
        "type": "image_ref",
        "image_ref": str(tmp_path / "images" / "002_cam_right_wrist.png"),
    }


def test_transcript_image_limit_drops_oldest_from_future_requests(tmp_path):
    transcript = _Transcript(tmp_path)
    transcript.add(
        {"role": "user", "content": "scene"},
        [("a.png", b"a"), ("b.png", b"b")],
    )
    transcript.enforce_image_limit(1)

    assert [part["type"] for part in transcript.messages[0]["content"]] == ["text", "image_url"]
    assert transcript.recorded[0]["content"][-1]["image_ref"].endswith("002_b.png")


def test_request_manifest_indexes_context_without_copying_content(tmp_path):
    transcript = _Transcript(tmp_path)
    transcript.add({"role": "user", "content": "scene"}, [("initial.png", b"first")])
    first_request = transcript.request_manifest(1, 1)
    transcript.add(
        {"role": "user", "content": "new observation"}, [("display_0.png", b"second")]
    )
    transcript.enforce_image_limit(1)
    second_request = transcript.request_manifest(2, 1)

    first_images = [
        image["image_ref"]
        for message in first_request["messages"]
        for image in message["images"]
    ]
    second_images = [
        image["image_ref"]
        for message in second_request["messages"]
        for image in message["images"]
    ]
    assert first_images == [str(tmp_path / "images" / "001_initial.png")]
    assert second_images == [str(tmp_path / "images" / "002_display_0.png")]
    assert all("content" not in message for message in first_request["messages"])
    assert all(Path(image).is_file() for image in first_images + second_images)


def test_on_primitive_attaches_each_stateful_record_frame():
    class Robot:
        ON_MOTION_IMAGES = ("head.png", "wrist.png")

        def _take_show_requests(self):
            return []

        def artifact(self, name, *, step=-1):
            return f"{step}:{name}".encode()

    toolkit = object.__new__(ArmToolkit)
    toolkit.images = "on-primitive"
    toolkit.robo = Robot()
    toolkit._displayed = []
    records = [
        SimpleNamespace(stateful=True, summary={"step": 2}),
        SimpleNamespace(stateful=False, summary={"step": 3}),
        SimpleNamespace(stateful=True, summary={"step": 5}),
    ]

    result = toolkit._attach_images({}, True, {}, records)

    assert result.images == [
        b"2:head.png",
        b"2:wrist.png",
        b"5:head.png",
        b"5:wrist.png",
    ]
    assert result.result["images"] == ["head.png", "wrist.png", "head.png", "wrist.png"]


def test_initial_images_remain_in_later_provider_requests(tmp_path):
    image = tmp_path / "initial.png"
    image.write_bytes(b"image-bytes")
    requests = []
    replies = [
        {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_tool",
                                "function": {
                                    "name": "show_image",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    },
                }
            ]
        },
        {"choices": [{"finish_reason": "stop", "message": {"content": "done"}}]},
    ]

    def transport(_url, body, _timeout):
        requests.append(deepcopy(body))
        if len(requests) == 1:
            return 500, {"error": "temporary failure"}
        return 200, replies.pop(0)

    toolkit = SimpleNamespace(
        get_tools_spec=lambda: [{"name": "show_image", "description": "", "input_schema": {}}],
        execute_tool=lambda _name, _arguments: ArmResult({"ok": True}),
        turn_budget_exhausted=False,
        finish=None,
        turns=[],
        robo=SimpleNamespace(_reported_success=lambda: False),
    )
    run_openai_agent(
        "scene",
        [image],
        toolkit,
        model="test",
        base_url="http://localhost/v1",
        api_key=None,
        max_turns=4,
        budget_s=10,
        out_dir=tmp_path / "run",
        transport=transport,
        retries=1,
        nudges=0,
        sleep=lambda _seconds: None,
    )

    assert len(requests) == 3
    assert any(
        part.get("type") == "image_url"
        for message in requests[0]["messages"]
        for part in (message.get("content") or [])
        if isinstance(part, dict)
    )
    assert any(
        part.get("type") == "image_url"
        for message in requests[1]["messages"]
        for part in (message.get("content") or [])
        if isinstance(part, dict)
    )
    assert all(tool["function"]["name"] != "manage_images" for tool in requests[0]["tools"])
    manifests = [
        json.loads(line)
        for line in (tmp_path / "run" / "request_log" / "requests.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [(entry["request"], entry["attempt"]) for entry in manifests] == [
        (1, 1), (1, 2), (2, 1)
    ]
    assert manifests[0]["messages"][0]["images"][0]["image_ref"].endswith("001_initial.png")
    assert manifests[1]["messages"] == manifests[0]["messages"]
    assert manifests[2]["messages"][0]["images"][0]["image_ref"].endswith("001_initial.png")

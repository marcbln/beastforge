"""Clip inventory, timing, and event checks (FR-022/023/025, data-model §8)."""

from __future__ import annotations

from beastforge.anim.registry import check_clip_params
from beastforge.model.findings import CORE_CLIPS, ValidationFinding
from beastforge.model.recipe import Clip, Recipe
from beastforge.validation.common import check_identifier, duplicates, finding


def _duration(clip: Clip) -> float | None:
    if clip.duration is not None and clip.ticks is not None:
        return None
    if clip.ticks is not None:
        return clip.ticks / 60.0
    if clip.duration is not None:
        return float(clip.duration)
    return None


def check_clips(
    recipe: Recipe, *, recipe_label: str, max_ticks: int = 600
) -> list[ValidationFinding]:
    """Check reserved clips, durations, generator parameters, and events."""
    findings: list[ValidationFinding] = []
    names = [clip.name for clip in recipe.clips]
    requires_core = recipe.meta.category != "other" and len(recipe.clips) > 0
    if requires_core:
        for core in CORE_CLIPS:
            if core not in names:
                findings.append(
                    finding(
                        "clip-missing-core",
                        f"Required core clip {core!r} is missing.",
                        recipe=recipe_label,
                        path="clips",
                        expected=f"reserved clips: {', '.join(CORE_CLIPS)}",
                        actual=names,
                        remedy=f"Add a clip named {core!r} using a documented generator.",
                    )
                )
    for duplicate in duplicates(names):
        findings.append(
            finding(
                "clip-duplicate",
                f"Clip name {duplicate!r} is declared more than once.",
                recipe=recipe_label,
                path=f"clips[{duplicate}]",
                expected="unique clip names",
                actual=duplicate,
                remedy="Rename one of the duplicate clips.",
            )
        )

    for clip in recipe.clips:
        path = f"clips[{clip.name}]"
        if clip.name == "baseline":
            findings.append(
                finding(
                    "clip-duplicate",
                    "The clip name 'baseline' is reserved for the synthesized "
                    "automatic-motion clip.",
                    recipe=recipe_label,
                    path=path,
                    expected="an authored clip name other than baseline",
                    actual=clip.name,
                    remedy="Rename the authored clip; remove automatic motion to drop baseline.",
                )
            )
        identifier = check_identifier(clip.name, recipe=recipe_label, path=path)
        if identifier is not None:
            findings.append(identifier)
        if clip.duration is not None and clip.ticks is not None:
            findings.append(
                finding(
                    "clip-param-invalid",
                    f"Clip {clip.name!r} declares both duration and ticks.",
                    recipe=recipe_label,
                    path=path,
                    expected="exactly one of duration or ticks",
                    actual="both",
                    remedy="Remove either duration or ticks.",
                )
            )
            duration = None
        elif clip.ticks is not None:
            if clip.ticks <= 0:
                findings.append(
                    finding(
                        "clip-nonpositive-duration",
                        f"Clip {clip.name!r} has non-positive ticks ({clip.ticks}).",
                        recipe=recipe_label,
                        path=f"{path}.ticks",
                        expected="> 0",
                        actual=clip.ticks,
                        remedy="Use a positive integer tick count.",
                    )
                )
            if clip.ticks > max_ticks:
                findings.append(
                    finding(
                        "clip-duration-over-budget",
                        f"Clip {clip.name!r} uses {clip.ticks} ticks, over the "
                        f"{max_ticks}-tick budget.",
                        recipe=recipe_label,
                        path=f"{path}.ticks",
                        expected=f"<= {max_ticks}",
                        actual=clip.ticks,
                        remedy="Shorten the clip or raise budgets.max_clip_ticks.",
                    )
                )
            duration = clip.ticks / 60.0
        elif clip.duration is not None:
            duration = float(clip.duration)
            if duration <= 0.0:
                findings.append(
                    finding(
                        "clip-nonpositive-duration",
                        f"Clip {clip.name!r} has non-positive duration ({duration}).",
                        recipe=recipe_label,
                        path=f"{path}.duration",
                        expected="> 0",
                        actual=duration,
                        remedy="Use a positive duration in seconds or an integer tick count.",
                    )
                )
            if duration > max_ticks / 60.0:
                findings.append(
                    finding(
                        "clip-duration-over-budget",
                        f"Clip {clip.name!r} lasts {duration}s, over the {max_ticks}-tick budget.",
                        recipe=recipe_label,
                        path=f"{path}.duration",
                        expected=f"<= {max_ticks / 60.0:g}s",
                        actual=duration,
                        remedy="Shorten the clip or raise budgets.max_clip_ticks.",
                    )
                )
        else:
            duration = None
            findings.append(
                finding(
                    "clip-param-invalid",
                    f"Clip {clip.name!r} declares neither duration nor ticks.",
                    recipe=recipe_label,
                    path=path,
                    expected="duration or ticks",
                    actual=None,
                    remedy="Add a positive duration in seconds or an integer tick count.",
                )
            )

        findings.extend(check_clip_params(clip, recipe_label=recipe_label))

        event_names: list[str] = []
        for event_index, event in enumerate(clip.events):
            event_path = f"{path}.events[{event_index}]"
            event_names.append(event.name)
            if event.time is not None and event.ticks is not None:
                findings.append(
                    finding(
                        "clip-param-invalid",
                        f"Event {event.name!r} in clip {clip.name!r} declares both time and ticks.",
                        recipe=recipe_label,
                        path=event_path,
                        expected="exactly one of time or ticks",
                        actual="both",
                        remedy="Remove either time or ticks.",
                    )
                )
                time = None
            elif event.ticks is not None:
                time = event.ticks / 60.0
            elif event.time is not None:
                time = float(event.time)
            else:
                time = None
                findings.append(
                    finding(
                        "clip-param-invalid",
                        f"Event {event.name!r} in clip {clip.name!r} has no time.",
                        recipe=recipe_label,
                        path=event_path,
                        expected="time or ticks",
                        actual=None,
                        remedy="Add a time in seconds or an integer tick count.",
                    )
                )
            if time is not None and time < 0.0:
                findings.append(
                    finding(
                        "clip-event-negative-time",
                        f"Event {event.name!r} in clip {clip.name!r} has a negative time.",
                        recipe=recipe_label,
                        path=event_path,
                        expected="0 <= time < duration",
                        actual=time,
                        remedy="Move the event to a non-negative time inside the clip.",
                    )
                )
            if time is not None and duration is not None and time >= duration:
                findings.append(
                    finding(
                        "clip-event-out-of-range",
                        f"Event {event.name!r} in clip {clip.name!r} is at or past "
                        "the clip duration.",
                        recipe=recipe_label,
                        path=event_path,
                        expected=f"0 <= time < {duration}",
                        actual=time,
                        remedy="Move the event earlier or lengthen the clip.",
                    )
                )
        for duplicate in duplicates(event_names):
            findings.append(
                finding(
                    "clip-event-duplicate",
                    f"Event name {duplicate!r} appears more than once in clip {clip.name!r}.",
                    recipe=recipe_label,
                    path=f"{path}.events",
                    expected="unique event names per clip",
                    actual=duplicate,
                    remedy="Rename one of the duplicate events.",
                )
            )
        if clip.name == "attack" and "impact" not in event_names:
            findings.append(
                finding(
                    "clip-missing-core",
                    "The attack clip must declare an 'impact' event.",
                    recipe=recipe_label,
                    path=f"{path}.events",
                    expected="an event named impact",
                    actual=event_names,
                    remedy="Add events: [{name: impact, time: <seconds>}] to the attack clip.",
                )
            )
    return findings

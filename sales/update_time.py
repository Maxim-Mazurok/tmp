"""Parse time-log.md and generate time.md with per-zone and global timing stats."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from constants import SALES_DIR
from markdown import format_markdown_table

TIME_LOG_PATH = SALES_DIR / "time-log.md"
TIME_MD_PATH = SALES_DIR / "time.md"

DATE_FORMAT = "%d %b %Y @ %I:%M:%S%p"


@dataclass
class Session:
    zone: str
    rod_level: int
    start: datetime
    finish: datetime
    fish_before: int
    fish_after: int
    electronics_before: int | None = None
    electronics_after: int | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.finish - self.start).total_seconds()

    @property
    def fish_caught(self) -> int:
        return self.fish_after - self.fish_before

    @property
    def electronics_gained(self) -> int:
        if self.electronics_before is None or self.electronics_after is None:
            return 0
        return self.electronics_after - self.electronics_before

    @property
    def seconds_per_fish(self) -> float:
        if self.fish_caught == 0:
            return 0.0
        return self.duration_seconds / self.fish_caught

    @property
    def seconds_per_electronic(self) -> float:
        if self.electronics_gained == 0:
            return 0.0
        return self.duration_seconds / self.electronics_gained


def parse_time_log(path: Path) -> list[Session]:
    """Parse time-log.md into a list of Session objects."""
    text = path.read_text(encoding="utf-8")
    sessions: list[Session] = []
    current_zone = ""
    pending: dict[str, object] = {}

    def flush() -> None:
        if "fish_after" in pending:
            sessions.append(Session(
                zone=current_zone,
                rod_level=pending["rod_level"],  # type: ignore[arg-type]
                start=pending["start"],  # type: ignore[arg-type]
                finish=pending["finish"],  # type: ignore[arg-type]
                fish_before=pending["fish_before"],  # type: ignore[arg-type]
                fish_after=pending["fish_after"],  # type: ignore[arg-type]
                electronics_before=pending.get("electronics_before"),  # type: ignore[arg-type]
                electronics_after=pending.get("electronics_after"),  # type: ignore[arg-type]
            ))

    for line in text.splitlines():
        line = line.strip()

        zone_match = re.match(r"^#\s+(.+)$", line)
        if zone_match:
            flush()
            pending = {}
            current_zone = zone_match.group(1).strip()
            continue

        if line == "---":
            flush()
            pending = {}
            continue

        if line.startswith("Rod Level:"):
            flush()
            pending = {}
            pending["rod_level"] = int(line.split(":")[1].strip())
            continue

        if line.startswith("Start:"):
            pending["start"] = datetime.strptime(line.split(":", 1)[1].strip(), DATE_FORMAT)
            continue

        if line.startswith("Finish:"):
            pending["finish"] = datetime.strptime(line.split(":", 1)[1].strip(), DATE_FORMAT)
            continue

        if line.startswith("Fish before:"):
            pending["fish_before"] = int(line.split(":")[1].strip())
            continue

        if line.startswith("Electronics before:"):
            pending["electronics_before"] = int(line.split(":")[1].strip())
            continue

        if line.startswith("Fish after:"):
            pending["fish_after"] = int(line.split(":")[1].strip())
            continue

        if line.startswith("Electronics after:"):
            pending["electronics_after"] = int(line.split(":")[1].strip())
            continue

    flush()
    return sessions


def format_duration(seconds: float) -> str:
    """Format seconds as Xm Ys."""
    minutes = int(seconds) // 60
    remaining_seconds = int(seconds) % 60
    return f"{minutes}m {remaining_seconds}s"


def build_zone_log_section(zone: str, sessions: list[Session]) -> str:
    """Build a per-zone log table with cumulative s/fish progression."""
    rows: list[tuple[str, ...]] = []
    for session in sessions:
        rows.append((
            session.finish.strftime("%d %b %Y %I:%M%p"),
            str(session.rod_level),
            str(session.fish_caught),
            format_duration(session.duration_seconds),
            f"{session.seconds_per_fish:.1f}s" if session.fish_caught else "-",
        ))

    table = format_markdown_table(
        headers=("Finished", "Rod", "Fish", "Duration", "s/fish"),
        rows=rows,
        right_aligned_columns={1, 2, 3, 4},
    )
    return f"### {zone}\n\n{table}"


def build_zone_average_section(
    zone: str,
    sessions: list[Session],
) -> list[tuple[str, ...]]:
    """Build rows for the per-zone per-rod-level average table."""
    by_rod_level: dict[int, list[Session]] = {}
    for session in sessions:
        by_rod_level.setdefault(session.rod_level, []).append(session)

    rows: list[tuple[str, ...]] = []
    for rod_level in sorted(by_rod_level):
        level_sessions = by_rod_level[rod_level]
        total_fish = sum(session.fish_caught for session in level_sessions)
        total_seconds = sum(session.duration_seconds for session in level_sessions)
        average_seconds_per_fish = total_seconds / total_fish if total_fish else 0
        rows.append((
            zone,
            str(rod_level),
            str(len(level_sessions)),
            str(total_fish),
            f"{average_seconds_per_fish:.1f}s" if total_fish else "-",
        ))
    return rows


def build_electronics_section(sessions: list[Session]) -> str:
    """Build global electronics log and average."""
    sessions = [s for s in sessions if s.electronics_before is not None]
    log_rows: list[tuple[str, ...]] = []
    for session in sessions:
        electronics_gained = session.electronics_gained
        log_rows.append((
            session.zone,
            session.finish.strftime("%d %b %Y %I:%M%p"),
            str(electronics_gained),
            format_duration(session.duration_seconds),
            f"{session.seconds_per_electronic:.1f}s" if electronics_gained else "-",
        ))

    log_table = format_markdown_table(
        headers=("Zone", "Finished", "Electronics", "Duration", "s/electronic"),
        rows=log_rows,
        right_aligned_columns={2, 3, 4},
    )

    total_electronics = sum(session.electronics_gained for session in sessions)
    total_seconds = sum(session.duration_seconds for session in sessions)
    global_average = total_seconds / total_electronics if total_electronics else 0

    summary = (
        f"**Global average:** {global_average:.1f}s/electronic"
        f" ({total_electronics} electronics in {format_duration(total_seconds)})"
    )

    return f"## Electronics\n\n{log_table}\n\n{summary}"


def build_time_md(sessions: list[Session]) -> str:
    """Build the full time.md content."""
    sections: list[str] = ["# Fishing Time Stats"]

    # Group by zone preserving first-seen order
    zone_order: list[str] = []
    by_zone: dict[str, list[Session]] = {}
    for session in sessions:
        if session.zone not in by_zone:
            zone_order.append(session.zone)
        by_zone.setdefault(session.zone, []).append(session)

    # Per-zone logs
    sections.append("## Session Log")
    for zone in zone_order:
        sections.append(build_zone_log_section(zone, by_zone[zone]))

    # Average s/fish per zone per rod level
    sections.append("## Average s/fish by Zone and Rod Level")
    average_rows: list[tuple[str, ...]] = []
    for zone in zone_order:
        average_rows.extend(build_zone_average_section(zone, by_zone[zone]))
    average_table = format_markdown_table(
        headers=("Zone", "Rod", "Sessions", "Fish", "Avg s/fish"),
        rows=average_rows,
        right_aligned_columns={1, 2, 3, 4},
    )
    sections.append(average_table)

    # Electronics (global)
    electronics_sessions = [s for s in sessions if s.electronics_before is not None]
    if electronics_sessions:
        sections.append(build_electronics_section(sessions))

    return "\n\n".join(sections) + "\n"


def main() -> None:
    if not TIME_LOG_PATH.exists():
        print(f"  {TIME_LOG_PATH.name} not found, skipping")
        return

    sessions = parse_time_log(TIME_LOG_PATH)
    if not sessions:
        print("  no sessions found in time-log.md")
        return

    content = build_time_md(sessions)
    TIME_MD_PATH.write_text(content, encoding="utf-8")
    print(f"  time.md updated ({len(sessions)} sessions)")


if __name__ == "__main__":
    main()

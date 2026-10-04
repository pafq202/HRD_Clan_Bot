"""구인 공고 영구 기록 관리 모듈

`pending_recruitment.json`과 달리, 이 모듈이 다루는 `recruitment_history.json`은
`/삭제`로 공고를 지워도 항목 자체가 삭제되지 않습니다.
삭제 시에는 deleted_at / deleted_by 필드만 채워서 "삭제된 기록"으로 영구 보존합니다.

작성자/삭제자의 닉네임과, 어느 디스코드 서버(길드)에서 작성되었는지도 함께 기록합니다.
"""
import os
import json
from datetime import datetime, timezone
from typing import Optional

from utils.directory import directory


def _get_history_path() -> str:
    """영구 보관용 구인 기록 파일 경로 반환 (삭제되지 않는 기록)"""
    data_dir = os.path.join(directory, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "recruitment_history.json")


def load_history_data() -> dict:
    """영구 보관용 구인 기록 로드 (삭제와 무관하게 계속 남는 기록)"""
    history_file = _get_history_path()
    if not os.path.exists(history_file):
        return {}

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 기록 로드 오류: {e}")
        return {}


def save_history_data(data: dict):
    """영구 보관용 구인 기록 저장"""
    history_file = _get_history_path()

    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ 기록 저장 오류: {e}")


def record_recruitment_created(message_id, data: dict):
    """구인 공고 생성/수정 시점의 정보를 영구 기록 파일에 반영 (절대 삭제되지 않음)

    data에는 다음 키를 포함할 수 있습니다:
        author_id, author_name, game_time, game_type, max_players,
        voice_channel, created_at, guild_id, guild_name
    """
    history = load_history_data()
    existing = history.get(str(message_id), {})
    history[str(message_id)] = {
        "author_id": data.get("author_id"),
        "author_name": data.get("author_name"),
        "game_time": data.get("game_time"),
        "game_type": data.get("game_type"),
        "max_players": data.get("max_players"),
        "voice_channel": data.get("voice_channel"),
        "created_at": data.get("created_at"),
        "guild_id": data.get("guild_id", existing.get("guild_id")),
        "guild_name": data.get("guild_name", existing.get("guild_name")),
        "deleted_at": existing.get("deleted_at"),
        "deleted_by": existing.get("deleted_by"),
        "deleted_by_name": existing.get("deleted_by_name"),
    }
    save_history_data(history)


def record_recruitment_deleted(
    message_id,
    deleted_by: Optional[int],
    deleted_by_name: Optional[str] = None,
):
    """구인 공고 삭제 시점 정보를 영구 기록에 추가 (기록 자체는 삭제하지 않고 상태만 갱신)"""
    history = load_history_data()
    entry = history.get(str(message_id))
    if entry is None:
        # 기록이 없던 경우에도 최소 정보로 남겨 둔다
        entry = {
            "author_id": None,
            "author_name": None,
            "game_time": None,
            "game_type": None,
            "max_players": None,
            "voice_channel": None,
            "created_at": None,
            "guild_id": None,
            "guild_name": None,
        }
    entry["deleted_at"] = datetime.now(timezone.utc).isoformat()
    entry["deleted_by"] = deleted_by
    entry["deleted_by_name"] = deleted_by_name
    history[str(message_id)] = entry
    save_history_data(history)

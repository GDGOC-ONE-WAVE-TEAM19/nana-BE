"""
Todo Preset Service

프리셋 JSON 파일을 로드하고 TagGroup, Tag, Todo를 일괄 생성하는 서비스입니다.
"""
import json
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from sqlmodel import Session

from app.core.auth import CurrentUser
from app.domain.tag.schema.dto import TagGroupCreate, TagCreate
from app.domain.tag.service import TagService
from app.domain.todo.schema.dto import TodoCreate
from app.domain.todo.schema.preset import (
    Preset,
    PresetInfo,
    PresetInitializeResult,
    PresetTodo,
)
from app.domain.todo.service import TodoService


# 프리셋 파일 저장 경로
PRESETS_DIR = Path(__file__).parent.parent.parent / "presets"


class PresetNotFoundError(Exception):
    """프리셋을 찾을 수 없음"""

    def __init__(self, preset_name: str):
        self.preset_name = preset_name
        super().__init__(f"프리셋을 찾을 수 없습니다: {preset_name}")


class PresetService:
    """
    프리셋 서비스
    
    프리셋 JSON 파일을 로드하고 사용자의 TagGroup, Tag, Todo를 일괄 생성합니다.
    """

    def __init__(self, session: Session, current_user: CurrentUser):
        self.session = session
        self.current_user = current_user
        self.tag_service = TagService(session, current_user)
        self.todo_service = TodoService(session, current_user)

    @staticmethod
    def _get_preset_path(preset_name: str) -> Path:
        """프리셋 파일 경로 반환"""
        return PRESETS_DIR / f"{preset_name}.json"

    @staticmethod
    def _load_preset_file(preset_path: Path) -> Preset:
        """프리셋 JSON 파일 로드 및 파싱"""
        with open(preset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Preset.model_validate(data)

    @staticmethod
    def _count_todos_recursive(todos: List[PresetTodo]) -> int:
        """Todo 총 개수 계산 (재귀)"""
        count = len(todos)
        for todo in todos:
            if todo.children:
                count += PresetService._count_todos_recursive(todo.children)
        return count

    def list_presets(self) -> List[PresetInfo]:
        """
        사용 가능한 프리셋 목록 조회
        
        :return: 프리셋 정보 리스트
        """
        presets = []

        if not PRESETS_DIR.exists():
            return presets

        for preset_file in PRESETS_DIR.glob("*.json"):
            try:
                preset = self._load_preset_file(preset_file)
                todo_count = self._count_todos_recursive(preset.todos)
                presets.append(PresetInfo(
                    name=preset.name,
                    description=preset.description,
                    tag_count=len(preset.tags),
                    todo_count=todo_count,
                ))
            except (json.JSONDecodeError, ValueError):
                # 잘못된 프리셋 파일은 건너뜀
                continue

        return presets

    def get_preset(self, preset_name: str) -> Preset:
        """
        프리셋 상세 조회
        
        :param preset_name: 프리셋 이름 (파일명에서 .json 제외)
        :return: 프리셋 데이터
        :raises PresetNotFoundError: 프리셋을 찾을 수 없는 경우
        """
        preset_path = self._get_preset_path(preset_name)

        if not preset_path.exists():
            raise PresetNotFoundError(preset_name)

        return self._load_preset_file(preset_path)

    def initialize_from_preset(self, preset_name: str) -> PresetInitializeResult:
        """
        프리셋으로 TagGroup, Tag, Todo 초기화
        
        1. TagGroup 생성
        2. Tag들 생성
        3. Todo들 생성 (계층 구조 지원)
        
        :param preset_name: 프리셋 이름
        :return: 초기화 결과
        :raises PresetNotFoundError: 프리셋을 찾을 수 없는 경우
        """
        preset = self.get_preset(preset_name)

        # 1. TagGroup 생성
        tag_group = self.tag_service.create_tag_group(TagGroupCreate(
            name=preset.tag_group.name,
            color=preset.tag_group.color,
            description=preset.tag_group.description,
            goal_ratios=preset.tag_group.goal_ratios,
            is_todo_group=preset.tag_group.is_todo_group,
        ))

        # 2. Tag들 생성 (이름 → ID 매핑 저장)
        tag_name_to_id: dict[str, UUID] = {}
        for preset_tag in preset.tags:
            tag = self.tag_service.create_tag(TagCreate(
                name=preset_tag.name,
                color=preset_tag.color,
                description=preset_tag.description,
                group_id=tag_group.id,
            ))
            tag_name_to_id[preset_tag.name] = tag.id

        # 3. Todo들 생성 (재귀적으로 계층 구조 처리)
        todos_created = self._create_todos_recursive(
            preset_todos=preset.todos,
            tag_group_id=tag_group.id,
            tag_name_to_id=tag_name_to_id,
            parent_id=None,
        )

        return PresetInitializeResult(
            preset_name=preset_name,
            tag_group_id=str(tag_group.id),
            tags_created=len(preset.tags),
            todos_created=todos_created,
        )

    def _create_todos_recursive(
            self,
            preset_todos: List[PresetTodo],
            tag_group_id: UUID,
            tag_name_to_id: dict[str, UUID],
            parent_id: Optional[UUID],
    ) -> int:
        """
        Todo들을 재귀적으로 생성
        
        :param preset_todos: 생성할 프리셋 Todo 리스트
        :param tag_group_id: 태그 그룹 ID
        :param tag_name_to_id: 태그 이름 → ID 매핑
        :param parent_id: 부모 Todo ID (루트면 None)
        :return: 생성된 Todo 총 개수
        """
        created_count = 0

        for preset_todo in preset_todos:
            # 태그 이름을 ID로 변환
            tag_ids: Optional[List[UUID]] = None
            if preset_todo.tag_names:
                tag_ids = [
                    tag_name_to_id[name]
                    for name in preset_todo.tag_names
                    if name in tag_name_to_id
                ]

            # Todo 생성
            todo = self.todo_service.create_todo(TodoCreate(
                title=preset_todo.title,
                description=preset_todo.description,
                tag_group_id=tag_group_id,
                tag_ids=tag_ids,
                parent_id=parent_id,
            ))
            created_count += 1

            # 자식 Todo들 재귀 생성
            if preset_todo.children:
                created_count += self._create_todos_recursive(
                    preset_todos=preset_todo.children,
                    tag_group_id=tag_group_id,
                    tag_name_to_id=tag_name_to_id,
                    parent_id=todo.id,
                )

        return created_count

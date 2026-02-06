"""
Todo Preset Schema

프리셋 JSON 파일의 구조를 정의합니다.
프리셋은 TagGroup, Tag, Todo를 일괄 생성하기 위한 템플릿입니다.
"""
from typing import Optional, List, Dict

from pydantic import field_validator

from app.core.base_model import CustomModel
from app.utils.validators import validate_color


class PresetTag(CustomModel):
    """프리셋 태그 정의"""
    name: str
    color: str
    description: Optional[str] = None

    @field_validator("color")
    @classmethod
    def validate_color_field(cls, v: str) -> str:
        """색상 코드 검증 (HEX 형식)"""
        return validate_color(v)


class PresetTagGroup(CustomModel):
    """프리셋 태그 그룹 정의"""
    name: str
    color: str
    description: Optional[str] = None
    goal_ratios: Optional[Dict[str, float]] = None
    is_todo_group: bool = True

    @field_validator("color")
    @classmethod
    def validate_color_field(cls, v: str) -> str:
        """색상 코드 검증 (HEX 형식)"""
        return validate_color(v)


class PresetTodo(CustomModel):
    """
    프리셋 Todo 정의 (계층 구조 지원)
    
    tag_names: 이 Todo에 연결할 태그 이름 리스트
    children: 자식 Todo 리스트 (재귀적 구조)
    """
    title: str
    description: Optional[str] = None
    tag_names: Optional[List[str]] = None
    children: Optional[List["PresetTodo"]] = None


# Forward reference 해결
PresetTodo.model_rebuild()


class Preset(CustomModel):
    """
    프리셋 전체 정의
    
    프리셋 JSON 파일의 루트 구조입니다.
    하나의 TagGroup과 그에 속한 Tag들, Todo들을 정의합니다.
    """
    name: str
    description: Optional[str] = None
    tag_group: PresetTagGroup
    tags: List[PresetTag] = []
    todos: List[PresetTodo] = []


class PresetInfo(CustomModel):
    """프리셋 목록 조회용 간략 정보"""
    name: str
    description: Optional[str] = None
    tag_count: int
    todo_count: int


class PresetInitializeResult(CustomModel):
    """프리셋 초기화 결과"""
    preset_name: str
    tag_group_id: str
    tags_created: int
    todos_created: int

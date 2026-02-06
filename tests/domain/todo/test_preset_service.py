"""
Preset Service Unit Tests

프리셋 서비스의 단위 테스트
"""
import pytest

from app.domain.todo.preset_service import PresetService, PresetNotFoundError, PRESETS_DIR
from app.domain.todo.schema.preset import Preset, PresetInfo


class TestPresetService:
    """프리셋 서비스 테스트"""

    def test_list_presets(self, test_session, test_user):
        """프리셋 목록 조회 테스트"""
        service = PresetService(test_session, test_user)
        presets = service.list_presets()

        # 예시 프리셋이 존재해야 함
        assert isinstance(presets, list)
        assert len(presets) >= 2  # study, project

        # PresetInfo 타입 확인
        for preset in presets:
            assert isinstance(preset, PresetInfo)
            assert preset.name
            assert preset.tag_count >= 0
            assert preset.todo_count >= 0

    def test_list_presets_includes_study(self, test_session, test_user):
        """프리셋 목록에 study 프리셋이 포함되는지 확인"""
        service = PresetService(test_session, test_user)
        presets = service.list_presets()

        preset_names = [p.name for p in presets]
        assert "study" in preset_names

    def test_list_presets_includes_project(self, test_session, test_user):
        """프리셋 목록에 project 프리셋이 포함되는지 확인"""
        service = PresetService(test_session, test_user)
        presets = service.list_presets()

        preset_names = [p.name for p in presets]
        assert "project" in preset_names

    def test_get_preset_success(self, test_session, test_user):
        """존재하는 프리셋 조회 테스트"""
        service = PresetService(test_session, test_user)
        preset = service.get_preset("study")

        assert isinstance(preset, Preset)
        assert preset.name == "study"
        assert preset.tag_group is not None
        assert len(preset.tags) >= 1
        assert len(preset.todos) >= 1

    def test_get_preset_not_found(self, test_session, test_user):
        """존재하지 않는 프리셋 조회 시 예외 발생 테스트"""
        service = PresetService(test_session, test_user)

        with pytest.raises(PresetNotFoundError) as exc_info:
            service.get_preset("non_existent_preset")

        assert "non_existent_preset" in str(exc_info.value)

    def test_initialize_from_preset_success(self, test_session, test_user):
        """프리셋으로 초기화 성공 테스트"""
        service = PresetService(test_session, test_user)
        result = service.initialize_from_preset("study")

        assert result.preset_name == "study"
        assert result.tag_group_id is not None
        assert result.tags_created >= 1
        assert result.todos_created >= 1

    def test_initialize_from_preset_creates_tag_group(self, test_session, test_user):
        """프리셋 초기화 시 태그 그룹이 생성되는지 확인"""
        from app.domain.tag.service import TagService

        preset_service = PresetService(test_session, test_user)
        result = preset_service.initialize_from_preset("study")

        tag_service = TagService(test_session, test_user)
        groups = tag_service.get_all_tag_groups()

        group_ids = [str(g.id) for g in groups]
        assert result.tag_group_id in group_ids

    def test_initialize_from_preset_creates_tags(self, test_session, test_user):
        """프리셋 초기화 시 태그들이 생성되는지 확인"""
        from uuid import UUID
        from app.domain.tag.service import TagService

        preset_service = PresetService(test_session, test_user)
        result = preset_service.initialize_from_preset("study")

        tag_service = TagService(test_session, test_user)
        tags = tag_service.get_tags_by_group(UUID(result.tag_group_id))

        assert len(tags) == result.tags_created

    def test_initialize_from_preset_creates_todos(self, test_session, test_user):
        """프리셋 초기화 시 Todo들이 생성되는지 확인"""
        from uuid import UUID
        from app.domain.todo.service import TodoService

        preset_service = PresetService(test_session, test_user)
        result = preset_service.initialize_from_preset("study")

        todo_service = TodoService(test_session, test_user)
        todos = todo_service.get_all_todos(group_ids=[UUID(result.tag_group_id)])

        assert len(todos.todos) == result.todos_created

    def test_initialize_from_preset_creates_hierarchy(self, test_session, test_user):
        """프리셋 초기화 시 Todo 계층 구조가 올바르게 생성되는지 확인"""
        from uuid import UUID
        from app.domain.todo.service import TodoService

        preset_service = PresetService(test_session, test_user)
        result = preset_service.initialize_from_preset("study")

        todo_service = TodoService(test_session, test_user)
        todos = todo_service.get_all_todos(group_ids=[UUID(result.tag_group_id)])

        # 부모 Todo 확인 (parent_id가 None)
        root_todos = [t for t in todos.todos if t.parent_id is None]
        assert len(root_todos) >= 1

        # 자식 Todo 확인 (parent_id가 있음)
        child_todos = [t for t in todos.todos if t.parent_id is not None]
        assert len(child_todos) >= 1

    def test_initialize_from_preset_assigns_tags(self, test_session, test_user):
        """프리셋 초기화 시 Todo에 태그가 올바르게 할당되는지 확인"""
        from uuid import UUID
        from app.domain.todo.service import TodoService

        preset_service = PresetService(test_session, test_user)
        result = preset_service.initialize_from_preset("study")

        todo_service = TodoService(test_session, test_user)
        todos = todo_service.get_all_todos(group_ids=[UUID(result.tag_group_id)])

        # 태그가 있는 Todo가 존재해야 함
        todos_with_tags = [t for t in todos.todos if len(t.tags) > 0]
        assert len(todos_with_tags) >= 1

    def test_initialize_from_preset_not_found(self, test_session, test_user):
        """존재하지 않는 프리셋으로 초기화 시 예외 발생 테스트"""
        service = PresetService(test_session, test_user)

        with pytest.raises(PresetNotFoundError):
            service.initialize_from_preset("non_existent_preset")

    def test_count_todos_recursive(self):
        """재귀적 Todo 카운트 테스트"""
        from app.domain.todo.schema.preset import PresetTodo

        # 계층 구조 생성
        todos = [
            PresetTodo(title="Parent 1", children=[
                PresetTodo(title="Child 1.1"),
                PresetTodo(title="Child 1.2", children=[
                    PresetTodo(title="Grandchild 1.2.1"),
                ]),
            ]),
            PresetTodo(title="Parent 2"),
        ]

        count = PresetService._count_todos_recursive(todos)
        # Parent 1, Child 1.1, Child 1.2, Grandchild 1.2.1, Parent 2 = 5
        assert count == 5

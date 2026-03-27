"""AutomationDriver 接口测试"""
import pytest
from core.interfaces.automation import AutomationDriver, ElementInfo


class TestElementInfo:
    def test_create_default(self):
        el = ElementInfo()
        assert el.text == ""
        assert el.bounds == (0, 0, 0, 0)
        assert el.clickable is False
        assert el.enabled is True

    def test_create_with_values(self):
        el = ElementInfo(
            text="搜索",
            resource_id="com.app:id/search",
            class_name="android.widget.Button",
            bounds=(100, 200, 300, 400),
            clickable=True,
        )
        assert el.text == "搜索"
        assert el.resource_id == "com.app:id/search"
        assert el.bounds == (100, 200, 300, 400)
        assert el.clickable is True

    def test_center_property(self):
        el = ElementInfo(bounds=(100, 200, 300, 400))
        assert el.center == (200, 300)

    def test_center_zero(self):
        el = ElementInfo(bounds=(0, 0, 0, 0))
        assert el.center == (0, 0)

    def test_serialization(self):
        el = ElementInfo(text="测试", bounds=(10, 20, 30, 40))
        data = el.model_dump()
        assert data["text"] == "测试"
        assert data["bounds"] == (10, 20, 30, 40)


class TestAutomationDriverABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            AutomationDriver()

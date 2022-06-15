from benchmarklib.models import Addon


def test_addons_enable_and_disable():
    # Test without args
    addon = Addon(name="bar")
    assert addon.enable == "bar"
    assert addon.disable == "bar"

    # Test with args
    addon = Addon(name="foo", enable_arg="1234", disable_arg="destroy-storage")
    assert addon.enable == "foo:1234"
    assert addon.disable == "foo:destroy-storage"

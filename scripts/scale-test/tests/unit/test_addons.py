from benchmarklib.models import Addon


def test_addons_enable_and_disable_args():
    addon = Addon(name="foo", enable_arg="1234", disable_arg="destroy-storage")

    assert addon.enable == "foo:1234"
    assert addon.disable == "foo:destroy-storage"

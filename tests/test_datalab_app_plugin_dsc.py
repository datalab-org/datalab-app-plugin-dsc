from datalab_app_plugin_dsc import __version__
from datalab_app_plugin_dsc.blocks import DSCDataBlock


def test_version():
    assert __version__


def test_example_data_block():
    block = DSCDataBlock
    assert block.version == __version__

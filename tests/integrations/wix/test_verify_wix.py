from unittest.mock import MagicMock

import pytest
from requests import exceptions as requests_exceptions

from briefcase.exceptions import BriefcaseCommandError, NetworkFailure
from briefcase.integrations.wix import verify_wix, WIX_DOWNLOAD_URL


@pytest.fixture
def mock_command(tmp_path):
    command = MagicMock()
    command.host_os = 'Windows'
    command.dot_briefcase_path = tmp_path / '.briefcase'

    return command


def test_non_windows_host(mock_command):
    "If the host OS isn't Windows, the validator fails"

    # Set the host OS to something not Windows
    mock_command.host_os = 'Other OS'

    with pytest.raises(BriefcaseCommandError, match="can only be created on Windows"):
        verify_wix(mock_command)


def test_valid_wix_envvar(mock_command, tmp_path):
    "If the WiX envvar points to a valid WiX install, the validator succeeds"
    # Mock the environment for a WiX install
    wix_path = tmp_path / 'wix'
    mock_command.os.environ.get.return_value = str(wix_path)

    # Mock the interesting parts of a WiX install
    (wix_path / 'bin').mkdir(parents=True)
    (wix_path / 'bin' / 'heat.exe').touch()
    (wix_path / 'bin' / 'light.exe').touch()
    (wix_path / 'bin' / 'candle.exe').touch()

    # Verify the install
    wix = verify_wix(mock_command)

    # The environment was queried.
    mock_command.os.environ.get.assert_called_with('WIX')

    # The returned paths are as expected
    assert str(wix.heat_exe) == str(tmp_path / 'wix' / 'bin' / 'heat.exe')
    assert str(wix.light_exe) == str(tmp_path / 'wix' / 'bin' / 'light.exe')
    assert str(wix.candle_exe) == str(tmp_path / 'wix' / 'bin' / 'candle.exe')


def test_invalid_wix_envvar(mock_command, tmp_path):
    "If the WiX envvar points to an invalid WiX install, the validator fails"
    # Mock the environment for a WiX install
    wix_path = tmp_path / 'wix'
    mock_command.os.environ.get.return_value = str(wix_path)

    # Don't create the actual install, and then attempt to validate
    with pytest.raises(BriefcaseCommandError, match="does not point to an install"):
        verify_wix(mock_command)


def test_existing_wix_install(mock_command, tmp_path):
    "If there's an existing WiX install, the validator succeeds"
    # Mock the environment as if there is not WiX variable
    mock_command.os.environ.get.return_value = None

    # Create a mock of a previously installed WiX version.
    wix_path = tmp_path / '.briefcase' / 'tools' / 'wix'
    wix_path.mkdir(parents=True)
    (wix_path / 'heat.exe').touch()
    (wix_path / 'light.exe').touch()
    (wix_path / 'candle.exe').touch()

    wix = verify_wix(mock_command)

    # The environment was queried.
    mock_command.os.environ.get.assert_called_with('WIX')

    # The returned paths are as expected
    assert wix.heat_exe == tmp_path / '.briefcase' / 'tools' / 'wix' / 'heat.exe'
    assert wix.light_exe == tmp_path / '.briefcase' / 'tools' / 'wix' / 'light.exe'
    assert wix.candle_exe == tmp_path / '.briefcase' / 'tools' / 'wix' / 'candle.exe'


def test_download_wix(mock_command, tmp_path):
    "If there's no existing WiX install, it is downloaded and unpacked"
    # Mock the environment as if there is not WiX variable
    mock_command.os.environ.get.return_value = None

    # Mock the download
    wix_path = tmp_path / '.briefcase' / 'tools' / 'wix'

    wix_zip_path = tmp_path / '.briefcase' / 'tools' / 'wix.zip'
    wix_zip = MagicMock()
    wix_zip.__str__.return_value = str(wix_zip_path)

    mock_command.download_url.return_value = wix_zip

    # Verify the install. This will trigger a download
    wix = verify_wix(mock_command)

    # The environment was queried.
    mock_command.os.environ.get.assert_called_with('WIX')

    # A download was initiated
    mock_command.download_url.assert_called_with(
        url=WIX_DOWNLOAD_URL,
        download_path=tmp_path / '.briefcase' / 'tools',
    )

    # The download was unpacked
    mock_command.shutil.unpack_archive.assert_called_with(
        str(wix_zip_path),
        extract_dir=str(wix_path)
    )

    # The zip file was removed
    wix_zip.unlink.assert_called_with()

    # The returned paths are as expected
    assert wix.heat_exe == tmp_path / '.briefcase' / 'tools' / 'wix' / 'heat.exe'
    assert wix.light_exe == tmp_path / '.briefcase' / 'tools' / 'wix' / 'light.exe'
    assert wix.candle_exe == tmp_path / '.briefcase' / 'tools' / 'wix' / 'candle.exe'


def test_download_fail(mock_command, tmp_path):
    "If the download doesn't complete, the validator fails"
    # Mock the environment as if there is not WiX variable
    mock_command.os.environ.get.return_value = None

    # Mock the download failure
    mock_command.download_url.side_effect = requests_exceptions.ConnectionError

    # Verify the install. This will trigger a download
    with pytest.raises(NetworkFailure):
        verify_wix(mock_command)

    # The environment was queried.
    mock_command.os.environ.get.assert_called_with('WIX')

    # A download was initiated
    mock_command.download_url.assert_called_with(
        url=WIX_DOWNLOAD_URL,
        download_path=tmp_path / '.briefcase' / 'tools',
    )

    # ... but the unpack didn't happen
    assert mock_command.shutil.unpack_archive.call_count == 0


def test_unpack_fail(mock_command, tmp_path):
    "If the download archive is corrupted, the validator fails"
    # Mock the environment as if there is not WiX variable
    mock_command.os.environ.get.return_value = None

    # Mock the download
    wix_path = tmp_path / '.briefcase' / 'tools' / 'wix'

    wix_zip_path = tmp_path / '.briefcase' / 'tools' / 'wix.zip'
    wix_zip = MagicMock()
    wix_zip.__str__.return_value = str(wix_zip_path)

    mock_command.download_url.return_value = wix_zip

    # Mock an unpack failure
    mock_command.shutil.unpack_archive.side_effect = EOFError

    # Verify the install. This will trigger a download,
    # but the unpack will fail
    with pytest.raises(BriefcaseCommandError, match="interrupted or corrupted"):
        verify_wix(mock_command)

    # The environment was queried.
    mock_command.os.environ.get.assert_called_with('WIX')

    # A download was initiated
    mock_command.download_url.assert_called_with(
        url=WIX_DOWNLOAD_URL,
        download_path=tmp_path / '.briefcase' / 'tools',
    )

    # The download was unpacked
    mock_command.shutil.unpack_archive.assert_called_with(
        str(wix_zip_path),
        extract_dir=str(wix_path)
    )

    # The zip file was not removed
    assert wix_zip.unlink.call_count == 0

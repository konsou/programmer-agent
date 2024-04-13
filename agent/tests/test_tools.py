import platform
from unittest import TestCase

from agent import consent
from agent import tools
from agent.tests.helpers import patch_decorator


class TestCommandLineWindows(TestCase):
    def setUp(self):
        if platform.system() != "Windows":
            self.skipTest(f"Skipping Windows tests on {platform.system()}")

        consent_patcher = patch_decorator(
            module_being_tested=tools,
            decorator_patch_location="agent.consent.ask_execution_consent",
        )
        consent_patcher.patch()
        self.addCleanup(consent_patcher.kill_patches)

    def test_run_command_line(self):
        result = tools.run_command_line("echo 'Hello World!'")
        self.assertEqual(result, "Hello World!\nProcess exited with code 0")
import unittest
from pathlib import Path
from unittest.mock import patch
from cases.registry import load
from backends.registry import generator,method

class Modules(unittest.TestCase):
    def test_case_is_separate_from_methods(self):
        case=load('srad4')
        self.assertEqual(case.option_count,4)
        self.assertFalse(hasattr(case,'merge'))
        self.assertFalse(hasattr(case,'baselines'))
        self.assertEqual(generator('darm').name,'darm-pair-generator')
    def test_method_flags_and_target_not_case_specific(self):
        with patch('vendor.engine.command') as command:
            for name in ['bf','darm']:
                method(name).transform(Path('/engine'),Path('/input.ll'),'another_kernel',Path('/out'))
                cmd=command.call_args.args[2]
                self.assertIn('-run-cfmelding-on-function=another_kernel',cmd)
                self.assertEqual('-run-branch-fusion-only' in cmd,name=='bf')
    def test_case_plugin(self):
        self.assertEqual(load('cases.srad.case:SRAD4').name,'srad4')
    def test_generic_session_has_no_case_names(self):
        import fusion.session
        source=Path(fusion.session.__file__).read_text()
        self.assertNotIn('srad',source.lower())

if __name__=='__main__':unittest.main()

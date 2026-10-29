import unittest,tempfile
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
    def test_pair_generator_defaults_to_minimal_cleanup(self):
        gen=generator('darm')
        gen.bindings=(Path('/unused'),'test',{},'');gen.case=object()
        with patch('vendor.engine.merge') as merge:
            gen.merge('test',{}, {},Path('/out'))
            self.assertEqual(merge.call_args.kwargs['cleanup_mode'],'minimal')
    def test_minimal_cleanup_has_no_o3(self):
        from vendor import engine as G
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);source=d/'input.ll'
            source.write_text('define void @f() {\nentry:\n  ret void\n}\n')
            with patch('vendor.engine.command') as command:
                G.cleanup(d,source,'f',mode='minimal')
                cmd=command.call_args.args[2]
                self.assertIn('-simplifycfg',cmd);self.assertIn('-verify',cmd)
                self.assertNotIn('-O3',cmd)
    def test_case_plugin(self):
        self.assertEqual(load('cases.srad.case:SRAD4').name,'srad4')
    def test_generic_session_has_no_case_names(self):
        import fusion.session
        source=Path(fusion.session.__file__).read_text()
        self.assertNotIn('srad',source.lower())

if __name__=='__main__':unittest.main()

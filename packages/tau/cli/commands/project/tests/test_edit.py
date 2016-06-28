# -*- coding: utf-8 -*-
#
# Copyright (c) 2016, ParaTools, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# (1) Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
# (2) Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
# (3) Neither the name of ParaTools, Inc. nor the names of its contributors may
#     be used to endorse or promote products derived from this software without
#     specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
"""Test functions.

Functions used for unit tests of edit.py.
"""


from tau import tests
from tau.cli.commands.project import edit
from tau.model.project import Project

class EditTest(tests.TestCase):
    """Tests for :any:`project.edit`."""

    def test_rename(self):
        self.reset_project_storage(project_name='proj1')
        argv = ['proj1', '--new-name', 'proj2']
        self.assertCommandReturnValue(0, edit.COMMAND, argv)
        proj_ctrl = Project.controller()
        self.assertIsNone(proj_ctrl.one({'name': 'proj1'}))
        self.assertIsNotNone(proj_ctrl.one({'name': 'proj2'}))
        self.exec_command(edit.COMMAND, ['proj2', '--new-name', 'proj1'])
    
    def test_set_tau_force_options(self):
        self.reset_project_storage(project_name='proj1')
        proj_ctrl = Project.controller()
        # Check that 'force-tau-options' is unset in the new project configuration
        proj1 = proj_ctrl.one({'name': 'proj1'})
        self.assertFalse('force-tau-options' in proj1)
        # Test --force-tau-options
        #tau_options = ['-optVerbose', '-optNoCompInst']
        #argv = ['proj1', '--force-tau-options'] + tau_options
        #self.assertCommandReturnValue(0, edit.COMMAND, argv)
        # Check that 'force-tau-options' is now a list containing the expected options in the project record
        #proj1 = proj_ctrl.one({'name': 'proj1'})
        #self.assertIsNotNone(proj1)
        #self.assertListEqual(proj1['force-tau-options'], tau_options)
        
    def test_wrongname(self):
        self.reset_project_storage(project_name='proj1')
        argv = ['proj2', '--new-name', 'proj3']
        _, _, stderr = self.exec_command(edit.COMMAND, argv)
        self.assertIn('project edit <project_name> [arguments]', stderr)
        self.assertIn('project edit: error', stderr)
        self.assertIn('is not a project name.', stderr)
        
    def test_wrongarg(self):
        self.reset_project_storage(project_name='proj1')
        argv = ['app1', '--arg', 'arg1']
        _, _, stderr = self.exec_command(edit.COMMAND, argv)
        self.assertIn('project edit <project_name> [arguments]', stderr)
        self.assertIn('project edit: error: unrecognized arguments: --arg arg1', stderr)

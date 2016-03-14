# -*- coding: utf-8 -*-
#
# Copyright (c) 2015, ParaTools, Inc.
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
"""TAU compiler knowledgebase.

TAU Commander uses this knowledgebase to try to work out what kind of compiler
the user is using to build their code.  We can get away with this because TAU 
itself will take care of most of the version-specific details if only we get 
the configuration line correct.

TAU depends very strongly on compiler characteristics. Each TAU configuration
is only valid for a single compiler, TAU's feature set changes depending on compiler
family and version, TAU's configure script is easily confused by compilers with
strange names or unusual installation paths, etc.  In most cases, TAU doesn't even 
try to detect the compiler and trusts the user to specify the right "magic words" 
at configuration. Worse, TAU sometimes does probe the compiler to discover things
like MPI headers, except it does such a poor job that many time we get the wrong
answer or simply cause the configure script to fail entirely. This has been a major
painpoints for TAU users.

Unfortunately, compiler detection is very hard.  Projects like `SciPy`_ that depend 
on a compiler's stdout stream for compiler detection have more or less failed in this
since compiler messages are exceptionally difficult to parse.  `CMake`_ does a good
job by invoking the compiler command and parsing strings out of a compiled object to
detect compiler characteristcs, but that approach is complex and still breaks easily.

The TAU Commander compiler knowledgebase associates a compiler command (`icc`)
with characteristics like family (`Intel`) and role (`CC`).  Any compiler commands
intercepted by TAU Commander are matched against the database to discover their
characteristics, hence we do not need to invoke the compiler to identify it.

.. _SciPy: http://www.scipy.org/
.. _CMake: http://www.cmake.org/
"""

import os
from tau import logger
from tau.cf import TrackedInstance, KeyedRecord
from tau.error import InternalError 


LOGGER = logger.get_logger(__name__)


class CompilerRole(KeyedRecord):
    """Information about a compiler's role.
    
    A compiler role identifies how the compiler is used in the build process. All compilers
    play at least one *role* in their compiler family.  Many compilers can play multiple 
    roles, e.g. icpc can be a C++ compiler in the CXX role, a C compiler in the CC role, 
    or even a linker.  TAU Commander must identify a compiler's role so it can configure TAU.
    
    Attributes:
        keyword (str): Name of the compiler's role, e.g. 'CXX'.
        language (str): Name of the programming language corresponding to the compiler role, e.g. 'C++'.
        required (bool): True if this role must be filled to compile TAU, False otherwise.
    """
    
    __key__ = 'keyword'
    
    def __init__(self, keyword, language, required=False):
        self.keyword = keyword
        self.language = language
        self.required = required

    @classmethod
    def tau_required(cls):
        """Iterate over roles that must be filled to get TAU to compile."""
        for role in cls.all():
            if role.required:
                yield role


class CompilerInfo(TrackedInstance):
    """Information about a compiler.
    
    A compiler's basic information includes it's family (e.g. `Intel`) and role (e.g. CXX).
    The compiler might not be installed in the system.  See :any:`InstalledCompiler`.  
    
    Attributes:
        command (str): Command without path or arguments, e.g. 'icpc'
        family (CompilerFamily): The family this compiler belongs to.
        role (CompilerRole): This compiler's *primary* role in the family.
        short_descr (str): A short description for command line help.
    """

    def __init__(self, command, family, role):
        self.command = command
        self.family = family
        self.role = role
        self.short_descr = "%s %s compiler" % (family.name, role.language)
        
    def __str__(self):
        return self.command
    
    def __len__(self):
        return len(self.command)
    
    @classmethod
    def find(cls, command):
        """Find compiler info that matches the given command.
        
        If an exact match cannot be found then information for the longest command
        contained in the passed command is returned.
        
        Examples:
            find("gcc-4.7-x86_64") returns info for "gcc" from possible candidates ["gcc", "cc"].
        
        Args:
            command (str): Absolute or relative path to a compiler command.

        Returns:
            CompilerInfo: The matching compiler information.
            
        Raises:
            KeyError: No compiler information is known for the given command.
        """
        command = os.path.basename(command)
        for instance in cls.all():
            if instance.command == command:
                return instance
        # Guess that the longest string is the best match
        LOGGER.debug("No compiler info exactly matches %s, trying approximate match", command)
        candidates = [inst for inst in cls.all() if inst.command in command]
        if not candidates:
            raise KeyError
        match = max(candidates, key=len)
        LOGGER.debug("Matched info for %s to %s", match, command)
        return match


class CompilerFamily(KeyedRecord):
    """Information about a compiler family.
    
    A compiler's family creates associations between different compiler commands
    and assigns compilers to roles.  All compiler commands within a family accept
    similar arguments, and produce binary compatible object files.

    Attributes:
        name (str): Family name, e.g. "Intel".
        version_flags (list): Command line flags that show the compiler version.
        include_path_flags (list): Command line flags that add a directory to the compiler's include path. 
        library_path_flags (list): Command line flags that add a directory to the compiler's library path.
        link_library_flags (list): Command line flags that link a library.
        show_wrapper_flags (list): Command line flags that show the wrapped compiler's complete command line.
    """
    
    __key__ = 'name'
    
    # It is very dangerous to use lists as default values
    # but we do it here anyway because we copy the lists.
    # pylint: disable=dangerous-default-value
    def __init__(self, name,
                 version_flags=['--version'],
                 include_path_flags=['-I'], 
                 library_path_flags=['-L'], 
                 link_library_flags=['-l'],
                 show_wrapper_flags=[]):
        self._info_by_command = {}
        self._info_by_role = {}
        self.name = name
        self.version_flags = list(version_flags)
        self.include_path_flags = list(include_path_flags)
        self.library_path_flags = list(library_path_flags)
        self.link_library_flags = list(link_library_flags)
        self.show_wrapper_flags = list(show_wrapper_flags)

    @classmethod
    def all(cls):
        """Iterate over all compiler families.
        
        First value yielded is the host's preferred compiler family.
        Subsequent values can be in any order.
        
        Yields:
           A CompilerFamily object.
        """
        preferred = cls.preferred()
        yield preferred
        # Settle down pylint... the __instances__ member is created by the metaclass
        # pylint: disable=no-member
        for instance in cls.__instances__.itervalues():
            if instance is not preferred:
                yield instance
                
    @classmethod
    def preferred(cls):
        """Return the host's preferred compiler family."""
        from tau.cf.target import host
        return host.preferred_compilers()

    @classmethod
    def family_names(cls):
        """Return an alphabetical list of all known compiler family names."""
        return sorted([str(inst) for inst in cls.all()])
    
    def __contains__(self, item):
        """Tests if a command is in the family or a role has been filled.
        
        Args:
            item: The absolute path to a compiler command as a string, or a CompilerRole instance.
            
        Returns:
            If a string is given then return True if the string is the absolute path to a compiler
            that is in this family.  If a CompilerRole instance is given, return True if at least
            one compiler in the family fills the role.  Return False in all other cases.
        """        
        if isinstance(item, basestring):
            return item in self._info_by_command
        else:
            return item.keyword in self._info_by_role
    
    def __iter__(self):
        """Yield information about all compilers in the family.
        
        May yield zero, one, or more CompilerInfo objects for any role,
        but it will yield each CompilerInfo object only once.
        """
        for info in self._info_by_command.itervalues():
            yield info

    def add(self, role, *commands):
        """Register compiler commands in the given role.
        
        Commands should be ordered by preference.  For example, we prefer to build
        C++ codes with "c++" instead of "CC" so that case-insensitive file systems
        (looking at you OS X) don't try to use a C compiler for C++ codes. 
        
        Args:
            role (CompilerRole) Role these commands fill in the family.
            *commands: Command strings without arguments.
        """ 
        assert isinstance(role, CompilerRole)
        for command in commands:
            assert isinstance(command, basestring)
            if command in self._info_by_command:
                raise InternalError('Command %s already a member of %s' % (command, self.name))
            info = CompilerInfo(command, self, role)
            self._info_by_command[command] = info
            self._info_by_role.setdefault(role.keyword, []).append(info)
                
    def members(self, key):
        """Get the compiler with the specified command or all compilers in the specified role.
         
        Args:
            key: Compiler command string or CompilerRole instance
             
        Returns:
            If `key` is a string, return the CompilerInfo instance matching the command string.
            If `key` is a CompilerRole, return a list of CompilerInfo instances in the specified role. 
        """
        if isinstance(key, basestring):
            return self._info_by_command[key]
        else:
            return self._info_by_role[key.keyword]        


CC_ROLE = CompilerRole('CC', 'C', True)
CXX_ROLE = CompilerRole('CXX', 'C++', True)
FC_ROLE = CompilerRole('FC', 'Fortran', True)
UPC_ROLE = CompilerRole('UPC', 'Universal Parallel C')

SYSTEM_COMPILERS = CompilerFamily('System')
SYSTEM_COMPILERS.add(CC_ROLE, 'cc')
SYSTEM_COMPILERS.add(CXX_ROLE, 'c++', 'cxx', 'CC')
SYSTEM_COMPILERS.add(FC_ROLE, 'ftn', 'f90', 'f77')
SYSTEM_COMPILERS.add(UPC_ROLE, 'upc')

GNU_COMPILERS = CompilerFamily('GNU')
GNU_COMPILERS.add(CC_ROLE, 'gcc')
GNU_COMPILERS.add(CXX_ROLE, 'g++')
GNU_COMPILERS.add(FC_ROLE, 'gfortran')
GNU_COMPILERS.add(UPC_ROLE, 'gupc')

INTEL_COMPILERS = CompilerFamily('Intel')
INTEL_COMPILERS.add(CC_ROLE, 'icc')
INTEL_COMPILERS.add(CXX_ROLE, 'icpc')
INTEL_COMPILERS.add(FC_ROLE, 'ifort')

PGI_COMPILERS = CompilerFamily('PGI')
PGI_COMPILERS.add(CC_ROLE, 'pgcc')
PGI_COMPILERS.add(CXX_ROLE, 'pgc++', 'pgcxx', 'pgCC')
PGI_COMPILERS.add(FC_ROLE, 'pgf90', 'pgf77')

IBM_COMPILERS = CompilerFamily('IBM')
IBM_COMPILERS.add(CC_ROLE, 'xlc', )
IBM_COMPILERS.add(CXX_ROLE, 'xlc++', 'xlC')
IBM_COMPILERS.add(FC_ROLE, 'xlf')

CRAY_COMPILERS = CompilerFamily('Cray', show_wrapper_flags=['-craype-verbose'])
CRAY_COMPILERS.add(CC_ROLE, 'cc')
CRAY_COMPILERS.add(CXX_ROLE, 'CC', 'c++', 'cxx')
CRAY_COMPILERS.add(FC_ROLE, 'ftn', 'f90', 'f77')
CRAY_COMPILERS.add(UPC_ROLE, 'upc')

